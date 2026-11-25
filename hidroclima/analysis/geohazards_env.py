"""Módulos especializados: Geotecnia SGC (lluvias detonantes), Erosividad RUSLE (ANLA), Sequías (SPEI/IAP) y Cuenca SCS-CN (INVIAS)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def _rolling_quantiles(s: pd.Series) -> dict[str, Any]:
    valid = s.dropna()
    if valid.empty:
        return {"mean": None, "p90": None, "p95": None, "p99": None, "max": None, "date_max": None}
    idx_max = valid.idxmax()
    return {
        "mean": round(float(valid.mean()), 2),
        "p90": round(float(np.percentile(valid.to_numpy(), 90)), 2),
        "p95": round(float(np.percentile(valid.to_numpy(), 95)), 2),
        "p99": round(float(np.percentile(valid.to_numpy(), 99)), 2),
        "max": round(float(valid.max()), 2),
        "date_max": idx_max.strftime("%Y-%m-%d"),
    }


def compute_sgc_landslide_thresholds(
    daily_df: pd.DataFrame,
    soil_cn: float = 75.0,
    r3_intercept: float = 70.0,
    r15_slope: float = 0.47,
) -> dict[str, Any]:
    """
    Análisis geotécnico de precipitaciones detonantes de movimientos en masa según guías del
    Servicio Geológico Colombiano (SGC):
    - Lluvia diaria (R1) y acumulada antecedente (R3, R7, R15, R30, R90 días).
    - Umbral empírico combinado (Moreno et al. / SGC): R3_crit = max(5, r3_intercept - r15_slope * R15_ant),
      donde R15_ant es la lluvia de los 15 días inmediatamente anteriores a la ventana R3.
    - Episodios históricos críticos de excedencia y balance diario de infiltración SCS-CN (AMC I/II/III).
    """
    if 1 not in daily_df or daily_df[1].dropna().empty:
        return {"available": False, "message": "Sin datos diarios de precipitación para análisis geotécnico SGC."}

    p_raw = daily_df[1].sort_index()
    full_idx = pd.date_range(p_raw.index.min(), p_raw.index.max(), freq="D")
    p = p_raw.reindex(full_idx)

    r1 = p
    r3 = p.rolling(3, min_periods=2).sum()
    r7 = p.rolling(7, min_periods=5).sum()
    r15_tot = p.rolling(15, min_periods=10).sum()
    r30 = p.rolling(30, min_periods=20).sum()
    r90 = p.rolling(90, min_periods=60).sum()
    r15_ant = p.shift(3).rolling(15, min_periods=10).sum()

    rolling_stats = {
        "R1 (24h)": _rolling_quantiles(r1),
        "R3 (3 días)": _rolling_quantiles(r3),
        "R7 (7 días)": _rolling_quantiles(r7),
        "R15 (15 días)": _rolling_quantiles(r15_tot),
        "R30 (30 días)": _rolling_quantiles(r30),
        "R90 (90 días)": _rolling_quantiles(r90),
    }

    # Evaluación diaria de superación de umbral crítico (R3 >= max(5, a - b * R15_ant)) en días húmedos (R1 >= 1 mm)
    df_ev = pd.DataFrame({
        "r1": r1,
        "r3": r3,
        "r15_ant": r15_ant,
        "r30": r30,
    }).dropna(subset=["r1", "r3", "r15_ant"])

    cn_ii = float(np.clip(soil_cn, 30.0, 99.0))
    cn_i = round(4.2 * cn_ii / (10.0 - 0.058 * cn_ii), 1)
    cn_iii = round(23.0 * cn_ii / (10.0 + 0.13 * cn_ii), 1)
    s_mm = (25400.0 / cn_ii) - 254.0
    ia_mm = 0.2 * s_mm

    if df_ev.empty:
        return {
            "available": True,
            "days_evaluated": 0,
            "rolling_stats": rolling_stats,
            "threshold_eq": f"R3 >= máx(5, {r3_intercept:.1f} - {r15_slope:.2f} · R15_ant)",
            "r3_intercept": round(r3_intercept, 2),
            "r15_slope": round(r15_slope, 3),
            "exceedance_days": 0,
            "exceedance_rate_pct": 0.0,
            "episodes": [],
            "annual_exceedances": [],
            "scatter_points": [],
            "infiltration_balance": {
                "cn_i": cn_i,
                "cn_ii": round(cn_ii, 1),
                "cn_iii": cn_iii,
                "s_max_mm": round(s_mm, 1),
                "ia_mm": round(ia_mm, 1),
                "mean_annual_runoff_mm": 0.0,
                "mean_annual_infiltration_mm": 0.0,
            },
        }

    thresh_vals = np.maximum(5.0, float(r3_intercept) - float(r15_slope) * df_ev["r15_ant"].to_numpy())
    df_ev["threshold_r3"] = thresh_vals
    df_ev["exceeds"] = (df_ev["r3"] >= df_ev["threshold_r3"]) & (df_ev["r1"] >= 1.0)
    df_ev["ratio"] = df_ev["r3"] / np.maximum(1.0, df_ev["threshold_r3"])

    # Balance diario SCS lluvia -> abstracción/infiltración + escorrentía directa
    p_valid = p.dropna()
    p_arr = p_valid.to_numpy(dtype=np.float64)
    q_daily = np.where(p_arr > ia_mm, ((p_arr - ia_mm) ** 2) / (p_arr - ia_mm + s_mm), 0.0)
    infilt_daily = np.maximum(0.0, p_arr - q_daily)
    n_yrs = max(1.0, len(p_arr) / 365.25)

    # Agrupar días críticos separados <= 3 días en episodios independientes
    exc_df = df_ev[df_ev["exceeds"]].copy()
    episodes: list[dict[str, Any]] = []
    if not exc_df.empty:
        cur_group: list[tuple[pd.Timestamp, pd.Series]] = []
        for dt, row in exc_df.iterrows():
            if cur_group and (dt - cur_group[-1][0]).days <= 3:
                cur_group.append((dt, row))
            else:
                if cur_group:
                    episodes.append(_summarize_episode(cur_group))
                cur_group = [(dt, row)]
        if cur_group:
            episodes.append(_summarize_episode(cur_group))
        episodes.sort(key=lambda e: (-e["severity_ratio"], -e["r3_peak_mm"]))

    ann_exc = (
        df_ev.groupby(df_ev.index.year)["exceeds"]
        .sum()
        .reset_index()
        .rename(columns={"index": "year"})
    )
    annual_exceedances = [{"year": int(r.iloc[0]), "exceedance_days": int(r["exceeds"])} for _, r in ann_exc.iterrows()]

    # Muestra equilibrada para dispersión R15_ant vs R3 (todos los excedentes + hasta 450 días húmedos normales)
    wet_normal = df_ev[(~df_ev["exceeds"]) & (df_ev["r1"] >= 1.0)]
    if len(wet_normal) > 450:
        stride = max(1, len(wet_normal) // 450)
        wet_normal = wet_normal.iloc[::stride][:450]

    scatter_points: list[dict[str, Any]] = []
    for dt, row in wet_normal.iterrows():
        scatter_points.append({
            "date": dt.strftime("%Y-%m-%d"),
            "r15_ant": round(float(row["r15_ant"]), 1),
            "r3": round(float(row["r3"]), 1),
            "exceeds": False,
        })
    for dt, row in exc_df.head(350).iterrows():
        scatter_points.append({
            "date": dt.strftime("%Y-%m-%d"),
            "r15_ant": round(float(row["r15_ant"]), 1),
            "r3": round(float(row["r3"]), 1),
            "exceeds": True,
        })

    return {
        "available": True,
        "days_evaluated": int(len(df_ev)),
        "rolling_stats": rolling_stats,
        "threshold_eq": f"R3 >= máx(5, {r3_intercept:.1f} - {r15_slope:.2f} · R15_ant)",
        "r3_intercept": round(r3_intercept, 2),
        "r15_slope": round(r15_slope, 3),
        "exceedance_days": int(len(exc_df)),
        "exceedance_rate_pct": round(100.0 * len(exc_df) / max(1, len(df_ev)), 2),
        "episodes_count": len(episodes),
        "episodes": episodes[:15],
        "annual_exceedances": annual_exceedances,
        "scatter_points": scatter_points,
        "infiltration_balance": {
            "cn_i": cn_i,
            "cn_ii": round(cn_ii, 1),
            "cn_iii": cn_iii,
            "s_max_mm": round(s_mm, 1),
            "ia_mm": round(ia_mm, 1),
            "mean_annual_runoff_mm": round(float(q_daily.sum() / n_yrs), 1),
            "mean_annual_infiltration_mm": round(float(infilt_daily.sum() / n_yrs), 1),
        },
    }


def _summarize_episode(items: list[tuple[pd.Timestamp, pd.Series]]) -> dict[str, Any]:
    peak_dt, peak_row = max(items, key=lambda x: float(x[1]["ratio"]))
    return {
        "start_date": items[0][0].strftime("%Y-%m-%d"),
        "end_date": items[-1][0].strftime("%Y-%m-%d"),
        "duration_days": int((items[-1][0] - items[0][0]).days + 1),
        "peak_date": peak_dt.strftime("%Y-%m-%d"),
        "r1_peak_mm": round(float(max(x[1]["r1"] for x in items)), 1),
        "r3_peak_mm": round(float(peak_row["r3"]), 1),
        "r15_ant_mm": round(float(peak_row["r15_ant"]), 1),
        "r30_mm": round(float(peak_row["r30"]) if pd.notna(peak_row["r30"]) else 0.0, 1),
        "threshold_r3_mm": round(float(peak_row["threshold_r3"]), 1),
        "severity_ratio": round(float(peak_row["ratio"]), 2),
    }


def compute_erosivity_rusle(monthly_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calcula erosividad pluvial (Factor R de RUSLE) e índices de estacionalidad requeridos
    en Estudios de Impacto Ambiental (ANLA) y ENA-IDEAM:
    - Índice de Fournier Modificado (MFI - Arnoldus 1980): F = sum(p_i^2) / P
    - Índice de Concentración de Precipitación (PCI - Oliver 1980): 100 * sum(p_i^2) / P^2
    - Factor R RUSLE (Renard & Freimund 1994 en SI: MJ·mm/(ha·h·año)) por F y por P.
    """
    if len(monthly_rows) != 12:
        return {"available": False}

    p_m = np.array([max(0.0, float(r.get("precip_mm") or 0.0)) for r in monthly_rows], dtype=np.float64)
    p_ann = float(np.sum(p_m))
    if p_ann <= 1e-6:
        return {"available": False}

    sum_p2 = float(np.sum(p_m ** 2))
    fi = float(np.max(p_m) ** 2 / p_ann)
    mfi = float(sum_p2 / p_ann)
    pci = float(100.0 * sum_p2 / (p_ann ** 2))

    if mfi < 55.0:
        r_mfi = 0.7397 * (mfi ** 1.847)
    else:
        r_mfi = 95.77 - 6.081 * mfi + 0.4770 * (mfi ** 2)

    if p_ann < 850.0:
        r_precip = 0.0483 * (p_ann ** 1.61)
    else:
        r_precip = 587.8 - 1.219 * p_ann + 0.004105 * (p_ann ** 2)

    if mfi < 60.0:
        aggr = "Muy baja"
    elif mfi < 90.0:
        aggr = "Baja"
    elif mfi < 120.0:
        aggr = "Moderada"
    elif mfi < 160.0:
        aggr = "Alta"
    else:
        aggr = "Muy alta"

    if pci <= 10.0:
        pci_cls = "Uniforme (sin estacionalidad marcada)"
    elif pci <= 15.0:
        pci_cls = "Moderadamente estacional"
    elif pci <= 20.0:
        pci_cls = "Estacional (lluvias concentradas)"
    else:
        pci_cls = "Fuertemente estacional"

    monthly_r = []
    for idx, r in enumerate(monthly_rows):
        share = float((p_m[idx] ** 2) / max(1e-9, sum_p2))
        monthly_r.append({
            "month": r["month_abbr"],
            "precip_mm": round(float(p_m[idx]), 1),
            "r_share_pct": round(share * 100.0, 1),
            "r_mfi_month": round(r_mfi * share, 1),
        })

    return {
        "available": True,
        "p_annual_mm": round(p_ann, 1),
        "fournier_fi_mm": round(fi, 2),
        "mfi_arnoldus_mm": round(mfi, 2),
        "aggressiveness_class": aggr,
        "pci_oliver_pct": round(pci, 2),
        "pci_class": pci_cls,
        "r_factor_mfi": round(max(0.0, r_mfi), 1),
        "r_factor_precip": round(max(0.0, r_precip), 1),
        "unit": "MJ·mm/(ha·h·año)",
        "monthly_distribution": monthly_r,
    }


