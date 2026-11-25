"""Gráficas científicas de publicación técnica de alta resolución (240 DPI)."""

from __future__ import annotations

import io
import os
from typing import Any

from hidroclima.config import DATA_DIR

if "MPLCONFIGDIR" not in os.environ:
    _mpl_cache = DATA_DIR.parent / ".cache" / "matplotlib"
    try:
        _mpl_cache.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(_mpl_cache)
    except OSError:
        pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
import numpy as np


def _apply_style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 8.8,
        "axes.titlesize": 10.2,
        "axes.titleweight": "bold",
        "axes.labelsize": 9.0,
        "axes.labelweight": "bold",
        "axes.edgecolor": "#1e293b",
        "axes.linewidth": 1.0,
        "grid.color": "#94a3b8",
        "grid.linestyle": (0, (3, 3)),
        "grid.linewidth": 0.55,
        "legend.edgecolor": "#475569",
        "legend.facecolor": "#ffffff",
        "legend.framealpha": 0.94,
        "figure.facecolor": "#ffffff",
        "axes.facecolor": "#ffffff",
    })


def _style_origin_axes(ax: plt.Axes, *, dual_left: bool = False, dual_right: bool = False, x_numeric: bool = False, y_log: bool = False) -> None:
    """Aplica marco completo de cuatro ejes con divisiones internas mayores y menores."""
    for side in ("top", "bottom", "left", "right"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_color("#1e293b")
        ax.spines[side].set_linewidth(1.0)

    if dual_right:
        ax.tick_params(axis="y", which="major", direction="in", length=5.0, width=0.9, right=True, left=False, labelsize=8.3)
        if not y_log:
            ax.yaxis.set_minor_locator(AutoMinorLocator(2))
            ax.tick_params(axis="y", which="minor", direction="in", length=2.6, width=0.7, right=True, left=False)
        return

    show_right = not dual_left
    ax.tick_params(axis="x", which="major", direction="in", length=5.0, width=0.9, top=True, bottom=True, labelsize=8.3, colors="#0f172a")
    ax.tick_params(axis="y", which="major", direction="in", length=5.0, width=0.9, left=True, right=show_right, labelsize=8.3, colors="#0f172a")

    if x_numeric:
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        ax.tick_params(axis="x", which="minor", direction="in", length=2.6, width=0.65, top=True, bottom=True)
    if not y_log:
        ax.yaxis.set_minor_locator(AutoMinorLocator(2))
        ax.tick_params(axis="y", which="minor", direction="in", length=2.6, width=0.65, left=True, right=show_right)

    ax.grid(True, which="major", alpha=0.35)


def _add_stat_box(ax: plt.Axes, text: str, x: float = 0.02, y: float = 0.96, ha: str = "left", va: str = "top") -> None:
    ax.text(
        x,
        y,
        text,
        transform=ax.transAxes,
        ha=ha,
        va=va,
        fontsize=7.6,
        color="#0f172a",
        bbox=dict(boxstyle="square,pad=0.35", facecolor="#f8fafc", edgecolor="#64748b", linewidth=0.75, alpha=0.94),
        zorder=8,
    )


def _fig_to_bytes(fig: plt.Figure, dpi: int = 240) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def render_climograph_png(analysis: dict[str, Any]) -> bytes:
    """Climograma científico mensual: Precipitación (barras con borde) y Temperaturas (ejes duales)."""
    _apply_style()
    rows = analysis.get("monthly_summary", [])
    summ = analysis.get("summary", {})
    pav = analysis.get("pavement", {})

    months = [r["month_abbr"] for r in rows]
    precip = [r["precip_mm"] for r in rows]
    tmean = [r["temp_mean_c"] for r in rows]
    tmax = [r["temp_max_c"] for r in rows]
    tmin = [r["temp_min_c"] for r in rows]

    fig, ax1 = plt.subplots(figsize=(7.8, 3.9))
    x = np.arange(len(months))
    ax1.bar(
        x, precip, width=0.56, color="#0072B2", edgecolor="#0f172a", linewidth=0.65, alpha=0.86, label="Precipitación [mm]", zorder=2
    )
    ax1.set_ylabel("Precipitación [mm/mes]", color="#005587")
    ax1.set_xticks(x)
    ax1.set_xticklabels(months)
    ax1.set_ylim(0, max(precip or [100]) * 1.28)
    _style_origin_axes(ax1, dual_left=True)

    ax2 = ax1.twinx()
    valid_temps = [v for v in (tmean + [v for v in tmax if v is not None] + [v for v in tmin if v is not None]) if v is not None]
    if valid_temps:
        t_lo = min(valid_temps)
        t_hi = max(valid_temps)
        pad = max(2.0, (t_hi - t_lo) * 0.25)
        ax2.set_ylim(t_lo - pad * 0.8, t_hi + pad * 1.15)
    if any(v is not None for v in tmax):
        ax2.plot(
            x, [v if v is not None else np.nan for v in tmax],
            color="#D55E00", linestyle="--", marker="^", markersize=4.5, markeredgecolor="#ffffff", markeredgewidth=0.5, linewidth=1.3, label="T. Máxima [°C]", zorder=4
        )
    ax2.plot(
        x, tmean,
        color="#1e293b", marker="o", markersize=5.2, markerfacecolor="#E69F00", markeredgecolor="#1e293b", markeredgewidth=0.8, linewidth=2.0, label="T. Media [°C]", zorder=5
    )
    if any(v is not None for v in tmin):
        ax2.plot(
            x, [v if v is not None else np.nan for v in tmin],
            color="#009E73", linestyle="-.", marker="v", markersize=4.5, markeredgecolor="#ffffff", markeredgewidth=0.5, linewidth=1.3, label="T. Mínima [°C]", zorder=4
        )
    ax2.set_ylabel("Temperatura del Aire [°C]", color="#9a3412")
    _style_origin_axes(ax2, dual_right=True)

    pma = pav.get("pma_mm", summ.get("annual_precip_mm"))
    tmap = pav.get("tmap_c")
    stat_txt = f"PMA = {pma:,.1f} mm/año  |  Tmed = {summ.get('mean_annual_temp_c', '-')} °C"
    if tmap is not None:
        stat_txt += f"  |  TMAP = {tmap} °C"
    _add_stat_box(ax1, stat_txt, x=0.02, y=0.96, ha="left", va="top")

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4, frameon=True, fontsize=7.8)
    ax1.set_title(f"Régimen Ombrotérmico Mensual Multianual — {analysis['project']['name']}", pad=8)
    return _fig_to_bytes(fig)


