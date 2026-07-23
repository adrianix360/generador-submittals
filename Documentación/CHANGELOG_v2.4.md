# CHANGELOG — Generador de Submittals ES

## v2.4 (2026-07-17) — Elaborado por Adrián Castro

### 🔴 FIX CRÍTICO: bug de "múltiples ventanas" en el .exe
- **Causa raíz encontrada:** en un `.exe` empaquetado, `sys.executable` es el
  propio ejecutable (no `python.exe`). El bootstrap de v2.3 ejecutaba
  `subprocess([sys.executable, "-m", "pip"/"playwright", ...])`, lo que
  **relanzaba el .exe en bucle** → decenas de ventanas hasta agotar la máquina.
- **Solución:**
  - Cuando el programa corre empaquetado (`sys.frozen`), el bootstrap **ya NO
    ejecuta ningún subprocess** (las librerías van embebidas). Solo verifica y
    avisa. Esto elimina el relanzamiento.
  - `multiprocessing.freeze_support()` al inicio (buena práctica de PyInstaller).
  - **Instancia única** por socket: si el programa ya está abierto, la 2ª
    ejecución avisa y se cierra (no abre otra ventana).
  - **Control de hilo** en GENERAR: si ya hay un proceso corriendo, ignora el
    nuevo clic ("El programa ya está generando…").
  - Botón GENERAR se deshabilita durante el proceso; aparece CANCELAR.
  - Liberación de recursos: `close()` de imágenes PIL, buffers y PDF writers en
    bloques `finally`.
- Validación: instancia única probada (2ª instancia = rechazada).

### 🔒 Seguridad: la API key ya no se puede copiar
- Se eliminó por completo el botón **"Copiar"** y su función.
- El panel de Mantenimiento ahora solo muestra el **estado**
  ("✅ Configurada" / "Sin configurar"), nunca la clave.
- La clave sigue guardada ofuscada (base64) y solo se puede **Limpiar** o
  **Cambiar**.

### ✨ Traducción automática de especificaciones
- ChatGPT detecta el idioma de las fichas y, si **no** están en español, las
  **traduce** y trabaja sobre la versión traducida.
- El JSON de cada material incluye `idioma_original` y `fue_traducido`.
- Cuando se traduce, se registra en el log: *"[TRADUCCION] ARQ01: ficha en
  inglés traducida al español"* y el resumen cuenta `traducidos`.
- No requiere librerías extra (la detección la hace el mismo modelo).

### ✨ Integración con SICOP (búsqueda de licitación)
- Nueva sección **"🔍 Búsqueda de licitación SICOP"**: se ingresa el número de
  procedimiento (se **convierte a MAYÚSCULAS** automáticamente) y con "Buscar"
  se intenta traer proyecto, cliente, plazo y monto para pre-llenar los datos.
- Manejo de errores: formato inválido, timeout, sin conexión → mensajes claros
  y **fallback manual** (nunca rompe el programa).
- Nota: SICOP es un portal dinámico sin un endpoint público estable, por lo que
  esta función es **best-effort**; si no logra extraer datos, avisa para que se
  ingresen a mano en "Datos del proyecto". El endpoint/parseo se puede ajustar
  en `buscar_licitacion_sicop()` si se dispone de uno.

### 🐛 Fix: página en blanco en la carátula del Ministerio de Salud
- Se corrigió el CSS de impresión: `.ms-sheet { min-height: 0 !important; }` en
  `@media print` (el `min-height:1056px` fijo hacía que Chromium desbordara a una
  2ª página en blanco) y `page-break-inside: avoid` en el formulario.
- Verificado: la carátula ocupa **1 sola página**; el compilado ya no tiene la
  página en blanco entre carátula y fichas.

### 📦 Librerías / config
- Nuevas dependencias (para SICOP): `requests`, `beautifulsoup4` (el bootstrap
  las instala solas en modo `.py`).
- `submitals_config.json`: `version` = "2.4".

### ⚠️ Recomendación de empaquetado
Al compilar el `.exe`, embeber plantillas y logos:
```
pyinstaller --onefile --windowed --name "GeneradorSubmittalsES" ^
  --collect-all playwright --collect-all jinja2 --collect-all pypdf ^
  --collect-all fitz --collect-all bs4 ^
  --add-data "template_caratula.html;." ^
  --add-data "template_ministerio_salud.html;." ^
  --add-data "Tabla visual refresh/assets/logo_es_crop.png;Tabla visual refresh/assets" ^
  --add-data "Tabla visual refresh/assets/ministerio_salud_banner.png;Tabla visual refresh/assets" ^
  submitals_gui.py
```
En modo `.exe`, las librerías van dentro; en la PC destino puede faltar Chromium
o Tesseract y el programa lo verifica al abrir (sin relanzarse).

---

## v2.3
- Bootstrap de dependencias, selector de carátula, datos de proyecto (Ministerio),
  campos vacíos, "forzar" sobreescribe.

## v2.2
- Compilados, multi-documento, OCR mejorado.

## v2.1
- Mantenimiento + normativas.

## v2.0
- Auto-generación de JSON con ChatGPT.

## v1.0
- Interfaz tkinter.
