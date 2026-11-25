"""Lanzador de escritorio nativo para HidroClima Studio (ventana pywebview o Edge/Chrome App)."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

import uvicorn

from hidroclima import __app_name__, __version__
from hidroclima.api.server import create_app
from hidroclima.config import STATIC_DIR


def _find_free_port(preferred: int = 8765) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _find_chromium_app_binary() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _wait_server_ready(port: int, timeout_s: float = 15.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)


def _open_browser_app(url: str) -> None:
    _wait_server_ready(int(url.rsplit(":", 1)[1]))
    browser_bin = _find_chromium_app_binary()
    if browser_bin:
        try:
            subprocess.Popen(
                [browser_bin, f"--app={url}", "--window-size=1440,920"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except OSError:
            pass
    webbrowser.open(url)


def main() -> None:
    port = _find_free_port(8765)
    url = f"http://127.0.0.1:{port}"
    fastapi_app = create_app()

    # Evitar AttributeError cuando se ejecuta sin consola (pythonw.exe o PyInstaller --noconsole)
    log_cfg = None if sys.stderr is None else uvicorn.config.LOGGING_CONFIG

    if "--no-browser" in sys.argv:
        uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning", log_config=log_cfg)
        return

    use_browser_mode = "--browser" in sys.argv
    if not use_browser_mode:
        try:
            import webview

            config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="warning", log_config=log_cfg)
            server = uvicorn.Server(config)
            srv_thread = threading.Thread(target=server.run, daemon=True)
            srv_thread.start()
            _wait_server_ready(port, timeout_s=15.0)

            webview.settings["ALLOW_DOWNLOADS"] = True
            icon_path = STATIC_DIR / "hidroclima_studio.ico"
            win_kwargs = {
                "title": f"{__app_name__} v{__version__} — Hidrología IDF, Balance Hídrico, Climatología y Pavimentos",
                "url": url,
                "width": 1440,
                "height": 900,
                "min_size": (1080, 700),
            }
            window = webview.create_window(**win_kwargs)

            def _on_closed() -> None:
                server.should_exit = True

            window.events.closed += _on_closed
            start_kwargs = {}
            if sys.platform == "win32" and icon_path.exists():
                start_kwargs["icon"] = str(icon_path)
            webview.start(**start_kwargs)
            server.should_exit = True
            srv_thread.join(timeout=3.0)
            return
        except Exception:
            try:
                server.should_exit = True  # type: ignore[name-defined]
                srv_thread.join(timeout=2.0)  # type: ignore[name-defined]
            except Exception:
                pass

    if sys.stdout is not None:
        print(f"\n  {__app_name__} iniciando en {url}")
    threading.Thread(target=_open_browser_app, args=(url,), daemon=True).start()
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning", log_config=log_cfg)


if __name__ == "__main__":
    main()
