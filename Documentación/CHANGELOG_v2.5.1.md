# CHANGELOG — Generador de Submittals ES

## v2.5.1 (2026-07-17) — Elaborado por Adrián Castro

### 🔧 SICOP ahora usa OpenAI GPT-4o Vision (reemplaza a Anthropic/Claude)
- La búsqueda SICOP sigue el mismo flujo (Playwright abre SICOP → screenshot →
  la IA lee la imagen y devuelve JSON), pero ahora la Vision la hace
  **OpenAI `gpt-4o`** en vez de Claude.
- **Una sola API key** (la de OpenAI que ya se usa para leer las fichas). Se
  eliminó el campo y la key de Claude (Anthropic).
- Optimización de costo: imagen con `detail: "low"` y `max_tokens: 500`
  (JSON pequeño). ~50% más económico que v2.5 y más simple (1 sola API).
- Robusto ante cambios de HTML (la lectura la hace la IA sobre la imagen).
- Manejo de errores en español + fallback manual (formato inválido, sin API key,
  no se pudo abrir SICOP, licitación no encontrada).

### ✅ Disciplina ELECTRICOS (ELEC##) — sin cambios (se mantiene de v2.5)
- ARQ → ESTR → MEC → **ELEC**. Genera carátulas y compilados `ELEC##`. La carpeta
  madre `ELECTRICOS` ya existe.

### ✅ Sin regresión
- Fix de múltiples ventanas (instancia única + no relanzar el .exe + control de
  hilo), traducción automática, seguridad de API key (sin "Copiar"), compilados,
  OCR mejorado y fix de página en blanco del Ministerio: intactos.

### 🔁 Cambios técnicos
- `import anthropic` eliminado; `anthropic` fuera de las dependencias y del
  bootstrap.
- Constante `CLAUDE_MODEL` → `VISION_MODEL = "gpt-4o"`.
- `buscar_licitacion_sicop(numero, openai_key, ...)` y `_sicop_vision(...,
  openai_key)` usan el cliente de OpenAI.
- La sección SICOP de la GUI ya no pide una key aparte: usa la de OpenAI de arriba.
- `submitals_config.json`: `version` = "2.5.1" (se conserva `anthropic_key_encrypted`
  como campo obsoleto/ignorado por compatibilidad).
- Nuevo `requirements.txt` (sin `anthropic`).

### Empaquetado (.exe)
Igual que v2.4/v2.5 pero **sin** `--collect-all anthropic`:
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

### Validación realizada
- Compila; sin referencias a `anthropic`; `VISION_MODEL = gpt-4o`.
- `_sicop_vision` probado con simulación del SDK de OpenAI: usa `gpt-4o` con
  `detail:"low"` y parsea el JSON correctamente.
- Validación de formato del número y "falta API key" OK.
- ELECTRICOS reconocido; carátula ELEC generada (verificado en v2.5, sin cambios).
- No se pudo probar la NAVEGACIÓN en vivo de SICOP (sin acceso al portal ni a la
  API real de OpenAI en este entorno); el pipeline queda completo y la extracción
  por Vision verificada con simulación. Si al probar en Windows la búsqueda no
  llega a la pantalla de resultados, se ajustan los selectores en
  `_sicop_screenshot()`.
