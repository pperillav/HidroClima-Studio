# Manual Técnico y Metodología de Cálculo — HidroClima Studio v1.0.0

Este documento detalla las bases matemáticas, modelos estadísticos, constantes físicas y normativas implementadas en **HidroClima Studio**, para soporte directo de memorias de cálculo, informes de consultoría vial, diseños hidráulicos y estudios ambientales.

---

## 1. Arquitectura de Series Diarias y Fusión Multi-Fuente

### 1.1 Almacenamiento Compacto `12 × 31`
Cada serie anual `(estación, variable, año, fuente)` se almacena en SQLite (modo WAL) como un vector binario comprimido (`zlib`) de **372 valores `float32`** correspondiente a una matriz fija de `12 meses × 31 días`. Los días inexistentes en calendario (p. ej., 30 de febrero) permanecen como `NaN` sin alterar los promedios ni conteos reales.

### 1.2 Jerarquía de Prioridad de Fuentes
Al consolidar múltiples fuentes para una misma estación y fecha en una serie única de análisis, el sistema fusiona en el siguiente orden de precedencia (de mayor a menor confiabilidad):

1. `Manual` (ediciones verificadas en el editor `12 × 31`)
2. `IDEAM-DHIME` (archivos oficiales descargados de DHIME)
3. `IDEAM-API` (consultas en línea vía Datos Abiertos `datos.gov.co`)
4. `Archivo-Histórico` y `IDEAM-Legacy` (bases históricas `.dat`)
5. `NASA-POWER` (reanálisis satelital diario)
6. `Open-Meteo` (reanálisis ERA5 histórico hasta la fecha actual)

---

## 2. Ponderación Espacial de Estaciones

Dado un conjunto de $k$ estaciones con coordenadas geodésicas $(\phi_i, \lambda_i)$ y un punto objetivo o polilínea de proyecto (eje de vía/corredor importado vía KML, KMZ o GeoJSON):

- **Distancia Inversa Ponderada (IDW, $p=2$):**
  Para un trazado discretizado en vértices $\{V_j\}_{j=1}^m$, la distancia característica de cada estación $i$ al corredor es $d_i = \min_j \, d_{\text{Haversine}}(E_i, V_j)$ (en km). El peso asignado es:

  $$w_i = \frac{(d_i + 0.1)^{-2}}{\sum_{r=1}^k (d_r + 0.1)^{-2}}$$

- **Polígonos de Thiessen (Voronoi discreto sobre área de estudio):**
  Se genera una grilla regular sobre la envolvente de las estaciones o el corredor vial con buffer $B$ (km). Cada celda dentro de la distancia buffer se asigna a la estación más cercana por distancia Haversine, obteniendo el peso proporcional al área cubierta: $w_i = N_{\text{celdas}, i} / N_{\text{total}}$.

---

## 3. Radiación Solar y Evapotranspiración de Referencia ($ET_0$)

### 3.1 Geometría Solar y Penman-Monteith FAO-56 (`Allen et al., 1998`)
Para una latitud $\phi$ (rad) y día juliano $J \in [1, 366]$:

$$d_r = 1 + 0.033 \cos\!\left(\frac{2\pi}{365} J\right), \qquad \delta = 0.409 \sin\!\left(\frac{2\pi}{365} J - 1.39\right)$$
$$\omega_s = \arccos(-\tan\phi \tan\delta), \qquad N = \frac{24}{\pi} \omega_s$$
$$R_a = \frac{24(60)}{\pi} G_{sc} d_r \left(\omega_s \sin\phi\sin\delta + \cos\phi\cos\delta\sin\omega_s\right), \quad G_{sc}=0.0820\ \text{MJ m}^{-2}\text{min}^{-1}$$

La radiación solar incidente $R_s$ se selecciona automáticamente por jerarquía de datos disponibles:
1. Observada / satelital directa (variable `12`).
2. **Angstrom-Prescott** desde brillo solar observado $n$ (variable `2`): $R_s = \left(0.25 + 0.50 \frac{n}{N}\right) R_a$.
3. **Hargreaves-Samani** desde amplitud térmica diaria: $R_s = k_{Rs} \sqrt{T_{\max} - T_{\min}}\, R_a$, con $k_{Rs} = 0.16$ (interior) o $0.19$ (zona costera).

