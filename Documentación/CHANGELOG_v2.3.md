# CHANGELOG — Generador de Submittals ES

## v2.3 (2026-07-16) — Elaborado por Adrián Castro

### ✨ Nuevo: Auto-verificación e instalación de dependencias (bootstrap)
- Al arrancar, una ventana de preparación verifica Python (≥3.9) y las librerías
  necesarias; **si faltan, las instala automáticamente** (pip) y descarga
  **Chromium** de Playwright la primera vez.
- Pensado para funcionar en **cualquier PC que solo tenga Python instalado**.
- **Tesseract-OCR** (binario del sistema) no se puede instalar en silencio de
  forma universal: si no está, se avisa y el programa continúa (los PDF de texto
  y DOCX siguen funcionando; el OCR de imágenes queda limitado).
- En modo `.exe` empaquetado, salta la instalación pip (ya va embebida) pero
  igual verifica Chromium y Tesseract.
- Manejo de errores en español (sin internet, permisos, etc.).

### ✨ Nuevo: Selector de carátula
- Antes de generar, se elige la carátula: **Clásica (ES Constructora)** o
  **Ministerio de Salud**. Las plantillas y logos van **precargados/embebidos**
  en el .exe (helper `resource_path` para modo empaquetado y desarrollo).
- Aviso visible: *"Si la carátula que necesita no está en esta lista, solicite al
  administrador una actualización del software."*
- La selección se recuerda en `submitals_config.json`.

### ✨ Nuevo: Datos del proyecto (carátula Ministerio de Salud)
- Menú **"Datos del proyecto"** para capturar los campos que no salen de las
  fichas: proyecto, cliente/institución, contrato/licitación, monto, plazo,
  responsable (nombre y cargo), fecha y fecha de emisión.
- Estos datos se guardan y se reutilizan en todas las carátulas del lote.
- **Reglas fijas por material:** `Versión` = siempre **v1**; `Registro` = el
  **consecutivo** del material (p. ej. ARQ07). Ambas automáticas.
- Al elegir "Ministerio de Salud" por primera vez sin datos, el menú se abre solo.

### 🔄 Cambio: Campos vacíos cuando falta información
- Si las fichas no aportan un dato, el campo queda **en blanco** (no se inventa).
- Los valores internos `SIN ESPECIFICAR` / `POR DEFINIR` ahora se muestran
  **vacíos** en la carátula (listos para completarse a mano).

### 🔄 Cambio: "Forzar regeneración" ahora SOBREESCRIBE
- Al marcar "Forzar regeneración", se **reemplazan** la carátula y el compilado
  existentes por los nuevos.
- Si un PDF está abierto en un visor (archivo bloqueado), se avisa:
  *"cierre el PDF y reintente"*, sin romper el resto del lote.
- "Solo faltantes" mantiene el comportamiento incremental (salta los que existen).

### 🔧 Otros
- `submitals_config.json` v2.3: nuevas claves `caratula_seleccionada` y
  `datos_proyecto`. Migración automática desde v2.1/v2.2 sin perder la API key
  ni las carpetas recientes.
- Ajuste mínimo en `generate_caratulas.py`: `process_material` acepta un
  contexto extra (para los campos del Ministerio) y vacía `SIN ESPECIFICAR`/
  `POR DEFINIR` al renderizar. No cambia el uso previo.

### 📦 Librerías / empaquetado
    pip install jinja2 openai pypdf pymupdf pytesseract Pillow python-docx playwright
    python -m playwright install chromium
Empaquetado (embebe plantillas y logos):
    pyinstaller --onefile --windowed --name "GeneradorSubmittalsES" ^
      --collect-all playwright --collect-all jinja2 --collect-all pypdf ^
      --collect-all fitz ^
      --add-data "template_caratula.html;." ^
      --add-data "template_ministerio_salud.html;." ^
      --add-data "Tabla visual refresh/assets/logo_es_crop.png;Tabla visual refresh/assets" ^
      --add-data "Tabla visual refresh/assets/ministerio_salud_banner.png;Tabla visual refresh/assets" ^
      submitals_gui.py

---

## v2.2
- Compilados (carátula + fichas), multi-documento por carpeta, OCR mejorado
  (PyMuPDF) para PDFs escaneados, autor en título.

## v2.1
- Panel de Mantenimiento y detección de normativas.

## v2.0
- Auto-generación de datos_materiales.json con ChatGPT.

## v1.0
- Interfaz tkinter para el motor de carátulas.
