# MEMORIA COMPLETA — Generador de Submittals ES · v2.5.1

> Documento de traspaso para continuar el desarrollo (incluido en Claude Code).
> Escrito para que otra persona/sesión entienda el proyecto sin preguntar.

---

## 1. Resumen ejecutivo
- **Proyecto:** Generador de Submittals — ES Constructora.
- **Versión actual:** v2.5.1.
- **Estado:** funcional / en producción interna. Núcleo (~95%) completo; pendiente
  validación en vivo de SICOP y pruebas de campo (ver §11 y CHECKLIST-QA.md).
- **Última actualización:** 2026-07-17.
- **Responsable:** Adrián Castro (ES Consultoría y Construcción S.A.).

## 2. Descripción del proyecto
Aplicación de escritorio (Windows) que **automatiza la elaboración de "submittals"**
(fichas de aprobación de materiales/equipos) para obra pública en Costa Rica. Por
cada material, ubicado en carpetas por disciplina, la app lee sus fichas técnicas,
extrae con IA los datos clave (marca, descripción, normativa) y genera una
**carátula PDF** de portada y un **compilado PDF** (carátula + fichas).

Sirve para preparar rápido y de forma consistente los paquetes que se entregan a
la institución contratante (p. ej. Municipalidad de Desamparados, Ministerio de
Salud). Puede además **buscar la licitación en SICOP** para pre-llenar los datos
del proyecto.

**Usuario final:** personal de ES Constructora sin conocimientos de programación
(interfaz gráfica; también empaquetable como `.exe`).

**Contexto:** Costa Rica; licitaciones públicas (SICOP); materiales de construcción
clasificados por disciplina (arquitectónico, mecánico, estructural, eléctrico).

## 3. Tecnología utilizada
- **Lenguaje:** Python 3.9+ (probado con 3.10/3.11).
- **GUI:** Tkinter (stdlib).
- **IA:** OpenAI — `gpt-4o-mini` (extracción de fichas) y `gpt-4o` (Vision para SICOP).
- **Automatización web:** Playwright (Chromium) para SICOP y para renderizar PDF.
- **Templates:** Jinja2 (HTML → PDF).
- **PDF:** `pypdf` (leer/fusionar), `pymupdf` (fitz, OCR de PDF escaneado),
  Playwright/WeasyPrint/pdfkit (render HTML→PDF).
- **Imágenes/OCR:** Pillow + `pytesseract` (requiere Tesseract-OCR del sistema).
- **DOCX:** `python-docx`.
- **HTTP:** `requests`, `beautifulsoup4` (utilitarios; SICOP real usa Playwright+Vision).
- **Config/datos:** JSON.
- **Excel:** `openpyxl` **solo** en scripts auxiliares (la app NO genera el Excel; ver §5, nota).
- **Empaquetado:** PyInstaller.

> Nota de precisión: el código **no** usa `PyPDF2`, `pdf2image` ni `langdetect`.
> La detección/traducción de idioma la hace el propio modelo de OpenAI.

## 4. Estructura del proyecto
```
C:\Users\castr\Downloads\Submitals ES\
├─ submitals_gui.py                     # GUI principal (v2.5.1)  ← se modifica
├─ generate_caratulas.py                # MOTOR render PDF        ← extendido, estable
├─ template_caratula.html               # carátula CLÁSICA (roja #E11D2D)
├─ template_ministerio_salud.html       # carátula Ministerio de Salud (azul #001F60)
├─ submitals_config.json                # configuración del usuario (API key cifrada)
├─ datos_materiales.json                # SALIDA: lista de materiales (generada)
├─ generate_caratulas.log               # SALIDA: log de la última corrida
├─ generate_caratulas_report.txt        # SALIDA: reporte resumen
├─ requirements.txt                     # dependencias
├─ Tabla visual refresh\assets\
│   ├─ logo_es_crop.png                 # logo ES (carátula clásica)
│   └─ ministerio_salud_banner.png      # banner Ministerio (carátula MS)
├─ ARQUITECTONICOS\   (ARQ01-… )        # disciplina 1
├─ ESTRUCTURALES\     (ESTR01-… )       # disciplina 2
├─ MECANICOS\         (MEC01-… )        # disciplina 3
├─ ELECTRICOS\        (ELEC01-… )       # disciplina 4 (v2.5)
├─ CHANGELOG_v2.x.md / MEMORIA-*.md     # documentación por versión
└─ dist\GeneradorSubmittalsES.exe       # (si se compiló con PyInstaller)
```
Dentro de cada subcarpeta de material:
```
ARQ01-BLOCK CONCRETO 15x20x40 CM\
├─ (fichas originales: *.pdf / *.jpg / *.png / *.docx)   ← las coloca el usuario
├─ CARATULA ARQ01-BLOCK CONCRETO 15x20x40 CM.pdf         ← portada (generada)
└─ ARQ01-BLOCK CONCRETO 15x20x40 CM-CMP.pdf              ← compilado (generado)
```

