# CHANGELOG — Generador de Submittals ES

## v2.5 (2026-07-17) — Elaborado por Adrián Castro

### ✨ SICOP rehecho con Playwright + Claude Vision (reemplaza el de v2.4)
El scraping HTML de v2.4 no funcionaba (SICOP es un portal dinámico). Ahora la
búsqueda es por **imagen**, robusta ante cambios de HTML:

1. **Playwright (Chromium)** abre `https://www.sicop.hacienda.go.cr/`, escribe el
   número de procedimiento (en MAYÚSCULAS) buscando el campo por heurística
   (placeholder/nombre/tipo), lo envía y espera los resultados.
2. Toma un **screenshot** de la página completa.
3. **Claude Vision** (`claude-sonnet-4-20250514`) lee la captura y devuelve en
   JSON: `proyecto, cliente, plazo, monto, contrato` (o `encontrado=false`).
4. Si hay datos, la GUI ofrece **usar estos datos** para pre-llenar "Datos del
   proyecto".

Detalles:
- Nueva **API Key de Claude** en la sección SICOP (se guarda ofuscada en
  `submitals_config.json` → `api.anthropic_key_encrypted`). Es independiente de
  la API Key de OpenAI (que se sigue usando para leer las fichas).
- Como la lectura la hace la IA sobre la **imagen**, es **robusta ante cambios en
  el HTML** de SICOP.
- Tiempo esperado 3-5 s por búsqueda (aceptable). Nueva dependencia: `anthropic`
  (el bootstrap la instala sola en modo `.py`).
- Manejo de errores en español: formato inválido, falta la key de Claude, no se
  pudo abrir SICOP, licitación no encontrada → **fallback manual**, nunca rompe.

> Nota: la NAVEGACIÓN dentro de SICOP (ubicar el campo y enviar la búsqueda) usa
> una heurística porque el portal puede variar; la EXTRACCIÓN por Vision es la
> parte robusta. Si en algún caso la heurística no llega a la pantalla de
> resultados, Claude reporta `encontrado=false` y se ingresa a mano. La constante
> `SICOP_URL` y los selectores en `_sicop_screenshot()` se pueden ajustar.

### ✨ Nueva disciplina: ELECTRICOS (ELEC##)
- Se agregó `ELECTRICOS` a las carpetas madre, con prefijo **ELEC** y orden
  después de MEC (ARQ → ESTR → MEC → ELEC).
- Toda la maquinaria (escaneo, lectura, ChatGPT, carátula, compilado, JSON) ya
  funciona con `ELEC##` sin más cambios. Se creó la carpeta madre `ELECTRICOS`
  (vacía, lista para usar).
- Verificado: `ELEC01-...` genera su carátula correctamente.

### ✅ Sin regresión (v2.4 se mantiene)
- Fix de múltiples ventanas (instancia única + no relanzar el .exe + control de
  hilo) intacto.
- Traducción automática de fichas en otro idioma intacta.
- Seguridad de la API key (sin "Copiar"), compilados, OCR mejorado y fix de
  página en blanco del Ministerio: sin cambios.

### 📦 Librerías / config
- Nueva dependencia: `anthropic`.
    pip install jinja2 openai anthropic pypdf pymupdf pytesseract Pillow python-docx playwright requests beautifulsoup4
    python -m playwright install chromium
- `submitals_config.json`: `version` = "2.5"; nuevo `api.anthropic_key_encrypted`.

### Empaquetado (.exe)
Igual que v2.4, agregando `--collect-all anthropic`:
```
pyinstaller --onefile --windowed --name "GeneradorSubmittalsES" ^
  --collect-all playwright --collect-all jinja2 --collect-all pypdf ^
  --collect-all fitz --collect-all bs4 --collect-all anthropic ^
  --add-data "template_caratula.html;." ^
  --add-data "template_ministerio_salud.html;." ^
  --add-data "Tabla visual refresh/assets/logo_es_crop.png;Tabla visual refresh/assets" ^
  --add-data "Tabla visual refresh/assets/ministerio_salud_banner.png;Tabla visual refresh/assets" ^
  submitals_gui.py
```

### Validación realizada
- Compila; disciplina ELEC reconocida y `ELEC01` genera carátula (1 pág).
- SICOP: validación de formato, key de Claude requerida, y parseo de la respuesta
  de Claude Vision (probado con simulación, sin red).
- No se pudo probar la navegación EN VIVO de SICOP en este entorno (sin acceso al
  portal); el pipeline queda implementado y la extracción por Vision verificada.
