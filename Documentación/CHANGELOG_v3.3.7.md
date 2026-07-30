# CHANGELOG v3.3.7 — Carátula con campos aplanados en el compilado

**Fecha:** 2026-07-29
**Estado:** publicada (commit `4cbbe45`, tag `v3.3.7`, Release con exe +
instalador subidos y verificados).
**Alcance:** cómo se incrusta la carátula en el PDF compilado (`-CMP.pdf`) y en
el compilado por disciplina. No cambia la carátula suelta (`CARATULA*.pdf`),
que sigue siendo editable.

> Se sumaron 15 cambios más a esta misma entrada (ver secciones abajo): orden
> manual de consecutivos, marcas alternativas con PDF real adjunto, edición
> libre de todo el texto de la carátula por material, guardado local vs.
> guardado en la BD para esos mismos campos, botón "Actualizar catálogo" al
> armar un submittal, datos del proyecto ya no obligatorios, sinónimos de
> búsqueda al cargar una ficha, botón "Guardar avance", la reversión del
> aplanado de esta misma entrada por un fix que mantiene edición Y
> compatibilidad a la vez, una reescritura completa del buscador de fichas
> (arregla un bug de scoring que lo hacía inservible + nueva UI con filtros y
> scroll), ventanas que se auto-dimensionan para que ningún botón quede fuera
> de pantalla, un guardrail contra el reseteo accidental del contador de
> consecutivos al reabrir un proyecto por la opción equivocada, la causa
> real de fondo del mismo reporte: cerrar la ventana con la X perdía en
> silencio el avance no guardado, una animación de confirmación al agregar
> un material a la lista del submittal, y "Abrir submittal existente" ahora
> lista los proyectos ya sincronizados en la BD (nube) para continuarlos
> desde otra PC sin compartir carpeta.

---

## El problema

La carátula se genera con campos de formulario (AcroForm) editables, para
poder corregir un dato a mano después. Pero al unirla dentro del PDF grande
del compilado (la carátula + la ficha técnica completa, o varias carátulas
fusionadas en el compilado por disciplina), varios visores de PDF **no
mostraban el valor de esos campos** — sobre todo en archivos grandes, o
cuando el compilado junta carátulas distintas con nombres de campo
repetidos.

## La solución

Se agrega `_caratula_reader_para_compilar()` en `submitals_gui.py` y en
`submitals_gui_v3.py`: antes de anexar la carátula al compilado, se **aplanan**
sus campos (`fitz.Document.bake(annots=True, widgets=True)`, vía PyMuPDF) —
el texto de la tabla queda incrustado en el contenido de la página, visible en
cualquier visor. El archivo `CARATULA*.pdf` suelto no se toca: solo se aplana
la copia que entra al compilado.

