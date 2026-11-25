"""Generador de identidad visual, logos vectoriales e icono HD para HidroClima Studio."""

from __future__ import annotations

import os
from pathlib import Path

from hidroclima.config import DATA_DIR

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
from matplotlib.patches import Circle, FancyBboxPatch, PathPatch, Polygon
from matplotlib.path import Path as MplPath
import numpy as np
from PIL import Image


def _draw_emblem(ax: plt.Axes, dark_bg: bool = False) -> None:
    """Dibuja el emblema geométrico de HidroClima Studio (montaña + curva hídrica + núcleo solar)."""
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal")
    ax.axis("off")

    primary = "#38BDF8" if dark_bg else "#0072B2"
    navy = "#F8FAFC" if dark_bg else "#0B192C"
    teal = "#2DD4BF" if dark_bg else "#00897B"
    subtle = "#1E3A5F" if dark_bg else "#E2E8F0"

    # Marco octogonal / escudo limpio redondeado
    shield = FancyBboxPatch(
        (8, 8), 84, 84,
        boxstyle="round,pad=0.0,rounding_size=16",
        facecolor="#0F2138" if dark_bg else "#FFFFFF",
        edgecolor=navy,
        linewidth=4.4,
        zorder=8,
    )
    # Fondo sólido recortable interior y borde nítido encima
    shield_fill = FancyBboxPatch(
        (8, 8), 84, 84,
        boxstyle="round,pad=0.0,rounding_size=16",
        facecolor="#0F2138" if dark_bg else "#FFFFFF",
        edgecolor="none",
        zorder=1,
    )
    shield_border = FancyBboxPatch(
        (8, 8), 84, 84,
        boxstyle="round,pad=0.0,rounding_size=16",
        facecolor="none",
        edgecolor=navy,
        linewidth=4.4,
        zorder=10,
    )
    ax.add_patch(shield_fill)

    # Halo solar / térmico en cuadrante superior derecho
    sun = Circle((67, 68), radius=9.8, facecolor=teal, edgecolor=navy, linewidth=2.1, alpha=0.95, zorder=2)
    sun.set_clip_path(shield_fill)
    ax.add_patch(sun)
    for ang in np.linspace(20, 130, 5):
        rad = np.deg2rad(ang)
        ln, = ax.plot(
            [67 + 12.2 * np.cos(rad), 67 + 16.0 * np.cos(rad)],
            [68 + 12.2 * np.sin(rad), 68 + 16.0 * np.sin(rad)],
            color=teal,
            linewidth=2.2,
            solid_capstyle="round",
            zorder=2,
        )
        ln.set_clip_path(shield_fill)

    # Cordillera / relieve geotécnico (dos cumbres superpuestas)
    mtn_back = Polygon(
        [(6, 26), (34, 65), (54, 41), (70, 57), (94, 26)],
        closed=True,
        facecolor=subtle,
        edgecolor=navy,
        linewidth=2.4,
        joinstyle="round",
        zorder=3,
    )
    mtn_back.set_clip_path(shield_fill)
    ax.add_patch(mtn_back)

    mtn_front = Polygon(
        [(6, 26), (28, 53), (42, 39), (58, 60), (94, 26)],
        closed=True,
        facecolor="#1E293B" if dark_bg else "#0B192C",
        edgecolor=navy,
        linewidth=2.3,
        joinstyle="round",
        zorder=4,
    )
    mtn_front.set_clip_path(shield_fill)
    ax.add_patch(mtn_front)

    # Onda hidrológica / curva de escorrentía en primer plano
    xs = np.linspace(8, 92, 100)
    ys1 = 27.0 + 3.6 * np.sin((xs - 10) / 12.0)
    ys2 = 18.5 + 3.0 * np.sin((xs - 16) / 12.0)
    poly_wave = ax.fill_between(xs, 8, ys1 + 1.5, color=primary, alpha=0.95, zorder=5)
    poly_wave.set_clip_path(shield_fill)
    l1, = ax.plot(xs, ys1, color="#FFFFFF" if not dark_bg else "#0B192C", linewidth=2.4, zorder=6)
    l2, = ax.plot(xs, ys2, color=teal if dark_bg else "#FFFFFF", linewidth=2.0, zorder=6)
    l1.set_clip_path(shield_fill)
    l2.set_clip_path(shield_fill)

    # Gota hidro-climatológica matemáticamente tangente en cuadrante superior izquierdo
    xc, yb, rad_d = 35.0, 62.0, 9.8
    alpha = np.deg2rad(32.0)
    arc_angles = np.linspace(np.pi - alpha, 2 * np.pi + alpha, 60)
    pts_drop = [(xc, yb + rad_d / np.sin(alpha))] + [
        (xc + rad_d * np.cos(a), yb + rad_d * np.sin(a)) for a in arc_angles
    ]
    drop = Polygon(
        pts_drop,
        closed=True,
        facecolor=primary,
        edgecolor=navy,
        linewidth=2.3,
        joinstyle="round",
        zorder=7,
    )
    drop.set_clip_path(shield_fill)
    ax.add_patch(drop)
    ax.add_patch(shield_border)


