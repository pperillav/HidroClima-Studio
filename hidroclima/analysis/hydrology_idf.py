"""Hidrología extrema: Frecuencia (Gumbel, Log-Normal, LP-III, GEV + K-S), Curvas IDF (INVIAS, Silva, Sherman, Bell), Hietogramas y RAS."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from hidroclima.config import (
    IDF_DURATIONS_MIN,
    IDF_REGIONS,
    IDF_RETURN_PERIODS,
    NORMATIVE_RETURN_PERIODS,
)


def _gringorten_plotting_positions(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Posiciones empíricas de Weibull/Gringorten ordenadas ascendentemente."""
    x_sorted = np.sort(values)
    n = len(x_sorted)
    ranks = np.arange(1, n + 1, dtype=np.float64)
    # Gringorten (apropiado para valores extremos): F_i = (i - 0.44) / (n + 0.12)
    f_emp = (ranks - 0.44) / (n + 0.12)
    return x_sorted, f_emp


def _fit_extreme_distributions(values: np.ndarray) -> dict[str, Any]:
    """
    Ajusta 4 distribuciones clásicas de hidrología sobre máximos anuales de 24h:
    Gumbel Tipo I, Log-Normal, Log-Pearson Tipo III y GEV.
    Evalúa bondad de ajuste con Kolmogorov-Smirnov (D, p-value) y R² empírico.
    """
    n = len(values)
    m_mean = float(np.mean(values))
    s_std = float(np.std(values, ddof=1)) if n > 1 else 0.0
    x_sorted, f_emp = _gringorten_plotting_positions(values)

    results: dict[str, dict[str, Any]] = {}

    def _eval_fit(name: str, cdf_vals: np.ndarray, ppf_fn) -> None:
        ks_d = float(np.max(np.abs(f_emp - cdf_vals)))
        # P-valor aproximado de Kolmogorov-Smirnov
        ks_p = float(stats.kstwo.sf(ks_d, n)) if n >= 3 else 1.0
        q_pred_emp = np.array([ppf_fn(f) for f in f_emp], dtype=np.float64)
        ss_res = float(np.sum((x_sorted - q_pred_emp) ** 2))
        ss_tot = float(np.sum((x_sorted - np.mean(x_sorted)) ** 2))
        r2 = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 1e-9 else 1.0
        quantiles = []
        for tr in IDF_RETURN_PERIODS:
            p_ex = 1.0 - 1.0 / tr
            val = max(0.0, float(ppf_fn(p_ex)))
            quantiles.append({"tr": tr, "p24h_mm": round(val, 2)})
        results[name] = {
            "name": name,
            "ks_d": round(ks_d, 4),
            "ks_pvalue": round(ks_p, 4),
            "r2": round(r2, 4),
            "quantiles": quantiles,
        }

    # 1. Gumbel Tipo I (método de momentos Ven Te Chow)
    if s_std > 1e-6:
        scale_g = s_std * math.sqrt(6.0) / math.pi
        loc_g = m_mean - 0.5772156649 * scale_g
        cdf_g = stats.gumbel_r.cdf(x_sorted, loc=loc_g, scale=scale_g)
        _eval_fit("Gumbel", cdf_g, lambda f: stats.gumbel_r.ppf(f, loc=loc_g, scale=scale_g))
    else:
        _eval_fit("Gumbel", f_emp, lambda _f: m_mean)

    pos_vals = values[values > 0]
    if len(pos_vals) >= 3 and np.std(np.log10(pos_vals)) > 1e-6:
        log_x = np.log10(pos_vals)
        lp_mu = float(np.mean(log_x))
        lp_sd = float(np.std(log_x, ddof=1))

        # 2. Log-Normal (2 parámetros)
        cdf_ln = stats.norm.cdf(np.log10(np.maximum(1e-6, x_sorted)), loc=lp_mu, scale=lp_sd)
        _eval_fit("Log-Normal", cdf_ln, lambda f: 10.0 ** stats.norm.ppf(f, loc=lp_mu, scale=lp_sd))

        # 3. Log-Pearson Tipo III
        skew_g = float(stats.skew(log_x, bias=False))
        if abs(skew_g) < 1e-4:
            _eval_fit("Log-Pearson III", cdf_ln, lambda f: 10.0 ** stats.norm.ppf(f, loc=lp_mu, scale=lp_sd))
        else:
            # pearson3 usa skew, loc=media, scale=desviación
            cdf_lp3 = stats.pearson3.cdf(np.log10(np.maximum(1e-6, x_sorted)), skew=skew_g, loc=lp_mu, scale=lp_sd)
            _eval_fit("Log-Pearson III", cdf_lp3, lambda f: 10.0 ** stats.pearson3.ppf(f, skew=skew_g, loc=lp_mu, scale=lp_sd))
    else:
        _eval_fit("Log-Normal", f_emp, lambda _f: m_mean)
        _eval_fit("Log-Pearson III", f_emp, lambda _f: m_mean)

    # 4. GEV (Valor Extremo Generalizado)
    if n >= 5 and s_std > 1e-6:
        try:
            c_gev, loc_gev, scale_gev = stats.genextreme.fit(values)
            cdf_gev = stats.genextreme.cdf(x_sorted, c_gev, loc=loc_gev, scale=scale_gev)
            _eval_fit("GEV", cdf_gev, lambda f: stats.genextreme.ppf(f, c_gev, loc=loc_gev, scale=scale_gev))
        except Exception:
            results["GEV"] = {**results["Gumbel"], "name": "GEV"}
    else:
        results["GEV"] = {**results["Gumbel"], "name": "GEV"}

    # Mejor ajuste por menor estadístico K-S D (y desempate por mayor R²)
    best_name = min(results.keys(), key=lambda k: (results[k]["ks_d"], -results[k]["r2"]))
    empirical_pts = [
        {"tr": round(float(1.0 / max(1e-4, 1.0 - f)), 2), "p24h_mm": round(float(x), 2)}
        for x, f in zip(x_sorted, f_emp)
    ]
    return {
        "best_distribution": best_name,
        "distributions": results,
        "empirical_points": empirical_pts,
    }


