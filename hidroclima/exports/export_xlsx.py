"""Exportación de libro Excel (.xlsx) profesional con formulación dinámica y gráficos nativos."""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


NAVY_FILL = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
TEAL_FILL = PatternFill(start_color="0E7490", end_color="0E7490", fill_type="solid")
SUBHDR_FILL = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
TOTAL_FILL = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
ZEBRA_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

FONT_TITLE = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
FONT_HDR = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
FONT_SUBHDR = Font(name="Calibri", size=10, bold=True, color="0F172A")
FONT_INPUT = Font(name="Calibri", size=10, color="0369A1")      # Entradas numéricas editables
FONT_FORMULA = Font(name="Calibri", size=10, color="0F172A")    # Fórmulas intra-hoja
FONT_LINK = Font(name="Calibri", size=10, color="0F766E")       # Vínculos entre hojas
FONT_TOTAL = Font(name="Calibri", size=10, bold=True, color="0F172A")

THIN_SIDE = Side(border_style="thin", color="CBD5E1")
MED_BOTTOM = Side(border_style="medium", color="0F172A")
CELL_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
TOTAL_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=MED_BOTTOM)


def _banner(ws, title: str, ncols: int, row: int = 1, fill=NAVY_FILL) -> None:
    ws.cell(row=row, column=1, value=title)
    if ncols > 1:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    for col in range(1, ncols + 1):
        c = ws.cell(row=row, column=col)
        c.fill = fill
        c.font = FONT_TITLE if row == 1 else FONT_HDR
        c.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
    ws.row_dimensions[row].height = 24 if row == 1 else 20


def _style_header_row(ws, row: int, ncols: int, height: float = 28.0) -> None:
    ws.row_dimensions[row].height = height
    for col in range(1, ncols + 1):
        c = ws.cell(row=row, column=col)
        c.fill = NAVY_FILL
        c.font = FONT_HDR
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = CELL_BORDER


def _style_data_range(
    ws,
    min_row: int,
    max_row: int,
    ncols: int,
    *,
    zebra: bool = True,
    num_fmt_map: dict[int, str] | None = None,
    formula_cols: set[int] | None = None,
    link_cols: set[int] | None = None,
) -> None:
    formula_cols = formula_cols or set()
    link_cols = link_cols or set()
    num_fmt_map = num_fmt_map or {}
    for r in range(min_row, max_row + 1):
        for col in range(1, ncols + 1):
            c = ws.cell(row=r, column=col)
            c.border = CELL_BORDER
            if zebra and (r - min_row) % 2 == 1:
                c.fill = ZEBRA_FILL
            val = c.value
            is_formula = isinstance(val, str) and val.startswith("=")
            if col in link_cols or (is_formula and "!" in str(val)):
                c.font = FONT_LINK
            elif col in formula_cols or is_formula:
                c.font = FONT_FORMULA
            elif isinstance(val, (int, float)):
                c.font = FONT_INPUT
            else:
                c.font = FONT_FORMULA
            if col in num_fmt_map:
                c.number_format = num_fmt_map[col]
            is_num = isinstance(val, (int, float)) or is_formula or col in num_fmt_map
            c.alignment = Alignment(
                horizontal="right" if is_num and col > 2 else ("center" if col == 1 and isinstance(val, int) else "left"),
                vertical="center",
                wrap_text=not is_num,
            )


def _autofit_sheet(ws, min_width: int = 10, max_width: int = 44) -> None:
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            # Ignorar celdas fusionadas de títulos largos en filas 1-2
            if cell.row <= 2 and col[0].column == 1:
                continue
            val = cell.value
            if isinstance(val, str) and val.startswith("="):
                max_len = max(max_len, 12)
            else:
                val_str = str(val if val is not None else "")
                max_len = max(max_len, max((len(line) for line in val_str.splitlines()), default=0))
        ws.column_dimensions[col_letter].width = min(max_width, max(min_width, max_len + 3))
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0


