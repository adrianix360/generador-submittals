# CHANGELOG COMPLETO — Generador de Submittals ES

Historial de versiones (v1.0 → v2.6.18). Elaborado por Adrián Castro.

---

## v2.6.18 (2026-07-24) — Carátulas editables (campos de formulario en el PDF)

- Ambas carátulas (Clásica y Ministerio de Salud) se generan ahora como PDF con
  **campos de formulario editables** sobre cada dato: se puede corregir un valor
  a mano en cualquier lector de PDF, sin volver a generar la carátula con la app.
- El aspecto es idéntico al anterior; el valor va dentro de un cuadro de texto
  (no queda texto "quemado" detrás, así que no se duplica al editar). Fuente,
  color y alineación se toman del propio diseño.
- El render (Playwright) mide la posición real de cada caja en modo impresión y
  coloca el campo con PyMuPDF (fitz). Los compilados (`-CMP.pdf`) fusionan la
  carátula con `append(...)` para no perder los campos editables.
- Si PyMuPDF no está disponible o algo falla, se genera la carátula plana
  anterior como respaldo. Solo aplica al motor Playwright (recomendado).

## v2.6.17 (2026-07-24) — Consecutivo inicial por disciplina (remedial/temporal)

- ⚠️ Función **temporal**, no definitiva: para cuando una lista de submittals
  debe continuar la numeración de otra lista previa en vez de reiniciarla.
- Nueva sección "🔢 CONSECUTIVO INICIAL (temporal)": por cada disciplina
  (ARQ, ESTR, MEC, ELEC) se indica desde qué número arranca su consecutivo
  (ej: ARQ = 35 → la 1ra carpeta ARQ sale como ARQ35, la siguiente ARQ36…).
- Renumera **en secuencia** (ignora el número de la carpeta); el nombre de las
  carpetas no cambia, solo el consecutivo de la carátula, el compilado y el
  Excel. Disciplinas con campo vacío mantienen la numeración normal.
- Los campos no se persisten (arrancan vacíos en cada sesión) y se pide
  confirmación antes de renumerar. Para reemplazar carátulas ya generadas debe
  estar activo "Forzar regeneración".

## v2.6.16 (2026-07-24) — Columna "Proveedor" en la Guía interna de materiales

- Cada hoja de "Guía interna materiales.xlsx" ahora incluye una sexta columna,
  "Proveedor", de llenado manual (depende del stock de cada proveedor y no se
  puede automatizar); la app nunca escribe valores en ella.
- Como este Excel se regenera por completo en cada actualización, si el
  archivo ya existía se preservan los valores previos de "Proveedor"
  emparejando filas por Consecutivo, para que no se pierdan al actualizar.

## v2.6.15 (2026-07-24) — Fix definitivo del tamaño de la carátula

- Chromium decide dónde cortar el contenido en páginas según el `@page` del
  CSS, de forma **independiente** al ancho/alto que se le pide a
  `page.pdf()` (eso solo define el tamaño físico de cada página resultante).
  Como la plantilla trae un `@page` fijo (pensado como respaldo para otros
  motores de PDF), cuando ese tamaño no coincidía exactamente con el alto
  real del contenido, Chromium seguía paginando de más o dejando espacio en
  blanco de más, según el caso — la causa de fondo de los dos intentos
  anteriores.
- Ahora, justo antes de generar el PDF, se inyecta un `@page` que coincide
  **exactamente** con el alto recién medido del contenido real, de forma que
  nunca compite con el tamaño solicitado. La carátula queda siempre en una
  sola página, ajustada a su contenido.

## v2.6.14 (2026-07-24) — Fix: páginas casi en blanco en la carátula

- El fix de v2.6.13 (alto dinámico de la carátula) estaba generando páginas
  enormes casi en blanco: el contenido se veía pequeño arriba y el resto de
  la hoja quedaba vacío. La causa: el alto se medía después de activar el
  modo impresión, y la hoja de respaldo del CSS (`@page`, agrandada en
  v2.6.13) hace que el body ocupe el alto completo de esa caja de página en
  modo impresión, en vez del alto real del contenido.
- Ahora el alto se mide en modo pantalla (antes de cambiar a impresión),
  directamente sobre el elemento de la hoja (`.om-sheet` / `.ms-sheet`), lo
  que refleja el contenido real sin importar el tamaño del `@page`.