Con la presión atmosférica $P = 101.3\left(\frac{293 - 0.0065 z}{293}\right)^{5.26}$ y constante psicrométrica $\gamma = 0.000665\, P$, se calcula $ET_0$ diaria (mm/día):

$$ET_0 = \frac{0.408 \Delta R_n + \gamma \frac{900}{T + 273} u_2 (e_s - e_a)}{\Delta + \gamma(1 + 0.34\, u_2)}$$

*(Si no existe registro de viento, se adopta el valor estándar FAO-56 $u_2 = 2.0\ \text{m/s}$; si el viento viene en $\text{km/día}$, se convierte multiplicando por $1000/86400$).*

### 3.2 Método de Thornthwaite (1948)
A partir de las temperaturas medias mensuales $T_m$ ($m=1\ldots 12$, truncadas en $0^\circ\text{C}$):

$$i_m = \left(\frac{T_m}{5}\right)^{1.514}, \qquad I = \sum_{m=1}^{12} i_m$$
$$a = 6.75\times 10^{-7} I^3 - 7.71\times 10^{-5} I^2 + 1.792\times 10^{-2} I + 0.49239$$

Para $T_m < 26.5^\circ\text{C}$, la ETP mensual sin corregir es $ETP_{0,m} = 16 \left(\frac{10\,T_m}{I}\right)^a$ (y polinómica estándar para $T_m \ge 26.5^\circ\text{C}$), corregida por duración astronómica del día a mitad de mes y días reales del mes:

$$ETP_m = ETP_{0,m} \cdot \left(\frac{N_m}{12}\right)\left(\frac{d_m}{30}\right)$$

---

## 4. Balance Hídrico Climatológico e Índices de Thornthwaite

El balance hídrico simula la reserva de humedad del suelo $R_m \in [0, R_{\max}]$ de manera **cíclica estacionaria** hasta converger a $R_{\text{fin}} = R_{\text{inicio}}$ (hasta 25 iteraciones):

- Si $P_m \ge ETP_m$: la reserva se recarga hasta $R_{\max}$, $ETR_m = ETP_m$, el sobrante sobre $R_{\max}$ constituye **Exceso hídrico** ($EXC_m$) y $\text{Déficit}_m = 0$.
- Si $P_m < ETP_m$: la reserva aporta $\Delta R = \min(R_{m-1},\ ETP_m - P_m)$, $ETR_m = P_m + \Delta R$, y $\text{Déficit}_m = ETP_m - ETR_m$.

Los índices anuales resultantes son:

$$I_h = 100\,\frac{\sum EXC}{ETP_{\text{anual}}}, \qquad I_a = 100\,\frac{\sum DEF}{ETP_{\text{anual}}}, \qquad I_m = I_h - 0.6\, I_a$$

---

## 5. Clasificaciones Climáticas y Bioclimáticas Oficiales

1. **Caldas-Lang (adoptada por el IDEAM):**
   - Piso térmico de Caldas según temperatura media anual $T$: Cálido ($>24^\circ\text{C}$), Templado ($17.5\text{–}24^\circ\text{C}$), Frío ($12.0\text{–}17.5^\circ\text{C}$), Páramo Bajo ($7.0\text{–}12.0^\circ\text{C}$), Páramo Alto ($<7.0^\circ\text{C}$).
   - Factor de humedad de Lang ($P_{\text{anual}} / T$): Desértico ($\le 20$), Árido ($20\text{–}40$), Semiárido ($40\text{–}60$), Semihúmedo ($60\text{–}100$), Húmedo ($100\text{–}160$) y Superhúmedo ($>160$).
2. **Zonas de Vida de Leslie R. Holdridge:**
   - Biotemperatura $T_{\text{bio}} = \frac{1}{12}\sum \mathrm{clip}(T_m,\ 0,\ 30)$.
   - Evapotranspiración potencial de Holdridge: $ETP_H = 58.93 \cdot T_{\text{bio}}$.
   - Relación de evapotranspiración potencial: $EPT = ETP_H / P_{\text{anual}}$, combinada con los pisos Tropical ($\ge 24^\circ\text{C}$), Premontano ($18\text{–}24^\circ\text{C}$), Montano Bajo ($12\text{–}18^\circ\text{C}$), Montano ($6\text{–}12^\circ\text{C}$), Subalpino ($3\text{–}6^\circ\text{C}$) y Alpino ($<3^\circ\text{C}$).
