# Memoria de contexto — Proyecto "Submitals ES" (Bodega Desamparados)

> Documento de traspaso para continuar el trabajo en otra conversación. Resume qué se hizo, el estado actual de los archivos y **cómo funciona en detalle** `generate_caratulas.py`.

---

## 1. Contexto del proyecto

- **Empresa:** ES Consultoría y Construcción S.A. (ES Constructora). Usuaria: Diana Solís.
- **Obra:** Bodega para la Municipalidad de Desamparados (Costa Rica).
- **Objetivo global:** armar los *submittals* (fichas técnicas de materiales para aprobación) a partir del presupuesto de la obra. Para cada material se necesita una carpeta con su ficha técnica y una **carátula** PDF de portada estandarizada.
- **Carpeta base de trabajo (Windows):** `C:\Users\castr\Downloads\Submitals ES`
- **Moneda del presupuesto:** colones costarricenses (₡). Precios sin IVA.

---

## 2. Origen de los datos

Partió del Excel `Presupuesto Bodega desamparados.xlsx`, hoja **"Presupuesto Sobre cotizaciones"**. De ahí se extrajeron **solo materiales físicos** (se excluyó mano de obra, demoliciones, laboratorio, topografía, fletes, dirección técnica, seguros, limpieza e indirectos).

Cada material se clasificó en 3 disciplinas:
- **ARQ** = Arquitectónicos
- **EST / ESTR** = Estructurales
- **MEC** = Mecánicos

---

## 3. Estructura de carpetas (estado actual)

Dentro de `C:\Users\castr\Downloads\Submitals ES` hay 3 **carpetas madre**:

- `ARQUITECTONICOS\` → subcarpetas `ARQ01…ARQ18`
- `ESTRUCTURALES\` → subcarpetas `ESTR01…ESTR33`
- `MECANICOS\` → subcarpetas `MEC01…MEC19`

**Total: 70 subcarpetas de material.** Formato de nombre de subcarpeta: `XX##-NOMBRE DEL MATERIAL` (ej. `ARQ07-CUBIERTA BANDEJA BLP-250 CAL.24 C-AISLANTE PIR`).

### Reglas de nomenclatura importantes
- Los consecutivos se renumeran **sin huecos** dentro de cada carpeta madre y **agrupados por familia** (numeración continua, no reinicia por familia).
- **Medidas normalizadas** en los nombres: se muestran en mm y su equivalente en pulgadas; el espesor siempre con un decimal en mm. Ejemplos:
  - `THN 100x150x2.4 (4"x6"x2.4mm)`
  - `ANGULAR 50x50x3.2 (2"x2"x3.2mm)`
  - `TUBO PVC 100MM (4") SDR 26`
- **En nombres de carpeta** el símbolo de pulgada `"` se reemplaza por `in` (Windows no permite `"` en nombres de archivo). En el Excel sí aparece el `"` correcto. Igual, `/` se reemplaza por `-`.

### Familias por carpeta madre
- **ARQUITECTONICOS:** Mampostería; Muro seco y paneles; Pinturas y recubrimientos; Láminas y cubiertas; Puertas y cerrajería; Ventanería y vidrio; Únicos.
- **ESTRUCTURALES:** Cementos y concretos; Acero de refuerzo; Pernería y anclajes; Tubo estructural THN; Perfil RT; Angulares; Pletinas; Juntas y sellos.
- **MECANICOS:** Tubería PVC; Accesorios PVC; Únicos.

---

## 4. Archivos clave en `Submitals ES`

| Archivo | Qué es |
|---|---|
| `generate_caratulas.py` | Script principal que genera las carátulas PDF. (Ver sección 6 en detalle.) |
| `template_caratula.html` | Plantilla HTML (Jinja2) de la carátula. |
| `datos_materiales.json` | Datos de los 70 materiales (entrada del script). |
| `Guía Materiales.xlsx` | Índice de materiales en Excel (3 hojas). |
| `Tabla visual refresh\assets\logo_es_crop.png` | Logo de ES usado en la carátula. |
| `generate_caratulas.log` | Log de la última corrida del script. |
| `generate_caratulas_report.txt` | Reporte resumen de la última corrida. |

