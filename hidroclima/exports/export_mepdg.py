"""Exportadores compatibles con AASHTOWare Pavement ME Design / MEPDG (.xml ClimateObject y _mepdg.txt)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape


def generate_mepdg_xml(analysis: dict[str, Any]) -> str:
    """
    Genera archivo XML <ClimateObject> compatible con el esquema observado en CLIMA / MEPDG,
    incluyendo estación climática, nivel freático, promedios anuales y registros diarios.
    """
    proj = analysis["project"]
    summ = analysis["summary"]
    stns = analysis.get("stations", [])
    primary = stns[0] if stns else {}
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    first_year = proj.get("actual_year_min", 2015)

    # Humedad media anual y temperatura media anual
    rh_vals = [r["rh_pct"] for r in analysis.get("monthly_summary", []) if r.get("rh_pct") is not None]
    avg_rh = sum(rh_vals) / len(rh_vals) if rh_vals else 75.0

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<ClimateObject xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">',
        "  <ErrorStatus>0</ErrorStatus>",
        "  <ErrorMessage />",
        f"  <displayName>{escape(proj['name'])}</displayName>",
        f"  <description>{escape(proj.get('description') or 'Generado por HidroClima Studio')}</description>",
        "  <author>HidroClima Studio</author>",
        f"  <authorDate>{now_iso}</authorDate>",
        "  <approver />",
        f"  <approverDate>{now_iso}</approverDate>",
        f"  <state>{escape(primary.get('departamento_nombre') or 'Colombia')}</state>",
        "  <district />",
        f"  <county>{escape(primary.get('municipio_nombre') or '')}</county>",
        f"  <highway>{escape(proj.get('location') or '')}</highway>",
        "  <direction />",
        "  <fromStation />",
        "  <toStation />",
        "  <laneNumber>0</laneNumber>",
        "  <user1 />",
        "  <user2 />",
        "  <user3 />",
        "  <objectTypeId>0</objectTypeId>",
        "  <objectId>-1</objectId>",
        "  <revisionNumber>0</revisionNumber>",
        "  <hasStochastic>false</hasStochastic>",
        "  <hasLocked>false</hasLocked>",
        "  <isLibrary>false</isLibrary>",
        "  <status>2</status>",
        "  <isUSCustomary>false</isUSCustomary>",
        "  <propertyLocked />",
        "  <stochastic />",
        "  <climateData>",
        "    <ErrorStatus>0</ErrorStatus>",
        "    <ErrorMessage />",
        f"    <displayName>{escape(proj['name'])}</displayName>",
        "    <description />",
        "    <author>HidroClima Studio</author>",
        f"    <authorDate>{now_iso}</authorDate>",
        "    <approver />",
        f"    <approverDate>{now_iso}</approverDate>",
        f"    <state>{escape(primary.get('departamento_nombre') or 'Colombia')}</state>",
        "    <district />",
        f"    <county>{escape(primary.get('municipio_nombre') or '')}</county>",
        "    <highway />",
        "    <direction />",
        "    <fromStation />",
        "    <toStation />",
        "    <laneNumber>0</laneNumber>",
        "    <user1 />",
        "    <user2 />",
        "    <user3 />",
        "    <objectTypeId>0</objectTypeId>",
        "    <objectId>-1</objectId>",
        "    <revisionNumber>0</revisionNumber>",
        "    <hasStochastic>false</hasStochastic>",
        "    <hasLocked>false</hasLocked>",
        "    <isLibrary>false</isLibrary>",
        "    <status>1</status>",
        "    <isUSCustomary>false</isUSCustomary>",
        "    <propertyLocked />",
        "    <stochastic />",
        f"    <humidity>{avg_rh:.4f}</humidity>",
        f"    <airTemp>{summ['mean_annual_temp_c']:.4f}</airTemp>",
        f"    <annualRain>{summ['annual_precip_mm']:.4f}</annualRain>",
        f"    <annualTemp>{summ['mean_annual_temp_c']:.4f}</annualTemp>",
        f"    <DaysFreezing>{analysis.get('pavement', {}).get('freezing_days_total', 0)}</DaysFreezing>",
        f"    <DaysWet>{analysis.get('pavement', {}).get('wet_days_total', 0)}</DaysWet>",
        "    <freezeThawDays>0</freezeThawDays>",
        f"    <annualWaterTable>{proj['water_table_m']:.2f}</annualWaterTable>",
        "    <springWater>0</springWater>",
        "    <summerWater>0</summerWater>",
        "    <fallWater>0</fallWater>",
        "    <winterWater>0</winterWater>",
        f"    <latitude>{proj['avg_lat']:.6f}</latitude>",
        f"    <longitude>{proj['avg_lon']:.6f}</longitude>",
        f"    <elevation>{proj['avg_alt']:.1f}</elevation>",
        "    <isSeasonalWater>false</isSeasonalWater>",
        "  </climateData>",
        "  <climateStation>",
    ]

    for st in stns:
        lines.extend([
            "    <ClimateStation>",
            f"      <distance>{st.get('distance_km', 0)}</distance>",
            f"      <stationId>{escape(str(st.get('codigo', '')))}</stationId>",
            f"      <city>{escape(st.get('municipio_nombre') or '')}</city>",
            f"      <state>{escape(st.get('departamento_nombre') or '')}</state>",
            "      <Country>Colombia</Country>",
            f"      <Latitude>{st.get('latitud', proj['avg_lat'])}</Latitude>",
            f"      <Longitude>{st.get('longitud', proj['avg_lon'])}</Longitude>",
            f"      <Altitude>{st.get('altitud', proj['avg_alt'])}</Altitude>",
            f"      <firstRecordDate>{first_year}-01-01T00:00:00</firstRecordDate>",
            "      <MissingComplete>C</MissingComplete>",
            "    </ClimateStation>",
        ])

    lines.extend([
        "  </climateStation>",
        "  <climateRecord>",
    ])

    for d in analysis.get("daily_climatology", []):
        p = d.get("precip_mm", 0.0) or 0.0
        tm = d.get("temp_mean_c")
        if tm is None:
            tm = summ["mean_annual_temp_c"]
        tx = d.get("temp_max_c")
        if tx is None:
            tx = tm + 4.0
        tn = d.get("temp_min_c")
        if tn is None:
            tn = tm - 4.0
        rh = d.get("rh_pct")
        if rh is None:
            rh = avg_rh
        ws = d.get("wind_ms")
        if ws is None:
            ws = 2.0
        sun_pct = min(100.0, max(0.0, 100.0 * (d.get("sunshine_h") or 5.0) / max(1.0, d.get("daylight_h") or 12.0)))
        lines.extend([
            "    <ClimateRecord>",
            f"      <dailyRecord>{d['month']:02d}/{d['day']:02d} Tmean={tm:.2f} Tmax={tx:.2f} Tmin={tn:.2f} Precip={p:.2f} Wind={ws:.2f} RH={rh:.1f} SunPct={sun_pct:.1f}</dailyRecord>",
            "    </ClimateRecord>",
        ])

    lines.extend([
        "  </climateRecord>",
        "</ClimateObject>",
    ])
    return "\n".join(lines)


def generate_mepdg_txt(analysis: dict[str, Any]) -> str:
    """Genera tabla _mepdg.txt tabulada con las variables climáticas diarias requeridas por MEPDG."""
    proj = analysis["project"]
    summ = analysis["summary"]
    lines = [
        f"# ARCHIVO PARA MEPDG - HidroClima Studio",
        f"# Proyecto: {proj['name']} | Lat: {proj['avg_lat']:.5f} | Lon: {proj['avg_lon']:.5f} | Alt(m): {proj['avg_alt']:.1f} | Nivel Freatico(m): {proj['water_table_m']:.2f}",
        f"# Indice Thornthwaite (%): {summ['thornthwaite_index_pct']:.2f} | Temperatura Media (C): {summ['mean_annual_temp_c']:.2f}",
        "Mes\tDia\tPrecipitacion_mm\tTempMedia_C\tTempMax_C\tTempMin_C\tHumedadRel_%\tVelViento_m_s\tBrilloSolar_h\tRadSolar_MJ_m2",
    ]
    for r in analysis.get("daily_climatology", []):
        tm = r["temp_mean_c"] if r["temp_mean_c"] is not None else summ["mean_annual_temp_c"]
        tx = f"{r['temp_max_c']:.2f}" if r["temp_max_c"] is not None else f"{tm + 4.0:.2f}"
        tn = f"{r['temp_min_c']:.2f}" if r["temp_min_c"] is not None else f"{tm - 4.0:.2f}"
        rh = f"{r['rh_pct']:.1f}" if r["rh_pct"] is not None else "75.0"
        ws = f"{r['wind_ms']:.2f}" if r["wind_ms"] is not None else "2.00"
        sun = f"{r['sunshine_h']:.2f}" if r["sunshine_h"] is not None else "4.50"
        rs = f"{r['solar_rad_mj']:.2f}" if r["solar_rad_mj"] is not None else "15.00"
        lines.append(f"{r['month']}\t{r['day']}\t{r['precip_mm']:.2f}\t{tm:.2f}\t{tx}\t{tn}\t{rh}\t{ws}\t{sun}\t{rs}")
    return "\r\n".join(lines)
