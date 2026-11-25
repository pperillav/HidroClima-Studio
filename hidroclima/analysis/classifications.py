"""Clasificaciones climáticas y bioclimáticas oficiales para estudios ambientales (ANLA, POMCA, ENA-IDEAM)."""

from __future__ import annotations

from typing import Any

import numpy as np

from hidroclima.config import ENA_ARIDITY_CLASSES


def classify_caldas_lang(
    mean_temp_c: float,
    annual_precip_mm: float,
    altitude_m: float | None = None,
) -> dict[str, Any]:
    """
    Clasificación Climática de Caldas-Lang adoptada por el IDEAM.
    Combina el piso térmico de Caldas (por temperatura media y altitud de referencia)
    con el factor de humedad de Lang (P / T).
    """
    t = float(mean_temp_c)
    p = max(0.0, float(annual_precip_mm))

    # Piso térmico de Caldas según temperatura media (criterio térmico principal en trópico colombiano)
    if t > 24.0:
        piso, sym_t, alt_ref = "Cálido", "C", "0 – 1.000 m"
    elif t >= 17.5:
        piso, sym_t, alt_ref = "Templado", "T", "1.001 – 2.000 m"
    elif t >= 12.0:
        piso, sym_t, alt_ref = "Frío", "F", "2.001 – 3.000 m"
    elif t >= 7.0:
        piso, sym_t, alt_ref = "Páramo Bajo", "Pb", "3.001 – 3.700 m"
    else:
        piso, sym_t, alt_ref = "Páramo Alto", "Pa", "> 3.700 m"

    lang_factor = p / max(0.5, t)
    if lang_factor <= 20.0:
        hum, sym_h = "Desértico", "D"
    elif lang_factor <= 40.0:
        hum, sym_h = "Árido", "A"
    elif lang_factor <= 60.0:
        hum, sym_h = "Semiárido", "sa"
    elif lang_factor <= 100.0:
        hum, sym_h = "Semihúmedo", "sh"
    elif lang_factor <= 160.0:
        hum, sym_h = "Húmedo", "H"
    else:
        hum, sym_h = "Superhúmedo", "SH"

    return {
        "piso_termico": piso,
        "altitud_ref": alt_ref,
        "altitud_estacion_m": round(float(altitude_m), 1) if altitude_m is not None else None,
        "lang_factor": round(lang_factor, 2),
        "grado_humedad": hum,
        "symbol": f"{sym_t}{sym_h}",
        "label": f"{piso} {hum} ({sym_t}{sym_h})",
    }


def classify_holdridge_life_zone(
    monthly_temps_c: list[float],
    annual_precip_mm: float,
    altitude_m: float | None = None,
) -> dict[str, Any]:
    """
    Sistema de Zonas de Vida de Leslie R. Holdridge.
    Biotemperatura (0 < T < 30 °C), ETP_Holdridge = 58.93 * T_bio, Relación EPT = ETP / P.
    """
    t_arr = np.clip(np.array(monthly_temps_c, dtype=float), 0.0, 30.0)
    t_bio = float(np.mean(t_arr)) if t_arr.size else 18.0
    etp_hold = 58.93 * t_bio
    p = max(1.0, float(annual_precip_mm))
    ept_ratio = etp_hold / p

    # Piso altitudinal / latitudinal (región tropical)
    if t_bio >= 24.0:
        piso_name, piso_sym = "Tropical", "T"
    elif t_bio >= 18.0:
        piso_name, piso_sym = "Premontano", "PM"
    elif t_bio >= 12.0:
        piso_name, piso_sym = "Montano Bajo", "MB"
    elif t_bio >= 6.0:
        piso_name, piso_sym = "Montano", "M"
    elif t_bio >= 3.0:
        piso_name, piso_sym = "Subalpino", "SA"
    else:
        piso_name, piso_sym = "Alpino", "A"

    # Provincia de humedad y formación vegetal por relación EPT = ETP / P
    if ept_ratio > 32.0:
        prov, veg, veg_sym = "Desértico", "Desierto", "d"
    elif ept_ratio > 16.0:
        prov, veg, veg_sym = "Matorral Desértico", "Matorral desértico", "md"
    elif ept_ratio > 8.0:
        prov, veg, veg_sym = "Espinoso", "Monte espinoso", "me"
    elif ept_ratio > 4.0:
        prov, veg, veg_sym = "Muy Seco", "Bosque muy seco", "bms"
    elif ept_ratio > 2.0:
        prov, veg, veg_sym = "Seco", "Bosque seco", "bs"
    elif ept_ratio > 1.0:
        prov, veg, veg_sym = "Húmedo", "Bosque húmedo", "bh"
    elif ept_ratio > 0.5:
        prov, veg, veg_sym = "Muy Húmedo", "Bosque muy húmedo", "bmh"
    elif ept_ratio > 0.25:
        prov, veg, veg_sym = "Perhúmedo (Pluvial)", "Bosque pluvial", "bp"
    else:
        prov, veg, veg_sym = "Superhúmedo (Pluvial)", "Bosque pluvial", "bp"

    if t_bio < 6.0:
        veg = "Páramo / Tundra " + prov.lower()
        veg_sym = "p"

    return {
        "biotemp_c": round(t_bio, 2),
        "etp_holdridge_mm": round(etp_hold, 1),
        "ept_ratio": round(ept_ratio, 3),
        "piso_altitudinal": piso_name,
        "provincia_humedad": prov,
        "symbol": f"{veg_sym}-{piso_sym}",
        "life_zone": f"{veg} {piso_name} ({veg_sym}-{piso_sym})",
    }