## 5. Funcionalidades implementadas (v2.5.1)
- GUI Tkinter con validación de entradas y barra de progreso (5 fases).
- OpenAI: extracción de datos de fichas (`gpt-4o-mini`) + **SICOP por Vision** (`gpt-4o`).
- Lectura de fichas: PDF (texto), **PDF escaneado por OCR** (PyMuPDF+Tesseract),
  imágenes (JPG/PNG/BMP/TIFF por OCR) y DOCX. Multi-documento por carpeta con fusión.
- **Traducción automática**: si la ficha no está en español, el modelo la traduce;
  se guardan `idioma_original` y `fue_traducido`.
- Generación de **carátulas** (motor Jinja2 + Playwright/WeasyPrint/pdfkit).
- **Compilados** PDF (carátula pág.1 + fichas pág.2+).
- **4 disciplinas:** ARQ, MEC, ESTR, ELEC. **2 carátulas:** clásica y Ministerio.
- **Menú "Datos del proyecto"** (para la carátula del Ministerio); `Versión`=v1 y
  `Registro`=consecutivo automáticos.
- **Búsqueda SICOP** (Playwright + GPT-4o Vision) para pre-llenar datos.
- Logs detallados + reporte.
- **Instancia única** (no múltiples ventanas) y control de hilo.
- Seguridad: la API key no se muestra ni se copia.
- Bootstrap: instala dependencias faltantes y Chromium al arrancar (modo `.py`).
- Empaquetable a `.exe` (PyInstaller).

> **Nota importante (Excel):** la **Guía Materiales.xlsx** que existe en la carpeta
> fue generada por **scripts auxiliares** en fases previas del proyecto, **no** por
> `submitals_gui.py`. Si se quiere que la app genere/actualice ese Excel
> automáticamente, es una **feature pendiente** (ver §11). Hoy la salida de la app
> es: PDFs por carpeta + `datos_materiales.json` + log + reporte.

## 6. Configuración y credenciales
- **API key necesaria:** OpenAI (`sk-...`), usada tanto para ChatGPT como para
  GPT-4o Vision (SICOP). **Una sola** desde v2.5.1.
- Se ingresa en la GUI (campo API Key) y se guarda **cifrada (base64)** en
  `submitals_config.json → api.openai_key_encrypted`.
- El panel **🔧 Mantenimiento** permite cambiar/limpiar la key (nunca se muestra).
- `submitals_config.json` (estructura v2.5.1):
```json
{
  "version": "2.5.1",
  "caratula_seleccionada": "clasica | ministerio_salud",
  "carpetas_recientes": ["..."],
  "ultimo_json": "",
  "opciones": {"solo_faltantes": true, "forzar_regeneracion": false,
               "mostrar_log": true, "generar_json_automatico": true,
               "usar_json_existente": false},
  "datos_proyecto": {"proyecto":"","cliente":"","contrato":"","monto":"",
                     "plazo":"","nombre_cargo":"","fecha":"","fecha_emision":""},
  "api": {"openai_key_encrypted":"", "anthropic_key_encrypted":"(obsoleto)",
          "ultima_validacion":""},
  "mantenimiento": {"ultima_limpieza_cache":"", "veces_reseted":0}
}
```
> La base64 **oculta** la clave pero NO es cifrado seguro. No compartir el config.

