# MEMORIA — Generador de Submittals ES (GUI)

> Documento de traspaso para continuar el desarrollo en otro chat sin perder contexto. Complementa a `MEMORIA-Proyecto-Submitals-ES.md` (que documenta el motor y el proyecto de la Bodega Desamparados).

---

## 1. RESUMEN EJECUTIVO

| Dato | Valor |
|---|---|
| **Nombre** | Generador de Submittals - ES Constructora |
| **Versión** | 1.0 |
| **Archivo principal** | `submitals_gui.py` |
| **Propósito** | Interfaz gráfica (tkinter) para que usuarias sin conocimiento de Python ejecuten `generate_caratulas.py` (genera carátulas PDF de submittals) de forma segura e intuitiva. Entregable final: `.exe` de Windows vía PyInstaller. |
| **Estado actual** | **FUNCIONAL.** Lógica no-GUI probada end-to-end (generación, modo incremental, forzar regeneración, errores). GUI verificada por diseño; pendiente prueba visual en Windows y empaquetado real del .exe. |
| **Última actualización** | 2026-07-16 |

---

## 2. ESTRUCTURA DE ARCHIVOS Y UBICACIÓN

**Ruta base del proyecto:** `C:\Users\castr\Downloads\Submitals ES`

### 2.1 Archivos relacionados

