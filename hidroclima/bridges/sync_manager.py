"""Orquestador unificado de sincronización de datos (IDEAM API, Open-Meteo, NASA POWER)."""

from __future__ import annotations

from datetime import date
from typing import Any

from hidroclima.bridges.ideam_socrata import sync_ideam_station_catalog, sync_station_from_ideam_api
from hidroclima.bridges.reanalysis_bridge import sync_station_from_reanalysis
from hidroclima.db.database import ClimateDatabase


def sync_stations_bridge(
    db: ClimateDatabase,
    station_codes: list[str],
    providers: list[str] | None = None,
    start_year: int = 2024,
    end_year: int | None = None,
    update_catalog: bool = False,
) -> dict[str, Any]:
    """Ejecuta sincronización en vivo para múltiples estaciones y proveedores."""
    provs = providers or ["IDEAM-API", "Open-Meteo"]
    end_yr = end_year or date.today().year
    results: list[dict[str, Any]] = []
    catalog_res: dict[str, Any] | None = None

    if update_catalog:
        try:
            catalog_res = sync_ideam_station_catalog(db)
        except Exception as exc:
            catalog_res = {"error": str(exc)}

    total_saved = 0
    for code in station_codes:
        stn_report: dict[str, Any] = {"station_code": code, "providers": []}
        for prov in provs:
            try:
                if prov == "IDEAM-API":
                    res = sync_station_from_ideam_api(db, code, start_year, end_yr, allow_nearby_auto_fallback=True)
                elif prov in ("Open-Meteo", "NASA-POWER"):
                    res = sync_station_from_reanalysis(db, code, provider=prov, start_year=start_year, end_year=end_yr)
                else:
                    res = {"error": f"Proveedor desconocido: {prov}"}
                total_saved += int(res.get("records_saved", 0))
                stn_report["providers"].append({"provider": prov, **res})
            except Exception as exc:
                stn_report["providers"].append({"provider": prov, "records_saved": 0, "error": str(exc)})
        results.append(stn_report)

    return {
        "catalog": catalog_res,
        "total_records_saved": total_saved,
        "stations": results,
    }
