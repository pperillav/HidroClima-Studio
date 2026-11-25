"""Exportación GIS (GeoJSON, KML), Hietograma CSV (HEC-HMS / SWMM) y reporte tabular texto."""

from __future__ import annotations

import json
from typing import Any
from xml.sax.saxutils import escape


def generate_geojson(analysis: dict[str, Any], route_coords: list[tuple[float, float]] | None = None) -> str:
    features: list[dict[str, Any]] = []
    for st in analysis.get("stations", []):
        if st.get("latitud") is None or st.get("longitud") is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(st["longitud"]), float(st["latitud"]), float(st.get("altitud") or 0.0)],
            },
            "properties": {
                "codigo": st.get("codigo"),
                "nombre": st.get("nombre"),
                "categoria": st.get("categoria_codigo"),
                "municipio": st.get("municipio_nombre"),
                "departamento": st.get("departamento_nombre"),
                "altitud_m": st.get("altitud"),
                "estado": st.get("estado"),
                "peso_normalizado": st.get("weight_norm"),
                "variables": st.get("available_vars", []),
            },
        })

    if route_coords and len(route_coords) >= 2:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[float(lon), float(lat)] for lat, lon in route_coords],
            },
            "properties": {"tipo": "Corredor de Proyecto", "nombre": analysis["project"]["name"]},
        })

    return json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2)


def generate_kml(analysis: dict[str, Any], route_coords: list[tuple[float, float]] | None = None) -> str:
    proj = analysis["project"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
        f"  <name>{escape(proj['name'])} — Estaciones Climáticas</name>",
        '  <Style id="stnStyle"><IconStyle><scale>1.0</scale><Icon><href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href></Icon></IconStyle></Style>',
        '  <Style id="routeStyle"><LineStyle><color>ff0055ff</color><width>3</width></LineStyle></Style>',
        "  <Folder>",
        "    <name>Estaciones Climáticas</name>",
    ]
    for st in analysis.get("stations", []):
        if st.get("latitud") is None or st.get("longitud") is None:
            continue
        desc = (
            f"Código: {st.get('codigo')}<br/>"
            f"Categoría: {st.get('categoria_nombre') or st.get('categoria_codigo')}<br/>"
            f"Municipio: {st.get('municipio_nombre')} ({st.get('departamento_nombre')})<br/>"
            f"Altitud: {st.get('altitud')} m<br/>"
            f"Peso: {st.get('weight_norm', 0)*100:.1f}%"
        )
        lines.extend([
            "    <Placemark>",
            f"      <name>{escape(str(st.get('codigo')))} - {escape(str(st.get('nombre')))}</name>",
            f"      <description>{escape(desc)}</description>",
            "      <styleUrl>#stnStyle</styleUrl>",
            f"      <Point><coordinates>{st['longitud']},{st['latitud']},{st.get('altitud') or 0}</coordinates></Point>",
            "    </Placemark>",
        ])
    lines.append("  </Folder>")

    if route_coords and len(route_coords) >= 2:
        coord_str = " ".join(f"{lon},{lat},0" for lat, lon in route_coords)
        lines.extend([
            "  <Placemark>",
            f"    <name>Corredor: {escape(proj['name'])}</name>",
            "    <styleUrl>#routeStyle</styleUrl>",
            f"    <LineString><tessellate>1</tessellate><coordinates>{coord_str}</coordinates></LineString>",
            "  </Placemark>",
        ])
    lines.extend(["</Document>", "</kml>"])
    return "\n".join(lines)


def generate_hyetograph_csv(analysis: dict[str, Any]) -> str:
    """Exporta el hietograma de Bloques Alternos en CSV listo para EPA SWMM / HEC-HMS."""
    idf = analysis.get("hydrology_idf", {})
    hyet = idf.get("hyetograph", [])
    lines = [
        f"# HidroClima Studio - Hietograma de Diseño (Bloques Alternos)",
        f"# Proyecto: {analysis['project']['name']} | Metodo IDF: {idf.get('idf_params', {}).get('method_label', '')} | Tr={idf.get('hyetograph_tr', 10)} anos",
        "Bloque,Intervalo_min,Tiempo_Fin_min,Lamina_mm,Intensidad_mm_h,Lamina_Acumulada_mm",
    ]
    for r in hyet:
        lines.append(f"{r['step']},{r['time_min']},{r['time_end_min']},{r['depth_mm']},{r['intensity_mmh']},{r['cum_depth_mm']}")
    return "\r\n".join(lines)


