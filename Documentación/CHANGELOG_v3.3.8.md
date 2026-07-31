# CHANGELOG v3.3.8 — Marcas por stock más fáciles: duplicar ficha (mismo PDF) + aviso automático de familia

**Fecha:** 2026-07-30
**Estado:** en trabajo — implementado y probado en el working tree, pendiente de
publicar (`deployment.py`).
**Alcance:** carga de fichas al catálogo (`VentanaGestionarBD`) y armado del
submittal (`TablaMateriales`). No cambia el formato de la BD ni del
`submittal_proyecto.json`; reutiliza los mecanismos ya existentes de marcas
alternativas y justificación por stock.

---

## El problema

Varios materiales van al submittal con **varias marcas por stock** (tubo
estructural de hierro negro, hierro galvanizado, tubería PVC, etc.): si al
momento de construir no hay una marca, se aprueba otra equivalente. Armar eso
era tedioso:

1. Agregar el material.
2. Seleccionarlo → "Editar marca(s)".
3. Buscar cada marca alternativa **una por una** en un buscador secundario.
4. Agregarlas y guardar.

Y en el catálogo había un problema aparte con proveedores como **METALCO**, que
documentan **todos** sus tubos estructurales en un **único PDF**, frente a
**MultiGroup**, que usa **una ficha por medida** (cientos de PDFs distintos).
Para catalogar el mismo alcance de METALCO había que **re-subir y re-procesar
(OCR/IA) el mismo PDF una vez por cada medida** — trabajo repetido sin
necesidad.

## La solución (2 mejoras que se complementan)

### 1. Botón "🔗 Duplicar (mismo PDF)" en Gestionar BD

Crea una ficha nueva para **otra especificación** reutilizando el PDF de una
ficha ya cargada, **sin volver a subir ni re-procesar el archivo**. Abre el
mismo diálogo de revisión (pre-llenado con los datos de la ficha original); el
usuario cambia lo que distingue la variante —casi siempre la medida— y el
nombre se regenera solo. Resuelve el caso METALCO: se carga el PDF una vez y se
duplica la ficha por cada medida en segundos.

Bajo el capó, `duplicar_ficha()` es un envoltorio delgado sobre `agregar_ficha()`
(la vía ya probada): reutiliza **toda** su lógica —validación, nombre único,
dedup del archivo, hash, `search_keywords`, índice, pendientes, push—; lo único
que cambia es el **origen** del PDF (la ficha existente en vez de un archivo que
elige el usuario). Cada ficha queda autocontenida (un PDF por ficha, con su
propio nombre y hash), sin rutas compartidas que compliquen la fusión entre PCs.

### 2. Aviso automático de "varias marcas por stock" al agregar un material

Al agregar una ficha al submittal, la app detecta sola si hay **otras fichas de
la misma especificación pero distinta marca** ya en el catálogo y, si las hay,
muestra un aviso: *"Este material tiene N marcas por stock"* con una casilla por
cada marca (todas marcadas por defecto). Al aceptar, esas fichas quedan como
**marcas alternativas** (con su PDF real adjunto) y se activa la **justificación
por stock** — el párrafo legal de la carátula se genera automáticamente al
generar. Baja el flujo de ~5 pasos a 2, sin tener que abrir "Editar material".

La detección de "familia" no necesita una base de datos nueva ni GPT: usa
`nomenclatura.clave_familia()`, que quita el sufijo `` - MARCA`` del nombre
(`nombre_sin_marca`) y normaliza el resto con la misma regla de `clave_unicidad`
(tolerante a cómo cada quien escribe las medidas). Dos fichas de la misma medida
y distinta marca comparten clave; distinta medida no. Es determinístico y
funciona offline.

| Archivo | Función/Clase | Cambio |
|---|---|---|
| `nomenclatura.py` | `clave_familia` (nueva) | Clave normalizada de la especificación ignorando la marca (`clave_unicidad(nombre_sin_marca(...))`). Base de la detección de familia. |
| `bd_manager.py` | `BDManager.fichas_misma_familia` (nueva) | Devuelve otras fichas de igual categoría + `clave_familia`, excluyéndose a sí misma; por defecto solo activas. |
| `bd_manager.py` | `BDManager.duplicar_ficha` (nueva) | Crea una ficha nueva reutilizando el PDF de otra (`ruta_local_ficha` del origen → `agregar_ficha`), sin resubir. |
| `submitals_gui_v3.py` | `VentanaGestionarBD._duplicar` (nueva) + botón | Abre `DialogoRevisarFicha` pre-llenado y llama a `bd.duplicar_ficha()`. Solo sobre fichas activas. |
| `submitals_gui_v3.py` | `TablaMateriales._agregar_ficha` | Tras elegir una ficha, consulta `fichas_misma_familia`; si hay, ofrece agregarlas. La detección nunca impide agregar (si falla, se agrega el material simple). |
| `submitals_gui_v3.py` | `TablaMateriales._preguntar_familia` (nueva) | Popup con la marca principal fija + una casilla por marca alternativa; devuelve las elegidas (`[]` si "solo esta marca" o si se cierra con la X). |

