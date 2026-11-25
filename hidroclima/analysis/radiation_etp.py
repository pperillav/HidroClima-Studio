"""Radiación solar FAO-56, horas de sol astronómicas y evapotranspiración de referencia Penman-Monteith."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

SOLAR_CONSTANT_MJ = 0.0820  # MJ m^-2 min^-1
STEFAN_BOLTZMANN_MJ = 4.903e-9  # MJ K^-4 m^-2 day^-1


def solar_geometry_series(lat_deg: float, doy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcula radiación extraterrestre Ra (MJ/m2/día) y horas máximas de insolación N (h/día)
    según ecuaciones FAO-56 (Allen et al., 1998) para latitud en grados y día juliano doy (1..366).
    """
    phi = math.radians(lat_deg)
    dr = 1.0 + 0.033 * np.cos((2.0 * math.pi / 365.0) * doy)
    delta = 0.409 * np.sin((2.0 * math.pi / 365.0) * doy - 1.39)
    cos_ws = np.clip(-math.tan(phi) * np.tan(delta), -1.0, 1.0)
    ws = np.arccos(cos_ws)
    daylight_hours = (24.0 / math.pi) * ws
    ra = (
        (24.0 * 60.0 / math.pi)
        * SOLAR_CONSTANT_MJ
        * dr
        * (ws * math.sin(phi) * np.sin(delta) + math.cos(phi) * np.cos(delta) * np.sin(ws))
    )
    return np.maximum(0.0, ra), np.maximum(0.1, daylight_hours)


def sat_vapor_pressure(temp_c: np.ndarray) -> np.ndarray:
    """Presión de vapor de saturación e°(T) en kPa (FAO-56 Ec. 11)."""
    return 0.6108 * np.exp((17.27 * temp_c) / (temp_c + 237.3))