## v2.6.13 (2026-07-24) — Fix: carátula cortada y botones de compilado

- **Carátula clásica cortada**: al agregar los nuevos datos de procedimiento,
  el contenido desbordaba la hoja tamaño carta y Chromium la dividía en 2
  páginas; como el compilado individual solo conservaba la primera página, el
  resto del contenido se perdía. Como la carátula nunca se imprime en papel,
  ahora el PDF se dimensiona dinámicamente al alto real del contenido, así
  que siempre ocupa una sola hoja completa sin importar cuántos datos u
  observaciones tenga.
- **"📦 Generar Compilados" y "Entrega final" no funcionaban**: eran un
  efecto secundario de la misma causa (carátulas partidas en 2 páginas). Al
  corregir el tamaño de la carátula, ambos botones vuelven a generar los
  compilados completos y correctos.
- **Ancho de hoja incorrecto**: el ancho real de la carátula se medía mal y
  generaba páginas de ~13 pulgadas con márgenes en blanco a los lados; ahora
  se fija correctamente a 8.5 pulgadas (816px), el ancho de diseño real.
- **Corte todavía posible con texto muy largo combinado**: la hoja de
  respaldo usada para calcular los saltos de página tenía un límite que aún
  podía cortar carátulas con varios campos de texto libre muy extensos
  combinados; se amplió ese límite a un valor que ninguna carátula real
  alcanza.
- **Excel vacío fallaba**: generar el Excel interno o el de entrega con un
  JSON sin materiales válidos producía un error interno; ahora devuelve un
  mensaje claro en vez de fallar.
- Motores de respaldo (weasyprint, pdfkit) también reciben una hoja más alta
  que carta como salvaguarda adicional.

## v2.6.12 (2026-07-23) — Datos del procedimiento en la carátula clásica

- La carátula clásica (ES Constructora) agrega una nueva sección
  **"Información del procedimiento"**, antes de la información del material o
  equipo, con la misma estética del resto de la carátula.
- Campos incluidos: Número de procedimiento, Nombre de la institución,
  Detalle de procedimiento, Duración de contrato y Monto.
- El botón **"Datos del proyecto"** ahora está disponible para ambas
  carátulas (antes solo para Ministerio de Salud). Los nuevos campos de la
  carátula clásica reutilizan los mismos datos ya existentes del proyecto
  (Contrato/Licitación, Cliente/Institución, Plazo, Monto) — así el dato se
  llena una sola vez y aplica a cualquiera de las dos carátulas.
- El campo **"Proyecto"** del diálogo es el mismo dato en ambas carátulas: en
  la de Ministerio de Salud se muestra como "Proyecto" (esa carátula no se
  puede modificar) y en la clásica se muestra como "Detalle de
  procedimiento".

## v2.6.11 (2026-07-23) — Notas de tolerancia para elementos de acero

- Las carátulas agregan al final de las observaciones una nota breve y
  profesional sobre la tolerancia aplicable a cada elemento de acero.
- Tubos estructurales ASTM A500/A500M: se aclara la tolerancia de hasta −10 %
  respecto al espesor nominal.
- Tuberías de acero ASTM A53/A53M: se indica la tolerancia específica de
  espesor de pared.
- Perfiles conformados en frío: se aplica la referencia de AISI S240 sobre el
  espesor base mínimo; perfiles, angulares, pletinas y otros laminados reciben
  la nota correspondiente a ASTM A6/A6M.
- La nota conserva las observaciones existentes, se muestra en ambas plantillas
  de carátula y no se duplica al reutilizar un JSON. Se excluyen PVC, CPVC,
  PPR, PEAD, cobre y otros materiales no cubiertos por esas normas de acero.

## v2.6.10 (2026-07-23) — Varias marcas en un mismo material

- Cuando una carpeta contiene fichas de dos o más fabricantes, el campo
  **Marca** muestra todas las alternativas en el formato
  `Marca 1 / Marca 2 / Marca 3`.
- Se eliminan duplicados, variantes casi idénticas y valores genéricos como
  `SIN ESPECIFICAR` o `POR DEFINIR`, respetando el orden de aparición en las
  fichas técnicas.

## v2.6.9 (2026-07-23) — Excel interno y Excel de entrega separados

