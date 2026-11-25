"""Pruebas científicas de FAO-56 Penman-Monteith, Thornthwaite, Superpave PG, IDF y geoespacial."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from hidroclima.analysis.classifications import (
    classify_caldas_lang,
    classify_ena_aridity_index,
    classify_holdridge_life_zone,
    classify_koppen_geiger,
)
from hidroclima.analysis.hydrology_idf import compute_idf_and_extremes
from hidroclima.analysis.pavement import (
    classify_invias_pavement_region,
    compute_pavement_metrics,
    shell_weighting_factor,
    shell_wf_to_tmap,
)
from hidroclima.analysis.quality import compute_etccdi_indices, mann_kendall_sen, pettitt_homogeneity_test
from hidroclima.analysis.radiation_etp import compute_fao56_daily_et0, solar_geometry_series
from hidroclima.analysis.spatial import (
    compute_idw_weights,
    compute_thiessen_weights,
    haversine_km,
    parse_kml_or_geojson_bytes,
    point_to_polyline_km,
)
from hidroclima.analysis.thornthwaite import (
    calculate_monthly_thornthwaite_standalone,
    compute_cyclic_water_balance,
)


def test_water_balance_mass_conservation():
    # Ecuación fundamental: Sum(P) + dStorage(0 en ciclo) == Sum(ETR) + Sum(Exceso)
    # y Sum(ETP) == Sum(ETR) + Sum(Déficit)
    precip = [190.6, 193.8, 189.2, 245.9, 144.6, 51.9, 39.8, 27.7, 43.3, 302.4, 374.1, 314.7]
    temp = [13.86, 13.76, 13.95, 14.12, 14.34, 14.39, 14.30, 14.27, 14.51, 13.79, 13.35, 13.39]
    res = calculate_monthly_thornthwaite_standalone(precip, temp, lat_deg=2.45, soil_max_reserve_mm=100.0)
    assert pytest.approx(res["total_precip_mm"], abs=0.2) == res["total_etr_mm"] + res["total_excess_mm"]
    assert pytest.approx(res["total_etp_mm"], abs=0.2) == res["total_etr_mm"] + res["total_deficit_mm"]
    assert res["thornthwaite_index_pct"] > 100.0
    assert res["humidity_class"] == "A. Excesivamente Húmedo"
    assert res["thermal_class"] == "Templado"


def test_fao56_penman_monteith_typical_colombia():
    # Escenario Popayán típico: Tmax=24, Tmin=14, Tmean=18.5, HR=78%, Brillo=5.2 h, viento=1.5 m/s
    dates = pd.date_range("2024-01-01", "2024-01-10", freq="D")
    df = pd.DataFrame(
        {
            2: [5.2] * 10,
            4: [78.0] * 10,
            5: [18.5] * 10,
            6: [24.0] * 10,
            7: [14.0] * 10,
            9: [1.5] * 10,
        },
        index=dates,
    )
    rad = compute_fao56_daily_et0(df, lat_deg=2.45, altitude_m=1752.0)
    et0 = rad["et0_mm"].mean()
    ra = rad["ra_mj"].mean()
    assert 30.0 <= ra <= 42.0
    assert 2.5 <= et0 <= 5.0


def test_solar_geometry_equator_daylight():
    ra, n_h = solar_geometry_series(lat_deg=0.0, doy=np.array([80, 172, 265, 355]))
    assert np.allclose(n_h, 12.0, atol=0.15)
    assert np.all((ra > 30.0) & (ra < 40.0))


def test_pavement_superpave_7day():
    dates = pd.date_range("2023-01-01", "2024-12-31", freq="D")
    rng = np.random.default_rng(42)
    tmax = 26.0 + rng.normal(0, 1.5, len(dates))
    # Olas de calor de 7 días en agosto
    tmax[210:217] = 35.0
    tmax[575:582] = 36.0
    df = pd.DataFrame(
        {
            1: np.where(rng.random(len(dates)) > 0.5, 5.0, 0.0),
            5: tmax - 5.0,
            6: tmax,
            7: tmax - 10.0,
        },
        index=dates,
    )
    pav = compute_pavement_metrics(df, lat_deg=4.5, thornthwaite_tmi=35.0, water_table_m=8.0)
    assert pav["max_7day_tmax_c"] >= 34.5
    assert pav["recommended_pg_grade"].startswith("PG ")
    assert 40.0 <= pav["dry_days_pct"] <= 60.0


def test_idf_and_gumbel():
    dates = pd.date_range("2010-01-01", "2024-12-31", freq="D")
    rng = np.random.default_rng(7)
    precip = rng.exponential(scale=8.0, size=len(dates))
    # Inyectar eventos máximos anuales realistas (~75-110 mm)
    for yr_idx in range(15):
        precip[yr_idx * 365 + 100] = 75.0 + yr_idx * 2.0
    df = pd.DataFrame({1: precip}, index=dates)
    idf = compute_idf_and_extremes(df, region_name="Andina")
    assert idf["available"] is True
    assert idf["years_count"] >= 14
    # Intensidad debe decrecer con duración y crecer con Tr
    t5 = idf["idf_table"][0]
    t60 = [r for r in idf["idf_table"] if r["duration_min"] == 60][0]
    assert t5["tr_100"] > t5["tr_10"] > t5["tr_2"]
    assert t5["tr_10"] > t60["tr_10"]


def test_mann_kendall_detects_increasing_trend():
    years = np.arange(2000, 2025)
    vals = 15.0 + 0.08 * (years - 2000)
    res = mann_kendall_sen(years, vals)
    assert res["available"] is True
    assert res["p_value"] < 0.001
    assert pytest.approx(res["sen_slope_per_year"], abs=0.001) == 0.08


def test_spatial_tools_and_kml():
    d = haversine_km(2.4448, -76.6147, 1.2136, -77.2811)  # Popayán - Pasto ~155 km
    assert 145.0 < d < 165.0

    kml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Placemark><LineString><coordinates>-76.61,2.44,0 -77.28,1.21,0</coordinates></LineString></Placemark>
    </kml>"""
    pts = parse_kml_or_geojson_bytes(kml, "ruta.kml")
    assert len(pts) == 2
    assert pytest.approx(pts[0][0], abs=0.01) == 2.44

    dist_mid = point_to_polyline_km(1.825, -76.945, pts)
    assert dist_mid < 5.0

    stations = [
        {"codigo": "A", "latitud": 2.44, "longitud": -76.61},
        {"codigo": "B", "latitud": 1.90, "longitud": -76.66},
    ]
    w_idw = compute_idw_weights(stations, polyline=pts)
    w_th = compute_thiessen_weights(stations, polyline=pts)
    assert pytest.approx(sum(w_idw.values()), abs=1e-4) == 1.0
    assert pytest.approx(sum(w_th.values()), abs=1e-4) == 1.0


