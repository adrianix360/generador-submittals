# CHANGELOG — Generador de Submittals ES

## v2.6 (2026-07-21) — Elaborado por Adrián Castro

### ✨ Detección y resolución de materiales duplicados
Nuevo botón **🧬 Detectar Duplicados** (pantalla principal). Compara todos los
materiales del `datos_materiales.json` entre sí (marca + descripción + normativa,
con `difflib.SequenceMatcher`, y coincidencia de nombre de carpeta) para detectar
cuando la MISMA ficha técnica quedó registrada dos veces bajo consecutivos
distintos.

- `detectar_duplicados(materiales, umbral=0.82)`: agrupa materiales cuya
  similitud de contenido supera el umbral (o que comparten nombre de carpeta con
  similitud ≥ 0.60). Ignora carpetas vacías o con ficha ilegible (no hay datos
  suficientes para comparar).
- Al detectar grupos, se abre un diálogo donde el usuario elige, por grupo, cuál
  consecutivo **conservar**; los demás quedan marcados para eliminar.
- `resolver_duplicados(base, materiales, consecutivos_a_eliminar, q=None)`
  aplica la corrección contemplando **todas las afectaciones**:
  1. La(s) carpeta(s) duplicada(s) se **mueven** (no se borran) a
     `_DUPLICADOS_ELIMINADOS/<consecutivo>-<nombre>_<timestamp>/` dentro de la
     carpeta base — la eliminación es reversible.
  2. Los consecutivos posteriores de la **misma disciplina** se reordenan para
     cerrar el hueco (ej. `ARQ01, ARQ03, ARQ04` → `ARQ01, ARQ02, ARQ03`),
     renombrando las carpetas en disco en orden ascendente (sin colisiones,
     porque la numeración solo se comprime, nunca se invierte).
  3. En las carpetas renombradas se borran la `CARATULA*.pdf` y el `*-CMP.pdf`
     existentes (referencian el consecutivo/nombre de archivo viejo) para que se
     regeneren limpias en la próxima corrida; las carpetas que NO cambiaron de
     número conservan su carátula intacta.
  4. `compilado_generado` de cada material renumerado se recalcula con el nuevo
     consecutivo.
  5. El compilado por disciplina (`CMP SUBMITTAL <disciplina>.pdf`) de cada
     disciplina afectada queda obsoleto (cambia contenido y paginación) y se
     elimina; se avisa al usuario que debe regenerarlo con
     **📦 Generar Compilados**.
  6. `datos_materiales.json` y `Guía Materiales.xlsx` se reescriben de inmediato.
  7. La GUI queda preconfigurada en modo **"usar JSON existente"** apuntando al
     JSON corregido, para que un solo clic en **🚀 GENERAR** regenere las
     carátulas pendientes **sin volver a consultar la API de OpenAI**.
- Validado con una batería de pruebas sobre una estructura de carpetas simulada
  (detección de un grupo duplicado, cuarentena, renombrado en cascada, limpieza
  selectiva de carátulas/compilados, actualización de JSON/Excel y wiring de la
  GUI) antes de integrarlo.

### ✨ Aspectos adicionales por relación entre fichas técnicas (multi-documento)
Cuando una carpeta de material contiene **2 o más fichas técnicas**, se consulta
a la misma IA ya usada en el proyecto (OpenAI `gpt-4o-mini`, sin agregar otro
proveedor) para clasificar la relación entre ellas y redactar el campo
"Aspectos/Observaciones adicionales" de la carátula:

- **Mismo proveedor / mismo producto** (documentos complementarios): se redacta
  automáticamente que se adjuntan N fichas del mismo proveedor que se
  complementan entre sí.
- **Mismo tipo de producto, distinta marca**: se redacta que se adjuntan N
  fichas de distintas marcas comerciales equivalentes, aclarando que por temas
  de stock/abastecimiento se podría usar cualquiera garantizando calidad y
  seguridad de la obra.
- **Discrepancia** (tipos de producto incompatibles en la misma carpeta, ej.
  clavos junto con tubería de PVC): NO se redacta texto en la carátula; se
  registra una **advertencia en `generate_caratulas.log`** (log persistente del
  motor) detallando la carpeta, los tipos de producto detectados y los archivos
  involucrados, para que se revise si la carpeta mezcló materiales por error.
- Nuevas funciones: `_chatgpt_json()` (helper común con reintentos, reutilizado
  también por la extracción de marca/descripción existente),
  `analizar_relacion_fichas()`, `construir_texto_aspectos_adicionales()`.
- Nuevo campo `aspectos_adicionales` en cada material del JSON; propagado al
  contexto Jinja2 en `generate_caratulas.py` y renderizado en
  `template_caratula.html` (antes vacío, sin variable) y en
  `template_ministerio_salud.html` (campo `observaciones_material`, antes
  forzado a vacío).
- Validado con llamadas reales a OpenAI para los 3 escenarios (mismo proveedor,
  misma familia/distinta marca, discrepancia): la clasificación acertó en los
  tres casos.

### ✨ Botón "Actualizar Excel"
Nuevo botón **📊 Actualizar Excel** en la pantalla principal: regenera
`Guía Materiales.xlsx` a demanda a partir del `datos_materiales.json` actual,
sin necesidad de correr un proceso completo de generación.

### 🐛 Fix: `generar_excel_materiales()` nunca había funcionado
`wb.create_sheet(titulo=nombre_hoja)` usaba el parámetro en español; la API de
`openpyxl` espera `title=`. Esto hacía que **toda** generación de Excel fallara
con `TypeError` desde que se implementó (el error quedaba silenciado dentro del
`try/except` del hilo de trabajo). Corregido a `wb.create_sheet(title=nombre_hoja)`;
verificado generando el Excel real sobre una estructura de prueba.

### ✅ Sin regresión
Compila sin errores; carátulas clásica y Ministerio de Salud siguen renderizando
igual para materiales de una sola ficha (`aspectos_adicionales` queda vacío,
como antes); compilados por disciplina, OCR, traducción automática y seguridad
de la API key: intactos.

### 🔁 Cambios técnicos
- `submitals_gui.py`: `import difflib`; nuevas constantes `CARPETA_CUARENTENA`,
  `UMBRAL_DUPLICADO`, `UMBRAL_DUPLICADO_MISMO_NOMBRE`,
  `RELACIONES_FICHAS_VALIDAS`; `construir_materiales(..., gc=None)` ahora recibe
  el módulo del motor para loguear advertencias de discrepancia directamente en
  `generate_caratulas.log`.
- `generate_caratulas.py`: contexto Jinja2 incluye `aspectos_adicionales`.