def render_water_balance_png(analysis: dict[str, Any]) -> bytes:
    """Balance hídrico mensual de dos paneles con estadísticas climatológicas integradas."""
    _apply_style()
    rows = analysis.get("monthly_summary", [])
    summ = analysis.get("summary", {})
    proj = analysis.get("project", {})

    months = [r["month_abbr"] for r in rows]
    p = [r["precip_mm"] for r in rows]
    etp = [r["etp_active_mm"] for r in rows]
    exc = [r["excess_mm"] for r in rows]
    defic = [-r["deficit_mm"] for r in rows]
    stor = [r["storage_mm"] for r in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.8, 5.2), sharex=True, gridspec_kw={"height_ratios": [1.35, 1.0], "hspace": 0.10})
    x = np.arange(len(months))
    w = 0.36
    ax1.bar(x - w / 2, p, width=w, color="#0072B2", edgecolor="#0f172a", linewidth=0.55, label="Precipitación [mm]")
    ax1.bar(x + w / 2, etp, width=w, color="#E69F00", edgecolor="#0f172a", linewidth=0.55, label="ETP [mm]")
    ax1.plot(x, stor, color="#009E73", marker="s", markersize=4.6, markeredgecolor="#0f172a", markeredgewidth=0.5, linewidth=1.9, label="Almacenamiento [mm]")
    ax1.set_ylabel("Lámina Hídrica [mm]")
    ax1.set_ylim(0, max(max(p or [100]), max(etp or [100]), max(stor or [100])) * 1.44)
    _style_origin_axes(ax1)
    ax1.legend(loc="upper right", frameon=True, fontsize=7.4, ncol=1)
    _add_stat_box(
        ax1,
        f"R_máx = {proj.get('soil_max_reserve_mm', 100):.0f} mm  |  Im = {summ.get('thornthwaite_index_pct', '-')}%\n"
        f"ETP = {summ.get('annual_etp_mm', 0):,.1f} mm  |  ETR = {summ.get('annual_etr_mm', 0):,.1f} mm",
        x=0.015, y=0.96,
    )
    ax1.set_title(f"Balance Hídrico Climatológico Mensual ({proj.get('etp_method_label', '')})", pad=8)

    ax2.bar(x, exc, width=0.50, color="#009E73", edgecolor="#0f172a", linewidth=0.55, alpha=0.88, label="Exceso Hídrico (+mm)")
    ax2.bar(x, defic, width=0.50, color="#D55E00", edgecolor="#0f172a", linewidth=0.55, alpha=0.88, label="Déficit Hídrico (-mm)")
    ax2.axhline(0, color="#0f172a", linewidth=0.95)
    ax2.set_ylabel("Exceso / Déficit [mm]")
    ax2.set_xlabel("Mes del Año")
    ax2.set_xticks(x)
    ax2.set_xticklabels(months)
    y_max = max(max(exc or [10]), max([abs(d) for d in defic] or [10]))
    ax2.set_ylim(min(defic or [0]) * 1.25 - 6, y_max * 1.38 + 8)
    _style_origin_axes(ax2)
    ax2.legend(loc="upper left", frameon=True, fontsize=7.4, ncol=2)
    return _fig_to_bytes(fig)