- El archivo de uso interno pasó a llamarse **Guía interna materiales.xlsx** y
  conserva la información técnica y de control por disciplina.
- La exportación final ya no incluye ese archivo interno: genera
  **Guía Submittal.xlsx**, con una hoja por disciplina y solo las columnas
  Consecutivo, Descripción, Aprobación y Observaciones para la administración
  del contrato.

## v2.6.8 (2026-07-23) — Lectura robusta de imágenes degradadas

- Antes de extraer información, la aplicación evalúa resolución, contraste y
  nitidez de las fichas en imagen; las versiones mejoradas se trabajan en
  memoria y el original no se modifica.
- El OCR compara versiones original, ampliada y binaria para conservar la
  estructura de tablas técnicas. OpenAI Vision recibe además acercamientos de
  alta resolución y una segunda lectura audita marca, descripción y normativa.
- El JSON registra modelo utilizado, métricas de calidad, confianza, evidencias
  y necesidad de revisión manual. Si Vision no está disponible, el flujo sigue
  con OCR y extracción de texto.
- Se publicó el ejecutable como Release para que el actualizador pueda ofrecer
  la versión nueva a los equipos de oficina.

## v2.6.7 (2026-07-23) — Publicación y actualización de la aplicación

- El repositorio se depuró para distribuir solo el código y los recursos de la
  aplicación: se excluyeron disciplinas de trabajo, respaldos y binarios del
  control de versiones.
- Se incorporó el manifiesto `VERSION.json`, el actualizador y la configuración
  de despliegue para publicar versiones desde GitHub y permitir actualizaciones
  posteriores del programa.

## v2.6.6 (2026-07-22) — Fix: columna "Descripción" del Excel + icono de la app + OCR sin admin

- 🐛 **Columna "Descripción" del Excel (`Guía Materiales.xlsx`)**: mostraba el
  texto largo que ChatGPT extrae de la ficha técnica (`item["descripcion"]`
  en `datos_materiales.json`), en vez del nombre real del material. Reportado
  por la usuaria: al actualizar el Excel, la columna debe mostrar el nombre
  del material tal como está en el nombre de la carpeta, no el nombre largo
  extraído del JSON.
  - Corrección en `generar_excel_materiales()`: la columna 3 ahora usa
    `item["nombre"]` (nombre de la subcarpeta, ej. `ARQ01-Cerámica 60x60`)
    en vez de `item["descripcion"]` (redacción de ChatGPT).
- ✨ **Icono de la app**: se incorporó el icono nuevo provisto por la usuaria
  (carpeta `Icono Generador de Submittals/`).
  - `assets/icono_app.ico` (variante "tile", fondo azul propio): icono de la
    ventana principal y del splash de arranque — es el que se ve en la barra
    de tareas de Windows mientras la app está abierta. También asignado como
    icono del `.exe` en `GeneradorSubmittalsES.spec` (`icon=`), y bundleado
    como dato (`datas`) para el build empaquetado.
  - `assets/icono_header.png` (variante "oscuro", sin fondo): logo pequeño
    agregado junto al título "GENERADOR DE SUBMITTALS" en el header de la
    interfaz, integrado sobre el azul del header (`_construir_ui()`).
  - Nueva función `_aplicar_icono_ventana()`: aplica `iconbitmap` (.ico) con
    respaldo a `iconphoto` (.png) si el primero falla.
- 🔧 **OCR sin permisos de administrador**: los datos de idioma español para
  Tesseract (`spa.traineddata`) ahora se guardan en una carpeta propia de la
  app (`tessdata_es/`) en vez de la carpeta de instalación de Tesseract-OCR
  (`Program Files\Tesseract-OCR\tessdata`), que requiere administrador para
  modificarse. `pytesseract` se apunta a la copia propia vía
  `TESSDATA_PREFIX`.
- ✅ Sin regresión: generación de carátulas, compilados y detección de
  duplicados intactos.

