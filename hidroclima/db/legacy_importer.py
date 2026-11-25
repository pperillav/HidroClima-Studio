"""Importador de series históricas (.zip / .rar / SHC/*.dat) y archivos de proyecto (.hclim y compatibilidad .cli)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

import numpy as np

from hidroclima.config import DAYS_IN_MONTH_LEAP
from hidroclima.db.database import SLOTS_PER_YEAR, ClimateDatabase, compute_year_stats, pack_372, utc_now_iso

ProgressCallback = Callable[[int, int, str], None]


def parse_legacy_cli_file(text: str) -> dict[str, Any]:
    """Parsea un archivo de proyecto hidrológico-climático en formato .cli."""
    lines = [ln.strip() for ln in text.splitlines()]
    meta: dict[int, str] = {}
    stations: list[dict[str, Any]] = []
    in_ec = False
    cur_code: str | None = None
    i = 0
    while i < len(lines):
        tok = lines[i]
        if tok == "[InicioEC]":
            in_ec = True
            i += 1
            continue
        if tok == "[FinEC]":
            in_ec = False
            i += 1
            continue
        if tok.startswith("["):
            i += 1
            continue
        if tok.isdigit():
            key = int(tok)
            val = lines[i + 1] if i + 1 < len(lines) else ""
            if in_ec:
                if key == 51:
                    cur_code = val.strip()
                elif key == 52 and cur_code:
                    try:
                        w = float(val.replace(",", "."))
                    except ValueError:
                        w = 1.0
                    stations.append({"codigo": cur_code, "weight": w})
                    cur_code = None
            else:
                meta[key] = val.strip()
            i += 2
            continue
        i += 1

    def _float(k: int, default: float) -> float:
        try:
            return float(meta.get(k, "").replace(",", "."))
        except ValueError:
            return default

    def _int(k: int, default: int) -> int:
        try:
            return int(float(meta.get(k, "").replace(",", ".")))
        except ValueError:
            return default

    method_code = _int(50, 2)
    return {
        "name": meta.get(1) or "Proyecto Importado (.hclim)",
        "description": meta.get(2) or "",
        "location": meta.get(3) or "",
        "soil_max_reserve_mm": _float(25, 100.0),
        "end_year": _int(26, 2025),
        "last_n_years": _int(27, 10),
        "etp_method": "thornthwaite" if method_code == 1 else "penman_monteith",
        "water_table_m": 10.0,
        "stations": stations,
    }


def parse_project_file(text: str) -> dict[str, Any]:
    """Parsea un archivo de proyecto nativo (.hclim JSON) o heredado en formato .cli."""
    stripped = text.lstrip()
    if stripped.startswith("{"):
        data = json.loads(stripped)
        return {
            "name": data.get("name") or "Proyecto Importado (.hclim)",
            "description": data.get("description") or "",
            "location": data.get("location") or "",
            "soil_max_reserve_mm": float(data.get("soil_max_reserve_mm", 100.0)),
            "water_table_m": float(data.get("water_table_m", 10.0)),
            "end_year": int(data.get("end_year", 2026)),
            "last_n_years": int(data.get("last_n_years", 0)),
            "etp_method": str(data.get("etp_method") or "penman_monteith"),
            "study_profile": str(data.get("study_profile") or "integral"),
            "idf_method": str(data.get("idf_method") or "invias"),
            "idf_region": data.get("idf_region"),
            "hyetograph_tr": int(data.get("hyetograph_tr", 10)),
            "hyetograph_duration_min": int(data.get("hyetograph_duration_min", 60)),
            "watershed_area_km2": float(data.get("watershed_area_km2", 1.0)),
            "watershed_length_m": float(data.get("watershed_length_m", 800.0)),
            "watershed_slope_pct": float(data.get("watershed_slope_pct", 5.0)),
            "curve_number": float(data.get("curve_number", 75.0)),
            "runoff_coeff": float(data.get("runoff_coeff", 0.5)),
            "sgc_r3_intercept": float(data.get("sgc_r3_intercept", 70.0)),
            "sgc_r15_slope": float(data.get("sgc_r15_slope", 0.47)),
            "route_coords": data.get("route_coords") or [],
            "stations": data.get("stations") or [],
        }
    return parse_legacy_cli_file(text)


def export_project_hclim(project: dict[str, Any]) -> str:
    """Genera el contenido de un archivo de proyecto nativo .hclim en formato JSON estructurado."""
    payload = {
        "format": "hidroclima-project",
        "version": "1.0.0",
        "name": project.get("name", ""),
        "description": project.get("description", ""),
        "location": project.get("location", ""),
        "soil_max_reserve_mm": float(project.get("soil_max_reserve_mm", 100.0)),
        "water_table_m": float(project.get("water_table_m", 10.0)),
        "end_year": int(project.get("end_year", 2026)),
        "last_n_years": int(project.get("last_n_years", 0)),
        "etp_method": project.get("etp_method", "penman_monteith"),
        "study_profile": project.get("study_profile", "integral"),
        "idf_method": project.get("idf_method", "invias"),
        "idf_region": project.get("idf_region"),
        "hyetograph_tr": int(project.get("hyetograph_tr", 10)),
        "hyetograph_duration_min": int(project.get("hyetograph_duration_min", 60)),
        "watershed_area_km2": float(project.get("watershed_area_km2", 1.0)),
        "watershed_length_m": float(project.get("watershed_length_m", 800.0)),
        "watershed_slope_pct": float(project.get("watershed_slope_pct", 5.0)),
        "curve_number": float(project.get("curve_number", 75.0)),
        "runoff_coeff": float(project.get("runoff_coeff", 0.5)),
        "sgc_r3_intercept": float(project.get("sgc_r3_intercept", 70.0)),
        "sgc_r15_slope": float(project.get("sgc_r15_slope", 0.47)),
        "stations": project.get("stations", []),
        "route_coords": project.get("route_coords", []),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def export_legacy_cli_text(project: dict[str, Any]) -> str:
    """Genera el contenido de un archivo de proyecto en formato .cli."""
    method_code = 1 if project.get("etp_method") == "thornthwaite" else 2
    lines = [
        "[Proyecto]",
        " 1 ",
        str(project.get("name", "")),
        " 2 ",
        str(project.get("description", "")),
        " 3 ",
        str(project.get("location", "")),
        " 25 ",
        f" {int(round(float(project.get('soil_max_reserve_mm', 100))))} ",
        " 26 ",
        f" {int(project.get('end_year', 2025))} ",
        " 27 ",
        f" {int(project.get('last_n_years', 10))} ",
        " 50 ",
        f" {method_code} ",
        "[InicioEC]",
    ]
    for st in project.get("stations", []):
        lines.append(" 51 ")
        lines.append(str(st.get("codigo", "")).strip())
        lines.append(" 52 ")
        lines.append(f" {st.get('weight', 1)} ")
    lines.extend(["[FinEC]", "[FinProyecto]", ""])
    return "\r\n".join(lines)


def import_catalog_ini_files(db: ClimateDatabase, source_dir: Path) -> dict[str, int]:
    """Importa Departamento.ini, Municipio.ini, Categoria.ini y EstClima.ini hacia SQLite."""
    db.init_schema()
    counts: dict[str, int] = {}
    now = utc_now_iso()

    def _read_lines(name: str) -> list[list[str]]:
        p = source_dir / name
        if not p.exists():
            return []
        with open(p, encoding="latin1", errors="replace") as fh:
            rows = []
            for idx, line in enumerate(fh):
                if idx == 0 or not line.strip():
                    continue
                rows.append([col.replace("\xa0", " ").strip() for col in line.rstrip("\r\n").split(";")])
            return rows

    with db.connect() as conn:
        deptos = [(r[0].zfill(2) if r[0].isdigit() else r[0], r[1]) for r in _read_lines("Departamento.ini") if len(r) >= 2]
        if deptos:
            conn.executemany("INSERT OR REPLACE INTO departamentos (codigo, nombre) VALUES (?,?)", deptos)
        counts["departamentos"] = len(deptos)

        muns = [
            (r[0].zfill(5) if r[0].isdigit() else r[0], r[1], r[2].zfill(2) if r[2].isdigit() else r[2])
            for r in _read_lines("Municipio.ini")
            if len(r) >= 3
        ]
        if muns:
            conn.executemany("INSERT OR REPLACE INTO municipios (codigo, nombre, departamento_codigo) VALUES (?,?,?)", muns)
        counts["municipios"] = len(muns)

        cats = [(r[0], r[1]) for r in _read_lines("Categoria.ini") if len(r) >= 2]
        if cats:
            conn.executemany("INSERT OR REPLACE INTO categorias (codigo, descripcion) VALUES (?,?)", cats)
        counts["categorias"] = len(cats)

        est_rows_raw = _read_lines("EstClima.ini")
        est_rows = []
        for r in est_rows_raw:
            if len(r) < 18:
                continue
            code = r[0].strip()
            mun = r[3].strip()
            if mun.isdigit():
                mun = mun.zfill(5)
            depto = mun[:2] if len(mun) >= 2 else ""

            def _to_float(val: str) -> float | None:
                if not val:
                    return None
                try:
                    return float(val.replace(",", "."))
                except ValueError:
                    return None

            est_rows.append(
                (
                    code,
                    code.zfill(10),
                    r[1].strip(),
                    r[2].strip(),
                    mun,
                    depto,
                    r[4].strip(),
                    r[5].strip(),
                    r[6].strip(),
                    r[7].strip(),
                    r[8].strip(),
                    r[9].strip(),
                    r[10].strip(),
                    r[11].strip(),
                    r[12].strip(),
                    r[13].strip(),
                    _to_float(r[14]),
                    _to_float(r[15]),
                    _to_float(r[16]),
                    r[17].strip(),
                    "IDEAM-Legacy",
                    now,
                )
            )
        if est_rows:
            conn.executemany(
                """
                INSERT OR REPLACE INTO estaciones (
                    codigo, codigo_ideam_10, nombre, categoria_codigo, municipio_codigo,
                    departamento_codigo, centro_poblado, entidad, corriente,
                    area_hidrografica, area_operativa, zona_hidrografica, subzona_hidrografica,
                    tecnologia, fecha_instalacion, fecha_suspension, latitud, longitud, altitud,
                    estado, source, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                est_rows,
            )
        counts["estaciones"] = len(est_rows)
    return counts