def render_annual_trends_png(analysis: dict[str, Any]) -> bytes:
    """Series anuales históricas de precipitación y temperatura con ecuaciones de tendencia y Mann-Kendall/Pettitt."""
    _apply_style()
    rows = [r for r in analysis.get("annual_summary", []) if r.get("precip_mm") is not None]
    qual = analysis.get("quality", {})
    tp = qual.get("trends", {}).get("precip_annual", {})
    tt = qual.get("trends", {}).get("temp_mean_annual", {})
    hp = qual.get("homogeneity", {}).get("precip_annual", {})
    ht = qual.get("homogeneity", {}).get("temp_mean_annual", {})

    if not rows:
        fig, ax = plt.subplots(figsize=(7.8, 3.0))
        ax.text(0.5, 0.5, "Sin datos anuales suficientes", ha="center", va="center")
        _style_origin_axes(ax)
        return _fig_to_bytes(fig)

    years = np.array([r["year"] for r in rows], dtype=float)
    prec = np.array([r["precip_mm"] for r in rows], dtype=float)
    temps = np.array([r["temp_mean_c"] if r.get("temp_mean_c") is not None else np.nan for r in rows], dtype=float)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.8, 5.0), sharex=True, gridspec_kw={"hspace": 0.12})
    ax1.bar(years, prec, color="#0072B2", edgecolor="#0f172a", linewidth=0.55, alpha=0.80, width=0.66, label="Precipitación anual [mm]")
    p_eq = ""
    if len(years) >= 3:
        z = np.polyfit(years, prec, 1)
        ax1.plot(years, np.polyval(z, years), color="#0f172a", linestyle="--", linewidth=1.6, label=f"Regresión lineal ({z[0]:+.1f} mm/año)")
        p_eq = f"Tendencia: {z[0]:+.1f} mm/año"
    if tp.get("available"):
        p_eq += f"\nMK Z={tp['z_stat']}, p={tp['p_value']} | Sen={tp['sen_slope_per_decade']} mm/déc"
    if hp.get("available"):
        p_eq += f"\nPettitt: {'Homogénea' if hp['homogeneous'] else 'Cambio ' + str(hp['change_year'])} (p={hp['p_value']})"
    ax1.set_ylim(0, (float(np.max(prec)) if prec.size else 100.0) * 1.32)
    ax1.set_ylabel("Precipitación [mm/año]")
    _style_origin_axes(ax1, x_numeric=True)
    ax1.legend(loc="upper right", fontsize=7.6)
    if p_eq:
        _add_stat_box(ax1, p_eq.strip(), x=0.015, y=0.96)
    ax1.set_title("Variabilidad Interanual, Homogeneidad y Tendencias Climáticas", pad=8)

    valid_t = ~np.isnan(temps)
    t_eq = ""
    if valid_t.any():
        ax2.plot(
            years[valid_t], temps[valid_t],
            color="#D55E00", marker="o", markersize=4.2, markeredgecolor="#0f172a", markeredgewidth=0.5, linewidth=1.7, label="Temp. media anual [°C]"
        )
        if valid_t.sum() >= 3:
            zt = np.polyfit(years[valid_t], temps[valid_t], 1)
            ax2.plot(years[valid_t], np.polyval(zt, years[valid_t]), color="#7f1d1d", linestyle="--", linewidth=1.5, label=f"Regresión lineal ({zt[0]:+.3f} °C/año)")
            t_eq = f"Pendiente: {zt[0]:+.3f} °C/año"
        t_lo, t_hi = float(np.min(temps[valid_t])), float(np.max(temps[valid_t]))
        span = max(1.0, t_hi - t_lo)
        ax2.set_ylim(t_lo - span * 0.25, t_hi + span * 0.55)
    if tt.get("available"):
        t_eq += f"\nMK Z={tt['z_stat']}, p={tt['p_value']} | Sen={tt['sen_slope_per_decade']} °C/déc"
    if ht.get("available"):
        t_eq += f"\nPettitt: {'Homogénea' if ht['homogeneous'] else 'Cambio ' + str(ht['change_year'])} (p={ht['p_value']})"
    ax2.set_ylabel("Temperatura Media [°C]")
    ax2.set_xlabel("Año Hidrometeorológico")
    _style_origin_axes(ax2, x_numeric=True)
    ax2.legend(loc="upper right", fontsize=7.6)
    if t_eq:
        _add_stat_box(ax2, t_eq.strip(), x=0.015, y=0.96)
    return _fig_to_bytes(fig)