## v2.6.5 (2026-07-22) — Fix: fichas con tablas técnicas densas (dimensiones/tolerancias)
- 🐛 Fichas con tablas de especificaciones (varios diámetros/medidas por fila,
  con tolerancias, ej. accesorios PVC, perfilería estructural) fallaban en
  `extraer_con_chatgpt()`: la causa NO era "OpenAI Vision" (esa función nunca
  usó Vision, solo texto), sino que `_leer_pdf_texto()` colapsa todos los
  saltos de línea a espacios, y la tabla queda "aplanada" en una sola tira de
  números sin fila/columna (ej. "13 19 25 32 ... 21.6 26.9 33.7 ... 0.2 0.3
  0.3 ..."). ChatGPT no puede reconstruir esa estructura y la marca/
  descripción salían vacías, genéricas o con ruido numérico.
- 🔧 Nueva detección `es_tabla_tecnica_densa()`: identifica cuando el texto
  extraído de una ficha PDF tiene esa forma (muchos números + palabras como
  "tolerancia"/"diámetro nominal"/"dimensiones", o 3+ símbolos "±").
- 🔧 Nueva `extraer_resumen_tabla_pdfplumber()`: si se detecta, se relee el
  mismo PDF con `pdfplumber` (respeta filas/columnas) y arma un resumen
  legible ("Columnas de la tabla: ...", filas de muestra) que se envía a
  ChatGPT en vez del texto aplanado. Si pdfplumber no encuentra tabla o no
  está instalado, se seguía usando el texto plano de siempre (sin romper
  nada existente).
- 🔧 Nueva validación `_desc_parece_valida()`: si aun así ChatGPT devuelve una
  "descripción" que en realidad es ruido numérico (<40% letras), se
  reemplaza por un texto genérico en vez de guardar basura en el submittal.
- ✨ `PROMPT_TXT` ahora indica explícitamente cómo tratar un documento marcado
  como tabla de especificaciones (describir el producto en general, ignorar
  tolerancias numéricas).
- ➕ Nueva dependencia opcional `pdfplumber` (agregada a `PIP_DEPS`,
  `requirements.txt` y al `.spec` de PyInstaller).
- ✅ Validado offline (sin consumir API de OpenAI) con fichas reales del
  proyecto: la detección da positivo en fichas con tablas de dimensiones
  (ej. `FT Ced 40 conexiones.pdf`) y negativo en fichas comerciales normales
  (pintura, Durock, cemento), sin falsos positivos en las probadas.

## v2.6.4 (2026-07-21) — Fix: marcas distintas tratadas como una sola (logo en imagen)
- 🐛 En ESTR23/ESTR24 (tubos estructurales), las fichas de MultiGroup y Metalco
  se trataban como el mismo proveedor. Causa: el nombre "METALCO" solo existe
  como logo gráfico en la portada de esa ficha, no como texto — confirmado
  extrayendo el texto completo (sin la palabra "METALCO") y renderizando la
  portada como imagen.
- 🔧 `analizar_relacion_fichas()` ahora también envía la imagen de portada de
  cada ficha a OpenAI Vision (`gpt-4o`, mismo proveedor) cuando hay 2+ fichas
  en una carpeta, para leer logos que el texto no captura. Se agregó además una
  salvaguarda determinista: si la IA identifica 2+ marcas distintas pero aun
  así clasifica como "mismo proveedor", se corrige automáticamente.
- ✨ Redacción de "distintas marcas" mejorada: ahora enfatiza que se solicita la
  aprobación previa de las N marcas del submittal para poder instalar
  cualquiera de ellas ante una eventual falta de stock.
- ✅ Validado con las fichas reales de ESTR23/ESTR24 (ahora identifica
  correctamente MultiGroup + Metalco) y con pruebas de regresión de los casos
  ya existentes (mismo proveedor, discrepancia).

## v2.6.3 (2026-07-21) — "Borrar todo" también elimina el JSON
- 🔧 El botón **🗑️ Borrar Carátulas y Compilados (empezar de 0)** ahora también
  elimina `datos_materiales.json` (antes lo conservaba). El diálogo de
  confirmación advierte que la próxima generación deberá releer las fichas con
  ChatGPT; al terminar, la GUI vuelve sola al modo "generar JSON automático".
  Las fichas técnicas originales de cada carpeta siguen sin tocarse.

## v2.6.2 (2026-07-21) — Fix crítico de render, fichas incompletas, borrado total
- 🔴 **Fix crítico: carátulas clásicas se veían mal.** Causa raíz: una carpeta
  `ms-playwright` vacía (creada por error en `_crear_carpetas_iniciales()`)
  hacía que la app redirigiera Playwright hacia ella en vez de la caché global
  donde Chromium SÍ estaba instalado y funcional. Playwright fallaba en cada
  carátula y el motor caía silenciosamente a `pdfkit`/wkhtmltopdf (pobre soporte
  de CSS moderno) sin avisar — de ahí "antes funcionaba perfecto". Corregido:
  la redirección ahora exige que la carpeta tenga contenido, no solo que exista;
  se eliminó la creación de esa carpeta vacía; se reinstaló Chromium.
- ✨ Nueva salvaguarda: contador `motor_fallback` — si una futura corrida vuelve
  a usar el motor de respaldo, la GUI avisa explícitamente al terminar el
  proceso (no vuelve a quedar enterrado solo en el log).
- ✨ **Fichas incompletas ya generan carátula**: antes se omitían por completo
  (`estado != FICHA_DISPONIBLE` o campos vacíos → sin PDF). Ahora se genera la
  carátula con los datos disponibles, dejando en blanco lo que falte (nunca se
  inventa información); se sigue registrando en el reporte que estaba incompleta.
- ✨ Nuevo botón **🗑️ Borrar Carátulas y Compilados (empezar de 0)**: borra todas
  las `CARATULA*.pdf`, `*-CMP.pdf` y `CMP SUBMITTAL *.pdf` bajo la carpeta base
  (con confirmación explícita; no toca fichas originales ni el JSON). Resuelve
  que, al sobrescribir una carátula, su compilado quedaba desincronizado porque
  "solo faltantes" lo encontraba ya existente y no lo regeneraba.
- ✅ Sin regresión: duplicados, aspectos adicionales por IA, Excel, compilados
  por disciplina y traducción automática, intactos.

## v2.6.1 (2026-07-21) — Fix: falsos positivos en Detectar Duplicados
- 🐛 El detector marcaba como "duplicados" materiales de la misma marca/familia
  y normativa pero de **tamaño o tipo distinto** (ej. costanera 3"x2" vs 4"x2";
  uniones/codos/reducciones PVC de 50/100/150mm), porque el texto de plantilla
  compartido (marca, normativa, frases de instalación) dominaba la similitud y
  ocultaba que la medida específica era distinta.
- 🔧 `detectar_duplicados()`: **veto duro por dimensiones** (nunca se marcan
  como duplicados si las medidas detectadas en nombre/descripción difieren),
  umbral de similitud 0.82→**0.95** (0.60→**0.75** con mismo nombre de carpeta),
  y agrupamiento por **clique** (un material debe coincidir con TODOS los del
  grupo, no solo con el primero) en vez de por "estrella".
- ✅ Validado reconstruyendo los 4 grupos falsos reportados (0 quedan) + pruebas
  de regresión de duplicados reales. `resolver_duplicados()` sin cambios.

## v2.6 (2026-07-21) — Duplicados, aspectos adicionales por IA y Excel
- ✨ **Detección y resolución de materiales duplicados**: nuevo botón
  **🧬 Detectar Duplicados** compara todos los materiales (marca+descripcion+
  normativa, `difflib`) y agrupa los que parecen ser la misma ficha registrada
  dos veces. El usuario elige cuál consecutivo conservar por grupo; al
  confirmar, `resolver_duplicados()`:
  1) mueve la(s) carpeta(s) duplicada(s) a `_DUPLICADOS_ELIMINADOS/` (reversible,
     no borra), 2) reordena los consecutivos posteriores de esa disciplina
     cerrando el hueco (renombra carpetas en disco), 3) borra la
     `CARATULA*.pdf`/`*-CMP.pdf` obsoletas SOLO en las carpetas renumeradas,
     4) recalcula `compilado_generado`, 5) elimina el compilado por disciplina
     (`CMP SUBMITTAL *.pdf`) que quedó obsoleto, 6) reescribe
     `datos_materiales.json` y `Guía Materiales.xlsx`, y 7) deja la GUI en modo
     "usar JSON existente" apuntando al JSON corregido para regenerar carátulas
     con un clic, sin volver a consultar la API.
