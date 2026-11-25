"""Cálculo del Índice de Thornthwaite (1948 y Penman-Monteith), Balance Hídrico y Clasificación Climática."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from hidroclima.analysis.radiation_etp import solar_geometry_series
from hidroclima.config import DAYS_IN_MONTH_NONLEAP, MONTH_NAMES_ES, THERMAL_CLASSES, THORNTHWAITE_HUMIDITY_CLASSES

MID_MONTH_DOY = np.array([15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349], dtype=np.float64)


def classify_humidity_thornthwaite(im_pct: float) -> tuple[str, str]:
    for threshold, label, desc in THORNTHWAITE_HUMIDITY_CLASSES:
        if im_pct <= threshold:
            return label, desc
    return THORNTHWAITE_HUMIDITY_CLASSES[-1][1], THORNTHWAITE_HUMIDITY_CLASSES[-1][2]


def classify_temperature_climalike(temp_c: float) -> str:
    for threshold, label in THERMAL_CLASSES:
        if temp_c <= threshold:
            return label
    return THERMAL_CLASSES[-1][1]


def thornthwaite_monthly_etp(
    monthly_temps: list[float],
    lat_deg: float,
) -> dict[str, Any]:
    """Calcula Índice de Calor I, exponente a, ETP sin corregir y ETP corregida de Thornthwaite (1948)."""
    temps = np.array([max(0.0, float(t)) for t in monthly_temps], dtype=np.float64)
    heat_indices = np.where(temps > 0.0, (temps / 5.0) ** 1.514, 0.0)
    annual_i = float(np.sum(heat_indices))

    if annual_i <= 1e-6:
        a = 0.49239
        etp_uncorr = np.zeros(12, dtype=np.float64)
    else:
        a = (
            6.75e-7 * (annual_i ** 3)
            - 7.71e-5 * (annual_i ** 2)
            + 1.792e-2 * annual_i
            + 0.49239
        )
        etp_uncorr = np.zeros(12, dtype=np.float64)
        for m in range(12):
            t = temps[m]
            if t <= 0.0:
                etp_uncorr[m] = 0.0
            elif t < 26.5:
                etp_uncorr[m] = 16.0 * ((10.0 * t / annual_i) ** a)
            else:
                etp_uncorr[m] = -415.85 + 32.24 * t - 0.43 * (t ** 2)

    _, daylight_h = solar_geometry_series(lat_deg, MID_MONTH_DOY)
    days = np.array(DAYS_IN_MONTH_NONLEAP, dtype=np.float64)
    corr_factor = (daylight_h / 12.0) * (days / 30.0)
    etp_corr = np.maximum(0.0, etp_uncorr * corr_factor)

    return {
        "heat_indices": [round(float(x), 3) for x in heat_indices],
        "annual_heat_index": round(annual_i, 3),
        "exponent_a": round(float(a), 5),
        "daylight_hours": [round(float(x), 2) for x in daylight_h],
        "etp_uncorrected": [round(float(x), 2) for x in etp_uncorr],
        "etp_corrected": [round(float(x), 2) for x in etp_corr],
    }


def compute_cyclic_water_balance(
    precip_vals: list[float],
    etp_vals: list[float],
    soil_max_reserve_mm: float = 100.0,
) -> dict[str, Any]:
    """
    Simula balance hídrico secuencial con reserva máxima de agua en el suelo R_max (mm),
    convergiendo a ciclo estacionario anual (equilibrio inicial == final).
    Balance hídrico secuencial cíclico (equilibrio inicial == final) con cálculo de ETR, Exceso y Déficit.
    """
    n = len(precip_vals)
    r_max = max(1.0, float(soil_max_reserve_mm))

    # Convergencia cíclica (hasta 25 iteraciones sobre el ciclo climatológico)
    storage_end = r_max
    for _ in range(25):
        s = storage_end
        for i in range(n):
            diff = float(precip_vals[i]) - float(etp_vals[i])
            s_cand = s + diff
            if s_cand > r_max:
                s = r_max
            elif s_cand < 0.0:
                s = 0.0
            else:
                s = s_cand
        if abs(s - storage_end) < 1e-4:
            break
        storage_end = s

    storage = []
    excess = []
    deficit = []
    etr = []
    tmi_step = []
    s = storage_end

    for i in range(n):
        p = float(precip_vals[i])
        etp = max(0.0, float(etp_vals[i]))
        s_cand = s + p - etp
        if s_cand > r_max:
            exc = s_cand - r_max
            defic = 0.0
            s_next = r_max
            e_real = etp
        elif s_cand < 0.0:
            exc = 0.0
            defic = -s_cand
            s_next = 0.0
            e_real = p + s
        else:
            exc = 0.0
            defic = 0.0
            s_next = s_cand
            e_real = etp
        s = s_next
        storage.append(round(s, 2))
        excess.append(round(exc, 2))
        deficit.append(round(defic, 2))
        etr.append(round(e_real, 2))
        if etp > 1e-6:
            tmi_step.append(round(100.0 * (exc - 0.6 * defic) / etp, 2))
        else:
            tmi_step.append(0.0)

    total_p = float(sum(precip_vals))
    total_etp = float(sum(etp_vals))
    total_exc = float(sum(excess))
    total_def = float(sum(deficit))
    total_etr = float(sum(etr))

    if total_etp > 1e-6:
        ih = 100.0 * total_exc / total_etp
        ia = 100.0 * total_def / total_etp
        im_1948 = ih - 0.6 * ia
        im_mepdg = 100.0 * (total_p / total_etp - 1.0)
    else:
        ih = ia = im_1948 = im_mepdg = 0.0

    hum_class, hum_desc = classify_humidity_thornthwaite(im_1948)

    return {
        "storage": storage,
        "excess": excess,
        "deficit": deficit,
        "etr": etr,
        "step_tmi_pct": tmi_step,
        "total_precip_mm": round(total_p, 2),
        "total_etp_mm": round(total_etp, 2),
        "total_etr_mm": round(total_etr, 2),
        "total_excess_mm": round(total_exc, 2),
        "total_deficit_mm": round(total_def, 2),
        "humidity_index_pct": round(ih, 2),
        "aridity_index_pct": round(ia, 2),
        "thornthwaite_index_pct": round(im_1948, 2),
        "thornthwaite_mepdg_tmi": round(im_mepdg, 2),
        "humidity_class": hum_class,
        "humidity_description": hum_desc,
    }


def calculate_monthly_thornthwaite_standalone(
    monthly_precip: list[float],
    monthly_temp: list[float],
    lat_deg: float,
    soil_max_reserve_mm: float = 100.0,
) -> dict[str, Any]:
    """Equivalente mejorado al módulo 'Cálculo Índice de Thornthwaite con Datos Mensuales'."""
    if len(monthly_precip) != 12 or len(monthly_temp) != 12:
        raise ValueError("Se requieren exactamente 12 valores mensuales de precipitación y temperatura.")
    tw = thornthwaite_monthly_etp(monthly_temp, lat_deg)
    wb = compute_cyclic_water_balance(monthly_precip, tw["etp_corrected"], soil_max_reserve_mm)
    mean_t = float(np.mean(monthly_temp))
    temp_class = classify_temperature_climalike(mean_t)

    rows = []
    for m in range(12):
        rows.append({
            "month_num": m + 1,
            "month": MONTH_NAMES_ES[m],
            "precip_mm": round(float(monthly_precip[m]), 2),
            "temp_c": round(float(monthly_temp[m]), 2),
            "heat_index": tw["heat_indices"][m],
            "daylight_h": tw["daylight_hours"][m],
            "etp_uncorrected_mm": tw["etp_uncorrected"][m],
            "etp_corrected_mm": tw["etp_corrected"][m],
            "etr_mm": wb["etr"][m],
            "storage_mm": wb["storage"][m],
            "excess_mm": wb["excess"][m],
            "deficit_mm": wb["deficit"][m],
            "tmi_step_pct": wb["step_tmi_pct"][m],
        })

    return {
        "rows": rows,
        "annual_heat_index": tw["annual_heat_index"],
        "exponent_a": tw["exponent_a"],
        "mean_temp_c": round(mean_t, 2),
        "thermal_class": temp_class,
        **wb,
    }