def render_idf_curves_png(analysis: dict[str, Any]) -> bytes:
    """Curvas IDF y análisis de frecuencia P24h con puntos empíricos de Gringorten y K-S."""
    _apply_style()
    idf = analysis.get("hydrology_idf", {})
    if not idf.get("available"):
        fig, ax = plt.subplots(figsize=(7.8, 3.0))
        ax.text(0.5, 0.5, "Sin datos de precipitación máxima 24h para curvas IDF", ha="center", va="center")
        _style_origin_axes(ax)
        return _fig_to_bytes(fig)

    table = idf["idf_table"]
    durations = [r["duration_min"] for r in table]
    trs_show = [2, 5, 10, 25, 50, 100]
    colors = ["#0072B2", "#009E73", "#E69F00", "#D55E00", "#dc2626", "#7e22ce"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.6, 4.0), gridspec_kw={"wspace": 0.26})
    for tr, col in zip(trs_show, colors):
        key = f"tr_{tr}"
        vals = [r[key] for r in table]
        ax1.plot(durations, vals, marker="o", markersize=2.8, linewidth=1.7, color=col, label=f"Tr = {tr} a")
    ax1.set_title(f"Curvas IDF — {idf['idf_params']['method_label']}", pad=7)
    ax1.set_xlabel("Duración t [min]")
    ax1.set_ylabel("Intensidad I [mm/h]")
    ax1.set_xlim(0, max(durations) + 5)
    ax1.set_ylim(0, max([r["tr_100"] for r in table] or [100]) * 1.15)
    _style_origin_axes(ax1, x_numeric=True)
    ax1.legend(fontsize=7.2, loc="upper right", ncol=2)
    _add_stat_box(ax1, f"{idf['idf_params']['formula']}\nM(P24h) = {idf['m_pmax_24h_mean_mm']:.1f} mm", x=0.97, y=0.58, ha="right", va="center")

    g_trs = [r["tr"] for r in idf["gumbel_return_periods"]]
    dists = idf.get("distributions", {})
    best = idf.get("best_distribution", "Gumbel")
    dist_styles = [
        ("Gumbel", "#0072B2", "-", "o"),
        ("Log-Normal", "#009E73", "-.", "^"),
        ("Log-Pearson III", "#D55E00", "--", "s"),
        ("GEV", "#7e22ce", ":", "D"),
    ]
    all_y_vals = []
    for d_name, d_col, d_ls, d_mk in dist_styles:
        q_list = dists.get(d_name, {}).get("quantiles")
        if q_list:
            ys = [r["p24h_mm"] for r in q_list]
            all_y_vals.extend(ys)
            lw = 2.2 if d_name == best else 1.4
            lbl = f"{d_name} ★" if d_name == best else d_name
            ax2.plot(g_trs, ys, marker=d_mk, markersize=3.8, linestyle=d_ls, linewidth=lw, color=d_col, label=lbl, zorder=4)

    emp_pts = idf.get("empirical_points", [])
    if emp_pts:
        emp_x = [p["tr"] for p in emp_pts]
        emp_y = [p["p24h_mm"] for p in emp_pts]
        all_y_vals.extend(emp_y)
        ax2.scatter(emp_x, emp_y, s=24, facecolors="#ffffff", edgecolors="#0f172a", linewidths=1.0, zorder=6, label="Observada (Gringorten)")

    ax2.set_xscale("log")
    ax2.set_title(f"Frecuencia P24h (Mejor K-S: {best})", pad=7)
    ax2.set_xlabel("Período de Retorno Tr [años]")
    ax2.set_ylabel("Precipitación Máx 24h [mm]")
    if all_y_vals:
        ax2.set_ylim(min(all_y_vals) * 0.85, max(all_y_vals) * 1.18)
    _style_origin_axes(ax2)
    ax2.grid(True, which="both", alpha=0.32)
    ax2.legend(fontsize=7.0, loc="upper left")
    best_obj = dists.get(best, {})
    _add_stat_box(
        ax2,
        f"{best}:\nK-S D = {best_obj.get('ks_d', '-')}\np-val = {best_obj.get('ks_pvalue', '-')}\nR² = {best_obj.get('r2', '-')}",
        x=0.97, y=0.05, ha="right", va="bottom",
    )
    return _fig_to_bytes(fig)