## 7. Dependencias y librerías
Ver `requirements.txt`. Resumen:
```
pip install openai jinja2 playwright pypdf pymupdf pytesseract Pillow python-docx requests beautifulsoup4
python -m playwright install chromium
```
Sistema: Python 3.9+, Chromium (vía Playwright), Tesseract-OCR (opcional, para OCR
de imágenes). `openpyxl` solo si se regeneran los Excel auxiliares.

## 8. Versión actual: v2.5.1
- SICOP con **OpenAI GPT-4o Vision** (reemplaza Anthropic de v2.5) → **una sola API**,
  ~50% menos costo.
- Disciplina **ELECTRICOS** completa (de v2.5).
- Se mantienen de v2.4: fix de múltiples ventanas, traducción automática, seguridad
  de API key, fix de página en blanco del Ministerio, compilados, OCR mejorado.
- Ver `CHANGELOG-COMPLETO.md` para el historial.

## 9. Cómo usar el programa
1. Ejecutar `python submitals_gui.py` (o `GeneradorSubmittalsES.exe`).
2. Primera vez: se instalan dependencias y Chromium (ventana de preparación).
3. Ingresar la **API Key de OpenAI** y pulsar "Test Conexión".
4. Elegir **tipo de carátula** (Clásica o Ministerio de Salud).
5. (Opcional) **Buscar en SICOP** el número de procedimiento para pre-llenar datos,
   o abrir **"Datos del proyecto"** e ingresarlos a mano (para la del Ministerio).
6. Elegir la **carpeta base** (debe contener ARQUITECTONICOS/MECANICOS/ESTRUCTURALES/ELECTRICOS).
7. Colocar las **fichas técnicas** dentro de cada subcarpeta de material.
8. Opciones: "Solo faltantes" (incremental) o "Forzar regeneración" (sobrescribe).
9. Pulsar **GENERAR**. Al terminar: PDFs en cada carpeta + `datos_materiales.json`
   + log/reporte.

**Archivos generados:** `CARATULA <CONS>-<NOMBRE>.pdf`, `<CONS>-<NOMBRE>-CMP.pdf`,
`datos_materiales.json`, `generate_caratulas.log`, `generate_caratulas_report.txt`.

## 10. Problemas conocidos y soluciones
- **API key inválida:** debe ser de OpenAI (`sk-…`) con créditos. Cambiar en 🔧 Mantenimiento.
- **SICOP no encuentra:** verificar el número (se pasa a MAYÚSCULAS); revisar internet;
  si el portal cambió, la *navegación* puede fallar (la lectura por Vision es robusta) →
  ingresar datos manualmente. Ajustar selectores en `_sicop_screenshot()` si hace falta.
- **Múltiples ventanas en .exe:** resuelto en v2.4/v2.5.1 (instancia única + no
  relanzar el .exe). Si reaparece, revisar que el bootstrap no ejecute `subprocess`
  cuando `sys.frozen`.
- **Tesseract no encontrado:** opcional; instalar desde UB-Mannheim si se necesita OCR
  de imágenes.
- **PDF bloqueado al forzar:** cerrar el PDF abierto en el visor y reintentar.

## 11. Próximos pasos / mejoras futuras
**Alta:** validar SICOP en vivo (20+ números), pruebas con 10+ proyectos reales,
afinar selectores de navegación SICOP, medir/optimizar velocidad.
**Media:** que la app **genere el Excel** (Guía Materiales) con columnas
Consecutivo/Familia/Descripción/Normativa/Estado/Idioma; más templates de
instituciones; editor de templates; historial de búsquedas SICOP; backup de config.
**Baja:** interfaz web, base de datos central, API REST, notificaciones.

## 12. Cómo compilar a .exe
```cmd
cd C:\Users\castr\Downloads\Submitals ES
pip install pyinstaller
pyinstaller --onefile --windowed --name "GeneradorSubmittalsES" ^
  --collect-all playwright --collect-all jinja2 --collect-all pypdf ^
  --collect-all fitz --collect-all bs4 ^
  --add-data "template_caratula.html;." ^
  --add-data "template_ministerio_salud.html;." ^
  --add-data "Tabla visual refresh/assets/logo_es_crop.png;Tabla visual refresh/assets" ^
  --add-data "Tabla visual refresh/assets/ministerio_salud_banner.png;Tabla visual refresh/assets" ^
  submitals_gui.py
```
Resultado: `dist\GeneradorSubmittalsES.exe`. En la PC destino puede faltar Chromium/
Tesseract: el programa lo verifica al abrir (y **no** se relanza a sí mismo).