Si PyMuPDF no está disponible o el aplanado falla, se cae al comportamiento
anterior (carátula con campos de formulario tal cual), con un aviso en el log.

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui.py` | `generar_compilado()` | Usa la carátula aplanada en vez de `PdfReader` directo. |
| `submitals_gui.py` | `compilar_por_disciplina()` | Ídem, **y** corrige un bug: antes anexaba `r.pages` completas de la carátula (podía incluir la 2ª hoja en blanco que agrega Chromium); ahora solo `pages=(0, 1)` y cuenta 1 página, no `len(r.pages)`. |
| `submitals_gui_v3.py` | `generar_compilado()` | Misma carátula aplanada. |
| `submitals_gui_v3.py` | `compilar_disciplinas()` | Ídem, y también se limita a `pages=(0, 1)` (antes anexaba el `PdfReader` completo). |

`README.md`: se actualizó la referencia de versión en la introducción de
`v3.0.0` a `v3.3.5` (desactualizada, sin relación funcional con lo anterior).

## Compatibilidad

- No cambia el formato de la BD ni del índice de fichas.
- No afecta carátulas ya generadas ni proyectos existentes — el aplanado
  ocurre solo al compilar, sobre una copia en memoria.
- Requiere PyMuPDF (`fitz`); si falta, hay fallback automático sin romper el
  compilado.

---

# Orden manual de consecutivos (Submittal v3)

## El problema

El consecutivo de cada material (`ESTR01`, `ESTR02`, ...) se recalculaba
siempre en el orden en que se habían agregado los materiales al submittal,
sin forma de decidir manualmente qué material ocupa qué número — importante
para trazabilidad del proyecto (ej: que el cemento sea siempre `ESTR06`).

## La solución

Se agregan botones **"↑ Subir" / "↓ Bajar"** en la tabla de materiales del
submittal (`TablaMateriales`). Mueven el material seleccionado un puesto
dentro de su misma categoría (ARQ/ESTR/MEC/ELEC); los consecutivos de esa
categoría se renumeran solos según la nueva posición.

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `TablaMateriales._renumerar` | Ahora numera respetando el orden actual de la lista en memoria, no el consecutivo previo (paso necesario para que el orden manual no se pise solo). |
| `submitals_gui_v3.py` | `TablaMateriales._mover` (nuevo) | Intercambia el material seleccionado con su vecino de la misma categoría y refresca. |
| `submitals_gui_v3.py` | `TablaMateriales._build` | Agrega botones "↑ Subir" / "↓ Bajar". |

## Compatibilidad

- No cambia el formato de `submittal_proyecto.json`: sigue siendo una lista
  de materiales con `consecutivo`/`categoria`; solo cambia el criterio de
  orden al renumerar. Submittals existentes se abren y renumeran igual que
  antes (el orden actual en el archivo se respeta como punto de partida).

---

# Marcas alternativas con ficha real adjunta (antes solo texto)

## El problema

Al usar "Editar marca(s)" para combinar varias marcas bajo un mismo
consecutivo (ej. `ESTR01` = tubo 100x100x2.4 en Metalco, Macopa y Multi), las
marcas alternativas eran texto libre escrito a mano. La carátula/Excel sí
mostraban "Metalco / Macopa / Multi" y el párrafo legal de "se adjuntan N
fichas técnicas...", **pero el compilado (`-CMP.pdf`) solo incluía el PDF de
la marca principal** — el texto prometía N fichas y solo se entregaba 1.

## La solución

"Marcas alternativas" deja de ser un campo de texto libre: ahora se buscan y
agregan fichas reales del catálogo (mismo cuadro de búsqueda que se usa para
agregar materiales), cada una vinculada por `id_ficha_bd`. Al materializar el
proyecto se copian también los PDFs de esas fichas alternativas a la carpeta
del material, así el compilado (que ya anexa todo lo que encuentra en la
carpeta) termina incluyendo los 3 PDFs reales.

Se mantiene compatibilidad con submittals viejos que ya tenían marcas
alternativas como texto suelto (sin ficha vinculada): se siguen mostrando
igual en carátula/Excel, solo que no aportan PDF adicional (como pasaba
antes).

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `TablaMateriales._editar` | El campo de texto "Marcas alternativas (coma)" se reemplaza por un buscador de catálogo + lista de alternativas agregadas (con botón "Quitar"). Cada alternativa guarda `{"id_ficha_bd", "marca"}`. |
| `bd_manager.py` | `_nombre_alternativa` / `_id_ficha_alternativa` (nuevas) | Helpers que leen una marca alternativa en formato viejo (string) o nuevo (dict), para no duplicar esa lógica en cada función. |
| `bd_manager.py` | `_marcas_material` | Usa `_nombre_alternativa` en vez de asumir siempre string. |
| `bd_manager.py` | `construir_datos_materiales` | `documentos_encontrados` ahora incluye también los PDFs de las marcas alternativas vinculadas a ficha. |
| `bd_manager.py` | `materializar_proyecto` | Copia también el PDF de cada marca alternativa vinculada a la carpeta del material (antes solo copiaba la ficha principal). |

## Compatibilidad

- Formato viejo de `marcas_alternativas` (lista de strings) se sigue leyendo
  y mostrando igual; solo las entradas nuevas (dict con `id_ficha_bd`) traen
  PDF adjunto real.
- No se tocó la BD ni el índice de fichas — la fuente de los PDFs sigue
  siendo el catálogo existente, solo se referencian más fichas por material.

## Pruebas

- `python -m unittest test_v3 -v`: 28 tests, 1 falla preexistente y no
  relacionada (`test_extraccion_ocr_ficha_real`, depende de servicio OCR
  externo). El resto, incluyendo `test_submittal_completo_sin_caratulas`
  (que ejercita `materializar_proyecto` + compilado de CMPs de punta a
  punta), pasa sin cambios.

---

# Editar todo el texto de la carátula por material

## El problema

El texto que sale en la carátula de cada material (nombre, descripción
técnica, normativa, aspectos adicionales) venía siempre de la ficha del
catálogo, sin forma de ajustarlo para un submittal puntual. A veces hace
falta cambiar una frase o un modelo solo para ese proyecto, sin tocar la
ficha original (que afectaría a todos los demás submittals que la usan).

## La solución

El mismo diálogo "Editar marca(s)" (ahora también edita más que marcas, se
renombra internamente a "Editar material") agrega campos editables para:
Nombre del material, Descripción técnica, Normativa, y Aspectos
adicionales/notas. Cada campo se pre-llena con el valor actual (el de la
ficha, o el texto auto-generado en el caso de "aspectos" cuando hay
justificación por stock) y el usuario puede escribir encima.

Los cambios quedan guardados **solo en el submittal**, nunca en la ficha del
catálogo — si el texto final coincide con el valor por defecto no se guarda
ningún override (para que, si más adelante cambia la ficha o se agregan/quitan
marcas alternativas, el texto sin editar se siga actualizando solo). Si el
usuario sí escribió algo distinto, eso queda fijo para ese material hasta que
lo vuelva a tocar. Para "Aspectos adicionales" hay un botón "↻ Recalcular
automático" que trae de nuevo el texto auto-generado (útil después de agregar
o quitar una marca alternativa, ya que cambia el número de fichas que dice el
párrafo legal).

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `TablaMateriales._editar` | Agrega campos Nombre / Descripción técnica / Normativa / Aspectos adicionales, con botón "↻ Recalcular automático" para el último. |
| `bd_manager.py` | `construir_datos_materiales` | `descripcion`/`normativa`/`aspectos_adicionales` ahora respetan el override guardado en el material (`"campo" in m`) antes de caer al valor de la ficha. |

## Compatibilidad

- No cambia el formato de la BD ni de fichas existentes — los overrides son
  claves nuevas y opcionales (`descripcion`, `normativa`, `aspectos_adicionales`)
  dentro de cada material del submittal; si no están presentes el
  comportamiento es idéntico al de antes.
- Submittals viejos (sin estas claves) siguen mostrando el texto de la ficha
  tal cual, sin cambios.

## Pruebas

- `python -m unittest test_v3 -v`: mismos 28 tests, misma única falla
  preexistente y no relacionada (`test_extraccion_ocr_ficha_real`). En
  particular `test_aspectos_adicionales_llega_a_datos_materiales` y
  `test_aspectos_adicionales_se_guarda_y_edita` (que cubren el camino sin
  override) siguen pasando sin cambios.

---

# Guardado local vs. guardado en la BD (mismo diálogo)

## El problema

El diálogo de "Editar material" (nombre, marca, descripción, normativa,
aspectos adicionales) guardaba todo como override local del submittal
únicamente. Pero a veces el cambio no es un ajuste puntual de un proyecto,
sino una corrección real de la ficha (ej: un error de transcripción, o un
dato que faltaba) que debería aplicar en todos los submittals presentes y
futuros que usan esa ficha — sin tener que ir a "Gestionar catálogo" a
editarla por separado.

## La solución

El diálogo ahora tiene 2 botones en vez de uno:

- **"💾 Guardar solo este proyecto"** — el comportamiento que ya existía:
  guarda los cambios como overrides de este material en este submittal
  (`bd_manager.py`, `construir_datos_materiales`), sin tocar la BD.
- **"☁️ Guardar en la BD (todos los proyectos)"** — con confirmación previa
  (advierte que afecta a todos los submittals que usan esa ficha), escribe
  los cambios directo en la ficha del catálogo vía `BDManager.editar_ficha()`
  y sube a GitHub con `git_push()` (mismo mecanismo que "Gestionar catálogo →
  Editar ficha"). Como el nuevo valor ya queda en la ficha, se limpian los
  overrides locales de descripción/normativa/aspectos de este material (para
  que no quede una copia vieja tapando el valor nuevo de la ficha).

Si el material no tiene una ficha vinculada en la BD (caso raro), el botón de
guardar en la BD avisa y no hace nada — solo queda disponible "Guardar solo
este proyecto".

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `_avisar_resultado_git` (nueva, nivel módulo) | Extrae el aviso de resultado de `git_push()` (subido/offline/sin token/error) que ya usaba `VentanaCatalogo._avisar_push`, para reutilizarlo también desde el submittal. |
| `submitals_gui_v3.py` | `TablaMateriales._editar` | El botón único "Confirmar" se separa en `_guardar_solo_proyecto()` y `_guardar_en_bd()`; esta última llama `bd.editar_ficha()` + `bd.git_push()` sobre la ficha vinculada (`id_ficha_bd`). |

## Compatibilidad

- Usa las mismas funciones de `bd_manager.py` que ya usaba "Gestionar
  catálogo → Editar ficha" (`editar_ficha`, `git_push`): mismo mecanismo de
  sincronización y resolución de conflictos entre PCs, nada nuevo que
  mantener.
- No cambia el formato de `submittal_proyecto.json` ni del índice de fichas.

## Pruebas

- `python -m unittest test_v3 -v`: mismos 28 tests, misma única falla
  preexistente y no relacionada (`test_extraccion_ocr_ficha_real`).

---

# Botón "Actualizar catálogo" al armar un submittal

## El problema

Al armar un submittal, si se cargaba una ficha técnica nueva a la BD desde el
mismo flujo ("＋ Cargar ficha nueva a BD"), a veces el buscador no la
reconocía hasta cerrar la ventana del submittal y volver a abrirla.

## La solución

Botón **"🔄 Actualizar catálogo"** junto al buscador de materiales: hace
`sincronizar()` (trae cambios de otras PCs por GitHub) y vuelve a correr la
búsqueda actual, sin cerrar nada.

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `TablaMateriales._actualizar_catalogo` (nueva) | `bd.sincronizar()` + `self._sugerir()`. |

## Compatibilidad

No cambia ningún formato de datos; es un botón adicional.

---

# Datos del proyecto: ningún campo obligatorio

## El problema

El diálogo "Datos del Proyecto" (número de procedimiento, institución,
detalle, plazo, monto) bloqueaba con "Datos incompletos" si faltaba
cualquiera de esos 5 campos, y `validar_proyecto()` repetía el mismo bloqueo
al momento de generar. A veces esos datos no están definidos todavía cuando
se necesita avanzar con el submittal.

## La solución

Se quitó la validación en ambos lados: el diálogo guarda lo que haya
(inclusive campos vacíos) y `validar_proyecto()` ya no exige esos 5 campos
para generar. Se eliminó la constante `CAMPOS_PROCEDIMIENTO` (quedó sin uso).

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `DatosProyectoDialog._guardar` | Ya no valida campos faltantes. |
| `bd_manager.py` | `validar_proyecto` | Se quita el chequeo de `CAMPOS_PROCEDIMIENTO`. |
| `bd_manager.py` | (constante) | Se elimina `CAMPOS_PROCEDIMIENTO` (sin más usos). |

## Compatibilidad

- Submittals ya guardados con esos campos completos siguen funcionando igual.
- La validación de materiales (mínimo 1, fichas activas en BD) sigue intacta.

---

# Sinónimos de búsqueda al cargar/editar una ficha

## El problema

Solo se podía encontrar una ficha por su nombre técnico exacto. Buscar
"apagador" no encontraba una ficha cargada como "Interruptor", aunque para
el usuario final sean el mismo objeto.

## La solución

Nuevo campo **"Sinónimos para la búsqueda"** (coma) al cargar o editar una
ficha. Se suma a `search_keywords`, así que cualquier sinónimo escrito
queda buscable igual que el nombre técnico. Ej: ficha "Interruptor sencillo"
con sinónimo "apagador" → buscar "apagador" la encuentra con 100% de
similitud (verificado con `fuzzy_search.buscar`).

| Archivo | Función | Cambio |
|---|---|---|
| `fuzzy_search.py` | `generar_search_keywords` | Suma `ficha.get("sinonimos", "")` a los campos tokenizados. |
| `bd_manager.py` | `agregar_ficha` | Guarda `sinonimos` en la ficha nueva. |
| `submitals_gui_v3.py` | `DialogoRevisarFicha.CAMPOS` | Nuevo campo "Sinónimos para la búsqueda". |
| `submitals_gui_v3.py` | `VentanaCatalogo._editar` | Incluye `sinonimos` entre los campos editables de una ficha existente. |

## Compatibilidad

- Fichas existentes sin `sinonimos` siguen funcionando igual (campo vacío,
  no afecta el resto de `search_keywords`).
- No cambia `CAMPOS_OBLIGATORIOS_FICHA`: sinónimos es opcional.

---

# Botón "Guardar avance"

## El problema

Al armar un submittal solo existía "🚀 Generar / Confirmar cambios", que
exige carpeta destino y regenera carátulas/compilados/Excel. Si el usuario
quería pausar a medio armar (sin destino elegido todavía, sin querer generar
nada aún), no había forma de guardar el trabajo sin salir del flujo de
generación completo.

## La solución

Botón **"💾 Guardar avance"**, junto al de generar: guarda los materiales y
los datos del proyecto en la BD (`guardar_submittal` + `git_push`) SIN tocar
carpeta destino ni generar carátulas/compilados/Excel. Después se retoma
igual que cualquier submittal guardado, desde "Abrir existente".

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `_VentanaSubmittal._guardar_avance` (nueva) | `bd.guardar_submittal()` + `bd.git_push()`, sin `generar_entregables()`. |

## Compatibilidad

- Usa el mismo `submittal_proyecto.json` y el mismo mecanismo de
  sincronización que ya usaba "Generar/Confirmar cambios" — nada nuevo que
  mantener.

## Pruebas

- `python -m unittest test_v3 -v`: mismos 28 tests, misma única falla
  preexistente y no relacionada (`test_extraccion_ocr_ficha_real`).
- Verificado a mano que `fuzzy_search.buscar("apagador", [...])` encuentra
  una ficha "Interruptor sencillo" con `sinonimos="apagador, breaker"`
  (similitud 1.0).

---

# Reemplazo del aplanado: campos con apariencia refrescada + nombre único (mantiene edición Y compatibilidad)

## El problema

La primera sección de este changelog resolvió la compatibilidad aplanando
(`fitz.Document.bake`) los campos de la carátula al entrar al compilado, pero
a costa de perder la edición (quedaban dibujados, ya no eran campos reales).

Además, se detectó en un caso real el bug de fondo que justificó el aplanado:
un compilado por disciplina de +500 páginas (69 carátulas) donde Acrobat solo
mostraba los datos de la 1a carátula — el resto aparecía en blanco. Causa
real: todas las carátulas salen del mismo template, con los MISMOS nombres de
campo (`numero_procedimiento`, `institucion`, etc.). Al fusionar varias en un
solo PDF, la especificación de PDF trata los campos con igual nombre como un
solo campo lógico compartido — Acrobat termina resolviendo eso mostrando el
valor de uno solo. No era un límite de tamaño de archivo, era colisión de
nombre de campo.

## La solución

Se reemplaza el aplanado por 2 cambios que atacan cada causa sin sacrificar
edición:

1. **Apariencia refrescada, no incrustada**: `widget.update()` (PyMuPDF) en
   vez de `doc.bake()`. Regenera el dibujo visual correcto del campo — se ve
   bien en cualquier lector, incluso los que no soportan `NeedAppearances`
   (Chrome, Preview, visores livianos) — pero el campo sigue siendo un widget
   real y editable donde el lector soporte formularios (Acrobat, Foxit,
   PDF-XChange, navegadores de escritorio).
2. **Nombre de campo único por carátula**: cada campo se renombra con el
   consecutivo de esa carátula (`ARQ01_marca`, `ARQ02_marca`, ...) antes de
   fusionar. Elimina la colisión de raíz — ya no hay 2 campos con el mismo
   nombre en el PDF final, sin importar cuántas carátulas se junten.

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `_caratula_reader_para_compilar` | Nuevo parámetro `prefijo_campos`; reemplaza `doc.bake(...)` por iterar `page.widgets()`, renombrar (si hay prefijo) y `widget.update()`. |
| `submitals_gui_v3.py` | `compilar_disciplinas` | Pasa `prefijo_campos=f"{cat}{n:02d}"` (ej. `ARQ01`) por cada carátula fusionada — antes no se pasaba prefijo alguno. |
| `submitals_gui_v3.py` | `generar_compilado` | Sin cambio de lógica (1 sola carátula por archivo, sin riesgo de colisión); solo se actualizó el comentario. |
| `submitals_gui.py` | `_caratula_reader_para_compilar` | Mismo cambio; usa el `cons` que ya recibía como prefijo (sanitizado a alfanumérico). |
| `submitals_gui.py` | `compilar_por_disciplina` | **Bug encontrado y corregido de paso**: pasaba `cons=disciplina` (ej. "ARQUITECTONICOS") igual para TODAS las carátulas de la disciplina — un prefijo repetido no evita la colisión. Ahora pasa el consecutivo propio de cada carátula (`f"{pfx}{n:02d}"`, ej. "ARQ01"). |

## Verificación

- Con PyMuPDF: renombrar `widget.field_name` + `widget.update()` en una
  carátula real del repo, guardar, reabrir → el campo aparece renombrado con
  su valor intacto.
- Fusionando 2 carátulas reales (`ARQ01`, `ARQ02`) con prefijo distinto:
  ambas páginas muestran sus propios valores por separado (antes, sin
  prefijo, es el escenario que colapsa a "solo se ve la 1a").
- **Prueba de extremo a extremo con el compilado real**: se copiaron 14
  carátulas reales del repo (`ARQUITECTONICOS/ARQ01..ARQ15`) a una carpeta
  aislada (sin tocar el repo) y se corrió `compilar_disciplinas()` tal cual
  queda en el código. Resultado: `CMP SUBMITTAL ARQUITECTONICO.pdf` de 14
  páginas, 168 campos en total, **0 colisiones de nombre**, cada página con
  su propio consecutivo y nombre de material correctos. Se confirmó además
  que el PDF resultante sigue siendo un formulario real (`doc.is_form_pdf`
  = 168, tipo de campo "Text", no de solo lectura) — no quedó aplanado.

## Compatibilidad

- No cambia el formato de `CARATULA*.pdf` suelta (nunca se tocó).
- No cambia el formato de `datos_materiales.json` ni de la BD.
- Compilados viejos generados con el aplanado (v3.3.6/primera mitad de esta
  entrada) no se ven afectados retroactivamente: esto solo aplica a
  compilados nuevos que se generen de aquí en adelante.

---

# Buscador de fichas reescrito (scoring + UI con filtros y scroll)

## El problema

El buscador era inservible: al buscar "interruptor" devolvía tubos, bloques y
cemento **todos al 100 %** de coincidencia, y la ficha buscada muchas veces ni
aparecía entre las 12 que mostraba. Además la lista era un `Listbox` de 5
filas fijas, sin scroll útil, sin columnas para distinguir fichas parecidas y
sin filtros. Afectaba tanto a "Generar submittal" como a "Gestionar Base de
Datos".

## Causa raíz (2 bugs de scoring en `fuzzy_search.puntuar`)

1. `qt in kt or kt in qt` sin guarda de longitud: un token de 1 letra del
   candidato ("e", "x", un dígito) es subcadena de casi cualquier consulta, así
   que `kt in qt` daba coincidencia total. Por eso todo puntuaba 100 %.
2. La regla de prefijo aceptaba tokens de 1 char: `"apagador".startswith("a")`
   matcheaba el token "a" al 92 %, contaminando fichas sin relación.

## La solución

**Scoring (`fuzzy_search.py`)** — reescrito para que la MEJOR coincidencia
quede siempre de primera:

- Nuevo `_match_token(qt, kt)` con guardas de longitud: igualdad = 1.0;
  prefijo (mínimo 3 chars el más corto) = 0.92; subcadena (query ≥ 3 chars) =
  0.80; y ratio de similitud (tolerancia a errores de tipeo) solo si supera el
  gate. Los tokens basura ya no matchean.
- `puntuar` ahora combina cobertura de tokens (0.85) + un bonus de frase
  (exacto/empieza-con/contiene) que prioriza la coincidencia literal.
- `buscar` puntúa contra varios campos con peso (nombre y material pesan más
  que las keywords crudas), aplica filtros y ordena por puntaje y, a empate,
  por nombre más corto/específico. Verificado: "interruptor" devuelve el
  interruptor de primera; errores de tipeo ("interruptr", "cemeto",
  "tuberia") también rankean su ficha #1.
- Nuevos filtros en `buscar`: `marca`, `modelo` (especificación / tipo /
  dimensiones / nombre) y `nombre`, además del `categoria` que ya existía.

**UI (`submitals_gui_v3.py`)** — nuevo widget reutilizable `_BuscadorFichas`:

- Caja de búsqueda libre + filtros por Categoría, Marca, Modelo/espec. y
  Nombre, con botón "Limpiar".
- Resultados en un `Treeview` con **scroll** y columnas para reconocer la
  ficha entre muchas: Nombre, Marca, Modelo/espec., Dimensiones, Categoría y
  % de coincidencia.
- La **mejor coincidencia queda seleccionada de primera**; doble clic o Enter
  la activan. Refresco con "debounce" para no releer en cada tecla.
- Se usa en los DOS lugares que el usuario señaló: al **armar un submittal**
  (`TablaMateriales`, activar = agregar el material) y al **gestionar la BD**
  (`VentanaGestionarBD`, activar = editar; con opción "Ver desactivadas" para
  reactivarlas).

| Archivo | Función/Clase | Cambio |
|---|---|---|
| `fuzzy_search.py` | `_match_token` (nueva) | Coincidencia token a token con guardas de longitud. |
| `fuzzy_search.py` | `puntuar` | Reescrita: cobertura + bonus de frase; sin el bug de subcadena. |
| `fuzzy_search.py` | `buscar` | Puntaje multi-campo ponderado; filtros marca/modelo/nombre; orden con desempate; listado por filtros con consulta vacía. |
| `fuzzy_search.py` | `_CAMPOS_PUNTAJE`, `_puntaje_ficha`, `_pasa_filtro` (nuevos) | Pesos por campo y helpers de filtro. |
| `submitals_gui_v3.py` | `_BuscadorFichas` (nueva) | Widget de búsqueda con filtros, columnas y scroll. |
| `submitals_gui_v3.py` | `TablaMateriales` | Usa `_BuscadorFichas` (reemplaza el `Listbox` + `_sugerir`); `_agregar_ficha` como callback. |
| `submitals_gui_v3.py` | `VentanaGestionarBD` | Usa `_BuscadorFichas` (reemplaza su `Treeview` propio + `_refrescar`/`_map`); `_sel` lee del buscador. |

## Compatibilidad

- `fuzzy_search.buscar` mantiene la firma anterior (los nuevos parámetros son
  opcionales), así que `BDManager.buscar` y el diálogo de marcas alternativas
  siguen funcionando y además heredan el mejor scoring.
- No cambia el formato de la BD, del índice ni de `search_keywords`.

## Pruebas

- `python -m unittest test_v3 -v`: mismos 28 tests (incluye `TestFuzzySearch`,
  8 casos), única falla preexistente y no relacionada
  (`test_extraccion_ocr_ficha_real`).
- Smoke test headless del widget con la BD real: buscar "tubo" devuelve 6
  fichas con el tubo de primera y auto-seleccionado; el filtro por marca
  "amanco" deja solo Amanco Wavin; el callback de activación recibe la ficha
  correcta.

---

# Ventanas que se auto-dimensionan (ningún botón queda fuera de pantalla)

## El problema

Varias ventanas abrían con un tamaño fijo (`geometry("820x640")`, etc.) que no
alcanzaba para mostrar todo su contenido — sobre todo tras agregar filas de
filtros y botones en cambios recientes de esta misma entrada. En pantallas
más chicas (laptops) los botones de abajo o de más a la derecha quedaban
fuera de la ventana, inalcanzables sin agrandarla a mano (y `_PinDialog` ni
eso permitía: tenía `resizable(False, False)`).

## La solución

Nuevo helper `_dimensionar_ventana(win, ancho, alto, margen=90)`: calcula el
tamaño **requerido** por el contenido ya construido (`winfo_reqwidth/height`,
que ya suma la barra de botones de abajo y la fila más ancha), lo usa como
piso mínimo (`minsize`) para que la ventana nunca abra —ni el usuario pueda
encogerla— por debajo de lo necesario para ver todo, y todo acotado al
tamaño real de la pantalla del usuario menos un margen. Se aplicó a las 9
ventanas principales (login/PIN, tabla de materiales, cargar ficha, revisar
ficha, generar/abrir submittal, elegir variante de ficha duplicada,
configuración, ventana principal, gestionar BD).

Cuando el contenido pide más alto de lo que cabe en pantalla (ej. la ventana
de generar submittal, que apila 2 tablas), la ventana se abre comprimida al
tamaño de pantalla disponible: las tablas (que tienen `expand=True`) se
encogen, pero la barra de botones de abajo —que NO tiene `expand`— sigue
recibiendo su espacio completo primero, según cómo reparte el espacio
`pack()`. Verificado a propósito simulando una pantalla de 1366×700: la
ventana de generar submittal (que pide 1106px de alto sin comprimir) abre en
610px y el botón "🚀 Generar / Confirmar cambios" sigue con espacio real
asignado, no desaparece.

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `_dimensionar_ventana` (nueva) | Calcula piso desde el contenido requerido, acota a pantalla, centra. |
| `submitals_gui_v3.py` | 9 ventanas (`_PinDialog`, `TablaMateriales`→dialogo editar, `VentanaCargarFicha`, `DialogoRevisarFicha`, `_VentanaSubmittal`, dialogo de variante duplicada, `DialogoConfiguracion`, `App`, `VentanaGestionarBD`) | Reemplaza `geometry()` fijo (o lo agrega donde no había) por `_dimensionar_ventana(...)`. |

## Compatibilidad

No cambia ningún dato ni formato; es únicamente tamaño/posición de ventanas.

## Pruebas

- Simulación con pantalla de 1366×700 (`winfo_screenwidth/height` parcheados)
  para las 4 ventanas más pesadas: todas abren dentro del tamaño de pantalla
  y sus botones de acción (incluidos los del fondo) quedan mapeados con
  tamaño real, no recortados ni invisibles.

---

# Guardrail: "Generar desde BD" ya no resetea el contador de consecutivos por error

## El problema reportado

"Si iba por ESTR32 y agrego otro, debe seguir el flujo (ESTR33), no
resetearse." Se investigó a fondo: la lógica de numeración en sí
(`_siguiente_consecutivo`/`_renumerar`) es correcta — se probó con proyectos
guardados y recargados desde disco, con categorías intercaladas, y siempre
continúa bien (ESTR32 → ESTR33).

La causa real es otra: hay 2 botones distintos para "seguir trabajando en un
submittal" — **"📤 Generar desde BD"** (siempre arranca `materiales_seleccionados`
vacío, pensado para un submittal NUEVO) y **"📂 Abrir submittal existente"**
(carga el progreso guardado). Si se usa el primero apuntando a la MISMA
carpeta de un submittal que ya tenía 32 materiales —algo muy fácil de hacer
si uno solo quiere "continuar" y no repara en que son 2 flujos distintos—
el conteo arranca de 1 en blanco, y además corre riesgo real de pisar el
`submittal_proyecto.json` ya guardado en esa carpeta al generar.

## La solución

En `_generar_desde_bd`, antes de armar un proyecto vacío, se revisa si la
carpeta elegida ya tiene un `submittal_proyecto.json` con materiales. Si lo
tiene, se avisa cuántos materiales hay y se ofrece continuar ESE submittal
(equivalente a "Abrir existente") en vez de empezar uno vacío sin darse
cuenta. Si el usuario confirma que quiere igual uno nuevo, se respeta.

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `App._generar_desde_bd` | Revisa `submittal_proyecto.json` en la carpeta elegida antes de crear un proyecto vacío; si existe con materiales, confirma y redirige a continuarlo. |

## Compatibilidad

- No cambia el formato de `submittal_proyecto.json`.
- Carpetas nuevas (sin submittal previo) siguen el flujo exacto de antes, sin
  preguntas de más.

## Pruebas

- Simulado con `App` real: apuntar "Generar desde BD" a una carpeta con 32
  materiales guardados + confirmar → abre `_VentanaSubmittal` con los 32
  materiales intactos (`titulo="Editando: ..."`), en vez de una lista vacía.
  Apuntar a una carpeta nueva sin submittal previo → sigue el flujo normal
  (proyecto vacío, sin preguntas extra).

---

# La causa real del "reseteo" de consecutivos: cerrar con la X perdía el avance sin guardar

## El problema

El guardrail de la sección anterior no alcanzaba — el usuario reportó que el
contador seguía "reseteándose" incluso usando el flujo correcto. Se investigó
más a fondo: la lógica de numeración (`_siguiente_consecutivo`/`_renumerar`)
se probó exhaustivamente (recarga desde disco, categorías intercaladas,
distintos escenarios) y **siempre** continúa bien (ESTR32 → ESTR33) — nunca
fue ahí el problema.

La causa real: `_VentanaSubmittal` (la ventana donde se arma el submittal) NO
tenía manejador de cierre (`WM_DELETE_WINDOW`). Al cerrarla con la X de
Windows — en vez de tocar explícitamente "💾 Guardar avance" o "🚀
Generar/Confirmar cambios" — se perdía en silencio TODO lo agregado en esa
sesión, sin aviso. Al reabrir después con "Abrir existente", el proyecto
continuaba desde el último guardado real (con menos materiales de los que la
persona alcanzó a ver en pantalla), y el siguiente material agregado quedaba
con un número más bajo del esperado — percibido como "se resetea el
contador", cuando en realidad nunca se había guardado el avance real.

## La solución

`_VentanaSubmittal` ahora guarda el avance SIEMPRE al cerrarse (con la X o
cualquier otro cierre), igual que si se hubiera tocado "Guardar avance", pero
sin popups (silencioso) para no interrumpir el cierre. Si el guardado local
falla (ej. error de disco), recién ahí se pregunta si de verdad quiere cerrar
perdiendo los cambios de la sesión — nunca se pierde nada sin que el usuario
lo sepa y lo confirme.

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `_VentanaSubmittal._guardar_avance` | Nuevo parámetro `silencioso` (omite log y aviso emergente). |
| `submitals_gui_v3.py` | `_VentanaSubmittal._on_close` (nueva) | Guarda el avance en silencio al cerrar; si falla, confirma antes de perder cambios. |
| `submitals_gui_v3.py` | `_VentanaSubmittal.__init__` | `self.protocol("WM_DELETE_WINDOW", self._on_close)`. |

## Compatibilidad

- Mismo mecanismo de guardado que "Guardar avance" (`guardar_submittal` +
  `git_push`); no cambia ningún formato de datos.
- Proyectos ya guardados no se ven afectados; esto solo agrega una red de
  seguridad al cerrar.

## Pruebas

- Repro exacto de punta a punta con una copia aislada de la BD real (nunca se
  tocó `BD_Submittals/` del repo): se agregan 32 materiales ESTR en memoria
  **sin** tocar "Guardar avance", se cierra la ventana con `_on_close()`
  (simulando la X), se recarga el proyecto desde disco con "Abrir
  existente" → los 32 materiales siguen ahí, y el próximo agregado sale
  `ESTR33` como corresponde.
- `python -m unittest test_v3`: mismos 28 tests, misma única falla
  preexistente y no relacionada (`test_extraccion_ocr_ficha_real`).

## Pendiente

Este changelog documenta el diff que ya está en el working tree (sin commit
ni push). Se sumarán más cambios antes de liberar la versión — actualizar
esta entrada (o dividirla) si el alcance final difiere de lo aquí descrito.

---

# Animación al agregar un material a la lista del submittal

## El problema

Al hacer doble clic en una ficha del buscador para agregarla al submittal, la
fila nueva aparecía en la tabla de materiales sin ninguna señal visual: con la
tabla ya larga, no siempre quedaba claro si el clic había surtido efecto o
cuál fila era la recién agregada.

## La solución

El renglón recién agregado se resalta en verde y se desvanece a blanco en
unos pocos pasos (4 tonos, ~110 ms cada uno), además de quedar seleccionado y
visible (`tree.see`). Es una animación puramente visual sobre el
`ttk.Treeview` existente (vía `tag_configure` + `after`), sin dependencias
nuevas.

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `TablaMateriales._refrescar` | Nuevo parámetro `resaltar` (consecutivo a destacar); selecciona y hace scroll a esa fila. |
| `submitals_gui_v3.py` | `TablaMateriales._animar_ingreso` (nueva) | Aplica un tag de color a la fila y lo desvanece en pasos con `after()`. |
| `submitals_gui_v3.py` | `TablaMateriales._agregar_ficha` | Llama a `self._refrescar(resaltar=cons)` en vez de `self._refrescar()`. |

## Compatibilidad

- No cambia ningún formato de datos ni de `submittal_proyecto.json`; es
  únicamente feedback visual en la tabla en memoria.
- `_refrescar()` sigue funcionando igual sin argumentos (usado por "Subir",
  "Bajar", editar y eliminar), que no llevan animación.

---

# "Abrir submittal existente" ahora lista los proyectos de la BD (continuar desde otra PC sin compartir carpeta)

## El problema

Un submittal se arma entre varias personas en distintas PCs (ej. alguien
carga los materiales eléctricos y otra persona sigue con los
arquitectónicos), pero "📂 Abrir submittal existente" solo permitía elegir
una carpeta LOCAL con `submittal_proyecto.json` adentro. Para que la segunda
persona pudiera seguir, necesitaba acceso a la carpeta de la primera (red
compartida, USB, etc.) — justo lo que se quería evitar.

En realidad la BD **ya sincroniza los metadatos del submittal** (materiales,
consecutivos, datos del proyecto) vía GitHub desde v3.1.0, igual que las
fichas técnicas — existía incluso `BDManager.listar_proyectos()` para leerlos,
pero la GUI nunca lo usaba.

## La solución

"📂 Abrir submittal existente" abre ahora un selector (`_SelectorProyectoNube`)
que:

1. Sincroniza con GitHub (`bd.sincronizar()`) y lista los proyectos guardados
   en la BD (`bd.listar_proyectos()`): nombre, cantidad de materiales, última
   actualización y qué PC actualizó por última vez.
2. Al elegir uno y confirmar, se carga directo desde la BD (sin tocar ninguna
   carpeta de otra PC) y se abre para seguir editando.
3. Se puede seguir buscando una carpeta local a mano ("💻 Buscar carpeta en
   esta PC…") para el caso de submittals viejos que nunca se guardaron con
   "Guardar avance" y por lo tanto no están en la BD.

La carpeta de entregables (donde se generan carátulas/compilados/Excel) sigue
siendo local y personal: si la ruta guardada por la última persona no existe
en esta PC, se deja vacía y se pide recién al generar (igual que "Generar
desde BD") — cada quien puede tener la suya sin pisar la del otro.

| Archivo | Función/Clase | Cambio |
|---|---|---|
| `bd_manager.py` | `listar_proyectos` | Suma `actualizado_por` a cada proyecto listado, para mostrar qué PC editó por última vez. |
| `submitals_gui_v3.py` | `_SelectorProyectoNube` (nueva) | Ventana con la lista de proyectos de la BD (sincroniza en segundo plano) + botón para buscar carpeta local. |
| `submitals_gui_v3.py` | `App._abrir_existente` | Usa `_SelectorProyectoNube` en vez de `filedialog.askdirectory` directo; resuelve el destino local de forma segura (solo lo reutiliza si existe en esta PC). |

## Viabilidad de edición simultánea (2 personas al mismo tiempo)

Se evaluó a pedido del usuario. **Con este cambio, NO es seguro que 2
personas editen el MISMO proyecto en simultáneo**: el conflicto de
`submittal_proyecto.json` se resuelve en `git_bd.py` (`_resolver_json_proyecto`)
por archivo completo — "gana la versión más reciente" por marca de tiempo,
sin fusionar materiales por consecutivo (a diferencia de `indice.json`, que sí
fusiona ficha por ficha). Si dos personas agregan materiales al mismo proyecto
casi al mismo tiempo y ambas guardan avance, la que pierde el timestamp pierde
TODOS los materiales que agregó en esa sesión, sin aviso. Quedó fuera de
alcance de este cambio (el usuario prefirió no implementarlo ahora); si más
adelante se necesita edición simultánea seguro, se resolvería extendiendo esa
función para fusionar `materiales_seleccionados` por consecutivo/categoría,
igual que ya se hace con las fichas.

Por ahora, el flujo seguro es el de traspaso: una persona termina su sesión
(que ya guarda solo al cerrar, ver sección anterior de este changelog) y la
otra continúa después desde el selector de la nube.

## Compatibilidad

- No cambia el formato de `submittal_proyecto.json` ni el mecanismo de
  sincronización existente (mismo `guardar_submittal`/`git_push` de siempre).
- Proyectos que nunca se guardaron en la BD (viejos, solo locales) se siguen
  pudiendo abrir con "💻 Buscar carpeta en esta PC…".

## Pruebas

- `python -m unittest test_v3 -v`: 28 tests, misma única falla preexistente y
  no relacionada (`test_extraccion_ocr_ficha_real`, depende de servicio OCR
  externo).

---

# Post-publicación: el workflow de GitHub Actions pasa a disparo manual (evita que corrompa el hash del Release)

## El problema

Al publicar v3.3.7 con `deployment.py --build --release`, el Release quedó
momentáneamente con un `GeneradorSubmittalsES_v3.exe` cuyo hash **no**
coincidía con el registrado en `VERSION.json` — a pesar de que el script local
reportó "subido y verificado con descarga real" para ese mismo archivo.

Causa: `.github/workflows/release.yml` se disparaba automáticamente con
cualquier push de tag `v*`. Al empujar el tag `v3.3.7`, ese workflow corrió EN
PARALELO a `deployment.py --release` y compiló **su propio** `.exe` (en el
runner de GitHub, con Python 3.11, distinto del entorno local usado para
generar `VERSION.json`). Como su paso de subida terminó *después* de que el
script local ya había subido y verificado el suyo, pisó en silencio el asset
del Release con un binario de hash distinto — el workflow no recalcula ni
actualiza `VERSION.json`, así que no puede dejar el Release en un estado
consistente por sí solo. Se detectó comparando a mano el hash de
`VERSION.json` contra el digest publicado (`gh release view --json assets`) y
se corrigió re-subiendo el build local con `gh release upload --clobber`.

## La solución

`.github/workflows/release.yml` cambia su disparador de `push: tags: 'v*'` a
`workflow_dispatch` (solo manual). Ya no corre nunca automáticamente al
empujar un tag, así que no puede volver a competir con `deployment.py`. Queda
documentado en el propio archivo como respaldo de emergencia únicamente (ej.
recompilar desde un entorno limpio si esta PC no tiene las dependencias), con
la advertencia de que quien lo dispare a mano debe re-subir el build local
después para que el Release quede consistente con `VERSION.json`.

Como red adicional (por si el workflow manual se dispara a mano y alguien se
olvida de re-subir el build local, o por si aparece otra causa de
sobrescritura a futuro), `deployment.py` suma una verificación final: después
de subir y verificar cada asset, vuelve a leer el Release YA PUBLICADO (`gh
release view --json assets`) y compara su digest contra el hash del build
local para el exe v3, el exe v2.6 hermano (si hay copia local) y el
instalador. Si algo no coincide, `crear_release()` devuelve `False` y
`main()` corta con error explícito — antes `main()` ignoraba el valor de
retorno de `crear_release()` y siempre imprimía "✅ publicada" aunque la
verificación (o la subida) hubiera fallado; ese bug quedó corregido de paso.

| Archivo | Cambio |
|---|---|
| `.github/workflows/release.yml` | Trigger `on: push: tags: 'v*'` → `on: workflow_dispatch: {}`, con comentario explicando la causa raíz y cómo usarlo a mano sin repetir el problema. |
| `deployment.py` | Nueva `verificar_release_completo(version)`: relee el Release publicado y compara hash contra el build local de cada asset conocido. `crear_release()` ahora devuelve `False` si la verificación final falla. `main()` corregido para de verdad chequear ese retorno (antes lo ignoraba). |
| `CLAUDE.md` | Nueva sección "5. Compilar y publicar una versión": protocolo exacto a seguir (incluye verificar el hash publicado contra `VERSION.json` como paso obligatorio, y no reactivar el trigger automático del workflow). |

## Compatibilidad

- No cambia ningún archivo de la app ni de la BD; es exclusivamente
  infraestructura de publicación (CI + documentación para Claude).
- No amerita una nueva versión de la app: no hay cambio de código ejecutable,
  por eso esta entrada queda dentro del mismo changelog de v3.3.7 en vez de
  abrir v3.3.8.

## Pruebas

- `python -m unittest test_v3 -v`: mismos 28 tests, misma única falla
  preexistente y no relacionada.
- YAML del workflow validado con `yaml.safe_load` tras el cambio (sin errores
  de sintaxis).
- Confirmado a mano que el digest publicado de `GeneradorSubmittalsES_v3.exe`
  en el Release de v3.3.7 quedó igual al hash de `VERSION.json`
  (`82de25828d8ee48eb11e62fc104567e8bc4d886a7026da8f2810130e2c070990`) después
  de la corrección.

---

# Post-publicación: orden de la carpeta de trabajo para el traspaso del proyecto

## El problema

La carpeta de desarrollo acumulaba, mezclados con el código, varios GB de
datos que no son parte de la aplicación: entregas y compilados reales de
proyectos de clientes en la raíz (`ARQUITECTONICOS/`, `ESTRUCTURALES/`,
`MECANICOS/`, `ELECTRICOS/`, `Distribucion/`, `Entregables y Respaldos/`,
`Fichas por ordenar/`, `Prueba especifica v3.1/`, `COMPILADO FINAL SUBMITTAL/`
+ su `.zip`), artefactos de build viejos (7 instaladores anteriores, ya
respaldados para siempre en GitHub Releases), temporales sueltos de sesiones
de trabajo pasadas, y un archivo de versión huérfano
(`VERSION_v3.json`, ningún `.py` lo usa). De cara al traspaso del proyecto a
otra persona, esto hacía difícil distinguir qué es la aplicación de qué es
trabajo de obra ya entregado.

## La solución

- Se movieron (no se borraron) las carpetas/zip de proyectos de clientes a
  una carpeta HERMANA fuera del repo: `Submitals_ES - Proyectos y Entregables
  (archivo)/`. Ninguna de esas rutas está hardcodeada en el código (se
  confirmó con `grep`: `bd_manager.py`/`generate_caratulas.py` arman esas
  rutas siempre a partir de un `destino` elegido por el usuario en tiempo de
  ejecución, nunca de la raíz del repo), así que mover esas carpetas no afecta
  el funcionamiento de la app.
- Se restauró una muestra mínima (3 PDFs reales, ~250 KB) en
  `ARQUITECTONICOS/ESTRUCTURALES/MECANICOS` en la raíz: `test_v3.py`
  (`_fichas_reales`) escanea esas rutas para el caso de prueba con fichas
  reales; el primer intento de mover TODO rompía esa cobertura en silencio
  (los tests pasaban a "skipped" en vez de ejecutar). Esas 3 carpetas siguen
  ignoradas por `.gitignore` igual que siempre, así que esta muestra no viaja
  al repositorio remoto (igual que antes de esta limpieza, quien clona de
  cero ya corría esos tests como "skipped" sin fichas locales).
- Se borraron artefactos regenerables/redundantes: `__pycache__/`, `build/`,
  temporales sueltos (`_probe_write.tmp`, PDFs `tmp*.pass{1,2}.pdf`, logs de
  `generate_caratulas`, `datos_materiales.json` y `Guía interna
  materiales.xlsx` sueltos en la raíz — sobras de corridas de prueba, no
  documentos de referencia), los 7 instaladores de versiones anteriores
  (`Instalador/`, solo queda v3.3.7), y `VERSION_v3.json`.
- Se reubicó documentación histórica sin dependencia de código
  (`README_v3.md`, `INSTRUCCIONES_LANZAMIENTO_v3.0.0.md`) dentro de
  `Documentación/`.
- **No se tocó absolutamente nada de `BD_Submittals/`** (catálogo de fichas,
  índice, metadatos de proyectos) ni `submitals_config.json`: se verificó con
  `git diff --stat -- BD_Submittals` que quedó sin cambios antes de commitear.
- Se verificó antes de mover que nada de lo reubicado fuera una dependencia
  activa: por ejemplo `Tabla visual refresh/assets/` casi se archiva por
  error, pero es de ahí de donde `generate_caratulas.py` (`LOGO_PATH`) y
  ambas GUIs toman el logo de la carátula — se dejó exactamente donde estaba.

| Cambio | Detalle |
|---|---|
| Movidas (no borradas) | `ARQUITECTONICOS/`, `ESTRUCTURALES/`, `MECANICOS/`, `ELECTRICOS/`, `Distribucion/`, `Entregables y Respaldos/`, `Fichas por ordenar/`, `Prueba especifica v3.1/`, `COMPILADO FINAL SUBMITTAL/` + `.zip` → carpeta hermana `Submitals_ES - Proyectos y Entregables (archivo)/`. |
| Restauradas (muestra mínima) | 1 PDF real por categoría en ARQ/ESTR/MEC en la raíz, para no perder la cobertura de `test_v3.py::TestCasosReales`. |
| Borradas | `__pycache__/`, `build/`, `_probe_write.tmp`, `tmp896xizw3.pass1.pdf`, `tmp896xizw3.pass2.pdf`, `tmpf2nghlre.pass1.pdf`, `tmpf2nghlre.pass2.pdf`, `generate_caratulas.log`, `generate_caratulas_report.txt`, `datos_materiales.json` (suelto), `Guía interna materiales.xlsx` (suelta), `Instalador/GeneradorSubmittalsES_Setup_v3.2.1.exe` … `v3.3.6.exe`, `VERSION_v3.json`. |
| Reubicadas dentro del repo | `README_v3.md` → `Documentación/README_v3 (historico).md`; `INSTRUCCIONES_LANZAMIENTO_v3.0.0.md` → `Documentación/`. |

## Compatibilidad

- `BD_Submittals/` sin cambios (verificado, `git diff` vacío para esa
  carpeta).
- No cambia ningún path que la app resuelva en tiempo de ejecución
  (confirmado con `grep` sobre las carpetas/archivos tocados antes de mover
  cada uno).
- El repositorio de trabajo local pasó de ~5.3 GB a ~1.8 GB (queda `.git/`
  con el historial, `dist/` e `Instalador/` con el build ya publicado y
  verificado de v3.3.7, y `BD_Submittals/`).

## Pruebas

- `python -m unittest test_v3 -v`: 28 tests, misma única falla preexistente
  (`test_extraccion_ocr_ficha_real`, servicio OCR externo) — en particular
  `TestCasosReales` vuelve a ejecutar (no "skipped") tras restaurar la
  muestra mínima.
- `python -m unittest test_git_bd test_nomenclatura test_marcas_multiples
  test_tablas_tecnicas`: 94 tests, OK (1 skipped por red/OCR, sin fallas).