---

## 5. La plantilla `template_caratula.html`

- Es **HTML puro** (se convirtió desde una plantilla de Claude Design; se eliminaron `<x-dc>`, `<helmet>`, `support.js`).
- Tamaño carta (816×1056 px), color de acento fijo **`#E11D2D`** (rojo ES) y azul institucional `#1F3864`. Fuentes Google: Archivo y Public Sans. Usa flexbox y **grid** (por eso el motor de PDF debe soportarlos bien).
- Contiene **variables Jinja2** que el script rellena:
  - `{{ logo_path }}` — ruta del logo en formato `file:///...`
  - `{{ consecutivo }}` — ej. `ARQ01`
  - `{{ nombre_comercial }}` — nombre del material
  - `{{ fabricante }}` — marca/distribuidor
  - `{{ descripcion_tecnica }}` — descripción breve
- Campos que quedan **vacíos** a propósito (se llenan a mano después de imprimir): *Normativa / Especificación aplicable*, *Documentación técnica adjunta*, *Observaciones adicionales*.

---

## 6. `generate_caratulas.py` — CÓMO FUNCIONA (detallado)

> Este es el punto más importante para evitar confusiones. El script **NO** lee las fichas técnicas ni el presupuesto: solo toma los datos ya preparados en `datos_materiales.json`, los mete en la plantilla y produce un PDF de carátula por material.

### 6.1 Entrada: `datos_materiales.json`
Estructura: un objeto con `resumen` (opcional) y un array `materiales`. Cada material tiene **7 campos obligatorios**:

```json
{
  "consecutivo": "ARQ01",
  "nombre": "BLOCK CONCRETO 15x20x40 CM",
  "marca": "PRODUCTOS DE CONCRETO",
  "descripcion": "Descripción técnica breve (máx 200 car.)",
  "estado": "FICHA_DISPONIBLE",
  "carpeta_vacia": false,
  "ruta_carpeta": "C:\\Users\\castr\\Downloads\\Submitals ES\\ARQUITECTONICOS\\ARQ01-BLOCK CONCRETO 15x20x40 CM"
}
```

- `estado` puede ser: `FICHA_DISPONIBLE`, `CARPETA_VACÍA`, `FICHA_INCOMPLETA`.
- `carpeta_vacia`: `true`/`false`. **Es la bandera que decide si se procesa o se salta.**
- El script acepta el JSON como `{"materiales": [...]}` o como un array directo.

### 6.2 Mapeo de campos JSON → variables de la plantilla
Esto es clave y suele confundir: **los nombres NO son iguales**. El script traduce:

| Campo en JSON | Variable en la plantilla |
|---|---|
| `nombre` | `nombre_comercial` |
| `marca` | `fabricante` |
| `descripcion` | `descripcion_tecnica` |
| `consecutivo` | `consecutivo` |
| (calculado) | `logo_path` |

`logo_path` NO viene del JSON: el script toma `LOGO_PATH` (el PNG en `Tabla visual refresh\assets`) y lo convierte a `file:///...` con los espacios codificados (`Submitals%20ES`).

### 6.3 Flujo general (`main`)
1. **Validaciones críticas** (si fallan, DETIENE todo con nivel `CRITICAL` y escribe el reporte):
   - Existe el directorio base.
   - Está instalado `jinja2`.
   - Hay al menos un motor de PDF disponible.
   - El JSON existe y es válido (si no, reporta la línea del error).
   - La plantilla existe y no está vacía/corrupta.
   - El logo existe en disco.
2. Recorre cada material y llama a `process_material`.
3. Al final escribe el **reporte** y un **resumen** en el log.