- ✨ **Aspectos adicionales por relación entre fichas (multi-documento)**:
  cuando una carpeta trae 2+ fichas técnicas, se consulta a OpenAI
  (`gpt-4o-mini`, mismo proveedor ya usado en el proyecto) para clasificar la
  relación y redactar "Aspectos/Observaciones adicionales": mismo proveedor
  (fichas complementarias), misma familia/distinta marca (alternativas por
  stock/abasto), o discrepancia de tipo de producto (no se redacta texto; se
  registra advertencia en `generate_caratulas.log` para revisión manual —
  evita, por ejemplo, mezclar clavos con tubería de PVC en una misma carpeta).
  Nuevo campo `aspectos_adicionales` propagado a ambas plantillas de carátula.
- ✨ Nuevo botón **📊 Actualizar Excel**: regenera `Guía Materiales.xlsx` a
  demanda desde el JSON actual, sin correr un proceso completo.
- 🐛 **Fix `generar_excel_materiales()` nunca generaba el Excel**:
  `wb.create_sheet(titulo=...)` (parámetro inválido) → `title=...`. El error
  quedaba silenciado dentro del hilo de trabajo desde que se implementó esta
  función.
- ✅ Sin regresión: carátulas de una sola ficha, compilados por disciplina, OCR,
  traducción automática y seguridad de la API key, intactos.

