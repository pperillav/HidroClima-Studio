"""Gestor SQLite de estaciones IDEAM, series históricas comprimidas y proyectos."""

from __future__ import annotations

import calendar
import gzip
import json
import shutil
import sqlite3
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd

from hidroclima.analysis.spatial import (
    haversine_vectorized_km,
    stations_distance_to_polyline,
)
from hidroclima.config import (
    CATALOG_DB_PATH,
    DAYS_IN_MONTH_LEAP,
    DAYS_IN_MONTH_NONLEAP,
    RUNTIME_DB_PATH,
    SAMPLE_DIR,
    SOURCE_PRIORITY,
    VARIABLES,
)

SLOTS_PER_YEAR = 372  # 12 meses * 31 días (índice determinístico m*31 + (d-1))

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS departamentos (
    codigo TEXT PRIMARY KEY,
    nombre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS municipios (
    codigo TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    departamento_codigo TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mun_depto ON municipios(departamento_codigo);

CREATE TABLE IF NOT EXISTS categorias (
    codigo TEXT PRIMARY KEY,
    descripcion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS variables (
    id INTEGER PRIMARY KEY,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    nombre_corto TEXT NOT NULL,
    unidad TEXT NOT NULL,
    agregacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS estaciones (
    codigo TEXT PRIMARY KEY,
    codigo_ideam_10 TEXT,
    nombre TEXT NOT NULL,
    categoria_codigo TEXT,
    municipio_codigo TEXT,
    departamento_codigo TEXT,
    centro_poblado TEXT,
    entidad TEXT,
    corriente TEXT,
    area_hidrografica TEXT,
    area_operativa TEXT,
    zona_hidrografica TEXT,
    subzona_hidrografica TEXT,
    tecnologia TEXT,
    fecha_instalacion TEXT,
    fecha_suspension TEXT,
    latitud REAL,
    longitud REAL,
    altitud REAL,
    estado TEXT,
    source TEXT DEFAULT 'IDEAM-Legacy',
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_est_depto ON estaciones(departamento_codigo);
CREATE INDEX IF NOT EXISTS idx_est_mun ON estaciones(municipio_codigo);
CREATE INDEX IF NOT EXISTS idx_est_cat ON estaciones(categoria_codigo);
CREATE INDEX IF NOT EXISTS idx_est_estado ON estaciones(estado);
CREATE INDEX IF NOT EXISTS idx_est_coords ON estaciones(latitud, longitud);

CREATE TABLE IF NOT EXISTS series_anuales (
    station_code TEXT NOT NULL,
    var_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'IDEAM-Legacy',
    updated_at TEXT NOT NULL,
    data_blob BLOB NOT NULL,
    valid_count INTEGER NOT NULL,
    annual_sum REAL,
    annual_mean REAL,
    annual_max REAL,
    annual_min REAL,
    PRIMARY KEY (station_code, var_id, year, source)
);
CREATE INDEX IF NOT EXISTS idx_series_stn_yr ON series_anuales(station_code, year);
CREATE INDEX IF NOT EXISTS idx_series_yr_var ON series_anuales(year, var_id);

CREATE TABLE IF NOT EXISTS sync_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    action TEXT NOT NULL,
    stations_count INTEGER DEFAULT 0,
    records_count INTEGER DEFAULT 0,
    year_min INTEGER,
    year_max INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    location TEXT,
    config_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def pack_372(values: np.ndarray) -> bytes:
    """Empaqueta un arreglo float32 de 372 posiciones con zlib."""
    arr = np.asarray(values, dtype=np.float32)
    if arr.shape != (SLOTS_PER_YEAR,):
        raise ValueError(f"Se esperaba forma (372,), recibido {arr.shape}")
    return zlib.compress(arr.tobytes(), level=6)


def unpack_372(blob: bytes) -> np.ndarray:
    """Desempaqueta un blob zlib a arreglo float32 de 372 posiciones."""
    raw = zlib.decompress(blob)
    return np.frombuffer(raw, dtype=np.float32).copy()


def compute_year_stats(arr: np.ndarray, year: int) -> tuple[int, float | None, float | None, float | None, float | None]:
    """Calcula estadísticas válidas del año calendario evitando días inexistentes (ej. 30 Feb)."""
    days_per_month = DAYS_IN_MONTH_LEAP if calendar.isleap(year) else DAYS_IN_MONTH_NONLEAP
    valid_vals = []
    for m in range(12):
        sl = arr[m * 31 : m * 31 + days_per_month[m]]
        mask = ~np.isnan(sl)
        if mask.any():
            valid_vals.append(sl[mask])
    if not valid_vals:
        return 0, None, None, None, None
    joined = np.concatenate(valid_vals).astype(np.float64)
    return (
        int(joined.size),
        float(np.sum(joined)),
        float(np.mean(joined)),
        float(np.max(joined)),
        float(np.min(joined)),
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _year_dates(year: int) -> list[pd.Timestamp]:
    days_per_month = DAYS_IN_MONTH_LEAP if calendar.isleap(year) else DAYS_IN_MONTH_NONLEAP
    dates: list[pd.Timestamp] = []
    for m in range(1, 13):
        for d in range(1, days_per_month[m - 1] + 1):
            dates.append(pd.Timestamp(year=year, month=m, day=d))
    return dates


def _extract_valid_calendar_values(arr: np.ndarray, year: int) -> np.ndarray:
    days_per_month = DAYS_IN_MONTH_LEAP if calendar.isleap(year) else DAYS_IN_MONTH_NONLEAP
    parts = [arr[m * 31 : m * 31 + days_per_month[m]] for m in range(12)]
    return np.concatenate(parts).astype(np.float64)


class ClimateDatabase:
    """Repositorio SQLite principal de HidroClima Studio."""

    def __init__(self, db_path: Path | str | None = None, auto_bootstrap: bool = True) -> None:
        self.db_path = Path(db_path) if db_path else RUNTIME_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if auto_bootstrap:
            self._bootstrap_if_needed()
        else:
            self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            # Garantizar tabla variables sincronizada con config.VARIABLES
            var_rows = [
                (v.id, v.codigo, v.nombre, v.nombre_corto, v.unidad, v.agregacion)
                for v in VARIABLES.values()
            ]
            conn.executemany(
                "INSERT OR REPLACE INTO variables (id, codigo, nombre, nombre_corto, unidad, agregacion) VALUES (?,?,?,?,?,?)",
                var_rows,
            )

    def _bootstrap_if_needed(self) -> None:
        existed = self.db_path.exists() and self.db_path.stat().st_size > 0
        if not existed and CATALOG_DB_PATH.exists() and self.db_path != CATALOG_DB_PATH:
            shutil.copy2(CATALOG_DB_PATH, self.db_path)
        self.init_schema()

        with self.connect() as conn:
            series_cnt = conn.execute("SELECT COUNT(*) FROM series_anuales").fetchone()[0]
            stn_cnt = conn.execute("SELECT COUNT(*) FROM estaciones").fetchone()[0]

        if series_cnt == 0 and stn_cnt > 0:
            sample_gz = SAMPLE_DIR / "sample_series.json.gz"
            if sample_gz.exists():
                self.load_sample_series_gz(sample_gz)

    def load_sample_series_gz(self, path: Path) -> int:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        rows = []
        now = utc_now_iso()
        for item in payload.get("records", []):
            arr = np.array([float(x) if x is not None else np.nan for x in item["values"]], dtype=np.float32)
            yr = int(item["year"])
            vc, s_sum, s_mean, s_max, s_min = compute_year_stats(arr, yr)
            if vc == 0:
                continue
            rows.append(
                (
                    str(item["station_code"]),
                    int(item["var_id"]),
                    yr,
                    item.get("source", "IDEAM-Legacy"),
                    item.get("updated_at", now),
                    pack_372(arr),
                    vc,
                    s_sum,
                    s_mean,
                    s_max,
                    s_min,
                )
            )
        if not rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO series_anuales
                (station_code, var_id, year, source, updated_at, data_blob, valid_count, annual_sum, annual_mean, annual_max, annual_min)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )
            conn.execute(
                "INSERT INTO sync_history (timestamp, source, action, stations_count, records_count, year_min, year_max, notes) VALUES (?,?,?,?,?,?,?,?)",
                (
                    now,
                    "Sample-Bundle",
                    "bootstrap",
                    len({r[0] for r in rows}),
                    len(rows),
                    min(r[2] for r in rows),
                    max(r[2] for r in rows),
                    "Carga automática de estaciones de referencia y Ejemplo Bogotá D.C.",
                ),
            )
        return len(rows)

    def get_database_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            total_stations = conn.execute("SELECT COUNT(*) FROM estaciones").fetchone()[0]
            active_stations = conn.execute("SELECT COUNT(*) FROM estaciones WHERE estado='Activa'").fetchone()[0]
            stations_with_data = conn.execute("SELECT COUNT(DISTINCT station_code) FROM series_anuales").fetchone()[0]
            total_series = conn.execute("SELECT COUNT(*) FROM series_anuales").fetchone()[0]
            yr_row = conn.execute("SELECT MIN(year) AS min_y, MAX(year) AS max_y FROM series_anuales").fetchone()
            src_rows = conn.execute(
                "SELECT source, COUNT(*) AS cnt, MAX(year) AS max_y FROM series_anuales GROUP BY source ORDER BY cnt DESC"
            ).fetchall()
            syncs = conn.execute(
                "SELECT id, timestamp, source, action, stations_count, records_count, year_min, year_max, notes FROM sync_history ORDER BY id DESC LIMIT 15"
            ).fetchall()
        return {
            "db_path": str(self.db_path),
            "db_size_mb": round(self.db_path.stat().st_size / (1024 * 1024), 2) if self.db_path.exists() else 0.0,
            "total_stations": total_stations,
            "active_stations": active_stations,
            "stations_with_data": stations_with_data,
            "total_annual_series": total_series,
            "year_min": yr_row["min_y"],
            "year_max": yr_row["max_y"],
            "sources": [dict(r) for r in src_rows],
            "recent_syncs": [dict(r) for r in syncs],
        }

    def list_catalog_filters(self) -> dict[str, Any]:
        with self.connect() as conn:
            deptos = [dict(r) for r in conn.execute("SELECT codigo, nombre FROM departamentos ORDER BY nombre").fetchall()]
            muns = [dict(r) for r in conn.execute("SELECT codigo, nombre, departamento_codigo FROM municipios ORDER BY nombre").fetchall()]
            cats = [dict(r) for r in conn.execute("SELECT codigo, descripcion FROM categorias ORDER BY descripcion").fetchall()]
            vars_list = [dict(r) for r in conn.execute("SELECT id, codigo, nombre, nombre_corto, unidad, agregacion FROM variables ORDER BY id").fetchall()]
        return {
            "departamentos": deptos,
            "municipios": muns,
            "categorias": cats,
            "variables": vars_list,
        }

    def search_stations(
        self,
        query: str = "",
        departamento: str = "",
        municipio: str = "",
        categoria: str = "",
        estado: str = "",
        only_with_data: bool = False,
        required_vars: list[int] | None = None,
        filter_year: int | None = None,
        precip_min: float | None = None,
        precip_max: float | None = None,
        temp_min: float | None = None,
        temp_max: float | None = None,
        center_lat: float | None = None,
        center_lon: float | None = None,
        radius_km: float | None = None,
        route_coords: list[tuple[float, float]] | None = None,
        route_buffer_km: float = 15.0,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT e.*, d.nombre AS departamento_nombre, m.nombre AS municipio_nombre, c.descripcion AS categoria_nombre
            FROM estaciones e
            LEFT JOIN departamentos d ON e.departamento_codigo = d.codigo
            LEFT JOIN municipios m ON e.municipio_codigo = m.codigo
            LEFT JOIN categorias c ON e.categoria_codigo = c.codigo
            WHERE 1=1
        """
        params: list[Any] = []
        if query.strip():
            q = f"%{query.strip()}%"
            sql += " AND (e.codigo LIKE ? OR e.nombre LIKE ? OR e.centro_poblado LIKE ? OR e.corriente LIKE ? OR m.nombre LIKE ?)"
            params.extend([q, q, q, q, q])
        if departamento:
            sql += " AND e.departamento_codigo = ?"
            params.append(departamento.zfill(2) if departamento.isdigit() else departamento)
        if municipio:
            sql += " AND e.municipio_codigo = ?"
            params.append(municipio.zfill(5) if municipio.isdigit() else municipio)
        if categoria:
            sql += " AND e.categoria_codigo = ?"
            params.append(categoria)
        if estado:
            sql += " AND UPPER(e.estado) = UPPER(?)"
            params.append(estado)
        if only_with_data:
            sql += " AND EXISTS (SELECT 1 FROM series_anuales s WHERE s.station_code = e.codigo)"

        if required_vars:
            for vid in required_vars:
                sql += " AND EXISTS (SELECT 1 FROM series_anuales s WHERE s.station_code = e.codigo AND s.var_id = ?)"
                params.append(int(vid))

        if precip_min is not None or precip_max is not None:
            yr_clause = "AND s.year = ?" if filter_year else ""
            conds = []
            if precip_min is not None:
                conds.append("s.annual_sum >= ?")
                params.append(float(precip_min))
            if precip_max is not None:
                conds.append("s.annual_sum <= ?")
                params.append(float(precip_max))
            if filter_year:
                params.append(int(filter_year))
            sql += f" AND EXISTS (SELECT 1 FROM series_anuales s WHERE s.station_code = e.codigo AND s.var_id = 1 AND {' AND '.join(conds)} {yr_clause})"

        if temp_min is not None or temp_max is not None:
            conds = []
            if temp_min is not None:
                conds.append("s.annual_mean >= ?")
                params.append(float(temp_min))
            if temp_max is not None:
                conds.append("s.annual_mean <= ?")
                params.append(float(temp_max))
            yr_clause = ""
            if filter_year:
                yr_clause = "AND s.year = ?"
                params.append(int(filter_year))
            sql += f" AND EXISTS (SELECT 1 FROM series_anuales s WHERE s.station_code = e.codigo AND s.var_id = 5 AND {' AND '.join(conds)} {yr_clause})"

        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

            # Adjuntar resumen de datos disponibles en un solo query
            meta_rows = conn.execute(
                """
                SELECT station_code,
                       GROUP_CONCAT(DISTINCT var_id) AS vars_csv,
                       MIN(year) AS min_year,
                       MAX(year) AS max_year,
                       COUNT(*) AS series_count
                FROM series_anuales
                GROUP BY station_code
                """
            ).fetchall()
            data_map = {r["station_code"]: dict(r) for r in meta_rows}

        for st in rows:
            info = data_map.get(st["codigo"])
            if info:
                st["available_vars"] = sorted(int(x) for x in info["vars_csv"].split(",") if x)
                st["min_year"] = info["min_year"]
                st["max_year"] = info["max_year"]
                st["series_count"] = info["series_count"]
                st["has_data"] = True
            else:
                st["available_vars"] = []
                st["min_year"] = None
                st["max_year"] = None
                st["series_count"] = 0
                st["has_data"] = False

        # Filtrado espacial vectorizado
        if rows and route_coords and len(route_coords) >= 1:
            lats = np.array([r["latitud"] if r["latitud"] is not None else np.nan for r in rows], dtype=float)
            lons = np.array([r["longitud"] if r["longitud"] is not None else np.nan for r in rows], dtype=float)
            dists = stations_distance_to_polyline(lats, lons, route_coords)
            filtered = []
            for r, d in zip(rows, dists):
                if np.isfinite(d) and d <= route_buffer_km:
                    r["distance_km"] = round(float(d), 2)
                    filtered.append(r)
            filtered.sort(key=lambda x: x["distance_km"])
            rows = filtered
        elif rows and center_lat is not None and center_lon is not None and radius_km is not None:
            lats = np.array([r["latitud"] if r["latitud"] is not None else np.nan for r in rows], dtype=float)
            lons = np.array([r["longitud"] if r["longitud"] is not None else np.nan for r in rows], dtype=float)
            dists = haversine_vectorized_km(center_lat, center_lon, lats, lons)
            filtered = []
            for r, d in zip(rows, dists):
                if np.isfinite(d) and d <= radius_km:
                    r["distance_km"] = round(float(d), 2)
                    filtered.append(r)
            filtered.sort(key=lambda x: x["distance_km"])
            rows = filtered

        if limit and len(rows) > limit:
            rows = rows[:limit]
        return rows

    def get_stations_by_codes(self, codes: list[str]) -> list[dict[str, Any]]:
        if not codes:
            return []
        clean = [c.strip() for c in codes if c.strip()]
        placeholders = ",".join("?" for _ in clean)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT e.*, d.nombre AS departamento_nombre, m.nombre AS municipio_nombre, c.descripcion AS categoria_nombre
                FROM estaciones e
                LEFT JOIN departamentos d ON e.departamento_codigo = d.codigo
                LEFT JOIN municipios m ON e.municipio_codigo = m.codigo
                LEFT JOIN categorias c ON e.categoria_codigo = c.codigo
                WHERE e.codigo IN ({placeholders})
                """,
                clean,
            ).fetchall()
        by_code = {r["codigo"]: dict(r) for r in rows}
        return [by_code[c] for c in clean if c in by_code]

    def get_station_detail(self, code: str) -> dict[str, Any] | None:
        stns = self.get_stations_by_codes([code])
        if not stns:
            return None
        stn = stns[0]
        with self.connect() as conn:
            summary = conn.execute(
                """
                SELECT var_id, source, MIN(year) AS min_year, MAX(year) AS max_year,
                       COUNT(*) AS years_count, SUM(valid_count) AS total_days
                FROM series_anuales
                WHERE station_code = ?
                GROUP BY var_id, source
                ORDER BY var_id, source
                """,
                (code,),
            ).fetchall()
        stn["series_summary"] = [dict(r) for r in summary]
        return stn

    def upsert_stations(self, stations: list[dict[str, Any]], source: str = "IDEAM-API") -> int:
        if not stations:
            return 0
        now = utc_now_iso()
        rows = []
        for s in stations:
            code = str(s["codigo"]).strip()
            mun = str(s.get("municipio_codigo") or "").strip()
            if mun.isdigit() and len(mun) <= 5:
                mun = mun.zfill(5)
            depto = str(s.get("departamento_codigo") or (mun[:2] if len(mun) >= 2 else "")).strip()
            rows.append(
                (
                    code,
                    s.get("codigo_ideam_10") or code.zfill(10),
                    s.get("nombre", "").strip(),
                    s.get("categoria_codigo", ""),
                    mun,
                    depto,
                    s.get("centro_poblado", ""),
                    s.get("entidad", ""),
                    s.get("corriente", ""),
                    s.get("area_hidrografica", ""),
                    s.get("area_operativa", ""),
                    s.get("zona_hidrografica", ""),
                    s.get("subzona_hidrografica", ""),
                    s.get("tecnologia", ""),
                    s.get("fecha_instalacion", ""),
                    s.get("fecha_suspension", ""),
                    s.get("latitud"),
                    s.get("longitud"),
                    s.get("altitud"),
                    s.get("estado", "Activa"),
                    source,
                    now,
                )
            )
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO estaciones (
                    codigo, codigo_ideam_10, nombre, categoria_codigo, municipio_codigo,
                    departamento_codigo, centro_poblado, entidad, corriente,
                    area_hidrografica, area_operativa, zona_hidrografica, subzona_hidrografica,
                    tecnologia, fecha_instalacion, fecha_suspension, latitud, longitud, altitud,
                    estado, source, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(codigo) DO UPDATE SET
                    nombre=COALESCE(NULLIF(excluded.nombre,''), estaciones.nombre),
                    categoria_codigo=COALESCE(NULLIF(excluded.categoria_codigo,''), estaciones.categoria_codigo),
                    entidad=COALESCE(NULLIF(excluded.entidad,''), estaciones.entidad),
                    tecnologia=COALESCE(NULLIF(excluded.tecnologia,''), estaciones.tecnologia),
                    latitud=COALESCE(excluded.latitud, estaciones.latitud),
                    longitud=COALESCE(excluded.longitud, estaciones.longitud),
                    altitud=COALESCE(excluded.altitud, estaciones.altitud),
                    estado=COALESCE(NULLIF(excluded.estado,''), estaciones.estado),
                    fecha_suspension=COALESCE(NULLIF(excluded.fecha_suspension,''), estaciones.fecha_suspension),
                    updated_at=excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def upsert_annual_series(
        self,
        records: list[tuple[str, int, int, str, np.ndarray]],
    ) -> int:
        """Inserta o actualiza series anuales. Cada tupla: (station_code, var_id, year, source, arr_372)."""
        if not records:
            return 0
        now = utc_now_iso()
        db_rows = []
        for stn, vid, yr, src, arr in records:
            arr32 = np.asarray(arr, dtype=np.float32)
            vc, s_sum, s_mean, s_max, s_min = compute_year_stats(arr32, int(yr))
            if vc == 0:
                continue
            db_rows.append(
                (
                    str(stn).strip(),
                    int(vid),
                    int(yr),
                    src,
                    now,
                    pack_372(arr32),
                    vc,
                    s_sum,
                    s_mean,
                    s_max,
                    s_min,
                )
            )
        if not db_rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO series_anuales
                (station_code, var_id, year, source, updated_at, data_blob, valid_count, annual_sum, annual_mean, annual_max, annual_min)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                db_rows,
            )
        return len(db_rows)

    def log_sync(
        self,
        source: str,
        action: str,
        stations_count: int = 0,
        records_count: int = 0,
        year_min: int | None = None,
        year_max: int | None = None,
        notes: str = "",
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_history (timestamp, source, action, stations_count, records_count, year_min, year_max, notes)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (utc_now_iso(), source, action, stations_count, records_count, year_min, year_max, notes),
            )

    def get_station_daily_dataframe(
        self,
        station_code: str,
        var_ids: list[int] | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        allowed_sources: list[str] | None = None,
        fill_gaps_with_secondary: bool = True,
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        """
        Devuelve DataFrame diario indexado por fecha para una estación, fusionando fuentes según prioridad.
        Retorna (df, source_day_counts).
        """
        vids = var_ids or list(VARIABLES.keys())
        sources_order = allowed_sources or SOURCE_PRIORITY
        prio_rank = {src: idx for idx, src in enumerate(sources_order)}

        sql = """
            SELECT var_id, year, source, data_blob
            FROM series_anuales
            WHERE station_code = ?
        """
        params: list[Any] = [station_code]
        if start_year is not None:
            sql += " AND year >= ?"
            params.append(int(start_year))
        if end_year is not None:
            sql += " AND year <= ?"
            params.append(int(end_year))
        placeholders = ",".join("?" for _ in vids)
        sql += f" AND var_id IN ({placeholders})"
        params.extend([int(v) for v in vids])

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        if not rows:
            return pd.DataFrame(), {}

        # Agrupar por (year, var_id) ordenando fuentes por prioridad
        grouped: dict[tuple[int, int], list[tuple[int, str, np.ndarray]]] = {}
        years_set: set[int] = set()
        for r in rows:
            src = r["source"]
            if allowed_sources is not None and src not in prio_rank:
                continue
            rank = prio_rank.get(src, 999)
            yr = int(r["year"])
            vid = int(r["var_id"])
            years_set.add(yr)
            grouped.setdefault((yr, vid), []).append((rank, src, unpack_372(r["data_blob"])))

        if not years_set:
            return pd.DataFrame(), {}

        min_y, max_y = min(years_set), max(years_set)
        all_dates: list[pd.Timestamp] = []
        for yr in range(min_y, max_y + 1):
            all_dates.extend(_year_dates(yr))

        index = pd.DatetimeIndex(all_dates, name="date")
        data_cols: dict[int, np.ndarray] = {vid: np.full(len(index), np.nan, dtype=np.float64) for vid in vids}
        source_counts: dict[str, int] = {}

        year_offsets: dict[int, tuple[int, int]] = {}
        pos = 0
        for yr in range(min_y, max_y + 1):
            n_days = 366 if calendar.isleap(yr) else 365
            year_offsets[yr] = (pos, pos + n_days)
            pos += n_days

        for (yr, vid), candidates in grouped.items():
            candidates.sort(key=lambda x: x[0])
            start_idx, end_idx = year_offsets[yr]
            merged = np.full(end_idx - start_idx, np.nan, dtype=np.float64)
            for idx_c, (_rank, src, arr372) in enumerate(candidates):
                vals = _extract_valid_calendar_values(arr372, yr)
                if idx_c == 0 or not fill_gaps_with_secondary:
                    valid = ~np.isnan(vals)
                    merged[valid] = vals[valid]
                    source_counts[src] = source_counts.get(src, 0) + int(valid.sum())
                    if not fill_gaps_with_secondary:
                        break
                else:
                    need = np.isnan(merged) & (~np.isnan(vals))
                    if need.any():
                        merged[need] = vals[need]
                        source_counts[src] = source_counts.get(src, 0) + int(need.sum())
            data_cols[vid][start_idx:end_idx] = merged

        df = pd.DataFrame({vid: data_cols[vid] for vid in vids}, index=index)
        return df, source_counts

    def get_year_matrix(self, station_code: str, var_id: int, year: int) -> dict[str, Any]:
        """Devuelve matriz 12x31 de un año/estación/variable para edición o inspección."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT source, data_blob, updated_at FROM series_anuales WHERE station_code=? AND var_id=? AND year=?",
                (station_code, int(var_id), int(year)),
            ).fetchall()
        if not rows:
            return {"station_code": station_code, "var_id": var_id, "year": year, "sources": [], "matrix": [[None]*31 for _ in range(12)]}
        prio = {s: i for i, s in enumerate(SOURCE_PRIORITY)}
        rows_sorted = sorted(rows, key=lambda r: prio.get(r["source"], 999))
        chosen = rows_sorted[0]
        arr = unpack_372(chosen["data_blob"])
        days_per_month = DAYS_IN_MONTH_LEAP if calendar.isleap(year) else DAYS_IN_MONTH_NONLEAP
        matrix = []
        for m in range(12):
            row_m = []
            for d in range(31):
                if d >= days_per_month[m]:
                    row_m.append(None)
                else:
                    v = float(arr[m * 31 + d])
                    row_m.append(None if np.isnan(v) else round(v, 3))
            matrix.append(row_m)
        return {
            "station_code": station_code,
            "var_id": var_id,
            "year": year,
            "active_source": chosen["source"],
            "updated_at": chosen["updated_at"],
            "available_sources": [r["source"] for r in rows_sorted],
            "matrix": matrix,
        }

    def save_year_matrix(
        self, station_code: str, var_id: int, year: int, matrix: list[list[float | None]], source: str = "Manual"
    ) -> int:
        arr = np.full(SLOTS_PER_YEAR, np.nan, dtype=np.float32)
        days_per_month = DAYS_IN_MONTH_LEAP if calendar.isleap(year) else DAYS_IN_MONTH_NONLEAP
        for m in range(12):
            for d in range(days_per_month[m]):
                val = matrix[m][d] if m < len(matrix) and d < len(matrix[m]) else None
                if val is not None:
                    arr[m * 31 + d] = float(val)
        return self.upsert_annual_series([(station_code, var_id, year, source, arr)])

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, name, description, location, updated_at, config_json FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["config"] = json.loads(d.pop("config_json"))
            out.append(d)
        return out

    def save_project(self, project_id: str, name: str, description: str, location: str, config: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO projects (id, name, description, location, config_json, updated_at)
                VALUES (?,?,?,?,?,?)
                """,
                (project_id, name, description, location, json.dumps(config, ensure_ascii=False), utc_now_iso()),
            )

    def delete_project(self, project_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
            return cur.rowcount > 0
