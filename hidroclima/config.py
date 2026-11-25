"""Configuración global, constantes climáticas y parámetros normativos de HidroClima Studio."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _resolve_paths() -> tuple[Path, Path, Path]:
    """
    Resuelve rutas de recursos empaquetados y almacenamiento persistente:
    - Modo instalado en Windows (presencia de unins000.exe o .installed): datos en %LOCALAPPDATA%\\HidroClimaStudio\\data.
    - Modo portable (.zip/.exe): carpeta data junto al ejecutable si es escribible, sino %LOCALAPPDATA%.
    - Modo código fuente: carpeta raíz del repositorio.
    """
    if getattr(sys, "frozen", False):
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        exe_dir = Path(sys.executable).resolve().parent
        local_app = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "HidroClimaStudio" / "data"
        is_installed = (exe_dir / "unins000.exe").exists() or (exe_dir / ".installed").exists()
        if not is_installed:
            portable_data = exe_dir / "data"
            if _is_writable_dir(portable_data):
                return exe_dir, bundle_dir, portable_data
        local_app.mkdir(parents=True, exist_ok=True)
        return exe_dir, bundle_dir, local_app
    root = Path(__file__).resolve().parent.parent
    return root, root, root / "data"


BASE_DIR, BUNDLE_DIR, DATA_DIR = _resolve_paths()
CATALOG_DB_PATH = BUNDLE_DIR / "data" / "catalog.db"
RUNTIME_DB_PATH = DATA_DIR / "hidroclima.db"
SAMPLE_DIR = BUNDLE_DIR / "data" / "sample_projects"
EXPORTS_DIR = DATA_DIR.parent / "exports" if getattr(sys, "frozen", False) else BASE_DIR / "exports"
STATIC_DIR = BUNDLE_DIR / "hidroclima" / "static"


@dataclass(frozen=True)
class VariableSpec:
    id: int
    codigo: str
    nombre: str
    nombre_corto: str
    unidad: str
    agregacion: str  # 'sum' | 'mean' | 'max' | 'min'
    min_val: float
    max_val: float


VARIABLES: dict[int, VariableSpec] = {
    1: VariableSpec(1, "00000001", "TOTALES DIARIOS DE PRECIPITACION (mms)", "Precipitación", "mm", "sum", 0.0, 500.0),
    2: VariableSpec(2, "00000002", "TOTALES DIARIOS DE BRILLO SOLAR (Horas)", "Brillo Solar", "h", "mean", 0.0, 14.0),
    3: VariableSpec(3, "00000003", "TOTALES DIARIOS DE EVAPORACION (mms)", "Evaporación", "mm", "sum", 0.0, 30.0),
    4: VariableSpec(4, "00000004", "MEDIOS DIARIOS DE HUMEDAD RELATIVA (%)", "Humedad Relativa", "%", "mean", 0.0, 100.0),
    5: VariableSpec(5, "00000005", "MEDIOS DIARIOS DE TEMPERATURA (oC)", "Temp. Media", "°C", "mean", -15.0, 50.0),
    6: VariableSpec(6, "00000006", "MAXIMOS DIARIOS DE TEMPERATURA (oC)", "Temp. Máxima", "°C", "max", -10.0, 55.0),
    7: VariableSpec(7, "00000007", "MINIMOS DIARIOS DE TEMPERATURA (oC)", "Temp. Mínima", "°C", "min", -20.0, 45.0),
    8: VariableSpec(8, "00000008", "TOTALES DIARIOS DE RECORRIDO DEL VIENTO (Kms)", "Recorrido Viento", "km/d", "mean", 0.0, 2500.0),
    9: VariableSpec(9, "00000009", "MEDIOS DIARIOS DE VELOCIDAD DEL VIENTO (m/s)", "Vel. Viento", "m/s", "mean", 0.0, 60.0),
    10: VariableSpec(10, "00000010", "MAXIMOS DIARIOS DE VELOCIDAD DEL VIENTO (m/s)", "Vel. Viento Máx.", "m/s", "max", 0.0, 80.0),
    11: VariableSpec(11, "00000011", "MEDIOS(V) DIARIOS DE VELOCIDAD DEL VIENTO (m/s)", "Vel. Viento (V)", "m/s", "mean", 0.0, 60.0),
    12: VariableSpec(12, "00000012", "RADIACION SOLAR GLOBAL DIARIA (MJ/m2/dia)", "Radiación Solar", "MJ/m²/d", "mean", 0.0, 40.0),
}

# Umbrales de clasificación climática por Índice de Thornthwaite (1948)
THORNTHWAITE_HUMIDITY_CLASSES: list[tuple[float, str, str]] = [
    (-40.0, "E. Árido", "Muy pocas lluvias, alta evaporación"),
    (-20.0, "D. Semiárido", "Pocas lluvias"),
    (0.0, "C1. Subhúmedo-Seco", "Lluvia moderada o lluvia fuertemente estacional"),
    (20.0, "C2. Subhúmedo-Húmedo", "Lluvia moderada o lluvia fuertemente estacional"),
    (40.0, "B1. Ligeramente Húmedo", "Lluvia moderada o lluvia fuertemente estacional"),
    (60.0, "B2. Moderadamente Húmedo", "Lluvia moderada o lluvia fuertemente estacional"),
    (80.0, "B3. Húmedo", "Lluvia moderada o lluvia fuertemente estacional"),
    (100.0, "B4. Muy Húmedo", "Lluvia estacional calurosa moderada"),
    (9999.0, "A. Excesivamente Húmedo", "Lluvias con alta frecuencia o muchos días con superficie húmeda"),
]

# Umbrales de clasificación térmica estándar
THERMAL_CLASSES: list[tuple[float, str]] = [
    (0.0, "Muy Frío"),
    (10.0, "Frío"),
    (20.0, "Templado"),
    (25.0, "Cálido"),
    (9999.0, "Muy Cálido"),
]

# Índice de Aridez ENA-IDEAM: IA = (ETP - ETR) / ETP
ENA_ARIDITY_CLASSES: list[tuple[float, str, str]] = [
    (0.15, "Altos excedentes de agua", "Superávit hídrico permanente y alta oferta superficial"),
    (0.20, "Excedentes de agua", "Disponibilidad hídrica alta con déficit mínimo"),
    (0.30, "Moderado y excedentes de agua", "Transición favorable hacia excedentes hídricos"),
    (0.40, "Moderado", "Equilibrio entre oferta de precipitación y demanda atmosférica"),
    (0.50, "Moderado y deficitario de agua", "Estacionalidad seca marcada o restricción moderada"),
    (0.60, "Deficitario de agua", "Insuficiencia hídrica estacional relevante"),
    (9999.0, "Altamente deficitario de agua", "Restricción hídrica severa; alta aridez superficial"),
]

# Ecuaciones regionales IDF para Colombia — Vargas & Díaz-Granados (1998) / Manual de Drenaje INVIAS
# i(T, t) = a * (T^b) * (M^d) / ((t / 60)^c)  [mm/h], con T en años, M=P24h max multianual (mm), t en minutos
IDF_REGIONS: dict[str, dict[str, float | str]] = {
    "Andina": {"region_code": "R1", "a": 0.94, "b": 0.18, "c": 0.66, "d": 0.83, "desc": "Región Andina (Vargas & Díaz-Granados / INVIAS R1)"},
    "Caribe": {"region_code": "R2", "a": 24.85, "b": 0.22, "c": 0.50, "d": 0.10, "desc": "Región Caribe (Vargas & Díaz-Granados / INVIAS R2)"},
    "Pacífico": {"region_code": "R3", "a": 13.92, "b": 0.19, "c": 0.58, "d": 0.20, "desc": "Región Pacífico (Vargas & Díaz-Granados / INVIAS R3)"},
    "Orinoquía": {"region_code": "R4", "a": 5.53, "b": 0.17, "c": 0.63, "d": 0.42, "desc": "Región Orinoquía-Amazonía (Vargas & Díaz-Granados / INVIAS R4)"},
}

# Períodos de retorno mínimos normativos en Colombia (RAS Res. 0330/2017 e INVIAS)
NORMATIVE_RETURN_PERIODS: list[dict[str, str | int]] = [
    {"norma": "RAS Res. 0330/2017", "obra": "Tramos iniciales residenciales (< 2 ha)", "tr_min": 3, "tr_rec": 5},
    {"norma": "RAS Res. 0330/2017", "obra": "Tramos iniciales comerciales/industriales (< 2 ha) y redes 2–10 ha", "tr_min": 5, "tr_rec": 5},
    {"norma": "RAS Res. 0330/2017", "obra": "Colectores de alcantarillado pluvial (> 10 ha)", "tr_min": 10, "tr_rec": 10},
    {"norma": "RAS Res. 0330/2017", "obra": "Canales abiertos (< 1.000 ha)", "tr_min": 50, "tr_rec": 50},
    {"norma": "RAS Res. 0330/2017", "obra": "Canales abiertos (>= 1.000 ha)", "tr_min": 100, "tr_rec": 100},
    {"norma": "Manual Drenaje INVIAS", "obra": "Zanjas de coronación y cunetas viales", "tr_min": 5, "tr_rec": 5},
    {"norma": "Manual Drenaje INVIAS", "obra": "Alcantarillas (D <= 0.90 m) y estructuras de caída", "tr_min": 10, "tr_rec": 10},
    {"norma": "Manual Drenaje INVIAS", "obra": "Alcantarillas mayores (D > 0.90 m)", "tr_min": 20, "tr_rec": 20},
    {"norma": "Manual Drenaje INVIAS", "obra": "Puentes menores (luz < 10 m)", "tr_min": 25, "tr_rec": 25},
    {"norma": "Manual Drenaje INVIAS", "obra": "Puentes mayores y obras críticas", "tr_min": 50, "tr_rec": 100},
]

IDF_DURATIONS_MIN: list[int] = [5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180]
IDF_RETURN_PERIODS: list[int] = [2, 3, 5, 10, 15, 20, 25, 30, 40, 50, 100]

# Prioridad de fuentes al fusionar series diarias (mayor prioridad primero)
SOURCE_PRIORITY: list[str] = [
    "Manual",
    "IDEAM-DHIME",
    "IDEAM-API",
    "Archivo-Histórico",
    "IDEAM-Legacy",
    "NASA-POWER",
    "Open-Meteo",
]

# Endpoints oficiales de IDEAM en Datos Abiertos Colombia (datos.gov.co SODA API)
IDEAM_SOCRATA_DATASETS: dict[str, dict[str, str | int]] = {
    "stations": {"id": "hp9r-jxuu", "name": "Catálogo Nacional de Estaciones del IDEAM"},
    "precip": {"id": "s54a-sgyg", "var_id": 1, "agg": "sum", "name": "Precipitación"},
    "tmean": {"id": "sbwg-7ju4", "var_id": 5, "agg": "mean", "name": "Temperatura Ambiente del Aire"},
    "tmax": {"id": "ccvq-rp9s", "var_id": 6, "agg": "max", "name": "Temperatura Máxima del Aire"},
    "tmin": {"id": "afdg-3zpb", "var_id": 7, "agg": "min", "name": "Temperatura Mínima del Aire"},
    "rh": {"id": "uext-mhny", "var_id": 4, "agg": "mean", "name": "Humedad del Aire"},
    "wind": {"id": "sgfv-3yp8", "var_id": 9, "agg": "mean", "name": "Velocidad del Viento"},
    "unified": {"id": "57sv-p2fu", "name": "Datos de Estaciones de IDEAM y de Terceros"},
}

DAYS_IN_MONTH_NONLEAP = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
DAYS_IN_MONTH_LEAP = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MONTH_NAMES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
MONTH_ABBR_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