def render_hyetograph_png(analysis: dict[str, Any]) -> bytes:
    """Hietograma de tormenta de diseño (Método de Bloques Alternos) con curva acumulada."""
    _apply_style()
    idf = analysis.get("hydrology_idf", {})
    hyet = idf.get("hyetograph", [])
    if not hyet:
        fig, ax = plt.subplots(figsize=(7.8, 3.0))
        ax.text(0.5, 0.5, "Sin datos de hietograma", ha="center", va="center")
        _style_origin_axes(ax)
        return _fig_to_bytes(fig)

    labels = [r["time_min"] for r in hyet]
    depths = [r["depth_mm"] for r in hyet]
    cums = [r["cum_depth_mm"] for r in hyet]
    max_int = max(r["intensity_mmh"] for r in hyet)

    fig, ax1 = plt.subplots(figsize=(7.8, 3.6))
    x = np.arange(len(labels))
    ax1.bar(x, depths, width=0.70, color="#0072B2", edgecolor="#0f172a", linewidth=0.65, alpha=0.88, label="Lámina incremental [mm]")
    ax1.set_ylabel("Lámina por Bloque [mm]", color="#005587")
    ax1.set_xlabel("Intervalo de Tiempo [min]")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=32, ha="right", fontsize=7.6)
    ax1.set_ylim(0, max(depths or [10]) * 1.28)
    _style_origin_axes(ax1, dual_left=True)

    ax2 = ax1.twinx()
    ax2.plot(x, cums, color="#D55E00", marker="o", markersize=4.0, markeredgecolor="#0f172a", markeredgewidth=0.5, linewidth=1.9, label="Lámina acumulada [mm]")
    ax2.set_ylabel("Lámina Acumulada [mm]", color="#9a3412")
    ax2.set_ylim(0, max(cums or [10]) * 1.18)
    _style_origin_axes(ax2, dual_right=True)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=7.6)
    _add_stat_box(
        ax1,
        f"P_total = {cums[-1]:.1f} mm\nI_pico = {max_int:.1f} mm/h\nTr = {idf.get('hyetograph_tr', 10)} años | Δt = 5 min",
        x=0.985, y=0.22, ha="right", va="bottom",
    )
    ax1.set_title(
        f"Hietograma de Tormenta de Diseño — Bloques Alternos (Tr = {idf.get('hyetograph_tr', 10)} años, Dur = {idf.get('hyetograph_duration_min', 60)} min)",
        pad=8,
    )
    return _fig_to_bytes(fig)