### 6.4 Lógica por material (`process_material`) — orden exacto
1. Verifica que estén los 7 campos obligatorios; si falta alguno → cuenta como *incompleta* y sale.
2. **Si `carpeta_vacia == True` → SALTA** (log `[SALTADO] carpeta vacia`). No genera PDF.
3. Si `estado != "FICHA_DISPONIBLE"` → SALTA como *ficha incompleta / estado inválido*.
4. Si algún campo de texto (`consecutivo`, `nombre`, `marca`, `descripcion`) está vacío → SALTA como *incompleta*.
5. Resuelve `ruta_carpeta` (si es relativa la vuelve absoluta bajo la base; si la carpeta no existe la crea; valida permiso de escritura).
6. **MODO INCREMENTAL (agregado más reciente):** busca en la carpeta cualquier PDF cuyo nombre empiece por `CARATULA` (insensible a mayúsculas). **Si ya existe una carátula, SALTA** esa carpeta (log `[SALTADO] ya tiene caratula: <archivo>`, se cuenta en `existentes`). Esto permite ir agregando fichas poco a poco y volver a correr el script sin regenerar lo ya hecho.
7. Trunca la descripción a 200 caracteres (corta en el último punto/espacio y agrega `...`; lo registra).
8. Renderiza la plantilla con Jinja2 usando el mapeo de 6.2.
9. Arma el nombre de salida: `CARATULA <consecutivo>-<nombre>.pdf`, saneando caracteres inválidos de Windows (`" → in`, `/ → -`, etc.).
10. Convierte a PDF probando los motores en orden hasta que uno funcione.
11. **Verifica integridad** del PDF (existe, pesa >0, abre con pypdf o al menos tiene cabecera `%PDF`/`%%EOF`). Si es inválido, borra y reintenta con otro motor; si aun así falla, lo elimina y lo marca como error.
12. Si todo bien → cuenta como `ok` y guarda el PDF en la carpeta del material.

**Importante:** la carátula se arma **solo con los datos del JSON**, no necesita que la ficha técnica esté físicamente en la carpeta. La ficha técnica es un documento aparte que acompaña a la carátula.

### 6.5 Motores de render (orden de preferencia)
Definidos en `available_engines()`. Se usa el **primero disponible** y, si falla en tiempo de ejecución, cae al siguiente:
1. **playwright** (Chromium headless) — **RECOMENDADO en Windows.** Renderiza idéntico a Chrome (respeta flexbox, grid, colores y fuentes). No requiere librerías del sistema ni permisos de admin.
2. **weasyprint** — en Windows suele fallar porque necesita las librerías GTK (dio el error "could not import some external libraries").
3. **pdfkit** — necesita el binario externo **wkhtmltopdf** en el PATH (o fijar `WKHTMLTOPDF_PATH` en el script). Sin ese binario da "No wkhtmltopdf executable found".

Config del PDF: tamaño **Letter**, márgenes 0, fondos activados (`print_background`), DPI 300 (en los motores que lo aceptan).

### 6.6 Manejo de errores y auto-corrección
- **Críticos** (detienen todo): JSON inválido, plantilla corrupta, logo no encontrado, sin motor, sin librerías.
- **No críticos** (saltan el material y continúan): carpeta no accesible, error de Jinja2, error de PDF, PDF corrupto.
- **Auto-corrige:** rutas relativas → absolutas; crea la carpeta si no existe; sanea caracteres inválidos del nombre; codifica espacios en la ruta del logo; trunca descripciones largas.

### 6.7 Logging y reporte
- **Log** `generate_caratulas.log` con formato `[TIMESTAMP] [NIVEL] [CONSECUTIVO] [MENSAJE]`. Niveles: INFO (éxitos), WARNING (saltados), ERROR (fallos por material), CRITICAL (detiene todo).
- **Reporte** `generate_caratulas_report.txt` con estadísticas (total, vacías, incompletas, procesados, **saltados por ya tener carátula**, PDFs OK, fallidos, críticos), y listados de: carpetas vacías, fichas incompletas, saltados con carátula existente, y errores no críticos.