## Compatibilidad

- **No cambia el formato de la BD ni del `submittal_proyecto.json`.** Las marcas
  alternativas y `justificacion_stock` ya existían (v3.3.7); esto solo las
  rellena automáticamente en vez de a mano.
- **No toca la BD real:** las fichas existentes de tubos HN/HG/PVC **no se
  borran**. Si en algún momento se quiere reordenar el catálogo con este flujo,
  se usa el soft-delete reversible ya existente, nunca borrado en duro.
- La ficha duplicada usa exactamente el mismo alta que cualquier ficha nueva, así
  que hereda su sincronización, dedup y resolución de conflictos sin nada nuevo
  que mantener.
- El botón de duplicar solo opera sobre fichas **activas**; el aviso de familia
  solo mira fichas **activas** (no resucita desactivadas).

---

# Buscador de "Editar marca(s)" demasiado chico (no se veían las descripciones completas)

## El problema

Al armar un submittal, el diálogo "Editar marca(s)" tiene un buscador para
agregar marcas alternativas al catálogo. La lista de resultados era un
`Listbox` de solo 4 filas, ancho fijo y sin scroll horizontal: los nombres
largos de fichas (tubos, tuberías, con medida y presentación) quedaban
cortados y no se leían completos.

Además, al revisar el diálogo para este arreglo apareció un bug real
preexistente (de la reescritura de v3.3.7, sin relación con el ticket): la
variable `v_s` (casilla "Justificar por stock") se leía en `_aspectos_auto()`
**antes** de definirse, y el diálogo **crasheaba con `NameError`** al abrirlo
sobre cualquier material sin texto de aspectos ya editado — justo el caso más
común (recién agregado el material). Se corrigió de paso.

## La solución

- El listbox de resultados de búsqueda pasa de 4 a 8 filas, con scrollbar
  **vertical y horizontal** (antes no tenía ninguna) dentro de un contenedor
  que se estira con la ventana.
- El listbox de "marcas alternativas ya elegidas" pasa de 4 a 5 filas y
  también se estira horizontalmente.
- La ventana del diálogo pasa de 620×760 a 820×820.
- Se corrigió el `NameError` moviendo la creación de `v_s` (checkbox
  "Justificar por stock") antes de su primer uso en `_aspectos_auto()`.

| Archivo | Función | Cambio |
|---|---|---|
| `submitals_gui_v3.py` | `TablaMateriales._editar` | Listbox de resultados con scroll H+V dentro de un frame que se estira; listbox de alternativas más alto; ventana más ancha; `v_s` definida antes de su primer uso. |

## Compatibilidad

- Solo cambia tamaños/scroll de widgets y el orden de dos líneas de creación
  de variables; no cambia ningún formato de datos ni el comportamiento de
  guardado.

## Pruebas

- `python -m unittest test_v3 test_nomenclatura`: 97 tests, misma única falla
  preexistente y no relacionada (`test_extraccion_ocr_ficha_real`).
- Smoke test con Tk real (BD temporal aislada): abre `_editar()` sobre un
  material recién agregado (antes crasheaba con `NameError`) — confirma que
  ya no crashea, que la ventana mide ≥780px de ancho, y que el listbox de
  resultados tiene 8 filas de alto con scrollbar horizontal Y vertical.

---

## Pruebas (mejoras de familias de marca, arriba)

- `python -m unittest test_v3.TestBDManager`: 22 tests OK, incluidos 6 nuevos:
  - `test_fichas_misma_familia_agrupa_por_especificacion` — misma medida/otra
    marca agrupa; otra medida no; nunca se incluye a sí misma.
  - `test_fichas_misma_familia_respeta_categoria` — mismo texto en otra
    disciplina no cuenta como familia.
  - `test_fichas_misma_familia_ignora_inactivas_por_defecto` — las
    desactivadas no aparecen salvo que se pidan explícitamente.
  - `test_duplicar_ficha_reusa_pdf_sin_resubir` — la ficha nueva tiene id/ruta
    propios pero PDF byte-idéntico (mismo hash) al de la original.
  - `test_duplicar_ficha_origen_inexistente` — origen inexistente → `BDError`.
  - `test_familia_a_marcas_alternativas_genera_justificacion` — flujo completo:
    familia → `marcas_alternativas` + `justificacion_stock` → la carátula recibe
    el texto legal de "2 fichas técnicas" y adjunta las 2 fichas.
- `python -m unittest test_v3 test_nomenclatura`: 97 tests, única falla
  preexistente y no relacionada (`test_extraccion_ocr_ficha_real`, servicio OCR
  externo).
- Smoke test con Tk real (`TablaMateriales` sobre una BD temporal aislada):
  - material con familia → alternativas + `justificacion_stock` activada;
  - "solo esta marca" → material simple, sin alternativas;
  - material sin familia → el popup ni se invoca.
- Smoke test del popup real `_preguntar_familia`: se arma (grab modal) y se
  destruye sin errores de runtime.
