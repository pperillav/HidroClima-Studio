"""Empaquetador de distribución Windows para HidroClima Studio (ejecutable + archivo portable .zip)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from hidroclima import __version__

ROOT = Path(__file__).resolve().parent


def build_bundle() -> Path:
    cmd_base = [sys.executable, "-m", "PyInstaller"]
    icon = ROOT / "hidroclima" / "static" / "hidroclima_studio.ico"

    cmd = cmd_base + [
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "HidroClimaStudio",
        f"--icon={icon}",
        f"--add-data={ROOT / 'hidroclima' / 'static'};hidroclima/static",
        f"--add-data={ROOT / 'data' / 'catalog.db'};data",
        f"--add-data={ROOT / 'data' / 'sample_projects'};data/sample_projects",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=webview",
        "--collect-submodules=scipy",
        str(ROOT / "run_hidroclima.py"),
    ]
    print("Ejecutando PyInstaller:", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)

    out_dir = ROOT / "dist" / "HidroClimaStudio"
    out_exe = out_dir / "HidroClimaStudio.exe"
    if not out_exe.exists():
        raise FileNotFoundError(f"No se generó el ejecutable esperado: {out_exe}")

    # Incluir documentación técnica dentro de la distribución portable
    for doc_name in ("README.md", "LICENSE", "CHANGELOG.md"):
        src_doc = ROOT / doc_name
        if src_doc.exists():
            shutil.copy2(src_doc, out_dir / doc_name)
    docs_dir = ROOT / "docs"
    if docs_dir.exists():
        shutil.copytree(docs_dir, out_dir / "docs", dirs_exist_ok=True)

    zip_base = ROOT / "dist" / f"HidroClimaStudio-{__version__}-Windows-Portable"
    zip_path = shutil.make_archive(str(zip_base), "zip", str(out_dir))
    print(f"\nEjecutable generado: {out_exe}")
    print(f"Paquete portable ZIP: {zip_path}")
    return out_exe


if __name__ == "__main__":
    build_bundle()
