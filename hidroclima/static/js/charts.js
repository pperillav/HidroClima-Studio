window.ClimaCharts = (() => {
  const instances = {};
  let idfLogMode = false;

  function isDark() {
    return document.documentElement.getAttribute("data-theme") === "dark";
  }

  function colors() {
    return isDark()
      ? { text: "#f1f5f9", muted: "#cbd5e1", grid: "rgba(148,163,184,0.22)", axis: "#64748b", bg: "transparent", boxBg: "#1e293b" }
      : { text: "#0f172a", muted: "#334155", grid: "rgba(100,116,139,0.22)", axis: "#1e293b", bg: "transparent", boxBg: "#ffffff" };
  }

  function originToolbox(title) {
    return {
      right: 8,
      top: 0,
      itemSize: 13,
      iconStyle: { borderColor: colors().muted },
      feature: {
        saveAsImage: {
          pixelRatio: 2,
          name: title || "HidroClima_Figura",
          title: "Descargar PNG (2x)",
          backgroundColor: isDark() ? "#111827" : "#ffffff",
        },
        restore: { title: "Restaurar vista" },
      },
    };
  }

  function boxedCategoryX(cats, name = "", extra = {}) {
    const c = colors();
    return [
      {
        type: "category",
        data: cats,
        name,
        nameLocation: "middle",
        nameGap: 24,
        nameTextStyle: { color: c.text, fontWeight: 700, fontSize: 11.5 },
        axisLine: { show: true, onZero: false, lineStyle: { color: c.axis, width: 1.2 } },
        axisTick: { show: true, inside: true, length: 5, alignWithLabel: true, lineStyle: { color: c.axis } },
        axisLabel: { color: c.muted, fontSize: 11, ...(extra.axisLabel || {}) },
        splitLine: { show: false },
      },
      {
        type: "category",
        position: "top",
        data: cats,
        axisLine: { show: true, onZero: false, lineStyle: { color: c.axis, width: 1.2 } },
        axisTick: { show: true, inside: true, length: 4, alignWithLabel: true, lineStyle: { color: c.axis } },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
    ];
  }

  function boxedY(name, rightSide = false, extra = {}) {
    const c = colors();
    return {
      type: extra.type || "value",
      name,
      nameLocation: "middle",
      nameGap: extra.nameGap || (rightSide ? 42 : 46),
      nameTextStyle: { color: extra.color || c.text, fontWeight: 700, fontSize: 11.5 },
      axisLine: { show: true, onZero: false, lineStyle: { color: c.axis, width: 1.2 } },
      axisTick: { show: true, inside: true, length: 5, lineStyle: { color: c.axis } },
      minorTick: { show: (extra.type || "value") === "value", splitNumber: 2, length: 3, lineStyle: { color: c.axis } },
      axisLabel: { color: extra.color || c.muted, fontSize: 11 },
      splitLine: rightSide
        ? { show: false }
        : { show: true, lineStyle: { color: c.grid, type: "dashed", width: 0.8 } },
      ...(extra.scale !== undefined ? { scale: extra.scale } : {}),
      ...(extra.min !== undefined ? { min: extra.min } : {}),
      ...(extra.max !== undefined ? { max: extra.max } : {}),
    };
  }

  function getChart(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    if (instances[id]) instances[id].dispose();
    const chart = echarts.init(el);
    instances[id] = chart;
    return chart;
  }

  function resizeAll() {
    Object.values(instances).forEach((c) => {
      try { c.resize(); } catch {}
    });
  }

  window.addEventListener("resize", resizeAll);

  function renderClimograph(analysis) {
    const chart = getChart("chartClimograph");
    if (!chart) return;
    const c = colors();
    const rows = analysis.monthly_summary || [];
    const s = analysis.summary || {};
    const pav = analysis.pavement || {};
    const pma = pav.pma_mm ?? s.annual_precip_mm;
    chart.setOption({
      backgroundColor: c.bg,
      title: {
        subtext: `PMA = ${Number(pma || 0).toLocaleString()} mm/año  |  TMAP = ${pav.tmap_c ?? "-"} °C  |  Tmed = ${s.mean_annual_temp_c ?? "-"} °C`,
        left: 56,
        top: 0,
        subtextStyle: { color: c.muted, fontSize: 11, fontWeight: 600 },
      },
      tooltip: { trigger: "axis" },
      toolbox: originToolbox("Climograma"),
      legend: { top: 22, textStyle: { color: c.text, fontSize: 11 } },
      grid: { left: 60, right: 56, top: 56, bottom: 38 },
      xAxis: boxedCategoryX(rows.map((r) => r.month_abbr)),
      yAxis: [
        boxedY("Precipitación [mm]", false, { color: "#0072b2" }),
        boxedY("Temperatura [°C]", true, { color: "#d55e00", scale: true }),
      ],
      series: [
        { name: "Precipitación", type: "bar", data: rows.map((r) => r.precip_mm), itemStyle: { color: "#0072b2", borderColor: c.axis, borderWidth: 0.6 } },
        { name: "T. Media", type: "line", yAxisIndex: 1, smooth: false, symbol: "circle", symbolSize: 6, data: rows.map((r) => r.temp_mean_c), itemStyle: { color: "#e69f00", borderColor: "#0f172a", borderWidth: 1 }, lineStyle: { width: 2.3, color: "#0f172a" } },
        { name: "T. Máxima", type: "line", yAxisIndex: 1, smooth: false, symbol: "triangle", symbolSize: 6, data: rows.map((r) => r.temp_max_c), itemStyle: { color: "#d55e00" }, lineStyle: { type: "dashed", width: 1.4 } },
        { name: "T. Mínima", type: "line", yAxisIndex: 1, smooth: false, symbol: "diamond", symbolSize: 5, data: rows.map((r) => r.temp_min_c), itemStyle: { color: "#009e73" }, lineStyle: { type: "dashDot", width: 1.4 } },
      ],
    });
  }

  function renderWaterBalance(analysis) {
    const chart = getChart("chartWaterBalance");
    if (!chart) return;
    const c = colors();
    const rows = analysis.monthly_summary || [];
    const s = analysis.summary || {};
    chart.setOption({
      backgroundColor: c.bg,
      title: {
        subtext: `ETP = ${Number(s.annual_etp_mm || 0).toLocaleString()} mm  |  ETR = ${Number(s.annual_etr_mm || 0).toLocaleString()} mm  |  Im = ${s.thornthwaite_index_pct ?? "-"}%`,
        left: 56,
        top: 0,
        subtextStyle: { color: c.muted, fontSize: 11, fontWeight: 600 },
      },
      tooltip: { trigger: "axis" },
      toolbox: originToolbox("Balance_Hidrico"),
      legend: { top: 22, textStyle: { color: c.text, fontSize: 11 } },
      grid: { left: 60, right: 24, top: 56, bottom: 38 },
      xAxis: boxedCategoryX(rows.map((r) => r.month_abbr)),
      yAxis: [
        boxedY("Lámina Hídrica [mm]", false),
        { type: "value", axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisTick: { show: true, inside: true, length: 4 }, axisLabel: { show: false }, splitLine: { show: false } },
      ],
      series: [
        { name: "Precipitación", type: "bar", data: rows.map((r) => r.precip_mm), itemStyle: { color: "#0072b2", borderColor: c.axis, borderWidth: 0.5 } },
        { name: "ETP", type: "bar", data: rows.map((r) => r.etp_active_mm), itemStyle: { color: "#e69f00", borderColor: c.axis, borderWidth: 0.5 } },
        { name: "Almacenamiento", type: "line", symbol: "rect", symbolSize: 6, data: rows.map((r) => r.storage_mm), itemStyle: { color: "#009e73" }, lineStyle: { width: 2.2 } },
        { name: "Exceso", type: "line", symbol: "circle", symbolSize: 5, areaStyle: { opacity: 0.14 }, data: rows.map((r) => r.excess_mm), itemStyle: { color: "#15803d" }, lineStyle: { width: 1.8 } },
        { name: "Déficit", type: "line", symbol: "triangle", symbolSize: 5, areaStyle: { opacity: 0.14 }, data: rows.map((r) => r.deficit_mm), itemStyle: { color: "#d55e00" }, lineStyle: { width: 1.8 } },
      ],
    });
  }

  function renderAnnualSeries(analysis) {
    const chart = getChart("chartAnnualSeries");
    if (!chart) return;
    const c = colors();
    const rows = analysis.annual_summary || [];
    chart.setOption({
      backgroundColor: c.bg,
      tooltip: { trigger: "axis" },
      toolbox: originToolbox("Serie_Anual"),
      legend: { top: 4, textStyle: { color: c.text } },
      grid: { left: 60, right: 56, top: 42, bottom: 52 },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 6 }],
      xAxis: boxedCategoryX(rows.map((r) => r.year)),
      yAxis: [
        boxedY("Precipitación [mm]", false, { color: "#0072b2" }),
        boxedY("T. Media [°C]", true, { color: "#d55e00", scale: true }),
      ],
      series: [
        { name: "Precipitación Anual", type: "bar", data: rows.map((r) => r.precip_mm), itemStyle: { color: "#0072b2", borderColor: c.axis, borderWidth: 0.5 } },
        { name: "Temp. Media Anual", type: "line", yAxisIndex: 1, symbol: "circle", symbolSize: 5, data: rows.map((r) => r.temp_mean_c), itemStyle: { color: "#d55e00" }, lineStyle: { width: 2.2 } },
      ],
    });
  }

  function renderDailyExplorer(analysis) {
    const chart = getChart("chartDailyExplorer");
    if (!chart) return;
    const c = colors();
    const rows = analysis.daily_series_explorer || [];
    chart.setOption({
      backgroundColor: c.bg,
      tooltip: { trigger: "axis" },
      toolbox: originToolbox("Explorador_Diario"),
      legend: { top: 4, textStyle: { color: c.text } },
      grid: { left: 56, right: 54, top: 42, bottom: 52 },
      dataZoom: [{ type: "inside", start: 70, end: 100 }, { type: "slider", start: 70, end: 100, height: 18, bottom: 6 }],
      xAxis: boxedCategoryX(rows.map((r) => r.date)),
      yAxis: [
        boxedY("Lluvia / ET0 [mm]", false),
        boxedY("Temp [°C]", true, { scale: true }),
      ],
      series: [
        { name: "Precipitación", type: "bar", data: rows.map((r) => r.precip), itemStyle: { color: "#0072b2" } },
        { name: "T. Media", type: "line", yAxisIndex: 1, showSymbol: false, data: rows.map((r) => r.tmean), itemStyle: { color: "#d55e00" }, lineStyle: { width: 1.5 } },
        { name: "ET0", type: "line", showSymbol: false, data: rows.map((r) => r.et0), itemStyle: { color: "#009e73" }, lineStyle: { width: 1.4 } },
      ],
    });
  }

  function renderDailyClimatology(analysis) {
    const chart = getChart("chartDailyClimatology");
    if (!chart) return;
    const c = colors();
    const rows = analysis.daily_climatology || [];
    chart.setOption({
      backgroundColor: c.bg,
      tooltip: { trigger: "axis" },
      toolbox: originToolbox("Ciclo_Diario_365"),
      legend: { top: 4, textStyle: { color: c.text } },
      grid: { left: 56, right: 54, top: 42, bottom: 38 },
      xAxis: boxedCategoryX(rows.map((r) => `${r.month_abbr}-${r.day}`)),
      yAxis: [
        boxedY("Lámina [mm/día]", false),
        boxedY("Temperatura [°C]", true, { scale: true }),
      ],
      series: [
        { name: "Precip. Media Diaria", type: "bar", data: rows.map((r) => r.precip_mm), itemStyle: { color: "#0072b2" } },
        { name: "ETP Diaria", type: "line", showSymbol: false, data: rows.map((r) => r.etp_used_mm), itemStyle: { color: "#e69f00" }, lineStyle: { width: 1.6 } },
        { name: "Temp. Media", type: "line", yAxisIndex: 1, showSymbol: false, data: rows.map((r) => r.temp_mean_c), itemStyle: { color: "#d55e00" }, lineStyle: { width: 1.8 } },
      ],
    });
  }

  function renderCompleteness(analysis) {
    const chart = getChart("chartCompleteness");
    if (!chart) return;
    const c = colors();
    const q = analysis.quality || {};
    const vars = q.variable_summary || [];
    const mat = q.completeness_matrix || [];
    const years = mat.map((r) => String(r.year));
    const varNames = vars.map((v) => v.name);
    const data = [];
    mat.forEach((row, xi) => {
      vars.forEach((v, yi) => {
        data.push([xi, yi, row[String(v.var_id)] ?? 0]);
      });
    });

    chart.setOption({
      backgroundColor: c.bg,
      tooltip: {
        position: "top",
        formatter: (p) => `${years[p.value[0]]} · ${varNames[p.value[1]]}: <b>${p.value[2]}%</b>`,
      },
      toolbox: originToolbox("Mapa_Completitud"),
      grid: { left: 118, right: 20, top: 24, bottom: 44 },
      xAxis: { type: "category", data: years, axisLine: { lineStyle: { color: c.axis } }, axisLabel: { color: c.muted } },
      yAxis: { type: "category", data: varNames, axisLine: { lineStyle: { color: c.axis } }, axisLabel: { color: c.muted, fontSize: 10.5 } },
      visualMap: {
        min: 0, max: 100, orient: "horizontal", left: "center", bottom: 2,
        inRange: { color: ["#ef4444", "#f59e0b", "#22c55e", "#00897b"] },
        textStyle: { color: c.muted },
      },
      series: [{ type: "heatmap", data, label: { show: years.length <= 16, fontSize: 9 } }],
    });
  }

  function renderIdfChart(analysis) {
    const idf = analysis.hydrology_idf || {};
    const chartIdf = getChart("chartIdfCurves");
    if (!chartIdf || !idf.available) return;
    const c = colors();
    const table = idf.idf_table || [];
    const trs = [2, 5, 10, 25, 50, 100];
    const pal = ["#0072b2", "#009e73", "#e69f00", "#d55e00", "#dc2626", "#7e22ce"];

    const xAxisDef = [
      {
        type: idfLogMode ? "log" : "value",
        name: "Duración t [min]",
        nameLocation: "middle",
        nameGap: 24,
        nameTextStyle: { color: c.text, fontWeight: 700, fontSize: 11.5 },
        min: idfLogMode ? 4 : 0,
        max: 185,
        axisLine: { show: true, onZero: false, lineStyle: { color: c.axis, width: 1.2 } },
        axisTick: { show: true, inside: true, length: 5, lineStyle: { color: c.axis } },
        minorTick: { show: !idfLogMode, splitNumber: 2, length: 3, lineStyle: { color: c.axis } },
        axisLabel: { color: c.muted },
        splitLine: { show: true, lineStyle: { color: c.grid, type: "dashed", width: 0.8 } },
      },
      {
        type: "value",
        position: "top",
        axisLine: { show: true, onZero: false, lineStyle: { color: c.axis, width: 1.2 } },
        axisLabel: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      },
    ];

    chartIdf.setOption({
      backgroundColor: c.bg,
      title: {
        subtext: `${idf.idf_params.formula}   |   M(P24h) = ${idf.m_pmax_24h_mean_mm} mm`,
        left: 60,
        top: 0,
        subtextStyle: { color: c.muted, fontSize: 11, fontWeight: 600 },
      },
      tooltip: { trigger: "axis" },
      toolbox: originToolbox("Curvas_IDF"),
      legend: { top: 22, textStyle: { color: c.text, fontSize: 11 } },
      grid: { left: 62, right: 24, top: 56, bottom: 42 },
      xAxis: xAxisDef,
      yAxis: [
        boxedY("Intensidad [mm/h]", false, { type: idfLogMode ? "log" : "value", nameGap: 46 }),
        { type: "value", axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
      ],
      series: trs.map((tr, i) => ({
        name: `Tr=${tr} a`,
        type: "line",
        symbol: "circle",
        symbolSize: 4,
        itemStyle: { color: pal[i] },
        lineStyle: { width: 2.0 },
        data: table.map((r) => [r.duration_min, r[`tr_${tr}`]]),
      })),
    });
  }

  function renderEngineering(analysis) {
    const idf = analysis.hydrology_idf || {};
    const pav = analysis.pavement || {};
    const c = colors();

    // 1. Curvas IDF
    renderIdfChart(analysis);

    // 2. Frecuencia P24h (4 distribuciones + puntos empíricos de Gringorten en escala log-X)
    const chartG = getChart("chartGumbel");
    if (chartG && idf.available) {
      const dists = idf.distributions || {};
      const styles = [
        { name: "Gumbel", color: "#0072b2", type: "solid" },
        { name: "Log-Normal", color: "#009e73", type: "dotted" },
        { name: "Log-Pearson III", color: "#d55e00", type: "dashed" },
        { name: "GEV", color: "#7e22ce", type: "solid" },
      ];
      const bestObj = dists[idf.best_distribution] || {};
      const series = styles
        .filter((st) => dists[st.name])
        .map((st) => ({
          name: st.name === idf.best_distribution ? `${st.name} ★` : st.name,
          type: "line",
          symbol: "none",
          data: dists[st.name].quantiles.map((q) => [q.tr, q.p24h_mm]),
          itemStyle: { color: st.color },
          lineStyle: { type: st.type, width: st.name === idf.best_distribution ? 2.6 : 1.6 },
        }));

      const empPts = idf.empirical_points || [];
      if (empPts.length) {
        series.push({
          name: "Observada (Gringorten)",
          type: "scatter",
          symbol: "circle",
          symbolSize: 7,
          itemStyle: { color: "#ffffff", borderColor: c.axis, borderWidth: 1.5 },
          data: empPts.map((p) => [p.tr, p.p24h_mm]),
          z: 6,
        });
      }

      chartG.setOption({
        backgroundColor: c.bg,
        title: {
          subtext: `Mejor K-S: ${idf.best_distribution} (D = ${bestObj.ks_d ?? "-"}, p = ${bestObj.ks_pvalue ?? "-"}, R² = ${bestObj.r2 ?? "-"})`,
          left: 60,
          top: 0,
          subtextStyle: { color: c.muted, fontSize: 11, fontWeight: 600 },
        },
        tooltip: { trigger: "axis" },
        toolbox: originToolbox("Frecuencia_P24h"),
        legend: { top: 22, textStyle: { color: c.text, fontSize: 10.5 } },
        grid: { left: 60, right: 24, top: 56, bottom: 42 },
        xAxis: [
          {
            type: "log",
            name: "Período de Retorno Tr [años]",
            nameLocation: "middle",
            nameGap: 24,
            nameTextStyle: { color: c.text, fontWeight: 700, fontSize: 11.5 },
            min: 1,
            max: 110,
            axisLine: { show: true, onZero: false, lineStyle: { color: c.axis, width: 1.2 } },
            axisTick: { show: true, inside: true, length: 5, lineStyle: { color: c.axis } },
            axisLabel: { color: c.muted },
            splitLine: { show: true, lineStyle: { color: c.grid, type: "dashed" } },
          },
          { type: "value", position: "top", axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
        ],
        yAxis: [
          boxedY("P24h máx [mm]", false, { scale: true }),
          { type: "value", axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
        ],
        series,
      });
    }

    // 2b. Hietograma Bloques Alternos
    const chartHy = getChart("chartHyetograph");
    if (chartHy && idf.available && (idf.hyetograph || []).length) {
      const hy = idf.hyetograph;
      const totP = hy[hy.length - 1]?.cum_depth_mm ?? 0;
      const maxI = Math.max(...hy.map((r) => r.intensity_mmh));
      chartHy.setOption({
        backgroundColor: c.bg,
        title: {
          subtext: `Tr = ${idf.hyetograph_tr} años  |  Dur = ${idf.hyetograph_duration_min} min  |  P_total = ${totP} mm  |  I_pico = ${maxI} mm/h`,
          left: 58,
          top: 0,
          subtextStyle: { color: c.muted, fontSize: 11, fontWeight: 600 },
        },
        tooltip: { trigger: "axis" },
        toolbox: originToolbox("Hietograma_Diseno"),
        legend: { top: 22, textStyle: { color: c.text, fontSize: 11 } },
        grid: { left: 58, right: 54, top: 56, bottom: 42 },
        xAxis: boxedCategoryX(hy.map((r) => r.time_min), "Intervalo [min]", { axisLabel: { fontSize: 10, rotate: 22 } }),
        yAxis: [
          boxedY("Lámina Bloque [mm]", false, { color: "#0072b2" }),
          boxedY("Acumulada [mm]", true, { color: "#d55e00" }),
        ],
        series: [
          { name: "Bloque [mm]", type: "bar", data: hy.map((r) => r.depth_mm), itemStyle: { color: "#0072b2", borderColor: c.axis, borderWidth: 0.6 } },
          { name: "Acumulada [mm]", type: "line", yAxisIndex: 1, symbol: "circle", symbolSize: 5, data: hy.map((r) => r.cum_depth_mm), itemStyle: { color: "#d55e00" }, lineStyle: { width: 2.0 } },
        ],
      });
    }

    // 3. TMAP Anual + 7-day Max Temp
    const chart7 = getChart("chart7DayTemp");
    if (chart7) {
      const rows7 = pav.max_7day_yearly || [];
      const rowsTmap = pav.tmap_yearly || [];
      const allYears = Array.from(new Set([...rows7.map((r) => r.year), ...rowsTmap.map((r) => r.year)])).sort((a, b) => a - b);
      const map7 = new Map(rows7.map((r) => [r.year, r.temp_7d_c]));
      const mapT = new Map(rowsTmap.map((r) => [r.year, r.tmap_c]));
      const reg = pav.invias_pavement_region || {};
      chart7.setOption({
        backgroundColor: c.bg,
        title: {
          subtext: `1. TMAP = ${pav.tmap_c ?? "-"} °C  |  2. PMA = ${Number(pav.pma_mm || 0).toLocaleString()} mm  |  INVIAS: ${reg.code || "-"}`,
          left: 58,
          top: 0,
          subtextStyle: { color: c.muted, fontSize: 11, fontWeight: 600 },
        },
        tooltip: { trigger: "axis" },
        toolbox: originToolbox("TMAP_Pavimentos"),
        legend: { top: 22, textStyle: { color: c.text, fontSize: 11 } },
        grid: { left: 58, right: 24, top: 56, bottom: 38 },
        xAxis: boxedCategoryX(allYears),
        yAxis: [
          boxedY("Temperatura [°C]", false, { scale: true }),
          { type: "value", axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
        ],
        series: [
          { name: "T.Máx 7d Consecutivos", type: "line", symbol: "triangle", symbolSize: 6, data: allYears.map((y) => map7.get(y) ?? null), itemStyle: { color: "#d55e00" }, areaStyle: { opacity: 0.08 }, lineStyle: { width: 2.0 } },
          { name: "TMAP Anual (Shell)", type: "line", symbol: "circle", symbolSize: 6, data: allYears.map((y) => mapT.get(y) ?? null), itemStyle: { color: "#00897b" }, lineStyle: { width: 2.4 } },
        ],
      });
    }

    // 4. SPI-3 & SPI-12
    const chartSpi = getChart("chartSpi");
    if (chartSpi && idf.spi) {
      const s3 = idf.spi.spi_3 || [];
      const s12 = idf.spi.spi_12 || [];
      const s12Map = new Map(s12.map((x) => [x.date, x.value]));
      chartSpi.setOption({
        backgroundColor: c.bg,
        tooltip: { trigger: "axis" },
        toolbox: originToolbox("Indice_SPI"),
        legend: { top: 4, textStyle: { color: c.text } },
        grid: { left: 54, right: 22, top: 42, bottom: 50 },
        dataZoom: [{ type: "inside" }, { type: "slider", height: 16, bottom: 6 }],
        xAxis: boxedCategoryX(s3.map((x) => x.date)),
        yAxis: [
          boxedY("Índice SPI [-]", false, { min: -3, max: 3 }),
          { type: "value", min: -3, max: 3, axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
        ],
        series: [
          {
            name: "SPI-3",
            type: "bar",
            data: s3.map((x) => ({
              value: x.value,
              itemStyle: { color: x.value >= 0 ? "#0072b2" : "#d55e00" },
            })),
          },
          {
            name: "SPI-12",
            type: "line",
            showSymbol: false,
            data: s3.map((x) => s12Map.get(x.date) ?? null),
            itemStyle: { color: "#0f766e" },
            lineStyle: { width: 2.1 },
          },
        ],
      });
    }
  }

  function renderTwStandalone(res) {
    const chart = getChart("chartTwStandalone");
    if (!chart) return;
    const c = colors();
    const rows = res.rows || [];
    chart.setOption({
      backgroundColor: c.bg,
      tooltip: { trigger: "axis" },
      toolbox: originToolbox("Thornthwaite_Mensual"),
      legend: { top: 4, textStyle: { color: c.text } },
      grid: { left: 58, right: 22, top: 42, bottom: 38 },
      xAxis: boxedCategoryX(rows.map((r) => r.month.slice(0, 3))),
      yAxis: [
        boxedY("Lámina [mm]", false),
        { type: "value", axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
      ],
      series: [
        { name: "Precipitación", type: "bar", data: rows.map((r) => r.precip_mm), itemStyle: { color: "#0072b2", borderColor: c.axis, borderWidth: 0.5 } },
        { name: "ETP Corregida", type: "bar", data: rows.map((r) => r.etp_corrected_mm), itemStyle: { color: "#e69f00", borderColor: c.axis, borderWidth: 0.5 } },
        { name: "Almacenamiento", type: "line", symbol: "rect", symbolSize: 5, data: rows.map((r) => r.storage_mm), itemStyle: { color: "#009e73" }, lineStyle: { width: 2 } },
        { name: "Exceso", type: "line", data: rows.map((r) => r.excess_mm), itemStyle: { color: "#15803d" } },
        { name: "Déficit", type: "line", data: rows.map((r) => r.deficit_mm), itemStyle: { color: "#d55e00" } },
      ],
    });
  }

  function setIdfLogMode(enabled, analysis) {
    idfLogMode = Boolean(enabled);
    if (analysis) renderIdfChart(analysis);
  }

  function renderGeohazardsDroughtAndRusle(analysis) {
    const c = colors();

    // A. Envolvente Empírica SGC (R15_ant vs R3)
    const chSgc = getChart("chartSgcThresholds");
    const sgc = analysis.geohazards_sgc || {};
    if (chSgc && sgc.available) {
      const pts = sgc.scatter_points || [];
      const norm = pts.filter((p) => !p.exceeds).map((p) => [p.r15_ant, p.r3, p.date]);
      const exc = pts.filter((p) => p.exceeds).map((p) => [p.r15_ant, p.r3, p.date]);
      const a = Number(sgc.r3_intercept || 70);
      const b = Number(sgc.r15_slope || 0.47);
      const maxX = Math.max(120, ...pts.map((p) => p.r15_ant), 180) * 1.05;
      const linePts = [];
      for (let i = 0; i <= 40; i++) {
        const xv = (maxX * i) / 40;
        linePts.push([Number(xv.toFixed(1)), Number(Math.max(5, a - b * xv).toFixed(2))]);
      }
      chSgc.setOption({
        backgroundColor: c.bg,
        tooltip: {
          trigger: "item",
          formatter: (p) => (p.value && p.value[2] ? `${p.seriesName}<br/>Fecha: <b>${p.value[2]}</b><br/>R15 ant: ${p.value[0]} mm<br/>R3: <b>${p.value[1]} mm</b>` : `${p.seriesName}: (${p.value[0]}, ${p.value[1]})`),
        },
        toolbox: originToolbox("SGC_Umbral_Lluvia"),
        legend: { top: 4, textStyle: { color: c.text, fontSize: 10.5 } },
        grid: { left: 54, right: 18, top: 40, bottom: 42 },
        xAxis: {
          type: "value", name: "Lluvia Antecedente 15 días [mm]", nameLocation: "middle", nameGap: 24,
          nameTextStyle: { color: c.text, fontWeight: 700, fontSize: 11 },
          axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisTick: { show: true, inside: true },
          axisLabel: { color: c.muted, fontSize: 10.5 }, splitLine: { lineStyle: { color: c.grid, type: "dashed" } },
        },
        yAxis: [
          boxedY("Lluvia 3 días R3 [mm]", false),
          { type: "value", axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
        ],
        series: [
          { name: "Días húmedos normales", type: "scatter", symbolSize: 5, data: norm, itemStyle: { color: "rgba(59, 130, 246, 0.55)" } },
          { name: "Excedencia SGC", type: "scatter", symbol: "diamond", symbolSize: 8, data: exc, itemStyle: { color: "#dc2626", borderColor: "#450a0a", borderWidth: 0.6 } },
          { name: "Umbral SGC", type: "line", showSymbol: false, data: linePts, itemStyle: { color: "#991b1b" }, lineStyle: { width: 2.0, type: "dashed" } },
        ],
      });
    }

    // B. SPEI-3 / SPEI-12 (D = P - ET0)
    const chSpei = getChart("chartSpeiDrought");
    const drg = analysis.drought || {};
    if (chSpei && (drg.spei_3 || []).length) {
      const s3 = drg.spei_3;
      const s12Map = new Map((drg.spei_12 || []).map((x) => [x.date, x.value]));
      chSpei.setOption({
        backgroundColor: c.bg,
        tooltip: { trigger: "axis" },
        toolbox: originToolbox("SPEI_Sequias"),
        legend: { top: 4, textStyle: { color: c.text } },
        grid: { left: 54, right: 20, top: 40, bottom: 48 },
        dataZoom: [{ type: "inside" }, { type: "slider", height: 15, bottom: 5 }],
        xAxis: boxedCategoryX(s3.map((x) => x.date)),
        yAxis: [
          boxedY("Índice SPEI [Z]", false, { min: -3.2, max: 3.2 }),
          { type: "value", min: -3.2, max: 3.2, axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
        ],
        series: [
          {
            name: "SPEI-3", type: "bar",
            data: s3.map((x) => ({ value: x.value, itemStyle: { color: x.value >= 0 ? "#009e73" : "#d55e00" } })),
          },
          { name: "SPEI-12", type: "line", showSymbol: false, data: s3.map((x) => s12Map.get(x.date) ?? null), itemStyle: { color: "#0f172a" }, lineStyle: { width: 2.0 } },
        ],
      });
    }

    // C. IAP (%) IDEAM Anual
    const chIap = getChart("chartIapAnnual");
    if (chIap && (drg.iap_annual || []).length) {
      const iap = drg.iap_annual;
      chIap.setOption({
        backgroundColor: c.bg,
        tooltip: { trigger: "axis" },
        toolbox: originToolbox("IAP_Anomalias_IDEAM"),
        grid: { left: 56, right: 20, top: 36, bottom: 38 },
        xAxis: boxedCategoryX(iap.map((r) => r.year)),
        yAxis: [
          boxedY("Anomalía P [%]", false),
          { type: "value", axisLine: { show: true, lineStyle: { color: c.axis, width: 1.2 } }, axisLabel: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
        ],
        series: [
          {
            name: "Anomalía vs PMA (%)", type: "bar",
            data: iap.map((r) => ({ value: r.anomaly_pct, itemStyle: { color: r.anomaly_pct >= 0 ? "#0072b2" : "#e69f00", borderColor: c.axis, borderWidth: 0.5 } })),
          },
        ],
      });
    }

    // D. Erosividad Mensual RUSLE (Factor R % + Precipitación)
    const chRusle = getChart("chartRusleMonthly");
    const ero = analysis.erosivity || {};
    if (chRusle && ero.available && (ero.monthly_distribution || []).length) {
      const mr = ero.monthly_distribution;
      chRusle.setOption({
        backgroundColor: c.bg,
        tooltip: { trigger: "axis" },
        toolbox: originToolbox("Erosividad_RUSLE"),
        legend: { top: 4, textStyle: { color: c.text } },
        grid: { left: 54, right: 54, top: 42, bottom: 36 },
        xAxis: boxedCategoryX(mr.map((m) => m.month)),
        yAxis: [
          boxedY("Aporte Factor R [%]", false, { color: "#b45309" }),
          boxedY("Precipitación [mm]", true, { color: "#0072b2" }),
        ],
        series: [
          { name: "Aporte R (%)", type: "bar", data: mr.map((m) => m.r_share_pct), itemStyle: { color: "#d97706", borderColor: c.axis, borderWidth: 0.5 } },
          { name: "Precipitación (mm)", type: "line", yAxisIndex: 1, symbol: "circle", symbolSize: 5, data: mr.map((m) => m.precip_mm), itemStyle: { color: "#0072b2" }, lineStyle: { width: 2.0 } },
        ],
      });
    }
  }

  function renderAllResults(analysis) {
    renderClimograph(analysis);
    renderWaterBalance(analysis);
    renderAnnualSeries(analysis);
    renderDailyExplorer(analysis);
    renderDailyClimatology(analysis);
    renderCompleteness(analysis);
    renderEngineering(analysis);
    renderGeohazardsDroughtAndRusle(analysis);
  }

  return { renderAllResults, renderTwStandalone, setIdfLogMode, resizeAll };
})();