3. **Köppen-Geiger (Peel et al., 2007):** grupos `A` (Tropical `Af/Am/Aw`), `B` (Árido/Semiárido `BW/BS` con umbral $P_{\text{thresh}} = 20\,T_{\text{anual}} + 140$ mm/año), `C` (Templado `Cf/Cw`), `D` (Frío `Df/Dw`) y `E` (Polar/Alta Montaña `ET/EF`).
4. **Índice de Aridez ENA-IDEAM:**

   $$IA = \frac{ETP - ETR}{ETP}$$

   Categorías oficiales ENA: Altos excedentes ($<0.15$), Excedentes ($0.15\text{–}0.20$), Moderado y excedentes ($0.20\text{–}0.30$), Moderado ($0.30\text{–}0.40$), Moderado y deficitario ($0.40\text{–}0.50$), Deficitario ($0.50\text{–}0.60$) y Altamente deficitario ($\ge 0.60$).

---

## 6. Hidrología de Valores Extremos, Curvas IDF y Normativa RAS / INVIAS

### 6.1 Análisis de Frecuencia de $P_{24h}$ Máxima Anual
Sobre la serie de máximos diarios anuales (filtrada por completitud anual $\ge 70\,\%$), se ajustan cuatro distribuciones probabilísticas para los períodos de retorno $T_r \in \{2, 3, 5, 10, 15, 20, 25, 30, 40, 50, 100\}$ años:

- **Gumbel Tipo I** (método de momentos).
- **Log-Normal** (2 parámetros en $\log_{10} P$).
- **Log-Pearson Tipo III** (`scipy.stats.pearson3` con coeficiente de asimetría en $\log_{10} P$).
- **GEV** (Distribución Generalizada de Valores Extremos por máxima verosimilitud).

Cada ajuste se evalúa contra las posiciones empíricas de **Gringorten**, $F_i = \frac{i - 0.44}{n + 0.12}$, calculando el estadístico **Kolmogorov-Smirnov ($D$)**, su **$p$-valor** y el coeficiente **$R^2$**.

### 6.2 Cuatro Metodologías de Curvas IDF ($I$ en $\text{mm/h}$, $t$ en $\text{min}$)

1. **Regionalización INVIAS / Vargas & Díaz-Granados (1998):**

   $$I(T_r, t) = \frac{a \cdot T_r^b \cdot M^d}{(t / 60)^c}$$

   donde $M = \overline{P_{24h}}$ (mm) y los parámetros regionales oficiales son:
   - **Andina (R1):** $a=0.94,\ b=0.18,\ c=0.66,\ d=0.83$
   - **Caribe (R2):** $a=24.85,\ b=0.22,\ c=0.50,\ d=0.10$
   - **Pacífico (R3):** $a=13.92,\ b=0.19,\ c=0.58,\ d=0.20$
   - **Orinoquía-Amazonía (R4):** $a=5.53,\ b=0.17,\ c=0.63,\ d=0.42$

2. **Gustavo Silva (Desagregación $P_{24h,T_r} \rightarrow P_{1h,T_r}$):**

   $$I(T_r, t) = \frac{P_{24h}(T_r)\cdot r_{1h/24h}\cdot (60 + b)^n}{(t + b)^n}$$

   *(por defecto $r_{1h/24h}=0.48$, $b=10\ \text{min}$, $n=0.50$, configurables).*

3. **Sherman Generalizada / Local:**

   $$I(T_r, t) = \frac{k \cdot T_r^m}{(t + c)^n}$$

4. **Bell (1969) Generalizada:**

   $$P(T_r, t) = (0.21 \ln T_r + 0.52)\,(0.54\,t^{0.25} - 0.50)\, P_{60}^{10}, \qquad I(T_r, t) = \frac{P(T_r, t)}{t / 60}$$