def compute_spei_and_anomalies(
    daily_df: pd.DataFrame,
    et0_series: pd.Series,
    annual_rows: list[dict[str, Any]],
    scales: tuple[int, ...] = (3, 12),
) -> dict[str, Any]:
    """
    Calcula SPEI (Vicente-Serrano et al., 2010) con D = P - ET0 ajustado mediante distribución
    Log-Logística (Fisk 3P), además del Índice de Anomalías de Precipitación (IAP % IDEAM).
    """
    out: dict[str, Any] = {"available": False, "spei_3": [], "spei_12": [], "iap_annual": [], "summary": {}}

    # IAP anual IDEAM: 100 * (P_año - P_media) / P_media  e índice porcentual P/P_media*100
    valid_ann = [r for r in annual_rows if r.get("precip_mm") is not None and r.get("completeness_precip_pct", 0) >= 65.0]
    if len(valid_ann) < 2:
        valid_ann = [r for r in annual_rows if r.get("precip_mm") is not None]
    if valid_ann:
        pma = float(np.mean([r["precip_mm"] for r in valid_ann]))
        iap_rows = []
        for r in valid_ann:
            anom = ((r["precip_mm"] - pma) / max(1e-6, pma)) * 100.0
            if anom >= 25.0:
                cat = "Muy húmedo (posible La Niña)"
            elif anom >= 10.0:
                cat = "Por encima de lo normal"
            elif anom > -10.0:
                cat = "Normal"
            elif anom > -25.0:
                cat = "Déficit moderado"
            else:
                cat = "Déficit severo (posible El Niño)"
            iap_rows.append({
                "year": r["year"],
                "precip_mm": round(r["precip_mm"], 1),
                "iap_pct": round(100.0 + anom, 1),
                "anomaly_pct": round(anom, 1),
                "category": cat,
            })
        out["iap_annual"] = iap_rows

    if 1 not in daily_df or et0_series.dropna().empty:
        out["available"] = bool(out["iap_annual"])
        return out

    p_mon = daily_df[1].resample("ME").agg(lambda s: s.sum() if s.notna().sum() >= 15 else np.nan)
    e_mon = et0_series.resample("ME").agg(lambda s: s.sum() if s.notna().sum() >= 15 else np.nan)
    d_mon = (p_mon - e_mon).dropna()

    for k in scales:
        roll = d_mon.rolling(window=k, min_periods=k).sum()
        spei_vals = pd.Series(np.nan, index=roll.index)
        for mo in range(1, 13):
            sub = roll[roll.index.month == mo].dropna()
            if len(sub) < 4:
                continue
            arr = sub.to_numpy(dtype=np.float64)
            if np.std(arr) <= 1e-6:
                continue
            try:
                c_shp, loc_g, scale_a = stats.fisk.fit(arr)
                cdf_vals = stats.fisk.cdf(arr, c_shp, loc=loc_g, scale=scale_a)
            except Exception:
                ranks = stats.rankdata(arr)
                cdf_vals = (ranks - 0.44) / (len(arr) + 0.12)
            cdf_vals = np.clip(cdf_vals, 1e-4, 1.0 - 1e-4)
            z_vals = np.clip(stats.norm.ppf(cdf_vals), -3.5, 3.5)
            spei_vals.loc[sub.index] = z_vals

        clean = spei_vals.dropna()
        out[f"spei_{k}"] = [{"date": dt.strftime("%Y-%m"), "value": round(float(v), 2)} for dt, v in clean.items()]

    s3 = out["spei_3"]
    if s3:
        vals3 = np.array([x["value"] for x in s3], dtype=float)
        worst = min(s3, key=lambda x: x["value"])
        wettest = max(s3, key=lambda x: x["value"])
        out["summary"] = {
            "months_count": len(s3),
            "drought_moderate_pct": round(100.0 * float(np.mean(vals3 <= -1.0)), 1),
            "drought_severe_pct": round(100.0 * float(np.mean(vals3 <= -1.5)), 1),
            "drought_extreme_pct": round(100.0 * float(np.mean(vals3 <= -2.0)), 1),
            "min_spei3": worst["value"],
            "min_spei3_date": worst["date"],
            "max_spei3": wettest["value"],
            "max_spei3_date": wettest["date"],
        }

    out["available"] = bool(out["spei_3"] or out["iap_annual"])
    return out


