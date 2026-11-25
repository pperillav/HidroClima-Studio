"""Puente en vivo hacia Datos Abiertos de Colombia (www.datos.gov.co - SODA API del IDEAM)."""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import numpy as np
import requests

from hidroclima.config import IDEAM_SOCRATA_DATASETS
from hidroclima.db.database import SLOTS_PER_YEAR, ClimateDatabase

SOCRATA_BASE = "https://www.datos.gov.co/resource"

# Mapeo de codigosensor en el stream unificado 57sv-p2fu -> (var_id, agregación diaria)
UNIFIED_SENSOR_MAP: dict[str, tuple[int, str]] = {
    "0240": (1, "sum"),   # Precipitación acumulada (mm)
    "0027": (4, "mean"),  # Humedad relativa (%)
    "0068": (5, "mean"),  # Temperatura del aire 2 m (°C)
    "0069": (6, "max"),   # Temperatura máxima del aire 2 m (°C)
    "0070": (7, "min"),   # Temperatura mínima del aire 2 m (°C)
    "0103": (9, "mean"),  # Velocidad del viento (m/s)
}


def _canonical_code_10(code: str) -> str:
    c = str(code).strip()
    if c.isdigit():
        return (c.lstrip("0") or c).zfill(10)
    return c


def _candidate_station_codes(code: str) -> list[str]:
    """Devuelve variantes del código IDEAM (10 dígitos con ceros primero, luego 8 dígitos)."""
    c = str(code).strip()
    variants: list[str] = []
    if c.isdigit():
        stripped = c.lstrip("0") or c
        for v in (stripped.zfill(10), stripped.zfill(8), stripped):
            if v not in variants:
                variants.append(v)
    else:
        variants.append(c)
    return variants