def generate_brand_assets(static_dir: Path | None = None) -> dict[str, Path]:
    """Genera PNGs del logo (emblema claro/oscuro, banner horizontal) y el archivo .ico."""
    target_dir = static_dir or (Path(__file__).resolve().parent.parent / "static")
    target_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    # 1. Emblema para fondos claros (portadas blancas de manuales, informes, UI header)
    for name, dark_bg in (("logo_mark_light.png", False), ("logo_mark_dark.png", True)):
        fig = plt.figure(figsize=(3.0, 3.0), dpi=220)
        ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
        fig.patch.set_alpha(0.0)
        ax.patch.set_alpha(0.0)
        _draw_emblem(ax, dark_bg=dark_bg)
        out_p = target_dir / name
        fig.savefig(out_p, transparent=True, dpi=220)
        plt.close(fig)
        paths[name] = out_p

    # 2. Lockup horizontal (Emblema + Wordmark) para franja inferior oscura de portadas de manuales
    fig = plt.figure(figsize=(6.8, 1.45), dpi=240)
    fig.patch.set_facecolor("#0B192C")
    ax_ico = fig.add_axes([0.02, 0.08, 0.19, 0.84])
    ax_ico.patch.set_alpha(0.0)
    _draw_emblem(ax_ico, dark_bg=True)

    ax_txt = fig.add_axes([0.23, 0.05, 0.75, 0.90])
    ax_txt.axis("off")
    ax_txt.text(0.0, 0.62, "HIDROCLIMA STUDIO", fontsize=23, fontweight="bold", color="#FFFFFF", family="DejaVu Sans")
    ax_txt.text(
        0.0,
        0.24,
        "HYDROLOGY  ·  GEOTECHNICS SGC  ·  PAVEMENTS TMAP  ·  CLIMATE",
        fontsize=8.8,
        fontweight="bold",
        color="#38BDF8",
        family="DejaVu Sans",
    )
    lockup_p = target_dir / "logo_lockup_dark.png"
    fig.savefig(lockup_p, facecolor="#0B192C", dpi=240)
    plt.close(fig)
    paths["logo_lockup_dark.png"] = lockup_p

    # 3. Lockup claro para encabezados de reportes PDF y Centro de Ayuda
    fig2 = plt.figure(figsize=(6.4, 1.25), dpi=240)
    fig2.patch.set_alpha(0.0)
    ax_ico2 = fig2.add_axes([0.01, 0.06, 0.18, 0.88])
    ax_ico2.patch.set_alpha(0.0)
    _draw_emblem(ax_ico2, dark_bg=False)
    ax_txt2 = fig2.add_axes([0.21, 0.05, 0.78, 0.90])
    ax_txt2.axis("off")
    ax_txt2.text(0.0, 0.62, "HidroClima Studio", fontsize=21, fontweight="bold", color="#0B192C", family="DejaVu Sans")
    ax_txt2.text(
        0.0,
        0.24,
        "Hidrología IDF · Geotecnia SGC · Pavimentos TMAP · Climatología ANLA",
        fontsize=8.8,
        fontweight="bold",
        color="#0072B2",
        family="DejaVu Sans",
    )
    lockup_light = target_dir / "logo_lockup_light.png"
    fig2.savefig(lockup_light, transparent=True, dpi=240)
    plt.close(fig2)
    paths["logo_lockup_light.png"] = lockup_light

    # 4. Icono multi-resolución Windows (.ico) actualizado con el nuevo emblema
    img = Image.open(paths["logo_mark_light.png"]).convert("RGBA")
    ico_p = target_dir / "hidroclima_studio.ico"
    img.save(ico_p, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    paths["hidroclima_studio.ico"] = ico_p
    return paths


if __name__ == "__main__":
    created = generate_brand_assets()
    for k, v in created.items():
        print(f"{k}: {v} ({v.stat().st_size} bytes)")