### 6.3 Hietograma de Diseño, Normativa RAS/INVIAS y SPI
- **Método de Bloques Alternos:** descompone la lámina acumulada $P(t_k) = I(T_r, t_k)\cdot (t_k/60)$ en incrementos $\Delta t = 5\ \text{min}$, ubicando el máximo en el centro y alternando los restantes a derecha e izquierda (compatible con **EPA SWMM** y **HEC-HMS**).
- **Tabla Normativa:** evalúa automáticamente $I(t_c=15\ \text{min})$ e $I(t_c=30\ \text{min})$ para los períodos de retorno mínimos del **RAS (Resolución 0330 de 2017)** (`3, 5, 10, 50, 100 años`) y del **Manual de Drenaje para Carreteras del INVIAS** (`5, 10, 20, 25, 50–100 años`).
- **SPI-3 y SPI-12:** ajuste de distribución Gamma por mes del año sobre acumulados móviles de 3 y 12 meses, transformado a variable normal estándar $Z \in [-3.5, +3.5]$.

---

## 7. Control de Calidad, Homogeneidad y Cambio Climático

- **Prueba de Pettitt (1979):** prueba no paramétrica basada en rangos $U_t$ para detectar rupturas de homogeneidad y el año probable de cambio de media ($p < 0.05$).
- **Mann-Kendall y Pendiente de Theil-Sen:** detección no paramétrica de tendencia lineal monotónica por año y por década ($p < 0.05$ y $p < 0.10$).
- **Índices Extremos OMM / ETCCDI:** `Rx1day`, `Rx5day`, `CDD` (racha seca máx. $<1\ \text{mm}$), `CWD` (racha húmeda máx. $\ge 1\ \text{mm}$), `R10mm`, `R20mm`, `R50mm`, `SU25`, `SU32`, `TXx` y `TNn`.

---

## 8. Ingeniería de Pavimentos (TMAP, INVIAS, Superpave y MEPDG)

### 8.1 Temperatura Media Anual Ponderada (`TMAP` / `w-MAAT` — Shell / INVIAS)
A partir de la temperatura media mensual $T_m$ ($^\circ\text{C}$), el factor de ponderación térmica mensual de la **Carta W de Shell** es:

$$WF_m = 10^{\left(-1.224 + 0.06508\,T_m - 0.000145\,T_m^2\right)}$$

Promediando los 12 meses ($\overline{WF} = \frac{1}{12}\sum WF_m$), la temperatura ponderada equivalente resulta:

$$\text{TMAP} = 19.66 + 16.91\,\log_{10}(\overline{WF}) + 0.3117\,\left[\log_{10}(\overline{WF})\right]^2$$

Se calcula tanto **año a año** (para años con al menos 10 meses válidos) como sobre el **ciclo climatológico mensual** con tabla detallada de $WF_m$.

### 8.2 Regiones Climáticas para Pavimentos Asfálticos INVIAS (`R1`–`R6`)
Según la **TMAP** ($^\circ\text{C}$) y la precipitación media anual **PMA** ($\text{mm}$):

| Región | Criterio Climático | Descripción INVIAS |
| :---: | :--- | :--- |
| **`R1`** | $\text{TMAP} < 13^\circ\text{C}$, $\text{PMA} < 2.000\ \text{mm}$ | Fría seca y fría semihúmeda *(equiv. R1-H si PMA $\ge 2.000\ \text{mm}$)* |
| **`R2`** | $13 \le \text{TMAP} \le 20^\circ\text{C}$, $\text{PMA} < 2.000\ \text{mm}$ | Templado seco y templado semihúmedo |
| **`R3`** | $\text{TMAP} > 20^\circ\text{C}$, $\text{PMA} < 2.000\ \text{mm}$ | Cálido seco y cálido semihúmedo |
| **`R4`** | $13 \le \text{TMAP} \le 20^\circ\text{C}$, $\text{PMA} \ge 2.000\ \text{mm}$ | Templado húmedo |
| **`R5`** | $\text{TMAP} > 20^\circ\text{C}$, $2.000 \le \text{PMA} \le 4.000\ \text{mm}$ | Cálido húmedo |
| **`R6`** | $\text{TMAP} > 20^\circ\text{C}$, $\text{PMA} > 4.000\ \text{mm}$ | Cálido muy húmedo |

### 8.3 Superpave PG (LTPP a 20 mm, Confiabilidad 98 %)
Tomando la temperatura media de los **7 días consecutivos más calientes** ($\overline{T}_{\text{air,7d}}$, desviación $\sigma_{\text{7d}}$) y la mínima extrema de 1 día ($\overline{T}_{\text{min,1d}}$):

