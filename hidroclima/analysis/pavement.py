"""Métricas de ingeniería de pavimentos: TMAP (Shell/INVIAS), Superpave PG, 7 días calientes y MEPDG."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from hidroclima.config import MONTH_ABBR_ES


def _round_pg_high(temp_c: float) -> int:
    grades = [46, 52, 58, 64, 70, 76, 82]
    for g in grades:
        if temp_c <= g:
            return g
    return 82


def _round_pg_low(temp_c: float) -> int:
    grades = [-10, -16, -22, -28, -34, -40, -46]
    for g in grades:
        if temp_c >= g:
            return g
    return -46


def shell_weighting_factor(temp_c: float) -> float:
    """Factor de ponderación térmica mensual (Carta W del método Shell / Manual INVIAS)."""
    t = float(temp_c)
    exp_val = -1.224 + 0.06508 * t - 0.000145 * (t ** 2)
    return float(10.0 ** exp_val)


def shell_wf_to_tmap(wf_avg: float) -> float:
    """Convierte el factor de ponderación promedio anual a TMAP / w-MAAT (°C)."""
    lg = math.log10(max(1e-6, float(wf_avg)))
    return float(19.66 + 16.91 * lg + 0.3117 * (lg ** 2))


def classify_invias_pavement_region(tmap_c: float, annual_precip_mm: float) -> dict[str, str]:
    """
    Zonificación climática del Manual de Diseño de Pavimentos Asfálticos en Vías
    con Medios y Altos Volúmenes de Tránsito del INVIAS (Regiones R1 a R6).
    """
    t = float(tmap_c)
    p = float(annual_precip_mm)
    if t < 13.0:
        if p < 2000.0:
            return {"code": "R1", "name": "Fría seca y fría semihúmeda", "criteria": "TMAP < 13 °C, PMA < 2.000 mm"}
        return {"code": "R1-H", "name": "Fría húmeda / Páramo (equivalente R1 con drenaje reforzado)", "criteria": "TMAP < 13 °C, PMA >= 2.000 mm"}
    if t <= 20.0:
        if p < 2000.0:
            return {"code": "R2", "name": "Templado seco y templado semihúmedo", "criteria": "13 <= TMAP <= 20 °C, PMA < 2.000 mm"}
        return {"code": "R4", "name": "Templado húmedo", "criteria": "13 <= TMAP <= 20 °C, PMA >= 2.000 mm"}
    if p < 2000.0:
        return {"code": "R3", "name": "Cálido seco y cálido semihúmedo", "criteria": "TMAP > 20 °C, PMA < 2.000 mm"}
    if p <= 4000.0:
        return {"code": "R5", "name": "Cálido húmedo", "criteria": "TMAP > 20 °C, 2.000 <= PMA <= 4.000 mm"}
    return {"code": "R6", "name": "Cálido muy húmedo", "criteria": "TMAP > 20 °C, PMA > 4.000 mm"}


def compute_tmap_shell(
    daily_df: pd.DataFrame,
    monthly_temps_clim: list[float] | None = None,
    annual_precip_mm: float = 0.0,
) -> dict[str, Any]:
    """
    Calcula la Temperatura Media Anual Ponderada (TMAP / w-MAAT) por metodología Shell / INVIAS:
    - Cálculo año a año (requiere >= 10 meses con datos en el año) y promedio multianual de TMAP anuales.
    - Cálculo sobre el ciclo mensual climatológico con desglose de factores WF mensuales.
    """
    yearly_tmap: list[dict[str, Any]] = []
    if 5 in daily_df and daily_df[5].notna().any():
        t_series = daily_df[5].dropna()
        for yr, grp in t_series.groupby(t_series.index.year):
            m_means = grp.groupby(grp.index.month).mean()
            if len(m_means) < 10:
                continue
            wfs = [shell_weighting_factor(float(val)) for val in m_means.values]
            wf_avg = float(np.mean(wfs))
            tmap_yr = shell_wf_to_tmap(wf_avg)
            yearly_tmap.append({
                "year": int(yr),
                "months_count": int(len(m_means)),
                "tmean_arith_c": round(float(m_means.mean()), 2),
                "wf_avg": round(wf_avg, 4),
                "tmap_c": round(tmap_yr, 2),
            })

    monthly_wf_table: list[dict[str, Any]] = []
    tmap_clim = None
    wf_clim_avg = None
    if monthly_temps_clim and len(monthly_temps_clim) == 12:
        wfs_c = [shell_weighting_factor(t) for t in monthly_temps_clim]
        wf_clim_avg = float(np.mean(wfs_c))
        tmap_clim = shell_wf_to_tmap(wf_clim_avg)
        for m_idx in range(12):
            monthly_wf_table.append({
                "month": MONTH_ABBR_ES[m_idx],
                "temp_c": round(float(monthly_temps_clim[m_idx]), 2),
                "wf": round(wfs_c[m_idx], 4),
            })

    tmap_project = (
        round(float(np.mean([r["tmap_c"] for r in yearly_tmap])), 2)
        if yearly_tmap
        else (round(tmap_clim, 2) if tmap_clim is not None else None)
    )
    invias_region = (
        classify_invias_pavement_region(tmap_project, annual_precip_mm)
        if tmap_project is not None
        else {"code": "N/D", "name": "Sin datos", "criteria": ""}
    )

    return {
        "tmap_c": tmap_project,
        "pma_mm": round(float(annual_precip_mm), 1),
        "tmap_clim_cycle_c": round(tmap_clim, 2) if tmap_clim is not None else None,
        "wf_clim_avg": round(wf_clim_avg, 4) if wf_clim_avg is not None else None,
        "tmap_yearly": yearly_tmap,
        "monthly_wf": monthly_wf_table,
        "invias_pavement_region": invias_region,
    }


def compute_pavement_metrics(
    daily_df: pd.DataFrame,
    lat_deg: float,
    thornthwaite_tmi: float,
    water_table_m: float = 10.0,
    monthly_temps_clim: list[float] | None = None,
    annual_precip_mm: float = 0.0,
) -> dict[str, Any]:
    """
    Calcula indicadores clave para diseño de pavimentos:
    - TMAP (Temperatura Media Anual Ponderada - método Shell / INVIAS) y región climática R1–R6
    - Temperatura media de los 7 días consecutivos más calientes (Tmax y Tmean)
    - Estimación de grado Superpave PG (confiabilidad 98% a 20 mm de profundidad según modelo LTPP)
    - % días con Tmax >= 32 °C, % días secos (P < 0.1 mm), días con heladas (Tmin <= 0 °C)
    """
    precip = daily_df[1].to_numpy(dtype=np.float64) if 1 in daily_df else np.array([], dtype=np.float64)
    tmean = daily_df[5].to_numpy(dtype=np.float64) if 5 in daily_df else np.array([], dtype=np.float64)
    tmax = daily_df[6].to_numpy(dtype=np.float64) if 6 in daily_df else np.array([], dtype=np.float64)
    tmin = daily_df[7].to_numpy(dtype=np.float64) if 7 in daily_df else np.array([], dtype=np.float64)

    p_valid = precip[~np.isnan(precip)]
    dry_days_pct = round(float((p_valid < 0.1).mean() * 100.0), 2) if p_valid.size else None
    wet_days_count = int((p_valid >= 0.1).sum()) if p_valid.size else 0

    t_ref_32 = tmax[~np.isnan(tmax)] if np.any(~np.isnan(tmax)) else tmean[~np.isnan(tmean)]
    days_ge_32_pct = round(float((t_ref_32 >= 32.0).mean() * 100.0), 2) if t_ref_32.size else None

    tmin_valid = tmin[~np.isnan(tmin)]
    freezing_days = int((tmin_valid <= 0.0).sum()) if tmin_valid.size else 0

    def _yearly_7d_max(series: pd.Series) -> tuple[float | None, float | None, list[dict[str, Any]]]:
        s = series.dropna()
        if s.empty:
            return None, None, []
        roll = series.rolling(window=7, min_periods=5).mean()
        by_yr = []
        for yr, grp in roll.groupby(roll.index.year):
            vals = grp.dropna()
            if vals.empty:
                continue
            peak_val = float(vals.max())
            peak_date = vals.idxmax()
            by_yr.append({"year": int(yr), "temp_7d_c": round(peak_val, 2), "end_date": peak_date.strftime("%Y-%m-%d")})
        if not by_yr:
            return None, None, []
        vals_yr = np.array([r["temp_7d_c"] for r in by_yr], dtype=np.float64)
        mean_7d = float(np.mean(vals_yr))
        std_7d = float(np.std(vals_yr, ddof=1)) if len(vals_yr) > 1 else 1.5
        return mean_7d, std_7d, by_yr

    tmean_7d_mean, tmean_7d_std, tmean_7d_yearly = (
        _yearly_7d_max(daily_df[5]) if 5 in daily_df else (None, None, [])
    )
    tmax_7d_mean, tmax_7d_std, tmax_7d_yearly = (
        _yearly_7d_max(daily_df[6]) if 6 in daily_df else (None, None, [])
    )

    min_1d_mean = None
    min_1d_std = 1.5
    if 7 in daily_df and daily_df[7].dropna().size > 0:
        yr_mins = daily_df[7].groupby(daily_df.index.year).min().dropna()
        if not yr_mins.empty:
            min_1d_mean = float(yr_mins.mean())
            min_1d_std = float(yr_mins.std(ddof=1)) if len(yr_mins) > 1 else 1.5

    t_air_hi = tmax_7d_mean if tmax_7d_mean is not None else tmean_7d_mean
    s_air_hi = tmax_7d_std if tmax_7d_mean is not None else (tmean_7d_std or 1.5)

    tpav_max_98 = None
    tpav_min_98 = None
    pg_grade = "N/D"
    if t_air_hi is not None:
        z_98 = 2.055
        h_depth = 20.0
        tpav_max_98 = (
            54.32
            + 0.78 * t_air_hi
            - 0.0025 * (lat_deg ** 2)
            - 15.14 * math.log10(h_depth + 25.0)
            + z_98 * math.sqrt(9.0 + 0.61 * (s_air_hi ** 2))
        )
        t_air_lo = min_1d_mean if min_1d_mean is not None else 5.0
        tpav_min_98 = (
            -1.56
            + 0.72 * t_air_lo
            - 0.004 * (lat_deg ** 2)
            + 6.26 * math.log10(h_depth + 25.0)
            - z_98 * math.sqrt(4.4 + 0.52 * (min_1d_std ** 2))
        )
        pg_grade = f"PG {_round_pg_high(tpav_max_98)}{_round_pg_low(tpav_min_98)}"

    tmap_data = compute_tmap_shell(
        daily_df=daily_df,
        monthly_temps_clim=monthly_temps_clim,
        annual_precip_mm=annual_precip_mm,
    )

    return {
        **tmap_data,
        "max_7day_tmean_c": round(tmean_7d_mean, 2) if tmean_7d_mean is not None else None,
        "max_7day_tmax_c": round(tmax_7d_mean, 2) if tmax_7d_mean is not None else None,
        "max_7day_tmax_std_c": round(tmax_7d_std, 2) if tmax_7d_std is not None else None,
        "max_7day_yearly": tmax_7d_yearly or tmean_7d_yearly,
        "min_1day_air_c": round(min_1d_mean, 2) if min_1d_mean is not None else None,
        "tpav_max_20mm_98_c": round(tpav_max_98, 2) if tpav_max_98 is not None else None,
        "tpav_min_20mm_98_c": round(tpav_min_98, 2) if tpav_min_98 is not None else None,
        "recommended_pg_grade": pg_grade,
        "days_ge_32c_pct": days_ge_32_pct,
        "dry_days_pct": dry_days_pct,
        "wet_days_total": wet_days_count,
        "freezing_days_total": freezing_days,
        "water_table_m": round(float(water_table_m), 2),
        "thornthwaite_tmi_pct": round(float(thornthwaite_tmi), 2),
    }
