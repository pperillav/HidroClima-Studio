"""Motor maestro de análisis multiproyecto para HidroClima Studio."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from hidroclima.analysis.classifications import compute_all_climate_classifications
from hidroclima.analysis.geohazards_env import (
    compute_erosivity_rusle,
    compute_sgc_landslide_thresholds,
    compute_spei_and_anomalies,
    compute_watershed_runoff_scs,
)
from hidroclima.analysis.hydrology_idf import compute_idf_and_extremes
from hidroclima.analysis.pavement import compute_pavement_metrics
from hidroclima.analysis.quality import compute_quality_report
from hidroclima.analysis.radiation_etp import compute_fao56_daily_et0
from hidroclima.analysis.spatial import detect_invias_region
from hidroclima.analysis.thornthwaite import (
    classify_temperature_climalike,
    compute_cyclic_water_balance,
    thornthwaite_monthly_etp,
)
from hidroclima.config import DAYS_IN_MONTH_NONLEAP, MONTH_ABBR_ES, MONTH_NAMES_ES, SOURCE_PRIORITY, VARIABLES
from hidroclima.db.database import ClimateDatabase


def _aggregate_weighted_daily_series(
    db: ClimateDatabase,
    station_weights: list[dict[str, Any]],
    start_year: int | None,
    end_year: int | None,
    allowed_sources: list[str] | None,
    fill_gaps: bool,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, int]]:
    """Combina las series diarias de las estaciones seleccionadas mediante promedio ponderado dinámico."""
    per_station_dfs: list[tuple[str, float, pd.DataFrame]] = []
    station_reports: list[dict[str, Any]] = []
    total_source_counts: dict[str, int] = {}

    all_vids = sorted(VARIABLES.keys())
    for item in station_weights:
        code = str(item["codigo"]).strip()
        w = max(0.0, float(item.get("weight", 1.0)))
        if w == 0.0:
            w = 1.0
        df_s, src_cnt = db.get_station_daily_dataframe(
            code,
            var_ids=all_vids,
            start_year=start_year,
            end_year=end_year,
            allowed_sources=allowed_sources,
            fill_gaps_with_secondary=fill_gaps,
        )
        for src, cnt in src_cnt.items():
            total_source_counts[src] = total_source_counts.get(src, 0) + cnt
        avail_vars = [int(v) for v in df_s.columns if df_s[v].notna().any()] if not df_s.empty else []
        station_reports.append({
            "codigo": code,
            "weight_raw": w,
            "has_data": not df_s.empty and len(avail_vars) > 0,
            "available_vars": avail_vars,
            "source_days": src_cnt,
            "years_range": [int(df_s.index.year.min()), int(df_s.index.year.max())] if not df_s.empty else None,
        })
        if not df_s.empty:
            per_station_dfs.append((code, w, df_s))

    total_w = sum(r["weight_raw"] for r in station_reports) or 1.0
    for r in station_reports:
        r["weight_norm"] = round(r["weight_raw"] / total_w, 4)

    if not per_station_dfs:
        return pd.DataFrame(), station_reports, total_source_counts

    min_dt = min(df.index.min() for _, _, df in per_station_dfs)
    max_dt = max(df.index.max() for _, _, df in per_station_dfs)
    full_idx = pd.date_range(min_dt, max_dt, freq="D", name="date")

    weighted_cols: dict[int, np.ndarray] = {}
    for vid in all_vids:
        num = np.zeros(len(full_idx), dtype=np.float64)
        den = np.zeros(len(full_idx), dtype=np.float64)
        for _, w, df_s in per_station_dfs:
            if vid not in df_s:
                continue
            aligned = df_s[vid].reindex(full_idx).to_numpy(dtype=np.float64)
            valid = ~np.isnan(aligned)
            num[valid] += aligned[valid] * w
            den[valid] += w
        col = np.divide(num, den, out=np.full(len(full_idx), np.nan, dtype=np.float64), where=den > 0.0)
        if np.any(~np.isnan(col)):
            weighted_cols[vid] = col

    merged_df = pd.DataFrame(weighted_cols, index=full_idx)

    # Si falta Tmedia (5) pero existen Tmax (6) y Tmin (7), derivar Tmedia = 0.5*(Tmax+Tmin) donde falte
    if 6 in merged_df and 7 in merged_df:
        tmax_v = merged_df[6]
        tmin_v = merged_df[7]
        calc_mean = 0.5 * (tmax_v + tmin_v)
        if 5 in merged_df:
            merged_df[5] = merged_df[5].fillna(calc_mean)
        else:
            merged_df[5] = calc_mean

    return merged_df, station_reports, total_source_counts


def run_project_analysis(
    db: ClimateDatabase,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Ejecuta análisis completo del proyecto climático:
    - Agregación multipunto ponderada
    - Promedios diarios (365/366), mensuales (12), diarios por año y mensuales por año
    - Radiación solar y FAO-56 Penman-Monteith / Thornthwaite 1948
    - Balance hídrico cíclico (Almacenamiento, Exceso, Déficit, ETR, TMI)
    - Ingeniería de pavimentos (7 días más calientes, Superpave PG, MEPDG)
    - Hidrología extrema (Gumbel, Log-Pearson III, Curvas IDF INVIAS, SPI)
    - Calidad de datos y tendencias Mann-Kendall
    """
    stations_cfg = config.get("stations", [])
    if not stations_cfg:
        raise ValueError("Debe seleccionar al menos una estación climática para analizar.")

    codes = [str(s["codigo"]).strip() for s in stations_cfg]
    meta_list = db.get_stations_by_codes(codes)
    meta_by_code = {m["codigo"]: m for m in meta_list}
    if not meta_by_code:
        raise ValueError("Ninguna de las estaciones seleccionadas existe en el catálogo.")

    end_year = int(config.get("end_year") or 2026)
    last_n_years = int(config.get("last_n_years") or 0)  # 0 = todos los años disponibles
    start_year = (end_year - last_n_years + 1) if last_n_years > 0 else None
    soil_reserve = float(config.get("soil_max_reserve_mm") or 100.0)
    water_table_m = float(config.get("water_table_m") or 10.0)
    etp_method = str(config.get("etp_method") or "penman_monteith")  # 'penman_monteith' | 'thornthwaite'
    allowed_sources = config.get("allowed_sources") or SOURCE_PRIORITY
    fill_gaps = bool(config.get("fill_gaps", True))

    merged_df, stn_reports, source_counts = _aggregate_weighted_daily_series(
        db=db,
        station_weights=stations_cfg,
        start_year=start_year,
        end_year=end_year,
        allowed_sources=allowed_sources,
        fill_gaps=fill_gaps,
    )

    # Enriquecer metadata de estaciones con su peso normalizado
    enriched_stations = []
    lat_sum = lon_sum = alt_sum = w_geo_sum = 0.0
    for rep in stn_reports:
        m = meta_by_code.get(rep["codigo"], {})
        w_n = rep["weight_norm"]
        lat = m.get("latitud")
        lon = m.get("longitud")
        alt = m.get("altitud")
        if lat is not None and lon is not None:
            lat_sum += float(lat) * w_n
            lon_sum += float(lon) * w_n
            alt_sum += float(alt or 0.0) * w_n
            w_geo_sum += w_n
        enriched_stations.append({
            **m,
            **rep,
        })

    avg_lat = round(lat_sum / w_geo_sum, 6) if w_geo_sum > 0 else 4.6097
    avg_lon = round(lon_sum / w_geo_sum, 6) if w_geo_sum > 0 else -74.0817
    avg_alt = round(alt_sum / w_geo_sum, 1) if w_geo_sum > 0 else 1500.0

    suggested_region = detect_invias_region(
        avg_lat, avg_lon, enriched_stations[0].get("departamento_nombre", "") if enriched_stations else ""
    )
    idf_region = str(config.get("idf_region") or suggested_region)

    if merged_df.empty:
        return {
            "has_data": False,
            "message": "Las estaciones seleccionadas no poseen registros en la base local para ese rango. Use el puente de actualización (IDEAM API / Open-Meteo / Base Histórica).",
            "project": {
                "name": config.get("name", "Sin Nombre"),
                "description": config.get("description", ""),
                "location": config.get("location", ""),
                "avg_lat": avg_lat,
                "avg_lon": avg_lon,
                "avg_alt": avg_alt,
                "suggested_idf_region": suggested_region,
            },
            "stations": enriched_stations,
        }

    # Calcular FAO-56 radiación y ET0 diaria
    coastal = abs(avg_alt) < 80.0 and avg_lat > 7.5
    rad_df = compute_fao56_daily_et0(merged_df, lat_deg=avg_lat, altitude_m=avg_alt, coastal_krs=coastal)
    daily_full = merged_df.copy()
    daily_full["ra_mj"] = rad_df["ra_mj"]
    daily_full["daylight_h"] = rad_df["daylight_h"]
    daily_full["rs_mj"] = rad_df["rs_mj"]
    daily_full["wind_ms"] = rad_df["wind_ms"]
    daily_full["et0_mm"] = rad_df["et0_mm"]

    # Agregar promedios diarios climatológicos (366 días del año calendario, índice mes-día)
    daily_full["month"] = daily_full.index.month
    daily_full["day"] = daily_full.index.day
    daily_full["year"] = daily_full.index.year

    # 1) Promedios mensuales por año (para series de tiempo y promedios climatológicos mensuales consistentes)
    monthly_by_year_rows: list[dict[str, Any]] = []
    for (yr, mo), grp in daily_full.groupby(["year", "month"], sort=True):
        p_sum = float(grp[1].sum()) if 1 in grp and grp[1].notna().any() else None
        t_mean = float(grp[5].mean()) if 5 in grp and grp[5].notna().any() else None
        tmax_mean = float(grp[6].mean()) if 6 in grp and grp[6].notna().any() else None
        tmin_mean = float(grp[7].mean()) if 7 in grp and grp[7].notna().any() else None
        rh_mean = float(grp[4].mean()) if 4 in grp and grp[4].notna().any() else None
        sun_mean = float(grp[2].mean()) if 2 in grp and grp[2].notna().any() else None
        evap_sum = float(grp[3].sum()) if 3 in grp and grp[3].notna().any() else None
        wind_mean = float(grp["wind_ms"].mean()) if grp["wind_ms"].notna().any() else None
        rs_mean = float(grp["rs_mj"].mean()) if grp["rs_mj"].notna().any() else None
        et0_sum = float(grp["et0_mm"].sum()) if grp["et0_mm"].notna().any() else None

        monthly_by_year_rows.append({
            "year": int(yr),
            "month": int(mo),
            "month_name": MONTH_ABBR_ES[int(mo) - 1],
            "precip_mm": round(p_sum, 2) if p_sum is not None else None,
            "temp_mean_c": round(t_mean, 2) if t_mean is not None else None,
            "temp_max_c": round(tmax_mean, 2) if tmax_mean is not None else None,
            "temp_min_c": round(tmin_mean, 2) if tmin_mean is not None else None,
            "rh_pct": round(rh_mean, 2) if rh_mean is not None else None,
            "sunshine_h": round(sun_mean, 2) if sun_mean is not None else None,
            "evap_mm": round(evap_sum, 2) if evap_sum is not None else None,
            "wind_ms": round(wind_mean, 2) if wind_mean is not None else None,
            "solar_rad_mj": round(rs_mean, 2) if rs_mean is not None else None,
            "et0_pm_mm": round(et0_sum, 2) if et0_sum is not None else None,
        })

    mby_df = pd.DataFrame(monthly_by_year_rows)

    # 2) Promedios diarios climatológicos (Mes 1..12, Día 1..31)
    daily_clim_rows: list[dict[str, Any]] = []
    for (mo, dy), grp in daily_full.groupby(["month", "day"], sort=True):
        if mo == 2 and dy == 29:
            continue  # tabla climática estándar de 365 días para balance diario limpio
        p_d = float(grp[1].mean()) if 1 in grp and grp[1].notna().any() else 0.0
        sun_d = float(grp[2].mean()) if 2 in grp and grp[2].notna().any() else None
        rh_d = float(grp[4].mean()) if 4 in grp and grp[4].notna().any() else None
        t_d = float(grp[5].mean()) if 5 in grp and grp[5].notna().any() else None
        tmin_d = float(grp[7].mean()) if 7 in grp and grp[7].notna().any() else None
        tmax_d = float(grp[6].mean()) if 6 in grp and grp[6].notna().any() else None
        w_d = float(grp["wind_ms"].mean()) if grp["wind_ms"].notna().any() else None
        rs_d = float(grp["rs_mj"].mean()) if grp["rs_mj"].notna().any() else None
        h_d = float(grp["daylight_h"].mean()) if grp["daylight_h"].notna().any() else None
        et0_d = float(grp["et0_mm"].mean()) if grp["et0_mm"].notna().any() else 0.0
        daily_clim_rows.append({
            "month": int(mo),
            "month_abbr": MONTH_ABBR_ES[int(mo) - 1],
            "day": int(dy),
            "precip_mm": round(p_d, 2),
            "sunshine_h": round(sun_d, 2) if sun_d is not None else None,
            "rh_pct": round(rh_d, 2) if rh_d is not None else None,
            "temp_mean_c": round(t_d, 2) if t_d is not None else None,
            "temp_min_c": round(tmin_d, 2) if tmin_d is not None else None,
            "temp_max_c": round(tmax_d, 2) if tmax_d is not None else None,
            "wind_ms": round(w_d, 2) if w_d is not None else None,
            "solar_rad_mj": round(rs_d, 2) if rs_d is not None else None,
            "daylight_h": round(h_d, 2) if h_d is not None else None,
            "etp_pm_mm": round(et0_d, 2),
        })

    # 3) Promedios mensuales multianuales (12 meses) + Thornthwaite & Penman-Monteith Balance
    monthly_p: list[float] = []
    monthly_t: list[float] = []
    monthly_tmax: list[float | None] = []
    monthly_tmin: list[float | None] = []
    monthly_rh: list[float | None] = []
    monthly_sun: list[float | None] = []
    monthly_wind: list[float | None] = []
    monthly_rs: list[float | None] = []
    monthly_pm_et0: list[float] = []

    for mo in range(1, 13):
        sub_d = [r for r in daily_clim_rows if r["month"] == mo]
        sub_m = mby_df[mby_df["month"] == mo]

        # Promedio mensual de precipitación sumando los promedios diarios del mes (garantiza consistencia diaria-mensual aunque falten días en años aislados)
        p_m_sum = float(sum(r["precip_mm"] for r in sub_d)) if sub_d else 0.0
        t_m = float(sub_m["temp_mean_c"].mean()) if "temp_mean_c" in sub_m and sub_m["temp_mean_c"].notna().any() else 18.0
        tmax_m = float(sub_m["temp_max_c"].mean()) if "temp_max_c" in sub_m and sub_m["temp_max_c"].notna().any() else None
        tmin_m = float(sub_m["temp_min_c"].mean()) if "temp_min_c" in sub_m and sub_m["temp_min_c"].notna().any() else None
        rh_m = float(sub_m["rh_pct"].mean()) if "rh_pct" in sub_m and sub_m["rh_pct"].notna().any() else None
        sun_m = float(sub_m["sunshine_h"].mean()) if "sunshine_h" in sub_m and sub_m["sunshine_h"].notna().any() else None
        w_m = float(sub_m["wind_ms"].mean()) if "wind_ms" in sub_m and sub_m["wind_ms"].notna().any() else None
        rs_m = float(sub_m["solar_rad_mj"].mean()) if "solar_rad_mj" in sub_m and sub_m["solar_rad_mj"].notna().any() else None
        et0_m = float(sum(r["etp_pm_mm"] for r in sub_d)) if sub_d else 0.0

        monthly_p.append(round(p_m_sum, 2))
        monthly_t.append(round(t_m, 2))
        monthly_tmax.append(round(tmax_m, 2) if tmax_m is not None else None)
        monthly_tmin.append(round(tmin_m, 2) if tmin_m is not None else None)
        monthly_rh.append(round(rh_m, 2) if rh_m is not None else None)
        monthly_sun.append(round(sun_m, 2) if sun_m is not None else None)
        monthly_wind.append(round(w_m, 2) if w_m is not None else None)
        monthly_rs.append(round(rs_m, 2) if rs_m is not None else None)
        monthly_pm_et0.append(round(et0_m, 2))

    tw_1948 = thornthwaite_monthly_etp(monthly_t, avg_lat)
    chosen_etp = tw_1948["etp_corrected"] if etp_method == "thornthwaite" else monthly_pm_et0
    wb_monthly = compute_cyclic_water_balance(monthly_p, chosen_etp, soil_reserve)

    # También correr balance diario sobre el año tipo (365 días) si Penman-Monteith está activo
    if etp_method == "thornthwaite":
        daily_etp_series = []
        for r in daily_clim_rows:
            m_idx = r["month"] - 1
            daily_etp_series.append(tw_1948["etp_corrected"][m_idx] / DAYS_IN_MONTH_NONLEAP[m_idx])
    else:
        daily_etp_series = [r["etp_pm_mm"] for r in daily_clim_rows]

    wb_daily = compute_cyclic_water_balance(
        [r["precip_mm"] for r in daily_clim_rows],
        daily_etp_series,
        soil_reserve,
    )
    for idx, r in enumerate(daily_clim_rows):
        r["etp_used_mm"] = round(daily_etp_series[idx], 2)
        r["storage_mm"] = wb_daily["storage"][idx]
        r["excess_mm"] = wb_daily["excess"][idx]
        r["deficit_mm"] = wb_daily["deficit"][idx]
        r["tmi_pct"] = wb_daily["step_tmi_pct"][idx]

    monthly_rows = []
    for m in range(12):
        monthly_rows.append({
            "month_num": m + 1,
            "month": MONTH_NAMES_ES[m],
            "month_abbr": MONTH_ABBR_ES[m],
            "precip_mm": monthly_p[m],
            "temp_mean_c": monthly_t[m],
            "temp_max_c": monthly_tmax[m],
            "temp_min_c": monthly_tmin[m],
            "rh_pct": monthly_rh[m],
            "sunshine_h": monthly_sun[m],
            "wind_ms": monthly_wind[m],
            "solar_rad_mj": monthly_rs[m],
            "heat_index": tw_1948["heat_indices"][m],
            "daylight_h": tw_1948["daylight_hours"][m],
            "etp_thornthwaite_uncorr_mm": tw_1948["etp_uncorrected"][m],
            "etp_thornthwaite_mm": tw_1948["etp_corrected"][m],
            "etp_penman_mm": monthly_pm_et0[m],
            "etp_active_mm": round(float(chosen_etp[m]), 2),
            "etr_mm": wb_monthly["etr"][m],
            "storage_mm": wb_monthly["storage"][m],
            "excess_mm": wb_monthly["excess"][m],
            "deficit_mm": wb_monthly["deficit"][m],
            "tmi_step_pct": wb_monthly["step_tmi_pct"][m],
        })

    # 4) Resumen anual (Promedios/Totales por Año)
    annual_rows: list[dict[str, Any]] = []
    for yr, grp in daily_full.groupby("year", sort=True):
        p_tot = float(grp[1].sum()) if 1 in grp and grp[1].notna().any() else None
        p_max24 = float(grp[1].max()) if 1 in grp and grp[1].notna().any() else None
        t_m = float(grp[5].mean()) if 5 in grp and grp[5].notna().any() else None
        tmax_m = float(grp[6].mean()) if 6 in grp and grp[6].notna().any() else None
        tmin_m = float(grp[7].mean()) if 7 in grp and grp[7].notna().any() else None
        rh_m = float(grp[4].mean()) if 4 in grp and grp[4].notna().any() else None
        et0_tot = float(grp["et0_mm"].sum()) if grp["et0_mm"].notna().any() else None
        comp_p = round(100.0 * float(grp[1].notna().sum()) / len(grp), 1) if 1 in grp else 0.0
        comp_t = round(100.0 * float(grp[5].notna().sum()) / len(grp), 1) if 5 in grp else 0.0
        annual_rows.append({
            "year": int(yr),
            "precip_mm": round(p_tot, 1) if p_tot is not None else None,
            "pmax_24h_mm": round(p_max24, 1) if p_max24 is not None else None,
            "temp_mean_c": round(t_m, 2) if t_m is not None else None,
            "temp_max_c": round(tmax_m, 2) if tmax_m is not None else None,
            "temp_min_c": round(tmin_m, 2) if tmin_m is not None else None,
            "rh_pct": round(rh_m, 1) if rh_m is not None else None,
            "et0_pm_mm": round(et0_tot, 1) if et0_tot is not None else None,
            "completeness_precip_pct": comp_p,
            "completeness_temp_pct": comp_t,
        })

    # 5) Promedio temperatura media, clase térmica y clasificaciones climáticas oficiales
    mean_annual_t = float(np.mean(monthly_t)) if monthly_t else 0.0
    thermal_class = classify_temperature_climalike(mean_annual_t)
    classifications = compute_all_climate_classifications(
        monthly_temps_c=monthly_t,
        monthly_precip_mm=monthly_p,
        annual_etp_mm=wb_monthly["total_etp_mm"],
        annual_etr_mm=wb_monthly["total_etr_mm"],
        altitude_m=avg_alt,
        thornthwaite_summary={
            "thornthwaite_index_pct": wb_monthly["thornthwaite_index_pct"],
            "humidity_class": wb_monthly["humidity_class"],
            "humidity_description": wb_monthly["humidity_description"],
            "thermal_class": thermal_class,
        },
    )

    # 6) Pavimentos, Hidrología IDF y Calidad de Datos
    pavement = compute_pavement_metrics(
        daily_df=daily_full,
        lat_deg=avg_lat,
        thornthwaite_tmi=wb_monthly["thornthwaite_index_pct"],
        water_table_m=water_table_m,
        monthly_temps_clim=monthly_t,
        annual_precip_mm=wb_monthly["total_precip_mm"],
    )
    idf_method = str(config.get("idf_method") or "invias")
    hyetograph_tr = int(config.get("hyetograph_tr") or 10)
    hyetograph_duration_min = int(config.get("hyetograph_duration_min") or 60)
    idf_result = compute_idf_and_extremes(
        daily_df=daily_full,
        region_name=idf_region,
        idf_method=idf_method,
        custom_params=config.get("idf_custom_params"),
        hyetograph_tr=hyetograph_tr,
        hyetograph_duration_min=hyetograph_duration_min,
    )
    quality = compute_quality_report(daily_full)

    # 6b) Análisis SGC (movimientos en masa), Erosividad RUSLE (ANLA), Sequías (SPEI/IAP) y Cuenca INVIAS/SCS
    curve_number = float(config.get("curve_number") or 75.0)
    sgc_r3_intercept = float(config.get("sgc_r3_intercept") or 70.0)
    sgc_r15_slope = float(config.get("sgc_r15_slope") or 0.47)
    geohazards_sgc = compute_sgc_landslide_thresholds(
        daily_df=daily_full,
        soil_cn=curve_number,
        r3_intercept=sgc_r3_intercept,
        r15_slope=sgc_r15_slope,
    )
    erosivity = compute_erosivity_rusle(monthly_rows)
    drought = compute_spei_and_anomalies(daily_df=daily_full, et0_series=rad_df["et0_mm"], annual_rows=annual_rows)
    watershed = compute_watershed_runoff_scs(
        idf_result=idf_result,
        area_km2=float(config.get("watershed_area_km2") or 1.0),
        length_m=float(config.get("watershed_length_m") or 800.0),
        slope_pct=float(config.get("watershed_slope_pct") or 5.0),
        curve_number=curve_number,
        runoff_coeff=float(config.get("runoff_coeff") or 0.50),
    )

    # 7) Serie diaria reciente / muestreada para el explorador interactivo (últimos 5 años o todo si <= 10 años)
    ts_years = sorted(daily_full["year"].unique().tolist())
    ts_cutoff_year = ts_years[-10] if len(ts_years) > 10 else ts_years[0]
    ts_sub = daily_full[daily_full["year"] >= ts_cutoff_year]
    daily_series_explorer = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "precip": round(float(row[1]), 2) if 1 in ts_sub and pd.notna(row[1]) else None,
            "tmean": round(float(row[5]), 2) if 5 in ts_sub and pd.notna(row[5]) else None,
            "tmax": round(float(row[6]), 2) if 6 in ts_sub and pd.notna(row[6]) else None,
            "tmin": round(float(row[7]), 2) if 7 in ts_sub and pd.notna(row[7]) else None,
            "rh": round(float(row[4]), 1) if 4 in ts_sub and pd.notna(row[4]) else None,
            "et0": round(float(row["et0_mm"]), 2) if pd.notna(row["et0_mm"]) else None,
        }
        for idx, row in ts_sub.iterrows()
    ]

    rs_sources_counts = rad_df["rs_source"].value_counts().to_dict()

    return {
        "has_data": True,
        "project": {
            "name": config.get("name") or "Sin Nombre",
            "description": config.get("description") or "",
            "location": config.get("location") or "",
            "soil_max_reserve_mm": soil_reserve,
            "water_table_m": water_table_m,
            "end_year": end_year,
            "last_n_years": last_n_years,
            "actual_year_min": int(daily_full["year"].min()),
            "actual_year_max": int(daily_full["year"].max()),
            "total_days_analyzed": int(len(daily_full)),
            "etp_method": etp_method,
            "etp_method_label": "Thornthwaite (Índice de Calor 1948)" if etp_method == "thornthwaite" else "Penman - Monteith (FAO-56)",
            "avg_lat": avg_lat,
            "avg_lon": avg_lon,
            "avg_alt": avg_alt,
            "suggested_idf_region": suggested_region,
            "idf_region": idf_region,
            "idf_method": idf_method,
            "study_profile": str(config.get("study_profile") or "integral"),
        },
        "stations": enriched_stations,
        "source_day_counts": source_counts,
        "radiation_sources": rs_sources_counts,
        "classifications": classifications,
        "summary": {
            "mean_annual_temp_c": round(mean_annual_t, 2),
            "thermal_class": thermal_class,
            "annual_precip_mm": wb_monthly["total_precip_mm"],
            "annual_etp_mm": wb_monthly["total_etp_mm"],
            "annual_etr_mm": wb_monthly["total_etr_mm"],
            "annual_excess_mm": wb_monthly["total_excess_mm"],
            "annual_deficit_mm": wb_monthly["total_deficit_mm"],
            "humidity_index_pct": wb_monthly["humidity_index_pct"],
            "aridity_index_pct": wb_monthly["aridity_index_pct"],
            "thornthwaite_index_pct": wb_monthly["thornthwaite_index_pct"],
            "thornthwaite_mepdg_tmi": wb_monthly["thornthwaite_mepdg_tmi"],
            "humidity_class": wb_monthly["humidity_class"],
            "humidity_description": wb_monthly["humidity_description"],
            "annual_heat_index": tw_1948["annual_heat_index"],
            "exponent_a": tw_1948["exponent_a"],
        },
        "water_balance_daily_summary": {
            "thornthwaite_index_pct": wb_daily["thornthwaite_index_pct"],
            "humidity_class": wb_daily["humidity_class"],
            "total_precip_mm": wb_daily["total_precip_mm"],
            "total_etp_mm": wb_daily["total_etp_mm"],
            "total_excess_mm": wb_daily["total_excess_mm"],
            "total_deficit_mm": wb_daily["total_deficit_mm"],
        },
        "pavement": pavement,
        "monthly_summary": monthly_rows,
        "daily_climatology": daily_clim_rows,
        "annual_summary": annual_rows,
        "monthly_by_year": monthly_by_year_rows,
        "hydrology_idf": idf_result,
        "quality": quality,
        "geohazards_sgc": geohazards_sgc,
        "erosivity": erosivity,
        "drought": drought,
        "watershed": watershed,
        "daily_series_explorer": daily_series_explorer,
    }
