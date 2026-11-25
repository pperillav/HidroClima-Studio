"""Esquemas Pydantic de entrada y salida de la API de HidroClima Studio."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StationSearchRequest(BaseModel):
    query: str = ""
    departamento: str = ""
    municipio: str = ""
    categoria: str = ""
    estado: str = ""
    only_with_data: bool = False
    required_vars: list[int] = Field(default_factory=list)
    filter_year: int | None = None
    precip_min: float | None = None
    precip_max: float | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    radius_km: float | None = None
    route_coords: list[list[float]] = Field(default_factory=list)
    route_buffer_km: float = 15.0
    limit: int = 1500


class StationWeightItem(BaseModel):
    codigo: str
    weight: float = 1.0


class WeightComputeRequest(BaseModel):
    station_codes: list[str]
    method: str = "idw"  # idw | thiessen | equal
    route_coords: list[list[float]] = Field(default_factory=list)
    buffer_km: float = 15.0


class ProjectAnalysisRequest(BaseModel):
    name: str = "Proyecto Vial"
    description: str = ""
    location: str = ""
    stations: list[StationWeightItem]
    end_year: int = 2026
    last_n_years: int = 0
    soil_max_reserve_mm: float = 100.0
    water_table_m: float = 10.0
    etp_method: str = "penman_monteith"  # penman_monteith | thornthwaite
    study_profile: str = "integral"  # integral | hidrologia | ambiental | geotecnia | pavimentos
    idf_region: str | None = None
    idf_method: str = "invias"  # invias | silva | sherman | bell
    idf_custom_params: dict[str, float] | None = None
    hyetograph_tr: int = 10
    hyetograph_duration_min: int = 60
    watershed_area_km2: float = 1.0
    watershed_length_m: float = 800.0
    watershed_slope_pct: float = 5.0
    curve_number: float = 75.0
    runoff_coeff: float = 0.50
    sgc_r3_intercept: float = 70.0
    sgc_r15_slope: float = 0.47
    allowed_sources: list[str] | None = None
    fill_gaps: bool = True
    route_coords: list[list[float]] = Field(default_factory=list)


class WatershedCalcRequest(BaseModel):
    idf_result: dict[str, Any]
    area_km2: float = 1.0
    length_m: float = 800.0
    slope_pct: float = 5.0
    curve_number: float = 75.0
    runoff_coeff: float = 0.50


class MonthlyThornthwaiteRequest(BaseModel):
    lat_deg: float = 2.45
    soil_max_reserve_mm: float = 100.0
    monthly_precip: list[float]
    monthly_temp: list[float]


class YearMatrixUpdateRequest(BaseModel):
    matrix: list[list[float | None]]
    source: str = "Manual"


class SyncBridgeRequest(BaseModel):
    station_codes: list[str]
    providers: list[str] = Field(default_factory=lambda: ["IDEAM-API", "Open-Meteo"])
    start_year: int = 2024
    end_year: int | None = None
    update_catalog: bool = False


class LegacyImportRequest(BaseModel):
    source_path: str
    station_codes: list[str] | None = None
    year_min: int | None = None
    year_max: int | None = None
    import_catalog: bool = False


class SaveProjectRequest(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    location: str = ""
    config: dict[str, Any]