def render_sgc_thresholds_png(analysis: dict[str, Any]) -> bytes:
    """Umbrales empíricos SGC (R15_ant vs R3) y días críticos anuales por movimientos en masa."""
    _apply_style()
    sgc = analysis.get("geohazards_sgc", {})
    if not sgc.get("available"):
        fig, ax = plt.subplots(figsize=(8.0, 3.2))
        ax.text(0.5, 0.5, "Sin datos diarios suficientes para umbral geotécnico SGC", ha="center", va="center")
        _style_origin_axes(ax)
        return _fig_to_bytes(fig)

    pts = sgc.get("scatter_points", [])
    ann = sgc.get("annual_exceedances", [])
    a = float(sgc.get("r3_intercept", 70.0))
    b = float(sgc.get("r15_slope", 0.47))

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(8.2, 3.8), gridspec_kw={"width_ratios": [1.35, 1.0]}, constrained_layout=True
    )

    norm_pts = [p for p in pts if not p["exceeds"]]
    exc_pts = [p for p in pts if p["exceeds"]]
    if norm_pts:
        ax1.scatter(
            [p["r15_ant"] for p in norm_pts],
            [p["r3"] for p in norm_pts],
            s=14,
            color="#60a5fa",
            alpha=0.55,
            edgecolors="none",
            label="Días húmedos bajo umbral",
            zorder=2,
        )
    if exc_pts:
        ax1.scatter(
            [p["r15_ant"] for p in exc_pts],
            [p["r3"] for p in exc_pts],
            s=36,
            marker="*",
            color="#dc2626",
            edgecolors="#450a0a",
            linewidths=0.45,
            label=f"Excedencia SGC ({sgc.get('exceedance_days', 0)} d)",
            zorder=4,
        )

    max_x = max([p["r15_ant"] for p in pts], default=180.0) * 1.06
    x_line = np.linspace(0.0, max(120.0, max_x), 200)
    y_line = np.maximum(5.0, a - b * x_line)
    ax1.plot(x_line, y_line, color="#991b1b", linestyle="--", linewidth=1.8, label=f"Umbral: máx(5, {a:.0f}−{b:.2f}·R15)", zorder=5)
    ax1.set_title("Envolvente Empírica SGC (R15_ant vs R3)", pad=7)
    ax1.set_xlabel("Lluvia Antecedente 15 días [mm]")
    ax1.set_ylabel("Lluvia Acumulada 3 días R3 [mm]")
    _style_origin_axes(ax1, x_numeric=True)
    max_r3 = max([p["r3"] for p in pts], default=100.0)
    ax1.set_ylim(0, max(max_r3 * 1.18, a * 1.28))
    ax1.legend(fontsize=7.0, loc="upper right")
    _add_stat_box(
        ax1,
        f"Episodios críticos: {sgc.get('episodes_count', 0)}\nTasa excedencia: {sgc.get('exceedance_rate_pct', 0):.2f} %\nCN II = {sgc.get('infiltration_balance', {}).get('cn_ii', 75)}",
        x=0.022, y=0.965, ha="left", va="top",
    )

    if ann:
        yrs = [r["year"] for r in ann]
        excs = [r["exceedance_days"] for r in ann]
        ax2.bar(yrs, excs, width=0.68, color="#D55E00", edgecolor="#0f172a", linewidth=0.55, alpha=0.88)
        ax2.set_title("Días Críticos Anuales (R3 ≥ Umbral)", pad=7)
        ax2.set_xlabel("Año")
        ax2.set_ylabel("Días sobre umbral [d/año]")
        _style_origin_axes(ax2, x_numeric=True)
    else:
        ax2.text(0.5, 0.5, "Sin serie anual de excedencias", ha="center", va="center")
        _style_origin_axes(ax2)

    return _fig_to_bytes(fig)