## v2.5.2 (2026-07-20) — Compilado por disciplina
- ✨ Nuevo botón opcional **📦 Generar Compilados** con checkboxes ARQ/ESTR/MEC/ELEC:
  genera un PDF único por disciplina con TODAS sus carátulas y fichas en orden
  (ej: `COMPILADO-ARQUITECTONICOS.pdf` = ARQ01 + ARQ02 + ARQ03…), ubicado en la
  carpeta madre de la disciplina.
- 🔧 Nueva función `compilar_por_disciplina()` en `submitals_gui.py`: usa **pypdf**
  puro (ya era dependencia del proyecto; no se agrega PyPDF2), reutiliza las
  carátulas/fichas ya generadas y **no consume API de OpenAI**.
- 🔄 Corre en un hilo independiente (`hilo_compilados_disciplina`) con su propia
  cola de eventos (`DISC_FASE`, `DISC_PROG`, `DISC_COMPLETE`); bloquea que se
  solape con la generación principal y viceversa.
- ✅ Sin regresión: es una opción nueva, no cambia el flujo de "GENERAR" existente.
- 🐛 **Fix `.exe`: no encontraba las plantillas de carátula.** Causa: `GeneradorSubmittalsES.spec`
  no tenía los `--add-data` de `template_caratula.html`, `template_ministerio_salud.html`
  ni los logos (`Tabla visual refresh/assets/*.png`), a diferencia del comando de la
  memoria (§12) → `resource_path()` no los hallaba ni embebidos ni junto al `.exe`.
  Corregido agregando esos 4 archivos a `datas` en el `.spec`; verificado extrayendo
  el `.exe` y confirmando `template_caratula.html`/`template_ministerio_salud.html`
  en la raíz de `_MEIPASS` y los `.png` en `Tabla visual refresh/assets/`.

## v2.5.1 (2026-07-17) — SICOP con OpenAI Vision
- 🔧 **SICOP con OpenAI `gpt-4o` Vision** en vez de Anthropic/Claude → **una sola
  API key** (la de OpenAI), ~50% menos costo. `detail:"low"`, `max_tokens:500`.
- 🧹 Eliminado `anthropic` (import, dependencia, campo de key en la GUI).
- ✅ Sin regresión: ELECTRICOS, fix de múltiples ventanas, traducción, seguridad.
- Config `version` = "2.5.1"; nuevo `requirements.txt` (sin anthropic).

## v2.5 (2026-07-17) — SICOP con Vision + disciplina ELECTRICOS
- ✨ **SICOP rehecho** con Playwright + **Claude Vision** (screenshot → IA lee la
  imagen → JSON). Robusto ante cambios de HTML. (Reemplazado por OpenAI en v2.5.1.)
