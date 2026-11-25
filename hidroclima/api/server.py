"""Servidor FastAPI de HidroClima Studio."""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from hidroclima import __version__
from hidroclima.analysis.engine import run_project_analysis
from hidroclima.analysis.geohazards_env import compute_watershed_runoff_scs
from hidroclima.analysis.spatial import (
    compute_idw_weights,
    compute_thiessen_weights,
    parse_kml_or_geojson_bytes,
)
from hidroclima.analysis.thornthwaite import calculate_monthly_thornthwaite_standalone
from hidroclima.api.schemas import (
    LegacyImportRequest,
    MonthlyThornthwaiteRequest,
    ProjectAnalysisRequest,
    SaveProjectRequest,
    StationSearchRequest,
    SyncBridgeRequest,
    WatershedCalcRequest,
    WeightComputeRequest,
    YearMatrixUpdateRequest,
)
from hidroclima.bridges.ideam_dhime import import_dhime_file
from hidroclima.bridges.ideam_socrata import find_nearby_automatic_stations
from hidroclima.bridges.sync_manager import sync_stations_bridge
from hidroclima.config import BASE_DIR, IDF_REGIONS, SAMPLE_DIR, SOURCE_PRIORITY, STATIC_DIR
from hidroclima.db.database import ClimateDatabase
from hidroclima.db.legacy_importer import (
    export_legacy_cli_text,
    export_project_hclim,
    import_from_legacy_source,
    parse_legacy_cli_file,
    parse_project_file,
)
from hidroclima.exports.charts_mpl import (
    render_annual_trends_png,
    render_climograph_png,
    render_hyetograph_png,
    render_idf_curves_png,
    render_sgc_thresholds_png,
    render_spei_drought_png,
    render_water_balance_png,
)
from hidroclima.exports.export_docx import generate_docx_report
from hidroclima.exports.export_gis import (
    generate_geojson,
    generate_hyetograph_csv,
    generate_kml,
    generate_resultado_txt,
)
from hidroclima.exports.export_mepdg import generate_mepdg_txt, generate_mepdg_xml
from hidroclima.exports.export_pdf import generate_pdf_report
from hidroclima.exports.export_xlsx import generate_xlsx_workbook
from hidroclima.exports.manuals_pdf import resolve_manual_path


