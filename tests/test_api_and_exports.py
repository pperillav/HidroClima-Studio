"""Pruebas de integración FastAPI, validación estructural de exportaciones (PDF, DOCX, XLSX, XML, GIS) y editor."""

from __future__ import annotations

import io
import json
from xml.etree import ElementTree as ET

import docx
import openpyxl
from fastapi.routing import APIRoute
from lxml import etree
from pypdf import PdfReader

from hidroclima.api.schemas import (
    MonthlyThornthwaiteRequest,
    ProjectAnalysisRequest,
    SaveProjectRequest,
    StationSearchRequest,
    WatershedCalcRequest,
    WeightComputeRequest,
    YearMatrixUpdateRequest,
)
from hidroclima.api.server import create_app


def _find_route(app, path: str, method: str = "GET"):
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method.upper() in route.methods:
            return route.endpoint
    raise AssertionError(f"Ruta no encontrada: {method} {path}")


def test_full_api_workflow_and_exports(tmp_path):
    app = create_app(db_path=tmp_path / "runtime.db")

    # 1. Health & bootstrap automático
    health = _find_route(app, "/api/health", "GET")()
    assert health["stats"]["total_stations"] == 8973
    assert health["stats"]["stations_with_data"] >= 2

    # 2. Catálogo y búsqueda Bogotá D.C.
    filters = _find_route(app, "/api/catalog/filters", "GET")()
    assert len(filters["departamentos"]) == 33
    assert len(filters["municipios"]) >= 1100

    search_res = _find_route(app, "/api/stations/search", "POST")(StationSearchRequest(query="21205791"))
    assert search_res["count"] >= 1
    assert search_res["stations"][0]["codigo"] == "21205791"

    detail = _find_route(app, "/api/stations/{code}", "GET")("21205791")
    assert detail["codigo"] == "21205791"
    assert len(detail["series_summary"]) >= 1

    # 3. Cálculo de pesos espaciales
    weights_res = _find_route(app, "/api/spatial/weights", "POST")(
        WeightComputeRequest(station_codes=["21205791", "21205580"], method="idw")
    )
    assert abs(sum(weights_res["weights"].values()) - 1.0) < 1e-4

    # 4. Análisis completo Ejemplo Bogotá D.C. (21205791 + 21205580)
    req = ProjectAnalysisRequest(
        name="Prueba Bogotá D.C. Integral",
        description="Validación automática multidisciplinaria",
        location="Bogotá D.C., Colombia",
        stations=[
            {"codigo": "21205791", "weight": 0.5},
            {"codigo": "21205580", "weight": 0.5},
        ],
        end_year=2024,
        last_n_years=10,
        soil_max_reserve_mm=100.0,
        water_table_m=10.0,
        etp_method="penman_monteith",
        study_profile="integral",
        idf_method="invias",
        hyetograph_tr=10,
        hyetograph_duration_min=60,
    )
    analysis = _find_route(app, "/api/analysis/run", "POST")(req)
    assert analysis["has_data"] is True
    assert len(analysis["monthly_summary"]) == 12
    assert len(analysis["daily_climatology"]) == 365
    assert analysis["pavement"]["tmap_c"] is not None
    assert analysis["pavement"]["pma_mm"] > 500
    assert analysis["pavement"]["invias_pavement_region"]["code"].startswith("R")
    assert len(analysis["hydrology_idf"]["empirical_points"]) >= 2
    assert "caldas_lang" in analysis["classifications"]
    assert "holdridge" in analysis["classifications"]
    assert "koppen_geiger" in analysis["classifications"]
    assert "ena_aridity" in analysis["classifications"]
    assert analysis["hydrology_idf"]["available"] is True
    assert len(analysis["hydrology_idf"]["distributions"]) == 4
    assert len(analysis["hydrology_idf"]["hyetograph"]) == 12
    assert len(analysis["hydrology_idf"]["normative_return_periods"]) >= 8
    assert analysis["geohazards_sgc"]["available"] is True
    assert analysis["erosivity"]["available"] is True
    assert analysis["erosivity"]["r_factor_mfi"] > 0
    assert analysis["drought"]["available"] is True
    assert analysis["watershed"]["available"] is True
    assert analysis["watershed"]["tc_kirpich_min"] >= 5.0

    # Recálculo instantáneo de cuenca INVIAS / SCS-CN
    ws_recalc = _find_route(app, "/api/analysis/watershed", "POST")(
        WatershedCalcRequest(
            idf_result=analysis["hydrology_idf"],
            area_km2=2.5,
            length_m=1500.0,
            slope_pct=4.0,
            curve_number=82.0,
            runoff_coeff=0.65,
        )
    )
    assert ws_recalc["available"] is True
    assert ws_recalc["area_km2"] == 2.5
    assert ws_recalc["tc_kirpich_min"] > analysis["watershed"]["tc_kirpich_min"]

    # 5. Probar TODAS las 17 exportaciones y validar su estructura interna real
    export_ep = _find_route(app, "/api/exports/{fmt}", "POST")

    # PDF válido con texto y múltiples páginas
    pdf_resp = export_ep("pdf", req)
    assert pdf_resp.status_code == 200
    reader = PdfReader(io.BytesIO(pdf_resp.body))
    assert len(reader.pages) >= 6
    full_pdf_txt = "\n".join(p.extract_text() or "" for p in reader.pages)
    assert "Caldas-Lang" in full_pdf_txt
    assert "Holdridge" in full_pdf_txt
    assert "TMAP" in full_pdf_txt
    assert "PMA" in full_pdf_txt
    assert "RAS" in full_pdf_txt
    assert "GEOTECNIA SGC" in full_pdf_txt
    assert "RUSLE" in full_pdf_txt

    # Word .docx válido con tablas e imágenes
    docx_resp = export_ep("docx", req)
    assert docx_resp.status_code == 200
    doc_obj = docx.Document(io.BytesIO(docx_resp.body))
    assert len(doc_obj.tables) >= 8
    assert len(doc_obj.inline_shapes) >= 6

    # Excel .xlsx válido con 10 hojas, formulación viva y gráficos nativos
    xlsx_resp = export_ep("xlsx", req)
    assert xlsx_resp.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_resp.body))
    assert set(wb.sheetnames) == {
        "Resumen_Ejecutivo",
        "Estaciones",
        "Balance_Mensual",
        "Pavimentos_TMAP",
        "Serie_Anual",
        "Promedios_Diarios_365",
        "IDF_Frecuencia_RAS",
        "Calidad_Homogeneidad_ETCCDI",
        "Geotecnia_SGC_Lluvias",
        "Cuenca_RUSLE_Sequias",
    }
    assert str(wb["Balance_Mensual"]["C17"].value).startswith("=SUM(")
    assert str(wb["Pavimentos_TMAP"]["C4"].value).startswith("=10^(")
    assert str(wb["Pavimentos_TMAP"]["B18"].value).startswith("=19.66+")
    assert str(wb["Pavimentos_TMAP"]["B21"].value).startswith("=IF(")
    assert str(wb["Resumen_Ejecutivo"]["B9"].value) == "=Pavimentos_TMAP!B19"
    assert str(wb["Geotecnia_SGC_Lluvias"]["H2"].value).startswith("=(25400/F2)")
    assert str(wb["Cuenca_RUSLE_Sequias"]["B23"].value).startswith("=IF(B20<55")
    assert str(wb["Cuenca_RUSLE_Sequias"]["G9"].value).startswith("=MAX(5,0.01947")
    assert len(wb["Balance_Mensual"]._charts) == 2
    assert len(wb["Cuenca_RUSLE_Sequias"]._charts) == 1

    # MEPDG XML bien formado
    xml_resp = export_ep("mepdg_xml", req)
    assert xml_resp.status_code == 200
    xml_root = etree.fromstring(xml_resp.body)
    assert xml_root.tag == "ClimateObject"

    # GeoJSON y KML válidos
    gj_resp = export_ep("geojson", req)
    gj = json.loads(gj_resp.body.decode("utf-8"))
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) >= 2

    kml_resp = export_ep("kml", req)
    kml_root = ET.fromstring(kml_resp.body)
    assert kml_root.tag.endswith("kml")

    # CSV Hietograma, MEPDG TXT, TXT, Proyecto .hclim y 7 PNGs
    assert "Lamina_mm" in export_ep("csv_hyetograph", req).body.decode("utf-8")
    assert "# ARCHIVO PARA MEPDG" in export_ep("mepdg_txt", req).body.decode("utf-8")
    assert "HIDROCLIMA STUDIO" in export_ep("txt", req).body.decode("utf-8")
    hclim_obj = json.loads(export_ep("hclim", req).body.decode("utf-8"))
    assert hclim_obj["format"] == "hidroclima-project"
    assert hclim_obj["name"] == "Prueba Bogotá D.C. Integral"
    assert "[Proyecto]" in export_ep("cli", req).body.decode("latin1")
    for png_fmt in (
        "png_climograph", "png_balance", "png_trends", "png_idf", "png_hyetograph",
        "png_sgc_thresholds", "png_spei_drought",
    ):
        p_resp = export_ep(png_fmt, req)
        assert p_resp.status_code == 200
        assert p_resp.body.startswith(b"\x89PNG")

    # 6. Calculadora Thornthwaite mensual independiente (Bogotá D.C.)
    r_tw = _find_route(app, "/api/analysis/thornthwaite-monthly", "POST")(
        MonthlyThornthwaiteRequest(
            lat_deg=4.71,
            soil_max_reserve_mm=100.0,
            monthly_precip=[34, 48, 72, 108, 102, 58, 44, 46, 70, 128, 114, 62],
            monthly_temp=[13.8, 14.0, 14.2, 14.3, 14.2, 14.0, 13.7, 13.8, 13.9, 13.8, 13.8, 13.7],
        )
    )
    assert r_tw["thornthwaite_index_pct"] > 0.0

    # 7. Editor matriz 12x31 y proyectos CRUD
    get_mat = _find_route(app, "/api/stations/{code}/matrix", "GET")
    put_mat = _find_route(app, "/api/stations/{code}/matrix", "PUT")
    mat_data = get_mat("21205791", var_id=1, year=2024)
    mat = mat_data["matrix"]
    mat[0][0] = 42.5
    put_mat("21205791", YearMatrixUpdateRequest(matrix=mat, source="Manual"), var_id=1, year=2024)
    mat_data2 = get_mat("21205791", var_id=1, year=2024)
    assert mat_data2["matrix"][0][0] == 42.5
    assert mat_data2["active_source"] == "Manual"

    save_proj = _find_route(app, "/api/projects", "POST")
    list_proj = _find_route(app, "/api/projects", "GET")
    del_proj = _find_route(app, "/api/projects/{project_id}", "DELETE")
    saved = save_proj(SaveProjectRequest(name="Test Proyecto", config=req.model_dump()))
    projs = list_proj()
    assert any(p["id"] == saved["id"] for p in projs["projects"])
    assert del_proj(saved["id"])["deleted"] is True

    # 8. Archivo HTML estático servido correctamente y manuales PDF oficiales disponibles
    idx_resp = _find_route(app, "/", "GET")()
    assert idx_resp.path.name == "index.html"
    idx_html = idx_resp.path.read_text(encoding="utf-8")
    assert "desktopMenubar" in idx_html and "helpModal" in idx_html

    man_ep = _find_route(app, "/api/manuals/{manual_id}", "GET")
    for mid in ("general", "tutorial", "scientific", "reference"):
        m_resp = man_ep(mid)
        assert m_resp.path.exists()
        assert m_resp.path.read_bytes()[:4] == b"%PDF"
