"""Pruebas para importación legacy (.dat, .cli), DHIME CSV y almacenamiento SQLite 372-slots."""

from __future__ import annotations

import numpy as np
import pytest

from hidroclima.bridges.ideam_dhime import import_dhime_file
from hidroclima.db.database import SLOTS_PER_YEAR, ClimateDatabase, pack_372, unpack_372
from hidroclima.db.legacy_importer import (
    export_legacy_cli_text,
    export_project_hclim,
    parse_legacy_cli_file,
    parse_project_file,
    parse_shc_dat_file,
)


def test_pack_unpack_372_roundtrip():
    arr = np.full(SLOTS_PER_YEAR, np.nan, dtype=np.float32)
    arr[0] = 12.5
    arr[31 + 28] = 4.2  # Feb 29
    arr[11 * 31 + 30] = 99.7  # Dic 31
    blob = pack_372(arr)
    out = unpack_372(blob)
    assert out.shape == (SLOTS_PER_YEAR,)
    assert pytest.approx(out[0], rel=1e-4) == 12.5
    assert pytest.approx(out[31 + 28], rel=1e-4) == 4.2
    assert pytest.approx(out[11 * 31 + 30], rel=1e-4) == 99.7
    assert np.isnan(out[5])


def test_cli_parse_and_export_roundtrip():
    sample_cli = """[Proyecto]
 1 
Corredor Sur Cauca
 2 
Estudio Fase III
 3 
Popayan - Pasto
 25 
 120 
 26 
 2024 
 27 
 10 
 50 
 2 
[InicioEC]
 51 
26035030
 52 
 0.65 
 51 
44015030
 52 
 0.35 
[FinEC]
[FinProyecto]
"""
    parsed = parse_legacy_cli_file(sample_cli)
    assert parsed["name"] == "Corredor Sur Cauca"
    assert parsed["soil_max_reserve_mm"] == 120.0
    assert parsed["end_year"] == 2024
    assert parsed["last_n_years"] == 10
    assert parsed["etp_method"] == "penman_monteith"
    assert len(parsed["stations"]) == 2
    assert parsed["stations"][0]["codigo"] == "26035030"
    assert parsed["stations"][0]["weight"] == 0.65

    regenerated = export_legacy_cli_text(parsed)
    reparsed = parse_legacy_cli_file(regenerated)
    assert reparsed["name"] == parsed["name"]
    assert reparsed["stations"] == parsed["stations"]


def test_hclim_json_parse_and_export_roundtrip():
    cfg = {
        "name": "Proyecto Vial Cauca Sur",
        "description": "Diseños hidrología y SGC",
        "location": "Popayán",
        "soil_max_reserve_mm": 115.0,
        "water_table_m": 8.0,
        "end_year": 2025,
        "last_n_years": 15,
        "etp_method": "penman_monteith",
        "study_profile": "geotecnia",
        "idf_method": "invias",
        "watershed_area_km2": 2.4,
        "watershed_length_m": 1350.0,
        "watershed_slope_pct": 6.2,
        "curve_number": 78.0,
        "runoff_coeff": 0.55,
        "sgc_r3_intercept": 75.0,
        "sgc_r15_slope": 0.45,
        "stations": [{"codigo": "26035030", "weight": 0.7}, {"codigo": "44015030", "weight": 0.3}],
        "route_coords": [[2.44, -76.61], [1.90, -76.67]],
    }
    raw_hclim = export_project_hclim(cfg)
    parsed = parse_project_file(raw_hclim)
    assert parsed["name"] == "Proyecto Vial Cauca Sur"
    assert parsed["study_profile"] == "geotecnia"
    assert parsed["watershed_area_km2"] == 2.4
    assert parsed["sgc_r3_intercept"] == 75.0
    assert len(parsed["route_coords"]) == 2
    assert parsed["stations"][0]["codigo"] == "26035030"


def test_parse_synthetic_shc_dat(tmp_path):
    rec = bytearray(4096)
    rec[0:31] = b"26035030       00000001    2024"
    # Ene día 1 = 15.4, Feb día 2 = 22.8
    rec[295 : 295 + 8] = b"15.4    "
    rec[295 + 256 + 8 : 295 + 256 + 16] = b"22.8    "
    dat_path = tmp_path / "Clima2024.dat"
    dat_path.write_bytes(bytes(rec))

    rows = parse_shc_dat_file(dat_path)
    assert len(rows) == 1
    stn, vid, yr, src, _now, blob, vc, s_sum, s_mean, s_max, s_min = rows[0]
    assert stn == "26035030"
    assert vid == 1
    assert yr == 2024
    assert src == "IDEAM-Legacy"
    assert vc == 2
    assert pytest.approx(s_sum, rel=1e-4) == 38.2
    arr = unpack_372(blob)
    assert pytest.approx(arr[0], rel=1e-4) == 15.4
    assert pytest.approx(arr[31 + 1], rel=1e-4) == 22.8


def test_import_dhime_csv(tmp_path):
    db = ClimateDatabase(tmp_path / "test.db", auto_bootstrap=False)
    csv_text = (
        "CodigoEstacion;NombreEstacion;Etiqueta;Fecha;Valor\n"
        "0026035030;APTO POPAYAN;PTPM_CON;2025-06-01;12,4\n"
        "0026035030;APTO POPAYAN;PTPM_CON;2025-06-02;0,0\n"
        "0026035030;APTO POPAYAN;TMX_CON;2025-06-01;25,8\n"
    )
    res = import_dhime_file(db, csv_text.encode("utf-8"), "dhime_export.csv")
    assert res["records_saved"] == 2
    assert "26035030" in res["stations"]
    df, counts = db.get_station_daily_dataframe("26035030", var_ids=[1, 6], start_year=2025, end_year=2025)
    assert counts["IDEAM-DHIME"] == 3
    assert pytest.approx(df.loc["2025-06-01", 1], rel=1e-4) == 12.4
    assert pytest.approx(df.loc["2025-06-01", 6], rel=1e-4) == 25.8
