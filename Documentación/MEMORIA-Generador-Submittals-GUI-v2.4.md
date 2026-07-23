# Memoria — Generador de Submittals ES · v2.4

Elaborado por Adrián Castro. Documento de referencia de la versión 2.4.

## Qué cambió en v2.4 (resumen)
1. **Fix crítico del bug de "múltiples ventanas" en el .exe.**
2. **Seguridad:** la API key ya no se puede copiar (solo estado).
3. **Traducción automática** de fichas en otro idioma.
4. **Integración SICOP** para buscar licitaciones (best-effort).
5. **Fix** de la página en blanco en la carátula del Ministerio.

---

## 1) El bug de las múltiples ventanas (explicación y solución)
**Por qué pasaba solo en el .exe:** al empaquetar con PyInstaller, `sys.executable`
apunta al propio `.exe`, no a `python.exe`. El auto-instalador de v2.3 hacía
`subprocess([sys.executable, "-m", "pip"...])`, así que **cada arranque relanzaba
el .exe**, que a su vez relanzaba otro… hasta colapsar la PC. En `.py` no pasaba
porque ahí `sys.executable` sí es python.

**Cómo quedó resuelto:**
- Si el programa corre empaquetado, el bootstrap **no ejecuta ningún subprocess**.
- `multiprocessing.freeze_support()` al inicio.
- **Instancia única** (candado por socket): la segunda ejecución avisa y se cierra.
- **Control de hilo**: si ya está generando, ignora nuevos clics.
- Botón GENERAR deshabilitado durante el proceso; recursos liberados con `close()`.

Prueba recomendada tras compilar: abrir el `.exe` varias veces → debe existir
**una sola** ventana; dar clic repetido en GENERAR → solo un proceso.

## 2) Cambiar la API key de forma segura
Panel **🔧 Mantenimiento**: ya no hay botón "Copiar" ni se muestra la clave.
Solo aparece el **estado** ("✅ Configurada"). Para cambiarla, escríbala en
"Cambiar clave" y pulse OK (se prueba con OpenAI y se guarda). También puede
"Limpiar" la clave. La clave se guarda ofuscada (base64) en el config.

## 3) Traducción automática
Al leer las fichas, ChatGPT detecta el idioma; si no es español, **traduce** y
extrae marca/descripción/normativa de la versión en español. En el JSON cada
material lleva `idioma_original` y `fue_traducido`. En el log aparece un aviso
`[TRADUCCION]` cuando ocurre. No hay que configurar nada.

## 4) Cómo usar SICOP
En la sección **"🔍 Búsqueda de licitación SICOP"**: escriba el número de
procedimiento (se pasa a MAYÚSCULAS automáticamente, p. ej. `2024-000123-01-CB`)
y pulse **Buscar**. Si encuentra la licitación, ofrece usar los datos para
pre-llenar proyecto, cliente, plazo, monto y el contrato. Si no puede (formato
inválido, sin conexión, o el portal no expone la consulta), avisa y usted puede
ingresar los datos a mano en **"Datos del proyecto"**. Nunca rompe el programa.

> Nota técnica: SICOP es un portal dinámico sin un endpoint público simple, así
> que la búsqueda es **best-effort**. Si su organización dispone de un endpoint o
> API, se ajusta dentro de la función `buscar_licitacion_sicop()`.

## 5) Página en blanco del Ministerio — resuelto
Era el `min-height:1056px` fijo de la hoja, que en Chromium empujaba una 2ª
página vacía. Se añadió `min-height:0 !important` en `@media print` y
`page-break-inside: avoid`. La carátula queda en 1 página y el compilado ya no
trae la hoja en blanco.

---

## Instalación / ejecución (recordatorio)
- PC con solo Python: `python submitals_gui.py` → el programa instala lo que falte.
- Dependencias: `jinja2 openai pypdf pymupdf pytesseract Pillow python-docx
  playwright requests beautifulsoup4` + `python -m playwright install chromium`.
- OCR de imágenes: Tesseract-OCR (opcional).
- Empaquetado `.exe`: ver el comando PyInstaller con `--add-data` en
  `CHANGELOG_v2.4.md` (embebe plantillas y logos).

## Estructura del JSON por material (v2.4)
`consecutivo, nombre, categoria, marca, descripcion, normativa, idioma_original,
fue_traducido, documentos_encontrados, compilado_generado, estado, carpeta_vacia,
ruta_carpeta`.
