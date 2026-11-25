window.ClimaHelp = (() => {
  const HELP_TOPICS = [
    {
      id: "workflow",
      cat: "Guía de Inicio",
      icon: "🚀",
      title: "Flujo de Trabajo Paso a Paso",
      subtitle: "Cómo pasar de estaciones hidrometeorológicas a informes de ingeniería completos en 6 pasos.",
      badges: ["F1: Ayuda", "Ctrl+Enter: Calcular", "6 Pestañas"],
      what: "Guía operativa estándar para estructurar cualquier estudio climático, hidrológico, ambiental, geotécnico o de pavimentos en HidroClima Studio.",
      inputs: [
        "1. En la pestaña <b>1. Área GIS, Corredor y Red</b>: filtra por departamento/municipio o carga un corredor vial (<b>KML, KMZ o GeoJSON</b>) con buffer en km.",
        "2. Agrega estaciones al proyecto y calcula pesos espaciales automáticos (<b>IDW</b> para corredores/puntos o <b>Thiessen</b> por área).",
        "3. (Opcional) Si faltan años recientes o variables (Tmax, Tmin, HR, Brillo/Radiación), ve a <b>5. Puente de Datos</b> o presiona <b>Actualizar Datos</b> para descargar desde <b>datos.gov.co (IDEAM)</b>, <b>Open-Meteo ERA5</b> o <b>NASA POWER</b>.",
        "4. En el panel izquierdo ajusta los parámetros del modelo: ventana de años, método ETP, reserva máx. de suelo, nivel freático, método IDF, geometría de cuenca y umbral SGC.",
        "5. Haz clic en <b>▶ Calcular Análisis</b> (o <code>Ctrl+Enter</code>).",
        "6. Explora resultados en <b>2. Climatología, Sequías y RUSLE</b> y <b>3. Hidrología IDF, Cuenca SGC y Pavimentos</b>, y exporta informes desde <b>6. Informes y Exportaciones</b>.",
      ],
      outputs: [
        "Informe PDF técnico multipágina sin desbordamientos.",
        "Documento Word (.docx) editable y libro Excel (.xlsx) con 10 hojas formuladas.",
        "Archivos listos para EPA SWMM, HEC-HMS, AASHTOWare MEPDG, sistemas GIS y 7 gráficas científicas de alta resolución.",
      ],
      norm: "Flujo unificado para consultoría vial (INVIAS / RAS), estudios ambientales (ANLA / ENA-IDEAM) y gestión del riesgo (SGC / UNGRD).",
    },
    {
      id: "gis_spatial",
      cat: "Geoespacial y Datos",
      icon: "🗺️",
      title: "Área GIS, Corredores KML/KMZ y Ponderación Espacial",
      subtitle: "Selección multipunto sobre el catálogo nacional de 8.973 estaciones y asignación de pesos.",
      badges: ["8.973 Estaciones", "IDW p=2", "Thiessen", "KML / KMZ / GeoJSON"],
      what: "Permite localizar estaciones ideológicas representativas dentro del área de influencia directa de una vía, predio o cuenca hidrográfica y combinar sus series diarias mediante ponderación dinámica día a día.",
      inputs: [
        "Filtros por Departamento (33), Municipio (1.121), Categoría, Estado o texto libre.",
        "Corredor o polígono importado (<code>.kml</code>, <code>.kmz</code>, <code>.geojson</code>) o trazado manualmente sobre el mapa Leaflet.",
        "Buffer de búsqueda y área de influencia en kilómetros (por defecto 15 km).",
      ],
      outputs: [
        "Tabla de estaciones con distancia mínima al corredor y series locales disponibles.",
        "Pesos normalizados (suma 100%) por <b>IDW</b> <code>w_i = (d_i + 0.1)^(-2)</code>, <b>Thiessen discreto</b> (conteo de celdas en Voronoi sobre el corredor) o asignación <b>Manual / Igual</b>.",
        "Exportación de estaciones ponderadas y traza de proyecto en GeoJSON y KML.",
      ],
      norm: "Distancias geodésicas calculadas por fórmula de Haversine sobre coordenadas WGS84.",
    },
    {
      id: "bridges_data",
      cat: "Geoespacial y Datos",
      icon: "🛰️",
      title: "Puentes Multi-Fuente y Editor Diario 12×31",
      subtitle: "Sincronización abierta y gratuita con Datos Abiertos Colombia, Open-Meteo, NASA POWER y archivos DHIME/SHC.",
      badges: ["Software Libre", "datos.gov.co", "ERA5 / NASA", "DHIME / .dat"],
      what: "Unifica fuentes oficiales colombianas e internacionales en una base local SQLite (modo WAL) comprimida con matrices anuales 12×31 en <code>zlib</code>, garantizando trazabilidad por prioridad sin sobrescribir observaciones oficiales con reanálisis.",
      inputs: [
        "<b>IDEAM API (datos.gov.co):</b> consulta catálogo y series Socrata abiertas (incluyendo tiempo real <code>57sv-p2fu</code> y estaciones automáticas cercanas <code>- AUT</code>).",
        "<b>Open-Meteo ERA5 & NASA POWER:</b> complementación diaria abierta y gratuita sin credenciales comerciales para lluvia, temperatura, humedad relativa, radiación solar y viento.",
        "<b>Importadores locales:</b> descargas CSV/XLSX de DHIME, paquetes comprimidos históricos (<code>.zip</code>, <code>.rar</code>, <code>SHC/*.dat</code>) y archivos de proyecto <code>.hclim</code>.",
        "<b>Editor Matriz 12×31:</b> corrección directa día a día marcada con prioridad máxima <code>Manual</code>.",
      ],
      outputs: [
        "Orden de prioridad al consolidar: <code>Manual &gt; IDEAM-DHIME &gt; IDEAM-API &gt; Archivo-Histórico &gt; IDEAM-Legacy &gt; NASA-POWER &gt; Open-Meteo</code>.",
        "Historial auditado de sincronizaciones y métricas exactas de origen por variable.",
      ],
      norm: "Arquitectura offline-first: todo análisis funciona localmente tras sincronizar o cargar archivos.",
    },
    {
      id: "climate_balance",
      cat: "Climatología y EIA",
      icon: "☀️",
      title: "Climatología, Evapotranspiración FAO-56 y Balance Hídrico",
      subtitle: "Radiación solar astronómica/estimada, ETP Penman-Monteith vs Thornthwaite y balance cíclico del suelo.",
      badges: ["Penman-Monteith FAO-56", "Thornthwaite 1948", "Reserva R_max"],
      what: "Calcula la evapotranspiración potencial diaria y mensual y simula el ciclo anual estacionario de humedad edáfica para cuantificar evapotranspiración real (ETR), excesos por escorrentía/percolación y déficit hídrico.",
      inputs: [
        "Latitud y altitud ponderadas de las estaciones activas.",
        "Método ETP: <b>Penman-Monteith (FAO-56)</b> o <b>Thornthwaite (1948)</b>.",
        "<b>Reserva Máxima de Agua en el Suelo (R_max)</b> en mm (típico 100 mm).",
        "Radiación solar en cadena jerárquica: observada directa &rarr; Angstrom-Prescott desde brillo solar &rarr; Hargreaves-Samani desde amplitud térmica.",
      ],
      outputs: [
        "Climograma ombrotérmico multianual (P, Tmed, Tmáx, Tmín).",
        "Balance hídrico cíclico mensual y diario (ETR, Almacenamiento, Exceso, Déficit).",
        "Índices de humedad (<code>Ih %</code>), aridez (<code>Ia %</code>), índice hídrico de Thornthwaite (<code>Im %</code> y <code>TMI MEPDG</code>) y temperatura media anual ponderada.",
        "Calculadora independiente <b>4. Thornthwaite Mensual</b> para digitación manual de 12 meses con presets de ciudades colombianas.",
      ],
      norm: "FAO Irrigation and Drainage Paper No. 56 (Allen et al., 1998) y Thornthwaite (1948).",
    },
    {
      id: "classifications",
      cat: "Climatología y EIA",
      icon: "🌿",
      title: "Clasificaciones Climáticas Oficiales (ANLA / ENA-IDEAM)",
      subtitle: "Caldas-Lang, Zonas de Vida de Holdridge, Köppen-Geiger, Thornthwaite e Índice de Aridez.",
      badges: ["Caldas-Lang", "Holdridge", "Köppen-Geiger", "Aridez ENA"],
      what: "Genera automáticamente los cuatro sistemas de zonificación bioclimática exigidos en Estudios de Impacto Ambiental (EIA ANLA), POMCA y Planes de Ordenamiento Territorial en Colombia.",
      inputs: [
        "Serie consolidada mensual multianual de precipitación y temperatura media del proyecto.",
        "ETR y ETP anuales del balance hídrico cíclico.",
      ],
      outputs: [
        "<b>Caldas-Lang (IDEAM):</b> Piso térmico de Caldas + Factor de Lang (<code>P/T</code>).",
        "<b>Holdridge (1967):</b> Biotemperatura media, <code>ETP_H = 58.93 * T_bio</code>, relación EPT y nombre oficial de Zona de Vida.",
        "<b>Köppen-Geiger:</b> Códigos globales tropicales/andinos/secos (<code>Af, Am, Aw, BW, BS, Cf, Cw, ET</code>).",
        "<b>Índice de Aridez ENA-IDEAM:</b> <code>IA = (ETP - ETR) / ETP</code> con su categoría oficial de excedente o déficit.",
      ],
      norm: "Metodología General para la Presentación de Estudios Ambientales (ANLA / MADS) y Estudio Nacional del Agua (IDEAM).",
    },
    {
      id: "idf_hydrology",
      cat: "Hidrología y Drenaje",
      icon: "🌧️",
      title: "Hidrología Extrema P24h, Curvas IDF y Hietograma",
      subtitle: "Frecuencias anuales con bondad de ajuste K-S, 4 modelos IDF colombianos, Bloques Alternos y normativa RAS/INVIAS.",
      badges: ["Gumbel / LP-III / GEV", "K-S Test", "4 Métodos IDF", "Bloques Alternos"],
      what: "Analiza la serie histórica de precipitación máxima en 24 horas (años con completitud ≥ 70%), ajusta cuatro distribuciones de probabilidad, construye la familia de curvas IDF para períodos de retorno de 2 a 100 años y sintetiza tormentas de diseño.",
      inputs: [
        "Serie diaria de precipitación y selección de método IDF: <b>INVIAS Regionalizado</b> (Vargas & Díaz-Granados 1998 para Andina, Caribe, Pacífico, Orinoquía), <b>Gustavo Silva</b>, <b>Sherman</b> o <b>Bell</b>.",
        "Período de retorno (<code>Tr</code>) y duración total de tormenta para el Hietograma de Diseño.",
      ],
      outputs: [
        "Tabla comparativa de cuantiles y bondad de ajuste <b>Kolmogorov-Smirnov (D, p-valor)</b> y <b>R²</b> frente a puntos empíricos de <b>Gringorten</b> para Gumbel, Log-Normal, Log-Pearson III y GEV.",
        "Gráficas interactivas con selector de escala <b>Log-Log / Lineal</b> y familia IDF completa (5 min a 24 h).",
        "<b>Hietograma de Bloques Alternos</b> (pasos Δt = 5 min) exportable directamente en CSV para <b>EPA SWMM</b> y <b>HEC-HMS</b>.",
        "Evaluación normativa de intensidades <code>i(tc=15m)</code> y <code>i(tc=30m)</code> según <b>RAS Res. 0330/2017</b> y <b>Manual de Drenaje INVIAS</b>.",
      ],
      norm: "RAS Resolución 0330 de 2017 (MVCT), Manual de Drenaje para Carreteras INVIAS y Vargas & Díaz-Granados (1998).",
    },
    {
      id: "watershed_scs",
      cat: "Hidrología y Drenaje",
      icon: "🌊",
      title: "Cuenca Hidrográfica (INVIAS / Kirpich / Racional / SCS-CN)",
      subtitle: "Cálculo instantáneo de tiempos de concentración y caudales pico de diseño hidráulico.",
      badges: ["Kirpich / Témez", "Método Racional", "SCS-CN Hidrograma", "Recálculo en Vivo"],
      what: "Transforma la curva IDF del proyecto en caudales pico de diseño y láminas de escorrentía/infiltración para obras de drenaje transversal y longitudinal (cunetas, alcantarillas, box culverts y puentes menores).",
      inputs: [
        "Área drenada <code>A</code> (km²), longitud hidráulica del cauce <code>L</code> (m) y pendiente media <code>S</code> (%).",
        "Cobertura / uso del suelo preestablecido o personalizado mediante <b>Número de Curva CN II</b> y <b>Coeficiente de Escorrentía C</b>.",
      ],
      outputs: [
        "Tiempo de concentración <code>tc</code> por <b>Kirpich (1940)</b> y <b>Témez (1978)</b>.",
        "Caudal pico <b>Método Racional</b> <code>Q = C · I(Tr, tc) · A / 3.6</code> (m³/s) para Tr = 2, 5, 10, 20, 25, 50 y 100 años.",
        "Lámina de tormenta de diseño, escorrentía directa <code>Qe</code> (mm), infiltración potencial <code>F</code> (mm) y caudal pico de hidrograma unitario triangular <b>SCS</b>.",
        "Recálculo instantáneo sin re-agregar series diarias desde la subpestaña <b>Cuenca INVIAS/SCS y Geotecnia SGC</b> y hoja formulada en Excel.",
      ],
      norm: "Manual de Drenaje para Carreteras INVIAS y metodología SCS-TR55 (USDA).",
    },
    {
      id: "geotecnia_sgc",
      cat: "Geotecnia SGC y Riesgo",
      icon: "⛰️",
      title: "Geotecnia SGC: Umbrales de Lluvia Detonante e Infiltración",
      subtitle: "Lluvias acumuladas móviles (R1..R90), envolvente empírica R15_ant vs R3 y episodios históricos críticos.",
      badges: ["Guías SGC", "Umbral R3-R15", "Episodios Críticos", "SCS CN I/II/III"],
      what: "Evalúa la susceptibilidad climática a la detonación de movimientos en masa por lluvia acumulada e intensidad previa, cuantificando ventanas móviles e identificando eventos históricos de excedencia para estudios geotécnicos de estabilidad de laderas y taludes viales.",
      inputs: [
        "Serie diaria continua de precipitación consolidada.",
        "Parámetros de envolvente crítica <b>Moreno et al. / SGC</b>: <code>R3_crít = máx(5, a - b · R15_ant)</code> (por defecto <code>a = 70 mm</code>, <code>b = 0.47</code>).",
        "Número de Curva <code>CN II</code> del suelo para estimar condición seca (<code>CN I</code>), normal (<code>CN II</code>) y saturada (<code>CN III</code>).",
      ],
      outputs: [
        "Cuantiles (<code>Media, P90, P95, P99, Máximo y Fecha</code>) para ventanas móviles <code>R1, R3, R7, R15, R30 y R90</code> días.",
        "Diagrama de dispersión <code>R15_ant vs R3</code> con línea de umbral crítico y conteo anual de días críticos.",
        "Catálogo de <b>episodios históricos críticos</b> agrupados con fecha pico, R1, R3, R15 antecedente y factor de severidad.",
        "Balance diario de infiltración potencial frente a escorrentía directa SCS y hoja formulada en Excel <code>Geotecnia_SGC_Lluvias</code>.",
      ],
      norm: "Guía Metodológica para Estudios de Amenaza, Vulnerabilidad y Riesgo por Movimientos en Masa (Servicio Geológico Colombiano - SGC).",
    },
    {
      id: "rusle_spei",
      cat: "Geotecnia SGC y Riesgo",
      icon: "📉",
      title: "Erosividad Pluvial (RUSLE / ANLA) y Sequías (SPEI / IAP)",
      subtitle: "Factor R mensual/anual, índices MFI/PCI, monitoreo multiescalar de sequías SPEI y anomalías IDEAM.",
      badges: ["RUSLE Factor R", "MFI Arnoldus / PCI", "SPEI-3 & SPEI-12", "IAP (%) IDEAM"],
      what: "Combina indicadores de agresividad erosiva del agua lluvia sobre suelos descubiertos (EIA ANLA) con monitoreo multiescalar de déficit/exceso hídrico para gestión ambiental y gestión del riesgo agroclimático/desabastecimiento.",
      inputs: [
        "Precipitación media mensual multianual para el cálculo de <b>Fournier (FI)</b>, <b>Fournier Modificado (MFI)</b>, <b>PCI</b> y <b>Factor R (Renard & Freimund 1994)</b>.",
        "Serie mensual continua de balance climático <code>D = P - ET0</code> para ajuste Log-Logístico de 3 parámetros (<b>Fisk</b>) en escalas de 3 y 12 meses (<b>SPEI</b>), junto a totales anuales para <b>IAP (%)</b>.",
      ],
      outputs: [
        "Clasificación de agresividad climática (Muy baja a Muy alta) y distribución mensual porcentual de erosividad <code>R_m</code>.",
        "Series de <b>SPEI-3</b> y <b>SPEI-12</b> con frecuencias de sequía moderada (≤ -1.0), severa (≤ -1.5) y extrema (≤ -2.0).",
        "Serie histórica de <b>IAP (%)</b> identificando años secos (El Niño) y muy húmedos (La Niña).",
      ],
      norm: "Renard & Freimund (1994), Arnoldus (1980), Oliver (1980), Vicente-Serrano et al. (2010) y lineamientos ANLA / UNGRD / IDEAM.",
    },
    {
      id: "pavement_tmap",
      cat: "Ingeniería de Pavimentos",
      icon: "🛣️",
      title: "Pavimentos: 1. TMAP (Shell) · 2. PMA · INVIAS · Superpave PG",
      subtitle: "Cálculo completo térmico y pluvial para diseño de pavimentos flexibles, rígidos y ligantes asfálticos.",
      badges: ["1. TMAP Carta W", "2. PMA (mm/a)", "INVIAS R1–R6", "Superpave PG / MEPDG"],
      what: "Calcula los parámetros climáticos normativos exigidos en diseño de pavimentos en Colombia e internacionalmente: Temperatura Media Anual Ponderada (TMAP), Precipitación Media Anual (PMA), región climática INVIAS y selección de grado asfáltico Superpave PG.",
      inputs: [
        "Temperaturas medias, máximas y mínimas diarias, precipitación total y nivel freático (m) configurado en el proyecto.",
      ],
      outputs: [
        "<b>1. TMAP / w-MAAT:</b> factor térmico mensual <code>WF = 10^(-1.224 + 0.06508·T - 0.000145·T²)</code> año a año y ciclo climatológico.",
        "<b>2. PMA:</b> precipitación media anual multianual en mm/año.",
        "<b>3. Zonificación INVIAS (R1–R6):</b> asignación automática según criterios TMAP y PMA del Manual INVIAS.",
        "<b>Superpave PG (98% LTPP a 20 mm):</b> temperatura de los 7 días consecutivos más calientes, temperatura de pavimento máx/mín y recomendación PG.",
        "Exportación directa a <b>AASHTOWare MEPDG</b> (<code>.xml</code> y <code>_mepdg.txt</code>) y hoja Excel <code>Pavimentos_TMAP</code> con fórmulas dinámicas.",
      ],
      norm: "Shell Pavement Design Manual (Chart W), Manual de Diseño de Pavimentos INVIAS y FHWA LTPP / AASHTOWare MEPDG.",
    },
    {
      id: "exports_catalog",
      cat: "Exportaciones e Informes",
      icon: "📤",
      title: "Qué Genera Cada Exportación (17 Formatos)",
      subtitle: "Detalle de entregables documentales, hojas de cálculo formuladas, archivos de modelación e imágenes HD.",
      badges: ["PDF 8+ págs", "Excel 10 Hojas", "Word .docx", "SWMM / MEPDG / GIS"],
      what: "Resume exactamente el contenido generado al presionar cada botón de la pestaña 6. Informes y Exportaciones o el menú Archivo.",
      inputs: [
        "Cualquier análisis ejecutado con al menos una estación válida con series históricas.",
      ],
      outputs: [
        "<b>Informe PDF Técnico:</b> 8+ páginas tamaño A4 sin desbordamiento de tablas, incluyendo resumen TMAP/PMA, clasificaciones, balance mensual, Pettitt/Mann-Kendall, curvas IDF, hietograma RAS/INVIAS, Geotecnia SGC, RUSLE, SPEI, Cuenca y episodios críticos.",
        "<b>Informe Word (.docx):</b> documento editable completamente estructurado con tablas estilizadas y figuras incrustadas.",
        "<b>Excel Formulado (.xlsx — 10 Hojas):</b> <code>Resumen_Ejecutivo</code> (vinculado), <code>Estaciones</code>, <code>Balance_Mensual</code>, <code>Pavimentos_TMAP</code> (con fórmula Shell 10^...), <code>Serie_Anual</code>, <code>Promedios_Diarios_365</code>, <code>IDF_Frecuencia_RAS</code>, <code>Calidad_Homogeneidad_ETCCDI</code>, <code>Geotecnia_SGC_Lluvias</code> y <code>Cuenca_RUSLE_Sequias</code> con 4 gráficos nativos.",
        "<b>Modelación e Imagen:</b> CSV Hietograma (SWMM/HEC-HMS), MEPDG XML/TXT, GeoJSON/KML, Reporte TXT, proyecto <code>.hclim</code> y 7 figuras científicas PNG de alta resolución (240 DPI).",
      ],
      norm: "Estándar listo para anexar directamente a memorias de cálculo de consultoría y licitaciones.",
    },
    {
      id: "licenses_sources",
      cat: "Sistema y Soporte",
      icon: "🔓",
      title: "Licencia MIT, Datos Abiertos y Verificación",
      subtitle: "Software gratuito de código abierto, fuentes públicas oficiales y modelos de verificación numérica.",
      badges: ["Licencia MIT", "Uso Libre y Gratuito", "19 Pruebas Auto", "Windows x64"],
      what: "HidroClima Studio es software libre y gratuito bajo licencia MIT. Toda descarga en línea emplea portales públicos gubernamentales y científicos de libre acceso, sin suscripciones ni licencias comerciales.",
      inputs: [
        "Internet únicamente necesario si deseas sincronizar en vivo desde Datos Abiertos Colombia, Open-Meteo ERA5 o NASA POWER.",
      ],
      outputs: [
        "<b>Catálogo precargado:</b> 8.973 estaciones IDEAM y caso demostrativo <b>Ejemplo Bogotá D.C.</b> integrados localmente.",
        "<b>Modelos de Verificación:</b> 19 pruebas unitarias y de integración automatizadas cubriendo balance hídrico, FAO-56, TMAP Shell, IDF, Pettitt, Mann-Kendall, SGC, RUSLE, SPEI, Cuenca INVIAS y todas las exportaciones.",
        "<b>Repositorio y Soporte:</b> código fuente abierto y documentado en <code>github.com/pperillav/HidroClima-Studio</code> bajo licencia MIT.",
      ],
      norm: "Python 3.11 + FastAPI + SciPy + Pandas + Matplotlib + Apache ECharts + Leaflet + pywebview.",
    },
  ];

  let activeTopicId = "workflow";
  let callbacks = {};

  function closeMenus() {
    document.querySelectorAll(".menu-root.open").forEach((el) => el.classList.remove("open"));
  }

  function renderNav(filterText = "") {
    const q = filterText.trim().toLowerCase();
    const list = document.getElementById("helpTopicNav");
    if (!list) return;
    const filtered = HELP_TOPICS.filter((t) => {
      if (!q) return true;
      const hay = [t.title, t.subtitle, t.what, t.norm, ...(t.badges || []), ...(t.inputs || []), ...(t.outputs || [])]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    if (!filtered.length) {
      list.innerHTML = `<div class="hint" style="padding:12px">No hay coincidencias para "${filterText}".</div>`;
      return;
    }
    if (!filtered.some((t) => t.id === activeTopicId)) {
      activeTopicId = filtered[0].id;
    }
    let lastCat = "";
    list.innerHTML = filtered
      .map((t) => {
        const hdr = t.cat !== lastCat ? `<div class="help-nav-cat">${t.cat}</div>` : "";
        lastCat = t.cat;
        return `${hdr}<button type="button" class="help-nav-btn ${t.id === activeTopicId ? "active" : ""}" data-topic="${t.id}"><span>${t.icon}</span><span>${t.title}</span></button>`;
      })
      .join("");
    list.querySelectorAll(".help-nav-btn").forEach((btn) => {
      btn.onclick = () => {
        activeTopicId = btn.dataset.topic;
        renderNav(document.getElementById("helpSearchInput")?.value || "");
        renderTopic(activeTopicId);
      };
    });
  }

  function renderTopic(id) {
    const t = HELP_TOPICS.find((x) => x.id === id) || HELP_TOPICS[0];
    activeTopicId = t.id;
    const pane = document.getElementById("helpContentPane");
    if (!pane) return;

    let actionBtns = "";
    if (t.id === "workflow" || t.id === "licenses_sources") {
      actionBtns = `
        <div class="help-actions-bar">
          <button type="button" class="btn btn-sm btn-primary" data-help-act="run_cauca">▶ Cargar y Ejecutar Ejemplo Bogotá</button>
          <button type="button" class="btn btn-sm btn-secondary" data-help-act="go_exports">Ir a Exportaciones</button>
        </div>`;
    } else if (t.id === "watershed_scs" || t.id === "geotecnia_sgc") {
      actionBtns = `
        <div class="help-actions-bar">
          <button type="button" class="btn btn-sm btn-primary" data-help-act="go_geo">Abrir Cuenca INVIAS y Geotecnia SGC</button>
        </div>`;
    } else if (t.id === "pavement_tmap") {
      actionBtns = `
        <div class="help-actions-bar">
          <button type="button" class="btn btn-sm btn-primary" data-help-act="go_pav">Abrir Pavimentos (TMAP / PG)</button>
        </div>`;
    } else if (t.id === "rusle_spei") {
      actionBtns = `
        <div class="help-actions-bar">
          <button type="button" class="btn btn-sm btn-primary" data-help-act="go_spei">Abrir Sequías SPEI y Erosividad RUSLE</button>
        </div>`;
    }

    pane.innerHTML = `
      <div class="help-topic-head">
        <div class="help-topic-kicker">${t.cat}</div>
        <h2>${t.icon} ${t.title}</h2>
        <p class="help-topic-sub">${t.subtitle}</p>
        <div class="help-badges">${(t.badges || []).map((b) => `<span class="badge-info">${b}</span>`).join("")}</div>
      </div>

      <div class="help-card">
        <h4>¿Qué hace y qué calcula?</h4>
        <p>${t.what}</p>
      </div>

      <div class="help-grid-2">
        <div class="help-card">
          <h4>Datos y Parámetros Requeridos</h4>
          <ul>${t.inputs.map((x) => `<li>${x}</li>`).join("")}</ul>
        </div>
        <div class="help-card">
          <h4>Resultados y Entregables que Genera</h4>
          <ul>${t.outputs.map((x) => `<li>${x}</li>`).join("")}</ul>
        </div>
      </div>

      <div class="help-card help-norm">
        <strong>Base Normativa y Metodológica:</strong> ${t.norm}
      </div>
      ${actionBtns}
    `;

    pane.querySelectorAll("[data-help-act]").forEach((btn) => {
      btn.onclick = () => {
        const act = btn.dataset.helpAct;
        closeHelp();
        if (act === "run_cauca" && callbacks.loadAndRunCauca) callbacks.loadAndRunCauca();
        if (act === "go_exports" && callbacks.switchTab) callbacks.switchTab("tab-exports");
        if (act === "go_geo" && callbacks.openEngSubtab) callbacks.openEngSubtab("sub-eng-geo");
        if (act === "go_pav" && callbacks.openEngSubtab) callbacks.openEngSubtab("sub-eng-pav");
        if (act === "go_spei" && callbacks.openResultsSubtab) callbacks.openResultsSubtab("sub-series");
      };
    });
  }

  function openHelp(topicId = "workflow") {
    const modal = document.getElementById("helpModal");
    if (!modal) return;
    closeMenus();
    activeTopicId = topicId || activeTopicId;
    const search = document.getElementById("helpSearchInput");
    if (search) search.value = "";
    renderNav("");
    renderTopic(activeTopicId);
    modal.style.display = "flex";
  }

  function closeHelp() {
    const modal = document.getElementById("helpModal");
    if (modal) modal.style.display = "none";
  }

  function handleMenuAction(act) {
    closeMenus();
    if (!act) return;
    if (act.startsWith("help:")) {
      openHelp(act.slice(5));
      return;
    }
    const map = {
      new_project: () => callbacks.resetProject && callbacks.resetProject(),
      open_projects: () => callbacks.openProjects && callbacks.openProjects(),
      save_project: () => callbacks.saveProject && callbacks.saveProject(),
      run_analysis: () => callbacks.runAnalysis && callbacks.runAnalysis(),
      run_cauca: () => callbacks.loadAndRunCauca && callbacks.loadAndRunCauca(),
      weights_idw: () => callbacks.computeWeights && callbacks.computeWeights("idw"),
      weights_thiessen: () => callbacks.computeWeights && callbacks.computeWeights("thiessen"),
      tab_gis: () => callbacks.switchTab && callbacks.switchTab("tab-gis"),
      tab_results: () => callbacks.switchTab && callbacks.switchTab("tab-results"),
      sub_spei: () => callbacks.openResultsSubtab && callbacks.openResultsSubtab("sub-series"),
      sub_rusle: () => callbacks.openResultsSubtab && callbacks.openResultsSubtab("sub-quality"),
      sub_idf: () => callbacks.openEngSubtab && callbacks.openEngSubtab("sub-eng-idf"),
      sub_geo: () => callbacks.openEngSubtab && callbacks.openEngSubtab("sub-eng-geo"),
      sub_pav: () => callbacks.openEngSubtab && callbacks.openEngSubtab("sub-eng-pav"),
      tab_tw: () => callbacks.switchTab && callbacks.switchTab("tab-thornthwaite"),
      tab_bridge: () => callbacks.switchTab && callbacks.switchTab("tab-bridge"),
      tab_exports: () => callbacks.switchTab && callbacks.switchTab("tab-exports"),
      export_pdf: () => callbacks.runExport && callbacks.runExport("pdf"),
      export_xlsx: () => callbacks.runExport && callbacks.runExport("xlsx"),
      export_docx: () => callbacks.runExport && callbacks.runExport("docx"),
      pdf_general: () => window.open("/api/manuals/general", "_blank", "noopener"),
      pdf_tutorial: () => window.open("/api/manuals/tutorial", "_blank", "noopener"),
      pdf_scientific: () => window.open("/api/manuals/scientific", "_blank", "noopener"),
      pdf_reference: () => window.open("/api/manuals/reference", "_blank", "noopener"),
      toggle_theme: () => callbacks.toggleTheme && callbacks.toggleTheme(),
      fit_colombia: () => callbacks.fitColombia && callbacks.fitColombia(),
      toggle_idf_scale: () => callbacks.toggleIdfScale && callbacks.toggleIdfScale(),
      open_github: () => window.open("https://github.com/pperillav/HidroClima-Studio", "_blank", "noopener"),
    };
    if (map[act]) map[act]();
  }

  function init(cbMap) {
    callbacks = cbMap || {};

    document.querySelectorAll(".menu-root-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const root = btn.closest(".menu-root");
        const wasOpen = root.classList.contains("open");
        closeMenus();
        if (!wasOpen) root.classList.add("open");
      });
      btn.addEventListener("mouseenter", () => {
        if (document.querySelector(".menu-root.open")) {
          closeMenus();
          btn.closest(".menu-root").classList.add("open");
        }
      });
    });

    document.querySelectorAll("[data-menu-act]").forEach((item) => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        handleMenuAction(item.dataset.menuAct);
      });
    });

    document.querySelectorAll(".help-tip").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        openHelp(btn.dataset.help || "workflow");
      });
    });

    const closeBtn = document.getElementById("btnCloseHelpModal");
    if (closeBtn) closeBtn.onclick = closeHelp;
    const modal = document.getElementById("helpModal");
    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) closeHelp();
      });
    }
    const search = document.getElementById("helpSearchInput");
    if (search) {
      search.addEventListener("input", () => renderNav(search.value));
    }

    document.addEventListener("click", closeMenus);
    document.addEventListener("keydown", (e) => {
      if (e.key === "F1") {
        e.preventDefault();
        openHelp(activeTopicId);
      } else if (e.key === "Escape") {
        closeMenus();
        closeHelp();
      } else if (e.ctrlKey && e.key === "Enter") {
        e.preventDefault();
        if (callbacks.runAnalysis) callbacks.runAnalysis();
      }
    });
  }

  return { init, openHelp, closeHelp };
})();