| Archivo | Qué es / cómo se usa |
|---|---|
| `submitals_gui.py` | **La GUI (este proyecto).** Se ejecuta con `python submitals_gui.py` o como .exe. Debe estar/apuntar a la carpeta que contiene el motor. Archivo único, ~760 líneas, comentado en español. |
| `submitals_config.json` | Configuración persistente de la GUI. Se crea/actualiza solo, **junto al .exe** (o junto al .py en desarrollo). Ver sección 7. |
| `generate_caratulas.py` | **El motor. NO MODIFICAR.** Genera los PDFs a partir del JSON + template. La GUI lo carga como módulo desde la carpeta base seleccionada. |
| `template_caratula.html` | Plantilla Jinja2 de la carátula (tamaño carta, rojo #E11D2D, azul #1F3864). Variables: `{{ logo_path }}`, `{{ consecutivo }}`, `{{ nombre_comercial }}`, `{{ fabricante }}`, `{{ descripcion_tecnica }}`. |
| `datos_materiales.json` | Entrada del motor: 70 materiales. Ver estructura en 2.2. |
| `Guía Materiales.xlsx` | Índice Excel (3 hojas: Arquitectónicos, Estructurales, Mecánicos). Columnas: Consecutivo, Familia, Descripción, Estado. |
| `Tabla visual refresh\assets\logo_es_crop.png` | Logo ES usado en la carátula. El motor lo exige. |
| `generate_caratulas.log` | Log detallado de la última corrida (lo escribe el motor). |
| `generate_caratulas_report.txt` | Reporte resumen de la última corrida (botón "Ver Log Completo" lo abre). |
| `dist\GeneradorSubmittalsES.exe` | Ejecutable generado con PyInstaller (comando exacto en sección 10). |
| `INSTRUCCIONES.txt` | Guía paso a paso para empaquetar y distribuir. |

### 2.2 Estructura del JSON de datos (ejemplo)

```json
{
  "materiales": [
    {
      "consecutivo": "ARQ01",
      "nombre": "BLOCK CONCRETO 15x20x40 CM",
      "marca": "PRODUCTOS DE CONCRETO",
      "descripcion": "Bloque de concreto de alta resistencia",
      "estado": "FICHA_DISPONIBLE",
      "carpeta_vacia": false,
      "ruta_carpeta": "C:\\Users\\castr\\Downloads\\Submitals ES\\ARQUITECTONICOS\\ARQ01-BLOCK"
    }
  ]
}
```

Los 7 campos son obligatorios. `estado` ∈ {`FICHA_DISPONIBLE`, `CARPETA_VACÍA`, `FICHA_INCOMPLETA`}. Solo se genera PDF si `estado == "FICHA_DISPONIBLE"` y `carpeta_vacia == false`.

### 2.3 Carpetas de disciplina

```
Submitals ES\
├── ARQUITECTONICOS\   → ARQ01…ARQ18
├── ESTRUCTURALES\     → ESTR01…ESTR33
├── MECANICOS\         → MEC01…MEC19
```

Total 70 subcarpetas de material, formato `XX##-NOMBRE DEL MATERIAL` (ej. `ARQ07-CUBIERTA BANDEJA BLP-250 CAL.24 C-AISLANTE PIR`). El PDF de carátula se guarda DENTRO de cada subcarpeta como `CARATULA <consecutivo>-<nombre>.pdf`.

---

## 3. ARQUITECTURA DEL PROGRAMA

### 3.1 Diagrama de flujo general

```
 ┌────────────────────────── HILO PRINCIPAL (GUI / tkinter) ─────────────────────────┐
 │                                                                                   │
 │  Inicio → cargar_config() → SubmitalsGUI() → _cargar_valores_iniciales()          │
 │                                   │                                               │
 │        Usuaria elige carpeta/JSON │  _validar() habilita/deshabilita botón        │
 │                                   ▼                                               │
 │                         [🚀 GENERAR] → _generar()                                 │
 │                                   │  - advertencias (template/logo)               │
 │                                   │  - guarda config                              │
 │                                   │  - lanza Thread(hilo_generacion)  ────────────┼──┐
 │                                   ▼                                               │  │
 │        _revisar_cola() cada 100 ms (self.after) lee queue.Queue  ◄────────────────┼──┤
 │            ├─ "LOG"           → mini-log en pantalla                              │  │
 │            ├─ "PDF_GENERATED" → barra de progreso + contadores                    │  │
 │            ├─ "WARN"          → línea de aviso                                    │  │
 │            ├─ "ERROR"         → pop-up de error, detiene                          │  │
 │            └─ "COMPLETE"      → 100%, tiempo, abre reporte si opción activa       │  │
 └───────────────────────────────────────────────────────────────────────────────────┘  │
                                                                                        │
 ┌────────────────────── HILO DE TRABAJO (hilo_generacion) ──────────────────────────┐  │
 │  1. Carga generate_caratulas.py con importlib desde la carpeta base  ◄────────────┼──┘
 │  2. Valida: jinja2, motor PDF, JSON, template, logo   (mensajes en español)       │
 │  3. Si "forzar": borra CARATULA*.pdf existentes                                   │
 │  4. for material in materiales:  gc.process_material(item, template, engines)     │
 │        └─ tras cada uno →  q.put(("PDF_GENERATED", i, total, stats))              │
 │  5. gc.write_report()  →  q.put(("COMPLETE", stats, segundos))                    │
 └───────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Componentes principales

- **Ventana principal (tkinter):** clase `SubmitalsGUI(tk.Tk)`, ventana fija 700×900, colores corporativos, 5 secciones (configuración, opciones, botón, progreso, resultados/acciones).
- **Thread de procesamiento:** función global `hilo_generacion(...)` que corre en un `threading.Thread(daemon=True)` y nunca toca widgets directamente.
- **Integración con el motor:** carga dinámica con `importlib` (ver sección 5). No se copia ni modifica código del motor.
- **Sistema de configuración:** `cargar_config()` / `guardar_config()` sobre `submitals_config.json` junto al .exe.

### 3.3 Clases y funciones clave

| Elemento (línea aprox.) | Qué hace | Recibe | Retorna |
|---|---|---|---|
| `app_dir()` (62) | Carpeta del .exe (frozen) o del .py | — | `Path` |
| `cargar_config()` (93) | Lee `submitals_config.json`, mezcla con defaults, tolera archivo corrupto | — | `dict` config |
| `guardar_config(cfg)` (109) | Escribe la config (fallo silencioso: no es crítico) | `dict` | — |
| `error_legible(e)` (120) | Traduce excepciones técnicas a español legible | `Exception` | `str` |
| `class Tooltip` (142) | Tooltip nativo (Toplevel amarillo) al pasar el mouse | widget, texto | — |
| `hilo_generacion(carpeta_base, ruta_json, opciones, q, cancelar)` (169) | Todo el trabajo pesado: carga motor, valida, borra si forzar, procesa materiales, reporte. Comunica TODO por la cola `q`. | rutas `str`, `dict` opciones, `queue.Queue`, `threading.Event` | — (eventos por cola) |
| `class SubmitalsGUI(tk.Tk)` (314) | Ventana principal | — | — |
| `_construir_ui()` (343) | Crea todos los widgets (secciones 1–5 de la GUI) | — | — |
| `_cargar_valores_iniciales()` (486) | Restaura carpeta/JSON de la config o defaults | — | — |
| `_carpeta_valida(ruta)` (502) | ¿Contiene ARQUITECTONICOS/MECANICOS/ESTRUCTURALES? | `str` | `bool` |
| `_json_valido(ruta)` (506) | ¿Parsea y tiene lista `materiales` no vacía? | `str` | `bool` |
| `_validar()` (514) | Actualiza etiquetas ✓/✗ y habilita/deshabilita botón principal | — | `bool` |
| `_examinar_carpeta()` / `_examinar_json()` (541/563) | Diálogos de selección + validación + guarda config | — | — |
| `_chk_solo()` / `_chk_forzar()` (582/586) | Checkboxes mutuamente excluyentes; forzar pide confirmación | — | — |
| `_generar()` (597) | Advertencias previas, reset visual, lanza el hilo | — | — |
| `_revisar_cola()` (642) | **Corazón de la GUI:** poll de la cola cada 100 ms, despacha eventos | — | (se re-agenda con `after`) |
| `_pintar_stats(st)` (686) | Convierte `stats` del motor en los 3 contadores de colores | `dict` stats | — |
| `_ver_log()` / `_abrir_resultados()` (712/727) | `os.startfile` sobre el reporte / carpeta de disciplina | — | — |
| `_nuevo_proceso()` / `_cerrar()` (743/758) | Reset de interfaz / cierre seguro (cancela hilo si corre) | — | — |

### 3.4 Flujo de ejecución paso a paso

1. `__main__` → `SubmitalsGUI()` → `mainloop()`.
2. `__init__`: carga config, crea variables tk, construye UI, restaura valores, valida, agenda `_revisar_cola` cada 100 ms, intercepta el cierre de ventana.
3. La usuaria selecciona carpeta → `_carpeta_cambiada()`: actualiza recientes (máx 3), guarda config, busca `datos_materiales.json` automáticamente, revalida.
4. Clic en GENERAR → `_generar()`: advertencias de template/logo (permiten continuar), guarda opciones, resetea visual, lanza `hilo_generacion` en thread daemon.
5. El hilo emite eventos; `_revisar_cola` los pinta. Al `COMPLETE`: barra al 100%, tiempo hh:mm:ss, abre el reporte si la opción está marcada, pop-up de advertencia si hubo fallidos.

---

## 4. CÓMO FUNCIONA LA GUI (detallado)

### 4.1 Sección "Configuración del Proyecto"

- **Carpeta Base:** `ttk.Combobox` de **solo lectura** (no editable a mano) cuyos valores son las últimas 3 carpetas usadas + botón `Examinar…` (`filedialog.askdirectory`). Validación: la carpeta debe contener al menos una de `ARQUITECTONICOS`, `MECANICOS`, `ESTRUCTURALES` (constante `CARPETAS_MADRE`). Debajo hay una etiqueta ✓ verde / ✗ roja con el resultado.
- **Archivo JSON:** `Entry` en `state="readonly"` + botón `Examinar…` (`askopenfilename`, filtro `*.json`). Validación: JSON parseable con lista `materiales` no vacía (acepta también un array directo, igual que el motor). Al elegir carpeta válida se autocompleta con `datos_materiales.json` si existe.
- El botón principal solo se habilita si **ambas** validaciones pasan (`_validar()`), y se deshabilita durante el procesamiento.

### 4.2 Sección "Opciones"

| Checkbox | Default | Efecto |
|---|---|---|
| Solo generar PDFs faltantes | ☑ | Modo incremental: es el comportamiento nativo del motor (salta carpetas que ya tienen `CARATULA*.pdf`). No requiere código extra. |
| Forzar regeneración (borrar existentes) | ☐ | Antes de procesar, la GUI borra los `CARATULA*.pdf` de cada `ruta_carpeta`. Al marcarlo: desmarca el otro checkbox y muestra `askyesno` de advertencia. Tooltip con ⚠. |
| Mostrar log al finalizar | ☑ | Al `COMPLETE`, abre `generate_caratulas_report.txt` con `os.startfile`. |

Los dos primeros son **mutuamente excluyentes** (`_chk_solo` / `_chk_forzar`). Los tres se guardan en config al generar.

### 4.3 Barra de progreso

- `ttk.Progressbar` con estilo verde (`Verde.Horizontal.TProgressbar`), `maximum=100`.
- **Fuente de datos:** el hilo emite `("PDF_GENERATED", i, total, stats)` después de **cada material** (generado O saltado). La GUI calcula `pct = i*100/total` y pinta `"XX% (NN/TOTAL)"`.
- La actualización nunca bloquea: el hilo solo escribe en la cola; los widgets se tocan únicamente desde `_revisar_cola` (hilo principal).

### 4.4 Resultados

Los contadores salen del diccionario `stats` del motor (se envía una copia en cada evento):

- ✅ **Generados** = `stats["ok"]`
- ⏭ **Saltados** = `existentes` (ya tenían carátula) + `vacias` (carpeta vacía) + `incompletas` (ficha incompleta), con desglose entre paréntesis.
- ❌ **Errores** = `stats["fallidos"]`
- ⏳ **Tiempo** = `time.time() - t0` del hilo, formateado `hh:mm:ss` al completar.

También hay un mini-log oscuro (Text de 6 líneas) que muestra en vivo las líneas del log del motor.

### 4.5 Botones de acción

| Botón | Acción |
|---|---|
| 📋 Ver Log Completo | `os.startfile(<base>/generate_caratulas_report.txt)` → abre en Notepad (app por defecto). Aviso si aún no existe. |
| 📁 Abrir Resultados | `os.startfile` sobre la primera carpeta de disciplina existente (ARQUITECTONICOS → MECANICOS → ESTRUCTURALES) o la base. |
| 🔄 Nuevo Proceso | Resetea barra, contadores y mini-log. Si hay proceso en curso, pide confirmación y activa el `Event` de cancelación. |
| ❌ Cerrar | Guarda config y cierra. Si hay proceso en curso, confirma primero. (También intercepta la X de la ventana vía `WM_DELETE_WINDOW`.) |

---

## 5. INTEGRACIÓN CON generate_caratulas.py

### 5.1 Cómo se llama el motor

**NO se usa subprocess.** Se carga como módulo con `importlib` desde la carpeta base seleccionada:

```python
spec = importlib.util.spec_from_file_location("generate_caratulas", str(ruta_motor))
gc = importlib.util.module_from_spec(spec)
sys.modules["generate_caratulas"] = gc
spec.loader.exec_module(gc)
```

**Punto clave:** el motor define `BASE_DIR = Path(__file__).resolve().parent` al importarse. Como se importa desde la carpeta seleccionada, `BASE_DIR`, `TEMPLATE_PATH`, `LOGO_PATH`, `LOG_PATH` y `REPORT_PATH` apuntan automáticamente a esa carpeta. **No hace falta parchear nada.** Además, cada corrida re-importa el módulo fresco → `stats` y las listas acumuladoras arrancan en cero.

La GUI **no llama a `gc.main()`** (porque usa `sys.exit` y no da progreso por ítem). En su lugar replica la orquestación llamando funciones públicas del motor:
`gc.available_engines()`, `gc.file_uri()`, `gc.to_absolute()`, `gc.process_material(item, template, engines)`, `gc.write_report()`, y lee/escribe `gc.stats`, `gc.lst_errores`, `gc.LOGO_URI`.

### 5.2 Parámetros que se pasan

- A `process_material`: cada `item` del JSON, el `jinja2.Template` compilado del `template_caratula.html`, y la lista `engines` de `available_engines()`.
- `gc.LOGO_URI = gc.file_uri(gc.LOGO_PATH)` se asigna antes del bucle (el motor lo hace en `main()`; la GUI lo replica).
- `gc.stats["total"] = len(materiales)` antes del bucle (para que el reporte sea correcto).

### 5.3 Cómo se captura el progreso

Dos vías simultáneas:

1. **Conteo directo:** la GUI controla el bucle `for`, así que tras cada `process_material` envía `("PDF_GENERATED", i, total, dict(gc.stats))`.
2. **Log en vivo:** se agrega un `logging.Handler` propio (`_QH`) al logger `"caratulas"` del motor, que reenvía cada línea formateada a la cola como `("LOG", texto)`.

Manejo de handlers (importante): antes de cada import se **cierran y quitan** los handlers previos del logger `"caratulas"` (evita duplicados y archivos .log bloqueados en Windows). Tras el import, se elimina cualquier `StreamHandler` con stream `None` (ocurre en .exe `--windowed`, donde no hay consola).

### 5.4 Manejo de errores de la llamada

- Validaciones previas (motor no encontrado, jinja2 ausente, sin motor de PDF, JSON inválido, template ausente/corrupto, logo ausente) → evento `("ERROR", mensaje_en_español)` y el hilo termina. El `main()` del motor haría `die()`/`sys.exit`; la GUI lo evita haciendo las mismas comprobaciones por su cuenta.
- Excepción dentro de `process_material` → se captura por ítem, suma a `gc.stats["fallidos"]` y `gc.lst_errores`, emite `("WARN", ...)` y **continúa** con el siguiente material (mismo criterio que el motor).
- Cualquier excepción no prevista del hilo → `except` global → `("ERROR", error_legible(e))`.

---

## 6. SISTEMA DE THREADING

### 6.1 Por qué

Generar 35+ PDFs con Chromium tarda minutos. Si corriera en el hilo principal, la ventana se congelaría ("No responde"). El hilo aparte mantiene la GUI viva y permite pintar progreso.

### 6.2 Cómo funciona

- **`threading.Thread(target=hilo_generacion, args=(...), daemon=True)`** — daemon para que no impida cerrar la app.
- **`queue.Queue`** (`self.cola`) — único canal de comunicación hilo→GUI. El hilo hace `q.put(evento)`; la GUI hace `get_nowait()` en `_revisar_cola`, re-agendada con `self.after(100, ...)`.
- **`threading.Event`** (`self.cancelar`) — canal GUI→hilo. "Nuevo Proceso"/"Cerrar" hacen `set()`; el hilo revisa `cancelar.is_set()` al inicio de cada material y aborta limpio.

Eventos definidos: `LOG`, `WARN`, `PDF_GENERATED`, `ERROR`, `COMPLETE` (ver docstring de `hilo_generacion`).

### 6.3 Sincronización

Regla de oro respetada: **solo el hilo principal toca widgets tkinter.** El hilo de trabajo jamás llama métodos de la GUI; todo pasa por la cola (`queue.Queue` es thread-safe por diseño).

### 6.4 Prevención de race conditions

- Los `stats` se envían como **copia** (`dict(gc.stats)`) en cada evento — la GUI nunca lee el dict compartido mientras el hilo lo muta.
- La bandera `self.procesando` solo se modifica en el hilo principal (al lanzar y al recibir `ERROR`/`COMPLETE`).
- Un solo hilo de trabajo a la vez: el botón GENERAR queda deshabilitado durante el proceso.
- La config se guarda desde el hilo principal únicamente.

---

## 7. PERSISTENCIA Y CONFIGURACIÓN

### 7.1 submitals_config.json — estructura completa

```json
{
  "carpetas_recientes": ["C:\\Users\\castr\\Downloads\\Submitals ES"],
  "ultimo_json": "C:\\Users\\castr\\Downloads\\Submitals ES\\datos_materiales.json",
  "opciones": {
    "solo_faltantes": true,
    "forzar_regeneracion": false,
    "mostrar_log": true
  }
}
```

- `carpetas_recientes`: máximo 3, la más reciente primero (alimenta el Combobox).
- Se actualiza: al seleccionar carpeta válida, al seleccionar JSON, al pulsar GENERAR (opciones) y al cerrar.
- Retro-compatibilidad: si existe el campo viejo `ultima_carpeta`, se migra a la lista.

### 7.2 Ubicación

`CONFIG_PATH = app_dir() / "submitals_config.json"` — junto al **.exe** si está congelado (`sys.frozen`), junto al **.py** en desarrollo. Si el archivo está corrupto o no existe → defaults (`CONFIG_DEFECTO`) sin error.

### 7.3 Recuperación al iniciar

`_cargar_valores_iniciales()`: usa la primera carpeta reciente que exista en disco; si ninguna, `DEFAULT_BASE` (`C:\Users\castr\Downloads\Submitals ES`) si existe. Restaura `ultimo_json` si el archivo sigue existiendo; si no, intenta autodetectar `datos_materiales.json` en la base.

---

## 8. MANEJO DE ERRORES

### 8.1 Errores posibles y detección

| Error | Dónde se detecta | Resultado |
|---|---|---|
| Carpeta sin carpetas de disciplina | `_carpeta_valida()` en vivo | ✗ rojo bajo el campo, botón deshabilitado |
| JSON inválido / sin `materiales` | `_json_valido()` al elegir + revalidación en el hilo | Pop-up "JSON invalido" / etiqueta ✗ |
| `generate_caratulas.py` ausente | inicio de `hilo_generacion` | ERROR fatal con la ruta esperada |
| Falta template o logo | `_generar()` (advertencia previa, **permite continuar**) y de nuevo en el hilo (fatal si realmente faltan) | `askyesno` de advertencia → si continúa y faltan, pop-up de error |
| Sin motor de PDF / falta chromium | `gc.available_engines()` vacío / mensaje de playwright | Pop-up con el comando de instalación |
| Permisos insuficientes | `PermissionError` (motor por-ítem, o traducción global) | Ítem fallido con aviso, o pop-up legible |
| Error inesperado por material | try/except del bucle | Cuenta como fallido, el proceso continúa |

### 8.2 Mensajes al usuario

Todos en español, sin traceback. `error_legible(e)` (línea 120) centraliza la traducción: archivo no encontrado, permisos, JSON con línea/columna, falta chromium ("python -m playwright install chromium"), falta librería ("pip install jinja2 pypdf playwright"), y un genérico truncado a 300 caracteres como último recurso.

### 8.3 Validaciones implementadas

En vivo: carpeta (disciplinas), JSON (parseo + lista). Pre-generación: existencia de `template_caratula.html` y del logo en `Tabla visual refresh\assets\` (advertencia, continúa si acepta). En el hilo: motor presente, jinja2, engines, JSON, template no corrupto (`<html` presente), logo. Probadas en sandbox: JSON malformado y carpeta sin motor → mensajes correctos.

---

## 9. DEPENDENCIAS Y LIBRERÍAS

### 9.1 Lista completa

| Librería | Tipo | Uso en la GUI |
|---|---|---|
| `tkinter` / `ttk` | built-in | Toda la interfaz |
| `threading`, `queue` | built-in | Hilo de trabajo + cola de eventos |
| `json`, `pathlib`, `os`, `sys`, `time`, `logging`, `importlib` | built-in | Config, rutas, carga del motor, log |
| `jinja2` | externa | La usa el motor (template) |
| `pypdf` | externa | La usa el motor (validar PDFs) |
| `playwright` | externa | Motor de render PDF (Chromium headless) — el recomendado en Windows |

Nota: `subprocess` NO se usa (se descartó a favor de importlib). `weasyprint`/`pdfkit` son motores alternativos que el motor detecta solo si están instalados; no son requisito.

### 9.2 Comando pip exacto

```
pip install jinja2 pypdf playwright
python -m playwright install chromium
```

(+ `pip install pyinstaller` solo para empaquetar.)

### 9.3 Versiones recomendadas

Cualquier versión actual funciona: jinja2 ≥ 3.0, pypdf ≥ 3.0, playwright ≥ 1.40, pyinstaller ≥ 6.0.

### 9.4 Compatibilidad

Python 3.9+ (se evitó sintaxis más nueva: sin `match`, sin `X | Y` en tipos). Windows 10/11. `os.startfile` es solo-Windows (intencional).

---

## 10. CÓMO EMPAQUETAR CON PyInstaller

### 10.1 Comando exacto

```
pyinstaller --onefile --windowed --name "GeneradorSubmittalsES" --collect-all playwright --collect-all jinja2 --collect-all pypdf submitals_gui.py
```

(Ejecutar en cmd, dentro de la carpeta donde está `submitals_gui.py`.)

### 10.2 Parámetros

- `--onefile`: un único .exe autocontenido.
- `--windowed`: sin ventana de consola negra (por eso el código quita el StreamHandler con stream None).
- `--collect-all <pkg>`: fuerza a incluir paquete + datos + binarios. **Imprescindible** porque el motor se importa dinámicamente y PyInstaller no puede detectar sus imports (jinja2/pypdf/playwright) por análisis estático.
- Opcional: `--icon logo_es.ico`.

### 10.3 Ubicación del .exe

`dist\GeneradorSubmittalsES.exe` (relativo a donde se corrió el comando). Pesa ~150 MB por el driver de Playwright: es normal.

### 10.4 Troubleshooting

- **"Falta el navegador de Playwright" en otra PC:** el .exe incluye la librería pero NO Chromium. Solución A (sin instalar nada): copiar `C:\Users\<usuario>\AppData\Local\ms-playwright` y pegarla **junto al .exe** con el nombre `ms-playwright` — la GUI detecta esa carpeta al arrancar y fija `PLAYWRIGHT_BROWSERS_PATH`. Solución B: `pip install playwright && python -m playwright install chromium` en esa PC.
- **Antivirus bloquea el .exe:** falso positivo típico de PyInstaller; agregar excepción.
- **`ModuleNotFoundError` al correr el .exe:** falta un `--collect-all`; re-empaquetar.
- **Empaquetado lento (5+ min):** normal con `--collect-all playwright`.

---

## 11. CÓMO HACER MODIFICACIONES FUTURAS

### 11.1 Estructura del código

Híbrida: funciones globales para lo no-GUI (`cargar_config`, `error_legible`, `hilo_generacion`…) y **una clase** `SubmitalsGUI(tk.Tk)` para la ventana. Archivo único a propósito (facilita PyInstaller). Orden del archivo: constantes → config → errores → Tooltip → hilo → clase GUI → `__main__`.

### 11.2 Nuevas validaciones

- De la GUI (en vivo): agregar método `_x_valida()` junto a `_carpeta_valida`/`_json_valido` (líneas ~502–512) y llamarlo desde `_validar()` (514).
- Del proceso: agregarlas al inicio de `hilo_generacion` (169), siguiendo el patrón `q.put(("ERROR", "mensaje")); return`.

### 11.3 Nuevos campos de entrada

En `_construir_ui()` (343), dentro de la sección 1 (buscar `SECCION 1`). Patrón: `tk.StringVar` en `__init__` → Label + Entry/Combobox + botón → validación → persistir en config (agregar clave en `CONFIG_DEFECTO` y en `_generar`).

### 11.4 Textos y mensajes

- Errores traducidos: `error_legible()` (120).
- Mensajes de validación: dentro de `_validar()` (514).
- Pop-ups: buscar `messagebox.` (aparece en ~10 lugares).
- Títulos de sección de la GUI: llamadas a `self._titulo_seccion(...)` en `_construir_ui`.

### 11.5 Colores y estilos

Constantes al inicio del archivo (líneas 48–53): `ROJO_ES`, `AZUL_ES`, `GRIS_BG`, `VERDE_OK`, `AMARILLO`, `BLANCO`. Fuentes: buscar `("Segoe UI"`. Estilo de la barra: `Verde.Horizontal.TProgressbar` en `_construir_ui`.

### 11.6 Nuevas opciones (checkboxes)

1. `tk.BooleanVar` en `__init__` (junto a `self.var_solo`).
2. Clave y default en `CONFIG_DEFECTO["opciones"]`.
3. `tk.Checkbutton` + `Tooltip` en la SECCION 2 de `_construir_ui`.
4. Incluirla en el dict `self.cfg["opciones"]` dentro de `_generar()`.
5. Leerla en `hilo_generacion` vía `opciones.get("mi_clave")`.

### 11.7 Nuevos botones

Sección 5 de `_construir_ui` (frame `facc`, usa `grid`): copiar el patrón de `self.btn_verlog` con `estilo_acc`, asignar `command=self._mi_metodo` y crear el método en la clase.

---

## 12. CAMBIOS COMUNES Y CÓMO HACERLOS

### 12.1 "Quiero cambiar el color del botón principal"

El rojo viene de la constante `ROJO_ES = "#E11D2D"` (línea 48). Para cambiar SOLO el botón: en `_construir_ui`, buscar `self.btn_generar = tk.Button(` y cambiar `bg=ROJO_ES` por el color deseado. Ojo: `_validar()` también re-pinta `bg=(ROJO_ES if habilitar else "#9AA0A8")` — cambiar ahí también, y `activebackground="#B01623"` (color al hacer clic).

### 12.2 "Quiero agregar un nuevo campo de entrada" (ej. "Nombre del proyecto")

1. En `__init__`: `self.var_proyecto = tk.StringVar(value=self.cfg.get("proyecto", ""))`.
2. En `CONFIG_DEFECTO`: agregar `"proyecto": ""`.
3. En `_construir_ui`, sección 1, después del campo JSON:
   ```python
   tk.Label(cuerpo, text="Nombre del Proyecto:", bg=GRIS_BG, fg=AZUL_ES,
            font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", pady=(6, 0))
   tk.Entry(cuerpo, textvariable=self.var_proyecto,
            font=("Segoe UI", 9)).pack(fill="x", ipady=3)
   ```
4. En `_generar()`: `self.cfg["proyecto"] = self.var_proyecto.get()` antes de `guardar_config`.
5. Si el hilo lo necesita: pasarlo dentro de `opciones` o como argumento extra de `hilo_generacion`.

### 12.3 "Quiero cambiar el tamaño de la ventana"

En `__init__`: `self.geometry("700x900")`. Para permitir redimensionar: `self.resizable(False, False)` → `(True, True)`.

### 12.4 "Quiero cambiar un mensaje de error"

Buscar el texto (o parte) con Ctrl+F en `submitals_gui.py`. Los traducidos están centralizados en `error_legible()` (línea 120); los de validación en `_validar()`; los fatales del proceso son los `q.put(("ERROR", "..."))` dentro de `hilo_generacion`.

### 12.5 "Quiero que solo procese una categoría (ARQ/MEC/ESTR)"

Filtrar la lista `materiales` en `hilo_generacion`, justo después de obtenerla (tras `gc.stats["total"] = len(materiales)` — actualizar ese total también):

```python
prefijo = opciones.get("filtro_categoria")          # ej. "ARQ", "MEC", "ESTR"
if prefijo:
    materiales = [m for m in materiales
                  if str(m.get("consecutivo", "")).upper().startswith(prefijo)]
    gc.stats["total"] = len(materiales)
```

Y en la GUI: un Combobox "Categoría" (TODAS/ARQ/MEC/ESTR) siguiendo 12.2, pasando el valor dentro de `opciones`. Nota: ESTR también cubre "ESTR01…" — usar `startswith` evita confundir con nada más porque ningún otro prefijo colisiona.

---

## 13. PRUEBAS Y VALIDACIÓN

### 13.1 Checklist de funcionalidades probadas

- ✓ Sintaxis (`py_compile`) OK.
- ✓ Generación completa: 1 material válido → 1 PDF real (motor weasyprint en sandbox Linux; en Windows será playwright — misma interfaz).
- ✓ Modo incremental: segunda corrida salta el existente (`existentes=1, ok=0`).
- ✓ Forzar regeneración: borra y regenera (`ok=1, existentes=0`).
- ✓ Material con `carpeta_vacia=true` → saltado como vacía.
- ✓ Material con campo vacío → saltado como incompleta.
- ✓ Eventos de progreso: 3 materiales → 3 eventos `PDF_GENERATED`.
- ✓ JSON malformado → ERROR legible con línea y columna.
- ✓ Carpeta sin `generate_caratulas.py` → ERROR legible.
- ✓ Reporte `generate_caratulas_report.txt` generado.
- ✓ PDF resultante válido (abre con pypdf, 1 página).

### 13.2 Casos de prueba documentados

JSON de prueba con 3 materiales: ARQ01 válido, ARQ02 `carpeta_vacia=true`, ARQ03 con `nombre` vacío. Resultado esperado y obtenido: `ok=1, vacias=1, incompletas=1, fallidos=0`.

### 13.3 Errores conocidos

- La GUI (ventana) no se pudo probar visualmente en el sandbox (sin display/tkinter); la lógica sí. **Pendiente:** prueba visual en Windows real.
- El primer PDF de cada corrida tarda varios segundos (arranque de Chromium): es normal, no es bug. `sync_playwright` lanza un navegador por PDF — si algún día es lento con 70 materiales, la optimización sería reutilizar el navegador, pero eso requeriría tocar el motor (prohibido) o renderizar aparte.
- Si el reporte está abierto en Notepad mientras se regenera, Windows no bloquea (Notepad no bloquea archivos): sin problema conocido.

### 13.4 Esperado vs real

Sin desviaciones en lo probado. Los contadores de la GUI coinciden 1:1 con el reporte del motor porque leen el mismo `stats`.

---

## 14. DISTRIBUCIÓN A LAS COMPAÑERAS

1. **Ubicación del .exe:** `dist\GeneradorSubmittalsES.exe` tras empaquetar.
2. **Cómo compartirlo:** carpeta compartida de red o USB (por email suele bloquearse un .exe de 150 MB). Entregar SIEMPRE la pareja: `GeneradorSubmittalsES.exe` + carpeta `ms-playwright\` (copiada de `AppData\Local\ms-playwright` de la PC donde se instaló chromium), juntas en la misma carpeta.
3. **Instrucciones de uso:** doble clic al .exe → Examinar → elegir la carpeta "Submitals ES" (el JSON se autodetecta) → GENERAR. No requiere instalación ni Python.
4. **Requisitos:** Windows 10/11, acceso a la carpeta del proyecto con: `generate_caratulas.py`, `template_caratula.html`, `datos_materiales.json`, el logo, y las carpetas de disciplina.
5. **Si hay problemas, revisar en orden:** ① el mensaje del pop-up (ya viene traducido con la solución), ② que la carpeta elegida sea la que contiene `generate_caratulas.py`, ③ que exista `ms-playwright` junto al .exe, ④ el antivirus, ⑤ `generate_caratulas.log` en la carpeta base para el detalle técnico.

---

## 15. CÓDIGO ANOTADO

### 15.1 Punto de entrada

```python
if __name__ == "__main__":
    app = SubmitalsGUI()   # construye toda la ventana y carga config
    app.mainloop()         # bucle de eventos tkinter (bloquea hasta cerrar)
```

No hay `main()` como tal; el equivalente es `SubmitalsGUI.__init__`.

### 15.2 Funciones clave (resumen mínimo)

- `hilo_generacion(...)` — TODO el trabajo pesado; solo se comunica por cola. Si se modifica el flujo de generación, es aquí.
- `_revisar_cola()` — único lugar que traduce eventos → widgets. Si se agrega un tipo de evento nuevo, se despacha aquí.
- `_validar()` — única fuente de verdad para habilitar el botón principal.
- `error_legible(e)` — única fuente de mensajes de error traducidos.

### 15.3 Variables globales/de instancia importantes

`self.cola` (Queue), `self.cancelar` (Event), `self.procesando` (bool), `self.cfg` (dict config), `self.var_*` (variables tkinter de cada control).

### 15.4 Constantes a considerar (inicio del archivo)

`ROJO_ES`, `AZUL_ES`, `GRIS_BG`, `VERDE_OK`, `AMARILLO`, `BLANCO` (tema), `CARPETAS_MADRE` (validación de carpeta), `NOMBRE_MOTOR`, `NOMBRE_JSON`, `NOMBRE_REPORTE` (nombres de archivo esperados), `DEFAULT_BASE` (carpeta por defecto), `CONFIG_PATH` (ubicación de config), `CONFIG_DEFECTO` (defaults). El bloque `ms-playwright` (líneas ~72–76) fija `PLAYWRIGHT_BROWSERS_PATH` si hay navegadores portables junto al .exe.

---

## 16. HISTORIAL DE CAMBIOS

| Versión | Fecha | Cambios |
|---|---|---|
| 1.0 | 2026-07-16 | Creación inicial: GUI completa, threading + cola, integración importlib con el motor, config persistente (últimas 3 carpetas + opciones), modo incremental/forzar, traducción de errores, soporte ms-playwright portable, INSTRUCCIONES.txt. |
| — | — | *(espacio para futuras versiones)* |

---

## 17. NOTAS Y ADVERTENCIAS IMPORTANTES

- ⛔ **NO modificar `generate_caratulas.py`.** Es el motor externo, funciona y está documentado en la otra memoria. La GUI depende de sus nombres públicos: `process_material`, `available_engines`, `write_report`, `file_uri`, `to_absolute`, `stats`, `lst_errores`, `LOGO_URI`, `TEMPLATE_PATH`, `LOGO_PATH`, `_CtxFilter`. Si el motor cambiara esos nombres, la GUI se rompe.
- La GUI **no llama a `gc.main()`** — replica sus validaciones sin `sys.exit`. Si el motor agrega validaciones nuevas a `main()`, evaluar replicarlas en `hilo_generacion`.
- `submitals_config.json` **persiste entre ejecuciones** (vive junto al .exe). Para "resetear de fábrica": borrarlo.
- **Threading es crítico:** jamás tocar widgets desde `hilo_generacion`; siempre por la cola.
- Los checkboxes "solo faltantes" y "forzar" son mutuamente excluyentes por diseño.
- PyInstaller con `--collect-all playwright` puede tardar 5+ minutos y el .exe pesa ~150 MB: normal.
- Cada modificación a `submitals_gui.py` requiere **re-empaquetar** y redistribuir el .exe.
- El .exe necesita Chromium en la PC destino: carpeta `ms-playwright` junto al .exe (opción sin instalación) o instalación con pip/playwright.
- Limpieza de logging entre corridas (cerrar handlers del logger `"caratulas"` antes de re-importar) es necesaria: evita logs duplicados y archivos bloqueados en Windows. No quitar ese bloque.

---

## 18. CONTACTO/RESPONSABLE

- **Creado por:** Fable (Claude, en chat de Cowork) — 2026-07-16
- **Mantenedora:** Diana Solís (diana.solis@esconstructora.com) — ES Consultoría y Construcción S.A.
- **Última revisión:** 2026-07-16

---

## GLOSARIO DE TÉRMINOS TÉCNICOS

- **tkinter / ttk:** librería de interfaces gráficas incluida con Python. `ttk` son los widgets "temables" (Combobox, Progressbar).
- **Thread (hilo):** ejecución en paralelo; aquí, el trabajo pesado corre aparte para no congelar la ventana.
- **Queue (cola):** estructura segura para pasar mensajes entre hilos.
- **Event:** bandera thread-safe; aquí se usa para pedir cancelación.
- **importlib:** mecanismo de Python para cargar un módulo desde una ruta arbitraria en tiempo de ejecución.
- **Jinja2:** motor de plantillas; rellena `{{ variables }}` en el HTML de la carátula.
- **Playwright / Chromium headless:** navegador sin ventana que convierte el HTML a PDF con fidelidad de Chrome.
- **PyInstaller:** empaqueta un script Python + dependencias en un .exe autónomo.
- **frozen:** estado de un programa empaquetado (`sys.frozen`); cambia dónde se busca la config.
- **Modo incremental:** saltar materiales cuya carpeta ya contiene un `CARATULA*.pdf`.
- **Submittal:** paquete de fichas técnicas de materiales que se somete a aprobación de la inspección (aquí, Municipalidad de Desamparados).
- **Carátula:** portada PDF estandarizada que encabeza cada submittal.