def parse_shc_dat_file(
    dat_path: Path,
    station_filter: set[str] | None = None,
) -> list[tuple[str, int, int, str, bytes, int, float | None, float | None, float | None, float | None]]:
    """Parsea un archivo SHC/climaYYYY.dat (registros de 4096 bytes) a tuplas listas para SQLite."""
    buf = dat_path.read_bytes()
    out = []
    now = utc_now_iso()
    for off in range(0, len(buf) - 4095, 4096):
        rec = buf[off : off + 4096]
        if rec[4095] == ord("*"):  # marcado como borrado en formato legacy
            continue
        stn = rec[:15].decode("latin1", errors="ignore").strip()
        if not stn:
            continue
        if station_filter is not None and stn not in station_filter:
            continue
        var_raw = rec[15:23].decode("latin1", errors="ignore").strip()
        yr_raw = rec[27:31].decode("latin1", errors="ignore").strip()
        if not var_raw.isdigit() or not yr_raw.isdigit():
            continue
        var_id = int(var_raw)
        year = int(yr_raw)

        arr = np.full(SLOTS_PER_YEAR, np.nan, dtype=np.float32)
        for m in range(12):
            m_off = 295 + m * 256
            max_d = DAYS_IN_MONTH_LEAP[m]
            for d in range(max_d):
                raw_val = rec[m_off + d * 8 : m_off + (d + 1) * 8].strip()
                if raw_val:
                    try:
                        arr[m * 31 + d] = float(raw_val.replace(b",", b"."))
                    except ValueError:
                        pass

        vc, s_sum, s_mean, s_max, s_min = compute_year_stats(arr, year)
        if vc == 0:
            continue
        out.append((stn, var_id, year, "IDEAM-Legacy", now, pack_372(arr), vc, s_sum, s_mean, s_max, s_min))
    return out


