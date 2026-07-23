# CHANGELOG — Generador de Submittals ES

## v2.1 (2026-07-16)

### ✨ Nuevo: Panel de Mantenimiento
- Botón **🔧 Mantenimiento** (arriba a la derecha de la sección API) que abre un diálogo modal.
- **API Key:** muestra la clave actual enmascarada (`sk-proj-••••••••••••`), con botones **Copiar** (al portapapeles) y **Limpiar**.
- **Cambiar clave:** campo para escribir una nueva key; valida el formato (`sk-`), la prueba contra OpenAI y, si es válida, la guarda y cierra el diálogo mostrando "✅ API key actualizada".
- **Reset:** botones **Limpiar caché** (borra archivos temporales de render y `__pycache__`), **Resetear config** (restaura `submitals_config.json` a valores por defecto) y **Abrir carpeta config**.
- **Info:** versión, fecha de última validación de la API, ruta del config y proyecto actual.
- El botón de mantenimiento se **deshabilita mientras hay un proceso en curso**.

### ✨ Nuevo: Detección automática de normativas
- La IA ahora también extrae **normas/estándares** de cada ficha (ASTM, ISO, DIN, EN, NBR, NTC, INEN, etc.).
- Nuevo campo **`normativa`** en cada material del JSON.
- Si no se detectan normas → `"SIN ESPECIFICAR"`. Si hay varias → separadas por comas. Máximo 500 caracteres (se truncan en la última coma).
- La barra de progreso indica: *"Extrayendo marca, descripción y normativas: ESTR15 (45/70)"*.

### 🔄 Cambios
- **Estructura JSON:** se agregó el campo `normativa` a cada material.
- **Prompt de ChatGPT:** ahora pide 3 campos (marca, descripción, normativa) en vez de 2.
- **`extraer_con_chatgpt()`** devuelve 3 valores; `construir_materiales()` los guarda.
- **`template_caratula.html`:** el campo "Normativa / Especificación aplicable" ahora recibe `{{ normativa }}` (queda vacío si es "SIN ESPECIFICAR").
- **`generate_caratulas.py`:** mapea `normativa` del JSON a la variable `{{ normativa }}` de la plantilla.
- **`submitals_config.json`:** nuevos campos `version`, `api.ultima_validacion` y bloque `mantenimiento` (`ultima_limpieza_cache`, `veces_reseted`).
- **Guía Materiales.xlsx:** nueva columna **Normativa** (Consecutivo | Familia | Descripción | Normativa | Estado).

### ✅ Compatibilidad
- Un `datos_materiales.json` de **v2.0 (sin `normativa`)** se carga sin problemas: el programa agrega `normativa = "SIN ESPECIFICAR"` automáticamente.
- Un JSON de v2.1 abierto por una versión anterior simplemente ignora el campo extra.

### 🐛 Correcciones / robustez
- Si ChatGPT devuelve un JSON sin el campo `normativa`, se usa el valor por defecto y se registra un aviso (no rompe el proceso).
- Manejo de errores de API key con mensajes en español y sugerencia del enlace de OpenAI.

---

## v2.0
- Auto-generación de `datos_materiales.json`: lectura de fichas (PDF / imagen con OCR / DOCX) y extracción de marca + descripción con ChatGPT (gpt-4o-mini).
- Sección "Configuración API", modos "Generar automático" vs "Usar JSON existente", threading con barra de progreso y botón Cancelar.

## v1.0
- Interfaz tkinter para ejecutar `generate_caratulas.py` sin línea de comandos: selección de carpeta y JSON, opciones (solo faltantes / forzar / mostrar log), progreso y resultados.