def generate_resultado_txt(analysis: dict[str, Any]) -> str:
    """Genera reporte de texto estructurado con resumen climatológico, balance e IDF."""
    proj = analysis["project"]
    summ = analysis["summary"]
    pav = analysis["pavement"]
    cls = analysis.get("classifications", {})
    idf = analysis.get("hydrology_idf", {})

    lines = [
        "==================================================================================================",
        "  HIDROCLIMA STUDIO — REPORTE DE ANÁLISIS HIDROMETEOROLÓGICO Y CLIMÁTICO",
        "==================================================================================================",
        f"  Proyecto      : {proj['name']}",
        f"  Descripción   : {proj.get('description', '')}",
        f"  Ubicación     : {proj.get('location', '')}",
        f"  Periodo       : {proj['actual_year_min']} - {proj['actual_year_max']}",
        f"  Método ETP    : {proj['etp_method_label']}",
        f"  Reserva Suelo : {proj['soil_max_reserve_mm']:.1f} mm  |  Nivel Freático: {proj['water_table_m']:.2f} m",
        f"  Coord. Prom.  : Lat {proj['avg_lat']:.5f}°  Lon {proj['avg_lon']:.5f}°  Alt {proj['avg_alt']:.1f} m",
        "--------------------------------------------------------------------------------------------------",
        "  CLASIFICACIONES CLIMÁTICAS:",
        f"  Caldas-Lang            : {cls.get('caldas_lang', {}).get('label', 'N/D')} (Factor Lang P/T = {cls.get('caldas_lang', {}).get('lang_factor', 'N/D')})",
        f"  Zona de Vida Holdridge : {cls.get('holdridge', {}).get('life_zone', 'N/D')} (EPT = {cls.get('holdridge', {}).get('ept_ratio', 'N/D')})",
        f"  Köppen-Geiger          : {cls.get('koppen_geiger', {}).get('label', 'N/D')}",
        f"  Índice Aridez ENA-IDEAM: {cls.get('ena_aridity', {}).get('ia', 'N/D')} -> {cls.get('ena_aridity', {}).get('category', 'N/D')}",
        "--------------------------------------------------------------------------------------------------",
        "  ESTACIONES CLIMÁTICAS DE ANÁLISIS:",
        "  Código      Nombre                           Cat   Peso(%)   Variables",
    ]
    for st in analysis.get("stations", []):
        vars_s = " ".join(str(v) for v in st.get("available_vars", []))
        lines.append(
            f"  {str(st.get('codigo','')):<11} {str(st.get('nombre',''))[:32]:<32} {str(st.get('categoria_codigo','')):<5} "
            f"{st.get('weight_norm',0)*100:6.2f}%   {vars_s}"
        )
    lines.extend([
        "--------------------------------------------------------------------------------------------------",
        "  Mes          T.Med(°C)  Precip(mm)   I.Calor  H.Sol(h)  ETP(mm)  Almac(mm)  Exceso(mm)  Déficit(mm)",
    ])
    for r in analysis.get("monthly_summary", []):
        lines.append(
            f"  {r['month']:<11} {r['temp_mean_c']:9.2f} {r['precip_mm']:10.2f} {r['heat_index']:9.2f} "
            f"{r['daylight_h']:8.2f} {r['etp_active_mm']:8.2f} {r['storage_mm']:10.2f} {r['excess_mm']:11.2f} {r['deficit_mm']:12.2f}"
        )
    lines.extend([
        "--------------------------------------------------------------------------------------------------",
        f"  Suma Anual  : P = {summ['annual_precip_mm']:.2f} mm | ETP = {summ['annual_etp_mm']:.2f} mm | Exceso = {summ['annual_excess_mm']:.2f} mm | Déficit = {summ['annual_deficit_mm']:.2f} mm",
        f"  Índice Humedad (Ih)    : {summ['humidity_index_pct']:.2f} %   |   Índice Aridez (Ia) : {summ['aridity_index_pct']:.2f} %",
        f"  Índice de Thornthwaite : {summ['thornthwaite_index_pct']:.2f} %  -> {summ['humidity_class']} ({summ['humidity_description']})",
        f"  Clasificación Térmica  : {summ['mean_annual_temp_c']:.2f} °C -> {summ['thermal_class']}",
        f"  Temp. Máx 7 días cons. : Tmax={pav.get('max_7day_tmax_c') or 'N/D'} °C | Tmean={pav.get('max_7day_tmean_c') or 'N/D'} °C | Superpave={pav.get('recommended_pg_grade')}",
    ])
    if idf.get("available"):
        lines.append(f"  Hidrología IDF         : {idf['idf_params'].get('method_label')} | {idf['idf_params'].get('formula')} | Mejor ajuste P24h: {idf.get('best_distribution')}")
    lines.append("==================================================================================================")
    return "\r\n".join(lines)
