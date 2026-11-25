"""Generador de suite de 4 manuales técnicos oficiales en PDF para HidroClima Studio."""

from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from hidroclima.config import BASE_DIR, BUNDLE_DIR, DATA_DIR, SAMPLE_DIR, STATIC_DIR

if "MPLCONFIGDIR" not in os.environ:
    _mpl_cache = DATA_DIR.parent / ".cache" / "matplotlib"
    try:
        _mpl_cache.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(_mpl_cache)
    except OSError:
        pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fpdf import FPDF
from fpdf.enums import Align, TableBordersLayout
from fpdf.fonts import FontFace
from PIL import Image

from hidroclima.exports.brand_assets import generate_brand_assets
from hidroclima.exports.charts_mpl import (
    render_annual_trends_png,
    render_climograph_png,
    render_hyetograph_png,
    render_idf_curves_png,
    render_sgc_thresholds_png,
    render_spei_drought_png,
    render_water_balance_png,
)


def _find_fonts() -> tuple[str | None, str | None, str | None]:
    mpl_ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    reg = mpl_ttf / "DejaVuSans.ttf"
    bold = mpl_ttf / "DejaVuSans-Bold.ttf"
    ital = mpl_ttf / "DejaVuSans-Oblique.ttf"
    if reg.exists() and bold.exists():
        return str(reg), str(bold), str(ital) if ital.exists() else None
    return None, None, None


def _render_eq_png(latex_expr: str) -> tuple[bytes, float, float]:
    """Renderiza una ecuación matemática LaTeX limpia mediante matplotlib mathtext (STIX)."""
    old_fontset = plt.rcParams.get("mathtext.fontset", "dejavusans")
    plt.rcParams["mathtext.fontset"] = "stix"
    fig = plt.figure(figsize=(6.8, 0.9), dpi=280)
    fig.patch.set_facecolor("#ffffff")
    txt = fig.text(0.5, 0.5, f"${latex_expr}$", fontsize=11.5, ha="center", va="center", color="#0f172a")
    fig.canvas.draw()
    bbox = txt.get_window_extent(renderer=fig.canvas.get_renderer())
    pad = 8
    w_in = max(1.2, (bbox.width + 2 * pad) / 280.0)
    h_in = max(0.32, (bbox.height + 2 * pad) / 280.0)
    plt.close(fig)

    fig2 = plt.figure(figsize=(w_in, h_in), dpi=280)
    fig2.patch.set_facecolor("#ffffff")
    fig2.text(0.5, 0.5, f"${latex_expr}$", fontsize=11.5, ha="center", va="center", color="#0f172a")
    buf = io.BytesIO()
    fig2.savefig(buf, format="png", dpi=280, facecolor="#ffffff")
    plt.close(fig2)
    plt.rcParams["mathtext.fontset"] = old_fontset
    buf.seek(0)
    raw = buf.read()
    with Image.open(io.BytesIO(raw)) as im:
        pw, ph = im.size
    mm_w = (pw / 280.0) * 25.4
    mm_h = (ph / 280.0) * 25.4
    return raw, mm_w, mm_h


def _latin_roman(n: int) -> str:
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    res = ""
    for v, sym in vals:
        while n >= v:
            res += sym
            n -= v
    return res or "I"


