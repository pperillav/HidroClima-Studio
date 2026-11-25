window.ClimaTables = (() => {
  function fmt(val, dec = 2) {
    if (val === null || val === undefined || Number.isNaN(val)) return "-";
    return Number(val).toFixed(dec);
  }

  function renderMonthlyTable(analysis) {
    const tbl = document.getElementById("tableMonthlySummary");
    const rows = analysis.monthly_summary || [];
    const s = analysis.summary || {};
    tbl.innerHTML = `
      <thead>
        <tr>
          <th>Mes</th><th>Precip (mm)</th><th>T.Med (°C)</th><th>T.Máx (°C)</th><th>T.Mín (°C)</th>
          <th>HR (%)</th><th>Brillo (h/d)</th><th>Viento (m/s)</th><th>Rad.Sol (MJ/m²)</th>
          <th>ETP (mm)</th><th>ETR (mm)</th><th>Almac (mm)</th><th>Exceso (mm)</th><th>Déficit (mm)</th><th>TMI (%)</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((r) => `
          <tr>
            <td><strong>${r.month}</strong></td>
            <td>${fmt(r.precip_mm, 1)}</td>
            <td>${fmt(r.temp_mean_c, 2)}</td>
            <td>${fmt(r.temp_max_c, 1)}</td>
            <td>${fmt(r.temp_min_c, 1)}</td>
            <td>${fmt(r.rh_pct, 1)}</td>
            <td>${fmt(r.sunshine_h, 2)}</td>
            <td>${fmt(r.wind_ms, 2)}</td>
            <td>${fmt(r.solar_rad_mj, 2)}</td>
            <td>${fmt(r.etp_active_mm, 1)}</td>
            <td>${fmt(r.etr_mm, 1)}</td>
            <td>${fmt(r.storage_mm, 1)}</td>
            <td>${fmt(r.excess_mm, 1)}</td>
            <td>${fmt(r.deficit_mm, 1)}</td>
            <td>${fmt(r.tmi_step_pct, 1)}</td>
          </tr>
        `).join("")}
        <tr style="font-weight:700;background:var(--surface-tint)">
          <td>ANUAL / PROM</td>
          <td>${fmt(s.annual_precip_mm, 1)}</td>
          <td>${fmt(s.mean_annual_temp_c, 2)}</td>
          <td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td>
          <td>${fmt(s.annual_etp_mm, 1)}</td>
          <td>${fmt(s.annual_etr_mm, 1)}</td>
          <td>-</td>
          <td>${fmt(s.annual_excess_mm, 1)}</td>
          <td>${fmt(s.annual_deficit_mm, 1)}</td>
          <td>${fmt(s.thornthwaite_index_pct, 2)}%</td>
        </tr>
      </tbody>
    `;
  }

  function renderAnnualTable(analysis) {
    const tbl = document.getElementById("tableAnnualSummary");
    const rows = analysis.annual_summary || [];
    tbl.innerHTML = `
      <thead>
        <tr>
          <th>Año</th><th>Precip Total (mm)</th><th>P. Máx 24h (mm)</th><th>T. Media (°C)</th>
          <th>T. Máx (°C)</th><th>T. Mín (°C)</th><th>HR (%)</th><th>ET0 PM (mm)</th>
          <th>Comp. Lluvia (%)</th><th>Comp. Temp (%)</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((r) => `
          <tr>
            <td><strong>${r.year}</strong></td>
            <td>${fmt(r.precip_mm, 1)}</td>
            <td>${fmt(r.pmax_24h_mm, 1)}</td>
            <td>${fmt(r.temp_mean_c, 2)}</td>
            <td>${fmt(r.temp_max_c, 1)}</td>
            <td>${fmt(r.temp_min_c, 1)}</td>
            <td>${fmt(r.rh_pct, 1)}</td>
            <td>${fmt(r.et0_pm_mm, 1)}</td>
            <td>${fmt(r.completeness_precip_pct, 1)}%</td>
            <td>${fmt(r.completeness_temp_pct, 1)}%</td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderDailyClimatologyTable(analysis) {
    const tbl = document.getElementById("tableDailyClimatology");
    const rows = analysis.daily_climatology || [];
    tbl.innerHTML = `
      <thead>
        <tr>
          <th>Mes</th><th>Día</th><th>Precip (mm)</th><th>T.Med (°C)</th><th>T.Máx (°C)</th>
          <th>T.Mín (°C)</th><th>HR (%)</th><th>Rad.Sol</th><th>ETP (mm)</th>
          <th>Almac (mm)</th><th>Exceso</th><th>Déficit</th><th>TMI (%)</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map((r) => `
          <tr>
            <td>${r.month_abbr}</td><td>${r.day}</td>
            <td>${fmt(r.precip_mm, 2)}</td><td>${fmt(r.temp_mean_c, 2)}</td>
            <td>${fmt(r.temp_max_c, 1)}</td><td>${fmt(r.temp_min_c, 1)}</td>
            <td>${fmt(r.rh_pct, 1)}</td><td>${fmt(r.solar_rad_mj, 2)}</td>
            <td>${fmt(r.etp_used_mm, 2)}</td><td>${fmt(r.storage_mm, 2)}</td>
            <td>${fmt(r.excess_mm, 2)}</td><td>${fmt(r.deficit_mm, 2)}</td>
            <td>${fmt(r.tmi_pct, 1)}</td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderQualityTable(analysis) {
    const q = analysis.quality || {};
    const tbl = document.getElementById("tableQualitySummary");
    tbl.innerHTML = `
      <thead>
        <tr><th>Variable</th><th>Unidad</th><th>Días Válidos</th><th>Días Totales</th><th>Completitud (%)</th><th>Alertas Rango</th></tr>
      </thead>
      <tbody>
        ${(q.variable_summary || []).map((v) => `
          <tr>
            <td class="col-wrap"><strong>${v.name}</strong></td><td>${v.unit}</td>
            <td>${v.valid_days.toLocaleString()}</td><td>${v.total_days.toLocaleString()}</td>
            <td>${fmt(v.completeness_pct, 2)}%</td><td>${v.out_of_range_count}</td>
          </tr>
        `).join("")}
      </tbody>
    `;

    const box = document.getElementById("qualityTrendsBox");
    const tp = (q.trends || {}).precip_annual || {};
    const tt = (q.trends || {}).temp_mean_annual || {};
    const hp = (q.homogeneity || {}).precip_annual || {};
    const ht = (q.homogeneity || {}).temp_mean_annual || {};
    const et = q.etccdi || {};
    const srcEntries = Object.entries(analysis.source_day_counts || {});
    box.innerHTML = `
      <div class="trend-item">
        <strong>Tendencia (Mann-Kendall) &amp; Homogeneidad (Pettitt) — Precipitación Anual</strong><br/>
        ${tp.available ? `${tp.trend} · Pendiente Sen: <b>${tp.sen_slope_per_decade} mm/década</b> (p=${tp.p_value})` : (tp.message || "N/D")}<br/>
        Pettitt: ${hp.available ? `${hp.status} (K=${hp.k_stat}, p=${hp.p_value})` : (hp.message || "N/D")}
      </div>
      <div class="trend-item">
        <strong>Tendencia (Mann-Kendall) &amp; Homogeneidad (Pettitt) — Temperatura Media Anual</strong><br/>
        ${tt.available ? `${tt.trend} · Pendiente Sen: <b>${tt.sen_slope_per_decade} °C/década</b> (p=${tt.p_value})` : (tt.message || "N/D")}<br/>
        Pettitt: ${ht.available ? `${ht.status} (K=${ht.k_stat}, p=${ht.p_value})` : (ht.message || "N/D")}
      </div>
      <div class="trend-item">
        <strong>Índices Climáticos Extremos (OMM / ETCCDI)</strong><br/>
        Rx1day: <b>${et.rx1day_mm ?? "-"} mm</b> · Rx5day: <b>${et.rx5day_mm ?? "-"} mm</b> ·
        CDD (racha seca): <b>${et.cdd_max_dry_days ?? "-"} d</b> · CWD (racha húmeda): <b>${et.cwd_max_wet_days ?? "-"} d</b> ·
        R20mm: <b>${et.r20mm_days_yr ?? "-"} d/año</b> · TXx/TNn: <b>${et.txx_abs_max_c ?? "-"} / ${et.tnn_abs_min_c ?? "-"} °C</b>
      </div>
      <div class="trend-item">
        <strong>Trazabilidad de Fuentes Utilizadas (días-variable)</strong><br/>
        ${srcEntries.length ? srcEntries.map(([k, v]) => `<span class="badge-info" style="margin-right:5px;margin-top:4px">${k}: ${v.toLocaleString()}</span>`).join("") : "N/D"}
      </div>
    `;
  }

  function renderClassificationsTable(analysis) {
    const tbl = document.getElementById("tableClassifications");
    if (!tbl) return;
    const cls = analysis.classifications || {};
    const cl = cls.caldas_lang || {};
    const ho = cls.holdridge || {};
    const ko = cls.koppen_geiger || {};
    const ena = cls.ena_aridity || {};
    const tw = cls.thornthwaite || {};
    tbl.innerHTML = `
      <thead><tr><th>Metodología / Norma</th><th>Clasificación Obtenida</th><th>Parámetros de Cálculo e Interpretación</th></tr></thead>
      <tbody>
        <tr><td class="col-wrap"><strong>Caldas-Lang (IDEAM)</strong></td><td class="col-wrap">${cl.label || "N/D"}</td><td class="col-wrap">Piso térmico: ${cl.piso_termico || "-"} (${cl.altitud_ref || "-"}) · Factor de Lang P/T = ${cl.lang_factor ?? "-"}</td></tr>
        <tr><td class="col-wrap"><strong>Zonas de Vida Holdridge</strong></td><td class="col-wrap">${ho.life_zone || "N/D"}</td><td class="col-wrap">Biotemperatura = ${ho.biotemp_c ?? "-"} °C · ETP = ${ho.etp_holdridge_mm ?? "-"} mm · Relación EPT = ${ho.ept_ratio ?? "-"}</td></tr>
        <tr><td class="col-wrap"><strong>Köppen-Geiger</strong></td><td class="col-wrap">${ko.label || "N/D"}</td><td class="col-wrap">Código climático estándar ${ko.code || "-"}</td></tr>
        <tr><td class="col-wrap"><strong>Thornthwaite (1948)</strong></td><td class="col-wrap">${tw.humidity_class || "N/D"} (${tw.index_pct ?? "-"}%)</td><td class="col-wrap">${tw.humidity_description || ""} · Térmica: ${tw.thermal_class || "-"}</td></tr>
        <tr><td class="col-wrap"><strong>Índice de Aridez (ENA-IDEAM)</strong></td><td class="col-wrap">${ena.category || "N/D"} (IA = ${ena.ia ?? "-"})</td><td class="col-wrap">${ena.description || ""}</td></tr>
      </tbody>
    `;
  }

  function renderEngineeringTables(analysis) {
    const idf = analysis.hydrology_idf || {};
    const pav = analysis.pavement || {};
    const summ = analysis.summary || {};

    const tblDist = document.getElementById("tableDistributionsKS");
    if (tblDist && idf.available) {
      const trs = idf.idf_return_periods || [];
      tblDist.innerHTML = `
        <thead><tr><th>Distribución</th><th>K-S D</th><th>K-S p-val</th><th>R²</th>${trs.map((t) => `<th>Tr ${t}</th>`).join("")}</tr></thead>
        <tbody>
          ${Object.entries(idf.distributions || {}).map(([dn, d]) => {
            const qmap = new Map(d.quantiles.map((q) => [q.tr, q.p24h_mm]));
            const bestTag = dn === idf.best_distribution ? ' <span class="badge-info">Mejor Ajuste</span>' : "";
            return `<tr><td class="col-wrap"><strong>${dn}</strong>${bestTag}</td><td>${fmt(d.ks_d, 4)}</td><td>${fmt(d.ks_pvalue, 4)}</td><td>${fmt(d.r2, 4)}</td>${trs.map((t) => `<td>${fmt(qmap.get(t), 1)}</td>`).join("")}</tr>`;
          }).join("")}
        </tbody>
      `;
    }

    const tblNorm = document.getElementById("tableNormativeRasInvias");
    if (tblNorm && idf.available) {
      tblNorm.innerHTML = `
        <thead><tr><th>Norma</th><th>Tipo de Obra / Estructura</th><th>Tr Mín.</th><th>Tr Rec.</th><th>i (tc=15 min)</th><th>i (tc=30 min)</th></tr></thead>
        <tbody>
          ${(idf.normative_return_periods || []).map((n) => `
            <tr>
              <td class="col-nowrap"><strong>${n.norma}</strong></td>
              <td class="col-wrap">${n.obra}</td>
              <td>${n.tr_min} a</td><td>${n.tr_rec} a</td>
              <td>${n.i_tc15_mmh ?? "-"} mm/h</td><td>${n.i_tc30_mmh ?? "-"} mm/h</td>
            </tr>
          `).join("")}
        </tbody>
      `;
    }

    const tblTmap = document.getElementById("tableTmapMonthly");
    if (tblTmap) {
      const wfRows = pav.monthly_wf || [];
      const reg = pav.invias_pavement_region || {};
      const pmaVal = pav.pma_mm ?? summ.annual_precip_mm;
      tblTmap.innerHTML = `
        <thead><tr><th>Mes</th><th>T. Media (°C)</th><th>Factor Ponderación Shell (WF)</th></tr></thead>
        <tbody>
          ${wfRows.map((r) => `<tr><td>${r.month}</td><td>${fmt(r.temp_c, 2)}</td><td>${fmt(r.wf, 4)}</td></tr>`).join("")}
          <tr style="font-weight:700;background:var(--surface-tint)">
            <td class="col-wrap">1. TMAP Proyecto: ${pav.tmap_c ?? "-"} °C</td>
            <td class="col-wrap">2. PMA: ${fmt(pmaVal, 1)} mm</td>
            <td class="col-wrap">INVIAS: ${reg.code || "-"} (WF prom: ${pav.wf_clim_avg ?? "-"})</td>
          </tr>
        </tbody>
      `;
    }
  }

  function renderIdfTable(analysis) {
    const tbl = document.getElementById("tableIdfMatrix");
    const idf = analysis.hydrology_idf || {};
    if (!idf.available) {
      tbl.innerHTML = "<tbody><tr><td>Sin datos suficientes</td></tr></tbody>";
      return;
    }
    const trs = idf.idf_return_periods || [];
    tbl.innerHTML = `
      <thead>
        <tr><th>Duración (min)</th>${trs.map((t) => `<th>Tr ${t} años</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${(idf.idf_table || []).map((row) => `
          <tr>
            <td><strong>${row.duration_min}</strong></td>
            ${trs.map((t) => `<td>${fmt(row[`tr_${t}`], 2)}</td>`).join("")}
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderWatershedTable(wshed) {
    const kpiBox = document.getElementById("watershedKpiStrip");
    const tbl = document.getElementById("tableWatershedDesign");
    if (!tbl || !kpiBox) return;
    if (!wshed || !wshed.available) {
      kpiBox.innerHTML = "";
      tbl.innerHTML = `<tbody><tr><td>${wshed?.message || "Ejecuta el análisis para calcular caudales de cuenca."}</td></tr></tbody>`;
      return;
    }
    kpiBox.innerHTML = `
      <div class="kpi-card"><div class="kpi-label">tc Kirpich</div><div class="kpi-val">${wshed.tc_kirpich_min} min</div><div class="kpi-sub">Témez: ${wshed.tc_temez_min} min</div></div>
      <div class="kpi-card"><div class="kpi-label">Retención SCS (S / Ia)</div><div class="kpi-val">${wshed.s_max_mm} mm</div><div class="kpi-sub">Ia = ${wshed.ia_mm} mm (CN=${wshed.curve_number})</div></div>
      <div class="kpi-card"><div class="kpi-label">Área / Hidrograma SCS</div><div class="kpi-val">${wshed.area_ha} ha</div><div class="kpi-sub">tp = ${wshed.scs_tp_h} h · tb = ${wshed.scs_tb_h} h</div></div>
    `;
    tbl.innerHTML = `
      <thead>
        <tr><th>Tr (a)</th><th>I(tc) mm/h</th><th>Q Racional (m³/s)</th><th>P Torm. (mm)</th><th>Qe SCS (mm)</th><th>Infilt F (mm)</th><th>Q Pico SCS (m³/s)</th></tr>
      </thead>
      <tbody>
        ${(wshed.design_rows || []).map((r) => `
          <tr>
            <td><strong>${r.tr}</strong></td>
            <td>${fmt(r.i_tc_mmh, 1)}</td>
            <td><strong>${fmt(r.q_rational_m3s, 3)}</strong></td>
            <td>${fmt(r.p_storm_mm, 1)}</td>
            <td>${fmt(r.qe_runoff_mm, 1)}</td>
            <td>${fmt(r.infiltration_mm, 1)}</td>
            <td>${fmt(r.q_scs_m3s, 3)}</td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderGeohazardsAndRusleTables(analysis) {
    // 1. SGC Landslide Thresholds
    const sgc = analysis.geohazards_sgc || {};
    const badgeSgc = document.getElementById("badgeSgcThreshold");
    const kpiSgc = document.getElementById("sgcKpiStrip");
    const tblRoll = document.getElementById("tableSgcRolling");
    const tblEp = document.getElementById("tableSgcEpisodes");
    if (badgeSgc) badgeSgc.textContent = sgc.available ? sgc.threshold_eq : "Sin serie diaria";
    if (kpiSgc) {
      if (sgc.available) {
        const inf = sgc.infiltration_balance || {};
        kpiSgc.innerHTML = `
          <div class="kpi-card kpi-highlight"><div class="kpi-label">Excedencias SGC</div><div class="kpi-val">${sgc.exceedance_days} d (${sgc.exceedance_rate_pct}%)</div><div class="kpi-sub">${sgc.episodes_count} episodios en ${sgc.days_evaluated.toLocaleString()} días</div></div>
          <div class="kpi-card"><div class="kpi-label">CN I / II / III (SCS)</div><div class="kpi-val">${inf.cn_i} / ${inf.cn_ii} / ${inf.cn_iii}</div><div class="kpi-sub">S_max = ${inf.s_max_mm} mm | Ia = ${inf.ia_mm} mm</div></div>
          <div class="kpi-card"><div class="kpi-label">Infiltración / Escorrentía</div><div class="kpi-val">${inf.mean_annual_infiltration_mm} mm/a</div><div class="kpi-sub">Escorrentía directa: ${inf.mean_annual_runoff_mm} mm/a</div></div>
        `;
      } else {
        kpiSgc.innerHTML = "";
      }
    }
    if (tblRoll) {
      const rs = Object.entries(sgc.rolling_stats || {});
      tblRoll.innerHTML = rs.length
        ? `<thead><tr><th>Ventana SGC</th><th>Media (mm)</th><th>P90 (mm)</th><th>P95 (mm)</th><th>P99 (mm)</th><th>Máx (mm)</th><th>Fecha Máx</th></tr></thead>
           <tbody>${rs.map(([k, v]) => `<tr><td class="col-nowrap"><strong>${k}</strong></td><td>${fmt(v.mean, 1)}</td><td>${fmt(v.p90, 1)}</td><td>${fmt(v.p95, 1)}</td><td>${fmt(v.p99, 1)}</td><td><strong>${fmt(v.max, 1)}</strong></td><td class="col-nowrap">${v.date_max || "-"}</td></tr>`).join("")}</tbody>`
        : "<tbody><tr><td>Sin datos</td></tr></tbody>";
    }
    if (tblEp) {
      const eps = sgc.episodes || [];
      tblEp.innerHTML = eps.length
        ? `<thead><tr><th>Inicio</th><th>Fin</th><th>Dur (d)</th><th>Fecha Pico</th><th>R1 Pico</th><th>R3 Pico</th><th>R15 Ant.</th><th>Umbral R3</th><th>Severidad</th></tr></thead>
           <tbody>${eps.map((e) => `<tr><td class="col-nowrap">${e.start_date}</td><td class="col-nowrap">${e.end_date}</td><td>${e.duration_days}</td><td class="col-nowrap"><strong>${e.peak_date}</strong></td><td>${fmt(e.r1_peak_mm, 1)}</td><td><strong>${fmt(e.r3_peak_mm, 1)}</strong></td><td>${fmt(e.r15_ant_mm, 1)}</td><td>${fmt(e.threshold_r3_mm, 1)}</td><td><strong>${fmt(e.severity_ratio, 2)}x</strong></td></tr>`).join("")}</tbody>`
        : "<tbody><tr><td>Ningún evento histórico superó el umbral crítico R3.</td></tr></tbody>";
    }

    // 2. Erosividad RUSLE (ANLA)
    const ero = analysis.erosivity || {};
    const badgeRusle = document.getElementById("badgeRusleClass");
    const kpiRusle = document.getElementById("rusleKpiStrip");
    const tblRusle = document.getElementById("tableRusleMonthly");
    if (badgeRusle) badgeRusle.textContent = ero.available ? `Agresividad: ${ero.aggressiveness_class} · PCI: ${ero.pci_class}` : "N/D";
    if (kpiRusle) {
      kpiRusle.innerHTML = ero.available
        ? `
          <div class="kpi-card kpi-highlight"><div class="kpi-label">Factor R (RUSLE / MFI)</div><div class="kpi-val">${ero.r_factor_mfi}</div><div class="kpi-sub">${ero.unit} (Por PMA: ${ero.r_factor_precip})</div></div>
          <div class="kpi-card"><div class="kpi-label">Fournier Modificado (MFI)</div><div class="kpi-val">${ero.mfi_arnoldus_mm} mm</div><div class="kpi-sub">Fournier clásico FI: ${ero.fournier_fi_mm} mm (${ero.aggressiveness_class})</div></div>
          <div class="kpi-card"><div class="kpi-label">Concentración PCI (Oliver)</div><div class="kpi-val">${ero.pci_oliver_pct}%</div><div class="kpi-sub">${ero.pci_class}</div></div>
        `
        : "";
    }
    if (tblRusle) {
      const mr = ero.monthly_distribution || [];
      tblRusle.innerHTML = mr.length
        ? `<thead><tr><th>Mes</th><th>P Media (mm)</th><th>Aporte R (%)</th><th>R Mensual (SI)</th></tr></thead>
           <tbody>${mr.map((m) => `<tr><td><strong>${m.month}</strong></td><td>${fmt(m.precip_mm, 1)}</td><td>${fmt(m.r_share_pct, 1)}%</td><td>${fmt(m.r_mfi_month, 1)}</td></tr>`).join("")}</tbody>`
        : "<tbody><tr><td>Sin datos mensuales</td></tr></tbody>";
    }

    // 3. SPEI Summary Badge
    const drg = analysis.drought || {};
    const bSpei = document.getElementById("badgeSpeiSummary");
    if (bSpei && drg.summary) {
      bSpei.textContent = `Meses ≤ -1.0: ${drg.summary.drought_moderate_pct}% | Mín SPEI-3: ${drg.summary.min_spei3} (${drg.summary.min_spei3_date})`;
    }
  }

  function renderTwTable(res) {
    const tbl = document.getElementById("tableTwResults");
    tbl.innerHTML = `
      <thead>
        <tr><th>Mes</th><th>P (mm)</th><th>T (°C)</th><th>I_calor</th><th>H.Sol</th><th>ETP Sin Corr.</th><th>ETP Corr.</th><th>Almac.</th><th>Exceso</th><th>Déficit</th></tr>
      </thead>
      <tbody>
        ${(res.rows || []).map((r) => `
          <tr>
            <td><strong>${r.month}</strong></td>
            <td>${fmt(r.precip_mm, 1)}</td><td>${fmt(r.temp_c, 2)}</td>
            <td>${fmt(r.heat_index, 2)}</td><td>${fmt(r.daylight_h, 2)}</td>
            <td>${fmt(r.etp_uncorrected_mm, 1)}</td><td>${fmt(r.etp_corrected_mm, 1)}</td>
            <td>${fmt(r.storage_mm, 1)}</td><td>${fmt(r.excess_mm, 1)}</td><td>${fmt(r.deficit_mm, 1)}</td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  function renderMatrixEditor(data) {
    const tbl = document.getElementById("matrixEditorTable");
    const months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    const mat = data.matrix || [];
    let html = `<thead><tr><th>Mes</th>${Array.from({ length: 31 }, (_, i) => `<th>${i + 1}</th>`).join("")}</tr></thead><tbody>`;
    for (let m = 0; m < 12; m++) {
      html += `<tr><td><strong>${months[m]}</strong></td>`;
      for (let d = 0; d < 31; d++) {
        const val = mat[m] && mat[m][d] !== null && mat[m][d] !== undefined ? mat[m][d] : "";
        html += `<td><input type="number" step="any" data-m="${m}" data-d="${d}" value="${val}" /></td>`;
      }
      html += "</tr>";
    }
    html += "</tbody>";
    tbl.innerHTML = html;
  }

  function renderSyncHistory(rows) {
    const tbl = document.getElementById("tableSyncHistory");
    if (!rows || !rows.length) {
      tbl.innerHTML = "<tbody><tr><td>Sin sincronizaciones registradas</td></tr></tbody>";
      return;
    }
    tbl.innerHTML = `
      <thead><tr><th>Fecha (UTC)</th><th>Fuente</th><th>Acción</th><th>Estaciones</th><th>Registros</th><th>Rango</th><th>Detalle</th></tr></thead>
      <tbody>
        ${rows.map((r) => `
          <tr>
            <td class="col-nowrap">${r.timestamp}</td><td><strong>${r.source}</strong></td><td>${r.action}</td>
            <td>${r.stations_count}</td><td>${r.records_count}</td>
            <td class="col-nowrap">${r.year_min || "-"}–${r.year_max || "-"}</td><td class="col-wrap">${r.notes || ""}</td>
          </tr>
        `).join("")}
      </tbody>
    `;
  }

  return {
    renderMonthlyTable,
    renderAnnualTable,
    renderDailyClimatologyTable,
    renderQualityTable,
    renderClassificationsTable,
    renderEngineeringTables,
    renderIdfTable,
    renderWatershedTable,
    renderGeohazardsAndRusleTables,
    renderTwTable,
    renderMatrixEditor,
    renderSyncHistory,
  };
})();