def compute_fao56_daily_et0(
    df: pd.DataFrame,
    lat_deg: float,
    altitude_m: float,
    coastal_krs: bool = False,
) -> pd.DataFrame:
    """
    Calcula variables derivadas FAO-56 diarias sobre un DataFrame indexado por DatetimeIndex:
    Columnas de entrada esperadas (por id numérico de VARIABLES):
      2: Brillo solar (h), 4: Humedad relativa (%), 5: T media (°C),
      6: T max (°C), 7: T min (°C), 8: Recorrido viento (km/d),
      9: Vel viento (m/s), 12: Radiación solar directa (MJ/m2/d)
    Retorna DataFrame con columns:
      ra_mj, daylight_h, rs_mj, rs_source, wind_ms, et0_mm
    """
    idx = df.index
    doy = idx.day_of_year.to_numpy(dtype=np.float64)
    ra, n_hours = solar_geometry_series(lat_deg, doy)

    tmean = df[5].to_numpy(dtype=np.float64) if 5 in df else np.full(len(df), np.nan)
    tmax = df[6].to_numpy(dtype=np.float64) if 6 in df else np.full(len(df), np.nan)
    tmin = df[7].to_numpy(dtype=np.float64) if 7 in df else np.full(len(df), np.nan)

    # Reconstruir Tmean si falta pero existen Tmax y Tmin, y viceversa
    both_minmax = ~np.isnan(tmax) & ~np.isnan(tmin)
    tmean_eff = np.where(~np.isnan(tmean), tmean, np.where(both_minmax, 0.5 * (tmax + tmin), np.nan))
    tmax_eff = np.where(~np.isnan(tmax), tmax, tmean_eff + 4.5)
    tmin_eff = np.where(~np.isnan(tmin), tmin, tmean_eff - 4.5)

    # Presión atmosférica y constante psicrométrica (FAO-56 Ec. 7 y 8)
    alt = max(0.0, float(altitude_m))
    p_atm = 101.3 * (((293.0 - 0.0065 * alt) / 293.0) ** 5.26)
    gamma = 0.000665 * p_atm

    # Presión de vapor de saturación y actual
    es = np.where(
        both_minmax,
        0.5 * (sat_vapor_pressure(tmax_eff) + sat_vapor_pressure(tmin_eff)),
        sat_vapor_pressure(tmean_eff),
    )

    rh = df[4].to_numpy(dtype=np.float64) if 4 in df else np.full(len(df), np.nan)
    rh_clipped = np.clip(rh, 5.0, 100.0)
    ea = np.where(
        ~np.isnan(rh_clipped),
        (rh_clipped / 100.0) * es,
        sat_vapor_pressure(tmin_eff),  # fallback FAO-56 Ec. 48 si no hay HR
    )
    ea = np.minimum(ea, es)

    # Radiación solar Rs (prioridad: directa > Angstrom-Prescott brillo solar > Hargreaves ΔT > promedio climatológico)
    rs_obs = df[12].to_numpy(dtype=np.float64) if 12 in df else np.full(len(df), np.nan)
    sunshine = df[2].to_numpy(dtype=np.float64) if 2 in df else np.full(len(df), np.nan)

    rs_angstrom = np.where(
        ~np.isnan(sunshine),
        (0.25 + 0.50 * np.clip(sunshine / n_hours, 0.0, 1.0)) * ra,
        np.nan,
    )
    k_rs = 0.19 if coastal_krs else 0.16
    dt_range = np.maximum(0.0, tmax_eff - tmin_eff)
    rs_hargreaves = np.where(both_minmax, np.minimum(ra, k_rs * np.sqrt(dt_range) * ra), np.nan)

    rs = np.where(~np.isnan(rs_obs), rs_obs, np.where(~np.isnan(rs_angstrom), rs_angstrom, rs_hargreaves))
    rs = np.where(~np.isnan(rs), np.clip(rs, 0.5, ra), 0.48 * ra)

    rs_source = np.where(
        ~np.isnan(rs_obs),
        "Observada/Satelital",
        np.where(~np.isnan(rs_angstrom), "Angstrom-Prescott (Brillo Solar)", np.where(~np.isnan(rs_hargreaves), "Hargreaves (ΔT)", "Estimada Ra")),
    )

    # Radiación de cielo despejado y radiación neta
    rso = (0.75 + 2e-5 * alt) * ra
    rns = (1.0 - 0.23) * rs
    rs_ratio = np.clip(rs / np.maximum(0.1, rso), 0.25, 1.0)
    t_k4 = 0.5 * ((tmax_eff + 273.16) ** 4 + (tmin_eff + 273.16) ** 4)
    rnl = STEFAN_BOLTZMANN_MJ * t_k4 * (0.34 - 0.14 * np.sqrt(np.maximum(0.01, ea))) * (1.35 * rs_ratio - 0.35)
    rn = rns - rnl

    # Velocidad del viento (prioridad: var 9 m/s > var 11 m/s > var 8 km/día > 2.0 m/s por defecto FAO-56)
    w9 = df[9].to_numpy(dtype=np.float64) if 9 in df else np.full(len(df), np.nan)
    w11 = df[11].to_numpy(dtype=np.float64) if 11 in df else np.full(len(df), np.nan)
    w8 = df[8].to_numpy(dtype=np.float64) if 8 in df else np.full(len(df), np.nan)
    w8_ms = w8 * 1000.0 / 86400.0

    wind = np.where(~np.isnan(w9), w9, np.where(~np.isnan(w11), w11, np.where(~np.isnan(w8_ms), w8_ms, 2.0)))
    wind = np.clip(wind, 0.1, 25.0)

    # Pendiente curva presión de vapor Delta
    delta_es = (4098.0 * sat_vapor_pressure(tmean_eff)) / ((tmean_eff + 237.3) ** 2)

    num = 0.408 * delta_es * rn + gamma * (900.0 / (tmean_eff + 273.0)) * wind * np.maximum(0.0, es - ea)
    den = delta_es + gamma * (1.0 + 0.34 * wind)
    et0 = np.where(~np.isnan(tmean_eff), np.maximum(0.0, num / den), np.nan)

    return pd.DataFrame(
        {
            "ra_mj": ra,
            "daylight_h": n_hours,
            "rs_mj": rs,
            "rs_source": rs_source,
            "wind_ms": wind,
            "et0_mm": et0,
        },
        index=idx,
    )
