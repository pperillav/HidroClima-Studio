"""Puente satelital y de reanálisis (Open-Meteo ERA5 & NASA POWER) para actualización y llenado de brechas."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np
import requests

from hidroclima.db.database import SLOTS_PER_YEAR, ClimateDatabase

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"


def _wind_10m_to_2m(u10: float) -> float:
    """Convierte velocidad del viento de 10 m a 2 m según perfil logarítmico FAO-56."""
    return u10 * (4.87 / math.log(67.8 * 10.0 - 5.42))


def fetch_open_meteo_daily(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    timeout: int = 30,
) -> dict[tuple[int, int], np.ndarray]:
    """
    Descarga variables diarias desde Open-Meteo ERA5 Historical Archive.
    Devuelve dict[(var_id, year)] = np.ndarray(372, float32).
    """
    resp = requests.get(
        OPEN_METEO_ARCHIVE_URL,
        params={
            "latitude": round(float(lat), 5),
            "longitude": round(float(lon), 5),
            "start_date": start_date,
            "end_date": end_date,
            "daily": ",".join([
                "precipitation_sum",
                "sunshine_duration",
                "relative_humidity_2m_mean",
                "temperature_2m_mean",
                "temperature_2m_max",
                "temperature_2m_min",
                "wind_speed_10m_mean",
                "shortwave_radiation_sum",
            ]),
            "wind_speed_unit": "ms",
            "timezone": "America/Bogota",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    daily = resp.json().get("daily", {})
    times = daily.get("time", [])
    if not times:
        return {}

    mapping: list[tuple[str, int, float]] = [
        ("precipitation_sum", 1, 1.0),
        ("sunshine_duration", 2, 1.0 / 3600.0),  # segundos -> horas
        ("relative_humidity_2m_mean", 4, 1.0),
        ("temperature_2m_mean", 5, 1.0),
        ("temperature_2m_max", 6, 1.0),
        ("temperature_2m_min", 7, 1.0),
        ("wind_speed_10m_mean", 9, _wind_10m_to_2m(1.0)),  # 10 m -> 2 m m/s
        ("shortwave_radiation_sum", 12, 1.0),  # MJ/m2/día
    ]

    out: dict[tuple[int, int], np.ndarray] = {}
    for idx, dt_str in enumerate(times):
        yr = int(dt_str[0:4])
        mo = int(dt_str[5:7])
        dy = int(dt_str[8:10])
        slot = (mo - 1) * 31 + (dy - 1)
        for field, vid, scale in mapping:
            arr_vals = daily.get(field)
            if not arr_vals or idx >= len(arr_vals):
                continue
            val = arr_vals[idx]
            if val is None:
                continue
            k = (vid, yr)
            if k not in out:
                out[k] = np.full(SLOTS_PER_YEAR, np.nan, dtype=np.float32)
            out[k][slot] = np.float32(float(val) * scale)
    return out


def fetch_nasa_power_daily(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    timeout: int = 35,
) -> dict[tuple[int, int], np.ndarray]:
    """
    Descarga variables diarias desde NASA POWER API (AG community).
    start_date / end_date en formato YYYY-MM-DD.
    """
    s_compact = start_date.replace("-", "")
    e_compact = end_date.replace("-", "")
    resp = requests.get(
        NASA_POWER_DAILY_URL,
        params={
            "parameters": "PRECTOTCORR,RH2M,T2M,T2M_MAX,T2M_MIN,WS2M,ALLSKY_SFC_SW_DWN",
            "community": "AG",
            "longitude": round(float(lon), 5),
            "latitude": round(float(lat), 5),
            "start": s_compact,
            "end": e_compact,
            "format": "JSON",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    params_data = resp.json().get("properties", {}).get("parameter", {})
    if not params_data:
        return {}

    field_map = {
        "PRECTOTCORR": 1,
        "RH2M": 4,
        "T2M": 5,
        "T2M_MAX": 6,
        "T2M_MIN": 7,
        "WS2M": 9,
        "ALLSKY_SFC_SW_DWN": 12,
    }
    out: dict[tuple[int, int], np.ndarray] = {}
    for p_name, vid in field_map.items():
        series = params_data.get(p_name, {})
        for ymd, val in series.items():
            if val is None or float(val) <= -900.0:
                continue
            yr = int(ymd[0:4])
            mo = int(ymd[4:6])
            dy = int(ymd[6:8])
            k = (vid, yr)
            if k not in out:
                out[k] = np.full(SLOTS_PER_YEAR, np.nan, dtype=np.float32)
            out[k][(mo - 1) * 31 + (dy - 1)] = np.float32(float(val))
    return out


def sync_station_from_reanalysis(
    db: ClimateDatabase,
    station_code: str,
    provider: str = "Open-Meteo",
    start_year: int = 2020,
    end_year: int | None = None,
) -> dict[str, Any]:
    """Sincroniza series diarias de reanálisis para las coordenadas exactas de una estación."""
    stns = db.get_stations_by_codes([station_code])
    if not stns:
        raise ValueError(f"Estación {station_code} no encontrada en el catálogo.")
    stn = stns[0]
    lat, lon = stn.get("latitud"), stn.get("longitud")
    if lat is None or lon is None:
        raise ValueError(f"Estación {station_code} no tiene coordenadas geográficas válidas.")

    today = date.today()
    e_year = end_year or today.year
    start_dt = f"{int(start_year)}-01-01"
    if e_year >= today.year:
        # Open-Meteo archive tiene un retardo típico de ~5 días
        end_dt = min(today, date.fromordinal(today.toordinal() - 5)).isoformat()
        if end_dt < start_dt:
            end_dt = today.isoformat()
    else:
        end_dt = f"{e_year}-12-31"

    prov_upper = provider.upper()
    if "NASA" in prov_upper:
        src_name = "NASA-POWER"
        fetched = fetch_nasa_power_daily(lat, lon, start_dt, end_dt)
    else:
        src_name = "Open-Meteo"
        fetched = fetch_open_meteo_daily(lat, lon, start_dt, end_dt)

    if not fetched:
        return {"station_code": station_code, "source": src_name, "records_saved": 0, "message": "Sin datos devueltos."}

    to_save = [(station_code, vid, yr, src_name, arr) for (vid, yr), arr in fetched.items()]
    saved = db.upsert_annual_series(to_save)
    years = sorted({yr for (_, yr) in fetched.keys()})
    db.log_sync(
        source=src_name,
        action="sync_reanalysis",
        stations_count=1,
        records_count=saved,
        year_min=years[0] if years else None,
        year_max=years[-1] if years else None,
        notes=f"Puente {src_name} para estación {station_code} ({start_dt} a {end_dt})",
    )
    return {
        "station_code": station_code,
        "source": src_name,
        "records_saved": saved,
        "years": years,
        "message": f"Sincronizados {saved} registros ({years[0]}–{years[-1]}) desde {src_name}.",
    }
