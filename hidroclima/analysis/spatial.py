"""Cálculos geoespaciales: distancias Haversine, corredores KML/GeoJSON, IDW y polígonos de Thiessen."""

from __future__ import annotations

import json
import math
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia geodésica Haversine en kilómetros entre dos puntos (WGS84)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def haversine_vectorized_km(
    lat1: float, lon1: float, lats: np.ndarray, lons: np.ndarray
) -> np.ndarray:
    """Distancia Haversine vectorizada desde un punto a arreglos de coordenadas."""
    phi1 = math.radians(lat1)
    lam1 = math.radians(lon1)
    phi2 = np.radians(lats)
    lam2 = np.radians(lons)
    dphi = phi2 - phi1
    dlam = lam2 - lam1
    a = np.sin(dphi / 2.0) ** 2 + math.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def point_to_polyline_km(
    lat: float, lon: float, polyline: list[tuple[float, float]]
) -> float:
    """Distancia mínima aproximada en km desde (lat, lon) a una polilínea [(lat, lon), ...]."""
    if not polyline:
        return float("inf")
    if len(polyline) == 1:
        return haversine_km(lat, lon, polyline[0][0], polyline[0][1])

    mean_lat = math.radians(sum(p[0] for p in polyline) / len(polyline))
    kx = EARTH_RADIUS_KM * math.cos(mean_lat) * math.pi / 180.0
    ky = EARTH_RADIUS_KM * math.pi / 180.0

    px = lon * kx
    py = lat * ky
    min_d2 = float("inf")

    for i in range(len(polyline) - 1):
        ax, ay = polyline[i][1] * kx, polyline[i][0] * ky
        bx, by = polyline[i + 1][1] * kx, polyline[i + 1][0] * ky
        vx, vy = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        seg_len2 = vx * vx + vy * vy
        if seg_len2 <= 1e-12:
            d2 = wx * wx + wy * wy
        else:
            t = max(0.0, min(1.0, (wx * vx + wy * vy) / seg_len2))
            cx, cy = ax + t * vx, ay + t * vy
            d2 = (px - cx) ** 2 + (py - cy) ** 2
        if d2 < min_d2:
            min_d2 = d2

    return math.sqrt(min_d2)


def stations_distance_to_polyline(
    lats: np.ndarray, lons: np.ndarray, polyline: list[tuple[float, float]]
) -> np.ndarray:
    """Calcula distancia mínima en km de cada estación a una polilínea."""
    if not polyline:
        return np.full(len(lats), np.inf)
    if len(polyline) == 1:
        return haversine_vectorized_km(polyline[0][0], polyline[0][1], lats, lons)

    mean_lat = math.radians(sum(p[0] for p in polyline) / len(polyline))
    kx = EARTH_RADIUS_KM * math.cos(mean_lat) * math.pi / 180.0
    ky = EARTH_RADIUS_KM * math.pi / 180.0

    px = lons * kx
    py = lats * ky
    min_d2 = np.full(len(lats), np.inf)

    for i in range(len(polyline) - 1):
        ax, ay = polyline[i][1] * kx, polyline[i][0] * ky
        bx, by = polyline[i + 1][1] * kx, polyline[i + 1][0] * ky
        vx, vy = bx - ax, by - ay
        seg_len2 = vx * vx + vy * vy
        if seg_len2 <= 1e-12:
            d2 = (px - ax) ** 2 + (py - ay) ** 2
        else:
            t = np.clip(((px - ax) * vx + (py - ay) * vy) / seg_len2, 0.0, 1.0)
            cx = ax + t * vx
            cy = ay + t * vy
            d2 = (px - cx) ** 2 + (py - cy) ** 2
        min_d2 = np.minimum(min_d2, d2)

    return np.sqrt(min_d2)


def detect_invias_region(lat: float, lon: float, departamento: str = "") -> str:
    """Sugiere la región IDF colombiana (Vargas & Díaz-Granados / INVIAS) según ubicación."""
    dep = (departamento or "").upper()
    if any(k in dep for k in ["ATLANTICO", "BOLIVAR", "CESAR", "CORDOBA", "LA GUAJIRA", "GUAJIRA", "MAGDALENA", "SUCRE", "SAN ANDRES"]):
        return "Caribe"
    if any(k in dep for k in ["CHOCO"]):
        return "Pacífico"
    if any(k in dep for k in ["ARAUCA", "CASANARE", "META", "VICHADA", "AMAZONAS", "GUAINIA", "GUAVIARE", "VAUPES", "PUTUMAYO", "CAQUETA"]):
        return "Orinoquía"
    if lon < -76.9 and 1.0 <= lat <= 8.5:
        return "Pacífico"
    if lat >= 8.2:
        return "Caribe"
    if lon > -72.8 and lat < 7.0:
        return "Orinoquía"
    return "Andina"


def compute_idw_weights(
    stations: list[dict],
    target_lat: float | None = None,
    target_lon: float | None = None,
    polyline: list[tuple[float, float]] | None = None,
    power: float = 2.0,
) -> dict[str, float]:
    """Calcula pesos normalizados por Distancia Inversa Ponderada (IDW)."""
    if not stations:
        return {}
    if len(stations) == 1:
        return {stations[0]["codigo"]: 1.0}

    if polyline and len(polyline) >= 2:
        dists = [max(0.1, point_to_polyline_km(s["latitud"], s["longitud"], polyline)) for s in stations]
    else:
        if target_lat is None or target_lon is None:
            target_lat = sum(s["latitud"] for s in stations) / len(stations)
            target_lon = sum(s["longitud"] for s in stations) / len(stations)
        dists = [max(0.1, haversine_km(target_lat, target_lon, s["latitud"], s["longitud"])) for s in stations]

    raw = [1.0 / (d ** power) for d in dists]
    total = sum(raw)
    return {s["codigo"]: round(w / total, 6) for s, w in zip(stations, raw)}


