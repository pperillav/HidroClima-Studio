"""Exportación de Informe Técnico Hidrometeorológico editable en formato Word (.docx)."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

from hidroclima.exports.charts_mpl import (
    render_annual_trends_png,
    render_climograph_png,
    render_hyetograph_png,
    render_idf_curves_png,
    render_sgc_thresholds_png,
    render_spei_drought_png,
    render_water_balance_png,
)


def _set_cell_margins(cell, top=60, bottom=60, left=90, right=90) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def _add_styled_table(
    doc: Document,
    headers: list[str],
    rows: list[list[Any]],
    col_widths_in: list[float] | None = None,
    right_align_from: int | None = None,
) -> None:
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    hdr_row = tbl.rows[0]
    trPr = hdr_row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:tblHeader"))
    trPr.append(OxmlElement("w:cantSplit"))

    for idx, h in enumerate(headers):
        cell = hdr_row.cells[idx]
        if col_widths_in and idx < len(col_widths_in):
            cell.width = Inches(col_widths_in[idx])
        cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="0F172A"/>'))
        _set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        run = p.add_run(str(h))
        run.bold = True
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, row_vals in enumerate(rows):
        row = tbl.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        bg = "F8FAFC" if r_idx % 2 == 1 else None
        for idx, val in enumerate(row_vals):
            cell = row.cells[idx]
            if col_widths_in and idx < len(col_widths_in):
                cell.width = Inches(col_widths_in[idx])
            if bg:
                cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg}"/>'))
            _set_cell_margins(cell, top=50, bottom=50, left=80, right=80)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            if right_align_from is not None and idx >= right_align_from:
                p.alignment = 2  # RIGHT
            run = p.add_run(str(val if val is not None else "-"))
            run.font.size = Pt(8.5)


def generate_docx_report(analysis: dict[str, Any]) -> bytes:
    """Genera documento Word .docx editable con tablas y gráficas científicas de alta resolución."""
    proj = analysis["project"]
    summ = analysis["summary"]
    pav = analysis["pavement"]
    idf = analysis["hydrology_idf"]
    cls = analysis.get("classifications", {})
    qual = analysis.get("quality", {})
    etccdi = qual.get("etccdi", {})

    doc = Document()
    for sec in doc.sections:
        sec.top_margin = Inches(0.65)
        sec.bottom_margin = Inches(0.65)
        sec.left_margin = Inches(0.65)
        sec.right_margin = Inches(0.65)

    title = doc.add_heading(f"Informe Técnico Hidrometeorológico — {proj['name']}", level=0)
    title.runs[0].font.color.rgb = RGBColor(14, 116, 144)

    sub = doc.add_paragraph()
    sub.add_run(
        f"HidroClima Studio v1.0.0  |  Ubicación: {proj.get('location') or 'Colombia'}  |  "
        f"Periodo: {proj['actual_year_min']}–{proj['actual_year_max']}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ).italic = True
    if proj.get("description"):
        doc.add_paragraph(proj["description"])

    doc.add_heading("1. Parámetros y Síntesis Ejecutiva", level=1)
    tmap_reg = pav.get("invias_pavement_region", {})
    pma_val = pav.get("pma_mm", summ["annual_precip_mm"])
    kpi_rows = [
        ["Coordenada Centroide / Altitud", f"{proj['avg_lat']:.5f}°, {proj['avg_lon']:.5f}°  |  {proj['avg_alt']:.1f} m s.n.m."],
        ["Método de Evapotranspiración", proj["etp_method_label"]],
        ["Reserva Máxima de Agua en el Suelo / Nivel Freático", f"{proj['soil_max_reserve_mm']:.1f} mm  |  {proj['water_table_m']:.2f} m"],
        ["1. Temperatura Media Anual Ponderada (TMAP)", f"{pav.get('tmap_c') or 'N/D'} °C (metodología Shell Carta W)"],
        ["2. Precipitación Media Anual (PMA)", f"{pma_val:,.1f} mm/año"],
        ["Región Climática Pavimentos (INVIAS)", f"Región {tmap_reg.get('code', '-')} — {tmap_reg.get('name', '-')} ({tmap_reg.get('criteria', '')})"],
        ["ETP / ETR / Exceso / Déficit Anual", f"ETP: {summ['annual_etp_mm']:,.1f} mm | ETR: {summ['annual_etr_mm']:,.1f} mm | Exc: {summ['annual_excess_mm']:,.1f} mm | Def: {summ['annual_deficit_mm']:,.1f} mm"],
        ["Temperatura Media Anual", f"{summ['mean_annual_temp_c']:.2f} °C ({summ['thermal_class']})"],
        ["Temperatura 7 días más calientes / Superpave PG", f"Tmax 7d: {pav.get('max_7day_tmax_c') or 'N/D'} °C  |  {pav.get('recommended_pg_grade', 'N/D')} (98% a 20 mm)"],
    ]
    _add_styled_table(doc, ["Indicador Técnico", "Valor Calculado"], kpi_rows, [2.8, 4.4])

    doc.add_heading("2. Clasificaciones Climáticas Oficiales (EIA / ANLA / POMCA / ENA)", level=1)
    cl = cls.get("caldas_lang", {})
    ho = cls.get("holdridge", {})
    ko = cls.get("koppen_geiger", {})
    ena = cls.get("ena_aridity", {})
    cls_rows = [
        ["Caldas-Lang (IDEAM)", cl.get("label", "N/D"), f"Piso térmico: {cl.get('piso_termico', '-')} | Factor de Lang P/T = {cl.get('lang_factor', '-')}"],
        ["Zonas de Vida Holdridge", ho.get("life_zone", "N/D"), f"Biotemperatura = {ho.get('biotemp_c', '-')} °C | ETP Holdridge = {ho.get('etp_holdridge_mm', '-')} mm | EPT = {ho.get('ept_ratio', '-')}"],
        ["Köppen-Geiger", ko.get("label", "N/D"), f"Código climático {ko.get('code', '-')}"],
        ["Thornthwaite (1948)", f"{summ['thornthwaite_index_pct']:.2f}% ({summ['humidity_class']})", summ["humidity_description"]],
        ["Índice de Aridez (ENA-IDEAM)", f"IA = {ena.get('ia', '-')} ({ena.get('category', 'N/D')})", ena.get("description", "")],
    ]
    _add_styled_table(doc, ["Sistema", "Clasificación", "Parámetros y Criterio"], cls_rows, [1.7, 2.3, 3.2])

    doc.add_heading("3. Estaciones Climáticas y Ponderación Espacial", level=1)
    stn_rows = [
        [
            s.get("codigo", ""), s.get("nombre", ""), s.get("categoria_codigo", ""), s.get("municipio_nombre", ""),
            f"{s.get('latitud', 0):.4f}" if s.get("latitud") is not None else "-",
            f"{s.get('longitud', 0):.4f}" if s.get("longitud") is not None else "-",
            f"{s.get('altitud', 0):.0f}" if s.get("altitud") is not None else "-",
            f"{s.get('weight_norm', 0)*100:.1f}%",
        ]
        for s in analysis.get("stations", [])
    ]
    _add_styled_table(
        doc,
        ["Código", "Estación", "Cat.", "Municipio", "Lat", "Lon", "Alt(m)", "Peso"],
        stn_rows,
        [0.8, 1.9, 0.45, 1.35, 0.75, 0.8, 0.55, 0.6],
        right_align_from=4,
    )
    doc.add_paragraph()
    doc.add_picture(io.BytesIO(render_climograph_png(analysis)), width=Inches(6.8))

    doc.add_heading("4. Promedios Mensuales y Balance Hídrico", level=1)
    m_rows = [
        [
            r["month"], f"{r['precip_mm']:.1f}", f"{r['temp_mean_c']:.2f}",
            f"{r['temp_max_c']:.1f}" if r["temp_max_c"] is not None else "-",
            f"{r['temp_min_c']:.1f}" if r["temp_min_c"] is not None else "-",
            f"{r['rh_pct']:.1f}" if r["rh_pct"] is not None else "-",
            f"{r['solar_rad_mj']:.2f}" if r["solar_rad_mj"] is not None else "-",
            f"{r['etp_active_mm']:.1f}", f"{r['storage_mm']:.1f}", f"{r['excess_mm']:.1f}", f"{r['deficit_mm']:.1f}",
        ]
        for r in analysis.get("monthly_summary", [])
    ]
    _add_styled_table(
        doc,
        ["Mes", "P (mm)", "Tm (°C)", "Tx (°C)", "Tn (°C)", "HR (%)", "Rs (MJ/m²)", "ETP", "Almac", "Exceso", "Déficit"],
        m_rows,
        [0.9, 0.6, 0.6, 0.55, 0.55, 0.55, 0.75, 0.65, 0.65, 0.7, 0.7],
        right_align_from=1,
    )
    doc.add_paragraph()
    doc.add_picture(io.BytesIO(render_water_balance_png(analysis)), width=Inches(6.8))

    doc.add_heading("5. Homogeneidad (Pettitt), Tendencias (Mann-Kendall) e Índices Extremos ETCCDI", level=1)
    tp = qual.get("trends", {}).get("precip_annual", {})
    tt = qual.get("trends", {}).get("temp_mean_annual", {})
    hp = qual.get("homogeneity", {}).get("precip_annual", {})
    ht = qual.get("homogeneity", {}).get("temp_mean_annual", {})
    q_rows = [
        ["Tendencia Precipitación (Mann-Kendall)", tp.get("trend", "N/D"), f"Sen = {tp.get('sen_slope_per_decade', '-')} mm/década (p={tp.get('p_value', '-')})"],
        ["Homogeneidad Precipitación (Pettitt)", hp.get("status", "N/D"), f"K = {hp.get('k_stat', '-')} (p={hp.get('p_value', '-')})"],
        ["Tendencia Temperatura (Mann-Kendall)", tt.get("trend", "N/D"), f"Sen = {tt.get('sen_slope_per_decade', '-')} °C/década (p={tt.get('p_value', '-')})"],
        ["Homogeneidad Temperatura (Pettitt)", ht.get("status", "N/D"), f"K = {ht.get('k_stat', '-')} (p={ht.get('p_value', '-')})"],
        ["Índices Extremos ETCCDI", f"Rx1day={etccdi.get('rx1day_mm', '-')} mm | Rx5day={etccdi.get('rx5day_mm', '-')} mm", f"CDD={etccdi.get('cdd_max_dry_days', '-')} d | CWD={etccdi.get('cwd_max_wet_days', '-')} d | R20mm={etccdi.get('r20mm_days_yr', '-')} d/año"],
    ]
    _add_styled_table(doc, ["Análisis", "Resultado", "Estadístico / Valores"], q_rows, [2.1, 2.3, 2.8])
    doc.add_paragraph()
    doc.add_picture(io.BytesIO(render_annual_trends_png(analysis)), width=Inches(6.8))

    if idf.get("available"):
        p_idf = idf["idf_params"]
        doc.add_heading(f"6. Hidrología Extrema, Curvas IDF ({p_idf['method_label']}) y Normativa RAS / INVIAS", level=1)
        doc.add_paragraph(
            f"Precipitación máxima 24h multianual M = {idf['m_pmax_24h_mean_mm']:.2f} mm (σ = {idf['pmax_24h_std_mm']:.2f} mm). "
            f"Mejor ajuste Kolmogorov-Smirnov: {idf.get('best_distribution')}. Ecuación IDF: {p_idf['formula']}."
        )
        trs = [2, 3, 5, 10, 20, 25, 50, 100]
        dist_rows = []
        for dn, dobj in idf.get("distributions", {}).items():
            qmap = {q["tr"]: q["p24h_mm"] for q in dobj["quantiles"]}
            dist_rows.append([dn + (" ★" if dn == idf.get("best_distribution") else ""), f"{dobj['ks_d']:.4f}", f"{dobj['r2']:.4f}"] + [f"{qmap.get(t, 0):.1f}" for t in trs])
        _add_styled_table(
            doc,
            ["Distribución", "K-S D", "R²"] + [f"Tr{t}" for t in trs],
            dist_rows,
            [1.45, 0.65, 0.58] + [0.56] * len(trs),
            right_align_from=1,
        )
        doc.add_paragraph()

        idf_rows = [
            [row["duration_min"]] + [f"{row.get(f'tr_{t}', 0):.1f}" for t in trs]
            for row in idf["idf_table"]
            if row["duration_min"] in (5, 10, 15, 20, 30, 45, 60, 90, 120, 150, 180)
        ]
        _add_styled_table(
            doc,
            ["Dur (min)"] + [f"Tr {t}" for t in trs],
            idf_rows,
            [0.8] + [0.8] * len(trs),
            right_align_from=1,
        )
        doc.add_paragraph()
        doc.add_picture(io.BytesIO(render_idf_curves_png(analysis)), width=Inches(6.9))
        doc.add_picture(io.BytesIO(render_hyetograph_png(analysis)), width=Inches(6.7))

        norm_rows = [
            [n["norma"], n["obra"], f"{n['tr_rec']} años", f"{n.get('i_tc15_mmh') or '-'} mm/h", f"{n.get('i_tc30_mmh') or '-'} mm/h"]
            for n in idf.get("normative_return_periods", [])
        ]
        _add_styled_table(
            doc,
            ["Norma", "Obra Hidráulica / Vial", "Tr Rec.", "i (tc=15m)", "i (tc=30m)"],
            norm_rows,
            [1.3, 3.2, 0.7, 1.0, 1.0],
            right_align_from=2,
        )

    sgc = analysis.get("geohazards_sgc", {})
    ero = analysis.get("erosivity", {})
    drg = analysis.get("drought", {})
    wshed = analysis.get("watershed", {})
    if sgc.get("available") or ero.get("available") or drg.get("available") or wshed.get("available"):
        doc.add_heading("7. Geotecnia SGC (Umbrales Detonantes), Erosividad RUSLE, Sequías SPEI y Cuenca INVIAS", level=1)
        rows_g = []
        if sgc.get("available"):
            inf = sgc.get("infiltration_balance", {})
            rows_g.append(["Umbral Detonante SGC", sgc.get("threshold_eq", ""), f"{sgc.get('exceedance_days', 0)} días ({sgc.get('exceedance_rate_pct', 0)}%) / {sgc.get('episodes_count', 0)} episodios"])
            rows_g.append(["Balance Infiltración SCS", f"CN I/II/III: {inf.get('cn_i')}/{inf.get('cn_ii')}/{inf.get('cn_iii')}", f"Infilt: {inf.get('mean_annual_infiltration_mm')} mm/a | Escorr: {inf.get('mean_annual_runoff_mm')} mm/a"])
        if ero.get("available"):
            rows_g.append(["Erosividad RUSLE (ANLA)", f"R = {ero.get('r_factor_mfi')} {ero.get('unit')}", f"MFI = {ero.get('mfi_arnoldus_mm')} mm ({ero.get('aggressiveness_class')}) | PCI = {ero.get('pci_oliver_pct')}%"])
        if drg.get("summary"):
            ds = drg["summary"]
            rows_g.append(["Sequías SPEI-3 (UNGRD)", f"Mín = {ds.get('min_spei3')} ({ds.get('min_spei3_date')})", f"≤ -1.0: {ds.get('drought_moderate_pct')}% | ≤ -1.5: {ds.get('drought_severe_pct')}% meses"])
        if wshed.get("available"):
            rows_g.append(["Cuenca INVIAS / SCS-CN", f"A={wshed['area_km2']} km², L={wshed['length_m']} m, S={wshed['slope_pct']}%", f"tc Kirpich={wshed['tc_kirpich_min']} min | tc Témez={wshed['tc_temez_min']} min"])
        if rows_g:
            _add_styled_table(doc, ["Módulo / Análisis", "Resultado Principal", "Detalle Técnico"], rows_g, [1.8, 2.3, 3.1])

        if wshed.get("available") and wshed.get("design_rows"):
            doc.add_paragraph()
            w_rows = [
                [f"{r['tr']} a", f"{r['i_tc_mmh']:.1f}", f"{r['q_rational_m3s']:.3f}", f"{r['p_storm_mm']:.1f}", f"{r['qe_runoff_mm']:.1f}", f"{r['infiltration_mm']:.1f}", f"{r['q_scs_m3s']:.3f}"]
                for r in wshed["design_rows"]
            ]
            _add_styled_table(
                doc,
                ["Tr", "I(tc) mm/h", "Q Racional m³/s", "P Torm. mm", "Qe SCS mm", "Infilt mm", "Q SCS m³/s"],
                w_rows,
                [0.7, 1.0, 1.15, 1.05, 1.1, 1.1, 1.1],
                right_align_from=1,
            )

        if sgc.get("available"):
            doc.add_paragraph()
            doc.add_picture(io.BytesIO(render_sgc_thresholds_png(analysis)), width=Inches(6.9))
        if drg.get("available") or ero.get("available"):
            doc.add_paragraph()
            doc.add_picture(io.BytesIO(render_spei_drought_png(analysis)), width=Inches(6.9))

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()
