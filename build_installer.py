"""Compila el paquete PyInstaller y genera el instalador clásico de Windows (Setup.exe con Inno Setup)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from build_portable import build_bundle
from hidroclima import __version__

ROOT = Path(__file__).resolve().parent


def find_iscc() -> Path | None:
    which_iscc = shutil.which("ISCC") or shutil.which("iscc")
    if which_iscc:
        return Path(which_iscc)

    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def main() -> None:
    skip_bundle = "--skip-bundle" in sys.argv
    exe_path = ROOT / "dist" / "HidroClimaStudio" / "HidroClimaStudio.exe"
    if not skip_bundle or not exe_path.exists():
        build_bundle()

    iscc = find_iscc()
    if iscc is None:
        raise FileNotFoundError(
            "No se encontró el compilador de Inno Setup 6 (ISCC.exe). "
            "Instálalo con: winget install JRSoftware.InnoSetup"
        )

    iss_path = ROOT / "installer" / "setup.iss"
    cmd = [str(iscc), f"/DAppVersion={__version__}", str(iss_path)]
    print("Compilando instalador Windows:", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)

    setup_exe = ROOT / "dist" / f"HidroClimaStudio-Setup-{__version__}.exe"
    print(f"\nInstalador Windows generado exitosamente: {setup_exe}")


if __name__ == "__main__":
    main()