$$T_{\text{pav,máx}}(20\text{ mm}) = 54.32 + 0.78\,\overline{T}_{\text{air,7d}} - 0.0025\,\phi^2 - 15.14\log_{10}(20 + 25) + 2.055\sqrt{9.0 + 0.61\,\sigma_{\text{7d}}^2}$$
$$T_{\text{pav,mín}}(20\text{ mm}) = -1.56 + 0.72\,\overline{T}_{\text{min,1d}} - 0.004\,\phi^2 + 6.26\log_{10}(20 + 25) - 2.055\sqrt{4.4 + 0.52\,\sigma_{\text{min}}^2}$$

Los límites se redondean hacia arriba/abajo al catálogo estándar PG (`PG 46, 52, 58, 64, 70, 76, 82` y `-10, -16, -22, -28, -34, -40, -46`).

---

## 9. Geotecnia SGC: Umbrales de Lluvias Detonantes e Infiltración SCS-CN

Siguiendo las guías metodológicas del **Servicio Geológico Colombiano (SGC)** para amenaza por movimientos en masa inducidos por precipitación:

- **Ventanas móviles antecedentes:** se calculan diariamente las láminas acumuladas $R_1$ (24 h), $R_3$, $R_7$, $R_{15}$, $R_{30}$ y $R_{90}$ días, reportando sus cuantiles (`P90`, `P95`, `P99`) y máximos históricos con fecha exacta.
- **Umbral empírico combinado (`Moreno et al. / SGC`):** relación entre la lluvia detonante reciente $R_3$ (últimos 3 días) y la lluvia antecedente previa $R_{15,\text{ant}}$ (los 15 días inmediatamente anteriores a la ventana $R_3$):

$$R_{3,\text{crít}} = \max\left(5,\ a - b \cdot R_{15,\text{ant}}\right)$$

  *(con parámetros base configurables $a = 70.0\ \text{mm}$ y $b = 0.47$, filtrando días húmedos con $R_1 \ge 1\ \text{mm}$ y agrupando excedencias cercanas en episodios independientes).*

- **Ajuste hidrológico antecedente (`SCS-CN`):** a partir de $CN_{II}$, se derivan los números de curva secos ($CN_I$) y saturados ($CN_{III}$), la retención máxima $S = \frac{25400}{CN_{II}} - 254$ (mm), la abstracción inicial $I_a = 0.2\,S$ y el balance medio anual de infiltración potencial frente a escorrentía directa diaria.

---

## 10. Erosividad Pluvial (RUSLE / EIA ANLA)

Para caracterización de erosión hídrica en **Estudios de Impacto Ambiental (ANLA)** y soporte del Factor $R$ en **RUSLE** con registros mensuales medios $p_m$ ($m=1\ldots 12$) y $P = \sum p_m$:

- **Índice de Fournier ($FI$) y Fournier Modificado ($MFI$, Arnoldus 1980):**

$$FI = \frac{\max(p_m)^2}{P}, \qquad MFI = \frac{\sum_{m=1}^{12} p_m^2}{P}$$

- **Índice de Concentración de Precipitación ($PCI$, Oliver 1980):**

$$PCI = 100 \cdot \frac{\sum_{m=1}^{12} p_m^2}{P^2}$$

- **Factor de Erosividad Pluvial $R$ ($\text{MJ}\cdot\text{mm}/(\text{ha}\cdot\text{h}\cdot\text{año})$, Renard & Freimund 1994):**

$$R = \begin{cases} 0.7397 \cdot MFI^{1.847}, & MFI < 55\ \text{mm} \\ 95.77 - 6.081 \cdot MFI + 0.4770 \cdot MFI^2, & MFI \ge 55\ \text{mm} \end{cases}$$

---

## 11. Sequías Hidrometeorológicas (`SPEI-3`, `SPEI-12` e `IAP` IDEAM)