### 6.8 Cómo se ejecuta (en Windows)
Instalación única:
```
pip install jinja2 pypdf playwright
python -m playwright install chromium
```
Correr:
```
cd "C:\Users\castr\Downloads\Submitals ES"
python generate_caratulas.py
```
Opcional: `python generate_caratulas.py --json otro_archivo.json`.

Para **forzar** la regeneración de una carátula: borrar ese PDF de la carpeta y volver a correr.

---

## 7. `Guía Materiales.xlsx`

Tres hojas: **Arquitectónicos**, **Estructurales**, **Mecánicos**. Columnas:
`Consecutivo | Familia | Descripción | Estado`

- `Estado` = **FALTANTE** (carpeta vacía, en rojo), **DISPONIBLE** (verde), **INCOMPLETA**.
- La columna `Descripción` muestra la descripción técnica cuando hay ficha, o el nombre normalizado del material cuando falta.
- Nota: el archivo puede quedar bloqueado si está abierto en Excel; en ese caso se guardó una copia `Guía Materiales (actualizada).xlsx`.

---

## 8. Estado actual de los materiales (última revisión)

De **70 materiales**:
- **35 con ficha DISPONIBLE** (`carpeta_vacia: false`, `estado: FICHA_DISPONIBLE`).
- **35 con carpeta VACÍA / FALTANTE** (fichas pendientes de solicitar).
- **0 incompletas.**

Marcas detectadas en las disponibles: Holcim (cemento y baldosas táctiles), ArcelorMittal (alambre), MultiGroup (costaneras/RT), Wavin y Amanco Wavin (tubería y conexiones PVC), Engepoli (Skylux y extractor Exhaust), Design Hardware (barra antipánico, llavín KIL, bisagras BB5, cierrapuertas 316R), Mesker (puerta de emergencia), USG/Durock, Goltex, Sur. Quedaron con marca **"POR DEFINIR"** (ficha legible pero sin marca explícita): muro seco (repello MPR 150M), cubierta BLP-250, tuberías PVC MEC01–04 y los tubos THN (ESTR15/17/22).

3 fichas eran imágenes escaneadas y se leyeron por **OCR** (llavín KIL, bisagras BB5, extractor Engepoli).

### Pendiente / advertencia importante
- La ficha técnica original de **ESTR01-CEMENTO** (`04421 - Ficha+Técnica.pdf`, datasheet de Holcim Cemento Fuerte ECOPlanet) **se borró por error** durante una limpieza. Hay que reponerla (desde la fuente original, la Papelera de Windows, o volviendo a descargar el datasheet de Holcim). Esto **no** afecta la generación de su carátula (que sale solo del JSON), solo falta el documento fuente.

---

## 9. Historial resumido de lo hecho en el chat

1. Extracción y clasificación de materiales del presupuesto (ARQ/MEC/ESTR) + memoria/resumen.
2. Creación de la estructura de carpetas madre + subcarpetas por material.
3. Renumeración consecutiva sin huecos.
4. Primera `Guía Materiales.xlsx` (Consecutivo + Descripción).
5. Reorganización por familias + normalización de medidas (mm y pulgadas) + actualización del Excel (columna Familia).
6. Conversión de la plantilla de Claude Design a `template_caratula.html` puro con placeholders Jinja2.
7. Validación del HTML.
8. Cambio del logo a variable `{{ logo_path }}` dinámica.
9. Creación y evolución de `generate_caratulas.py` (con validaciones, logging, reporte).
10. Lectura de fichas técnicas (incl. OCR), detección de carpetas vacías, y `datos_materiales.json` + Excel con columna Estado.
11. Corrección del script para Windows: motor **Playwright** como principal (por fallar wkhtmltopdf y GTK/weasyprint).
12. **Modo incremental:** el script ahora salta cualquier carpeta que ya contenga una carátula.