def _build_idf_table(
    idf_method: str,
    m_mean: float,
    region_name: str,
    dist_quantiles: dict[int, float],
    silva_ratio_1h_24h: float = 0.48,
    silva_b_min: float = 10.0,
    silva_n: float = 0.50,
    custom_params: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Construye matriz de intensidades IDF (mm/h) según el método seleccionado:
    - 'invias': Vargas & Díaz-Granados (1998) regionalizado INVIAS
    - 'silva': Desagregación Gustavo Silva / UNAL-IDEAM desde P24h_Tr
    - 'sherman': Ecuación general de Sherman I = k * T^m / (t + c)^n
    - 'bell': Ecuación generalizada de Bell (1969) desde P_60^10 estimado
    """
    method = (idf_method or "invias").lower()
    table: list[dict[str, Any]] = []

    if method == "silva":
        for dur_min in IDF_DURATIONS_MIN:
            row: dict[str, Any] = {"duration_min": dur_min}
            for tr in IDF_RETURN_PERIODS:
                p24_tr = dist_quantiles.get(tr, m_mean)
                p1_tr = p24_tr * silva_ratio_1h_24h
                a_tr = p1_tr * ((60.0 + silva_b_min) ** silva_n)
                intensity = a_tr / ((dur_min + silva_b_min) ** silva_n)
                row[f"tr_{tr}"] = round(float(intensity), 2)
            table.append(row)
        meta = {
            "method": "silva",
            "method_label": "Gustavo Silva (Desagregación P24h → P1h)",
            "region": region_name,
            "formula": f"I(Tr,t) = [P24h(Tr)·{silva_ratio_1h_24h}·(60+{silva_b_min})^{silva_n}] / (t+{silva_b_min})^{silva_n}",
            "silva_ratio_1h_24h": silva_ratio_1h_24h,
            "b": silva_b_min,
            "n": silva_n,
        }
        return table, meta

    if method == "sherman":
        cp = custom_params or {}
        k = float(cp.get("k", 950.0))
        m_exp = float(cp.get("m", 0.18))
        c_t0 = float(cp.get("c", 12.0))
        n_exp = float(cp.get("n", 0.72))
        for dur_min in IDF_DURATIONS_MIN:
            row = {"duration_min": dur_min}
            for tr in IDF_RETURN_PERIODS:
                intensity = k * (tr ** m_exp) / ((dur_min + c_t0) ** n_exp)
                row[f"tr_{tr}"] = round(float(intensity), 2)
            table.append(row)
        meta = {
            "method": "sherman",
            "method_label": "Sherman Generalizada / Local",
            "region": "Local / Calibrada",
            "formula": f"I(Tr,t) = {k} · Tr^{m_exp} / (t + {c_t0})^{n_exp}",
            "k": k, "m": m_exp, "c": c_t0, "n": n_exp,
        }
        return table, meta

    if method == "bell":
        # P_60^10 estimado desde P24h(Tr=10) usando relación convectiva 0.48
        p10_24 = dist_quantiles.get(10, m_mean * 1.35)
        p10_60 = p10_24 * silva_ratio_1h_24h
        for dur_min in IDF_DURATIONS_MIN:
            row = {"duration_min": dur_min}
            dur_h = dur_min / 60.0
            for tr in IDF_RETURN_PERIODS:
                f_tr = 0.21 * math.log(max(1.1, tr)) + 0.52
                f_t = 0.54 * (dur_min ** 0.25) - 0.50
                depth_mm = max(0.5, f_tr * f_t * p10_60)
                intensity = depth_mm / dur_h
                row[f"tr_{tr}"] = round(float(intensity), 2)
            table.append(row)
        meta = {
            "method": "bell",
            "method_label": "Bell (1969) Generalizada",
            "region": region_name,
            "formula": f"P(Tr,t) = (0.21·ln(Tr)+0.52)·(0.54·t^0.25-0.50)·P60^10  (P60^10={p10_60:.1f} mm)",
            "p10_60_mm": round(p10_60, 2),
        }
        return table, meta

    # Default: 'invias' — Vargas & Díaz-Granados (1998) / Manual de Drenaje INVIAS
    if custom_params and all(k in custom_params for k in ("a", "b", "c", "d")):
        a = float(custom_params["a"])
        b = float(custom_params["b"])
        c = float(custom_params["c"])
        d = float(custom_params["d"])
        reg_label = "Personalizada"
    else:
        reg = IDF_REGIONS.get(region_name, IDF_REGIONS["Andina"])
        a, b, c, d = float(reg["a"]), float(reg["b"]), float(reg["c"]), float(reg["d"])
        reg_label = region_name if region_name in IDF_REGIONS else "Andina"

    for dur_min in IDF_DURATIONS_MIN:
        row = {"duration_min": dur_min}
        for tr in IDF_RETURN_PERIODS:
            intensity = a * (tr ** b) * (max(1.0, m_mean) ** d) / ((dur_min / 60.0) ** c)
            row[f"tr_{tr}"] = round(float(intensity), 2)
        table.append(row)

    meta = {
        "method": "invias",
        "method_label": f"INVIAS Regionalizado ({reg_label})",
        "region": reg_label,
        "formula": f"i = {a} · Tr^{b} · M^{d} / (t/60)^{c}",
        "a": a, "b": b, "c": c, "d": d,
    }
    return table, meta


def build_alternating_block_hyetograph(
    idf_table: list[dict[str, Any]],
    tr: int = 10,
    total_duration_min: int = 60,
    dt_min: int = 5,
) -> list[dict[str, Any]]:
    """
    Construye Hietograma de Tormenta de Diseño por el Método de Bloques Alternos
    (estándar HEC-HMS / EPA SWMM / RAS) a partir de la curva IDF para un Tr dado.
    """
    row_by_dur = {int(r["duration_min"]): float(r[f"tr_{tr}"]) for r in idf_table if f"tr_{tr}" in r}
    durs_avail = sorted(row_by_dur.keys())
    if not durs_avail:
        return []

    n_blocks = max(3, total_duration_min // dt_min)
    cum_depths: list[float] = []
    for k in range(1, n_blocks + 1):
        t_k = k * dt_min
        # Interpolación log-lineal entre duraciones disponibles
        if t_k in row_by_dur:
            i_k = row_by_dur[t_k]
        else:
            i_k = float(np.interp(t_k, durs_avail, [row_by_dur[d] for d in durs_avail]))
        cum_depths.append(i_k * (t_k / 60.0))

    inc_depths = [cum_depths[0]] + [max(0.0, cum_depths[i] - cum_depths[i - 1]) for i in range(1, len(cum_depths))]
    inc_sorted = sorted(inc_depths, reverse=True)

    ordered = [0.0] * n_blocks
    mid = n_blocks // 2
    ordered[mid] = inc_sorted[0]
    left, right = mid - 1, mid + 1
    for idx, val in enumerate(inc_sorted[1:], start=1):
        if idx % 2 == 1:
            if right < n_blocks:
                ordered[right] = val
                right += 1
            elif left >= 0:
                ordered[left] = val
                left -= 1
        else:
            if left >= 0:
                ordered[left] = val
                left -= 1
            elif right < n_blocks:
                ordered[right] = val
                right += 1

    hyetograph = []
    cum = 0.0
    for idx, d_mm in enumerate(ordered):
        cum += d_mm
        hyetograph.append({
            "step": idx + 1,
            "time_min": f"{idx * dt_min}–{(idx + 1) * dt_min}",
            "time_end_min": (idx + 1) * dt_min,
            "depth_mm": round(d_mm, 2),
            "intensity_mmh": round(d_mm / (dt_min / 60.0), 2),
            "cum_depth_mm": round(cum, 2),
        })
    return hyetograph


def compute_idf_and_extremes(
    daily_df: pd.DataFrame,
    region_name: str = "Andina",
    idf_method: str = "invias",
    custom_params: dict[str, float] | None = None,
    min_year_completeness_pct: float = 70.0,
    hyetograph_tr: int = 10,
    hyetograph_duration_min: int = 60,
) -> dict[str, Any]:
    """
    Análisis hidrológico completo para diseños hidráulicos y drenaje (RAS 0330/2017 e INVIAS):
    - Máximos anuales de P24h
    - Ajuste comparativo Gumbel, Log-Normal, Log-Pearson III y GEV + Prueba K-S
    - Curvas IDF (INVIAS / Gustavo Silva / Sherman / Bell)
    - Hietograma de Bloques Alternos
    - Tabla normativa de períodos de retorno RAS Res. 0330/2017 e INVIAS
    - Índice SPI-3 y SPI-12
    """
    if 1 not in daily_df or daily_df[1].dropna().empty:
        return {"available": False, "message": "Sin datos diarios de precipitación para análisis hidrológico."}

    p = daily_df[1]
    annual_max_rows: list[dict[str, Any]] = []
    for yr, grp in p.groupby(p.index.year):
        valid = grp.dropna()
        total_days = len(grp)
        comp = 100.0 * len(valid) / max(1, total_days)
        if valid.empty:
            continue
        pmax = float(valid.max())
        dt_max = valid.idxmax().strftime("%Y-%m-%d")
        annual_max_rows.append({
            "year": int(yr),
            "pmax_24h_mm": round(pmax, 2),
            "annual_total_mm": round(float(valid.sum()), 1),
            "completeness_pct": round(comp, 1),
            "date_max": dt_max,
            "included": comp >= min_year_completeness_pct,
        })

    included_vals = np.array([r["pmax_24h_mm"] for r in annual_max_rows if r["included"]], dtype=np.float64)
    if included_vals.size < 2:
        included_vals = np.array([r["pmax_24h_mm"] for r in annual_max_rows], dtype=np.float64)

    if included_vals.size == 0:
        return {"available": False, "message": "No hay máximos anuales suficientes."}

    m_mean = float(np.mean(included_vals))
    s_std = float(np.std(included_vals, ddof=1)) if included_vals.size > 1 else 0.0

    fit_res = _fit_extreme_distributions(included_vals)
    best_dist_name = fit_res["best_distribution"]
    best_quantiles = {q["tr"]: q["p24h_mm"] for q in fit_res["distributions"][best_dist_name]["quantiles"]}

    silva_ratio = float((custom_params or {}).get("silva_ratio_1h_24h", 0.48))
    idf_matrix, idf_meta = _build_idf_table(
        idf_method=idf_method,
        m_mean=m_mean,
        region_name=region_name,
        dist_quantiles=best_quantiles,
        silva_ratio_1h_24h=silva_ratio,
        custom_params=custom_params,
    )

    hyetograph = build_alternating_block_hyetograph(
        idf_matrix, tr=hyetograph_tr, total_duration_min=hyetograph_duration_min, dt_min=5
    )

    # Evaluación rápida de intensidades normativas RAS & INVIAS (para tc=15 min y tc=30 min)
    row_15 = next((r for r in idf_matrix if r["duration_min"] == 15), idf_matrix[0])
    row_30 = next((r for r in idf_matrix if r["duration_min"] == 30), idf_matrix[0])
    normative_eval = []
    for item in NORMATIVE_RETURN_PERIODS:
        tr_rec = int(item["tr_rec"])
        tr_key = f"tr_{tr_rec}"
        normative_eval.append({
            **item,
            "i_tc15_mmh": row_15.get(tr_key),
            "i_tc30_mmh": row_30.get(tr_key),
        })

    spi_series = compute_spi_series(p, scales=(3, 12))

    return {
        "available": True,
        "years_count": int(included_vals.size),
        "m_pmax_24h_mean_mm": round(m_mean, 2),
        "pmax_24h_std_mm": round(s_std, 2),
        "pmax_24h_abs_max_mm": round(float(np.max(included_vals)), 2),
        "annual_max_series": annual_max_rows,
        "best_distribution": best_dist_name,
        "distributions": fit_res["distributions"],
        "empirical_points": fit_res.get("empirical_points", []),
        # Compatibilidad directa para gráficos existentes
        "gumbel_return_periods": fit_res["distributions"]["Gumbel"]["quantiles"],
        "lp3_return_periods": fit_res["distributions"]["Log-Pearson III"]["quantiles"],
        "idf_params": idf_meta,
        "idf_durations_min": IDF_DURATIONS_MIN,
        "idf_return_periods": IDF_RETURN_PERIODS,
        "idf_table": idf_matrix,
        "hyetograph_tr": hyetograph_tr,
        "hyetograph_duration_min": hyetograph_duration_min,
        "hyetograph": hyetograph,
        "normative_return_periods": normative_eval,
        "spi": spi_series,
    }


def compute_spi_series(daily_precip: pd.Series, scales: tuple[int, ...] = (3, 12)) -> dict[str, list[dict[str, Any]]]:
    """Calcula el Índice Estandarizado de Precipitación (SPI) por ajuste Gamma mensual."""
    monthly = daily_precip.resample("ME").agg(lambda s: s.sum() if s.notna().sum() >= 15 else np.nan)
    out: dict[str, list[dict[str, Any]]] = {}

    for k in scales:
        roll = monthly.rolling(window=k, min_periods=k).sum()
        spi_vals = pd.Series(np.nan, index=roll.index)

        for month_num in range(1, 13):
            mask = roll.index.month == month_num
            vals = roll[mask].dropna()
            if len(vals) < 4:
                continue
            q_zero = float((vals <= 0).mean())
            pos = vals[vals > 0]
            if len(pos) < 3 or pos.std() <= 1e-6:
                continue
            try:
                shape, _loc, scale_p = stats.gamma.fit(pos.to_numpy(), floc=0.0)
                cdf_pos = stats.gamma.cdf(vals.to_numpy(), shape, loc=0.0, scale=scale_p)
                h_prob = np.clip(q_zero + (1.0 - q_zero) * cdf_pos, 1e-4, 1.0 - 1e-4)
                z_vals = stats.norm.ppf(h_prob)
                spi_vals.loc[vals.index] = np.clip(z_vals, -3.5, 3.5)
            except Exception:
                continue

        items = []
        for dt, val in spi_vals.dropna().items():
            items.append({"date": dt.strftime("%Y-%m"), "value": round(float(val), 2)})
        out[f"spi_{k}"] = items
    return out