def _parse_num(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(str(val).replace(",", "."))
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def sync_ideam_station_catalog(
    db: ClimateDatabase,
    limit: int = 12000,
    timeout: int = 30,
) -> dict[str, Any]:
    """Sincroniza el Catálogo Nacional de Estaciones del IDEAM (hp9r-jxuu) desde datos.gov.co."""
    ds_id = IDEAM_SOCRATA_DATASETS["stations"]["id"]
    url = f"{SOCRATA_BASE}/{ds_id}.json"

    with db.connect() as conn:
        cat_rows = conn.execute("SELECT codigo, descripcion FROM categorias").fetchall()
        mun_rows = conn.execute("SELECT codigo, nombre, departamento_codigo FROM municipios").fetchall()
        dep_rows = conn.execute("SELECT codigo, nombre FROM departamentos").fetchall()

    cat_by_desc = {r["descripcion"].upper(): r["codigo"] for r in cat_rows}
    cat_by_desc.update({
        "PLUVIOMÉTRICA": "PM",
        "PLUVIOMETRICA": "PM",
        "CLIMATOLÓGICA ORDINARIA": "CO",
        "CLIMATOLOGICA ORDINARIA": "CO",
        "CLIMATOLÓGICA PRINCIPAL": "CP",
        "CLIMATOLOGICA PRINCIPAL": "CP",
        "SINÓPTICA PRINCIPAL": "SP",
        "SINOPTICA PRINCIPAL": "SP",
        "SINÓPTICA SUPLEMENTARIA": "SS",
        "AGROMETEOROLÓGICA": "AM",
        "LIMNIGRÁFICA": "LG",
        "LIMNIMÉTRICA": "LM",
        "METEOROLÓGICA ESPECIAL": "ME",
        "PLUVIOGRÁFICA": "PG",
        "RADIOSONDA": "RS",
    })
    dep_by_name = {r["nombre"].upper(): r["codigo"] for r in dep_rows}
    mun_by_name = {(r["departamento_codigo"], r["nombre"].upper()): r["codigo"] for r in mun_rows}

    fetched: list[dict[str, Any]] = []
    offset = 0
    page_size = 2000
    while offset < limit:
        batch = min(page_size, limit - offset)
        resp = requests.get(
            url,
            params={"$limit": batch, "$offset": offset, "$order": "codigo ASC"},
            timeout=timeout,
        )
        resp.raise_for_status()
        items = resp.json()
        if not items:
            break
        for row in items:
            raw_code = str(row.get("codigo", "")).strip()
            if not raw_code:
                continue
            short_code = raw_code.lstrip("0") if raw_code.isdigit() and raw_code.startswith("00") and len(raw_code) == 10 else raw_code
            cat_desc = str(row.get("categoria") or "").strip().upper()
            cat_code = cat_by_desc.get(cat_desc, cat_desc[:2] if cat_desc else "")
            dep_name = str(row.get("departamento") or "").strip().upper()
            mun_name = str(row.get("municipio") or "").strip().upper()
            dep_code = dep_by_name.get(dep_name, "")
            mun_code = mun_by_name.get((dep_code, mun_name), "")
            fetched.append({
                "codigo": short_code,
                "codigo_ideam_10": raw_code.zfill(10) if raw_code.isdigit() else raw_code,
                "nombre": str(row.get("nombre") or "").split("[")[0].strip(),
                "categoria_codigo": cat_code,
                "municipio_codigo": mun_code,
                "departamento_codigo": dep_code,
                "entidad": str(row.get("entidad") or "").strip(),
                "area_hidrografica": str(row.get("area_hidrografica") or "").strip(),
                "area_operativa": str(row.get("area_operativa") or "").strip(),
                "zona_hidrografica": str(row.get("zona_hidrografica") or "").strip(),
                "subzona_hidrografica": str(row.get("subzona_hidrografica") or "").strip(),
                "tecnologia": str(row.get("tecnologia") or "").strip(),
                "fecha_instalacion": str(row.get("fecha_instalacion") or "").strip(),
                "fecha_suspension": str(row.get("fecha_suspension") or "").strip(),
                "latitud": _parse_num(row.get("latitud")),
                "longitud": _parse_num(row.get("longitud")),
                "altitud": _parse_num(row.get("altitud")),
                "estado": str(row.get("estado") or "Activa").strip(),
            })
        if len(items) < batch:
            break
        offset += batch

    updated = db.upsert_stations(fetched, source="IDEAM-API")
    db.log_sync(
        source="IDEAM-API",
        action="sync_catalog",
        stations_count=updated,
        records_count=updated,
        notes="Actualización del Catálogo Nacional de Estaciones (hp9r-jxuu)",
    )
    return {"fetched": len(fetched), "upserted": updated}


def find_nearby_automatic_stations(
    db: ClimateDatabase,
    lat: float,
    lon: float,
    radius_km: float = 25.0,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Busca estaciones automáticas cercanas en el catálogo local para usarlas como puente IDEAM-API."""
    candidates = db.search_stations(
        center_lat=lat,
        center_lon=lon,
        radius_km=radius_km,
        limit=100,
    )
    auto = [
        c for c in candidates
        if "AUT" in (c.get("tecnologia") or "").upper() or "- AUT" in (c.get("nombre") or "").upper()
    ]
    return (auto or candidates)[:limit]


def _write_slot(out_arrays: dict[tuple[int, int], np.ndarray], var_id: int, dia_str: str, val: float) -> None:
    if len(dia_str) != 10:
        return
    try:
        yr = int(dia_str[0:4])
        mo = int(dia_str[5:7])
        dy = int(dia_str[8:10])
    except ValueError:
        return
    if not (1 <= mo <= 12 and 1 <= dy <= 31):
        return
    k = (var_id, yr)
    if k not in out_arrays:
        out_arrays[k] = np.full(SLOTS_PER_YEAR, np.nan, dtype=np.float32)
    out_arrays[k][(mo - 1) * 31 + (dy - 1)] = np.float32(val)


def fetch_ideam_unified_realtime(
    station_code: str,
    timeout: int = 12,
) -> tuple[dict[tuple[int, int], np.ndarray], list[str]]:
    """Consulta el feed en tiempo real 57sv-p2fu (rápido, últimos días)."""
    out_arrays: dict[tuple[int, int], np.ndarray] = {}
    warnings: list[str] = []
    ds_id = str(IDEAM_SOCRATA_DATASETS["unified"]["id"])
    url = f"{SOCRATA_BASE}/{ds_id}.json"

    for code_cand in _candidate_station_codes(station_code)[:2]:
        try:
            resp = requests.get(
                url,
                params={
                    "$where": f"codigoestacion='{code_cand}'",
                    "$limit": 2000,
                },
                timeout=timeout,
            )
            if resp.status_code != 200:
                continue
            rows = resp.json()
            if not rows:
                continue
            buckets: dict[tuple[int, str], list[float]] = {}
            for row in rows:
                sensor = str(row.get("codigosensor") or "").strip()
                if sensor not in UNIFIED_SENSOR_MAP:
                    continue
                vid, _agg = UNIFIED_SENSOR_MAP[sensor]
                dia_str = str(row.get("fechaobservacion") or "")[:10]
                val = _parse_num(row.get("valorobservado"))
                if val is None or len(dia_str) != 10:
                    continue
                buckets.setdefault((vid, dia_str), []).append(val)
            for (vid, dia_str), vals in buckets.items():
                agg_mode = next((a for v_id, a in UNIFIED_SENSOR_MAP.values() if v_id == vid), "mean")
                if agg_mode == "sum":
                    agg_v = sum(vals)
                elif agg_mode == "max":
                    agg_v = max(vals)
                elif agg_mode == "min":
                    agg_v = min(vals)
                else:
                    agg_v = sum(vals) / len(vals)
                _write_slot(out_arrays, vid, dia_str, agg_v)
            if out_arrays:
                break
        except requests.RequestException as exc:
            warnings.append(f"57sv-p2fu ({code_cand}): {exc}")
    return out_arrays, warnings


def fetch_ideam_socrata_daily(
    station_code: str,
    start_year: int,
    end_year: int,
    var_keys: list[str] | None = None,
    timeout: int = 8,
) -> tuple[dict[tuple[int, int], np.ndarray], list[str]]:
    """
    Descarga y agrega diariamente datos desde los datasets IDEAM de datos.gov.co usando SoQL en paralelo.
    Prioriza el feed rápido 57sv-p2fu y consulta datasets históricos por variable con tolerancia a timeouts.
    """
    out_arrays, warnings = fetch_ideam_unified_realtime(station_code, timeout=timeout)
    keys = var_keys or ["precip", "tmean", "tmax", "tmin", "rh", "wind"]
    code_10 = _canonical_code_10(station_code)
    start_iso = f"{int(start_year)}-01-01T00:00:00"
    end_iso = f"{int(end_year) + 1}-01-01T00:00:00"

    def _fetch_one(key: str) -> tuple[str, int, list[tuple[str, float]], str | None]:
        spec = IDEAM_SOCRATA_DATASETS.get(key)
        if not spec or "var_id" not in spec:
            return key, 0, [], None
        ds_id = str(spec["id"])
        var_id = int(spec["var_id"])
        agg = str(spec["agg"])
        where = (
            f"codigoestacion='{code_10}' "
            f"AND fechaobservacion >= '{start_iso}' AND fechaobservacion < '{end_iso}'"
        )
        select = f"date_trunc_ymd(fechaobservacion) AS dia, {agg}(valorobservado) AS val"
        url = f"{SOCRATA_BASE}/{ds_id}.json"
        try:
            resp = requests.get(
                url,
                params={
                    "$select": select,
                    "$where": where,
                    "$group": "date_trunc_ymd(fechaobservacion)",
                    "$order": "dia ASC",
                    "$limit": 5000,
                },
                timeout=timeout,
            )
            if resp.status_code != 200:
                return key, var_id, [], None
            parsed: list[tuple[str, float]] = []
            for row in resp.json():
                dia_str = str(row.get("dia", ""))[:10]
                val = _parse_num(row.get("val"))
                if val is not None:
                    parsed.append((dia_str, val))
            return key, var_id, parsed, None
        except requests.RequestException:
            return key, var_id, [], f"{ds_id} ({key}): timeout/red"

    with ThreadPoolExecutor(max_workers=min(6, max(1, len(keys)))) as pool:
        futures = [pool.submit(_fetch_one, k) for k in keys]
        for fut in as_completed(futures):
            _key, var_id, rows_parsed, warn = fut.result()
            if warn:
                warnings.append(warn)
            for dia_str, val in rows_parsed:
                _write_slot(out_arrays, var_id, dia_str, val)

    return out_arrays, warnings


def sync_station_from_ideam_api(
    db: ClimateDatabase,
    station_code: str,
    start_year: int,
    end_year: int,
    allow_nearby_auto_fallback: bool = True,
) -> dict[str, Any]:
    """Sincroniza una estación desde datos.gov.co (con puente a estación automática cercana si es convencional)."""
    stns = db.get_stations_by_codes([station_code])
    stn = stns[0] if stns else None

    fetched, warnings = fetch_ideam_socrata_daily(station_code, start_year, end_year)
    used_proxy_code: str | None = None

    if not fetched and allow_nearby_auto_fallback and stn and stn.get("latitud") is not None:
        nearby = find_nearby_automatic_stations(db, float(stn["latitud"]), float(stn["longitud"]), radius_km=20.0, limit=2)
        for cand in nearby:
            if cand["codigo"] == station_code:
                continue
            cand_data, cand_warn = fetch_ideam_socrata_daily(cand["codigo"], start_year, end_year)
            warnings.extend(cand_warn)
            if cand_data:
                fetched = cand_data
                used_proxy_code = cand["codigo"]
                break

    if not fetched:
        return {
            "station_code": station_code,
            "records_saved": 0,
            "used_proxy_code": None,
            "warnings": warnings,
            "message": "Sin registros recientes disponibles vía IDEAM-API para esta estación/rango.",
        }

    to_save = [(station_code, vid, yr, "IDEAM-API", arr) for (vid, yr), arr in fetched.items()]
    saved = db.upsert_annual_series(to_save)
    years = sorted({yr for (_, yr) in fetched.keys()})
    notes = f"Estación {station_code} ({start_year}-{end_year})"
    if used_proxy_code:
        notes += f" vía estación automática cercana {used_proxy_code}"
    db.log_sync(
        source="IDEAM-API",
        action="sync_series",
        stations_count=1,
        records_count=saved,
        year_min=years[0] if years else None,
        year_max=years[-1] if years else None,
        notes=notes,
    )
    return {
        "station_code": station_code,
        "records_saved": saved,
        "years": years,
        "used_proxy_code": used_proxy_code,
        "warnings": warnings,
        "message": f"Sincronizados {saved} registros anuales desde IDEAM Datos Abiertos"
        + (f" (puente automática {used_proxy_code})" if used_proxy_code else ""),
    }