def compute_watershed_runoff_scs(
    idf_result: dict[str, Any],
    area_km2: float = 1.0,
    length_m: float = 800.0,
    slope_pct: float = 5.0,
    curve_number: float = 75.0,
    runoff_coeff: float = 0.50,
) -> dict[str, Any]:
    """
    Transformación lluvia-escorrentía según Manual de Drenaje INVIAS / SCS:
    - Tiempo de concentración tc: Kirpich (min) y Témez (h->min).
    - Caudal pico Racional Q = C * I(Tr, tc) * A / 3.6 (m3/s).
    - Escorrentía directa Qe (mm), infiltración potencial F (mm) y caudal pico SCS
      sobre lámina de tormenta de diseño para duración = tc (o 60 min mínimo referencia).
    """
    if not idf_result.get("available"):
        return {"available": False, "message": "Requiere curvas IDF válidas para estimar caudales de diseño."}

    area = max(0.001, float(area_km2))
    length = max(20.0, float(length_m))
    slope = max(0.1, float(slope_pct)) / 100.0  # m/m
    cn = float(np.clip(curve_number, 30.0, 99.0))
    c_rat = float(np.clip(runoff_coeff, 0.05, 0.98))

    # Kirpich (1940): tc(min) = 0.01947 * L(m)^0.77 * S(m/m)^(-0.385)
    tc_kirpich = max(5.0, 0.01947 * (length ** 0.77) * (slope ** -0.385))
    # Témez (1978): tc(h) = 0.3 * (L(km) / S(m/m)^0.25)^0.76
    tc_temez = max(5.0, 60.0 * 0.3 * ((length / 1000.0) / (slope ** 0.25)) ** 0.76)
    tc_design = round(tc_kirpich, 2)

    s_mm = (25400.0 / cn) - 254.0
    ia_mm = 0.2 * s_mm

    idf_table = idf_result["idf_table"]
    durs_avail = np.array([r["duration_min"] for r in idf_table], dtype=float)
    trs_eval = [2, 5, 10, 20, 25, 50, 100]

    # Hidrograma unitario triangular SCS
    tp_h = 0.5 * (tc_design / 60.0) + 0.6 * (tc_design / 60.0)  # D ≈ tc -> tp = 1.1 tc
    tb_h = 2.67 * tp_h

    rows = []
    for tr in trs_eval:
        col_key = f"tr_{tr}"
        ints = np.array([r.get(col_key, 0.0) for r in idf_table], dtype=float)
        i_tc = float(np.interp(np.clip(tc_design, durs_avail[0], durs_avail[-1]), durs_avail, ints))
        q_rational = (c_rat * i_tc * area) / 3.6  # m3/s

        # Tormenta equivalente sobre D = max(60 min, tc) para lámina SCS
        dur_storm_h = max(1.0, tc_design / 60.0)
        p_storm = float(np.interp(np.clip(dur_storm_h * 60.0, durs_avail[0], durs_avail[-1]), durs_avail, ints)) * dur_storm_h
        qe_scs = ((p_storm - ia_mm) ** 2) / (p_storm - ia_mm + s_mm) if p_storm > ia_mm else 0.0
        f_infilt = max(0.0, p_storm - min(p_storm, ia_mm) - qe_scs)
        q_scs = (0.208 * area * qe_scs) / max(0.05, tp_h)  # m3/s

        rows.append({
            "tr": tr,
            "i_tc_mmh": round(i_tc, 2),
            "q_rational_m3s": round(q_rational, 3),
            "p_storm_mm": round(p_storm, 2),
            "qe_runoff_mm": round(qe_scs, 2),
            "infiltration_mm": round(f_infilt, 2),
            "q_scs_m3s": round(q_scs, 3),
        })

    return {
        "available": True,
        "area_km2": round(area, 4),
        "area_ha": round(area * 100.0, 2),
        "length_m": round(length, 1),
        "slope_pct": round(slope * 100.0, 2),
        "curve_number": round(cn, 1),
        "runoff_coeff": round(c_rat, 2),
        "tc_kirpich_min": tc_design,
        "tc_temez_min": round(tc_temez, 2),
        "s_max_mm": round(s_mm, 1),
        "ia_mm": round(ia_mm, 1),
        "scs_tp_h": round(tp_h, 3),
        "scs_tb_h": round(tb_h, 3),
        "design_rows": rows,
    }
