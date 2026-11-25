# Guía de Usuario — HidroClima Studio v1.0.0

Bienvenido a **HidroClima Studio**. Esta guía explica el flujo completo desde la instalación hasta la generación de informes técnicos y archivos para modelación externa.

---

## 1. Primeros Pasos e Instalación

1. Ejecuta **`HidroClimaStudio-Setup-1.0.0.exe`** y sigue el asistente de instalación.
   - Si no cuentas con permisos de administrador, conserva la ruta sugerida en tu perfil de usuario (`%LOCALAPPDATA%\Programs\HidroClima Studio`).
2. Abre el programa desde el acceso directo del **Escritorio** o el **Menú Inicio → HidroClima Studio** (donde también encontrarás los **4 Manuales Oficiales PDF**).
3. Al iniciar por primera vez, el catálogo nacional precargado (**8.973 estaciones**) y el proyecto demostrativo **Ejemplo Bogotá D.C.** se inicializan automáticamente en segundo plano sin requerir conexión a internet.
4. En cualquier momento presiona **`F1`** o usa el menú superior **`Ayuda → Documentación`** para consultar el Centro de Ayuda interactivo, ecuaciones científicas, modelos de verificación y manuales PDF.

> **Nota sobre ubicación de datos:** en modo instalado, la base de datos `hidroclima.db` se guarda en `%LOCALAPPDATA%\HidroClimaStudio\data\`, garantizando que tus series descargadas, ediciones manuales y proyectos permanezcan intactos ante futuras actualizaciones del programa.

---

## 2. Flujo de Trabajo Recomendado

### Paso 1 — Búsqueda Geoespacial o por Corredor de Estudio
En el panel izquierdo (**Selección Espacial**):
- Filtra estaciones por **Departamento**, **Municipio**, **Categoría**, **Estado** o código/nombre.
- Activa *"Solo estaciones con series cargadas"* si deseas explorar rápidamente las estaciones ya sincronizadas.
- **Análisis por Ruta / Corredor:** sube un archivo **KML, KMZ o GeoJSON** (o dibuja puntos directamente sobre el mapa) y define un **Radio / Buffer (km)** para listar todas las estaciones dentro del área de influencia del proyecto.

### Paso 2 — Selección y Ponderación de Estaciones
- Haz clic en **Agregar** sobre las estaciones que conformarán tu proyecto multipunto.
- Elige el método de ponderación espacial automático:
  - **IDW:** ideal cuando varias estaciones rodean un corredor vial o punto de diseño.
  - **Thiessen:** proporcional al área de influencia dentro del polígono o corredor.
  - **Igual / Manual:** permite asignar porcentajes personalizados que sumen `100 %`.

### Paso 3 — Actualización y Carga de Datos (Puentes en Vivo e Importadores)
En la pestaña o modal **Puentes de Datos**:
1. **Datos Abiertos (`datos.gov.co`) + Open-Meteo ERA5 + NASA POWER:**
   - Selecciona las estaciones del proyecto y el rango de años deseado y presiona **Sincronizar**.
   - Si una estación convencional no reporta en tiempo real, el puente consulta automáticamente la estación automática cercana (`- AUT`) o completa las variables faltantes desde Open-Meteo ERA5 / NASA POWER.
2. **Importar DHIME (`.csv` / `.xlsx`):**
   - Arrastra o selecciona archivos descargados directamente desde el portal DHIME del IDEAM.
3. **Importar Paquetes Históricos (`.zip`, `.rar`, `SHC/*.dat`, `.hclim`):**
   - Puedes importar selectivamente solo las estaciones de tu proyecto o el archivo completo con barra de progreso en vivo.
4. **Editor Diario `12 × 31`:**
   - Permite consultar, corregir o ingresar manualmente datos diarios de cualquiera de las 12 variables soportadas; toda edición queda marcada con fuente `Manual` (máxima prioridad).

### Paso 4 — Configuración del Análisis y Ejecución
Configura los parámetros del panel principal:
- **Perfil de Estudio:** *Integral*, *Hidrología y Drenaje (IDF / RAS)*, *Ambiental (EIA ANLA / RUSLE)*, *Geotecnia SGC y Taludes* o *Pavimentos (TMAP / PMA / Superpave)*.
- **Ventana Temporal:** año final y ventana multianual (p. ej., últimos 10 o 20 años).
- **Método de ETP:** *Penman-Monteith FAO-56* o *Thornthwaite (1948)*.
- **Reserva Máxima de Agua en el Suelo ($R_{\max}$)** (por defecto `100 mm`) y **Nivel Freático ($m$)**.
- **Metodología IDF y Cuenca/Geotecnia:** *INVIAS Regionalizado* (`Andina`, `Caribe`, `Pacífico`, `Orinoquía`), *Gustavo Silva*, *Sherman* o *Bell*, además de parámetros geomorfológicos de **Cuenca Hidrográfica** (`Área`, `Longitud L`, `Pendiente S`, `CN II`, `C`) y envolvente **SGC** (`a`, `b`).

Haz clic en **Ejecutar Análisis** para actualizar al instante todas las pestañas de resultados.

---

## 3. Interpretación de Pestañas y Exportación

- **2. Climatología, Sequías y RUSLE:** climograma anual, balance hídrico, series históricas, monitoreo de sequías **SPEI-3 / SPEI-12** (`D = P - ET0`), anomalías anuales **IAP (%) IDEAM**, prueba de **Pettitt**, **Mann-Kendall**, **ETCCDI** y módulo completo de **Erosividad Pluvial RUSLE (MFI, PCI y Factor R)**.
- **3. Hidrología IDF, Cuenca SGC y Pavimentos:** organizada en tres subpestañas especializadas:
  - *Curvas IDF, Hietograma y RAS/INVIAS:* ajuste de frecuencias $P_{24h}$ (**Gumbel**, **Log-Normal**, **LP-III**, **GEV**) con mejor ajuste K-S, curvas IDF con modo Log-Log, hietograma de diseño y cumplimiento **RAS Res. 0330/2017** / **INVIAS**.
  - *Cuenca INVIAS/SCS y Geotecnia SGC:* calculadora instantánea de **tiempos de concentración** (`Kirpich` y `Témez`), **caudales Racional y SCS**, escorrentía/infiltración y análisis completo **SGC** de lluvia antecedente (`R1..R90`), episodios históricos detonantes y gráfica de envolvente empírica `R15_ant vs R3`.
  - *Pavimentos (1. TMAP · 2. PMA · Superpave PG):* **TMAP (Shell Carta W)** año a año y climatológico, **PMA**, región **INVIAS (`R1`–`R6`)**, 7 días calientes y grado **Superpave PG**.

Usa la pestaña **6. Informes y Exportaciones** para descargar al instante **PDF técnico**, **Word (`.docx`)**, **Excel (`.xlsx` de 10 hojas formuladas)**, **Hietograma CSV (SWMM / HEC-HMS)**, **MEPDG (`.xml` / `_mepdg.txt`)**, **GeoJSON**, **KML**, **Reporte.txt**, **`.hclim`** y **7 gráficas PNG HD (240 DPI)**.
