"""Control de calidad, homogeneidad (Pettitt), tendencias (Mann-Kendall/Sen) e índices extremos ETCCDI."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from hidroclima.config import VARIABLES


def mann_kendall_sen(years: np.ndarray, values: np.ndarray) -> dict[str, Any]:
    """Prueba no paramétrica de tendencia de Mann-Kendall y pendiente de Theil-Sen."""
    mask = ~np.isnan(values)
    x = years[mask].astype(np.float64)
    y = values[mask].astype(np.float64)
    n = len(y)
    if n < 5:
        return {"available": False, "n_years": n, "message": "Se requieren al menos 5 años para tendencia Mann-Kendall."}

    s = 0
    slopes: list[float] = []
    for i in range(n - 1):
        diffs = y[i + 1 :] - y[i]
        dx = x[i + 1 :] - x[i]
        s += int(np.sum(np.sign(diffs)))
        valid_dx = dx > 0
        if np.any(valid_dx):
            slopes.extend((diffs[valid_dx] / dx[valid_dx]).tolist())

    _, counts = np.unique(y, return_counts=True)
    ties = counts[counts > 1]
    tie_term = float(np.sum(ties * (ties - 1) * (2 * ties + 5))) if ties.size else 0.0
    var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0

    if var_s <= 0:
        z = 0.0
    elif s > 0:
        z = (s - 1.0) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1.0) / math.sqrt(var_s)
    else:
        z = 0.0

    p_value = float(2.0 * (1.0 - stats.norm.cdf(abs(z))))
    sen_slope = float(np.median(slopes)) if slopes else 0.0

    if p_value < 0.05:
        trend_label = "Tendencia creciente significativa (p < 0.05)" if sen_slope > 0 else "Tendencia decreciente significativa (p < 0.05)"
    elif p_value < 0.10:
        trend_label = "Tendencia creciente moderada (p < 0.10)" if sen_slope > 0 else "Tendencia decreciente moderada (p < 0.10)"
    else:
        trend_label = "Sin tendencia estadísticamente significativa"

    return {
        "available": True,
        "n_years": n,
        "z_stat": round(z, 3),
        "p_value": round(p_value, 4),
        "sen_slope_per_year": round(sen_slope, 4),
        "sen_slope_per_decade": round(sen_slope * 10.0, 3),
        "trend": trend_label,
    }


def pettitt_homogeneity_test(years: np.ndarray, values: np.ndarray) -> dict[str, Any]:
    """
    Prueba no paramétrica de Pettitt (1979) para detección de punto de cambio y homogeneidad
    de series climáticas anuales (requerida en estudios hidrológicos ANLA / POMCA).
    """
    mask = ~np.isnan(values)
    x = years[mask].astype(int)
    y = values[mask].astype(np.float64)
    n = len(y)
    if n < 6:
        return {"available": False, "n_years": n, "message": "Se requieren al menos 6 años para prueba de Pettitt."}

    u_vals = np.zeros(n - 1, dtype=np.float64)
    for t in range(1, n):
        diff_mat = y[:t, None] - y[None, t:]
        u_vals[t - 1] = float(np.sum(np.sign(diff_mat)))

    abs_u = np.abs(u_vals)
    idx_max = int(np.argmax(abs_u))
    k_stat = float(abs_u[idx_max])
    change_year = int(x[idx_max])
    p_approx = min(1.0, 2.0 * math.exp((-6.0 * (k_stat ** 2)) / (n ** 3 + n ** 2)))

    homogeneous = p_approx >= 0.05
    return {
        "available": True,
        "n_years": n,
        "k_stat": round(k_stat, 1),
        "p_value": round(p_approx, 4),
        "change_year": change_year,
        "homogeneous": homogeneous,
        "status": "Serie homogénea (p >= 0.05)" if homogeneous else f"Posible cambio de media alrededor de {change_year} (p < 0.05)",
    }


def _max_consecutive_run(bool_arr: np.ndarray) -> int:
    best = 0
    cur = 0
    for val in bool_arr:
        if val:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def compute_etccdi_indices(daily_df: pd.DataFrame) -> dict[str, Any]:
    """Calcula índices climáticos extremos estándar OMM / ETCCDI para informes ambientales y riesgo."""
    out: dict[str, Any] = {}
    if 1 in daily_df and daily_df[1].notna().any():
        p = daily_df[1].dropna()
        rx1 = float(p.max())
        rx5_roll = daily_df[1].rolling(window=5, min_periods=3).sum()
        rx5 = float(rx5_roll.max()) if rx5_roll.notna().any() else rx1
        p_full = daily_df[1].to_numpy(dtype=np.float64)
        valid_p = ~np.isnan(p_full)
        cdd = _max_consecutive_run(valid_p & (p_full < 1.0))
        cwd = _max_consecutive_run(valid_p & (p_full >= 1.0))
        n_years = max(1.0, len(p) / 365.25)
        r10 = round(float((p >= 10.0).sum()) / n_years, 1)
        r20 = round(float((p >= 20.0).sum()) / n_years, 1)
        r50 = round(float((p >= 50.0).sum()) / n_years, 1)
        out.update({
            "rx1day_mm": round(rx1, 1),
            "rx5day_mm": round(rx5, 1),
            "cdd_max_dry_days": cdd,
            "cwd_max_wet_days": cwd,
            "r10mm_days_yr": r10,
            "r20mm_days_yr": r20,
            "r50mm_days_yr": r50,
        })

    if 6 in daily_df and daily_df[6].notna().any():
        tx = daily_df[6].dropna()
        n_years_t = max(1.0, len(tx) / 365.25)
        out["txx_abs_max_c"] = round(float(tx.max()), 2)
        out["su25_days_yr"] = round(float((tx >= 25.0).sum()) / n_years_t, 1)
        out["su32_days_yr"] = round(float((tx >= 32.0).sum()) / n_years_t, 1)

    if 7 in daily_df and daily_df[7].notna().any():
        tn = daily_df[7].dropna()
        out["tnn_abs_min_c"] = round(float(tn.min()), 2)

    return out


def compute_quality_report(daily_df: pd.DataFrame) -> dict[str, Any]:
    """Calcula completitud, alertas físicas, tendencias Mann-Kendall, homogeneidad Pettitt e índices ETCCDI."""
    if daily_df.empty:
        return {"completeness_matrix": [], "variable_summary": [], "trends": {}, "homogeneity": {}, "etccdi": {}}

    years = sorted(daily_df.index.year.unique().tolist())
    active_vars = [vid for vid in daily_df.columns if vid in VARIABLES and daily_df[vid].notna().any()]

    var_summary = []
    outliers_total = 0
    for vid in active_vars:
        spec = VARIABLES[vid]
        s = daily_df[vid]
        total_days = len(s)
        valid_cnt = int(s.notna().sum())
        pct = round(100.0 * valid_cnt / max(1, total_days), 2)
        out_mask = s.notna() & ((s < spec.min_val) | (s > spec.max_val))
        n_out = int(out_mask.sum())
        outliers_total += n_out
        var_summary.append({
            "var_id": vid,
            "name": spec.nombre_corto,
            "unit": spec.unidad,
            "valid_days": valid_cnt,
            "total_days": total_days,
            "completeness_pct": pct,
            "out_of_range_count": n_out,
        })

    matrix_rows = []
    for yr in years:
        sub = daily_df[daily_df.index.year == yr]
        row: dict[str, Any] = {"year": int(yr)}
        for vid in active_vars:
            row[str(vid)] = round(100.0 * float(sub[vid].notna().sum()) / max(1, len(sub)), 1)
        matrix_rows.append(row)

    trends: dict[str, Any] = {}
    homogeneity: dict[str, Any] = {}
    if 1 in daily_df:
        ann_p, ann_yp = [], []
        for yr in years:
            sub = daily_df.loc[daily_df.index.year == yr, 1].dropna()
            if len(sub) >= int(0.75 * 365):
                ann_yp.append(yr)
                ann_p.append(float(sub.sum()))
        trends["precip_annual"] = mann_kendall_sen(np.array(ann_yp), np.array(ann_p))
        homogeneity["precip_annual"] = pettitt_homogeneity_test(np.array(ann_yp), np.array(ann_p))

    if 5 in daily_df:
        ann_t, ann_yt = [], []
        for yr in years:
            sub = daily_df.loc[daily_df.index.year == yr, 5].dropna()
            if len(sub) >= int(0.75 * 365):
                ann_yt.append(yr)
                ann_t.append(float(sub.mean()))
        trends["temp_mean_annual"] = mann_kendall_sen(np.array(ann_yt), np.array(ann_t))
        homogeneity["temp_mean_annual"] = pettitt_homogeneity_test(np.array(ann_yt), np.array(ann_t))

    etccdi = compute_etccdi_indices(daily_df)

    return {
        "years": years,
        "active_vars": active_vars,
        "variable_summary": var_summary,
        "completeness_matrix": matrix_rows,
        "outliers_total": outliers_total,
        "trends": trends,
        "homogeneity": homogeneity,
        "etccdi": etccdi,
    }