- **SPEI (`Vicente-Serrano et al., 2010`):** sobre el balance climático mensual $D_m = P_m - ET_{0,m}$, se acumulan ventanas móviles de $k \in \{3, 12\}$ meses, se ajusta cada mes calendario mediante distribución **Log-Logística de 3 parámetros (`Fisk`)** y se transforma a variable normal estandarizada $Z \in [-3.5, +3.5]$, evaluando las frecuencias bajo los umbrales de sequía moderada ($\le -1.0$), severa ($\le -1.5$) y extrema ($\le -2.0$).
- **Índice de Anomalías de Precipitación (`IAP %` IDEAM):** compara la precipitación de cada año contra la precipitación media multianual ($\text{IAP} = 100 \cdot P_i / \overline{P}$) para identificar años Niño/Niña.

---

## 12. Hidráulica de Cuenca Hidrográfica (INVIAS / Racional / SCS)

Para transformación lluvia–escorrentía en drenaje vial (`Manual de Drenaje INVIAS`):

- **Tiempo de concentración ($t_c$, mín. 5 min):**
  - **Kirpich (1940):** $t_c = 0.01947 \cdot L^{0.77} \cdot S^{-0.385}$ ($L$ en m, $S$ en m/m).
  - **Témez (1978):** $t_c = 60 \cdot 0.3 \cdot \left(\frac{L_{\text{km}}}{S^{0.25}}\right)^{0.76}$.
- **Caudal Pico Método Racional:** interpolando la intensidad $I(T_r, t_c)$ directamente sobre la familia IDF seleccionada:

$$Q = \frac{C \cdot I(T_r, t_c) \cdot A}{3.6} \quad [\text{m}^3/\text{s}]$$

- **Escorrentía Directa e Hidrograma Unitario Triangular SCS:**

$$Q_e = \frac{(P_{\text{torm}} - I_a)^2}{P_{\text{torm}} - I_a + S}, \qquad q_{\text{SCS}} = \frac{0.208 \cdot A \cdot Q_e}{t_p}$$

---

## 13. Referencias Bibliográficas y Normativas

1. **RAS — Ministerio de Vivienda, Ciudad y Territorio.** *Resolución 0330 de 2017: Reglamento Técnico del Sector de Agua Potable y Saneamiento Básico*. Colombia.
2. **INVIAS.** *Manual de Drenaje para Carreteras*. Instituto Nacional de Vías, Colombia.
3. **INVIAS.** *Manual de Diseño de Pavimentos Asfálticos en Vías con Medios y Altos Volúmenes de Tránsito*. Instituto Nacional de Vías, Colombia.
4. **Vargas, R. & Díaz-Granados, M. (1998).** *Curvas Sintéticas Regionalizadas de Intensidad-Duración-Frecuencia para Colombia*. Universidad de los Andes.
5. **Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998).** *Crop Evapotranspiration — Guidelines for Computing Crop Water Requirements (FAO Irrigation and Drainage Paper 56)*.
6. **IDEAM.** *Estudio Nacional del Agua (ENA)* y *Atlas Climatológico de Colombia* (Caldas-Lang, Índice de Aridez).
7. **Thornthwaite, C. W. (1948).** *An Approach toward a Rational Classification of Climate*. Geographical Review, 38(1), 55–94.
8. **Holdridge, L. R. (1967).** *Life Zone Ecology*. Tropical Science Center, San José, Costa Rica.
9. **Peel, M. C., Finlayson, B. L., & McMahon, T. A. (2007).** *Updated world map of the Köppen-Geiger climate classification*. HESS, 11, 1633–1644.
10. **Pettitt, A. N. (1979).** *A Non-Parametric Approach to the Change-Point Problem*. Applied Statistics, 28(2), 126–135.
11. **Shell International Petroleum / FHWA LTPP.** *Shell Pavement Design Manual (Chart W)* y *Superpave Bind Grade Temperature Models*.
12. **Servicio Geológico Colombiano (SGC).** *Guía Metodológica para Estudios de Amenaza, Vulnerabilidad y Riesgo por Movimientos en Masa* y umbrales de lluvia antecedente (`Moreno et al. / Aristizábal`).
13. **Arnoldus, H. M. J. (1980) & Renard, K. G., Freimund, J. R. (1994).** *Using monthly precipitation data to estimate the R-factor in the revised USLE*. Journal of Hydrology, 157, 287–306.
14. **Vicente-Serrano, S. M., Beguería, S., & López-Moreno, J. I. (2010).** *A Multiscalar Drought Index Sensitive to Global Warming: The Standardized Precipitation Evapotranspiration Index (SPEI)*. Journal of Climate, 23(7).