def compute_thiessen_weights(
    stations: list[dict],
    polyline: list[tuple[float, float]] | None = None,
    buffer_km: float = 15.0,
    grid_n: int = 80,
) -> dict[str, float]:
    """Calcula pesos aproximados por polígonos de Thiessen en malla geodésica local."""
    if not stations:
        return {}
    if len(stations) == 1:
        return {stations[0]["codigo"]: 1.0}

    lats = np.array([s["latitud"] for s in stations], dtype=float)
    lons = np.array([s["longitud"] for s in stations], dtype=float)

    if polyline and len(polyline) >= 1:
        p_lats = [p[0] for p in polyline]
        p_lons = [p[1] for p in polyline]
        pad_deg = max(0.05, buffer_km / 111.0)
        lat_min, lat_max = min(p_lats) - pad_deg, max(p_lats) + pad_deg
        lon_min, lon_max = min(p_lons) - pad_deg, max(p_lons) + pad_deg
    else:
        pad_deg = max(0.1, 0.2 * max(lats.max() - lats.min(), lons.max() - lons.min(), 0.2))
        lat_min, lat_max = lats.min() - pad_deg, lats.max() + pad_deg
        lon_min, lon_max = lons.min() - pad_deg, lons.max() + pad_deg

    gx = np.linspace(lon_min, lon_max, grid_n)
    gy = np.linspace(lat_min, lat_max, grid_n)
    glon, glat = np.meshgrid(gx, gy)
    flat_lat = glat.ravel()
    flat_lon = glon.ravel()

    if polyline and len(polyline) >= 2:
        corridor_d = stations_distance_to_polyline(flat_lat, flat_lon, polyline)
        mask = corridor_d <= max(buffer_km, 2.0)
        if mask.sum() >= 20:
            flat_lat = flat_lat[mask]
            flat_lon = flat_lon[mask]

    mean_lat = math.radians(float(lats.mean()))
    cos_lat = math.cos(mean_lat)
    d2 = ((flat_lat[:, None] - lats[None, :]) ** 2) + (((flat_lon[:, None] - lons[None, :]) * cos_lat) ** 2)
    nearest = np.argmin(d2, axis=1)
    counts = np.bincount(nearest, minlength=len(stations))
    total = float(counts.sum()) or 1.0
    return {stations[i]["codigo"]: round(float(counts[i]) / total, 6) for i in range(len(stations))}


def parse_kml_or_geojson_bytes(content: bytes, filename: str = "") -> list[tuple[float, float]]:
    """Extrae coordenadas [(lat, lon), ...] desde KML, KMZ, GeoJSON o texto pegado de Google Earth."""
    name = filename.lower()
    if name.endswith(".kmz") or content[:2] == b"PK":
        with zipfile.ZipFile(BytesIO(content)) as zf:
            for member in zf.namelist():
                if member.lower().endswith(".kml"):
                    content = zf.read(member)
                    break

    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return []

    if text.startswith("{") or name.endswith(".geojson") or name.endswith(".json"):
        data = json.loads(text)
        coords: list[tuple[float, float]] = []

        def walk(obj: object) -> None:
            if isinstance(obj, dict):
                if "coordinates" in obj and isinstance(obj["coordinates"], list):
                    c = obj["coordinates"]
                    if c and isinstance(c[0], (int, float)) and len(c) >= 2:
                        coords.append((float(c[1]), float(c[0])))
                    else:
                        for item in c:
                            if isinstance(item, list):
                                if item and isinstance(item[0], (int, float)) and len(item) >= 2:
                                    coords.append((float(item[1]), float(item[0])))
                                else:
                                    walk({"coordinates": item})
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
        return coords

    # KML / XML coordinates (<coordinates>lon,lat[,alt] ...</coordinates>)
    if "<" in text and "coordinates" in text.lower():
        try:
            root = ET.fromstring(text)
            pts: list[tuple[float, float]] = []
            for elem in root.iter():
                if elem.tag.lower().endswith("coordinates") and elem.text:
                    for token in elem.text.strip().split():
                        parts = token.split(",")
                        if len(parts) >= 2:
                            lon, lat = float(parts[0]), float(parts[1])
                            pts.append((lat, lon))
            if pts:
                return pts
        except ET.ParseError:
            pass
        # Fallback regex for partial pasted KML snippets from Google Earth
        matches = re.findall(r"<coordinates[^>]*>(.*?)</coordinates>", text, flags=re.IGNORECASE | re.DOTALL)
        pts = []
        for block in matches:
            for token in block.strip().split():
                parts = token.split(",")
                if len(parts) >= 2:
                    pts.append((float(parts[1]), float(parts[0])))
        if pts:
            return pts

    # Plain coordinate pairs ("lat, lon" or "lon, lat")
    pts = []
    for line in text.splitlines():
        nums = re.findall(r"-?\d+(?:[.,]\d+)?", line)
        if len(nums) >= 2:
            a, b = float(nums[0].replace(",", ".")), float(nums[1].replace(",", "."))
            if -15 <= a <= 20 and -85 <= b <= -60:
                pts.append((a, b))
            elif -15 <= b <= 20 and -85 <= a <= -60:
                pts.append((b, a))
    return pts