def generate_xlsx_workbook(analysis: dict[str, Any]) -> bytes:
    """Genera libro Excel .xlsx profesional con fórmulas vivas, trazabilidad y gráficos nativos."""
    wb = Workbook()
    proj = analysis["project"]
    summ = analysis["summary"]
    pav = analysis["pavement"]
    idf = analysis["hydrology_idf"]
    cls = analysis.get("classifications", {})
    qual = analysis.get("quality", {})
    etccdi = qual.get("etccdi", {})
    tmap_reg = pav.get("invias_pavement_region", {})
    pma_val = pav.get("pma_mm", summ["annual_precip_mm"])

    # Precrear las 8 hojas en el orden estándar
    ws_res = wb.active
    ws_res.title = "Resumen_Ejecutivo"
    ws_stn = wb.create_sheet("Estaciones")
    ws_bal = wb.create_sheet("Balance_Mensual")
    ws_pav = wb.create_sheet("Pavimentos_TMAP")
    ws_ann = wb.create_sheet("Serie_Anual")
    ws_day = wb.create_sheet("Promedios_Diarios_365")
    ws_idf = wb.create_sheet("IDF_Frecuencia_RAS")
    ws_cal = wb.create_sheet("Calidad_Homogeneidad_ETCCDI")
    ws_sgc = wb.create_sheet("Geotecnia_SGC_Lluvias")
    ws_cua = wb.create_sheet("Cuenca_RUSLE_Sequias")

    # =========================================================================
    # HOJA 3: Balance_Mensual (base de cálculos mensuales + fórmulas vivas)
    # =========================================================================
    _banner(ws_bal, f"HIDROCLIMA STUDIO v1.0.0 — BALANCE HÍDRICO Y RÉGIMEN MENSUAL ({proj['name']})", 21, row=1)
    ws_bal.cell(row=2, column=1, value="Reserva Máx. Suelo (mm):").font = FONT_SUBHDR
    ws_bal.cell(row=2, column=3, value=float(proj["soil_max_reserve_mm"])).font = FONT_INPUT
    ws_bal.cell(row=2, column=3).number_format = "#,##0.0"
    ws_bal.cell(row=2, column=4, value="Latitud (°):").font = FONT_SUBHDR
    ws_bal.cell(row=2, column=5, value=float(proj["avg_lat"])).font = FONT_INPUT
    ws_bal.cell(row=2, column=5).number_format = "0.0000"
    ws_bal.cell(row=2, column=6, value="Método ETP:").font = FONT_SUBHDR
    ws_bal.cell(row=2, column=7, value=proj["etp_method_label"]).font = FONT_FORMULA
    ws_bal.cell(row=2, column=10, value="Código colores: Azul = entrada | Negro = fórmula | Verde = vínculo").font = Font(
        name="Calibri", size=9, italic=True, color="64748B"
    )

    bal_headers = [
        "Mes #", "Mes", "Precipitación (mm)", "T. Media (°C)", "T. Máxima (°C)", "T. Mínima (°C)",
        "Humedad Relativa (%)", "Brillo Solar (h/d)", "Vel. Viento (m/s)", "Rad. Solar (MJ/m²/d)",
        "Horas Sol (N)", "Índice Calor (i)", "ETP Thornthwaite (mm)", "ETP Penman-Monteith (mm)",
        "ETP Activa (mm)", "P - ETP (mm)", "ETR (mm)", "Almacenamiento (mm)", "Exceso (mm)",
        "Déficit (mm)", "TMI Paso (%)"
    ]
    for col, h in enumerate(bal_headers, start=1):
        ws_bal.cell(row=4, column=col, value=h)
    _style_header_row(ws_bal, 4, len(bal_headers))
    ws_bal.freeze_panes = "C5"

    m_rows = analysis.get("monthly_summary", [])
    for idx, r in enumerate(m_rows, start=5):
        ws_bal.cell(row=idx, column=1, value=r["month_num"])
        ws_bal.cell(row=idx, column=2, value=r["month"])
        ws_bal.cell(row=idx, column=3, value=r["precip_mm"])
        ws_bal.cell(row=idx, column=4, value=r["temp_mean_c"])
        ws_bal.cell(row=idx, column=5, value=r["temp_max_c"])
        ws_bal.cell(row=idx, column=6, value=r["temp_min_c"])
        ws_bal.cell(row=idx, column=7, value=r["rh_pct"])
        ws_bal.cell(row=idx, column=8, value=r["sunshine_h"])
        ws_bal.cell(row=idx, column=9, value=r["wind_ms"])
        ws_bal.cell(row=idx, column=10, value=r["solar_rad_mj"])
        ws_bal.cell(row=idx, column=11, value=r["daylight_h"])
        ws_bal.cell(row=idx, column=12, value=f"=IF(D{idx}>0,(D{idx}/5)^1.514,0)")
        ws_bal.cell(row=idx, column=13, value=r["etp_thornthwaite_mm"])
        ws_bal.cell(row=idx, column=14, value=r["etp_penman_mm"])
        ws_bal.cell(row=idx, column=15, value=r["etp_active_mm"])
        ws_bal.cell(row=idx, column=16, value=f"=C{idx}-O{idx}")
        ws_bal.cell(row=idx, column=17, value=f"=O{idx}-T{idx}")
        ws_bal.cell(row=idx, column=18, value=r["storage_mm"])
        ws_bal.cell(row=idx, column=19, value=r["excess_mm"])
        ws_bal.cell(row=idx, column=20, value=r["deficit_mm"])
        ws_bal.cell(row=idx, column=21, value=f"=IF(O{idx}>0,100*((S{idx}-0.6*T{idx})/O{idx}),0)")

    bal_fmt = {
        3: "#,##0.0", 4: "0.00", 5: "0.0", 6: "0.0", 7: "0.0", 8: "0.00", 9: "0.00", 10: "0.00",
        11: "0.00", 12: "0.000", 13: "#,##0.0", 14: "#,##0.0", 15: "#,##0.0", 16: "#,##0.0",
        17: "#,##0.0", 18: "#,##0.0", 19: "#,##0.0", 20: "#,##0.0", 21: "0.0",
    }
    _style_data_range(ws_bal, 5, 16, 21, num_fmt_map=bal_fmt, formula_cols={12, 16, 17, 21})

    # Fila 17: ANUAL / PROMEDIO con fórmulas vivas
    ws_bal.cell(row=17, column=1, value="-")
    ws_bal.cell(row=17, column=2, value="ANUAL / PROM (Fórmula)")
    sum_cols = {3, 12, 13, 14, 15, 16, 17, 19, 20}
    avg_cols = {4, 5, 6, 7, 8, 9, 10, 11, 18}
    for col in range(3, 21):
        let = get_column_letter(col)
        if col in sum_cols:
            ws_bal.cell(row=17, column=col, value=f"=SUM({let}5:{let}16)")
        elif col in avg_cols:
            ws_bal.cell(row=17, column=col, value=f"=AVERAGE({let}5:{let}16)")
    ws_bal.cell(row=17, column=21, value="=IF(O17>0,100*((S17-0.6*T17)/O17),0)")
    for col in range(1, 22):
        c = ws_bal.cell(row=17, column=col)
        c.fill = TOTAL_FILL
        c.font = FONT_TOTAL
        c.border = TOTAL_BORDER
        if col in bal_fmt:
            c.number_format = bal_fmt[col]

    # Índices hídricos calculados por fórmula debajo de la tabla (filas 19-22)
    bal_kpis = [
        (19, "Exponente de Thornthwaite (a)", "=6.75E-7*L17^3-7.71E-5*L17^2+0.01792*L17+0.49239", "0.00000"),
        (20, "Índice de Humedad (Ih %)", "=IF(O17>0,100*S17/O17,0)", "0.00"),
        (21, "Índice de Aridez Thornthwaite (Ia %)", "=IF(O17>0,100*T17/O17,0)", "0.00"),
        (22, "Índice de Aridez ENA-IDEAM (IA)", "=IF(O17>0,(O17-Q17)/O17,0)", "0.000"),
    ]
    for r_idx, lbl, formula, nfmt in bal_kpis:
        ws_bal.cell(row=r_idx, column=2, value=lbl).font = FONT_SUBHDR
        c_val = ws_bal.cell(row=r_idx, column=3, value=formula)
        c_val.font = FONT_TOTAL
        c_val.number_format = nfmt
        c_val.fill = ZEBRA_FILL
        c_val.border = CELL_BORDER

    # Gráfico nativo 1 en Balance_Mensual: Climograma
    c_clim = BarChart()
    c_clim.title = "Climograma Mensual: Precipitación [mm] vs Temperatura [°C]"
    c_clim.y_axis.title = "Precipitación [mm]"
    c_clim.x_axis.title = "Mes"
    c_clim.add_data(Reference(ws_bal, min_col=3, min_row=4, max_row=16), titles_from_data=True)
    c_clim.set_categories(Reference(ws_bal, min_col=2, min_row=5, max_row=16))
    c_clim.style = 10
    c_clim.width = 16
    c_clim.height = 9.5

    c_temp = LineChart()
    c_temp.add_data(Reference(ws_bal, min_col=4, min_row=4, max_row=16), titles_from_data=True)
    c_temp.y_axis.title = "Temp. Media [°C]"
    c_temp.y_axis.axId = 200
    c_clim.y_axis.crosses = "min"
    c_clim += c_temp
    ws_bal.add_chart(c_clim, "B24")

    # Gráfico nativo 2 en Balance_Mensual: Balance Hídrico
    c_wb = BarChart()
    c_wb.title = "Balance Hídrico Mensual: ETP, Exceso y Déficit [mm]"
    c_wb.y_axis.title = "Lámina [mm]"
    c_wb.add_data(Reference(ws_bal, min_col=15, min_row=4, max_row=16), titles_from_data=True)
    c_wb.add_data(Reference(ws_bal, min_col=19, min_row=4, max_row=16), titles_from_data=True)
    c_wb.add_data(Reference(ws_bal, min_col=20, min_row=4, max_row=16), titles_from_data=True)
    c_wb.set_categories(Reference(ws_bal, min_col=2, min_row=5, max_row=16))
    c_wb.width = 16
    c_wb.height = 9.5
    ws_bal.add_chart(c_wb, "L24")

    # =========================================================================
    # HOJA 4: Pavimentos_TMAP (1. TMAP Shell Carta W + 2. PMA + INVIAS R1-R6)
    # =========================================================================
    _banner(ws_pav, "INGENIERÍA DE PAVIMENTOS — 1. TMAP (SHELL CARTA W) · 2. PMA · REGIÓN INVIAS R1–R6 · SUPERPAVE PG", 5, row=1)
    ws_pav.cell(row=2, column=1, value="Fórmula Carta W: WF = 10^(-1.224 + 0.06508·T - 0.000145·T²)  |  TMAP = 19.66 + 16.91·log10(WF_prom) + 0.3117·[log10(WF_prom)]²").font = Font(
        name="Calibri", size=9, italic=True, color="475569"
    )
    for col, h in enumerate(["Mes", "Temp. Media Mensual (°C)", "Factor Ponderación Shell (WF)"], start=1):
        ws_pav.cell(row=3, column=col, value=h)
    _style_header_row(ws_pav, 3, 3)

    wf_rows = pav.get("monthly_wf", [])
    for idx in range(12):
        r_excel = 4 + idx
        m_lbl = wf_rows[idx]["month"] if idx < len(wf_rows) else (m_rows[idx]["month_abbr"] if idx < len(m_rows) else f"M{idx+1}")
        ws_pav.cell(row=r_excel, column=1, value=m_lbl)
        ws_pav.cell(row=r_excel, column=2, value=f"=Balance_Mensual!D{5 + idx}")
        ws_pav.cell(row=r_excel, column=3, value=f"=10^(-1.224+0.06508*B{r_excel}-0.000145*B{r_excel}^2)")
    _style_data_range(ws_pav, 4, 15, 3, num_fmt_map={2: "0.00", 3: "0.0000"}, formula_cols={3}, link_cols={2})

    ws_pav.cell(row=16, column=1, value="WF Promedio Ciclo Climatológico").font = FONT_TOTAL
    ws_pav.cell(row=16, column=2, value="=AVERAGE(B4:B15)").number_format = "0.00"
    ws_pav.cell(row=16, column=3, value="=AVERAGE(C4:C15)").number_format = "0.0000"
    for col in range(1, 4):
        c = ws_pav.cell(row=16, column=col)
        c.fill = TOTAL_FILL
        c.font = FONT_TOTAL
        c.border = TOTAL_BORDER

    # Bloque de Cálculo Anual de TMAP (filas 25+)
    yearly_tmap = pav.get("tmap_yearly", [])
    yr_start = 25
    yr_end = yr_start + len(yearly_tmap) - 1
    if yearly_tmap:
        for col, h in enumerate(["Año", "Meses Válidos", "Temp. Media Aritmética (°C)", "WF Promedio Anual", "TMAP Anual (°C)"], start=1):
            ws_pav.cell(row=24, column=col, value=h)
        _style_header_row(ws_pav, 24, 5)
        for idx, r in enumerate(yearly_tmap, start=yr_start):
            ws_pav.cell(row=idx, column=1, value=r["year"])
            ws_pav.cell(row=idx, column=2, value=r["months_count"])
            ws_pav.cell(row=idx, column=3, value=r["tmean_arith_c"])
            ws_pav.cell(row=idx, column=4, value=r["wf_avg"])
            ws_pav.cell(row=idx, column=5, value=f"=19.66+16.91*LOG10(D{idx})+0.3117*(LOG10(D{idx}))^2")
        _style_data_range(ws_pav, yr_start, yr_end, 5, num_fmt_map={3: "0.00", 4: "0.0000", 5: "0.00"}, formula_cols={5})

    # Síntesis 1. TMAP + 2. PMA + Clasificación INVIAS viva (filas 18-22)
    tmap_proj_formula = f"=AVERAGE(E{yr_start}:E{yr_end})" if yearly_tmap else "=B18"
    pav_kpis = [
        (18, "1a. TMAP Ciclo Climatológico (Shell w-MAAT, °C)", "=19.66+16.91*LOG10(C16)+0.3117*(LOG10(C16))^2", "0.00", "Ciclo mensual ponderado"),
        (19, "1b. Temperatura Media Anual Ponderada — TMAP (°C)", tmap_proj_formula, "0.00", "Promedio multianual de TMAP anuales"),
        (20, "2. Precipitación Media Anual — PMA (mm/año)", "=Balance_Mensual!C17", "#,##0.0", "Suma anual climatológica"),
        (
            21,
            "3. Región Climática Pavimentos INVIAS (R1–R6)",
            '=IF(B19<13,IF(B20<2000,"R1 — Fría seca y semihúmeda","R1-H — Fría húmeda / Páramo"),IF(B19<=20,IF(B20<2000,"R2 — Templado seco y semihúmedo","R4 — Templado húmedo"),IF(B20<2000,"R3 — Cálido seco y semihúmedo",IF(B20<=4000,"R5 — Cálido húmedo","R6 — Cálido muy húmedo"))))',
            "@",
            tmap_reg.get("criteria", ""),
        ),
        (22, "Grado Superpave PG (98 % conf., 20 mm)", pav.get("recommended_pg_grade", "N/D"), "@", f"Tmax 7d: {pav.get('max_7day_tmax_c') or '-'} °C"),
    ]
    for r_idx, lbl, val, nfmt, note in pav_kpis:
        ws_pav.cell(row=r_idx, column=1, value=lbl).font = FONT_SUBHDR
        ws_pav.cell(row=r_idx, column=1).fill = SUBHDR_FILL
        ws_pav.cell(row=r_idx, column=1).border = CELL_BORDER
        cv = ws_pav.cell(row=r_idx, column=2, value=val)
        cv.font = FONT_TOTAL
        cv.number_format = nfmt
        cv.fill = TOTAL_FILL if r_idx in (19, 20, 21) else ZEBRA_FILL
        cv.border = CELL_BORDER
        cn = ws_pav.cell(row=r_idx, column=3, value=note)
        cn.font = FONT_FORMULA
        cn.border = CELL_BORDER

    # Gráfico de Factor Shell WF mensual en Pavimentos_TMAP
    c_wf = LineChart()
    c_wf.title = "Factor de Ponderación Térmica Mensual Shell (Carta W)"
    c_wf.y_axis.title = "Factor WF"
    c_wf.add_data(Reference(ws_pav, min_col=3, min_row=3, max_row=15), titles_from_data=True)
    c_wf.set_categories(Reference(ws_pav, min_col=1, min_row=4, max_row=15))
    c_wf.width = 13
    c_wf.height = 8.5
    ws_pav.add_chart(c_wf, "E3")
    ws_pav.freeze_panes = "A4"

    # =========================================================================
    # HOJA 7: IDF_Frecuencia_RAS (fórmulas IDF + Bloques Alternos + INDEX/MATCH RAS)
    # =========================================================================
    if idf.get("available"):
        p_idf = idf["idf_params"]
        trs = idf["idf_return_periods"]
        ncols_idf = max(8, 1 + len(trs))
        _banner(ws_idf, f"HIDROLOGÍA EXTREMA, CURVAS IDF ({p_idf['method_label'].upper()}) Y NORMATIVA RAS / INVIAS", ncols_idf, row=1)

        # Fila 3: Parámetros editables (inputs azules)
        method = p_idf.get("method", "invias")
        ws_idf.cell(row=2, column=1, value="Método IDF").font = FONT_SUBHDR
        ws_idf.cell(row=3, column=1, value=p_idf["method_label"]).font = FONT_FORMULA
        ws_idf.cell(row=2, column=2, value="M = P24h máx (mm)").font = FONT_SUBHDR
        ws_idf.cell(row=3, column=2, value=idf["m_pmax_24h_mean_mm"]).font = FONT_INPUT
        ws_idf.cell(row=3, column=2).number_format = "0.00"
        ws_idf.cell(row=2, column=7, value="Mejor Ajuste K-S").font = FONT_SUBHDR
        ws_idf.cell(row=3, column=7, value=idf.get("best_distribution", "Gumbel")).font = FONT_TOTAL

        if method == "invias":
            p_labels = [("a", p_idf["a"]), ("b", p_idf["b"]), ("c", p_idf["c"]), ("d", p_idf["d"])]
        elif method == "sherman":
            p_labels = [("k", p_idf["k"]), ("m", p_idf["m"]), ("c (min)", p_idf["c"]), ("n", p_idf["n"])]
        elif method == "silva":
            p_labels = [("r (P1h/P24h)", p_idf["silva_ratio_1h_24h"]), ("b (min)", p_idf["b"]), ("n", p_idf["n"]), ("P24h ref", idf["m_pmax_24h_mean_mm"])]
        else:
            p_labels = [("r (P1h/P24h)", 0.48), ("P60^10 (mm)", p_idf.get("p10_60_mm", 50.0)), ("Factor Tr", 0.21), ("Factor Dur", 0.54)]

        for idx_p, (pl, pv) in enumerate(p_labels, start=3):
            ws_idf.cell(row=2, column=idx_p, value=pl).font = FONT_SUBHDR
            cp = ws_idf.cell(row=3, column=idx_p, value=float(pv))
            cp.font = FONT_INPUT
            cp.number_format = "0.0000" if abs(float(pv)) < 2 else "0.00"
            cp.border = CELL_BORDER

        # Sección A (filas 5-10): Distribuciones P24h máx y Bondad de Ajuste K-S
        ws_idf.cell(row=5, column=1, value="Distribución P24h").font = FONT_HDR
        ws_idf.cell(row=5, column=2, value="K-S D").font = FONT_HDR
        ws_idf.cell(row=5, column=3, value="K-S p-val").font = FONT_HDR
        ws_idf.cell(row=5, column=4, value="R²").font = FONT_HDR
        for t_i, tr in enumerate(trs, start=5):
            ws_idf.cell(row=5, column=t_i, value=tr)
        _style_header_row(ws_idf, 5, 4 + len(trs), height=22)

        best_name = idf.get("best_distribution")
        best_dist_row = 6
        dist_start = 6
        for d_idx, (dn, dobj) in enumerate(idf.get("distributions", {}).items()):
            r_d = dist_start + d_idx
            is_best = dn == best_name
            if is_best:
                best_dist_row = r_d
            qmap = {q["tr"]: q["p24h_mm"] for q in dobj["quantiles"]}
            ws_idf.cell(row=r_d, column=1, value=dn + (" ★" if is_best else ""))
            ws_idf.cell(row=r_d, column=2, value=dobj["ks_d"])
            ws_idf.cell(row=r_d, column=3, value=dobj["ks_pvalue"])
            ws_idf.cell(row=r_d, column=4, value=dobj["r2"])
            for t_i, tr in enumerate(trs, start=5):
                ws_idf.cell(row=r_d, column=t_i, value=qmap.get(tr))
        dist_end = dist_start + max(0, len(idf.get("distributions", {})) - 1)
        _style_data_range(
            ws_idf, dist_start, dist_end, 4 + len(trs),
            num_fmt_map={**{2: "0.0000", 3: "0.0000", 4: "0.0000"}, **{c: "0.0" for c in range(5, 5 + len(trs))}},
        )

        # Sección B: Matriz de Intensidades IDF (mm/h) CON FÓRMULAS VIVAS
        idf_hdr_row = dist_end + 2
        ws_idf.cell(row=idf_hdr_row, column=1, value="Duración (min)")
        for t_i, tr in enumerate(trs, start=2):
            c_tr = ws_idf.cell(row=idf_hdr_row, column=t_i, value=tr)
            c_tr.number_format = '"Tr="0" años"'
        _style_header_row(ws_idf, idf_hdr_row, 1 + len(trs), height=24)

        idf_start = idf_hdr_row + 1
        idf_rows = idf["idf_table"]
        for r_off, row_d in enumerate(idf_rows):
            r_x = idf_start + r_off
            ws_idf.cell(row=r_x, column=1, value=row_d["duration_min"])
            for t_i in range(len(trs)):
                col_x = 2 + t_i
                col_let = get_column_letter(col_x)
                dist_let = get_column_letter(5 + t_i)
                if method == "invias":
                    expr = f"=$C$3*({col_let}${idf_hdr_row}^$D$3)*($B$3^$F$3)/(($A{r_x}/60)^$E$3)"
                elif method == "sherman":
                    expr = f"=$C$3*({col_let}${idf_hdr_row}^$D$3)/(($A{r_x}+$E$3)^$F$3)"
                elif method == "silva":
                    expr = f"=({dist_let}${best_dist_row}*$C$3*((60+$D$3)^$E$3))/(($A{r_x}+$D$3)^$E$3)"
                else:
                    expr = f"=MAX(0.5,(0.21*LN(MAX(1.1,{col_let}${idf_hdr_row}))+0.52)*(0.54*($A{r_x}^0.25)-0.5)*$D$3)/($A{r_x}/60)"
                ws_idf.cell(row=r_x, column=col_x, value=expr)
        idf_end = idf_start + len(idf_rows) - 1
        _style_data_range(
            ws_idf, idf_start, idf_end, 1 + len(trs),
            num_fmt_map={c: "0.00" for c in range(2, 2 + len(trs))},
            formula_cols=set(range(2, 2 + len(trs))),
        )
        ws_idf.freeze_panes = f"B{idf_start}"

        # Sección C: Hietograma de Bloques Alternos con fórmulas de Intensidad y Acumulada
        hyet_hdr = idf_end + 2
        for col, h in enumerate(["Bloque #", "Intervalo (min)", "Lámina (mm)", "Intensidad (mm/h)", "Lámina Acumulada (mm)"], start=1):
            ws_idf.cell(row=hyet_hdr, column=col, value=h)
        _style_header_row(ws_idf, hyet_hdr, 5, height=22)

        hyet_list = idf.get("hyetograph", [])
        hyet_start = hyet_hdr + 1
        for h_i, hr in enumerate(hyet_list):
            r_h = hyet_start + h_i
            ws_idf.cell(row=r_h, column=1, value=hr["step"])
            ws_idf.cell(row=r_h, column=2, value=hr["time_min"])
            ws_idf.cell(row=r_h, column=3, value=hr["depth_mm"])
            ws_idf.cell(row=r_h, column=4, value=f"=C{r_h}/(5/60)")
            ws_idf.cell(row=r_h, column=5, value=f"=SUM($C${hyet_start}:C{r_h})")
        hyet_end = hyet_start + max(0, len(hyet_list) - 1)
        if hyet_list:
            _style_data_range(
                ws_idf, hyet_start, hyet_end, 5,
                num_fmt_map={3: "0.00", 4: "0.00", 5: "0.00"},
                formula_cols={4, 5},
            )

        # Sección D: Evaluación Normativa RAS / INVIAS enlazada con INDEX/MATCH a la matriz IDF
        norm_hdr = (hyet_end if hyet_list else hyet_hdr) + 2
        for col, h in enumerate(["Norma", "Tipo de Obra / Estructura", "Tr Mín (a)", "Tr Rec (a)", "i (tc=15 min) [mm/h]", "i (tc=30 min) [mm/h]"], start=1):
            ws_idf.cell(row=norm_hdr, column=col, value=h)
        _style_header_row(ws_idf, norm_hdr, 6, height=22)

        norm_list = idf.get("normative_return_periods", [])
        norm_start = norm_hdr + 1
        tr_last_let = get_column_letter(1 + len(trs))
        for n_i, nr in enumerate(norm_list):
            r_n = norm_start + n_i
            ws_idf.cell(row=r_n, column=1, value=nr["norma"])
            ws_idf.cell(row=r_n, column=2, value=nr["obra"])
            ws_idf.cell(row=r_n, column=3, value=nr["tr_min"])
            ws_idf.cell(row=r_n, column=4, value=nr["tr_rec"])
            ws_idf.cell(
                row=r_n,
                column=5,
                value=f"=INDEX($B${idf_start}:${tr_last_let}${idf_end},MATCH(15,$A${idf_start}:$A${idf_end},0),MATCH(D{r_n},$B${idf_hdr_row}:${tr_last_let}${idf_hdr_row},0))",
            )
            ws_idf.cell(
                row=r_n,
                column=6,
                value=f"=INDEX($B${idf_start}:${tr_last_let}${idf_end},MATCH(30,$A${idf_start}:$A${idf_end},0),MATCH(D{r_n},$B${idf_hdr_row}:${tr_last_let}${idf_hdr_row},0))",
            )
        if norm_list:
            _style_data_range(
                ws_idf, norm_start, norm_start + len(norm_list) - 1, 6,
                num_fmt_map={5: "0.00", 6: "0.00"},
                formula_cols={5, 6},
            )

        # Gráfico nativo IDF
        c_idf = LineChart()
        c_idf.title = "Familia de Curvas IDF (mm/h)"
        c_idf.x_axis.title = "Duración [min]"
        c_idf.y_axis.title = "Intensidad [mm/h]"
        for tr_pick in (2, 5, 10, 25, 50, 100):
            if tr_pick in trs:
                col_idx = 2 + trs.index(tr_pick)
                c_idf.add_data(Reference(ws_idf, min_col=col_idx, min_row=idf_hdr_row, max_row=idf_end), titles_from_data=True)
        c_idf.set_categories(Reference(ws_idf, min_col=1, min_row=idf_start, max_row=idf_end))
        c_idf.width = 15.5
        c_idf.height = 10.0
        ws_idf.add_chart(c_idf, "H" + str(hyet_hdr))
    else:
        ws_idf.append(["Sin datos de precipitación diaria para análisis IDF"])

    # =========================================================================
    # HOJA 2: Estaciones
    # =========================================================================
    _banner(ws_stn, "RED DE ESTACIONES CLIMÁTICAS SELECCIONADAS Y PONDERACIÓN ESPACIAL", 12, row=1)
    stn_headers = [
        "Código", "Nombre", "Categoría", "Municipio", "Departamento", "Latitud",
        "Longitud", "Altitud (m)", "Estado", "Peso Asignado", "Variables", "Rango Años",
    ]
    for col, h in enumerate(stn_headers, start=1):
        ws_stn.cell(row=2, column=col, value=h)
    _style_header_row(ws_stn, 2, len(stn_headers))
    ws_stn.freeze_panes = "A3"
    stns = analysis.get("stations", [])
    for idx, s in enumerate(stns, start=3):
        yr_r = f"{s['years_range'][0]}-{s['years_range'][1]}" if s.get("years_range") else ""
        vals = [
            s.get("codigo"), s.get("nombre"), s.get("categoria_codigo"), s.get("municipio_nombre"),
            s.get("departamento_nombre"), s.get("latitud"), s.get("longitud"), s.get("altitud"),
            s.get("estado"), s.get("weight_norm"), ",".join(str(v) for v in s.get("available_vars", [])), yr_r,
        ]
        for col, v in enumerate(vals, start=1):
            ws_stn.cell(row=idx, column=col, value=v)
    if stns:
        end_stn = 2 + len(stns)
        _style_data_range(ws_stn, 3, end_stn, 12, num_fmt_map={6: "0.0000", 7: "0.0000", 8: "#,##0.0", 10: "0.00%"})
        ws_stn.cell(row=end_stn + 1, column=9, value="SUMA PESOS:").font = FONT_TOTAL
        c_sum = ws_stn.cell(row=end_stn + 1, column=10, value=f"=SUM(J3:J{end_stn})")
        c_sum.font = FONT_TOTAL
        c_sum.fill = TOTAL_FILL
        c_sum.border = TOTAL_BORDER
        c_sum.number_format = "0.0%"

    # =========================================================================
    # HOJA 5: Serie_Anual (con estadísticas multianuales por fórmula)
    # =========================================================================
    _banner(ws_ann, "SERIE HISTÓRICA ANUAL Y ESTADÍSTICOS MULTIANUALES", 10, row=1)
    ann_headers = ["Año", "Precipitación Total (mm)", "P. Máx 24h (mm)", "T. Media (°C)", "T. Máxima (°C)", "T. Mínima (°C)", "HR (%)", "ET0 PM (mm)", "Comp. P (%)", "Comp. T (%)"]
    for col, h in enumerate(ann_headers, start=1):
        ws_ann.cell(row=2, column=col, value=h)
    _style_header_row(ws_ann, 2, 10)
    ws_ann.freeze_panes = "B3"
    ann_rows = analysis.get("annual_summary", [])
    for idx, r in enumerate(ann_rows, start=3):
        vals = [
            r["year"], r["precip_mm"], r["pmax_24h_mm"], r["temp_mean_c"], r["temp_max_c"],
            r["temp_min_c"], r["rh_pct"], r["et0_pm_mm"], r["completeness_precip_pct"], r["completeness_temp_pct"],
        ]
        for col, v in enumerate(vals, start=1):
            ws_ann.cell(row=idx, column=col, value=v)
    if ann_rows:
        ann_end = 2 + len(ann_rows)
        _style_data_range(
            ws_ann, 3, ann_end, 10,
            num_fmt_map={2: "#,##0.0", 3: "0.0", 4: "0.00", 5: "0.0", 6: "0.0", 7: "0.0", 8: "#,##0.0", 9: "0.0", 10: "0.0"},
        )
        stat_specs = [("PROMEDIO", "AVERAGE"), ("MÁXIMO", "MAX"), ("MÍNIMO", "MIN"), ("DESV. EST.", "STDEV.S")]
        for s_off, (slbl, sfn) in enumerate(stat_specs, start=ann_end + 1):
            ws_ann.cell(row=s_off, column=1, value=slbl).font = FONT_TOTAL
            ws_ann.cell(row=s_off, column=1).fill = TOTAL_FILL
            ws_ann.cell(row=s_off, column=1).border = CELL_BORDER
            for col in range(2, 11):
                let = get_column_letter(col)
                c = ws_ann.cell(row=s_off, column=col, value=f"={sfn}({let}3:{let}{ann_end})")
                c.font = FONT_TOTAL
                c.fill = TOTAL_FILL
                c.border = CELL_BORDER
                c.number_format = "0.00" if col in (4, 5, 6) else "#,##0.0"

    # =========================================================================
    # HOJA 6: Promedios_Diarios_365
    # =========================================================================
    _banner(ws_day, "CLIMATOLOGÍA DIARIA MULTIANUAL (365 DÍAS)", 16, row=1)
    day_headers = ["Mes", "Día", "Precipitación (mm)", "Brillo Solar (h)", "HR (%)", "T. Media (°C)", "T. Mínima (°C)", "T. Máxima (°C)", "Viento (m/s)", "Rad. Solar (MJ/m²/d)", "Horas Sol (N)", "ETP (mm)", "Almacenamiento (mm)", "Exceso (mm)", "Déficit (mm)", "TMI (%)"]
    for col, h in enumerate(day_headers, start=1):
        ws_day.cell(row=2, column=col, value=h)
    _style_header_row(ws_day, 2, 16)
    ws_day.freeze_panes = "C3"
    day_rows = analysis.get("daily_climatology", [])
    for idx, r in enumerate(day_rows, start=3):
        vals = [
            r["month_abbr"], r["day"], r["precip_mm"], r["sunshine_h"], r["rh_pct"], r["temp_mean_c"],
            r["temp_min_c"], r["temp_max_c"], r["wind_ms"], r["solar_rad_mj"], r["daylight_h"],
            r.get("etp_used_mm"), r.get("storage_mm"), r.get("excess_mm"), r.get("deficit_mm"), r.get("tmi_pct"),
        ]
        for col, v in enumerate(vals, start=1):
            ws_day.cell(row=idx, column=col, value=v)
    if day_rows:
        _style_data_range(ws_day, 3, 2 + len(day_rows), 16, num_fmt_map={c: "0.00" for c in range(3, 17)})

    # =========================================================================
    # HOJA 8: Calidad_Homogeneidad_ETCCDI
    # =========================================================================
    _banner(ws_cal, "CONTROL DE CALIDAD, HOMOGENEIDAD (PETTITT), TENDENCIAS (MANN-KENDALL) E ÍNDICES ETCCDI", 6, row=1)
    for col, h in enumerate(["Variable", "Unidad", "Días Válidos", "Días Totales", "Completitud (%)", "Alertas Fuera Rango"], start=1):
        ws_cal.cell(row=2, column=col, value=h)
    _style_header_row(ws_cal, 2, 6)
    v_sum = qual.get("variable_summary", [])
    for idx, vs in enumerate(v_sum, start=3):
        ws_cal.cell(row=idx, column=1, value=vs["name"])
        ws_cal.cell(row=idx, column=2, value=vs["unit"])
        ws_cal.cell(row=idx, column=3, value=vs["valid_days"])
        ws_cal.cell(row=idx, column=4, value=vs["total_days"])
        ws_cal.cell(row=idx, column=5, value=f"=IF(D{idx}>0,100*C{idx}/D{idx},0)")
        ws_cal.cell(row=idx, column=6, value=vs["out_of_range_count"])
    if v_sum:
        _style_data_range(ws_cal, 3, 2 + len(v_sum), 6, num_fmt_map={3: "#,##0", 4: "#,##0", 5: "0.00"}, formula_cols={5})

    et_hdr = 4 + len(v_sum)
    ws_cal.cell(row=et_hdr, column=1, value="Indicador / Prueba Estadística").font = FONT_HDR
    ws_cal.cell(row=et_hdr, column=2, value="Valor / Estadístico").font = FONT_HDR
    ws_cal.cell(row=et_hdr, column=3, value="Interpretación").font = FONT_HDR
    _style_header_row(ws_cal, et_hdr, 3)

    tp = qual.get("trends", {}).get("precip_annual", {})
    tt = qual.get("trends", {}).get("temp_mean_annual", {})
    hp = qual.get("homogeneity", {}).get("precip_annual", {})
    ht = qual.get("homogeneity", {}).get("temp_mean_annual", {})
    stat_rows = [
        ("Mann-Kendall Precipitación Anual", f"Z={tp.get('z_stat', '-')}, Sen={tp.get('sen_slope_per_decade', '-')} mm/déc", tp.get("trend", tp.get("message", "N/D"))),
        ("Pettitt Homogeneidad Precipitación", f"K={hp.get('k_stat', '-')}, p={hp.get('p_value', '-')}", hp.get("status", hp.get("message", "N/D"))),
        ("Mann-Kendall Temperatura Media", f"Z={tt.get('z_stat', '-')}, Sen={tt.get('sen_slope_per_decade', '-')} °C/déc", tt.get("trend", tt.get("message", "N/D"))),
        ("Pettitt Homogeneidad Temperatura", f"K={ht.get('k_stat', '-')}, p={ht.get('p_value', '-')}", ht.get("status", ht.get("message", "N/D"))),
    ]
    for k, v in etccdi.items():
        stat_rows.append((f"ETCCDI: {k}", v, "Índice climático OMM / ETCCDI"))
    for off, (k, v, desc) in enumerate(stat_rows, start=et_hdr + 1):
        ws_cal.cell(row=off, column=1, value=k)
        ws_cal.cell(row=off, column=2, value=v)
        ws_cal.cell(row=off, column=3, value=desc)
    _style_data_range(ws_cal, et_hdr + 1, et_hdr + len(stat_rows), 3)

    # =========================================================================
    # HOJA 1: Resumen_Ejecutivo (enlazada por fórmulas hacia hojas de cálculo)
    # =========================================================================
    _banner(ws_res, f"HIDROCLIMA STUDIO v1.0.0 — RESUMEN EJECUTIVO ({proj['name']})", 3, row=1)
    for col, h in enumerate(["Parámetro / Indicador Técnico", "Valor Calculado", "Unidad / Norma / Referencia"], start=1):
        ws_res.cell(row=2, column=col, value=h)
    _style_header_row(ws_res, 2, 3)
    ws_res.freeze_panes = "A3"

    summary_items = [
        ("Nombre del Proyecto", proj["name"], ""),
        ("Ubicación", proj.get("location", ""), ""),
        ("Periodo Analizado", f"{proj['actual_year_min']} – {proj['actual_year_max']}", f"{proj['total_days_analyzed']} días analizados"),
        ("Coordenada / Altitud Ponderada", f"{proj['avg_lat']:.5f}°, {proj['avg_lon']:.5f}°", f"{proj['avg_alt']:.1f} m s.n.m."),
        ("Método ETP Seleccionado", proj["etp_method_label"], "Balance hídrico cíclico"),
        ("Reserva Máxima Suelo / Nivel Freático", "=Balance_Mensual!C2", f"mm | Nivel freático MEPDG = {proj['water_table_m']} m"),
        ("1. Temperatura Media Anual Ponderada (TMAP)", "=Pavimentos_TMAP!B19", "°C (Metodología Shell Carta W)"),
        ("2. Precipitación Media Anual (PMA)", "=Balance_Mensual!C17", "mm/año (Promedio multianual ponderado)"),
        ("3. Región Climática Pavimentos INVIAS", "=Pavimentos_TMAP!B21", tmap_reg.get("criteria", "")),
        ("ETP Media Anual", "=Balance_Mensual!O17", "mm/año"),
        ("ETR Media Anual", "=Balance_Mensual!Q17", "mm/año"),
        ("Exceso Hídrico Anual", "=Balance_Mensual!S17", "mm/año"),
        ("Déficit Hídrico Anual", "=Balance_Mensual!T17", "mm/año"),
        ("Índice Hídrico de Thornthwaite (Im 1948)", "=Balance_Mensual!U17", f"% — {summ['humidity_class']}"),
        ("Temperatura Media Anual Aritmética", "=Balance_Mensual!D17", f"°C — {summ['thermal_class']}"),
        ("Clasificación Caldas-Lang (IDEAM)", cls.get("caldas_lang", {}).get("label"), f"Factor Lang P/T = {cls.get('caldas_lang', {}).get('lang_factor')}"),
        ("Zona de Vida Holdridge", cls.get("holdridge", {}).get("life_zone"), f"EPT = {cls.get('holdridge', {}).get('ept_ratio')}"),
        ("Clasificación Köppen-Geiger", cls.get("koppen_geiger", {}).get("label"), ""),
        ("Índice de Aridez (ENA-IDEAM)", "=Balance_Mensual!C22", cls.get("ena_aridity", {}).get("category")),
        ("Temp. Máx 7 días consecutivos (Tmax)", pav.get("max_7day_tmax_c"), "°C (Base Superpave)"),
        ("Grado Superpave PG Recomendado (98 %)", pav.get("recommended_pg_grade"), "Profundidad 20 mm (LTPP)"),
        ("P24h Máxima Multianual (M)", "=IDF_Frecuencia_RAS!B3" if idf.get("available") else "N/D", f"mm (Mejor K-S: {idf.get('best_distribution', 'N/D')})"),
        ("Erosividad Pluvial Factor R (RUSLE)", "=Cuenca_RUSLE_Sequias!B23" if analysis.get("erosivity", {}).get("available") else "N/D", f"{analysis.get('erosivity', {}).get('unit', '')} — {analysis.get('erosivity', {}).get('aggressiveness_class', '')}"),
        ("Días Críticos SGC (R3 ≥ Umbral)", analysis.get("geohazards_sgc", {}).get("exceedance_days", "N/D"), f"{analysis.get('geohazards_sgc', {}).get('episodes_count', 0)} episodios críticos"),
        ("tc Kirpich / Q Racional Tr=10a", "=Cuenca_RUSLE_Sequias!G9" if analysis.get("watershed", {}).get("available") else "N/D", f"tc (min) | Tr10 Q={next((r['q_rational_m3s'] for r in analysis.get('watershed', {}).get('design_rows', []) if r['tr']==10), '-')} m³/s"),
    ]
    for idx, (lbl, val, unit) in enumerate(summary_items, start=3):
        ws_res.cell(row=idx, column=1, value=lbl)
        ws_res.cell(row=idx, column=2, value=val)
        ws_res.cell(row=idx, column=3, value=unit)
    _style_data_range(
        ws_res, 3, 2 + len(summary_items), 3,
        num_fmt_map={2: "#,##0.00"},
    )
    # Resaltar filas clave 1. TMAP, 2. PMA y 3. INVIAS
    for highlight_r in (9, 10, 11):
        for col in range(1, 4):
            ws_res.cell(row=highlight_r, column=col).fill = TOTAL_FILL
            ws_res.cell(row=highlight_r, column=col).font = FONT_TOTAL

    # =========================================================================
    # HOJA 9: Geotecnia_SGC_Lluvias (Umbrales SGC + Ventanas Móviles + SCS Infilt)
    # =========================================================================
    sgc = analysis.get("geohazards_sgc", {})
    _banner(ws_sgc, f"GEOTECNIA SGC — LLUVIAS ANTECEDENTES DETONANTES Y BALANCE INFILTRACIÓN SCS ({proj['name']})", 9, row=1)
    if sgc.get("available"):
        ws_sgc.cell(row=2, column=1, value="Intercepto R3 a (mm):").font = FONT_SUBHDR
        ws_sgc.cell(row=2, column=2, value=float(sgc.get("r3_intercept", 70.0))).font = FONT_INPUT
        ws_sgc.cell(row=2, column=3, value="Pendiente R15 b:").font = FONT_SUBHDR
        ws_sgc.cell(row=2, column=4, value=float(sgc.get("r15_slope", 0.47))).font = FONT_INPUT
        inf = sgc.get("infiltration_balance", {})
        ws_sgc.cell(row=2, column=5, value="CN II Suelo:").font = FONT_SUBHDR
        ws_sgc.cell(row=2, column=6, value=float(inf.get("cn_ii", 75.0))).font = FONT_INPUT
        ws_sgc.cell(row=2, column=7, value="S_max SCS (mm):").font = FONT_SUBHDR
        c_smax = ws_sgc.cell(row=2, column=8, value="=(25400/F2)-254")
        c_smax.font = FONT_FORMULA
        c_smax.number_format = "0.0"

        for col, h in enumerate(["Ventana Móvil SGC", "Media (mm)", "P90 (mm)", "P95 (mm)", "P99 (mm)", "Máximo (mm)", "Fecha Máximo"], start=1):
            ws_sgc.cell(row=4, column=col, value=h)
        _style_header_row(ws_sgc, 4, 7)
        r_stats = list(sgc.get("rolling_stats", {}).items())
        for idx, (w_name, st) in enumerate(r_stats, start=5):
            vals = [w_name, st.get("mean"), st.get("p90"), st.get("p95"), st.get("p99"), st.get("max"), st.get("date_max")]
            for c_i, val in enumerate(vals, start=1):
                ws_sgc.cell(row=idx, column=c_i, value=val)
        _style_data_range(ws_sgc, 5, 4 + len(r_stats), 7, num_fmt_map={2: "0.00", 3: "0.0", 4: "0.0", 5: "0.0", 6: "0.0"})

        ep_hdr = 6 + len(r_stats)
        ep_headers = ["Inicio Episodio", "Fin Episodio", "Duración (d)", "Fecha Pico", "R1 Pico (mm)", "R3 Pico (mm)", "R15 Antecedente (mm)", "Umbral R3 Fórmula (mm)", "Factor Severidad (R3/Umbral)"]
        for col, h in enumerate(ep_headers, start=1):
            ws_sgc.cell(row=ep_hdr, column=col, value=h)
        _style_header_row(ws_sgc, ep_hdr, 9)
        eps = sgc.get("episodes", [])
        for e_i, ep in enumerate(eps, start=ep_hdr + 1):
            ws_sgc.cell(row=e_i, column=1, value=ep["start_date"])
            ws_sgc.cell(row=e_i, column=2, value=ep["end_date"])
            ws_sgc.cell(row=e_i, column=3, value=ep["duration_days"])
            ws_sgc.cell(row=e_i, column=4, value=ep["peak_date"])
            ws_sgc.cell(row=e_i, column=5, value=ep["r1_peak_mm"])
            ws_sgc.cell(row=e_i, column=6, value=ep["r3_peak_mm"])
            ws_sgc.cell(row=e_i, column=7, value=ep["r15_ant_mm"])
            ws_sgc.cell(row=e_i, column=8, value=f"=MAX(5,$B$2-$D$2*G{e_i})")
            ws_sgc.cell(row=e_i, column=9, value=f"=IF(H{e_i}>0,F{e_i}/H{e_i},0)")
        if eps:
            _style_data_range(ws_sgc, ep_hdr + 1, ep_hdr + len(eps), 9, num_fmt_map={5: "0.0", 6: "0.0", 7: "0.0", 8: "0.0", 9: "0.00"}, formula_cols={8, 9})

        c_sgc = BarChart()
        c_sgc.type = "col"
        c_sgc.title = "Lluvias Máximas y Percentiles SGC (R1..R90)"
        c_sgc.y_axis.title = "Precipitación [mm]"
        c_sgc.add_data(Reference(ws_sgc, min_col=3, max_col=6, min_row=4, max_row=4 + len(r_stats)), titles_from_data=True)
        c_sgc.set_categories(Reference(ws_sgc, min_col=1, min_row=5, max_row=4 + len(r_stats)))
        c_sgc.width = 14.5
        c_sgc.height = 9.0
        ws_sgc.add_chart(c_sgc, "A" + str((ep_hdr + len(eps) + 2) if eps else (ep_hdr + 2)))
    else:
        ws_sgc.append(["Sin datos diarios suficientes para análisis geotécnico SGC"])

    # =========================================================================
    # HOJA 10: Cuenca_RUSLE_Sequias (Erosividad ANLA + Cuenca INVIAS + SPEI/IAP)
    # =========================================================================
    ero = analysis.get("erosivity", {})
    wshed = analysis.get("watershed", {})
    drg = analysis.get("drought", {})
    _banner(ws_cua, f"EROSIVIDAD RUSLE (ANLA), SEQUÍAS (SPEI/IAP) Y CUENCA INVIAS/SCS ({proj['name']})", 13, row=1)

    # Sección A (Cols A-D): Erosividad Mensual RUSLE vinculada a Balance_Mensual!C5:C16
    _banner(ws_cua, "A. EROSIVIDAD PLUVIAL RUSLE (MFI / PCI / FACTOR R)", 4, row=3, fill=TEAL_FILL)
    for col, h in enumerate(["Mes", "P Media (mm)", "p_i² (mm²)", "Aporte R (%)"], start=1):
        ws_cua.cell(row=4, column=col, value=h)
    _style_header_row(ws_cua, 4, 4)
    for idx in range(5, 17):
        r_m = idx
        ws_cua.cell(row=r_m, column=1, value=f"=Balance_Mensual!B{idx}")
        ws_cua.cell(row=r_m, column=2, value=f"=Balance_Mensual!C{idx}")
        ws_cua.cell(row=r_m, column=3, value=f"=B{r_m}^2")
        ws_cua.cell(row=r_m, column=4, value=f"=IF($C$17>0,100*C{r_m}/$C$17,0)")
    _style_data_range(ws_cua, 5, 16, 4, num_fmt_map={2: "#,##0.0", 3: "#,##0.0", 4: "0.0"}, formula_cols={3, 4}, link_cols={1, 2})

    ws_cua.cell(row=17, column=1, value="TOTAL ANUAL").font = FONT_TOTAL
    ws_cua.cell(row=17, column=2, value="=SUM(B5:B16)")
    ws_cua.cell(row=17, column=3, value="=SUM(C5:C16)")
    ws_cua.cell(row=17, column=4, value="=SUM(D5:D16)")
    for c_i in range(1, 5):
        cell = ws_cua.cell(row=17, column=c_i)
        cell.fill = TOTAL_FILL
        cell.font = FONT_TOTAL
        cell.border = TOTAL_BORDER
        if c_i in (2, 3):
            cell.number_format = "#,##0.0"
        elif c_i == 4:
            cell.number_format = "0.0"

    ero_kpis = [
        (19, "Índice de Fournier Clásico (FI)", "=IF(B17>0,MAX(C5:C16)/B17,0)", "0.00"),
        (20, "Índice de Fournier Modificado (MFI)", "=IF(B17>0,C17/B17,0)", "0.00"),
        (21, "Índice Concentración PCI (%)", "=IF(B17>0,100*C17/(B17^2),0)", "0.00"),
        (22, "Clase Agresividad Climática", ero.get("aggressiveness_class", "-"), "@"),
        (23, "Factor R RUSLE (Renard & Freimund)", "=IF(B20<55,0.7397*B20^1.847,95.77-6.081*B20+0.477*B20^2)", "#,##0.0"),
    ]
    for r_k, lbl, formula_v, nfmt in ero_kpis:
        ws_cua.cell(row=r_k, column=1, value=lbl).font = FONT_SUBHDR
        c_v = ws_cua.cell(row=r_k, column=2, value=formula_v)
        c_v.font = FONT_TOTAL if r_k == 23 else FONT_FORMULA
        if r_k == 23:
            c_v.fill = TOTAL_FILL
        c_v.border = CELL_BORDER
        c_v.number_format = nfmt

    # Sección B (Cols F-L): Cuenca Hidrográfica INVIAS / Racional / SCS-CN con fórmulas
    ws_cua.cell(row=3, column=6, value="B. CUENCA HIDROGRÁFICA INVIAS (KIRPICH / RACIONAL / SCS-CN)")
    ws_cua.merge_cells("F3:L3")
    for c_i in range(6, 13):
        cc = ws_cua.cell(row=3, column=c_i)
        cc.fill = TEAL_FILL
        cc.font = FONT_HDR
        cc.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    if wshed.get("available"):
        ws_inputs = [
            (4, "Área Cuenca A (km²)", wshed["area_km2"], "0.000", True),
            (5, "Longitud Cauce L (m)", wshed["length_m"], "#,##0.0", True),
            (6, "Pendiente S (%)", wshed["slope_pct"], "0.00", True),
            (7, "Número de Curva CN", wshed["curve_number"], "0.0", True),
            (8, "Coef. Escorrentía C", wshed["runoff_coeff"], "0.00", True),
            (9, "tc Kirpich (min)", "=MAX(5,0.01947*(G5^0.77)*((G6/100)^-0.385))", "0.00", False),
            (10, "tc Témez (min)", "=MAX(5,60*0.3*((G5/1000)/((G6/100)^0.25))^0.76)", "0.00", False),
            (11, "Retención S_max (mm)", "=(25400/G7)-254", "0.0", False),
            (12, "Abstracción Ia (mm)", "=0.2*G11", "0.0", False),
        ]
        for rr, lbl, val, nfmt, is_in in ws_inputs:
            ws_cua.cell(row=rr, column=6, value=lbl).font = FONT_SUBHDR
            cv = ws_cua.cell(row=rr, column=7, value=val)
            cv.font = FONT_INPUT if is_in else FONT_FORMULA
            cv.border = CELL_BORDER
            cv.number_format = nfmt

        wh_hdr = 14
        wh_cols = ["Tr (años)", "I(tc) mm/h", "Q Racional (m³/s)", "P Tormenta (mm)", "Qe SCS (mm)", "Infilt F (mm)", "Q Pico SCS (m³/s)"]
        for off, h in enumerate(wh_cols):
            c_wh = ws_cua.cell(row=wh_hdr, column=6 + off, value=h)
            c_wh.fill = NAVY_FILL
            c_wh.font = FONT_HDR
            c_wh.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c_wh.border = CELL_BORDER
        ws_cua.row_dimensions[wh_hdr].height = 26

        d_rows = wshed.get("design_rows", [])
        for r_i, dr in enumerate(d_rows, start=wh_hdr + 1):
            ws_cua.cell(row=r_i, column=6, value=dr["tr"])
            ws_cua.cell(row=r_i, column=7, value=dr["i_tc_mmh"])
            ws_cua.cell(row=r_i, column=8, value=f"=($G$8*G{r_i}*$G$4)/3.6")
            ws_cua.cell(row=r_i, column=9, value=dr["p_storm_mm"])
            ws_cua.cell(row=r_i, column=10, value=f"=IF(I{r_i}>$G$12,((I{r_i}-$G$12)^2)/(I{r_i}-$G$12+$G$11),0)")
            ws_cua.cell(row=r_i, column=11, value=f"=MAX(0,I{r_i}-MIN(I{r_i},$G$12)-J{r_i})")
            ws_cua.cell(row=r_i, column=12, value=dr["q_scs_m3s"])
        _style_data_range(ws_cua, wh_hdr + 1, wh_hdr + len(d_rows), 12, num_fmt_map={7: "0.00", 8: "0.000", 9: "0.00", 10: "0.00", 11: "0.00", 12: "0.000"}, formula_cols={8, 10, 11})

    # Sección C: Anomalías Anuales IAP IDEAM (abajo desde fila 25)
    iap_list = drg.get("iap_annual", [])
    if iap_list:
        iap_hdr = 25
        for c_i, h in enumerate(["Año", "P Anual (mm)", "IAP (% Media)", "Anomalía (%)", "Clasificación IDEAM"], start=1):
            ws_cua.cell(row=iap_hdr, column=c_i, value=h)
        _style_header_row(ws_cua, iap_hdr, 5)
        iap_start = iap_hdr + 1
        iap_end = iap_start + len(iap_list) - 1
        for i_k, ir in enumerate(iap_list, start=iap_start):
            ws_cua.cell(row=i_k, column=1, value=ir["year"])
            ws_cua.cell(row=i_k, column=2, value=ir["precip_mm"])
            ws_cua.cell(row=i_k, column=3, value=f"=100*B{i_k}/AVERAGE($B${iap_start}:$B${iap_end})")
            ws_cua.cell(row=i_k, column=4, value=f"=C{i_k}-100")
            ws_cua.cell(row=i_k, column=5, value=ir["category"])
        _style_data_range(ws_cua, iap_start, iap_end, 5, num_fmt_map={2: "#,##0.0", 3: "0.0", 4: "0.0"}, formula_cols={3, 4})

    if ero.get("available"):
        c_ero = BarChart()
        c_ero.type = "col"
        c_ero.title = "Aporte Mensual Factor R RUSLE (%)"
        c_ero.y_axis.title = "Participación [%]"
        c_ero.add_data(Reference(ws_cua, min_col=4, min_row=4, max_row=16), titles_from_data=True)
        c_ero.set_categories(Reference(ws_cua, min_col=1, min_row=5, max_row=16))
        c_ero.width = 13.5
        c_ero.height = 8.5
        ws_cua.add_chart(c_ero, "N3")

    for ws in (ws_res, ws_stn, ws_bal, ws_pav, ws_ann, ws_day, ws_idf, ws_cal, ws_sgc, ws_cua):
        _autofit_sheet(ws)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