def render_spei_drought_png(analysis: dict[str, Any]) -> bytes:
    """Índice de sequías SPEI-3 / SPEI-12 (UNGRD) y distribución mensual RUSLE (ANLA)."""
    _apply_style()
    drought = analysis.get("drought", {})
    ero = analysis.get("erosivity", {})

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.2, 5.2), constrained_layout=True)

    s3 = drought.get("spei_3", [])
    s12 = drought.get("spei_12", [])
    if s3:
        dates = [r["date"] for r in s3]
        vals = np.array([r["value"] for r in s3], dtype=float)
        x = np.arange(len(dates))
        colors = ["#009E73" if v >= 0 else "#D55E00" for v in vals]
        ax1.bar(x, vals, width=0.85, color=colors, alpha=0.82, label="SPEI-3 (estacional)")
        if s12:
            s12_map = {r["date"]: r["value"] for r in s12}
            y12 = [s12_map.get(d, np.nan) for d in dates]
            ax1.plot(x, y12, color="#0f172a", linewidth=1.45, label="SPEI-12 (interanual)")
        ax1.axhline(0.0, color="#334155", linewidth=0.8)
        ax1.axhline(-1.0, color="#d97706", linestyle="--", linewidth=0.9, label="Sequía mod. (-1.0)")
        ax1.axhline(-1.5, color="#dc2626", linestyle=":", linewidth=1.0, label="Sequía sev. (-1.5)")
        step = max(1, len(dates) // 9)
        ax1.set_xticks(x[::step])
        ax1.set_xticklabels(dates[::step], fontsize=7.6)
        ax1.set_ylim(-3.2, 3.2)
        ax1.set_ylabel("Índice SPEI [Z]")
        ax1.set_title("Monitoreo de Sequías e Hiper-humedad — SPEI-3 y SPEI-12 (D = P - ET0)", pad=6)
        _style_origin_axes(ax1)
        ax1.legend(fontsize=6.9, loc="upper right", ncol=2)
        ds = drought.get("summary", {})
        if ds:
            _add_stat_box(
                ax1,
                f"Meses ≤ -1.0: {ds.get('drought_moderate_pct', 0)}%\nMín SPEI-3: {ds.get('min_spei3', '-')} ({ds.get('min_spei3_date', '-')})",
                x=0.015, y=0.06, ha="left", va="bottom",
            )
    else:
        ax1.text(0.5, 0.5, "Sin serie mensual continua suficiente para SPEI", ha="center", va="center")
        _style_origin_axes(ax1)

    m_ero = ero.get("monthly_distribution", [])
    if ero.get("available") and m_ero:
        xm = np.arange(len(m_ero))
        months = [r["month"] for r in m_ero]
        shares = [r["r_share_pct"] for r in m_ero]
        p_m = [r["precip_mm"] for r in m_ero]
        ax2.bar(xm, shares, width=0.58, color="#d97706", edgecolor="#0f172a", linewidth=0.6, alpha=0.86, label="Aporte mensual Factor R [%]")
        ax2.set_xticks(xm)
        ax2.set_xticklabels(months)
        ax2.set_ylabel("Participación Erosividad [%]", color="#b45309")
        ax2.set_ylim(0, max(shares or [20]) * 1.44)
        _style_origin_axes(ax2, dual_left=True)

        ax2b = ax2.twinx()
        ax2b.plot(xm, p_m, color="#0072B2", marker="o", markersize=4.2, linewidth=1.7, label="Precipitación media [mm]")
        ax2b.set_ylabel("Precipitación Media [mm]", color="#005587")
        ax2b.set_ylim(0, max(p_m or [100]) * 1.42)
        _style_origin_axes(ax2b, dual_right=True)

        h1, l1 = ax2.get_legend_handles_labels()
        h2, l2 = ax2b.get_legend_handles_labels()
        ax2.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=7.2)
        ax2.set_title("Distribución Intraanual de Erosividad Pluvial RUSLE (MFI Arnoldus / Renard & Freimund)", pad=6)
        _add_stat_box(
            ax2,
            f"MFI = {ero.get('mfi_arnoldus_mm')} mm ({ero.get('aggressiveness_class')})  |  PCI = {ero.get('pci_oliver_pct')}%\nFactor R = {ero.get('r_factor_mfi')} MJ·mm/(ha·h·a)",
            x=0.985, y=0.96, ha="right", va="top",
        )
    else:
        ax2.text(0.5, 0.5, "Sin datos de erosividad RUSLE", ha="center", va="center")
        _style_origin_axes(ax2)

    return _fig_to_bytes(fig)
