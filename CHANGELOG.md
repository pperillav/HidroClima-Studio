# Registro de Cambios (Changelog)

Todos los cambios relevantes de **HidroClima Studio** se documentan en este archivo siguiendo [Semantic Versioning](https://semver.org/).

## [1.0.0] — Versión Inicial

### Agregado
- **Interfaz gráfica de escritorio** profesional (`pywebview` / Chromium App) con **barra de menús clásica (`Archivo · Análisis · Datos · Ver · Ayuda F1`)**, submenús en cascada, **Centro de Ayuda interactivo** y logotipo vectorial propio, junto a mapa SIG (**Leaflet** + *MarkerCluster*, OSM / ESRI Satélite / Topográfico) y gráficas (**Apache ECharts**).
- **Suite de 4 Manuales Oficiales en PDF** (`docs/manuals/`) integrados en el menú Ayuda y accesos directos de Windows (`01 Información General`, `02 Tutorial y Casos`, `03 Manual Científico con Ecuaciones` y `04 Referencia y Verificación`).
- **Catálogo nacional integrado** de **8.973 estaciones** en **33 departamentos** y **1.121 municipios**, con proyecto demostrativo multipunto y corredor de ejemplo en **Bogotá D.C.** (`El Dorado – Cerros Orientales`).
- **Ponderación espacial** de estaciones mediante **IDW** ($p=2$), **Polígonos de Thiessen** o asignación manual, además de filtrado espacial por radio y trazado/carga de corredores **KML, KMZ y GeoJSON**.
- **Puentes de datos multi-fuente:**
  - Sincronización en línea con **Datos Abiertos Colombia (`datos.gov.co`)** incluyendo el flujo en tiempo real `57sv-p2fu` y detección automática de estaciones automáticas cercanas (`- AUT`).
  - Reanálisis satelital y actualización diaria mediante **Open-Meteo ERA5** y **NASA POWER**.
  - Importación directa de descargas **IDEAM DHIME** (`.csv` / `.xlsx`) y paquetes históricos comprimidos (`.zip`, `.rar`, `SHC/*.dat`, `.hclim`/`.cli`).
  - Editor interactivo diario matriz `12 × 31` con almacenamiento compacto en SQLite (WAL).
- **Climatología, balance hídrico y estudios ambientales:**
  - Evapotranspiración de referencia ($ET_0$) por **Penman-Monteith FAO-56** (radiación observada, Angstrom-Prescott desde brillo solar o Hargreaves-Samani) y **Thornthwaite (1948)**.
  - Simulación de balance hídrico cíclico con cálculo de $ETR$, exceso, déficit e índices hídricos ($I_h, I_a, I_m$).
  - Clasificaciones oficiales: **Caldas-Lang**, **Zonas de Vida de Holdridge**, **Köppen-Geiger**, **Índice de Aridez ENA-IDEAM** y **Thornthwaite**.
  - **Erosividad Pluvial RUSLE (ANLA EIA):** Índice de Fournier clásico ($FI$), **Fournier Modificado ($MFI$, Arnoldus)**, **PCI (Oliver)**, **Factor $R$ (Renard & Freimund)** y reparto mensual porcentual.
  - **Sequías e Hiper-humedad:** **SPEI-3 / SPEI-12** (`D = P - ET0` ajustado por distribución Log-Logística) e **IAP (%) anual IDEAM**, además de prueba de homogeneidad de **Pettitt (1979)**, tendencias **Mann-Kendall / Theil-Sen** e índices extremos **ETCCDI**.
- **Hidrología de extremos, curvas IDF y cuenca hidrográfica:**
  - Ajuste de máximos anuales $P_{24h}$ mediante **Gumbel Tipo I**, **Log-Normal**, **Log-Pearson III** y **GEV**, con evaluación **Kolmogorov-Smirnov** y $R^2$.
  - Cuatro metodologías IDF: **INVIAS Regionalizado** (Andina, Caribe, Pacífico, Orinoquía), **Gustavo Silva**, **Sherman** y **Bell**, con modo Log-Log interactivo.
  - **Hietograma de Bloques Alternos**, tabla de cumplimiento normativo **RAS Res. 0330/2017** e **INVIAS Drenaje**, e índices **SPI-3 / SPI-12**.
  - **Cuenca Hidrográfica (INVIAS / SCS-CN):** tiempos de concentración **Kirpich** y **Témez**, caudales pico **Método Racional** y **SCS Triangular**, escorrentía directa $Q_e$ e infiltración potencial $F$.
- **Geotecnia SGC (Movimientos en Masa):**
  - Lluvias acumuladas móviles (`R1`, `R3`, `R7`, `R15`, `R30`, `R90`), umbral empírico combinado $R_3 \ge \max(5, a - b \cdot R_{15,\text{ant}})$, episodios históricos críticos y balance diario de infiltración **SCS (`CN I/II/III`)**.
- **Ingeniería de pavimentos:**
  - Cálculo de **Temperatura Media Anual Ponderada (`TMAP` / `w-MAAT`)** según factores térmicos mensuales de la **Carta W de Shell** (anual y ciclo climatológico) y clasificación automática en las regiones climáticas del **INVIAS (`R1` a `R6`)**.
  - Temperatura media de los **7 días consecutivos más calientes**, grado asfáltico **Superpave PG** (98 % LTPP a 20 mm) y parámetros para **AASHTOWare MEPDG**.
- **Motor de exportación completo (17 formatos):** informes **PDF**, **Word (`.docx`)**, **Excel (`.xlsx`)** de **10 hojas formuladas** y gráficos nativos, **Hietograma CSV** (SWMM/HEC-HMS), **MEPDG XML/TXT**, **GeoJSON**, **KML**, **TXT**, proyecto **`.hclim`** y **7 figuras PNG científicas de alta resolución (`240 DPI`)**.
- **Empaquetado profesional para Windows:** instalador estándar **`Setup.exe`** mediante **Inno Setup 6** (`installer/setup.iss` + `build_installer.py`) y paquete portable `.zip` (`build_portable.py`).