def _extract_archive_with_system_tools(archive_path: Path, dest_dir: Path, members_pattern: str | None = None) -> None:
    """Extrae archivos .rar o .zip usando 7z si está instalado o bsdtar nativo de Windows."""
    seven_z = shutil.which("7z") or (r"C:\Program Files\7-Zip\7z.exe" if Path(r"C:\Program Files\7-Zip\7z.exe").exists() else None)
    if seven_z:
        cmd = [seven_z, "x", str(archive_path), f"-o{dest_dir}", "-y"]
        if members_pattern:
            cmd.append(members_pattern)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return

    tar_bin = shutil.which("tar") or r"C:\Windows\System32\tar.exe"
    if not Path(tar_bin).exists():
        raise RuntimeError("No se encontró 'tar' ni '7z' en el sistema para descomprimir archivos .rar.")
    cmd = [tar_bin, "-xf", str(archive_path), "-C", str(dest_dir)]
    if members_pattern:
        cmd.append(members_pattern)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def import_from_legacy_source(
    db: ClimateDatabase,
    source_path: Path,
    station_filter: set[str] | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    import_catalog: bool = True,
    progress_cb: ProgressCallback | None = None,
) -> dict[str, Any]:
    """
    Importa datos históricos desde:
    - Carpeta instalada de CLIMA (conteniendo EstClima.ini y/o SHC/)
    - Carpeta SHC directamente
    - Archivo Clima.rar
    - Archivo Instalador-Clima.zip (conteniendo Instalador Clima/Clima.rar)
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"No existe la ruta: {source_path}")

    temp_ctx: tempfile.TemporaryDirectory[str] | None = None
    work_dir: Path = source_path

    try:
        if source_path.is_file():
            temp_ctx = tempfile.TemporaryDirectory(prefix="hidroclima_imp_")
            tmp = Path(temp_ctx.name)
            if progress_cb:
                progress_cb(0, 100, f"Extrayendo {source_path.name}...")

            if source_path.suffix.lower() == ".zip":
                with zipfile.ZipFile(source_path, "r") as zf:
                    rar_members = [m for m in zf.namelist() if m.lower().endswith("clima.rar")]
                    if rar_members:
                        rar_out = tmp / "Clima.rar"
                        with zf.open(rar_members[0]) as src, open(rar_out, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        _extract_archive_with_system_tools(rar_out, tmp)
                        work_dir = tmp
                    else:
                        zf.extractall(tmp)
                        work_dir = tmp
            elif source_path.suffix.lower() == ".rar":
                _extract_archive_with_system_tools(source_path, tmp)
                work_dir = tmp
            else:
                raise ValueError(f"Formato no soportado para importación masiva: {source_path.suffix}")

        # Localizar carpeta que contiene SHC y/o EstClima.ini
        shc_dir: Path | None = None
        if work_dir.name.upper() == "SHC" and work_dir.is_dir():
            shc_dir = work_dir
            cat_dir = work_dir.parent
        elif (work_dir / "SHC").is_dir():
            shc_dir = work_dir / "SHC"
            cat_dir = work_dir
        else:
            found = list(work_dir.rglob("SHC"))
            shc_dir = found[0] if found else None
            cat_dir = shc_dir.parent if shc_dir else work_dir

        cat_counts: dict[str, int] = {}
        if import_catalog and (cat_dir / "EstClima.ini").exists():
            if progress_cb:
                progress_cb(5, 100, "Importando catálogo de estaciones y municipios...")
            cat_counts = import_catalog_ini_files(db, cat_dir)

        if not shc_dir or not shc_dir.exists():
            raise FileNotFoundError("No se encontró la carpeta SHC/ con los archivos históricos climaYYYY.dat.")

        dat_files = sorted(shc_dir.glob("*.dat"), key=lambda p: p.name.lower())
        selected_files: list[tuple[int, Path]] = []
        for p in dat_files:
            m = re.search(r"(\d{4})", p.stem)
            if not m:
                continue
            yr = int(m.group(1))
            if year_min is not None and yr < year_min:
                continue
            if year_max is not None and yr > year_max:
                continue
            selected_files.append((yr, p))

        total_files = len(selected_files)
        total_records = 0
        stations_seen: set[str] = set()
        min_y_seen: int | None = None
        max_y_seen: int | None = None

        with db.connect() as conn:
            for idx, (yr, dat_path) in enumerate(selected_files, start=1):
                rows = parse_shc_dat_file(dat_path, station_filter=station_filter)
                if rows:
                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO series_anuales
                        (station_code, var_id, year, source, updated_at, data_blob, valid_count, annual_sum, annual_mean, annual_max, annual_min)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        rows,
                    )
                    total_records += len(rows)
                    for r in rows:
                        stations_seen.add(r[0])
                    min_y_seen = yr if min_y_seen is None else min(min_y_seen, yr)
                    max_y_seen = yr if max_y_seen is None else max(max_y_seen, yr)

                if progress_cb and (idx % 5 == 0 or idx == total_files):
                    pct = 10 + int(90 * idx / max(1, total_files))
                    progress_cb(pct, 100, f"Procesado año {yr} ({idx}/{total_files}) — {total_records:,} registros")

        db.log_sync(
            source="IDEAM-Legacy",
            action="import_legacy",
            stations_count=len(stations_seen),
            records_count=total_records,
            year_min=min_y_seen,
            year_max=max_y_seen,
            notes=f"Importado desde {source_path.name}",
        )
        return {
            "catalog_counts": cat_counts,
            "files_processed": total_files,
            "records_imported": total_records,
            "stations_imported": len(stations_seen),
            "year_min": min_y_seen,
            "year_max": max_y_seen,
        }
    finally:
        if temp_ctx is not None:
            temp_ctx.cleanup()