def test_tmap_shell_invias_and_classifications():
    # Autocomprobación inversa de la Carta W de Shell en 12, 20 y 28 °C
    for t_ref in (12.0, 20.0, 28.0):
        wf = shell_weighting_factor(t_ref)
        t_back = shell_wf_to_tmap(wf)
        assert pytest.approx(t_back, abs=0.15) == t_ref

    assert classify_invias_pavement_region(11.5, 950.0)["code"] == "R1"
    assert classify_invias_pavement_region(18.0, 1400.0)["code"] == "R2"
    assert classify_invias_pavement_region(26.5, 1100.0)["code"] == "R3"
    assert classify_invias_pavement_region(17.5, 2500.0)["code"] == "R4"
    assert classify_invias_pavement_region(25.0, 2800.0)["code"] == "R5"
    assert classify_invias_pavement_region(27.0, 5200.0)["code"] == "R6"

    # Clasificaciones ambientales (Bogotá / Popayán típico)
    cl = classify_caldas_lang(mean_temp_c=14.0, annual_precip_mm=1800.0, altitude_m=2550.0)
    assert cl["piso_termico"] == "Frío"
    assert cl["grado_humedad"] == "Húmedo"

    ho = classify_holdridge_life_zone([14.0] * 12, annual_precip_mm=780.0, altitude_m=2550.0)
    assert ho["piso_altitudinal"] == "Montano Bajo"
    assert "bh-MB" in ho["life_zone"]

    ho_pluvial = classify_holdridge_life_zone([14.0] * 12, annual_precip_mm=1800.0, altitude_m=2550.0)
    assert "bp-MB" in ho_pluvial["life_zone"]

    kg = classify_koppen_geiger([14.0] * 12, [150.0] * 12)
    assert kg["code"] == "Cfb"
    kg_desert = classify_koppen_geiger([28.5] * 12, [25.0] * 12)
    assert kg_desert["code"] == "BWh"

    ena = classify_ena_aridity_index(etp_mm=1000.0, etr_mm=920.0)
    assert ena["category"] == "Altos excedentes de agua"


def test_idf_methods_hyetograph_and_pettitt_etccdi():
    dates = pd.date_range("2010-01-01", "2024-12-31", freq="D")
    rng = np.random.default_rng(11)
    precip = rng.exponential(scale=7.0, size=len(dates))
    for yr_idx in range(15):
        precip[yr_idx * 365 + 100] = 72.0 + yr_idx * 1.5
    df = pd.DataFrame({1: precip, 6: np.full(len(dates), 28.0), 7: np.full(len(dates), 15.0)}, index=dates)

    for method in ("invias", "silva", "sherman", "bell"):
        res = compute_idf_and_extremes(df, region_name="Andina", idf_method=method, hyetograph_tr=10, hyetograph_duration_min=60)
        assert res["available"] is True
        assert res["best_distribution"] in ("Gumbel", "Log-Normal", "Log-Pearson III", "GEV")
        assert len(res["hyetograph"]) == 12
        # Bloque central (máximo) debe ubicarse en la mitad del hietograma de Bloques Alternos
        depths = [b["depth_mm"] for b in res["hyetograph"]]
        assert max(depths) == depths[len(depths) // 2]

    # Prueba de Pettitt sobre cambio abrupto sintético
    years = np.arange(2000, 2020)
    vals = np.concatenate([np.full(10, 1200.0), np.full(10, 1900.0)])
    pt = pettitt_homogeneity_test(years, vals)
    assert pt["available"] is True
    assert pt["homogeneous"] is False
    assert pt["change_year"] in (2009, 2010)

    et = compute_etccdi_indices(df)
    assert et["rx1day_mm"] >= 70.0
    assert et["rx5day_mm"] >= et["rx1day_mm"]
