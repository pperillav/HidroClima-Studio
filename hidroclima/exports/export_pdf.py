"""Exportación de Informe Técnico Hidrometeorológico completo en formato PDF sin desbordamiento de texto."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
from fpdf import FPDF
from fpdf.enums import Align, TableBordersLayout
from fpdf.fonts import FontFace

from hidroclima.config import STATIC_DIR
from hidroclima.exports.charts_mpl import (
    render_annual_trends_png,
    render_climograph_png,
    render_hyetograph_png,
    render_idf_curves_png,
    render_sgc_thresholds_png,
    render_spei_drought_png,
    render_water_balance_png,
)


def _find_unicode_fonts() -> tuple[str | None, str | None]:
    mpl_ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    reg = mpl_ttf / "DejaVuSans.ttf"
    bold = mpl_ttf / "DejaVuSans-Bold.ttf"
    if reg.exists() and bold.exists():
        return str(reg), str(bold)
    win_reg = Path(r"C:\Windows\Fonts\arial.ttf")
    win_bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if win_reg.exists() and win_bold.exists():
        return str(win_reg), str(win_bold)
    return None, None


class TechnicalReportPDF(FPDF):
    def __init__(self, project_name: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.project_name = project_name
        reg, bold = _find_unicode_fonts()
        if reg and bold:
            self.add_font("UniFont", "", reg)
            self.add_font("UniFont", "B", bold)
            self.font_family_name = "UniFont"
        else:
            self.font_family_name = "Helvetica"
        self.set_auto_page_break(auto=True, margin=16)

    def _s(self, text: Any) -> str:
        txt = str(text if text is not None else "")
        if self.font_family_name == "Helvetica":
            return txt.encode("latin-1", errors="replace").decode("latin-1")
        return txt

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font(self.font_family_name, "B", 8.2)
        self.set_text_color(71, 85, 105)
        self.cell(0, 6, self._s(f"HidroClima Studio  |  Informe Técnico: {self.project_name}"[:95]), align="L")
        self.ln(4.5)
        self.set_draw_color(203, 213, 225)
        self.line(12, self.get_y(), 198, self.get_y())
        self.ln(3.5)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_font(self.font_family_name, "", 7.8)
        self.set_text_color(100, 116, 139)
        self.cell(
            0,
            8,
            self._s(f"Generado por HidroClima Studio v1.0.0  •  {datetime.now().strftime('%Y-%m-%d %H:%M')}  •  Página {self.page_no()}/{{nb}}"),
            align="C",
        )

    def _fmt(self, val: Any, dec: int = 2, suffix: str = "") -> str:
        if val is None:
            return "-"
        if isinstance(val, (int, float)):
            return f"{val:.{dec}f}{suffix}"
        return f"{val}{suffix}"

    def section_title(self, title: str) -> None:
        self.ln(2.5)
        self.set_fill_color(15, 23, 42)
        self.set_text_color(255, 255, 255)
        self.set_font(self.font_family_name, "B", 9.6)
        self.multi_cell(0, 6.6, self._s(f"  {title}"), fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_fill_color(255, 255, 255)
        self.set_text_color(15, 23, 42)
        self.ln(1.8)

    def render_kv_table(self, pairs: list[tuple[str, str]]) -> None:
        """Renderiza tabla clave-valor en 2 columnas pareadas con ajuste automático de línea (cero desbordes)."""
        self.set_font(self.font_family_name, "", 7.9)
        self.set_draw_color(203, 213, 225)
        key_style = FontFace(emphasis="BOLD", color=(15, 23, 42), fill_color=(241, 245, 249), size_pt=7.8)
        val_style = FontFace(color=(15, 23, 42), fill_color=(255, 255, 255), size_pt=7.9)

        with self.table(
            col_widths=(36, 57, 36, 57),
            width=186,
            line_height=4.4,
            padding=(1.2, 1.8),
            borders_layout=TableBordersLayout.ALL,
            first_row_as_headings=False,
        ) as table:
            for i in range(0, len(pairs), 2):
                p1 = pairs[i]
                p2 = pairs[i + 1] if i + 1 < len(pairs) else ("", "")
                row = table.row()
                row.cell(self._s(p1[0]), style=key_style, align=Align.L)
                row.cell(self._s(p1[1]), style=val_style, align=Align.L)
                row.cell(self._s(p2[0]), style=key_style, align=Align.L)
                row.cell(self._s(p2[1]), style=val_style, align=Align.L)
        self.ln(1.5)

    def render_data_table(
        self,
        headers: list[str],
        rows: list[list[Any]],
        col_widths: tuple[int | float, ...] | list[int | float],
        col_aligns: list[Align] | None = None,
        font_size: float = 7.4,
        bold_last_row: bool = False,
    ) -> None:
        """Tabla estructurada FPDF2 con ajuste automático de texto multi-línea y repetición de encabezados."""
        self.set_font(self.font_family_name, "", font_size)
        self.set_draw_color(203, 213, 225)
        hdr_style = FontFace(emphasis="BOLD", color=(15, 23, 42), fill_color=(226, 232, 240), size_pt=font_size)
        even_style = FontFace(color=(15, 23, 42), fill_color=(255, 255, 255), size_pt=font_size)
        zebra_style = FontFace(color=(15, 23, 42), fill_color=(248, 250, 252), size_pt=font_size)
        total_style = FontFace(emphasis="BOLD", color=(15, 23, 42), fill_color=(219, 234, 254), size_pt=font_size)

        with self.table(
            col_widths=col_widths,
            width=186,
            line_height=4.2,
            padding=(1.1, 1.4),
            borders_layout=TableBordersLayout.ALL,
            headings_style=hdr_style,
            text_align=col_aligns or Align.L,
            repeat_headings=1,
        ) as table:
            h_row = table.row(style=hdr_style)
            for idx, h in enumerate(headers):
                al = col_aligns[idx] if col_aligns and idx < len(col_aligns) else Align.C
                h_row.cell(self._s(h), align=al)

            n_rows = len(rows)
            for r_idx, r_vals in enumerate(rows):
                is_tot = bold_last_row and r_idx == n_rows - 1
                row_style = total_style if is_tot else (zebra_style if r_idx % 2 == 1 else even_style)
                row = table.row(style=row_style)
                for val in r_vals:
                    row.cell(self._s(val))
        self.ln(1.5)


def generate_pdf_report(analysis: dict[str, Any]) -> bytes:
    """Construye el PDF completo del informe técnico hidrometeorológico y normativo."""
    proj = analysis["project"]
    summ = analysis["summary"]
    pav = analysis["pavement"]
    idf = analysis["hydrology_idf"]
    cls = analysis.get("classifications", {})
    qual = analysis.get("quality", {})
    etccdi = qual.get("etccdi", {})

    pdf = TechnicalReportPDF(proj["name"])
    pdf.alias_nb_pages()
    pdf.set_margins(12, 12, 12)
    pdf.add_page()

    # Banner portada ejecutiva con logo institucional
    pdf.set_fill_color(14, 116, 144)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(pdf.font_family_name, "B", 14)
    pdf.multi_cell(0, 10, pdf._s("  INFORME TÉCNICO HIDROMETEOROLÓGICO Y CLIMÁTICO"), fill=True, new_x="LMARGIN", new_y="NEXT")
    logo_badge = STATIC_DIR / "logo_mark_light.png"
    if logo_badge.exists():
        pdf.image(str(logo_badge), x=186, y=13.2, w=8.2)
    pdf.set_fill_color(240, 249, 255)
    pdf.set_text_color(15, 23, 42)
    pdf.set_font(pdf.font_family_name, "B", 10)
    pdf.multi_cell(0, 6.8, pdf._s(f"  Proyecto: {proj['name']}"), fill=True, new_x="LMARGIN", new_y="NEXT")
    if proj.get("location") or proj.get("description"):
        pdf.set_font(pdf.font_family_name, "", 8.5)
        pdf.multi_cell(0, 5.5, pdf._s(f"  Ubicación: {proj.get('location') or 'Colombia'}  |  {proj.get('description') or ''}"), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)

    # 1. Parámetros y Síntesis
    pdf.section_title("1. SÍNTESIS CLIMÁTICA, TMAP, PMA Y PARÁMETROS DEL ESTUDIO")
    tmap_reg = pav.get("invias_pavement_region", {})
    pma_val = pav.get("pma_mm", summ["annual_precip_mm"])
    pdf.render_kv_table([
        ("Periodo Analizado", f"{proj['actual_year_min']}–{proj['actual_year_max']} ({proj['total_days_analyzed']:,} días)"),
        ("Método ETP", proj["etp_method_label"]),
        ("Coordenada / Altitud", f"{proj['avg_lat']:.4f}°, {proj['avg_lon']:.4f}° | {proj['avg_alt']:.0f} m s.n.m."),
        ("Reserva Máx. Suelo / NF", f"{proj['soil_max_reserve_mm']:.0f} mm | {proj['water_table_m']:.1f} m"),
        ("1. TMAP (Shell / INVIAS)", f"{pav.get('tmap_c') or 'N/D'} °C"),
        ("2. PMA (Precip. Media Anual)", f"{pma_val:,.1f} mm/año"),
        ("Región Pavimentos INVIAS", f"{tmap_reg.get('code', '-')} — {tmap_reg.get('name', '-')}"),
        ("Superpave PG / T7d máx", f"{pav['recommended_pg_grade']} (Tmax 7d: {pav.get('max_7day_tmax_c') or 'N/D'} °C)"),
        ("ETP / ETR Anual", f"{summ['annual_etp_mm']:,.1f} / {summ['annual_etr_mm']:,.1f} mm/año"),
        ("Exceso / Déficit Anual", f"{summ['annual_excess_mm']:,.1f} / {summ['annual_deficit_mm']:,.1f} mm/año"),
    ])

    # 2. Clasificaciones Climáticas Oficiales
    pdf.section_title("2. CLASIFICACIONES CLIMÁTICAS (EIA / ANLA / POMCA / ENA)")
    cl = cls.get("caldas_lang", {})
    ho = cls.get("holdridge", {})
    ko = cls.get("koppen_geiger", {})
    ena = cls.get("ena_aridity", {})
    pdf.render_data_table(
        headers=["Metodología / Norma", "Clasificación Obtenida", "Parámetros de Cálculo e Interpretación"],
        rows=[
            ["Caldas-Lang (IDEAM)", cl.get("label", "N/D"), f"Piso térmico: {cl.get('piso_termico', '-')} ({cl.get('altitud_ref', '-')}) · Factor Lang P/T = {cl.get('lang_factor', '-')}"],
            ["Zonas de Vida Holdridge", ho.get("life_zone", "N/D"), f"Biotemp = {ho.get('biotemp_c', '-')} °C · ETP = {ho.get('etp_holdridge_mm', '-')} mm · Relación EPT = {ho.get('ept_ratio', '-')}"],
            ["Köppen-Geiger", ko.get("label", "N/D"), f"Código climático estándar {ko.get('code', '-')}"],
            ["Thornthwaite (1948)", f"{summ['thornthwaite_index_pct']:.1f}% — {summ['humidity_class']}", f"{summ['humidity_description']} · Térmica: {summ['thermal_class']}"],
            ["Índice Aridez (ENA-IDEAM)", f"{ena.get('category', 'N/D')} (IA={ena.get('ia', '-')})", ena.get("description", "")],
        ],
        col_widths=(40, 58, 88),
        col_aligns=[Align.L, Align.L, Align.L],
        font_size=7.4,
    )

    # 3. Estaciones
    pdf.section_title("3. RED DE ESTACIONES Y PONDERACIÓN ESPACIAL")
    stn_rows = [
        [
            st.get("codigo", ""),
            st.get("nombre") or "",
            st.get("categoria_codigo") or "",
            st.get("municipio_nombre") or "",
            f"{st.get('latitud', 0):.4f}" if st.get("latitud") is not None else "",
            f"{st.get('longitud', 0):.4f}" if st.get("longitud") is not None else "",
            f"{st.get('altitud', 0):.0f}" if st.get("altitud") is not None else "",
            f"{st.get('weight_norm', 0)*100:.1f}%",
        ]
        for st in analysis.get("stations", [])
    ]
    pdf.render_data_table(
        headers=["Código", "Nombre Estación", "Cat.", "Municipio", "Latitud", "Longitud", "Alt(m)", "Peso"],
        rows=stn_rows,
        col_widths=(20, 56, 11, 35, 19, 19, 13, 13),
        col_aligns=[Align.C, Align.L, Align.C, Align.L, Align.R, Align.R, Align.R, Align.R],
        font_size=7.3,
    )

    pdf.set_font(pdf.font_family_name, "", 7.5)
    pdf.multi_cell(0, 4.4, pdf._s(f"Fuentes integradas (días-dato): {analysis.get('source_day_counts', {})}."), new_x="LMARGIN", new_y="NEXT")

    clim_png = render_climograph_png(analysis)
    if pdf.get_y() > 190:
        pdf.add_page()
    pdf.ln(2)
    pdf.image(io.BytesIO(clim_png), x=14, w=182)

    # Página 2: Balance Hídrico Mensual
    pdf.add_page()
    pdf.section_title("4. RÉGIMEN MENSUAL Y BALANCE HÍDRICO CLIMATOLÓGICO")
    m_rows = [
        [
            r["month"],
            f"{r['precip_mm']:.1f}",
            f"{r['temp_mean_c']:.2f}",
            f"{r['temp_max_c']:.1f}" if r["temp_max_c"] is not None else "-",
            f"{r['temp_min_c']:.1f}" if r["temp_min_c"] is not None else "-",
            f"{r['rh_pct']:.1f}" if r["rh_pct"] is not None else "-",
            f"{r['solar_rad_mj']:.2f}" if r["solar_rad_mj"] is not None else "-",
            f"{r['etp_active_mm']:.1f}",
            f"{r['storage_mm']:.1f}",
            f"{r['excess_mm']:.1f}",
            f"{r['deficit_mm']:.1f}",
        ]
        for r in analysis.get("monthly_summary", [])
    ]
    m_rows.append([
        "ANUAL / PROM",
        f"{summ['annual_precip_mm']:.1f}",
        f"{summ['mean_annual_temp_c']:.2f}",
        "-", "-", "-", "-",
        f"{summ['annual_etp_mm']:.1f}",
        "-",
        f"{summ['annual_excess_mm']:.1f}",
        f"{summ['annual_deficit_mm']:.1f}",
    ])
    pdf.render_data_table(
        headers=["Mes", "Precip\n(mm)", "T.Med\n(°C)", "T.Máx\n(°C)", "T.Mín\n(°C)", "HR\n(%)", "Rad.Sol\n(MJ/m²)", "ETP\n(mm)", "Almac\n(mm)", "Exceso\n(mm)", "Déficit\n(mm)"],
        rows=m_rows,
        col_widths=(22, 17, 15, 15, 15, 14, 18, 17.5, 17.5, 17.5, 17.5),
        col_aligns=[Align.L] + [Align.R] * 10,
        font_size=7.2,
        bold_last_row=True,
    )

    wb_png = render_water_balance_png(analysis)
    pdf.image(io.BytesIO(wb_png), x=14, w=182)

    # Página 3: Tendencias, Homogeneidad, ETCCDI y Pavimentos
    pdf.add_page()
    pdf.section_title("5. HOMOGENEIDAD (PETTITT), TENDENCIAS (MANN-KENDALL) E ÍNDICES ETCCDI")
    tp = qual.get("trends", {}).get("precip_annual", {})
    tt = qual.get("trends", {}).get("temp_mean_annual", {})
    hp = qual.get("homogeneity", {}).get("precip_annual", {})
    ht = qual.get("homogeneity", {}).get("temp_mean_annual", {})
    pdf.render_kv_table([
        ("Mann-Kendall Precip.", f"{tp.get('trend', 'N/D')} (Sen={tp.get('sen_slope_per_decade', '-')} mm/déc)" if tp.get("available") else "Insuficiente (<5 años)"),
        ("Pettitt Precip.", hp.get("status", "Insuficiente (<6 años)")),
        ("Mann-Kendall Temp.", f"{tt.get('trend', 'N/D')} (Sen={tt.get('sen_slope_per_decade', '-')} °C/déc)" if tt.get("available") else "Insuficiente (<5 años)"),
        ("Pettitt Temp.", ht.get("status", "Insuficiente (<6 años)")),
        ("Rx1day / Rx5day", f"{etccdi.get('rx1day_mm', '-')} mm / {etccdi.get('rx5day_mm', '-')} mm"),
        ("Rachas CDD / CWD", f"{etccdi.get('cdd_max_dry_days', '-')} d secos / {etccdi.get('cwd_max_wet_days', '-')} d húmedos"),
        ("Días R20mm / R50mm", f"{etccdi.get('r20mm_days_yr', '-')} / {etccdi.get('r50mm_days_yr', '-')} días/año"),
        ("Extremos TXx / TNn", f"{etccdi.get('txx_abs_max_c', '-')} °C / {etccdi.get('tnn_abs_min_c', '-')} °C"),
    ])

    trends_png = render_annual_trends_png(analysis)
    pdf.ln(1)
    pdf.image(io.BytesIO(trends_png), x=14, w=182)

    pdf.section_title("6. INGENIERÍA DE PAVIMENTOS (1. TMAP SHELL · 2. PMA · SUPERPAVE PG · MEPDG)")
    pdf.render_kv_table([
        ("1. TMAP (Shell / w-MAAT)", f"{pav.get('tmap_c') or 'N/D'} °C (Ciclo clim: {pav.get('tmap_clim_cycle_c') or 'N/D'} °C)"),
        ("2. PMA (Precip. Media Anual)", f"{pma_val:,.1f} mm/año"),
        ("Región Climática INVIAS", f"{tmap_reg.get('code', '-')} — {tmap_reg.get('name', '-')} ({tmap_reg.get('criteria', '')})"),
        ("Grado Superpave PG (98%)", str(pav.get("recommended_pg_grade", "N/D"))),
        ("T. Máx 7 días consecutivos", f"{pav.get('max_7day_tmax_c') or 'N/D'} °C (Tmed 7d: {pav.get('max_7day_tmean_c') or 'N/D'} °C)"),
        ("T. Pavimento 20 mm (Máx/Mín)", f"{pav.get('tpav_max_20mm_98_c') or '-'} °C / {pav.get('tpav_min_20mm_98_c') or '-'} °C"),
        ("Días >= 32 °C / Secos / NF", f"{pdf._fmt(pav.get('days_ge_32c_pct'), 1, '%')} / {pdf._fmt(pav.get('dry_days_pct'), 1, '%')} / {pav.get('water_table_m')} m"),
        ("Thornthwaite TMI (MEPDG)", f"{pav.get('thornthwaite_tmi_pct') or '-'}%"),
    ])

    # Página 4: Hidrología Extrema, Bondad de Ajuste K-S, IDF, Hietograma y RAS/INVIAS
    if idf.get("available"):
        pdf.add_page()
        p_idf = idf["idf_params"]
        pdf.section_title(f"7. HIDROLOGÍA EXTREMA, CURVAS IDF ({p_idf['method_label'].upper()}) Y NORMATIVA RAS/INVIAS")
        pdf.set_font(pdf.font_family_name, "", 8.0)
        pdf.multi_cell(
            0,
            4.6,
            pdf._s(
                f"Serie P24h máx: M = {idf['m_pmax_24h_mean_mm']:.2f} mm (σ = {idf['pmax_24h_std_mm']:.2f} mm, {idf['years_count']} años). "
                f"Mejor ajuste Kolmogorov-Smirnov: {idf.get('best_distribution')}. Ecuación IDF: {p_idf['formula']}."
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(1.5)

        trs_show = [2, 3, 5, 10, 20, 25, 50, 100]
        dist_rows = []
        for d_name, d_obj in idf.get("distributions", {}).items():
            q_map = {q["tr"]: q["p24h_mm"] for q in d_obj["quantiles"]}
            tag = " ★" if d_name == idf.get("best_distribution") else ""
            dist_rows.append(
                [d_name + tag, f"{d_obj['ks_d']:.3f}", f"{d_obj['r2']:.3f}"]
                + [f"{q_map.get(tr, 0):.1f}" for tr in trs_show]
            )
        pdf.render_data_table(
            headers=["Distribución P24h", "K-S D", "R²"] + [f"Tr{tr}" for tr in trs_show],
            rows=dist_rows,
            col_widths=(36, 18, 16) + tuple([14.5] * len(trs_show)),
            col_aligns=[Align.L] + [Align.R] * (2 + len(trs_show)),
            font_size=7.1,
        )

        key_durs = {5, 10, 15, 20, 30, 45, 60, 90, 120, 150, 180}
        idf_rows = [
            [str(row["duration_min"])] + [f"{row.get(f'tr_{tr}', 0):.1f}" for tr in trs_show]
            for row in idf["idf_table"]
            if row["duration_min"] in key_durs
        ]
        pdf.render_data_table(
            headers=["Dur (min)"] + [f"Tr {tr} a" for tr in trs_show],
            rows=idf_rows,
            col_widths=(22,) + tuple([20.5] * len(trs_show)),
            col_aligns=[Align.C] + [Align.R] * len(trs_show),
            font_size=7.1,
        )

        idf_png = render_idf_curves_png(analysis)
        pdf.image(io.BytesIO(idf_png), x=12, w=186)

        # Página 5: Hietograma Bloques Alternos y Tabla Normativa RAS / INVIAS
        pdf.add_page()
        pdf.section_title("8. HIETOGRAMA DE DISEÑO Y PERÍODOS DE RETORNO NORMATIVOS (RAS / INVIAS)")
        hyet_png = render_hyetograph_png(analysis)
        pdf.image(io.BytesIO(hyet_png), x=14, w=182)
        pdf.ln(1.5)

        norm_rows = [
            [
                nr["norma"],
                str(nr["obra"]),
                f"{nr['tr_rec']} a",
                f"{nr.get('i_tc15_mmh') or '-'} mm/h",
                f"{nr.get('i_tc30_mmh') or '-'} mm/h",
            ]
            for nr in idf.get("normative_return_periods", [])
        ]
        pdf.render_data_table(
            headers=["Norma", "Tipo de Obra / Estructura", "Tr Rec.", "i (tc=15m)", "i (tc=30m)"],
            rows=norm_rows,
            col_widths=(36, 86, 16, 24, 24),
            col_aligns=[Align.L, Align.L, Align.C, Align.R, Align.R],
            font_size=7.2,
        )

    # Página 6: Geotecnia SGC, Erosividad RUSLE (ANLA), Sequías (SPEI/IAP) y Cuenca INVIAS/SCS
    sgc = analysis.get("geohazards_sgc", {})
    ero = analysis.get("erosivity", {})
    drg = analysis.get("drought", {})
    wshed = analysis.get("watershed", {})
    if sgc.get("available") or ero.get("available") or drg.get("available") or wshed.get("available"):
        pdf.add_page()
        pdf.section_title("9. GEOTECNIA SGC (LLUVIA DETONANTE), EROSIVIDAD RUSLE, SEQUÍAS SPEI Y CUENCA INVIAS")

        kv_geo = []
        if sgc.get("available"):
            inf = sgc.get("infiltration_balance", {})
            kv_geo.append((
                "Umbral Detonante SGC",
                f"{sgc.get('threshold_eq')} | Excedencias: {sgc.get('exceedance_days', 0)} días ({sgc.get('exceedance_rate_pct', 0)} %) en {sgc.get('episodes_count', 0)} episodios",
            ))
            kv_geo.append((
                "Infiltración SCS-CN Diaria",
                f"CN I/II/III = {inf.get('cn_i')}/{inf.get('cn_ii')}/{inf.get('cn_iii')} | Infiltración media = {inf.get('mean_annual_infiltration_mm')} mm/a | Escorr = {inf.get('mean_annual_runoff_mm')} mm/a",
            ))
        if ero.get("available"):
            kv_geo.append((
                "Erosividad RUSLE (ANLA)",
                f"MFI = {ero.get('mfi_arnoldus_mm')} mm ({ero.get('aggressiveness_class')}) | PCI = {ero.get('pci_oliver_pct')}% ({ero.get('pci_class')}) | Factor R = {ero.get('r_factor_mfi')} {ero.get('unit')}",
            ))
        if drg.get("summary"):
            ds = drg["summary"]
            kv_geo.append((
                "Sequías SPEI-3 (UNGRD/OMM)",
                f"Mín SPEI-3 = {ds.get('min_spei3')} ({ds.get('min_spei3_date')}) | Meses ≤ -1.0: {ds.get('drought_moderate_pct')}% | ≤ -1.5: {ds.get('drought_severe_pct')}%",
            ))
        if wshed.get("available"):
            kv_geo.append((
                "Parámetros de Cuenca INVIAS",
                f"A = {wshed['area_km2']} km² | L = {wshed['length_m']} m | S = {wshed['slope_pct']}% | tc Kirpich = {wshed['tc_kirpich_min']} min | tc Témez = {wshed['tc_temez_min']} min",
            ))
        if kv_geo:
            pdf.render_kv_table(kv_geo)

        if sgc.get("available") and sgc.get("rolling_stats"):
            r_rows = [
                [
                    w_lbl,
                    f"{d.get('mean') or '-'}",
                    f"{d.get('p90') or '-'}",
                    f"{d.get('p95') or '-'}",
                    f"{d.get('p99') or '-'}",
                    f"{d.get('max') or '-'}",
                    str(d.get("date_max") or "-"),
                ]
                for w_lbl, d in sgc["rolling_stats"].items()
            ]
            pdf.render_data_table(
                headers=["Ventana SGC", "Media (mm)", "P90 (mm)", "P95 (mm)", "P99 (mm)", "Máx (mm)", "Fecha Máx"],
                rows=r_rows,
                col_widths=(36, 22, 22, 22, 22, 24, 38),
                col_aligns=[Align.L, Align.R, Align.R, Align.R, Align.R, Align.R, Align.C],
                font_size=7.2,
            )

        if wshed.get("available") and wshed.get("design_rows"):
            w_rows = [
                [
                    f"{r['tr']} a",
                    f"{r['i_tc_mmh']:.1f}",
                    f"{r['q_rational_m3s']:.3f}",
                    f"{r['p_storm_mm']:.1f}",
                    f"{r['qe_runoff_mm']:.1f}",
                    f"{r['infiltration_mm']:.1f}",
                    f"{r['q_scs_m3s']:.3f}",
                ]
                for r in wshed["design_rows"]
            ]
            pdf.render_data_table(
                headers=["Tr", "I(tc) mm/h", "Q Racional m³/s", "P Torm. mm", "Qe SCS mm", "Infilt F mm", "Q SCS m³/s"],
                rows=w_rows,
                col_widths=(16, 28, 30, 28, 28, 28, 28),
                col_aligns=[Align.C] + [Align.R] * 6,
                font_size=7.2,
            )

        if sgc.get("available"):
            pdf.image(io.BytesIO(render_sgc_thresholds_png(analysis)), x=13, w=184)

        if drg.get("available") or ero.get("available"):
            pdf.add_page()
            pdf.section_title("9B. MONITOREO DE SEQUÍAS SPEI-3 / SPEI-12, EROSIVIDAD RUSLE Y EPISODIOS SGC")
            pdf.image(io.BytesIO(render_spei_drought_png(analysis)), x=13, w=184)
            eps = (sgc.get("episodes") or [])[:8]
            if eps:
                pdf.ln(2)
                ep_rows = [
                    [
                        e["start_date"], e["end_date"], str(e["duration_days"]), e["peak_date"],
                        f"{e['r1_peak_mm']:.1f}", f"{e['r3_peak_mm']:.1f}", f"{e['r15_ant_mm']:.1f}",
                        f"{e['threshold_r3_mm']:.1f}", f"{e['severity_ratio']:.2f}x",
                    ]
                    for e in eps
                ]
                pdf.render_data_table(
                    headers=["Inicio", "Fin", "Dur(d)", "Fecha Pico", "R1(mm)", "R3(mm)", "R15 Ant", "Umbral", "Sever."],
                    rows=ep_rows,
                    col_widths=(23, 23, 14, 24, 20, 20, 22, 20, 20),
                    col_aligns=[Align.C, Align.C, Align.C, Align.C, Align.R, Align.R, Align.R, Align.R, Align.R],
                    font_size=7.0,
                )

    return bytes(pdf.output())