- ✨ Nueva disciplina **ELECTRICOS (ELEC##)** (orden ARQ → ESTR → MEC → ELEC);
  carpeta madre creada; carátulas y compilados ELEC OK.
- 🔴 El scraping HTML de SICOP de v2.4 no funcionaba → se abandonó.

## v2.4 (2026-07-16) — Fix crítico + seguridad + traducción + SICOP inicial
- 🔴 **FIX CRÍTICO "múltiples ventanas" en el .exe**: causa = el bootstrap ejecutaba
  `subprocess([sys.executable, ...])` y en un `.exe` eso **relanza el propio .exe**
  en bucle. Solución: no ejecutar subprocess cuando `sys.frozen`;
  `multiprocessing.freeze_support()`; **instancia única** por socket; control de hilo;
  cierre de recursos en `finally`.
- 🔒 **Seguridad**: se eliminó "Copiar" de la API key; solo se muestra su estado.
- ✨ **Traducción automática**: el modelo detecta idioma y traduce; JSON con
  `idioma_original` y `fue_traducido`.
- ✨ **SICOP v1** (scraping con requests/bs4) — no funcional; reemplazado en v2.5.
- 🐛 **Fix página en blanco** en la carátula del Ministerio (`min-height:0` en print).

## v2.3 (2026-07-16) — Multi-PC, selector de carátula, datos de proyecto
- ✨ **Bootstrap de dependencias**: verifica Python y librerías; instala lo que falte
  y Chromium al arrancar. Funciona en cualquier PC con solo Python.
- ✨ **Selector de carátula** (Clásica / Ministerio de Salud), plantillas y logos
  embebibles en el `.exe` (`resource_path`), con aviso "pida actualización al admin".
- ✨ **Menú "Datos del proyecto"** para la carátula del Ministerio; `Versión`=v1 y
  `Registro`=consecutivo automáticos.
- 🔄 **Campos vacíos** cuando falta info (no se inventa).
- 🔄 **"Forzar regeneración" sobrescribe** carátula y compilado existentes.

## v2.2 (2026-07-16) — Compilados, multi-documento, OCR mejorado
- ✨ **Compilados** `<CONS>-<NOMBRE>-CMP.pdf` (carátula pág.1 + todas las fichas).
- ✨ **Multi-documento** por carpeta: lee todas las fichas y fusiona los datos en un
  solo request a ChatGPT.
- ✨ **OCR mejorado** para PDF escaneado/imágenes (PyMuPDF + realce + Tesseract).
  Corrige el caso `BB5-BISAGRAS` que antes fallaba.
- ✨ Autor en el título ("Elaborado por Adrián Castro").

## v2.1 (2026-07-15) — Mantenimiento + normativas
- ✨ **Panel de Mantenimiento** (cambiar/limpiar/probar API key, resetear config,
  abrir carpeta, info).
- ✨ **Detección de normativas**: la IA extrae normas/estándares (ASTM, ISO, DIN…) →
  campo `normativa` en el JSON y en la carátula.

## v2.0 (2026-07-15) — Auto-generación de JSON con ChatGPT
- ✨ La app **lee las fichas** (PDF/imagen OCR/DOCX) y **extrae marca y descripción**
  con ChatGPT (`gpt-4o-mini`), construyendo `datos_materiales.json` automáticamente.
- ✨ Sección de configuración de API; modos "auto" vs "JSON existente"; threading con
  barra de progreso y botón Cancelar.

## v1.0 (2026-07-15) — Interfaz base
- ✨ GUI Tkinter para ejecutar el motor `generate_caratulas.py` sin usar consola:
  selección de carpeta y JSON, opciones (solo faltantes / forzar / mostrar log),
  progreso y resultados. Corre el motor en un hilo con comunicación por cola.

---

### Motor `generate_caratulas.py` (evolución)
- Base: renderiza `template_caratula.html` a PDF con Playwright → WeasyPrint → pdfkit.
- Añadido en v2.1: variable `normativa`.
- Añadido en v2.3: `process_material(..., extra_ctx=None)` para inyectar los campos
  del Ministerio y vaciar `SIN ESPECIFICAR`/`POR DEFINIR` al renderizar.
- Modo incremental: salta la carpeta si ya existe la carátula.

### Bugs resueltos (resumen)
- Truncamiento de archivos por sincronización del entorno (se reescribió el motor).
- Ficha `BB5-BISAGRAS` ilegible → OCR con PyMuPDF (v2.2).
- Página en blanco en Ministerio → CSS de impresión (v2.4).
- Múltiples ventanas en `.exe` → no relanzar el .exe + instancia única (v2.4).
- SICOP por scraping no funcionaba → Vision sobre screenshot (v2.5 / v2.5.1).
