# CHECKLIST QA — Generador de Submittals v2.5.2

Casos de prueba para validar la versión. Marcar ✅/❌ y anotar observaciones.
"Cómo probar" asume ejecución en Windows (`python submitals_gui.py` o el `.exe`).

## A. Arranque y dependencias
- [ ] **A1** En una PC con solo Python, al abrir se instalan las dependencias y
  Chromium sin errores. *Cómo:* borrar venv / usar PC limpia → `python submitals_gui.py`.
  *Éxito:* la ventana de preparación termina y abre la app.
- [ ] **A2** Corre con Python 3.9+; muestra mensaje claro si es menor.
- [ ] **A3** (Empaquetado) el `.exe` NO ejecuta pip ni se relanza. *Éxito:* no aparecen
  ventanas múltiples.

## B. Instancia única (fix crítico)
- [ ] **B1** Abrir el `.exe` **10 veces seguidas** → existe **1 sola** ventana; las
  demás avisan "ya está abierto" y se cierran. *Criterio:* Task Manager muestra 1 proceso.
- [ ] **B2** Clic en GENERAR **5 veces rápido** → solo se procesa una vez ("ya está
  generando"). 
- [ ] **B3** Memoria estable durante el proceso (no crece indefinidamente).

## C. API key (seguridad)
- [ ] **C1** En 🔧 Mantenimiento NO existe botón "Copiar" y la clave nunca se muestra
  (solo "✅ Configurada" / "Sin configurar").
- [ ] **C2** "Cambiar clave" valida formato `sk-`, la prueba con OpenAI y la guarda.
- [ ] **C3** "Test Conexión" con key válida → ✅; con key inválida → ❌ mensaje claro.
- [ ] **C4** La API key no aparece en `generate_caratulas.log` ni en el reporte.

## D. Búsqueda SICOP (Playwright + GPT-4o Vision)
- [ ] **D1** Ingresar `2024-000123-01-cb` → el campo lo pasa a **MAYÚSCULAS**.
- [ ] **D2** Buscar **10+ números reales** → extrae proyecto/cliente/plazo/monto y
  ofrece "usar estos datos" (pre-llena "Datos del proyecto").
- [ ] **D3** Buscar **5+ números inválidos/inexistentes** → error *graceful* y opción
  de ingresar manual (no rompe).
- [ ] **D4** Formato incorrecto (ej. `abc`) → mensaje "Formato incorrecto…".
- [ ] **D5** Sin API key de OpenAI → pide ingresarla (no intenta buscar).
- [ ] **D6** Tarda ~2-5 s por búsqueda; la ventana no se congela (corre en hilo).
- [ ] **D7** Screenshot borroso → Vision aún intenta; si no, reporta y permite manual.
> Nota: si la navegación no llega a la pantalla de resultados (SICOP cambió), ajustar
> `_sicop_screenshot()`. La lectura por Vision es la parte robusta.

## E. Disciplinas (ARQ, MEC, ESTR, ELEC)
- [ ] **E1** Con carpetas de las 4 disciplinas y fichas, GENERAR crea las carátulas.
- [ ] **E2** **ELEC##** genera `CARATULA ELEC##-...pdf` correctamente.
- [ ] **E3** Compilado `ELEC##-...-CMP.pdf` = carátula pág.1 + fichas pág.2+.
- [ ] **E4** Orden en el JSON: ARQ → ESTR → MEC → ELEC.

## F. Lectura de fichas y traducción
- [ ] **F1** PDF de texto → extrae datos.
- [ ] **F2** PDF escaneado/imagen → OCR (requiere Tesseract) lo lee.
- [ ] **F3** Carpeta con 2+ fichas → las fusiona en un solo material.
- [ ] **F4** Ficha en inglés/otro idioma → se traduce; `fue_traducido=true` en el JSON
  y aviso `[TRADUCCION]` en el log.
- [ ] **F5** Sin información suficiente → los campos quedan **en blanco** (no inventa;
  "SIN ESPECIFICAR"/"POR DEFINIR" salen vacíos en la carátula).

## G. Carátulas y compilados
- [ ] **G1** Carátula **Clásica** se ve correcta (logo ES, rojo #E11D2D).
- [ ] **G2** Carátula **Ministerio de Salud** se ve idéntica al formato oficial
  (azul #001F60, banner) y **en 1 página** (sin hoja en blanco).
- [ ] **G3** Ministerio: `Versión`=v1 y `Registro`=consecutivo automáticos; datos de
  proyecto correctos.
- [ ] **G4** "Solo faltantes" salta lo ya generado; "Forzar" **sobrescribe**.
- [ ] **G5** Compilado abre correctamente en Adobe Reader; total = 1 + N fichas.

## H. Salidas y logs
- [ ] **H1** `datos_materiales.json` incluye `idioma_original`, `fue_traducido`,
  `documentos_encontrados`, `compilado_generado`.
- [ ] **H2** `generate_caratulas.log` y `generate_caratulas_report.txt` se generan y
  son legibles.
- [ ] **H3** Barra de progreso pasa por las fases (lectura/IA → carátulas → compilados).

## I. Compilación a .exe
- [ ] **I1** PyInstaller compila sin errores (ver comando en la memoria §12).
- [ ] **I2** El `.exe` incluye las 2 plantillas y los 2 logos (embebidos con --add-data).
- [ ] **I3** En PC destino sin Chromium/Tesseract, el `.exe` avisa y no se cae.

## J. Compilado por disciplina (v2.5.2)
- [x] **J1** Con carátulas ya generadas en ARQ01/ARQ02/ARQ03, el botón genera
  `COMPILADO-ARQUITECTONICOS.pdf` en la raíz de `ARQUITECTONICOS\`. *Verificado
  en headless (pypdf) con copia de datos reales: 10 materiales, 39 páginas.*
- [x] **J2** Orden correcto: carátula + fichas de ARQ01, luego ARQ02, luego ARQ03…
- [x] **J3** Material sin carátula generada → se omite del compilado con aviso
  (`WARN`), no detiene el proceso.
- [x] **J4** Disciplina inválida o carpeta inexistente → error claro, sin excepción.
- [x] **J5** No usa OpenAI (solo `pypdf`); funciona sin conexión a internet.
- [ ] **J6** Probar en la GUI real con las 4 disciplinas y datos de producción
  (pendiente de validación por la usuaria final).
- [x] **J7** No bloquea ni es bloqueado por el proceso principal de GENERAR
  (se deshabilitan mutuamente mientras uno corre).

### Criterio general de aprobación
Todos los B (instancia única), C1–C4 (seguridad) y E2/E3 (ELEC) deben pasar. SICOP
(D) se aprueba si D1, D3, D4, D5 pasan y D2 funciona en la mayoría de números reales;
si la navegación falla por cambios del portal, se documenta y se ajustan selectores.
