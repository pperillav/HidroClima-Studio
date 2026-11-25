(() => {
  const state = {
    catalog: { departamentos: [], municipios: [], categorias: [], variables: [] },
    foundStations: [],
    selectedStations: [],
    lastAnalysis: null,
    activeProjectId: null,
    idfLogMode: false,
  };

  function toast(msg, type = "info") {
    const container = document.getElementById("toastContainer");
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4200);
  }

  async function api(url, opts = {}) {
    const res = await fetch(url, opts);
    if (!res.ok) {
      let detail = `Error HTTP ${res.status}`;
      try {
        const j = await res.json();
        detail = j.detail || detail;
      } catch {}
      throw new Error(detail);
    }
    return res.json();
  }

  function updateStatusBar() {
    const profSel = document.getElementById("projStudyProfile");
    const etpSel = document.getElementById("projEtpMethod");
    const idfSel = document.getElementById("projIdfMethod");
    const sbProf = document.getElementById("sbProfile");
    const sbMeth = document.getElementById("sbMethod");
    const sbStns = document.getElementById("sbStations");
    if (sbProf && profSel) {
      sbProf.innerHTML = `Enfoque: <strong>${profSel.options[profSel.selectedIndex]?.text || profSel.value}</strong>`;
    }
    if (sbMeth && etpSel && idfSel) {
      const etpLbl = etpSel.value === "thornthwaite" ? "Thornthwaite" : "Penman-Monteith";
      const idfLbl = (idfSel.options[idfSel.selectedIndex]?.text || idfSel.value).split("(")[0].trim();
      sbMeth.innerHTML = `ETP: <strong>${etpLbl}</strong> | IDF: <strong>${idfLbl}</strong>`;
    }
    if (sbStns) {
      sbStns.innerHTML = `Estaciones en proyecto: <strong>${state.selectedStations.length}</strong>`;
    }
  }

  function updateRouteBadge(coords) {
    const badge = document.getElementById("routeStatusBadge");
    if (!badge) return;
    const n = (coords || []).length;
    const buf = document.getElementById("filterBufferKm")?.value || 15;
    if (n >= 2) {
      badge.textContent = `Corredor activo: ${n} vértices · Buffer ${buf} km`;
    } else if (n === 1) {
      badge.textContent = `Punto activo · Radio ${buf} km`;
    } else {
      badge.textContent = "Sin corredor activo";
    }
  }

  function switchTab(tabId) {
    document.querySelectorAll(".nav-tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tabId));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === tabId));
    if (tabId === "tab-gis") window.ClimaMap.invalidateSize();
    if (tabId === "tab-results" || tabId === "tab-eng" || tabId === "tab-thornthwaite") {
      setTimeout(() => window.ClimaCharts.resizeAll(), 80);
    }
  }

  function buildProjectConfig() {
    const route = window.ClimaMap.getRoute();
    return {
      name: document.getElementById("projName").value.trim() || "Sin Nombre",
      description: document.getElementById("projDesc").value.trim(),
      location: document.getElementById("projLocation").value.trim(),
      soil_max_reserve_mm: Number(document.getElementById("projSoilReserve").value || 100),
      water_table_m: Number(document.getElementById("projWaterTable").value || 10),
      end_year: Number(document.getElementById("projEndYear").value || 2026),
      last_n_years: Number(document.getElementById("projLastNYears").value || 0),
      etp_method: document.getElementById("projEtpMethod").value,
      study_profile: document.getElementById("projStudyProfile").value,
      idf_method: document.getElementById("projIdfMethod").value,
      idf_region: document.getElementById("projIdfRegion").value || null,
      hyetograph_tr: Number(document.getElementById("projHyetTr").value || 10),
      hyetograph_duration_min: Number(document.getElementById("projHyetDur").value || 60),
      watershed_area_km2: Number(document.getElementById("projWatershedArea")?.value || 1.0),
      watershed_length_m: Number(document.getElementById("projWatershedLength")?.value || 800),
      watershed_slope_pct: Number(document.getElementById("projWatershedSlope")?.value || 5.0),
      curve_number: Number(document.getElementById("projCurveNumber")?.value || 75),
      runoff_coeff: Number(document.getElementById("projRunoffCoeff")?.value || 0.50),
      sgc_r3_intercept: Number(document.getElementById("projSgcIntercept")?.value || 70),
      sgc_r15_slope: Number(document.getElementById("projSgcSlope")?.value || 0.47),
      stations: state.selectedStations.map((s) => ({ codigo: s.codigo, weight: Number(s.weight || 1) })),
      route_coords: route,
    };
  }

  function renderSelectedTable() {
    document.getElementById("selectedCount").textContent = state.selectedStations.length;
    document.getElementById("activeProjectLabel").textContent = `Proyecto: ${document.getElementById("projName").value.trim() || "Sin Nombre"}`;
    const tbody = document.querySelector("#selectedStationsTable tbody");
    tbody.innerHTML = state.selectedStations
      .map(
        (s, idx) => `
      <tr>
        <td class="col-nowrap"><strong>${s.codigo}</strong></td>
        <td class="col-wrap" title="${s.nombre || ""}">${s.nombre || ""}</td>
        <td><input class="weight-input" type="number" step="0.01" min="0" value="${s.weight}" data-idx="${idx}" /></td>
        <td class="col-nowrap">${s.has_data ? `${s.min_year || ""}-${s.max_year || ""}` : '<span style="color:var(--warn)">Sin datos</span>'}</td>
        <td><button class="btn btn-xs btn-danger-ghost" data-rm="${idx}">✕</button></td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll(".weight-input").forEach((inp) => {
      inp.addEventListener("change", (e) => {
        const i = Number(e.target.dataset.idx);
        state.selectedStations[i].weight = Math.max(0, Number(e.target.value || 1));
      });
    });
    tbody.querySelectorAll("[data-rm]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const i = Number(e.target.dataset.rm);
        state.selectedStations.splice(i, 1);
        renderSelectedTable();
        refreshMapMarkers();
      });
    });
    updateStatusBar();
  }

  function renderFoundTable() {
    document.getElementById("foundCount").textContent = state.foundStations.length;
    document.getElementById("mapResultInfo").textContent = `Mostrando ${state.foundStations.length.toLocaleString()} estaciones`;
    const tbody = document.querySelector("#foundStationsTable tbody");
    const selectedCodes = new Set(state.selectedStations.map((s) => s.codigo));

    tbody.innerHTML = state.foundStations
      .slice(0, 350)
      .map((s) => {
        const added = selectedCodes.has(s.codigo);
        const seriesTxt = s.has_data ? `${s.min_year}–${s.max_year} (${s.available_vars.join(",")})` : "Sin datos";
        return `
        <tr>
          <td class="col-nowrap"><strong>${s.codigo}</strong></td>
          <td class="col-wrap">${s.nombre}</td>
          <td class="col-nowrap">${s.categoria_codigo || ""}</td>
          <td class="col-wrap">${s.municipio_nombre || ""} (${s.departamento_nombre || ""})</td>
          <td class="col-nowrap">${s.altitud ?? "-"}</td>
          <td class="col-nowrap">${s.estado || ""}</td>
          <td class="col-nowrap">${s.distance_km !== undefined ? s.distance_km : "-"}</td>
          <td class="col-wrap">${seriesTxt}</td>
          <td class="col-nowrap">
            <div class="btn-row">
              <button class="btn btn-xs ${added ? "btn-ghost" : "btn-primary"}" data-add="${s.codigo}">${added ? "Incluida" : "+ Proyecto"}</button>
              <button class="btn btn-xs btn-secondary" data-insp="${s.codigo}">Ver</button>
            </div>
          </td>
        </tr>`;
      })
      .join("");

    tbody.querySelectorAll("[data-add]").forEach((btn) => {
      btn.addEventListener("click", () => addStationByCode(btn.dataset.add));
    });
    tbody.querySelectorAll("[data-insp]").forEach((btn) => {
      btn.addEventListener("click", () => inspectStation(btn.dataset.insp));
    });
  }

  function refreshMapMarkers() {
    const selectedSet = new Set(state.selectedStations.map((s) => s.codigo));
    window.ClimaMap.setStations(state.foundStations, selectedSet);
  }

  async function addStationByCode(code) {
    if (state.selectedStations.some((s) => s.codigo === code)) {
      toast(`Estación ${code} ya está en el proyecto.`);
      return;
    }
    let st = state.foundStations.find((s) => s.codigo === code);
    if (!st) {
      try {
        st = await api(`/api/stations/${code}`);
      } catch (err) {
        toast(err.message, "error");
        return;
      }
    }
    state.selectedStations.push({
      codigo: st.codigo,
      nombre: st.nombre,
      categoria_codigo: st.categoria_codigo,
      has_data: st.has_data ?? (st.series_summary && st.series_summary.length > 0),
      min_year: st.min_year,
      max_year: st.max_year,
      weight: 1,
    });
    renderSelectedTable();
    renderFoundTable();
    refreshMapMarkers();
    toast(`Estación ${code} agregada al proyecto.`, "success");
  }

  async function inspectStation(code) {
    try {
      const detail = await api(`/api/stations/${code}`);
      document.getElementById("stationModalTitle").textContent = `${detail.codigo} — ${detail.nombre}`;
      const summ = (detail.series_summary || [])
        .map(
          (r) =>
            `<tr><td>Var ${r.var_id}</td><td>${r.source}</td><td>${r.min_year}–${r.max_year}</td><td>${r.years_count} años</td><td>${r.total_days} días</td></tr>`
        )
        .join("");
      const auto = (detail.nearby_automatic || [])
        .map((a) => `<li><code>${a.codigo}</code> — ${a.nombre} (${a.distance_km} km)</li>`)
        .join("");

      document.getElementById("stationModalBody").innerHTML = `
        <p><strong>Categoría:</strong> ${detail.categoria_nombre || detail.categoria_codigo} · <strong>Estado:</strong> ${detail.estado}</p>
        <p><strong>Ubicación:</strong> ${detail.municipio_nombre || ""}, ${detail.departamento_nombre || ""} · <strong>Altitud:</strong> ${detail.altitud} m · <strong>Coord:</strong> ${detail.latitud}, ${detail.longitud}</p>
        <p><strong>Corriente:</strong> ${detail.corriente || "-"} · <strong>Entidad:</strong> ${detail.entidad || "-"}</p>
        <h4>Series Almacenadas Localmente</h4>
        ${summ ? `<table class="data-table"><thead><tr><th>Variable</th><th>Fuente</th><th>Años</th><th>Cant.</th><th>Días</th></tr></thead><tbody>${summ}</tbody></table>` : "<p class='hint'>Sin series cargadas aún en base local.</p>"}
        <h4 style="margin-top:10px">Estaciones Automáticas Cercanas (Puente Datos Abiertos)</h4>
        <ul>${auto || "<li>Ninguna en 25 km</li>"}</ul>
        <div class="btn-row" style="margin-top:12px">
          <button class="btn btn-sm btn-primary" id="modalAddStnBtn">+ Agregar al Proyecto</button>
          <button class="btn btn-sm btn-accent" id="modalSyncStnBtn">Sincronizar Esta Estación</button>
          <button class="btn btn-sm btn-secondary" id="modalEditStnBtn">Abrir en Editor</button>
        </div>
      `;
      document.getElementById("stationModal").style.display = "flex";
      document.getElementById("modalAddStnBtn").onclick = () => {
        addStationByCode(detail.codigo);
        document.getElementById("stationModal").style.display = "none";
      };
      document.getElementById("modalSyncStnBtn").onclick = () => {
        document.getElementById("syncStationCodes").value = detail.codigo;
        document.getElementById("stationModal").style.display = "none";
        switchTab("tab-bridge");
      };
      document.getElementById("modalEditStnBtn").onclick = () => {
        document.getElementById("editStationCode").value = detail.codigo;
        document.getElementById("stationModal").style.display = "none";
        switchTab("tab-bridge");
        loadMatrixEditor();
      };
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function searchStations(fitToResults = false) {
    const payload = {
      query: document.getElementById("filterQuery").value.trim(),
      departamento: document.getElementById("filterDepto").value,
      municipio: document.getElementById("filterMun").value,
      categoria: document.getElementById("filterCat").value,
      estado: document.getElementById("filterEstado").value,
      only_with_data: document.getElementById("filterOnlyWithData").checked,
      route_coords: window.ClimaMap.getRoute(),
      route_buffer_km: Number(document.getElementById("filterBufferKm").value || 15),
      limit: 2000,
    };
    try {
      const res = await api("/api/stations/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      state.foundStations = res.stations || [];
      renderFoundTable();
      refreshMapMarkers();
      updateRouteBadge(payload.route_coords);
      if (fitToResults && state.foundStations.length) {
        window.ClimaMap.fitStations(state.foundStations);
      }
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function computeWeights(method) {
    if (!state.selectedStations.length) return;
    try {
      const res = await api("/api/spatial/weights", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          station_codes: state.selectedStations.map((s) => s.codigo),
          method,
          route_coords: window.ClimaMap.getRoute(),
          buffer_km: Number(document.getElementById("filterBufferKm").value || 15),
        }),
      });
      const wMap = res.weights || {};
      state.selectedStations.forEach((s) => {
        if (wMap[s.codigo] !== undefined) s.weight = wMap[s.codigo];
      });
      renderSelectedTable();
      toast(`Pesos calculados por método ${method.toUpperCase()}.`, "success");
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function runAnalysis() {
    if (!state.selectedStations.length) {
      toast("Selecciona al menos una estación antes de analizar.", "error");
      return;
    }
    const cfg = buildProjectConfig();
    const sbEng = document.getElementById("sbEngineState");
    if (sbEng) sbEng.textContent = "Calculando modelo...";
    try {
      toast("Ejecutando cálculos hidrometeorológicos...");
      const res = await api("/api/analysis/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      });
      if (!res.has_data) {
        if (sbEng) sbEng.textContent = "Sin series locales en selección";
        toast(res.message || "Sin datos locales para estas estaciones.", "error");
        return;
      }
      state.lastAnalysis = res;
      renderAnalysisViews(res);
      switchTab(cfg.study_profile === "hidrologia" || cfg.study_profile === "pavimentos" ? "tab-eng" : "tab-results");
      toast("Análisis completado correctamente.", "success");
    } catch (err) {
      if (sbEng) sbEng.textContent = "Error de cálculo";
      toast(err.message, "error");
    }
  }

  function renderAnalysisViews(res) {
    document.getElementById("resultsEmptyState").style.display = "none";
    document.getElementById("resultsContent").style.display = "block";
    document.getElementById("engEmptyState").style.display = "none";
    document.getElementById("engContent").style.display = "block";

    const s = res.summary;
    const p = res.project;
    const pav = res.pavement;
    const idf = res.hydrology_idf;
    const cls = res.classifications || {};
    const tmapReg = pav.invias_pavement_region || {};
    const pmaVal = pav.pma_mm ?? s.annual_precip_mm;
    const sgc = res.geohazards_sgc || {};
    const ero = res.erosivity || {};
    const wshed = res.watershed || {};
    const q10 = (wshed.design_rows || []).find((r) => r.tr === 10);

    document.getElementById("kpiStrip").innerHTML = `
      <div class="kpi-card kpi-highlight"><div class="kpi-label">1. TMAP (Shell / w-MAAT)</div><div class="kpi-val">${pav.tmap_c ?? "-"} °C</div><div class="kpi-sub">Región INVIAS ${tmapReg.code || "-"} (${tmapReg.name || ""})</div></div>
      <div class="kpi-card kpi-highlight"><div class="kpi-label">2. PMA (Precip. Media Anual)</div><div class="kpi-val">${Number(pmaVal).toLocaleString()} mm/a</div><div class="kpi-sub">ETP: ${Number(s.annual_etp_mm).toLocaleString()} mm/a (${p.actual_year_min}–${p.actual_year_max})</div></div>
      <div class="kpi-card"><div class="kpi-label">Índice Thornthwaite</div><div class="kpi-val">${s.thornthwaite_index_pct}%</div><div class="kpi-sub">${s.humidity_class}</div></div>
      <div class="kpi-card"><div class="kpi-label">Caldas-Lang / Holdridge</div><div class="kpi-val">${cls.caldas_lang?.label || "-"}</div><div class="kpi-sub">${cls.holdridge?.life_zone || "-"}</div></div>
      <div class="kpi-card"><div class="kpi-label">Erosividad RUSLE (ANLA)</div><div class="kpi-val">${ero.available ? ero.r_factor_mfi : "-"}</div><div class="kpi-sub">${ero.available ? `MFI=${ero.mfi_arnoldus_mm} mm (${ero.aggressiveness_class})` : "Sin cálculo"}</div></div>
      <div class="kpi-card"><div class="kpi-label">Superpave PG (Est.)</div><div class="kpi-val">${pav.recommended_pg_grade}</div><div class="kpi-sub">T7d máx: ${pav.max_7day_tmax_c ?? pav.max_7day_tmean_c ?? "-"} °C</div></div>
    `;

    document.getElementById("badgeThornthwaiteClass").textContent = `${s.humidity_class} — ${s.humidity_description}`;

    document.getElementById("pavSummaryBanner").innerHTML = `
      <div>
        <div class="pav-metric-title">1. Temperatura Media Anual Ponderada (TMAP)</div>
        <div class="pav-metric-val">${pav.tmap_c ?? "-"} °C</div>
        <div class="pav-metric-sub">Metodología Shell Carta W (ciclo: ${pav.tmap_clim_cycle_c ?? "-"} °C · WF prom: ${pav.wf_clim_avg ?? "-"})</div>
      </div>
      <div>
        <div class="pav-metric-title">2. Precipitación Media Anual (PMA)</div>
        <div class="pav-metric-val">${Number(pmaVal).toLocaleString()} mm/año</div>
        <div class="pav-metric-sub">Exceso: ${Number(s.annual_excess_mm).toLocaleString()} mm · Déficit: ${Number(s.annual_deficit_mm).toLocaleString()} mm</div>
      </div>
      <div>
        <div class="pav-metric-title">3. Zonificación Climática Pavimentos INVIAS</div>
        <div class="pav-metric-val">Región ${tmapReg.code || "-"} — ${tmapReg.name || "-"}</div>
        <div class="pav-metric-sub">${tmapReg.criteria || ""}</div>
      </div>
    `;

    document.getElementById("engKpiStrip").innerHTML = `
      <div class="kpi-card kpi-highlight"><div class="kpi-label">P24h Máx Multianual (M)</div><div class="kpi-val">${idf.available ? idf.m_pmax_24h_mean_mm + " mm" : "N/D"}</div><div class="kpi-sub">${idf.available ? "Mejor K-S: " + idf.best_distribution : ""}</div></div>
      <div class="kpi-card"><div class="kpi-label">1. TMAP / 2. PMA</div><div class="kpi-val">${pav.tmap_c ?? "-"} °C · ${Number(pmaVal).toLocaleString()} mm</div><div class="kpi-sub">Región INVIAS ${tmapReg.code || "-"} (${tmapReg.name || ""})</div></div>
      <div class="kpi-card"><div class="kpi-label">Cuenca INVIAS (Tr=10a)</div><div class="kpi-val">${q10 ? q10.q_rational_m3s + " m³/s" : "N/D"}</div><div class="kpi-sub">${wshed.available ? `tc=${wshed.tc_kirpich_min} min | Q_SCS=${q10?.q_scs_m3s ?? "-"} m³/s` : ""}</div></div>
      <div class="kpi-card"><div class="kpi-label">Geotecnia SGC / Superpave</div><div class="kpi-val">${sgc.available ? sgc.exceedance_days + " días crít." : pav.recommended_pg_grade}</div><div class="kpi-sub">${sgc.available ? `${sgc.episodes_count} episodios | PG ${pav.recommended_pg_grade}` : `T7d=${pav.max_7day_tmax_c ?? "-"}°C`}</div></div>
    `;
    if (idf.available) {
      const pr = idf.idf_params;
      document.getElementById("badgeIdfFormula").textContent = `${pr.method_label}: ${pr.formula}`;
    }

    if (wshed.available) {
      document.getElementById("wsAreaKm2").value = wshed.area_km2;
      document.getElementById("wsLengthM").value = wshed.length_m;
      document.getElementById("wsSlopePct").value = wshed.slope_pct;
      document.getElementById("wsCn").value = wshed.curve_number;
      document.getElementById("wsCoeffC").value = wshed.runoff_coeff;
    }

    const sbMeta = document.getElementById("sbResultMeta");
    const sbEng = document.getElementById("sbEngineState");
    if (sbMeta) {
      sbMeta.innerHTML = `Centroide: <strong>${p.avg_lat.toFixed(4)}°, ${p.avg_lon.toFixed(4)}° (${p.avg_alt.toFixed(0)} m)</strong> | TMAP: <strong>${pav.tmap_c ?? "-"} °C</strong> | PMA: <strong>${Number(pmaVal).toLocaleString()} mm</strong>`;
    }
    if (sbEng) {
      sbEng.textContent = `Calculado (${p.actual_year_min}–${p.actual_year_max})`;
    }
    updateStatusBar();

    window.ClimaTables.renderClassificationsTable(res);
    window.ClimaTables.renderMonthlyTable(res);
    window.ClimaTables.renderAnnualTable(res);
    window.ClimaTables.renderDailyClimatologyTable(res);
    window.ClimaTables.renderQualityTable(res);
    window.ClimaTables.renderIdfTable(res);
    window.ClimaTables.renderEngineeringTables(res);
    window.ClimaTables.renderWatershedTable(wshed);
    window.ClimaTables.renderGeohazardsAndRusleTables(res);
    window.ClimaCharts.renderAllResults(res);
  }

  async function refreshHealthAndCatalog() {
    const [h, f] = await Promise.all([api("/api/health"), api("/api/catalog/filters")]);
    document.getElementById("appVersion").textContent = `v${h.version}`;
    const st = h.stats;
    const yrTxt = st.year_min ? `${st.year_min}–${st.year_max}` : "Sin series";
    document.getElementById("dbStatsPill").textContent = `${st.total_stations.toLocaleString()} est. (${st.stations_with_data} con datos · ${yrTxt})`;
    window.ClimaTables.renderSyncHistory(st.recent_syncs || []);

    if (h.detected_legacy_sources && h.detected_legacy_sources.length && !document.getElementById("legacySourcePath").value) {
      document.getElementById("legacySourcePath").value = h.detected_legacy_sources[0];
    }

    state.catalog = f;
    const fillSelect = (id, items, valKey, labelKey, firstLabel) => {
      const sel = document.getElementById(id);
      sel.innerHTML = `<option value="">${firstLabel}</option>` + items.map((x) => `<option value="${x[valKey]}">${x[labelKey]}</option>`).join("");
    };
    fillSelect("filterDepto", f.departamentos, "codigo", "nombre", "Todos");
    fillSelect("filterMun", f.municipios, "codigo", "nombre", "Todos");
    fillSelect("filterCat", f.categorias, "codigo", "descripcion", "Todas");
    fillSelect("dhimeDefaultVar", f.variables, "id", "nombre_corto", "Detectar automáticamente");
    const editVar = document.getElementById("editVarId");
    editVar.innerHTML = f.variables.map((v) => `<option value="${v.id}">${v.id} - ${v.nombre_corto} (${v.unidad})</option>`).join("");
  }

  async function loadSampleProject(projectObj) {
    const cfg = projectObj.config || projectObj;
    document.getElementById("projName").value = cfg.name || "Ejemplo Bogotá D.C.";
    document.getElementById("projDesc").value = cfg.description || "";
    document.getElementById("projLocation").value = cfg.location || "";
    document.getElementById("projSoilReserve").value = cfg.soil_max_reserve_mm ?? 100;
    document.getElementById("projWaterTable").value = cfg.water_table_m ?? 10;
    document.getElementById("projEndYear").value = cfg.end_year ?? 2025;
    document.getElementById("projLastNYears").value = cfg.last_n_years ?? 10;
    document.getElementById("projEtpMethod").value = cfg.etp_method || "penman_monteith";
    if (cfg.study_profile) document.getElementById("projStudyProfile").value = cfg.study_profile;
    if (cfg.watershed_area_km2 !== undefined) document.getElementById("projWatershedArea").value = cfg.watershed_area_km2;
    if (cfg.watershed_length_m !== undefined) document.getElementById("projWatershedLength").value = cfg.watershed_length_m;
    if (cfg.watershed_slope_pct !== undefined) document.getElementById("projWatershedSlope").value = cfg.watershed_slope_pct;
    if (cfg.curve_number !== undefined) document.getElementById("projCurveNumber").value = cfg.curve_number;
    if (cfg.runoff_coeff !== undefined) document.getElementById("projRunoffCoeff").value = cfg.runoff_coeff;
    if (cfg.sgc_r3_intercept !== undefined) document.getElementById("projSgcIntercept").value = cfg.sgc_r3_intercept;
    if (cfg.sgc_r15_slope !== undefined) document.getElementById("projSgcSlope").value = cfg.sgc_r15_slope;
    if (cfg.route_coords && cfg.route_coords.length) {
      window.ClimaMap.setRoute(cfg.route_coords);
    }

    const loaded = [];
    for (const st of cfg.stations || []) {
      try {
        const d = await api(`/api/stations/${st.codigo}`);
        const years = (d.series_summary || []).map((x) => [x.min_year, x.max_year]);
        loaded.push({
          codigo: d.codigo,
          nombre: d.nombre,
          categoria_codigo: d.categoria_codigo,
          has_data: years.length > 0,
          min_year: years.length ? Math.min(...years.map((y) => y[0])) : null,
          max_year: years.length ? Math.max(...years.map((y) => y[1])) : null,
          weight: st.weight ?? 1,
        });
      } catch {}
    }
    state.selectedStations = loaded;
    renderSelectedTable();
    refreshMapMarkers();
    updateStatusBar();
  }

  function initStandaloneThornthwaite() {
    const months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
    const presets = {
      popayan: { lat: 2.45, p: [190.6, 193.8, 189.2, 245.9, 144.6, 51.9, 39.8, 27.7, 43.3, 302.4, 374.1, 314.7], t: [13.86, 13.76, 13.95, 14.12, 14.34, 14.39, 14.30, 14.27, 14.51, 13.79, 13.35, 13.39] },
      bogota: { lat: 4.71, p: [34, 48, 72, 110, 108, 62, 48, 46, 70, 122, 102, 54], t: [13.2, 13.5, 13.8, 13.9, 13.9, 13.7, 13.3, 13.5, 13.5, 13.5, 13.5, 13.2] },
      barranquilla: { lat: 10.92, p: [2, 1, 3, 25, 92, 95, 65, 105, 145, 175, 85, 18], t: [26.8, 27.0, 27.4, 28.0, 28.3, 28.5, 28.4, 28.5, 28.2, 27.7, 27.6, 27.1] },
    };

    const tbody = document.querySelector("#twInputTable tbody");
    function setPreset(key) {
      const pr = presets[key];
      document.getElementById("twLat").value = pr.lat;
      tbody.innerHTML = months
        .map(
          (m, idx) => `
        <tr>
          <td>${m}</td>
          <td><input type="number" step="0.1" class="tw-p" value="${pr.p[idx]}" /></td>
          <td><input type="number" step="0.01" class="tw-t" value="${pr.t[idx]}" /></td>
        </tr>`
        )
        .join("");
    }
    setPreset("bogota");

    async function calc() {
      const monthly_precip = Array.from(document.querySelectorAll(".tw-p")).map((el) => Number(el.value || 0));
      const monthly_temp = Array.from(document.querySelectorAll(".tw-t")).map((el) => Number(el.value || 0));
      const res = await api("/api/analysis/thornthwaite-monthly", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat_deg: Number(document.getElementById("twLat").value || 4.71),
          soil_max_reserve_mm: Number(document.getElementById("twReserve").value || 100),
          monthly_precip,
          monthly_temp,
        }),
      });
      document.getElementById("twKpiStrip").innerHTML = `
        <div class="kpi-card"><div class="kpi-label">Índice Thornthwaite</div><div class="kpi-val">${res.thornthwaite_index_pct}%</div><div class="kpi-sub">${res.humidity_class}</div></div>
        <div class="kpi-card"><div class="kpi-label">Temp. Media Mensual</div><div class="kpi-val">${res.mean_temp_c} °C</div><div class="kpi-sub">${res.thermal_class}</div></div>
        <div class="kpi-card"><div class="kpi-label">PMA / ETP Anual</div><div class="kpi-val">${res.total_precip_mm} / ${res.total_etp_mm}</div><div class="kpi-sub">mm/año (I=${res.annual_heat_index})</div></div>
        <div class="kpi-card"><div class="kpi-label">Exceso / Déficit</div><div class="kpi-val">${res.total_excess_mm} / ${res.total_deficit_mm}</div><div class="kpi-sub">mm/año</div></div>
      `;
      window.ClimaCharts.renderTwStandalone(res);
      window.ClimaTables.renderTwTable(res);
    }

    document.getElementById("btnTwPresetPopayan").onclick = () => { setPreset("popayan"); calc(); };
    document.getElementById("btnTwPresetBogota").onclick = () => { setPreset("bogota"); calc(); };
    document.getElementById("btnTwPresetBarranquilla").onclick = () => { setPreset("barranquilla"); calc(); };
    document.getElementById("btnCalcMonthlyTw").onclick = () => calc().catch((e) => toast(e.message, "error"));
    calc().catch(() => {});
  }

  async function loadMatrixEditor() {
    const code = document.getElementById("editStationCode").value.trim();
    const vid = Number(document.getElementById("editVarId").value || 1);
    const yr = Number(document.getElementById("editYear").value || 2024);
    try {
      const data = await api(`/api/stations/${code}/matrix?var_id=${vid}&year=${yr}`);
      window.ClimaTables.renderMatrixEditor(data);
      document.getElementById("matrixMetaInfo").textContent = data.active_source
        ? `Fuente activa: ${data.active_source} (${(data.available_sources || []).join(", ")})`
        : "Año vacío (puedes digitar y guardar como Manual)";
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function saveMatrixEditor() {
    const code = document.getElementById("editStationCode").value.trim();
    const vid = Number(document.getElementById("editVarId").value || 1);
    const yr = Number(document.getElementById("editYear").value || 2024);
    const matrix = Array.from({ length: 12 }, () => Array(31).fill(null));
    document.querySelectorAll("#matrixEditorTable input").forEach((inp) => {
      const m = Number(inp.dataset.m);
      const d = Number(inp.dataset.d);
      const raw = inp.value.trim();
      matrix[m][d] = raw === "" ? null : Number(raw);
    });
    try {
      await api(`/api/stations/${code}/matrix?var_id=${vid}&year=${yr}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ matrix, source: "Manual" }),
      });
      toast("Matriz diaria guardada con origen 'Manual'.", "success");
      refreshHealthAndCatalog();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function runExport(fmt) {
    if (!state.selectedStations.length) {
      toast("Selecciona estaciones y ejecuta el análisis primero.", "error");
      return;
    }
    try {
      toast(`Generando exportación ${fmt.toUpperCase()}...`);
      const res = await fetch(`/api/exports/${fmt}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildProjectConfig()),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error exportando ${fmt}`);
      }
      const disp = res.headers.get("Content-Disposition") || "";
      const match = disp.match(/filename="([^"]+)"/);
      const fname = match ? match[1] : `HidroClimaStudio_${fmt}`;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast(`Descargado ${fname}`, "success");
    } catch (err) {
      toast(err.message, "error");
    }
  }

  function wireEvents() {
    document.querySelectorAll(".nav-tab").forEach((btn) => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));
    document.querySelectorAll(".subtab").forEach((btn) =>
      btn.addEventListener("click", () => {
        const panel = btn.closest(".tab-panel") || document;
        panel.querySelectorAll(".subtab").forEach((b) => b.classList.toggle("active", b === btn));
        panel.querySelectorAll(".subtab-panel").forEach((p) => p.classList.toggle("active", p.id === btn.dataset.subtab));
        setTimeout(() => window.ClimaCharts.resizeAll(), 60);
      })
    );

    const wsPreset = document.getElementById("wsCnPreset");
    if (wsPreset) {
      wsPreset.addEventListener("change", () => {
        if (!wsPreset.value) return;
        const [cnVal, cVal] = wsPreset.value.split(",").map(Number);
        document.getElementById("wsCn").value = cnVal;
        document.getElementById("wsCoeffC").value = cVal;
        document.getElementById("projCurveNumber").value = cnVal;
        document.getElementById("projRunoffCoeff").value = cVal;
      });
    }

    const btnRecalcWs = document.getElementById("btnRecalcWatershed");
    if (btnRecalcWs) {
      btnRecalcWs.addEventListener("click", async () => {
        if (!state.lastAnalysis || !state.lastAnalysis.hydrology_idf?.available) {
          toast("Ejecuta primero el análisis principal para disponer de las curvas IDF.", "error");
          return;
        }
        const area_km2 = Number(document.getElementById("wsAreaKm2").value || 1.0);
        const length_m = Number(document.getElementById("wsLengthM").value || 800);
        const slope_pct = Number(document.getElementById("wsSlopePct").value || 5.0);
        const curve_number = Number(document.getElementById("wsCn").value || 75);
        const runoff_coeff = Number(document.getElementById("wsCoeffC").value || 0.50);
        document.getElementById("projWatershedArea").value = area_km2;
        document.getElementById("projWatershedLength").value = length_m;
        document.getElementById("projWatershedSlope").value = slope_pct;
        document.getElementById("projCurveNumber").value = curve_number;
        document.getElementById("projRunoffCoeff").value = runoff_coeff;
        try {
          const wshed = await api("/api/analysis/watershed", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              idf_result: state.lastAnalysis.hydrology_idf,
              area_km2,
              length_m,
              slope_pct,
              curve_number,
              runoff_coeff,
            }),
          });
          state.lastAnalysis.watershed = wshed;
          window.ClimaTables.renderWatershedTable(wshed);
          toast(`Caudales de cuenca recalculados (tc = ${wshed.tc_kirpich_min} min).`, "success");
        } catch (err) {
          toast(err.message, "error");
        }
      });
    }

    ["projStudyProfile", "projEtpMethod", "projIdfMethod"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", updateStatusBar);
    });
    const bufEl = document.getElementById("filterBufferKm");
    if (bufEl) bufEl.addEventListener("change", () => updateRouteBadge(window.ClimaMap.getRoute()));

    document.getElementById("btnThemeToggle").onclick = () => {
      const cur = document.documentElement.getAttribute("data-theme") || "light";
      document.documentElement.setAttribute("data-theme", cur === "light" ? "dark" : "light");
      if (state.lastAnalysis) window.ClimaCharts.renderAllResults(state.lastAnalysis);
    };

    const btnIdfScale = document.getElementById("btnToggleIdfScale");
    if (btnIdfScale) {
      btnIdfScale.onclick = () => {
        state.idfLogMode = !state.idfLogMode;
        btnIdfScale.textContent = state.idfLogMode ? "Escala Lineal" : "Escala Log-Log";
        if (state.lastAnalysis) window.ClimaCharts.setIdfLogMode(state.idfLogMode, state.lastAnalysis);
      };
    }

    document.getElementById("filterDepto").onchange = (e) => {
      const dep = e.target.value;
      const muns = dep ? state.catalog.municipios.filter((m) => m.departamento_codigo === dep) : state.catalog.municipios;
      const sel = document.getElementById("filterMun");
      sel.innerHTML = `<option value="">Todos</option>` + muns.map((m) => `<option value="${m.codigo}">${m.nombre}</option>`).join("");
    };

    document.getElementById("btnSearchStations").onclick = () => searchStations(true);
    document.getElementById("filterQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") searchStations(true); });
    document.getElementById("btnResetFilters").onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      ["filterQuery", "filterDepto", "filterMun", "filterCat", "filterEstado"].forEach((id) => (document.getElementById(id).value = ""));
      document.getElementById("filterOnlyWithData").checked = false;
      window.ClimaMap.clearRoute();
      searchStations(false);
    };

    document.getElementById("btnFitColombia").onclick = () => window.ClimaMap.fitColombia();
    document.getElementById("btnAddVisibleToProject").onclick = () => {
      state.foundStations.slice(0, 10).forEach((s) => {
        if (!state.selectedStations.some((x) => x.codigo === s.codigo)) {
          state.selectedStations.push({ ...s, weight: 1 });
        }
      });
      renderSelectedTable();
      renderFoundTable();
      refreshMapMarkers();
    };

    document.getElementById("btnWeightEqual").onclick = () => computeWeights("equal");
    document.getElementById("btnWeightIDW").onclick = () => computeWeights("idw");
    document.getElementById("btnWeightThiessen").onclick = () => computeWeights("thiessen");
    document.getElementById("btnClearStations").onclick = () => {
      state.selectedStations = [];
      renderSelectedTable();
      renderFoundTable();
      refreshMapMarkers();
    };

    document.getElementById("btnDrawRoute").onclick = () => {
      window.ClimaMap.startDraw();
      document.getElementById("btnDrawRoute").style.display = "none";
      document.getElementById("btnFinishDraw").style.display = "inline-flex";
      toast("Haz clic sobre el mapa para trazar los vértices del corredor o área.");
    };
    document.getElementById("btnFinishDraw").onclick = () => {
      window.ClimaMap.stopDraw();
      document.getElementById("btnDrawRoute").style.display = "inline-flex";
      document.getElementById("btnFinishDraw").style.display = "none";
      searchStations(true);
    };
    document.getElementById("btnClearRoute").onclick = () => {
      window.ClimaMap.clearRoute();
      document.getElementById("btnDrawRoute").style.display = "inline-flex";
      document.getElementById("btnFinishDraw").style.display = "none";
      searchStations(false);
    };

    document.getElementById("btnTogglePasteCoords").onclick = () => {
      document.getElementById("corridorPasteBox").classList.toggle("open");
    };

    document.getElementById("inputRouteFile").onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);
      try {
        const res = await api("/api/spatial/parse-route", { method: "POST", body: fd });
        window.ClimaMap.setRoute(res.route_coords);
        toast(`Corredor cargado (${res.count} vértices). Buscando estaciones en el buffer...`, "success");
        searchStations(true);
      } catch (err) {
        toast(err.message, "error");
      }
    };

    document.getElementById("btnParsePastedRoute").onclick = async () => {
      const raw = document.getElementById("pasteKmlCoords").value.trim();
      if (!raw) return;
      const fd = new FormData();
      fd.append("raw_text", raw);
      try {
        const res = await api("/api/spatial/parse-route", { method: "POST", body: fd });
        window.ClimaMap.setRoute(res.route_coords);
        document.getElementById("corridorPasteBox").classList.remove("open");
        searchStations(true);
      } catch (err) {
        toast(err.message, "error");
      }
    };

    document.getElementById("btnLoadSampleRoute").onclick = () => {
      const demo = [[4.7056, -74.1507], [4.6693, -74.1027], [4.6381, -74.0891], [4.5984, -74.0616]];
      window.ClimaMap.setRoute(demo);
      searchStations(true);
      toast("Ruta demo Bogotá – Cerros Orientales cargada.");
    };

    document.getElementById("btnCalculateMain").onclick = runAnalysis;
    document.getElementById("btnRunAnalysisTop").onclick = runAnalysis;
    document.getElementById("btnQuickSync").onclick = () => {
      if (state.selectedStations.length) {
        document.getElementById("syncStationCodes").value = state.selectedStations.map((s) => s.codigo).join(",");
      }
      switchTab("tab-bridge");
    };

    document.getElementById("btnLoadSampleCauca").onclick = async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const data = await api("/api/projects");
      if (data.samples && data.samples.length) {
        await loadSampleProject(data.samples[0]);
        toast("Ejemplo Bogotá D.C. cargado.", "success");
      }
    };

    document.getElementById("btnSaveProject").onclick = async () => {
      const cfg = buildProjectConfig();
      try {
        const res = await api("/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: state.activeProjectId,
            name: cfg.name,
            description: cfg.description,
            location: cfg.location,
            config: cfg,
          }),
        });
        state.activeProjectId = res.id;
        toast(`Proyecto '${cfg.name}' guardado.`, "success");
      } catch (err) {
        toast(err.message, "error");
      }
    };

    document.getElementById("btnOpenProjects").onclick = async () => {
      const data = await api("/api/projects");
      const all = [...(data.projects || []), ...(data.samples || [])];
      const box = document.getElementById("projectsListContainer");
      box.innerHTML = all.length
        ? all
            .map(
              (p, i) => `
          <div class="trend-item" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div>
              <strong>${p.name}</strong> ${p.is_sample ? '<span class="badge-info">Ejemplo</span>' : ""}<br/>
              <span class="hint">${p.location || ""} · ${(p.config?.stations || []).length} estaciones</span>
            </div>
            <div class="btn-row">
              <button class="btn btn-xs btn-primary" data-load-p="${i}">Abrir</button>
              ${!p.is_sample ? `<button class="btn btn-xs btn-danger-ghost" data-del-p="${p.id}">Eliminar</button>` : ""}
            </div>
          </div>`
            )
            .join("")
        : "<p class='hint'>No hay proyectos guardados.</p>";
      box.querySelectorAll("[data-load-p]").forEach((b) => {
        b.onclick = async () => {
          const p = all[Number(b.dataset.loadP)];
          state.activeProjectId = p.is_sample ? null : p.id;
          await loadSampleProject(p);
          document.getElementById("projectsModal").style.display = "none";
        };
      });
      box.querySelectorAll("[data-del-p]").forEach((b) => {
        b.onclick = async () => {
          await api(`/api/projects/${b.dataset.delP}`, { method: "DELETE" });
          document.getElementById("btnOpenProjects").click();
        };
      });
      document.getElementById("projectsModal").style.display = "flex";
    };

    document.getElementById("inputImportCli").onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);
      try {
        const res = await api("/api/projects/import", { method: "POST", body: fd });
        await loadSampleProject(res.project);
        document.getElementById("projectsModal").style.display = "none";
        toast(`Proyecto '${res.project.name}' importado.`, "success");
      } catch (err) {
        toast(err.message, "error");
      }
    };

    document.getElementById("btnCloseProjects").onclick = () => (document.getElementById("projectsModal").style.display = "none");
    document.getElementById("btnCloseStationModal").onclick = () => (document.getElementById("stationModal").style.display = "none");

    // Bridges
    document.getElementById("btnUseProjectStationsSync").onclick = () => {
      if (state.selectedStations.length) {
        document.getElementById("syncStationCodes").value = state.selectedStations.map((s) => s.codigo).join(",");
      }
    };

    document.getElementById("btnRunLiveSync").onclick = async () => {
      const codes = document.getElementById("syncStationCodes").value.split(",").map((s) => s.trim()).filter(Boolean);
      const providers = [];
      if (document.getElementById("syncProvIdeam").checked) providers.push("IDEAM-API");
      if (document.getElementById("syncProvOpenMeteo").checked) providers.push("Open-Meteo");
      if (document.getElementById("syncProvNasa").checked) providers.push("NASA-POWER");

      const logBox = document.getElementById("syncLogBox");
      logBox.textContent = "Conectando con APIs en vivo (datos.gov.co / Open-Meteo / NASA POWER)...\n";
      try {
        const res = await api("/api/bridges/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            station_codes: codes,
            providers,
            start_year: Number(document.getElementById("syncStartYear").value || 2024),
            end_year: Number(document.getElementById("syncEndYear").value || 2026),
            update_catalog: document.getElementById("syncUpdateCatalog").checked,
          }),
        });
        logBox.textContent = JSON.stringify(res, null, 2);
        toast(`Sincronización finalizada: ${res.total_records_saved} registros guardados.`, "success");
        await refreshHealthAndCatalog();
        await searchStations(false);
      } catch (err) {
        logBox.textContent = `ERROR: ${err.message}`;
        toast(err.message, "error");
      }
    };

    document.getElementById("btnRunLegacyImport").onclick = async () => {
      const source_path = document.getElementById("legacySourcePath").value.trim();
      if (!source_path) {
        toast("Indica la ruta al archivo .zip, .rar o carpeta SHC.", "error");
        return;
      }
      const stnStr = document.getElementById("legacyStationFilter").value.trim();
      const yMin = document.getElementById("legacyYearMin").value;
      const yMax = document.getElementById("legacyYearMax").value;
      try {
        const job = await api("/api/bridges/import-legacy", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_path,
            station_codes: stnStr ? stnStr.split(",").map((s) => s.trim()).filter(Boolean) : null,
            year_min: yMin ? Number(yMin) : null,
            year_max: yMax ? Number(yMax) : null,
          }),
        });
        document.getElementById("legacyProgressWrap").style.display = "block";
        const timer = setInterval(async () => {
          try {
            const st = await api(`/api/jobs/${job.job_id}`);
            document.getElementById("legacyProgressFill").style.width = `${st.progress}%`;
            document.getElementById("legacyProgressMsg").textContent = st.message;
            if (st.status === "completed") {
              clearInterval(timer);
              toast(st.message, "success");
              refreshHealthAndCatalog();
              searchStations(false);
            } else if (st.status === "failed") {
              clearInterval(timer);
              toast(st.error || "Error en importación", "error");
            }
          } catch {
            clearInterval(timer);
          }
        }, 900);
      } catch (err) {
        toast(err.message, "error");
      }
    };

    document.getElementById("btnImportDhime").onclick = async () => {
      const f = document.getElementById("dhimeFileInput").files[0];
      if (!f) { toast("Selecciona un archivo CSV o XLSX de DHIME.", "error"); return; }
      const fd = new FormData();
      fd.append("file", f);
      const stn = document.getElementById("dhimeDefaultStn").value.trim();
      const vid = document.getElementById("dhimeDefaultVar").value;
      if (stn) fd.append("default_station_code", stn);
      if (vid) fd.append("default_var_id", vid);
      try {
        const res = await api("/api/bridges/import-dhime", { method: "POST", body: fd });
        document.getElementById("dhimeStatusMsg").textContent = `Importados ${res.records_saved} registros (${(res.stations || []).join(", ")}).`;
        toast("Archivo DHIME importado.", "success");
        refreshHealthAndCatalog();
      } catch (err) {
        toast(err.message, "error");
      }
    };

    document.getElementById("btnLoadMatrix").onclick = loadMatrixEditor;
    document.getElementById("btnSaveMatrix").onclick = saveMatrixEditor;

    document.querySelectorAll(".export-btn").forEach((btn) => {
      btn.addEventListener("click", () => runExport(btn.dataset.fmt));
    });

    if (window.ClimaHelp) {
      window.ClimaHelp.init({
        switchTab,
        openResultsSubtab: (subId) => {
          switchTab("tab-results");
          const btn = document.querySelector(`#tab-results .subtab[data-subtab="${subId}"]`);
          if (btn) btn.click();
        },
        openEngSubtab: (subId) => {
          switchTab("tab-eng");
          const btn = document.querySelector(`#tab-eng .subtab[data-subtab="${subId}"]`);
          if (btn) btn.click();
        },
        runAnalysis,
        loadAndRunCauca: async () => {
          const data = await api("/api/projects");
          if (data.samples && data.samples.length) {
            await loadSampleProject(data.samples[0]);
            await runAnalysis();
          }
        },
        resetProject: () => {
          state.activeProjectId = null;
          state.selectedStations = [];
          document.getElementById("projName").value = "Nuevo Proyecto";
          document.getElementById("projDesc").value = "";
          renderSelectedTable();
          refreshMapMarkers();
          updateStatusBar();
          switchTab("tab-gis");
        },
        openProjects: () => document.getElementById("btnOpenProjects")?.click(),
        saveProject: () => document.getElementById("btnSaveProject")?.click(),
        computeWeights,
        runExport,
        toggleTheme: () => document.getElementById("btnThemeToggle")?.click(),
        fitColombia: () => document.getElementById("btnFitColombia")?.click(),
        toggleIdfScale: () => document.getElementById("btnToggleIdfScale")?.click(),
      });
    }
  }

  async function boot() {
    window.ClimaMap.init({
      onRouteChanged: updateRouteBadge,
      onAddStation: addStationByCode,
      onInspectStation: inspectStation,
      onCursorMove: (lat, lon) => {
        const el = document.getElementById("mapCoordReadout");
        if (el) el.textContent = `Cursor: ${lat.toFixed(4)}°, ${lon.toFixed(4)}°`;
      },
    });
    wireEvents();
    initStandaloneThornthwaite();
    await refreshHealthAndCatalog();
    await searchStations(false);

    try {
      const pData = await api("/api/projects");
      if (pData.samples && pData.samples.length) {
        await loadSampleProject(pData.samples[0]);
      }
    } catch {}
    loadMatrixEditor();
    updateStatusBar();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