def create_app(db_path: Path | str | None = None) -> FastAPI:
    app = FastAPI(title="HidroClima Studio API", version=__version__)
    db = ClimateDatabase(db_path=db_path)
    app.state.db = db
    jobs: dict[str, dict[str, Any]] = {}
    jobs_lock = threading.Lock()

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def serve_index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="Interfaz web no encontrada.")
        return FileResponse(index_path)

    @app.get("/api/manuals/{manual_id}")
    def get_manual_pdf(manual_id: str) -> FileResponse:
        pdf_path = resolve_manual_path(manual_id)
        if pdf_path is None or not pdf_path.exists():
            raise HTTPException(status_code=404, detail=f"Manual '{manual_id}' no encontrado.")
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{pdf_path.name}"'},
        )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        stats = db.get_database_stats()
        detected_legacy = [
            str(p)
            for p in [BASE_DIR / "Instalador-Clima.zip", BASE_DIR / "Clima.rar", BASE_DIR / "SHC"]
            if p.exists()
        ]
        return {
            "status": "ok",
            "version": __version__,
            "stats": stats,
            "detected_legacy_sources": detected_legacy,
            "idf_regions": IDF_REGIONS,
            "source_priority": SOURCE_PRIORITY,
        }

    @app.get("/api/catalog/filters")
    def catalog_filters() -> dict[str, Any]:
        return {
            **db.list_catalog_filters(),
            "idf_regions": IDF_REGIONS,
            "source_priority": SOURCE_PRIORITY,
        }

    @app.post("/api/stations/search")
    def search_stations(req: StationSearchRequest) -> dict[str, Any]:
        route = [(float(p[0]), float(p[1])) for p in req.route_coords if len(p) >= 2]
        rows = db.search_stations(
            query=req.query,
            departamento=req.departamento,
            municipio=req.municipio,
            categoria=req.categoria,
            estado=req.estado,
            only_with_data=req.only_with_data,
            required_vars=req.required_vars or None,
            filter_year=req.filter_year,
            precip_min=req.precip_min,
            precip_max=req.precip_max,
            temp_min=req.temp_min,
            temp_max=req.temp_max,
            center_lat=req.center_lat,
            center_lon=req.center_lon,
            radius_km=req.radius_km,
            route_coords=route or None,
            route_buffer_km=req.route_buffer_km,
            limit=req.limit,
        )
        return {"count": len(rows), "stations": rows}

    @app.get("/api/stations/{code}")
    def station_detail(code: str) -> dict[str, Any]:
        detail = db.get_station_detail(code)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Estación {code} no encontrada.")
        nearby_auto = []
        if detail.get("latitud") is not None and detail.get("longitud") is not None:
            nearby_auto = find_nearby_automatic_stations(
                db, float(detail["latitud"]), float(detail["longitud"]), radius_km=25.0, limit=5
            )
        detail["nearby_automatic"] = nearby_auto
        return detail

    @app.get("/api/stations/{code}/matrix")
    def get_matrix(code: str, var_id: int = 1, year: int = 2024) -> dict[str, Any]:
        return db.get_year_matrix(code, var_id=var_id, year=year)

    @app.put("/api/stations/{code}/matrix")
    def put_matrix(code: str, req: YearMatrixUpdateRequest, var_id: int = 1, year: int = 2024) -> dict[str, Any]:
        saved = db.save_year_matrix(code, var_id=var_id, year=year, matrix=req.matrix, source=req.source)
        return {"saved": saved, "station_code": code, "var_id": var_id, "year": year}

    @app.post("/api/spatial/parse-route")
    async def parse_route(
        file: UploadFile | None = File(default=None),
        raw_text: str | None = Form(default=None),
    ) -> dict[str, Any]:
        if file is not None:
            content = await file.read()
            coords = parse_kml_or_geojson_bytes(content, file.filename or "")
        elif raw_text:
            coords = parse_kml_or_geojson_bytes(raw_text.encode("utf-8"), "pasted.kml")
        else:
            raise HTTPException(status_code=400, detail="Debe enviar un archivo KML/KMZ/GeoJSON o texto de coordenadas.")
        if not coords:
            raise HTTPException(status_code=400, detail="No se encontraron coordenadas válidas en el archivo o texto.")
        return {"count": len(coords), "route_coords": [[lat, lon] for lat, lon in coords]}

    @app.post("/api/spatial/weights")
    def compute_weights(req: WeightComputeRequest) -> dict[str, Any]:
        stns = [s for s in db.get_stations_by_codes(req.station_codes) if s.get("latitud") is not None]
        if not stns:
            return {"weights": {}}
        if req.method == "equal":
            w = round(1.0 / len(stns), 6)
            return {"weights": {s["codigo"]: w for s in stns}}
        route = [(float(p[0]), float(p[1])) for p in req.route_coords if len(p) >= 2]
        if req.method == "thiessen":
            return {"weights": compute_thiessen_weights(stns, polyline=route or None, buffer_km=req.buffer_km)}
        return {"weights": compute_idw_weights(stns, polyline=route or None)}

    @app.post("/api/analysis/run")
    def run_analysis(req: ProjectAnalysisRequest) -> dict[str, Any]:
        try:
            return run_project_analysis(db, req.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/analysis/watershed")
    def calc_watershed(req: WatershedCalcRequest) -> dict[str, Any]:
        return compute_watershed_runoff_scs(
            idf_result=req.idf_result,
            area_km2=req.area_km2,
            length_m=req.length_m,
            slope_pct=req.slope_pct,
            curve_number=req.curve_number,
            runoff_coeff=req.runoff_coeff,
        )

    @app.post("/api/analysis/thornthwaite-monthly")
    def thornthwaite_monthly(req: MonthlyThornthwaiteRequest) -> dict[str, Any]:
        try:
            return calculate_monthly_thornthwaite_standalone(
                monthly_precip=req.monthly_precip,
                monthly_temp=req.monthly_temp,
                lat_deg=req.lat_deg,
                soil_max_reserve_mm=req.soil_max_reserve_mm,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/analysis/watershed")
    def calc_watershed(req: WatershedCalcRequest) -> dict[str, Any]:
        return compute_watershed_runoff_scs(
            idf_result=req.idf_result,
            area_km2=req.area_km2,
            length_m=req.length_m,
            slope_pct=req.slope_pct,
            curve_number=req.curve_number,
            runoff_coeff=req.runoff_coeff,
        )

    @app.post("/api/exports/{fmt}")
    def export_report(fmt: str, req: ProjectAnalysisRequest) -> Response:
        analysis = run_project_analysis(db, req.model_dump())
        if not analysis.get("has_data"):
            raise HTTPException(status_code=400, detail=analysis.get("message", "Sin datos para exportar."))

        safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (req.name or "HidroClimaStudio")).strip("_") or "HidroClimaStudio"
        route = [(float(p[0]), float(p[1])) for p in req.route_coords if len(p) >= 2]

        fmt_l = fmt.lower()
        if fmt_l == "pdf":
            data = generate_pdf_report(analysis)
            return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe_name}_Informe.pdf"'})
        if fmt_l == "docx":
            data = generate_docx_report(analysis)
            return Response(
                data,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="{safe_name}_Informe.docx"'},
            )
        if fmt_l == "xlsx":
            data = generate_xlsx_workbook(analysis)
            return Response(
                data,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{safe_name}_Datos.xlsx"'},
            )
        if fmt_l == "mepdg_xml":
            txt = generate_mepdg_xml(analysis)
            return Response(txt.encode("utf-8"), media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{safe_name}_MEPDG.xml"'})
        if fmt_l == "mepdg_txt":
            txt = generate_mepdg_txt(analysis)
            return Response(txt.encode("utf-8"), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{safe_name}_mepdg.txt"'})
        if fmt_l == "geojson":
            txt = generate_geojson(analysis, route or None)
            return Response(txt.encode("utf-8"), media_type="application/geo+json", headers={"Content-Disposition": f'attachment; filename="{safe_name}.geojson"'})
        if fmt_l == "kml":
            txt = generate_kml(analysis, route or None)
            return Response(txt.encode("utf-8"), media_type="application/vnd.google-earth.kml+xml", headers={"Content-Disposition": f'attachment; filename="{safe_name}.kml"'})
        if fmt_l == "csv_hyetograph":
            txt = generate_hyetograph_csv(analysis)
            return Response(txt.encode("utf-8"), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{safe_name}_Hietograma.csv"'})
        if fmt_l == "txt":
            txt = generate_resultado_txt(analysis)
            return Response(txt.encode("utf-8"), media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{safe_name}_Reporte.txt"'})
        if fmt_l == "hclim":
            txt = export_project_hclim(req.model_dump())
            return Response(txt.encode("utf-8"), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{safe_name}.hclim"'})
        if fmt_l == "cli":
            txt = export_legacy_cli_text(req.model_dump())
            return Response(txt.encode("latin1", errors="replace"), media_type="text/plain", headers={"Content-Disposition": f'attachment; filename="{safe_name}.cli"'})
        if fmt_l == "png_climograph":
            return Response(render_climograph_png(analysis), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{safe_name}_Climograma.png"'})
        if fmt_l == "png_balance":
            return Response(render_water_balance_png(analysis), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{safe_name}_BalanceHidrico.png"'})
        if fmt_l == "png_trends":
            return Response(render_annual_trends_png(analysis), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{safe_name}_Tendencias.png"'})
        if fmt_l == "png_idf":
            return Response(render_idf_curves_png(analysis), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{safe_name}_CurvasIDF.png"'})
        if fmt_l == "png_hyetograph":
            return Response(render_hyetograph_png(analysis), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{safe_name}_Hietograma.png"'})
        if fmt_l == "png_sgc_thresholds":
            return Response(render_sgc_thresholds_png(analysis), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{safe_name}_Geotecnia_SGC.png"'})
        if fmt_l == "png_spei_drought":
            return Response(render_spei_drought_png(analysis), media_type="image/png", headers={"Content-Disposition": f'attachment; filename="{safe_name}_SPEI_Erosividad.png"'})
        raise HTTPException(status_code=400, detail=f"Formato de exportación no soportado: {fmt}")

    @app.post("/api/bridges/sync")
    def bridge_sync(req: SyncBridgeRequest) -> dict[str, Any]:
        return sync_stations_bridge(
            db=db,
            station_codes=req.station_codes,
            providers=req.providers,
            start_year=req.start_year,
            end_year=req.end_year,
            update_catalog=req.update_catalog,
        )

    @app.post("/api/bridges/import-dhime")
    async def bridge_import_dhime(
        file: UploadFile = File(...),
        default_station_code: str | None = Form(default=None),
        default_var_id: int | None = Form(default=None),
    ) -> dict[str, Any]:
        content = await file.read()
        try:
            return import_dhime_file(
                db=db,
                content=content,
                filename=file.filename or "dhime.csv",
                default_station_code=default_station_code,
                default_var_id=default_var_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/analysis/watershed")
    def calc_watershed(req: WatershedCalcRequest) -> dict[str, Any]:
        return compute_watershed_runoff_scs(
            idf_result=req.idf_result,
            area_km2=req.area_km2,
            length_m=req.length_m,
            slope_pct=req.slope_pct,
            curve_number=req.curve_number,
            runoff_coeff=req.runoff_coeff,
        )

    @app.post("/api/bridges/import-legacy")
    def bridge_import_legacy(req: LegacyImportRequest) -> dict[str, Any]:
        src = Path(req.source_path)
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"No existe la ruta: {req.source_path}")
        job_id = uuid.uuid4().hex[:10]
        with jobs_lock:
            jobs[job_id] = {"id": job_id, "status": "running", "progress": 0, "message": "Iniciando importación...", "result": None, "error": None}

        def _worker() -> None:
            def _cb(cur: int, tot: int, msg: str) -> None:
                with jobs_lock:
                    jobs[job_id]["progress"] = int(100 * cur / max(1, tot))
                    jobs[job_id]["message"] = msg

            try:
                res = import_from_legacy_source(
                    db=db,
                    source_path=src,
                    station_filter=set(req.station_codes) if req.station_codes else None,
                    year_min=req.year_min,
                    year_max=req.year_max,
                    import_catalog=req.import_catalog,
                    progress_cb=_cb,
                )
                with jobs_lock:
                    jobs[job_id]["status"] = "completed"
                    jobs[job_id]["progress"] = 100
                    jobs[job_id]["message"] = f"Completado: {res['records_imported']:,} registros importados."
                    jobs[job_id]["result"] = res
            except Exception as exc:
                with jobs_lock:
                    jobs[job_id]["status"] = "failed"
                    jobs[job_id]["error"] = str(exc)
                    jobs[job_id]["message"] = f"Error: {exc}"

        threading.Thread(target=_worker, daemon=True).start()
        return {"job_id": job_id, "status": "running"}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        with jobs_lock:
            job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
        return job

    @app.get("/api/projects")
    def list_projects() -> dict[str, Any]:
        projects = db.list_projects()
        # Incluir ejemplo demostrativo incluido (Bogotá D.C.) si el usuario aún no ha guardado proyectos
        samples = []
        ejemplo_path = SAMPLE_DIR / "Ejemplo_Bogota.hclim"
        if ejemplo_path.exists():
            parsed = parse_project_file(ejemplo_path.read_text(encoding="utf-8", errors="replace"))
            samples.append({
                "id": "sample_bogota",
                "name": parsed["name"] or "Ejemplo Bogotá D.C. (El Dorado – Cerros Orientales)",
                "description": parsed["description"] or "Corredor hidrometeorológico y geotécnico Bogotá D.C. 2005–2025",
                "location": parsed["location"] or "Bogotá D.C., Colombia",
                "is_sample": True,
                "config": parsed,
            })
        return {"projects": projects, "samples": samples}

    @app.post("/api/projects")
    def save_project(req: SaveProjectRequest) -> dict[str, Any]:
        pid = req.id or uuid.uuid4().hex[:12]
        db.save_project(pid, req.name, req.description, req.location, req.config)
        return {"id": pid, "status": "saved"}

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str) -> dict[str, Any]:
        return {"deleted": db.delete_project(project_id)}

    @app.post("/api/projects/import")
    @app.post("/api/projects/import-cli")
    async def import_project_file(file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin1", errors="replace")
        parsed = parse_project_file(text)
        return {"project": parsed}

    return app


_default_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    global _default_app
    if name == "app":
        if _default_app is None:
            _default_app = create_app()
        return _default_app
    raise AttributeError(name)
