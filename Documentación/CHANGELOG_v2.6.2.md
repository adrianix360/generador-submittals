# CHANGELOG — Generador de Submittals ES

## v2.6.2 (2026-07-21) — Elaborado por Adrián Castro

### 🐛 Fix crítico: carátulas "clásicas" (ES) se generaban visualmente mal
**Causa raíz encontrada:** `_crear_carpetas_iniciales()` creaba, sin darse cuenta,
una carpeta **vacía** `ms-playwright` dentro de la carpeta base del proyecto. El
arranque de la app (`submitals_gui.py`) redirige `PLAYWRIGHT_BROWSERS_PATH` hacia
esa carpeta con solo verificar que **existiera** (sin revisar si tenía contenido).
Como quedaba vacía, Playwright ya no encontraba el Chromium correctamente
instalado en la caché global (`%LOCALAPPDATA%\ms-playwright`, instalado desde
antes y funcional) y fallaba en **cada** carátula
(`generate_caratulas.log`: `Motor playwright fallo... Executable doesn't exist`).
El motor caía silenciosamente a `pdfkit`/`wkhtmltopdf` (reportando "PDF generado
exitosamente" igual), cuyo soporte de CSS moderno (flexbox/grid, que usa
`template_caratula.html`) es muy pobre → carátulas con el layout roto. Por eso
"antes funcionaba perfecto": la carpeta vacía no existía todavía.

- 🔧 `submitals_gui.py`: la redirección a `ms-playwright` local ahora exige que
  la carpeta exista **y tenga contenido** (`any(_pw_local.iterdir())`), no solo
  que exista.
- 🔧 `_crear_carpetas_iniciales()` ya NO crea esa carpeta vacía (no cumplía
  ningún propósito real; el `.spec` de PyInstaller no empaqueta un Chromium ahí).
- ✨ **Salvaguarda para que esto no vuelva a pasar desapercibido**: nuevo
  contador `stats["motor_fallback"]` en `generate_caratulas.py` — cuenta cuántas
  carátulas se generaron con un motor de respaldo (no Playwright). Se reporta en
  `generate_caratulas_report.txt` y, si es > 0, la GUI muestra un aviso explícito
  al terminar el proceso indicando ejecutar `python -m playwright install chromium`.
- ✅ Validado: se reinstaló Chromium, se eliminó la carpeta local vacía, y se
  generó una carátula real (con el nuevo campo "Aspectos adicionales" de v2.6
  incluido) usando Playwright sin caer a pdfkit — el layout se renderiza
  correctamente (grid de 2 columnas, cajas alineadas, tipografía).

### ✨ Fichas técnicas incompletas ya generan carátula (con lo que se tenga)
Antes, si una ficha quedaba con `estado != FICHA_DISPONIBLE` (texto no legible,
OCR fallido, ChatGPT sin respuesta) o con algún campo vacío, `process_material()`
**omitía por completo** la carátula de ese material — el submittal se quedaba
sin ese documento. Ahora:
- Ya no se hace `return` ante ficha incompleta ni ante campos vacíos: se genera
  la carátula igual, con los datos que sí se pudieron extraer.
- Los campos sin dato quedan en blanco (vía `_vaciar()`, que ya existía) — nunca
  se inventa información.
- Se sigue registrando en el reporte/log que la ficha estaba incompleta (para
  que quede constancia de cuáles requieren revisión manual), pero ya no bloquea
  la generación del documento.
- Validado generando carátulas reales para (a) una ficha con `FICHA_INCOMPLETA`
  y (b) una con nombre/marca/descripción vacíos: ambas producen su PDF.

### ✨ Botón "🗑️ Borrar Carátulas y Compilados (empezar de 0)"
Nuevo botón en la pantalla principal. Resuelve el problema reportado de que, al
sobrescribir una carátula manualmente, el compilado (`*-CMP.pdf`) de esa carpeta
no se regeneraba (el modo incremental "solo faltantes" lo encuentra ya existente
y lo salta), quedando desincronizado con la carátula nueva.
- `borrar_caratulas_y_compilados(base, q=None)`: elimina, bajo toda la carpeta
  base, **todas** las `CARATULA*.pdf`, todos los compilados individuales
  (`*-CMP.pdf`) y todos los compilados por disciplina (`CMP SUBMITTAL *.pdf`).
  **No toca** las fichas técnicas originales ni `datos_materiales.json` (los
  datos ya extraídos con ChatGPT se conservan; solo se borran los PDF generados).
- Requiere confirmación explícita antes de ejecutar (acción irreversible: borrado
  permanente, no a una carpeta de respaldo — a diferencia de "Detectar
  Duplicados", aquí todo es 100% regenerable desde el JSON existente sin
  volver a consultar la API).
- Validado sobre una estructura simulada con 2 disciplinas: borra exactamente
  las carátulas/compilados/compilado-de-disciplina esperados y preserva intactas
  las fichas técnicas originales y el JSON.

### ✅ Sin regresión
Detección/resolución de duplicados (v2.6/v2.6.1), aspectos adicionales por IA,
botón de Excel, compilados por disciplina y traducción automática: intactos.
