"""Pruebas unitarias para Geotecnia SGC, Erosividad RUSLE, Sequías SPEI/IAP y Cuenca INVIAS/SCS."""

from __future__ import annotations

import numpy as np
import pandas as pd

from hidroclima.analysis.geohazards_env import (
    compute_erosivity_rusle,
    compute_sgc_landslide_thresholds,
    compute_spei_and_anomalies,
    compute_watershed_runoff_scs,
)
from hidroclima.config import MONTH_ABBR_ES


def test_sgc_landslide_thresholds_and_infiltration():
    idx = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    rng = np.random.default_rng(7)
    p = rng.uniform(0.0, 8.0, size=len(idx))
    # Inyectar evento detonante realista tras 15 días húmedos (~120 mm -> umbral = 70 - 0.47*120 = 13.6 mm)
    p[180:195] = 8.0
    p[195:198] = 32.0
    daily_df = pd.DataFrame({1: p}, index=idx)

    res = compute_sgc_landslide_thresholds(daily_df, soil_cn=75.0, r3_intercept=70.0, r15_slope=0.47)
    assert res["available"] is True
    assert res["exceedance_days"] >= 1
    assert res["episodes_count"] >= 1
    assert res["episodes"][0]["severity_ratio"] >= 1.0
    assert res["rolling_stats"]["R3 (3 días)"]["max"] >= 96.0
    inf = res["infiltration_balance"]
    assert inf["cn_i"] < inf["cn_ii"] < inf["cn_iii"]
    assert inf["mean_annual_infiltration_mm"] > 0
    assert inf["mean_annual_runoff_mm"] >= 0


def test_erosivity_rusle_mfi_pci_and_r_factor():
    # Régimen bimodal andino de ejemplo (~1800 mm/año)
    p_m = [80.0, 95.0, 160.0, 230.0, 210.0, 90.0, 70.0, 75.0, 140.0, 240.0, 230.0, 180.0]
    monthly_rows = [{"month_abbr": MONTH_ABBR_ES[i], "precip_mm": p_m[i]} for i in range(12)]
    res = compute_erosivity_rusle(monthly_rows)
    assert res["available"] is True
    p_ann = sum(p_m)
    expected_mfi = sum(x ** 2 for x in p_m) / p_ann
    expected_pci = 100.0 * sum(x ** 2 for x in p_m) / (p_ann ** 2)
    assert abs(res["mfi_arnoldus_mm"] - expected_mfi) < 0.05
    assert abs(res["pci_oliver_pct"] - expected_pci) < 0.05
    expected_r = 95.77 - 6.081 * expected_mfi + 0.4770 * (expected_mfi ** 2)
    assert abs(res["r_factor_mfi"] - expected_r) < 0.5
    assert abs(sum(r["r_share_pct"] for r in res["monthly_distribution"]) - 100.0) < 0.3


def test_spei_and_iap_anomalies():
    idx = pd.date_range("2015-01-01", "2024-12-31", freq="D")
    rng = np.random.default_rng(19)
    p = rng.gamma(shape=1.4, scale=4.0, size=len(idx))
    # Sequía severa en 2023
    p[(idx.year == 2023)] *= 0.25
    daily_df = pd.DataFrame({1: p}, index=idx)
    et0 = pd.Series(np.full(len(idx), 3.2), index=idx)
    ann_rows = [
        {"year": yr, "precip_mm": float(daily_df[daily_df.index.year == yr][1].sum()), "completeness_precip_pct": 100.0}
        for yr in range(2015, 2025)
    ]

    res = compute_spei_and_anomalies(daily_df, et0, ann_rows)
    assert res["available"] is True
    assert len(res["spei_3"]) >= 90
    assert len(res["spei_12"]) >= 80
    assert len(res["iap_annual"]) == 10
    yr_2023 = next(r for r in res["iap_annual"] if r["year"] == 2023)
    assert yr_2023["anomaly_pct"] < -25.0
    assert res["summary"]["min_spei3"] < -1.0


def test_watershed_runoff_invias_scs():
    idf_stub = {
        "available": True,
        "idf_table": [
            {"duration_min": 5, "tr_2": 110.0, "tr_5": 140.0, "tr_10": 165.0, "tr_20": 190.0, "tr_25": 200.0, "tr_50": 230.0, "tr_100": 260.0},
            {"duration_min": 30, "tr_2": 60.0, "tr_5": 78.0, "tr_10": 92.0, "tr_20": 106.0, "tr_25": 112.0, "tr_50": 128.0, "tr_100": 145.0},
            {"duration_min": 60, "tr_2": 40.0, "tr_5": 52.0, "tr_10": 62.0, "tr_20": 71.0, "tr_25": 75.0, "tr_50": 86.0, "tr_100": 98.0},
            {"duration_min": 180, "tr_2": 18.0, "tr_5": 24.0, "tr_10": 28.0, "tr_20": 32.0, "tr_25": 34.0, "tr_50": 39.0, "tr_100": 45.0},
        ],
    }
    res = compute_watershed_runoff_scs(idf_stub, area_km2=2.0, length_m=1200.0, slope_pct=4.0, curve_number=80.0, runoff_coeff=0.60)
    assert res["available"] is True
    expected_tc = 0.01947 * (1200.0 ** 0.77) * (0.04 ** -0.385)
    assert abs(res["tc_kirpich_min"] - round(expected_tc, 2)) < 0.02
    row_100 = next(r for r in res["design_rows"] if r["tr"] == 100)
    expected_q = (0.60 * row_100["i_tc_mmh"] * 2.0) / 3.6
    assert abs(row_100["q_rational_m3s"] - round(expected_q, 3)) < 0.01
    # Conservación lámina SCS: Qe + F + min(P, Ia) == P_storm
    ia = res["ia_mm"]
    assert abs(row_100["qe_runoff_mm"] + row_100["infiltration_mm"] + min(row_100["p_storm_mm"], ia) - row_100["p_storm_mm"]) < 0.05