def classify_koppen_geiger(
    monthly_temps_c: list[float],
    monthly_precip_mm: list[float],
) -> dict[str, Any]:
    """Clasificación climática estándar de Köppen-Geiger (Peel et al., 2007)."""
    if len(monthly_temps_c) != 12 or len(monthly_precip_mm) != 12:
        return {"code": "N/D", "label": "Datos insuficientes"}

    t = np.array(monthly_temps_c, dtype=float)
    p = np.array(monthly_precip_mm, dtype=float)
    mat = float(np.mean(t))
    map_p = float(np.sum(p))
    t_max = float(np.max(t))
    t_min = float(np.min(t))
    p_min = float(np.min(p))

    # Polar (E)
    if t_max < 10.0:
        code = "EF" if t_max < 0.0 else "ET"
        lbl = "Polar / Nival (EF)" if code == "EF" else "Tundra / Alta Montaña (ET)"
        return {"code": code, "label": lbl}

    # Umbral de aridez (Peel et al., 2007) en mm/año: P_thresh = 20*MAT + 140 (lluvia bimodal/uniforme)
    p_thresh = 20.0 * mat + 140.0
    if map_p < p_thresh:
        is_desert = map_p < 0.5 * p_thresh
        bw_bs = "BW" if is_desert else "BS"
        hk = "h" if mat >= 18.0 else "k"
        code = f"{bw_bs}{hk}"
        desc = "Árido cálido" if code == "BWh" else ("Árido frío" if code == "BWk" else ("Semiárido cálido" if code == "BSh" else "Semiárido frío"))
        return {"code": code, "label": f"{desc} ({code})"}

    # Tropical (A)
    if t_min >= 18.0:
        if p_min >= 60.0:
            return {"code": "Af", "label": "Tropical ecuatorial húmedo sin estación seca (Af)"}
        if p_min >= 100.0 - map_p / 25.0:
            return {"code": "Am", "label": "Tropical monzónico (Am)"}
        return {"code": "Aw", "label": "Tropical de sabana con estación seca (Aw)"}

    # Templado (C) / Frío continental (D)
    group = "C" if t_min > 0.0 else "D"
    # Estacionalidad precipitación
    p_wet = float(np.max(p))
    if p_min < 40.0 and p_min < p_wet / 3.0:
        precip_sub = "w"
    else:
        precip_sub = "f"

    months_ge_10 = int(np.sum(t >= 10.0))
    if t_max >= 22.0:
        temp_sub = "a"
        t_desc = "verano cálido"
    elif months_ge_10 >= 4:
        temp_sub = "b"
        t_desc = "templado oceánico/andino"
    else:
        temp_sub = "c"
        t_desc = "subpolar/frío"

    code = f"{group}{precip_sub}{temp_sub}"
    grp_lbl = "Templado" if group == "C" else "Frío"
    return {"code": code, "label": f"{grp_lbl} húmedo {t_desc} ({code})"}


def classify_ena_aridity_index(etp_mm: float, etr_mm: float) -> dict[str, Any]:
    """Índice de Aridez del Estudio Nacional del Agua (ENA - IDEAM): IA = (ETP - ETR) / ETP."""
    if etp_mm <= 1e-6:
        return {"ia": 0.0, "category": "N/D", "description": "Sin demanda evaporativa estimada"}
    ia = max(0.0, (float(etp_mm) - float(etr_mm)) / float(etp_mm))
    for thresh, cat, desc in ENA_ARIDITY_CLASSES:
        if ia < thresh:
            return {"ia": round(ia, 3), "category": cat, "description": desc}
    return {"ia": round(ia, 3), "category": ENA_ARIDITY_CLASSES[-1][1], "description": ENA_ARIDITY_CLASSES[-1][2]}


def compute_all_climate_classifications(
    monthly_temps_c: list[float],
    monthly_precip_mm: list[float],
    annual_etp_mm: float,
    annual_etr_mm: float,
    altitude_m: float | None,
    thornthwaite_summary: dict[str, Any],
) -> dict[str, Any]:
    """Agrupa las 5 clasificaciones oficiales requeridas en estudios climáticos, EIA, POMCA y vías."""
    mean_t = float(np.mean(monthly_temps_c)) if monthly_temps_c else 18.0
    annual_p = float(np.sum(monthly_precip_mm)) if monthly_precip_mm else 0.0

    return {
        "caldas_lang": classify_caldas_lang(mean_t, annual_p, altitude_m),
        "holdridge": classify_holdridge_life_zone(monthly_temps_c, annual_p, altitude_m),
        "koppen_geiger": classify_koppen_geiger(monthly_temps_c, monthly_precip_mm),
        "ena_aridity": classify_ena_aridity_index(annual_etp_mm, annual_etr_mm),
        "thornthwaite": {
            "index_pct": thornthwaite_summary.get("thornthwaite_index_pct"),
            "humidity_class": thornthwaite_summary.get("humidity_class"),
            "humidity_description": thornthwaite_summary.get("humidity_description"),
            "thermal_class": thornthwaite_summary.get("thermal_class"),
        },
    }
