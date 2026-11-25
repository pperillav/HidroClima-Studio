window.ClimaMap = (() => {
  let map = null;
  let clusterGroup = null;
  let routeLayer = null;
  let drawMode = false;
  let routeCoords = [];
  let onRouteChanged = null;
  let onAddStation = null;
  let onInspectStation = null;
  let onCursorMove = null;

  function init(callbacks) {
    onRouteChanged = callbacks.onRouteChanged;
    onAddStation = callbacks.onAddStation;
    onInspectStation = callbacks.onInspectStation;
    onCursorMove = callbacks.onCursorMove;

    const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 18,
    });
    const sat = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { attribution: "&copy; Esri World Imagery", maxZoom: 18 }
    );
    const topo = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenTopoMap",
      maxZoom: 17,
    });

    map = L.map("leafletMap", {
      center: [4.57, -74.29],
      zoom: 6,
      layers: [osm],
    });

    L.control.layers({ "Mapa Calle (OSM)": osm, "Satélite (ESRI)": sat, "Topográfico": topo }).addTo(map);
    L.control.scale({ metric: true, imperial: false }).addTo(map);
    clusterGroup = L.markerClusterGroup({ chunkedLoading: true, maxClusterRadius: 45 });
    map.addLayer(clusterGroup);

    map.on("mousemove", (e) => {
      if (onCursorMove) {
        onCursorMove(e.latlng.lat, e.latlng.lng);
      }
    });

    map.on("click", (e) => {
      if (!drawMode) return;
      routeCoords.push([Number(e.latlng.lat.toFixed(6)), Number(e.latlng.lng.toFixed(6))]);
      renderRoute();
      if (onRouteChanged) onRouteChanged(routeCoords);
    });
  }

  function setStations(stations, selectedSet) {
    if (!map || !clusterGroup) return;
    clusterGroup.clearLayers();
    const markers = [];

    for (const st of stations) {
      if (st.latitud == null || st.longitud == null) continue;
      const isSelected = selectedSet.has(st.codigo);
      let color = "#94a3b8";
      if (isSelected) color = "#00897b";
      else if (st.has_data) color = "#0072b2";
      else if ((st.estado || "").toLowerCase() === "activa") color = "#d97706";

      const m = L.circleMarker([st.latitud, st.longitud], {
        radius: isSelected ? 8 : 6,
        color: "#ffffff",
        weight: 1.5,
        fillColor: color,
        fillOpacity: 0.92,
      });

      const varsBadge = st.available_vars && st.available_vars.length
        ? `${st.min_year}–${st.max_year} (${st.available_vars.length} vars)`
        : "Sin series locales";

      const popupHtml = `
        <div style="min-width:225px;font-size:12px">
          <strong>${st.codigo} — ${st.nombre}</strong><br/>
          <span style="color:#64748b">${st.categoria_nombre || st.categoria_codigo || ""} · ${st.estado || ""}</span><br/>
          <div>Mun: ${st.municipio_nombre || ""} (${st.departamento_nombre || ""})</div>
          <div>Altitud: <b>${st.altitud ?? "-"} m</b> · Coord: ${Number(st.latitud).toFixed(4)}, ${Number(st.longitud).toFixed(4)}</div>
          <div>Datos: <b>${varsBadge}</b></div>
          <div style="margin-top:8px;display:flex;gap:6px">
            <button onclick="window.__mapAddStation('${st.codigo}')" style="padding:4px 8px;border:none;border-radius:4px;background:#0072b2;color:#fff;cursor:pointer;font-weight:600">+ Proyecto</button>
            <button onclick="window.__mapInspectStation('${st.codigo}')" style="padding:4px 8px;border:1px solid #cbd5e1;border-radius:4px;background:#f8fafc;cursor:pointer">Inspeccionar</button>
          </div>
        </div>
      `;
      m.bindPopup(popupHtml);
      markers.push(m);
    }

    clusterGroup.addLayers(markers);
    window.__mapAddStation = (code) => onAddStation && onAddStation(code);
    window.__mapInspectStation = (code) => onInspectStation && onInspectStation(code);
  }

  function setRoute(coords) {
    routeCoords = coords ? coords.map((p) => [Number(p[0]), Number(p[1])]) : [];
    renderRoute();
    if (onRouteChanged) onRouteChanged(routeCoords);
    if (routeLayer && routeCoords.length >= 2) {
      map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });
    }
  }

  function getRoute() {
    return routeCoords;
  }

  function renderRoute() {
    if (!map) return;
    if (routeLayer) {
      map.removeLayer(routeLayer);
      routeLayer = null;
    }
    if (routeCoords.length >= 1) {
      routeLayer = L.featureGroup();
      if (routeCoords.length >= 2) {
        L.polyline(routeCoords, { color: "#dc2626", weight: 3.5, dashArray: "6,4" }).addTo(routeLayer);
      }
      routeCoords.forEach((pt, idx) => {
        L.circleMarker(pt, {
          radius: 4.5,
          color: "#ffffff",
          weight: 1.5,
          fillColor: idx === 0 ? "#16a34a" : "#dc2626",
          fillOpacity: 1,
        }).addTo(routeLayer);
      });
      routeLayer.addTo(map);
    }
  }

  function startDraw() {
    drawMode = true;
    map.getContainer().style.cursor = "crosshair";
  }

  function stopDraw() {
    drawMode = false;
    map.getContainer().style.cursor = "";
  }

  function clearRoute() {
    stopDraw();
    routeCoords = [];
    renderRoute();
    if (onRouteChanged) onRouteChanged([]);
  }

  function fitColombia() {
    if (map) map.setView([4.57, -74.29], 6);
  }

  function fitStations(stations) {
    const pts = stations.filter((s) => s.latitud != null && s.longitud != null).map((s) => [s.latitud, s.longitud]);
    if (pts.length && map) {
      map.fitBounds(pts, { padding: [35, 35], maxZoom: 11 });
    }
  }

  function invalidateSize() {
    if (map) setTimeout(() => map.invalidateSize(), 120);
  }

  return {
    init,
    setStations,
    setRoute,
    getRoute,
    startDraw,
    stopDraw,
    clearRoute,
    fitColombia,
    fitStations,
    invalidateSize,
  };
})();
