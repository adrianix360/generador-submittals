# CHANGELOG — Generador de Submittals ES

## v2.2 (2026-07-16) — Elaborado por Adrián Castro

### ✨ Nuevo: Compilados (carátula + fichas en un solo PDF)
- Además de la carátula (`CARATULA <CONS>-<NOMBRE>.pdf`), ahora genera un **compilado** `<CONS>-<NOMBRE>-CMP.pdf` en cada carpeta con documentos.
- Estructura del compilado: **página 1 = carátula**, **páginas siguientes = TODAS las fichas** de la carpeta (PDFs e imágenes), en orden alfabético.
- Las imágenes (JPG/PNG/BMP/TIFF) se convierten a página PDF automáticamente.
- Si la carpeta no tiene documentos, **no** se genera compilado (solo la carátula).
- Los archivos originales **nunca se borran ni modifican**.

### ✨ Nuevo: Manejo de múltiples documentos por carpeta
- Si una carpeta tiene 2+ fichas, se leen **todas**, se combinan y se envían a ChatGPT en **un solo request**, que **fusiona** la información:
  - Marca: la principal.
  - Descripción: integra lo más importante de todos.
  - Normativas: reúne **todas** las normas (sin duplicados, orden alfabético).
- Ya no se salta ninguna carpeta por tener varios archivos.

### ✨ Nuevo: OCR mejorado para PDFs escaneados/imágenes
- Detecta si un PDF es de **texto** o de **imagen/scan**.
- Los PDF-imagen y las imágenes (JPG/PNG/BMP/TIFF) se procesan con **PyMuPDF → realce (contraste + nitidez) → Tesseract**.
- Corrige el caso que fallaba en v2.1: **`BB5-BISAGRAS ESPECIFICACIONES.pdf`** ahora se lee correctamente (≈1800 caracteres).
- Si el OCR falla (imagen de muy baja calidad), se marca `FICHA_INCOMPLETA` y **el proceso continúa**.

### ✨ Nuevo: Autor en la interfaz
- Título de la ventana y encabezado: *"…| v2.2 | Elaborado por Adrián Castro"*.
- Panel de Mantenimiento: *"Versión: 2.2 - Elaborado por Adrián Castro"*.

### 🔄 Cambios
- **Tipos de archivo admisibles ampliados:** PDF (texto e imagen), JPG, JPEG, PNG, BMP, TIFF/TIF, DOCX (el `.doc` antiguo se avisa; conviértalo a `.docx`/PDF).
- **Estructura JSON:** cada material añade `documentos_encontrados` (lista) y `compilado_generado` (nombre del PDF o `null`). El `resumen` añade `documentos_totales` y `compilados_generados`.
- **Prompt de ChatGPT:** ahora indica que puede recibir varios documentos de un mismo material y debe integrarlos.
- **Progreso:** 5 fases (verificación → lectura/IA → carátulas → compilados → fin), reflejadas en la barra y el log.
- **Forzar regeneración:** ahora también borra los compilados `*-CMP.pdf` antiguos.
- **"Solo faltantes":** salta carátula **y** compilado si ambos ya existen.
- `submitals_config.json`: `version` = "2.2".

### 🐛 Fix / robustez
- Compatibilidad **BB5-BISAGRAS** (PDF imagen) resuelta con el nuevo OCR.
- Un documento problemático (ilegible o no compilable) genera aviso pero **no rompe** el flujo.
- Compatibilidad con JSON de v2.0/v2.1: si falta `normativa` se agrega `"SIN ESPECIFICAR"`; los compilados se calculan desde el disco.

### 📦 Librerías nuevas
    pip install pymupdf pillow
Comando completo:
    pip install jinja2 playwright openai python-docx pypdf pymupdf pytesseract Pillow
    python -m playwright install chromium
Y (opcional, para OCR de imágenes) Tesseract-OCR en el sistema.

---

## v2.1
- Panel de Mantenimiento (cambiar/limpiar/probar API key, resetear config, abrir carpeta).
- Detección de normativas (campo `normativa`).

## v2.0
- Auto-generación de `datos_materiales.json` leyendo fichas + ChatGPT (marca, descripción).

## v1.0
- Interfaz tkinter para ejecutar `generate_caratulas.py` sin consola.