class ManualBookPDF(FPDF):
    """Libro técnico multipágina con portada geométrica, tabla de contenido y capítulos."""

    def __init__(self, doc_subtitle: str, logo_mark: Path, logo_lockup: Path) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc_subtitle = doc_subtitle
        self.logo_mark = logo_mark
        self.logo_lockup = logo_lockup
        self.mode = "cover"  # cover | toc | body
        self.current_chapter_label = ""
        self.toc_entries: list[tuple[int, str, str, int]] = []  # (level, num, title, body_page_no)
        self.toc_page_count = 1
        self.show_running_header = True

        reg, bold, ital = _find_fonts()
        self.has_italic = False
        if reg and bold:
            self.add_font("UniFont", "", reg)
            self.add_font("UniFont", "B", bold)
            if ital:
                self.add_font("UniFont", "I", ital)
                self.has_italic = True
            self.fam = "UniFont"
        else:
            self.fam = "Helvetica"
            self.has_italic = True
        self.set_auto_page_break(auto=True, margin=18)

    def _s(self, txt: Any) -> str:
        s = str(txt if txt is not None else "")
        return s.encode("latin-1", errors="replace").decode("latin-1") if self.fam == "Helvetica" else s

    def header(self) -> None:
        if self.mode == "cover":
            return
        if self.mode == "toc":
            self.set_font(self.fam, "", 9.0)
            self.set_text_color(71, 85, 105)
            roman = _latin_roman(max(1, self.page_no() - 1))
            self.cell(0, 6, self._s(f"Tabla de Contenido   |   {roman}"), align="R")
            self.ln(10)
            return
        if not self.show_running_header:
            self.show_running_header = True
            return
        body_pg = self.page_no() - 1 - self.toc_page_count
        self.set_font(self.fam, "", 8.2)
        self.set_text_color(100, 116, 139)
        self.cell(125, 5.5, self._s(self.current_chapter_label), align="L")
        self.cell(0, 5.5, self._s(f"HidroClima Studio v1.0.0   |   {max(1, body_pg)}"), align="R")
        self.ln(6)
        self.set_draw_color(203, 213, 225)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        if self.mode == "cover" or self.page_no() == 1:
            return
        if self.mode == "toc":
            self.set_y(-13)
            self.set_font(self.fam, "", 8.0)
            self.set_text_color(100, 116, 139)
            self.cell(0, 6, self._s("Tabla de Contenido  |  HidroClima Studio"), align="R")
            return
        self.set_y(-13)
        self.set_font(self.fam, "", 7.8)
        self.set_text_color(120, 132, 148)
        self.cell(120, 6, self._s(f"HidroClima Studio v1.0.0  •  {self.doc_subtitle}"), align="L")
        body_pg = self.page_no() - 1 - self.toc_page_count
        self.cell(0, 6, self._s(f"Página {max(1, body_pg)}"), align="R")

    def render_cover(self, code_tag: str, main_title: str, subtitle_lines: list[str]) -> None:
        self.mode = "cover"
        self.set_margins(0, 0, 0)
        self.set_auto_page_break(False)
        self.add_page()

        # Barra superior gris neutra de portada
        self.set_fill_color(160, 166, 174)
        self.rect(0, 0, 210, 8, "F")

        # Panel izquierdo gris suave (#EAECEF) y panel derecho blanco (#FFFFFF)
        self.set_fill_color(234, 236, 239)
        self.rect(0, 8, 133, 238, "F")
        self.set_fill_color(255, 255, 255)
        self.rect(133, 8, 77, 238, "F")

        # Títulos de portada en panel izquierdo
        self.set_xy(20, 34)
        self.set_text_color(15, 23, 42)
        self.set_font(self.fam, "B", 20)
        self.multi_cell(104, 9.5, self._s("HIDROCLIMA STUDIO\nv1.0.0"), align="L")

        line_y = self.get_y() + 4
        self.set_draw_color(100, 116, 139)
        self.set_line_width(0.5)
        self.line(20, line_y, 76, line_y)

        self.set_xy(20, line_y + 5)
        self.set_font(self.fam, "", 18.5)
        self.set_text_color(30, 41, 59)
        self.multi_cell(105, 9.0, self._s(main_title), align="L")

        self.set_xy(20, self.get_y() + 6)
        self.set_font(self.fam, "", 10.5)
        self.set_text_color(71, 85, 105)
        for line in subtitle_lines:
            self.set_x(20)
            self.multi_cell(104, 5.8, self._s(line), align="L")

        # Emblema geométrico en panel derecho blanco
        if self.logo_mark.exists():
            self.image(str(self.logo_mark), x=153, y=35, w=38)

        # Código y fecha al pie del panel blanco derecho
        self.set_xy(136, 224)
        self.set_font(self.fam, "", 9.2)
        self.set_text_color(71, 85, 105)
        self.multi_cell(64, 5, self._s(f"Código: {code_tag}\nEdición: {datetime.now().strftime('%Y-%m')}"), align="R")

        # Banda inferior sólida oscura (#0B192C) con logo lockup
        self.set_fill_color(11, 25, 44)
        self.rect(0, 246, 210, 51, "F")
        if self.logo_lockup.exists():
            self.image(str(self.logo_lockup), x=16, y=253, w=118)

        self.set_xy(135, 281)
        self.set_font(self.fam, "", 7.5)
        self.set_text_color(148, 163, 184)
        self.cell(62, 5, self._s("© HidroClima Studio · Licencia MIT · Software Abierto"), align="R")

        self.set_margins(18, 18, 18)
        self.set_auto_page_break(True, margin=18)

    def render_toc_pages(self, entries: list[tuple[int, str, str, int]], toc_page_count: int) -> None:
        self.mode = "toc"
        self.toc_page_count = toc_page_count
        self.add_page()

        self.set_font(self.fam, "B", 24)
        self.set_text_color(15, 23, 42)
        self.cell(0, 12, self._s("Contenido"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(8)

        for lvl, num, title, rel_pg in entries:
            true_pg = rel_pg
            if self.get_y() > 266:
                self.add_page()
            if lvl == 1:
                self.ln(2.5)
                self.set_font(self.fam, "B", 11.2)
                self.set_text_color(15, 23, 42)
                indent = 0
            elif lvl == 2:
                self.set_font(self.fam, "", 9.4)
                self.set_text_color(30, 41, 59)
                indent = 8
            else:
                self.set_font(self.fam, "", 8.6)
                self.set_text_color(71, 85, 105)
                indent = 16

            label = f"{num}  {title}".strip()
            pg_str = str(true_pg)
            self.set_x(18 + indent)
            usable_w = 174 - indent
            lbl_w = self.get_string_width(self._s(label))
            pg_w = self.get_string_width(pg_str) + 4
            dots_w = max(8.0, usable_w - lbl_w - pg_w - 2)
            dot_w = self.get_string_width(".")
            dots = "." * max(3, int(dots_w / max(0.5, dot_w)))
            self.cell(usable_w - pg_w, 5.4 if lvl == 1 else 4.7, self._s(f"{label} {dots}"), align="L")
            self.cell(pg_w, 5.4 if lvl == 1 else 4.7, pg_str, align="R", new_x="LMARGIN", new_y="NEXT")

    def chapter_page(self, num: str, title: str) -> None:
        self.mode = "body"
        self.show_running_header = False
        self.current_chapter_label = f"{num}  {title}"
        self.add_page()

        # Banda superior de capítulo (#E2E5E9)
        self.set_fill_color(226, 229, 233)
        self.rect(0, 0, 210, 74, "F")

        # Número gigante blanco translúcido a la derecha
        self.set_font(self.fam, "B", 84)
        self.set_text_color(255, 255, 255)
        self.set_xy(135, 10)
        self.cell(57, 40, self._s(num), align="R")

        # Barra divisoria inferior de capítulo
        self.set_fill_color(148, 163, 184)
        self.rect(0, 74, 210, 2.2, "F")

        self.set_xy(18, 52)
        self.set_font(self.fam, "B", 16.0)
        self.set_text_color(15, 23, 42)
        self.multi_cell(174, 8.8, self._s(title), align="R")

        body_pg = self.page_no() - 1 - self.toc_page_count
        self.toc_entries.append((1, num, title, max(1, body_pg)))
        self.set_y(84)

    def section(self, num: str, title: str) -> None:
        if self.get_y() > 252:
            self.add_page()
        self.ln(4.5)
        body_pg = self.page_no() - 1 - self.toc_page_count
        self.toc_entries.append((2, num, title, max(1, body_pg)))

        self.set_font(self.fam, "B", 13.5)
        self.set_text_color(15, 23, 42)
        num_w = self.get_string_width(self._s(num)) + 3
        self.cell(num_w, 7, self._s(num), align="L")
        # Separador vertical sutil (idéntico a 1.1 | Preface)
        x_bar = self.get_x() + 1.5
        y_top = self.get_y() + 0.8
        self.set_draw_color(148, 163, 184)
        self.line(x_bar, y_top, x_bar, y_top + 5.2)
        self.set_x(x_bar + 4)
        self.multi_cell(0, 7, self._s(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def subsection(self, num: str, title: str) -> None:
        if self.get_y() > 258:
            self.add_page()
        self.ln(2.5)
        body_pg = self.page_no() - 1 - self.toc_page_count
        self.toc_entries.append((3, num, title, max(1, body_pg)))
        self.set_font(self.fam, "B", 10.6)
        self.set_text_color(14, 116, 144)
        self.multi_cell(0, 5.8, self._s(f"{num}   {title}"), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def para(self, text: str) -> None:
        self.set_font(self.fam, "", 9.4)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 5.0, self._s(text), align="J", new_x="LMARGIN", new_y="NEXT")
        self.ln(1.8)

    def bullets(self, items: list[str]) -> None:
        self.set_font(self.fam, "", 9.2)
        self.set_text_color(30, 41, 59)
        for item in items:
            self.set_x(22)
            self.cell(4, 4.9, "•")
            self.multi_cell(165, 4.9, self._s(item), new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

    def callout(self, title: str, text: str, kind: str = "warn") -> None:
        if self.get_y() > 240:
            self.add_page()
        bg = (254, 243, 199) if kind == "warn" else (239, 246, 255)
        border = (217, 119, 6) if kind == "warn" else (37, 99, 235)
        hdr_c = (146, 64, 14) if kind == "warn" else (30, 64, 175)
        self.set_font(self.fam, "", 8.8)
        # Estimar alto de caja
        lines = self.multi_cell(162, 4.7, self._s(text), dry_run=True, output="LINES")
        box_h = 10.5 + len(lines) * 4.7 + 4
        if self.get_y() + box_h > 274:
            self.add_page()
        y0 = self.get_y()
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        self.set_line_width(0.45)
        self.rect(18, y0, 174, box_h, "DF")
        self.set_xy(23, y0 + 3)
        self.set_font(self.fam, "B", 9.5)
        self.set_text_color(*hdr_c)
        prefix = "▲ " if kind == "warn" else "ℹ "
        self.cell(0, 5.2, self._s(prefix + title), new_x="LMARGIN", new_y="NEXT")
        self.set_xy(23, y0 + 9.2)
        self.set_font(self.fam, "", 8.8)
        self.set_text_color(30, 41, 59)
        self.multi_cell(164, 4.7, self._s(text), new_x="LMARGIN", new_y="NEXT")
        self.set_y(y0 + box_h + 4)

    def equation(self, latex_expr: str, eq_num: str) -> None:
        raw, mm_w, mm_h = _render_eq_png(latex_expr)
        scale = min(1.0, 145.0 / max(1.0, mm_w))
        disp_w = mm_w * scale
        disp_h = mm_h * scale
        if self.get_y() + disp_h + 6 > 272:
            self.add_page()
        y0 = self.get_y() + 1.5
        x_img = 18.0 + max(0.0, (152.0 - disp_w) / 2.0)
        self.image(io.BytesIO(raw), x=x_img, y=y0, w=disp_w)
        self.set_xy(172, y0 + disp_h / 2.0 - 2.5)
        self.set_font(self.fam, "", 9.0)
        self.set_text_color(71, 85, 105)
        self.cell(20, 5, self._s(f"({eq_num})"), align="R")
        self.set_y(y0 + disp_h + 3.5)

    def table_block(
        self,
        headers: list[str],
        rows: list[list[Any]],
        col_widths: tuple[float, ...],
        col_aligns: list[Align] | None = None,
        font_size: float = 7.8,
    ) -> None:
        self.set_font(self.fam, "", font_size)
        self.set_draw_color(203, 213, 225)
        hdr_style = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=(15, 23, 42), size_pt=font_size)
        odd_style = FontFace(color=(15, 23, 42), fill_color=(248, 250, 252), size_pt=font_size)
        evn_style = FontFace(color=(15, 23, 42), fill_color=(255, 255, 255), size_pt=font_size)
        with self.table(
            col_widths=col_widths,
            width=174,
            line_height=4.4,
            padding=(1.2, 1.8),
            borders_layout=TableBordersLayout.ALL,
            headings_style=hdr_style,
            text_align=col_aligns or Align.L,
        ) as tbl:
            r0 = tbl.row()
            for h in headers:
                r0.cell(self._s(h))
            for r_i, row_vals in enumerate(rows):
                r = tbl.row(style=odd_style if r_i % 2 == 1 else evn_style)
                for val in row_vals:
                    r.cell(self._s(val))
        self.ln(3)

    def figure(self, png_bytes: bytes, caption: str, width: float = 170) -> None:
        if self.get_y() > 175:
            self.add_page()
        x0 = 18.0 + (174.0 - width) / 2.0
        self.image(io.BytesIO(png_bytes), x=x0, w=width)
        self.ln(1.5)
        self.set_font(self.fam, "I" if self.has_italic else "", 8.2)
        self.set_text_color(71, 85, 105)
        self.multi_cell(0, 4.5, self._s(caption), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)


def _compile_two_pass(
    code_tag: str,
    main_title: str,
    subtitle_lines: list[str],
    doc_subtitle: str,
    logo_mark: Path,
    logo_lockup: Path,
    body_fn: Callable[[ManualBookPDF], None],
) -> bytes:
    """Compila un manual en dos pasadas para garantizar Tabla de Contenido con numeración exacta."""
    # Pasada 1: medir TOC y números de página relativos
    p1 = ManualBookPDF(doc_subtitle, logo_mark, logo_lockup)
    p1.toc_page_count = 1
    p1.render_cover(code_tag, main_title, subtitle_lines)
    p1.mode = "toc"
    p1.add_page()
    body_fn(p1)
    entries = list(p1.toc_entries)

    # Estimar páginas reales requeridas para TOC
    p_measure = ManualBookPDF(doc_subtitle, logo_mark, logo_lockup)
    p_measure.render_cover(code_tag, main_title, subtitle_lines)
    p_measure.render_toc_pages(entries, toc_page_count=1)
    actual_toc_pages = p_measure.page_no() - 1

    # Pasada final con offset exacto
    pf = ManualBookPDF(doc_subtitle, logo_mark, logo_lockup)
    pf.render_cover(code_tag, main_title, subtitle_lines)
    pf.render_toc_pages(entries, toc_page_count=actual_toc_pages)
    body_fn(pf)
    return bytes(pf.output())


def _sample_bogota_analysis() -> dict[str, Any] | None:
    """Ejecuta el proyecto demostrativo Bogotá D.C. sobre una BD temporal para incluir cifras reales."""
    import tempfile
    from hidroclima.analysis.engine import run_project_analysis
    from hidroclima.db.database import ClimateDatabase
    from hidroclima.db.legacy_importer import parse_project_file

    cli_p = SAMPLE_DIR / "Ejemplo_Bogota.hclim"
    if not cli_p.exists():
        return None
    cfg = parse_project_file(cli_p.read_text(encoding="utf-8", errors="replace"))
    cfg.update({
        "end_year": 2025,
        "last_n_years": 0,
        "etp_method": "penman_monteith",
        "idf_method": "invias",
        "hyetograph_tr": 10,
        "hyetograph_duration_min": 60,
        "watershed_area_km2": 1.2,
        "watershed_length_m": 950.0,
        "watershed_slope_pct": 6.5,
        "curve_number": 75.0,
        "runoff_coeff": 0.52,
    })
    with tempfile.TemporaryDirectory() as tmpd:
        db = ClimateDatabase(Path(tmpd) / "manual_demo.db")
        return run_project_analysis(db, cfg)


def generate_all_manuals(out_dir: Path | None = None, analysis_demo: dict[str, Any] | None = None) -> dict[str, Path]:
    """Genera los 4 manuales técnicos oficiales en docs/manuals/."""
    assets = generate_brand_assets(STATIC_DIR)
    logo_mark = assets["logo_mark_light.png"]
    logo_lockup = assets["logo_lockup_dark.png"]

    target_dir = out_dir or (BASE_DIR / "docs" / "manuals")
    target_dir.mkdir(parents=True, exist_ok=True)
    demo = analysis_demo if analysis_demo and analysis_demo.get("has_data") else _sample_bogota_analysis()

    out_paths: dict[str, Path] = {}

    # =========================================================================
    # MANUAL 1: INFORMACIÓN GENERAL
    # =========================================================================
    def _build_m1(pdf: ManualBookPDF) -> None:
        pdf.chapter_page("1", "Introducción")
        pdf.section("1.1", "Propósito del Software y Alcance Multidisciplinario")
        pdf.para(
            "HidroClima Studio es una suite de escritorio concebida para ingeniería civil, hidrología, hidráulica vial, "
            "geotecnia, gestión ambiental y diseño de pavimentos. Centraliza la adquisición de series diarias desde fuentes "
            "abiertas oficiales y satelitales, la ponderación espacial sobre corredores viales, el modelado climático e "
            "hidrológico normativo y la emisión automatizada de memorias de cálculo e insumos para modelación externa."
        )
        pdf.bullets([
            "Consultoría de Drenaje y Hidrología (RAS Res. 0330/2017 e INVIAS): frecuencia de máximos 24h, 4 metodologías IDF, Bloques Alternos, hidrogramas SCS-CN y Método Racional.",
            "Ingeniería de Pavimentos (INVIAS / Shell / Superpave / MEPDG): Temperatura Media Anual Ponderada (1. TMAP), Precipitación Media Anual (2. PMA), zonificación R1–R6 y grado asfáltico Superpave PG.",
            "Geotecnia y Amenaza (Guías SGC): lluvias antecedentes acumuladas (R1 a R90 días), envolvente empírica detonante R3–R15 e infiltración diaria SCS.",
            "Estudios Ambientales (EIA ANLA / ENA-IDEAM / UNGRD): Penman-Monteith FAO-56, Caldas-Lang, Holdridge, Köppen-Geiger, erosividad pluvial RUSLE (MFI, PCI, Factor R) y sequías SPEI / IAP.",
        ])

        pdf.section("1.2", "Aviso de Responsabilidad Técnica")
        pdf.callout(
            "Responsabilidad Profesional del Ingeniero",
            "HidroClima Studio implementa formulaciones científicas estándar y normativas colombianas vigentes bajo controles "
            "estrictos de calidad. No obstante, la validez de cualquier diseño geotécnico, hidráulico o estructural depende de "
            "la verificación crítica de las series históricas, la representatividad de las estaciones y el criterio ingenieril "
            "del profesional responsable.",
            kind="warn",
        )

        pdf.chapter_page("2", "Arquitectura, Fuentes de Datos y Licencia")
        pdf.section("2.1", "Software Abierto y Fuentes Públicas de Información")
        pdf.para(
            "HidroClima Studio es un software gratuito de código abierto distribuido bajo licencia MIT, sin suscripciones "
            "comerciales ni claves de acceso restringidas. El programa funciona de forma local con un catálogo nacional precargado "
            "de 8.973 estaciones y sincroniza series recientes directamente contra repositorios científicos y públicos abiertos:"
        )
        pdf.table_block(
            ["Proveedor", "Cobertura y Variables", "Protocolo / Acceso", "Prioridad"],
            [
                ["Editor Matriz 12×31", "Edición manual directa en escritorio", "SQLite Local (WAL)", "1 (Máxima)"],
                ["IDEAM DHIME (.csv/.xlsx)", "Series oficiales descargadas del portal IDEAM", "Importador Local", "2"],
                ["Datos Abiertos (datos.gov.co)", "Catálogo, tiempo real (57sv-p2fu) y automáticas", "API Socrata (Abierta)", "3"],
                ["Archivo Histórico / .dat / .hclim", "Paquetes locales (.zip, .rar, SHC/*.dat)", "Importador Multi-hilo", "4–5"],
                ["NASA POWER & Open-Meteo", "Reanálisis diario hasta hoy (Rs, Viento, T, P, HR)", "API REST Abierta", "6–7"],
            ],
            col_widths=(44, 62, 42, 26),
        )

        pdf.section("2.2", "Resumen de Módulos y Capacidades")
        pdf.bullets([
            "Mapa GIS interactivo (Leaflet + MarkerCluster) con carga de corredores KML, KMZ, GeoJSON y dibujo directo en pantalla.",
            "Almacenamiento binario comprimido (zlib 12 meses × 31 días en float32) en SQLite con historial auditado.",
            "17 formatos de exportación: PDF técnico multipágina, Word (.docx), Excel formulado de 10 hojas (.xlsx), SWMM/HEC-HMS CSV, MEPDG XML/TXT, GeoJSON, KML, TXT, .hclim y 7 PNGs 240 DPI.",
        ])

        pdf.chapter_page("3", "Instalación y Requisitos del Sistema")
        pdf.section("3.1", "Requisitos Mínimos y Recomendados")
        pdf.table_block(
            ["Componente", "Requisito Mínimo", "Recomendado para Series Masivas"],
            [
                ["Sistema Operativo", "Windows 10 (64 bits)", "Windows 10 / 11 (64 bits)"],
                ["Procesador y RAM", "Intel Core i3 / AMD Ryzen 3 · 4 GB RAM", "Core i5+ / 8+ GB RAM"],
                ["Espacio en Disco", "280 MB libres", "1 GB libre (para importaciones SHC masivas)"],
                ["Conectividad", "Opcional (modo 100% offline soportado)", "Internet para puentes IDEAM / ERA5 / NASA"],
            ],
            col_widths=(44, 62, 68),
        )

        pdf.section("3.2", "Instalador Windows (Setup.exe) vs Versión Portable (.zip)")
        pdf.para(
            "El instalador HidroClimaStudio-Setup-1.0.0.exe permite instalación por usuario (%LOCALAPPDATA%\\Programs\\HidroClima Studio) "
            "sin exigir privilegios administrativos, crea accesos directos en Escritorio y Menú Inicio e incluye desinstalador estándar. "
            "La base de datos de trabajo persiste en %LOCALAPPDATA%\\HidroClimaStudio\\data\\hidroclima.db separada del programa."
        )
        pdf.para(
            "En la distribución portable (.zip), basta descomprimir en cualquier carpeta con permisos de escritura y ejecutar "
            "HidroClimaStudio.exe; la base hidroclima.db se crea localmente en la subcarpeta data/ junto al ejecutable."
        )

        pdf.chapter_page("4", "Licencias de Terceros y Créditos")
        pdf.section("4.1", "Licencia MIT y Componentes de Código Abierto")
        pdf.para(
            "HidroClima Studio se distribuye bajo licencia MIT. Emplea bibliotecas científicas y visuales abiertas de primer nivel: "
            "Python 3.11, FastAPI, NumPy, Pandas, SciPy, Matplotlib, FPDF2, python-docx, OpenPyXL, pywebview, Apache ECharts y Leaflet."
        )

    out_paths["informacion_general"] = target_dir / "01_Manual_Informacion_General.pdf"
    out_paths["informacion_general"].write_bytes(
        _compile_two_pass(
            "HC-DOC-01",
            "Manual de\nInformación General",
            ["Arquitectura del sistema, puentes de datos", "abiertos, instalación en Windows y módulos."],
            "Manual de Información General",
            logo_mark,
            logo_lockup,
            _build_m1,
        )
    )

    # =========================================================================
    # MANUAL 2: MANUAL TUTORIAL Y CASOS PRÁCTICOS
    # =========================================================================
    def _build_m2(pdf: ManualBookPDF) -> None:
        pdf.chapter_page("1", "Caso Práctico Integral: Corredor Bogotá D.C.")
        pdf.section("1.1", "Objetivo y Estaciones Seleccionadas")
        pdf.para(
            "Este tutorial guía paso a paso el análisis hidrometeorológico, ambiental, geotécnico y de pavimentos sobre el "
            "corredor Bogotá D.C. (Aeropuerto El Dorado – Cerros Orientales), combinando las estaciones 21205791 "
            "(ELDORADO CATAM - AUT, 2.548 m) y 21205580 (VENADO ORO VIVERO, 2.725 m) incluidas en el proyecto demostrativo "
            "Ejemplo_Bogota.hclim."
        )
        pdf.bullets([
            "Paso 1: En la pestaña 1. Área GIS, haz clic en 'Cargar Ejemplo Bogotá' en el panel Parámetros de Simulación.",
            "Paso 2: Verifica en el mapa Leaflet la ubicación del corredor y las estaciones ponderadas (50% – 50% o ajusta mediante IDW/Thiessen).",
            "Paso 3: En Enfoque del Estudio selecciona 'Integral Multidisciplinario', método ETP 'Penman - Monteith (FAO-56)' e IDF 'INVIAS Regionalizado'.",
            "Paso 4: Presiona ▶ Calcular Análisis (o Ctrl+Enter).",
        ])

        if demo:
            s = demo["summary"]
            pav = demo["pavement"]
            ero = demo.get("erosivity", {})
            sgc = demo.get("geohazards_sgc", {})
            ws = demo.get("watershed", {})
            pdf.section("1.2", "Interpretación de Resultados Climáticos y Balance Hídrico")
            pdf.table_block(
                ["Indicador Calculado", "Valor Demostrativo Bogotá D.C.", "Criterio / Referencia"],
                [
                    ["1. TMAP (Shell Carta W)", f"{pav.get('tmap_c')} °C", f"INVIAS Región {pav['invias_pavement_region']['code']} ({pav['invias_pavement_region']['name']})"],
                    ["2. PMA (Precip. Media Anual)", f"{s['annual_precip_mm']:,.1f} mm/año", f"Exceso {s['annual_excess_mm']:,.1f} mm | Déficit {s['annual_deficit_mm']:.1f} mm"],
                    ["ETP FAO-56 / Thornthwaite Im", f"{s['annual_etp_mm']:,.1f} mm / {s['thornthwaite_index_pct']}%", s["humidity_class"]],
                    ["Superpave PG (98% LTPP 20 mm)", pav["recommended_pg_grade"], f"Tmax 7d = {pav.get('max_7day_tmax_c')} °C"],
                    ["Erosividad RUSLE (ANLA)", f"R = {ero.get('r_factor_mfi')} MJ·mm/(ha·h·a)", f"MFI = {ero.get('mfi_arnoldus_mm')} mm ({ero.get('aggressiveness_class')})"],
                    ["Umbral SGC y Cuenca INVIAS", f"{sgc.get('exceedance_days', 0)} días crít. ({sgc.get('episodes_count', 0)} ep.)", f"tc Kirpich = {ws.get('tc_kirpich_min')} min | A={ws.get('area_km2')} km²"],
                ],
                col_widths=(56, 52, 66),
            )
            pdf.figure(render_climograph_png(demo), "Figura 1.1: Climograma mensual multianual del corredor Bogotá D.C.")
            pdf.figure(render_water_balance_png(demo), "Figura 1.2: Balance hídrico climatológico cíclico (ETP, Almacenamiento y Excesos).")

            pdf.section("1.3", "Hidrología IDF, Cuenca INVIAS y Geotecnia SGC")
            pdf.para(
                "En la pestaña 3. Hidrología IDF, Cuenca SGC y Pavimentos explora las tres subpestañas especializadas: "
                "(a) Curvas IDF y Hietograma RAS/INVIAS, (b) Calculadora hidráulica de Cuenca INVIAS + Umbrales SGC y "
                "(c) Pavimentos (TMAP / PMA / Superpave PG)."
            )
            pdf.figure(render_idf_curves_png(demo), "Figura 1.3: Familia de curvas IDF INVIAS y ajuste probabilístico P24h vs Gringorten.")
            pdf.figure(render_sgc_thresholds_png(demo), "Figura 1.4: Envolvente crítica SGC (R15_ant vs R3) y días detonantes por año.")

        pdf.chapter_page("2", "Tutoriales de Herramientas Especializadas")
        pdf.section("2.1", "Calculadora Independiente de Thornthwaite Mensual")
        pdf.para(
            "Cuando dispones únicamente de promedios mensuales de lluvia y temperatura (por ejemplo, tomados de un anuario o "
            "estudio previo sin serie diaria), utiliza la pestaña 4. Thornthwaite Mensual. Incluye preajustes rápidos para "
            "Popayán, Bogotá y Barranquilla."
        )
        pdf.section("2.2", "Puentes de Datos en Vivo, DHIME y Editor 12×31")
        pdf.bullets([
            "Pestaña 5. Puente de Datos: digita códigos IDEAM separados por coma (o usa 'Actualizar Datos' tras seleccionar estaciones en el mapa), selecciona proveedores (IDEAM API, Open-Meteo ERA5, NASA POWER) y presiona Sincronizar.",
            "Importador DHIME / Histórico: sube archivos CSV/XLSX de DHIME o indica la ruta local de paquetes .zip/.rar/SHC.",
            "Editor 12×31: consulta cualquier estación, variable y año en formato matriz 12 meses × 31 días y guarda correcciones marcadas con prioridad Manual.",
        ])

    out_paths["tutorial"] = target_dir / "02_Manual_Tutorial.pdf"
    out_paths["tutorial"].write_bytes(
        _compile_two_pass(
            "HC-DOC-02",
            "Manual Tutorial y\nCasos Prácticos",
            ["Guía guiada paso a paso sobre Bogotá D.C.,", "módulos IDF, SGC, RUSLE, SPEI y puentes IDEAM."],
            "Manual Tutorial y Casos Prácticos",
            logo_mark,
            logo_lockup,
            _build_m2,
        )
    )

    # =========================================================================
    # MANUAL 3: MANUAL CIENTÍFICO Y MATEMÁTICO
    # =========================================================================
    def _build_m3(pdf: ManualBookPDF) -> None:
        pdf.chapter_page("1", "Ponderación Espacial y Geometría Solar")
        pdf.section("1.1", "Ponderación Espacial IDW y Thiessen sobre Corredor")
        pdf.para(
            "Dado un conjunto de estaciones georreferenciadas y un eje vial o polígono, la distancia característica de cada "
            "estación corresponde a la mínima distancia geodésica de Haversine hacia los vértices del trazado. El método de "
            "Distancia Inversa Ponderada (IDW, p = 2) asigna los pesos normalizados:"
        )
        pdf.equation(r"w_i = \frac{(d_i + 0.1)^{-2}}{\sum_{r=1}^{k} (d_r + 0.1)^{-2}}", "1.1")
        pdf.para(
            "Alternativamente, mediante Polígonos de Thiessen discretizados sobre una malla regular confinada al buffer "
            "del corredor, el peso equivale a la fracción de área asignada por vecindad más cercana."
        )

        pdf.section("1.2", "Radiación Astronómica y Evapotranspiración FAO-56 (Allen et al., 1998)")
        pdf.para(
            "Para la latitud ponderada φ (radianes) y el día juliano J, la distancia inversa Tierra-Sol, declinación solar y "
            "radiación extraterrestre diaria Ra (MJ/m²/día) se determinan mediante:"
        )
        pdf.equation(r"d_r = 1 + 0.033\cos\!\left(\frac{2\pi}{365}J\right), \quad \delta = 0.409\sin\!\left(\frac{2\pi}{365}J - 1.39\right)", "1.2")
        pdf.equation(r"ET_0 = \frac{0.408\,\Delta\,R_n + \gamma\frac{900}{T+273}u_2(e_s - e_a)}{\Delta + \gamma(1 + 0.34\,u_2)}", "1.3")
        pdf.para(
            "Si falta radiación medida directa, el motor aplica secuencialmente Angstrom-Prescott desde brillo solar o "
            "Hargreaves-Samani (kRs = 0.16 interior, 0.19 zona costera)."
        )

        pdf.chapter_page("2", "Balance Hídrico y Clasificaciones Climáticas")
        pdf.section("2.1", "Método de Thornthwaite (1948) y Balance Cíclico")
        pdf.para("Con temperaturas medias mensuales Tm truncadas en 0 °C, el índice calórico anual e índices hídricos son:")
        pdf.equation(r"i_m = \left(\frac{T_m}{5}\right)^{1.514}, \qquad I = \sum_{m=1}^{12} i_m, \qquad I_m = I_h - 0.6\,I_a", "2.1")

        pdf.section("2.2", "Caldas-Lang, Holdridge, Köppen-Geiger y Aridez ENA-IDEAM")
        pdf.para("La biotemperatura de Holdridge, evapotranspiración potencial y el Índice de Aridez ENA-IDEAM vienen dados por:")
        pdf.equation(r"ETP_H = 58.93 \cdot T_{\mathrm{bio}}, \qquad EPT = \frac{ETP_H}{P}, \qquad IA = \frac{ETP - ETR}{ETP}", "2.2")

        pdf.chapter_page("3", "Hidrología Extrema, IDF y Cuenca INVIAS")
        pdf.section("3.1", "Frecuencia P24h y Curvas IDF Regionalizadas")
        pdf.para(
            "Se ajustan Gumbel Tipo I, Log-Normal, Log-Pearson Tipo III y GEV frente a posiciones empíricas de Gringorten, "
            "evaluando el estadístico Kolmogorov-Smirnov. La ecuación regionalizada INVIAS (Vargas & Díaz-Granados, 1998) es:"
        )
        pdf.equation(r"F_i = \frac{i - 0.44}{n + 0.12}, \qquad I(T_r, t) = \frac{a \cdot T_r^b \cdot M^d}{(t/60)^c}", "3.1")

        pdf.section("3.2", "Cuenca Hidrográfica: Kirpich, Método Racional y SCS-CN")
        pdf.para("Para una cuenca de área A (km²), longitud L (m), pendiente S (m/m) y Número de Curva CN:")
        pdf.equation(r"t_c = 0.01947\,L^{0.77}\,S^{-0.385}, \qquad Q = \frac{C \cdot I(T_r, t_c) \cdot A}{3.6}", "3.2")
        pdf.equation(r"S_{\max} = \frac{25400}{CN} - 254, \qquad Q_e = \frac{(P - 0.2\,S_{\max})^2}{P + 0.8\,S_{\max}}, \qquad q_{\mathrm{SCS}} = \frac{0.208\,A\,Q_e}{t_p}", "3.3")

        pdf.chapter_page("4", "Geotecnia SGC, Erosividad RUSLE y Sequías SPEI")
        pdf.section("4.1", "Umbral Detonante de Movimientos en Masa (SGC)")
        pdf.para("Relación empírica entre lluvia reciente de 3 días (R3) y acumulada de los 15 días previos (R15_ant):")
        pdf.equation(r"R_{3,\mathrm{crit}} = \max\!\left(5,\ a - b \cdot R_{15,\mathrm{ant}}\right)", "4.1")

        pdf.section("4.2", "Erosividad Pluvial RUSLE (Arnoldus MFI / Renard & Freimund)")
        pdf.equation(r"MFI = \frac{\sum_{m=1}^{12} p_m^2}{P}, \qquad PCI = 100\,\frac{\sum_{m=1}^{12} p_m^2}{P^2}", "4.2")
        pdf.equation(r"R = 0.7397\,MFI^{1.847}\;(MFI < 55), \qquad R = 95.77 - 6.081\,MFI + 0.4770\,MFI^2\;(MFI \geq 55)", "4.3")

        pdf.section("4.3", "Sequías SPEI (Vicente-Serrano et al., 2010)")
        pdf.para(
            "Sobre ventanas móviles de k = 3 y 12 meses del balance climático mensual D = P − ET0, se ajusta una distribución "
            "Log-Logística de 3 parámetros (Fisk) por mes calendario y se estandariza vía inversa normal."
        )

        pdf.chapter_page("5", "Ingeniería de Pavimentos (TMAP, INVIAS, Superpave)")
        pdf.section("5.1", "Temperatura Media Anual Ponderada Shell (Carta W) y LTPP Superpave")
        pdf.equation(r"WF_m = 10^{\left(-1.224 + 0.06508\,T_m - 0.000145\,T_m^2\right)}, \qquad \mathrm{TMAP} = 19.66 + 16.91\log_{10}(\overline{WF}) + 0.3117\left[\log_{10}(\overline{WF})\right]^2", "5.1")
        pdf.equation(r"T_{\mathrm{pav,max}}(20\mathrm{\,mm}) = 54.32 + 0.78\,\overline{T}_{7\mathrm{d}} - 0.0025\,\phi^2 - 15.14\log_{10}(45) + 2.055\sqrt{9 + 0.61\,\sigma_{7\mathrm{d}}^2}", "5.2")

        pdf.chapter_page("A", "Apéndice: Símbolos y Referencias")
        pdf.section("A.1", "Principales Símbolos y Unidades")
        pdf.table_block(
            ["Símbolo", "Descripción", "Unidad"],
            [
                ["P, ETP, ETR", "Precipitación, evapotranspiración potencial y real", "mm"],
                ["M, Tr, I", "Media P24h máx., período de retorno, intensidad", "mm / años / mm/h"],
                ["tc, A, Q", "Tiempo concentración, área cuenca, caudal pico", "min / km² / m³/s"],
                ["R3, R15_ant", "Lluvia acumulada 3 d y antecedente 15 días", "mm"],
                ["MFI, PCI, R", "Fournier modif., concentración y erosividad RUSLE", "mm / % / MJ·mm/(ha·h·a)"],
                ["TMAP, WF, PG", "Temp. media ponderada Shell, factor peso y grado", "°C / adim. / PG"],
            ],
            col_widths=(36, 98, 40),
        )

    out_paths["cientifico"] = target_dir / "03_Manual_Cientifico.pdf"
    out_paths["cientifico"].write_bytes(
        _compile_two_pass(
            "HC-DOC-03",
            "Manual Científico\ny Formulación",
            ["Ecuaciones fundamentales FAO-56, INVIAS, RAS,", "SGC, RUSLE, SPEI, Pettitt, Shell TMAP y LTPP."],
            "Manual Científico y Formulación Matemática",
            logo_mark,
            logo_lockup,
            _build_m3,
        )
    )

    # =========================================================================
    # MANUAL 4: REFERENCIA DE FUNCIONES Y MODELOS DE VERIFICACIÓN
    # =========================================================================
    def _build_m4(pdf: ManualBookPDF) -> None:
        pdf.chapter_page("1", "Referencia de Interfaz, Comandos y Exportaciones")
        pdf.section("1.1", "Estructura de Menús, Atajos y Pestañas")
        pdf.table_block(
            ["Elemento / Pestaña", "Atajo / Acceso", "Funciones Principales y Salidas"],
            [
                ["Menú Superior Desktop", "Archivo / Análisis / Datos / Ver / Ayuda", "Acceso directo a proyectos, pesos, temas, manuales PDF y ayuda F1."],
                ["1. Área GIS y Corredor", "Tab 1", "Filtros 8.973 estaciones, carga KML/KMZ/GeoJSON, IDW, Thiessen."],
                ["2. Climatología, Sequías y RUSLE", "Tab 2 (4 subpestañas)", "Climograma, Balance, SPEI-3/12, IAP, RUSLE Factor R, Pettitt y ETCCDI."],
                ["3. Hidrología, Cuenca SGC y Pav.", "Tab 3 (3 subpestañas)", "IDF Log-Log, Gumbel..GEV, Hietograma, Cuenca INVIAS, SGC y TMAP/PG."],
                ["4. Thornthwaite Mensual", "Tab 4", "Calculadora independiente de 12 meses con presets de ciudades."],
                ["5. Puente de Datos y Editor", "Tab 5", "Sincronización IDEAM/ERA5/NASA, importador DHIME/.zip y matriz 12×31."],
                ["6. Informes y Exportaciones", "Tab 6", "17 entregables: PDF, DOCX, Excel 10 hojas, SWMM CSV, MEPDG, GIS, 7 PNG."],
            ],
            col_widths=(48, 38, 88),
        )

        pdf.section("1.2", "Hojas Formuladas del Libro Excel (.xlsx)")
        pdf.bullets([
            "1. Resumen_Ejecutivo (vínculos vivos a TMAP, PMA, IDF, RUSLE, Cuenca) | 2. Estaciones (pesos =SUM).",
            "3. Balance_Mensual (=SUM, =AVERAGE, Ih, Ia, IA) | 4. Pavimentos_TMAP (=10^(...), TMAP Shell, =IF Región INVIAS).",
            "5. Serie_Anual (=AVERAGE, =MAX, =MIN, =STDEV.S) | 6. Promedios_Diarios_365 | 7. IDF_Frecuencia_RAS (=INDEX/MATCH).",
            "8. Calidad_Homogeneidad_ETCCDI | 9. Geotecnia_SGC_Lluvias (=MAX(5,a-b*R15)) | 10. Cuenca_RUSLE_Sequias (MFI, Factor R, Kirpich, Q=CIA/3.6).",
        ])

        pdf.chapter_page("2", "Modelos de Verificación Numérica y Benchmark")
        pdf.section("2.1", "Matriz de Pruebas Automatizadas (19 Verificaciones)")
        pdf.para(
            "Cada compilación ejecutable de HidroClima Studio valida 19 pruebas unitarias y de integración antes de liberarse, "
            "asegurando convergencia exacta frente a soluciones analíticas conocidas:"
        )
        pdf.table_block(
            ["Caso de Verificación", "Principio Verificado", "Criterio de Aceptación"],
            [
                ["V-01 Balance Hídrico Cíclico", "Conservación de masa P = ETR + Exc", "Error de cierre < 1e-4 mm"],
                ["V-02 Radiación y ET0 FAO-56", "Caso ecuatorial y rangos físicos Colombia", "Ra y ET0 dentro de rango FAO"],
                ["V-03 TMAP Shell & INVIAS", "Ecuación Carta W y matriz climática R1–R6", "Diferencia analítica < 0.01 °C"],
                ["V-04 Cuenca Kirpich y SCS-CN", "tc = 0.01947·L^0.77·S^-0.385 y P = Qe + Ia + F", "Residuo < 0.05 mm y Q exacto"],
                ["V-05 Erosividad RUSLE", "Arnoldus MFI, Oliver PCI y Renard Factor R", "Aporte ∑r_share = 100.0 %"],
                ["V-06 Geotecnia SGC & SPEI-3", "Detección episodio R3 ≥ máx(5, a-b·R15) y Z Fisk", "Identificación de episodios y sequías"],
                ["V-07 Suite API y 17 Exportaciones", "Bogotá D.C. 21205791+21205580 en PDF/DOCX/XLSX/XML/PNG", "200 OK y firmas/fórmulas válidas"],
            ],
            col_widths=(48, 72, 54),
        )
        if demo:
            pdf.figure(render_spei_drought_png(demo), "Figura 2.1: Verificación SPEI-3 / SPEI-12 e intraanualidad RUSLE sobre Ejemplo Bogotá D.C.")
            pdf.figure(render_hyetograph_png(demo), "Figura 2.2: Verificación de hietograma de diseño (Bloques Alternos) Tr = 10 años.")

    out_paths["referencia"] = target_dir / "04_Manual_Referencia_y_Verificacion.pdf"
    out_paths["referencia"].write_bytes(
        _compile_two_pass(
            "HC-DOC-04",
            "Manual de Referencia\ny Verificación",
            ["Diccionario completo de funciones, 17 salidas,", "hojas formuladas Excel y casos de verificación."],
            "Manual de Referencia y Verificación",
            logo_mark,
            logo_lockup,
            _build_m4,
        )
    )

    return out_paths


def resolve_manual_path(manual_id: str) -> Path | None:
    """Localiza el PDF de un manual oficial tanto en desarrollo como en el ejecutable empaquetado."""
    filename_map = {
        "general": "01_Manual_Informacion_General.pdf",
        "tutorial": "02_Manual_Tutorial.pdf",
        "scientific": "03_Manual_Cientifico.pdf",
        "reference": "04_Manual_Referencia_y_Verificacion.pdf",
    }
    fname = filename_map.get(manual_id)
    if not fname:
        return None
    for base in (BASE_DIR / "docs" / "manuals", BUNDLE_DIR / "docs" / "manuals"):
        candidate = base / fname
        if candidate.exists():
            return candidate
    return None


if __name__ == "__main__":
    generated = generate_all_manuals()
    for k, p in generated.items():
        print(f"{k}: {p} ({p.stat().st_size:,} bytes)")