## 13. Archivos críticos
- **Tocar con cuidado / no romper:** `generate_caratulas.py` (motor; fue extendido
  con `normativa` y `extra_ctx`, es estable), `template_caratula.html`,
  `template_ministerio_salud.html` (su CSS está calibrado para 1 página).
- **Editable:** `submitals_gui.py` (interfaz/lógica).
- **Generados (no editar a mano):** `datos_materiales.json`, `generate_caratulas.log`,
  `generate_caratulas_report.txt`, y `submitals_config.json` (lo escribe la app).

## 14. Convenciones
- Carpetas madre en MAYÚSCULAS; subcarpetas `XX##-NOMBRE` en MAYÚSCULAS.
- Python: `snake_case` funciones/variables, `PascalCase` clases, 4 espacios, UTF-8.
- Comentarios y textos de UI en español.
- Log: `[TIMESTAMP] NIVEL CONSECUTIVO mensaje` (DEBUG/INFO/WARNING/ERROR/CRITICAL).

## 15. Contacto y referencias
- Desarrollador: Adrián Castro — ES Consultoría y Construcción S.A.
- Proyecto de referencia: Bodega Municipalidad de Desamparados (Costa Rica).
- SICOP: https://www.sicop.hacienda.go.cr — OpenAI: https://platform.openai.com
- Playwright: https://playwright.dev — PyInstaller: https://pyinstaller.org

## 16. Continuar en Claude Code
Ver **GUÍA-CLAUDE-CODE.md**. Resumen:
```bash
cd "C:\Users\castr\Downloads\Submitals ES"
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
python submitals_gui.py
```

## 17. Testing y validación
Ver **CHECKLIST-QA.md** para los casos de prueba y criterios de éxito.

---

### Arquitectura interna (referencia rápida para devs)
- `submitals_gui.py`
  - `bootstrap()` / `_arrancar()`: verificación e instalación de deps + splash.
  - `instancia_unica()`: candado por socket (fix múltiples ventanas).
  - `construir_materiales()`: escanea carpetas, lee fichas, llama a ChatGPT
    (`extraer_con_chatgpt` → marca, descripción, normativa, idioma, traducido).
  - `hilo_trabajo(modo, base, json, api_key, opciones, caratula, datos_proyecto, q, cancelar)`:
    genera JSON (auto) o lo lee (existente) → FASE 4 carátulas → FASE 5 compilados.
  - SICOP: `_sicop_screenshot()` (Playwright) + `_sicop_vision()` (OpenAI gpt-4o) +
    `buscar_licitacion_sicop()` + `hilo_sicop()`.
  - `SubmitalsGUI(tk.Tk)`: toda la interfaz, la cola de eventos (`_revisar_cola`),
    panel Mantenimiento, datos de proyecto, selector de carátula, SICOP.
- `generate_caratulas.py`
  - `process_material(item, template, engines, extra_ctx=None)`: valida, salta
    vacías/incompletas, salta si ya existe la carátula (incremental), renderiza y
    escribe el PDF. `extra_ctx` inyecta los campos del Ministerio y vacía
    `SIN ESPECIFICAR`/`POR DEFINIR`.
  - `available_engines()`: Playwright → WeasyPrint → pdfkit.
- Variables Jinja2:
  - Clásica: `logo_path, consecutivo, nombre_comercial, fabricante, descripcion_tecnica, normativa`.
  - Ministerio: además `logo_ministerio, registro, version, proyecto, cliente, plazo,
    contrato, monto, nombre_cargo, fecha, fecha_emision, documentacion_tecnica,
    observaciones_material, estado, fecha_revision, observaciones_respuesta, revisa`.
- Campos JSON por material: `consecutivo, nombre, categoria, marca, descripcion,
  normativa, idioma_original, fue_traducido, documentos_encontrados,
  compilado_generado, estado, carpeta_vacia, ruta_carpeta`.
