"""Importador de archivos CSV/Excel exportados desde IDEAM DHIME (dhime.ideam.gov.co)."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hidroclima.db.database import SLOTS_PER_YEAR, ClimateDatabase

# Etiquetas típicas de parámetros DHIME -> var_id de HidroClima Studio
DHIME_PARAM_MAP: dict[str, int] = {
    "PTPM_CON": 1,
    "PTPM_TT_M": 1,
    "PRECIPITACION": 1,
    "PRECIPITACIÓN": 1,
    "BSHG_CON": 2,
    "BRILLO SOLAR": 2,
    "EVAP_CON": 3,
    "EVAPORACION": 3,
    "EVAPORACIÓN": 3,
    "HR_CAL": 4,
    "HRHG_CON": 4,
    "HUMEDAD RELATIVA": 4,
    "TSSM_CON": 5,
    "TM_CON": 5,
    "TA_MEDIA": 5,
    "TEMPERATURA MEDIA": 5,
    "TEMPERATURA AMBIENTE": 5,
    "TMX_CON": 6,
    "TEMPERATURA MAXIMA": 6,
    "TEMPERATURA MÁXIMA": 6,
    "TMN_CON": 7,
    "TEMPERATURA MINIMA": 7,
    "TEMPERATURA MÍNIMA": 7,
    "VVAG_CON": 8,
    "RECORRIDO DEL VIENTO": 8,
    "VV_AUT_10": 9,
    "VV_MEDIA": 9,
    "VELOCIDAD DEL VIENTO": 9,
    "VVX_AUT": 10,
    "RADIACION SOLAR": 12,
    "RADIACIÓN SOLAR": 12,
}


def _infer_var_id(label: str) -> int | None:
    u = label.strip().upper()
    if u in DHIME_PARAM_MAP:
        return DHIME_PARAM_MAP[u]
    if "PRECIP" in u or "PTPM" in u:
        return 1
    if "BRILLO" in u or "BSHG" in u:
        return 2
    if "EVAP" in u:
        return 3
    if "HUMEDAD" in u or u.startswith("HR"):
        return 4
    if "TEMP" in u and ("MAX" in u or "MÁX" in u or "TMX" in u):
        return 6
    if "TEMP" in u and ("MIN" in u or "MÍN" in u or "TMN" in u):
        return 7
    if "TEMP" in u or "TSSM" in u:
        return 5
    if "RECORRIDO" in u or "VVAG" in u:
        return 8
    if "VIENTO" in u and ("MAX" in u or "MÁX" in u):
        return 10
    if "VIENTO" in u or "VV_" in u:
        return 9
    if "RADIAC" in u:
        return 12
    return None


def _read_dhime_dataframe(content: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))

    for enc in ("utf-8-sig", "utf-8", "latin1"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("latin1", errors="replace")

    first_line = text.splitlines()[0] if text.splitlines() else ""
    sep = ";" if first_line.count(";") >= first_line.count(",") else ","
    # Detectar coma decimal si el separador es punto y coma
    decimal = "," if sep == ";" else "."
    return pd.read_csv(io.StringIO(text), sep=sep, decimal=decimal)


def import_dhime_file(
    db: ClimateDatabase,
    content: bytes,
    filename: str,
    default_station_code: str | None = None,
    default_var_id: int | None = None,
) -> dict[str, Any]:
    """Importa archivo CSV/XLSX de DHIME IDEAM a la base SQLite."""
    df = _read_dhime_dataframe(content, filename)
    if df.empty:
        raise ValueError("El archivo DHIME está vacío.")

    cols_norm = {str(c).strip().lower(): c for c in df.columns}

    def _find_col(candidates: list[str]) -> str | None:
        for cand in candidates:
            for k, orig in cols_norm.items():
                if cand in k:
                    return orig
        return None

    col_stn = _find_col(["codigoestacion", "codigo_estacion", "estacion", "codigo", "idestacion"])
    col_date = _find_col(["fecha", "date", "fechaobservacion"])
    col_val = _find_col(["valor", "value", "dato", "valorobservado"])
    col_param = _find_col(["etiqueta", "parametro", "parámetro", "variable", "idparametro", "nombreparametro"])

    if not col_date or not col_val:
        raise ValueError(
            f"No se identificaron columnas de Fecha y Valor en {filename}. Columnas encontradas: {list(df.columns)}"
        )

    dates = pd.to_datetime(df[col_date], errors="coerce", dayfirst=False)
    # Reintentar dayfirst=True si hubo muchos NaT
    if dates.isna().mean() > 0.4:
        dates_df = pd.to_datetime(df[col_date], errors="coerce", dayfirst=True)
        if dates_df.notna().sum() > dates.notna().sum():
            dates = dates_df

    vals = pd.to_numeric(df[col_val].astype(str).str.replace(",", ".", regex=False), errors="coerce")

    grouped: dict[tuple[str, int, int], np.ndarray] = {}
    skipped = 0

    for idx in range(len(df)):
        dt = dates.iloc[idx]
        val = vals.iloc[idx]
        if pd.isna(dt) or pd.isna(val):
            skipped += 1
            continue

        stn = default_station_code
        if col_stn is not None and pd.notna(df[col_stn].iloc[idx]):
            raw_s = str(df[col_stn].iloc[idx]).strip()
            raw_s = re.sub(r"\.0$", "", raw_s)
            if raw_s.isdigit() and raw_s.startswith("00") and len(raw_s) == 10:
                raw_s = raw_s.lstrip("0")
            if raw_s:
                stn = raw_s
        if not stn:
            skipped += 1
            continue

        vid = default_var_id
        if col_param is not None and pd.notna(df[col_param].iloc[idx]):
            inferred = _infer_var_id(str(df[col_param].iloc[idx]))
            if inferred:
                vid = inferred
        if not vid:
            skipped += 1
            continue

        yr = int(dt.year)
        mo = int(dt.month)
        dy = int(dt.day)
        key = (stn, vid, yr)
        if key not in grouped:
            grouped[key] = np.full(SLOTS_PER_YEAR, np.nan, dtype=np.float32)
        grouped[key][(mo - 1) * 31 + (dy - 1)] = np.float32(val)

    records = [(stn, vid, yr, "IDEAM-DHIME", arr) for (stn, vid, yr), arr in grouped.items()]
    saved = db.upsert_annual_series(records)
    stations = sorted({r[0] for r in records})
    years = sorted({r[2] for r in records})
    db.log_sync(
        source="IDEAM-DHIME",
        action="import_dhime",
        stations_count=len(stations),
        records_count=saved,
        year_min=years[0] if years else None,
        year_max=years[-1] if years else None,
        notes=f"Archivo {Path(filename).name}",
    )
    return {
        "records_saved": saved,
        "stations": stations,
        "years": years,
        "skipped_rows": skipped,
    }
