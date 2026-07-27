# CHANGELOG v3.2.0 — Nomenclatura inteligente de fichas

**Fecha:** 2026-07-27
**Alcance:** cómo se nombran, corrigen y distinguen las fichas. La
sincronización con GitHub (v3.1.0) y la generación de entregables (v2.6) no
cambian.

---

## El problema

Nombres como `Tubería Estructural` o `TUBO RECTANGULAR e INDUSTRIAL` no permiten
saber qué ficha es cuál. Con la BD creciendo, dos tubos distintos aparecían como
dos filas idénticas — en la búsqueda, en las carátulas y en los Excel.

## La solución

Cada ficha recibe un nombre descriptivo y único, generado automáticamente según
la **familia** del material, porque lo que distingue un tubo no es lo mismo que
lo que distingue un saco de cemento:

| Familia | Qué la distingue | Ejemplo |
|---|---|---|
| Tubos y perfiles | forma + dimensiones + calibre | `TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup` |
| | | `TUBO ESTRUCTURAL RECTANGULAR 6" x 2" CH 13 - MultiGroup` |
| Acabados por área | dimensiones + unidad | `CERÁMICA PORCELANATO 60 x 60 cm - Porcelanato Plus` |
| Agregados y comunes | presentación (lo que se compra) | `CEMENTO HIDRÁULICO SACO 50 kg - Holcim` |
| | | `PINTURA ACRÍLICA SATINADA BLANCO CUBETA 5 gal - Sur` |
| Eléctricos | tipo y/o modelo | `BREAKER TERMOMAGNÉTICO 2P 60 A QO260 - Schneider` |
| | | `CABLE THHN #12 AWG - Viakón` |
| Mecánicos | diámetro + designación | `TUBERÍA PVC 4" SDR 26 - Amanco` |

El criterio de diseño, en palabras del usuario: *"lo importante es que una
persona con bajo conocimiento técnico logre distinguir qué material es"*.

---

## Módulo nuevo: `nomenclatura.py`

| Función | Qué hace |
|---|---|
| `generar_nombre_ficha_unico(metadata)` | El nombre completo de la ficha. |
| `analizar(metadata)` | El nombre **más** el detalle: familia, forma, dimensiones, designaciones, presentación, modelo, `suficiente` y `faltantes`. |
| `formatear_dimensiones(origen)` | Acepta texto libre (`8"x8"x3/16"`) o el dict `dimensiones_detectadas`. |
| `decimal_a_fraccion(0.1875)` | `'3/16'`. |
| `nombre_sin_marca(nombre, marca)` | Para carátulas y Excel, donde la marca ya tiene su columna. |
| `clave_unicidad(nombre)` | Detección de repetidos, tolerante al formato. |
| `slug_archivo(nombre)` | Nombre de archivo seguro y legible. |

### Tres reglas que se apartan del plan original

**1. La normativa no entra en el nombre.** El plan era contradictorio: incluía
`ASTM A53` en un ejemplo y omitía `ASTM A500M` en otro. Se resolvió por
indicación del usuario: las normas formales (ASTM, ISO, INTE, ANSI, DIN, NFPA,
UL…) se quedan en su campo y en la búsqueda. No ayudan a alguien sin formación
técnica a distinguir el material.

Sí entran las **designaciones de producto** — `CH 13`, `SDR 26`, `SCH 40`,
`#12 AWG`, `60 A`, `2P` — porque son justamente lo que diferencia una ficha de
otra. Es la distinción que el plan no hacía.

**2. Las unidades no se inventan.** Se conserva la que traiga la ficha; si no
trae ninguna, se escriben los números solos (`45 x 45`). Única excepción
razonable: una fracción típica de pulgada (`3/16`, `1/2`, `1 1/4`) implica
pulgadas. Convención de escritura: la pulgada se repite en cada medida
(`8" x 8" x 3/16"`) y las unidades con letras se escriben una vez al final
(`60 x 60 cm`), que es como se leen en obra.

**3. `TUBO RECTANGULAR E INDUSTRIAL` → `TUBO RECTANGULAR INDUSTRIAL`.** La "e"
era un artefacto de la extracción, no parte del nombre. (El plan la incluía en
su lista de ejemplos y la omitía en su unit test.)

---

## Preview antes de guardar (`DialogoRevisarFicha`)

Al cargar una ficha, el nombre generado aparece arriba, **editable**:

- Se recalcula en vivo mientras se corrigen los campos.
- Deja de recalcularse en cuanto el usuario lo escribe a mano; el botón
  **↻ Regenerar** lo vuelve a tomar del sistema.
- **Valida que el nombre distinga la ficha.** Si no hay dimensiones,
  presentación ni modelo, el aviso se pone en rojo, dice *qué dato falta según la
  familia* y el botón Guardar queda deshabilitado. Escape: si el usuario escribe
  a mano un nombre que sí distingue (contiene números o es suficientemente
  específico), se acepta — la persona sabe más que la heurística.
- **Nombre repetido:** se muestra la ficha existente y se ofrece *usar la que ya
  existe*, *reemplazar su PDF* o *guardar como variante*.

---

## Corregir en vez de borrar

El plan pedía cambiar el soft delete por **hard delete**. Analizándolo con el
usuario quedó claro que la necesidad de borrar venía de no poder **corregir** una
ficha mal nombrada. Y el hard delete tenía un costo concreto: rompía una garantía
de la v3.1.0 — el merge conserva toda ficha que exista localmente y falte en el
remoto, *porque el borrado era lógico*. Con hard delete, si PC1 borraba una
ficha, **PC2 la resucitaba** apuntando a un PDF que ya no existía. Evitarlo
habría exigido lápidas en el índice.

Se resolvió agregando lo que faltaba:

| Acción nueva | Para qué |
|---|---|
| **✏️ Editar ficha** | Corrige los datos y regenera el nombre. Doble clic en la lista. |
| **📄 Reemplazar PDF** | Ficha bien identificada, archivo equivocado. Conserva el `id`, el nombre y las referencias de los submittals. |
| **♻️ Reactivar** | Deshace una desactivación. |
| **Aviso de ficha en uso** | Antes de desactivar, lista los submittals que la referencian y advierte que no podrán regenerarse. |
| **Generar nombres** | Al abrir Gestionar BD, ofrece nombrar las fichas cargadas con versiones anteriores. |

---

## Cambios en el índice

```json
{
  "id": "uuid",
  "nombre_ficha": "TUBO ESTRUCTURAL CUADRADO 8\" x 8\" x 3/16\" - MultiGroup",
  "nombre_ficha_manual": false,
  "nombre_material": "Tubo Estructural",
  "marca": "MultiGroup",
  "ruta_pdf": "ESTR/TUBO-ESTRUCTURAL-CUADRADO-8-x-8-x-3-16-MultiGroup.pdf"
}
```

El PDF se guarda con el nombre descriptivo, así la carpeta de la BD se puede leer
sin abrir el índice. `nombre_ficha` entra primero en `search_keywords`: quien
busca `tubo 8` encuentra la ficha por su nombre completo.

**Compatibilidad:** las fichas de v3.1.0 sin `nombre_ficha` siguen funcionando —
`BDManager.nombre_de()` lo calcula al vuelo, y `migrar_nombres_ficha()` lo
persiste (también por CLI: `python bd_manager.py --migrar-nombres`).

---

## Entregables

Al agregar un material desde la BD, el submittal hereda el nombre descriptivo
**sin la marca** (que ya tiene su propia columna en carátulas y Excel):
`TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16"`. Así dos tubos del mismo tipo dejan
de aparecer como dos filas idénticas en la Guía Submittal.

---

## Revisión independiente: 13 bugs corregidos

Se pasó el generador por las **71 fichas reales** de `datos_materiales.json` del
proyecto. Ahí aparecieron fallos que los casos sintéticos no tocaban — la
mayoría por texto en mayúsculas y por prosa en español:

| # | Qué fallaba | Con qué entrada |
|---|---|---|
| 1 | `100X100X2` **no detectaba ninguna dimensión** (la `X` mayúscula no separaba) → el botón Guardar quedaba deshabilitado con una ficha correcta | `dimensiones: "60 X 60 cm"` |
| 2 | La pista de familia `cal` capturaba `calibre`, `calidad` y `caliente` → un tubo "galvanizado en caliente" se clasificaba como agregado y perdía el modelo | `especificacion: "CH 13, galvanizado en caliente"` |
| 3 | `EN` en la lista de normativas se comía la preposición española | `"disponible en 12 AWG"` perdía el calibre |
| 4 | `1/0`, `2/0`, `4/0 AWG` colapsaban a `#0 AWG` → dos cables distintos con el mismo nombre | `"2/0 AWG"` |
| 5 | `grado`/`clase` capturaban la palabra siguiente | `"grado de humedad"` → `GRADO DE` |
| 6 | La `A` de un rango se leía como amperios | `"espesor de 20 A 30 mm"` |
| 7 | Una unidad compuesta se tomaba como presentación | `"concreto 210 kg/cm2"` → *saco de 210 kg* |
| 8 | Un rango daba el extremo superior como medida | `"tejas de 400 a 500 mm"` → `500 mm` |
| 9 | `CAL.24` y `#26` no se reconocían como calibre → bloqueaban el guardado | fichas reales de lámina |
| 10 | Un `.jpg` se guardaba como `.pdf` → `pypdf` fallaba y el CMP salía **con la carátula sola**, sin aviso | cargar una ficha escaneada en imagen |
| 11 | Editando una ficha duplicada, elegir "reemplazar PDF" **descartaba la edición en silencio** | flujo de edición |
| 12 | Cualquier tecla (flecha, Tab, Ctrl) marcaba el nombre como manual → no se regeneraba nunca más | preview |
| 13 | La migración de nombres reescribía `fecha_modificacion` → una migración cosmética le ganaba a una edición real de otra PC | dos PCs |

Otros arreglos menores del mismo repaso: el caché se invalida por **hash** y no
por tamaño (un reemplazo del mismo peso seguía devolviendo el archivo viejo);
`materializar_proyecto` empareja por **consecutivo** y no por posición (con la
lista desordenada el PDF iba a la carpeta de otro material); `inf`/`NaN` en el
JSON del OCR ya no llegan como *traceback*; el dict de dimensiones usa lista
blanca de claves (`"confianza": 0.97` entraba como medida); y un calibre pegado al
nombre no se duplica (`LÁMINA ESMALTADA #26` → `... CH 26`, no `#26 CH 26`).

Resultado sobre las 71 fichas del proyecto: **39 se nombran solas** y 32 piden un
dato al usuario — que es exactamente lo que se buscaba, porque son las que hoy no
se pueden distinguir.

## Pruebas: 115 en total, sin internet

`test_nomenclatura.py` (61, nuevo) — incluye una prueba de regresión por cada bug
de la tabla anterior y una que pasa el generador por las 71 fichas reales:

- Los cinco casos de la especificación, con las desviaciones documentadas arriba.
- Una familia por tipo de material y el mensaje de "qué falta" de cada una.
- Dimensiones: fracciones (`0.1875 → 3/16`), pulgadas vs métricas, medida única
  (`4"`, `Ø 2 1/2"`), dict con y sin unidad, y que un número sin unidad dentro de
  texto libre **no** se tome como dimensión (`"resistente hasta 50 años"`).
- Bordes: dimensiones ya presentes en el nombre (no se duplican), forma repetida,
  normativas eliminadas, ficha vacía, falta de marca, `"a 60 grados"` que no debe
  leerse como 60 amperios.
- Integración: alta con nombre y PDF nombrado, nombre manual respetado,
  regeneración forzada, búsqueda por el nombre nuevo, duplicados tolerantes al
  formato, reemplazo de archivo (con validación, ajuste de extensión e
  invalidación del caché), soft delete reversible, migración idempotente y aviso
  de ficha en uso.

Otro bug que encontraron las pruebas: en `8"x8"x3/16"` la alternancia del regex
capturaba `3` en lugar de `3/16` (la fracción debía probarse antes que el
decimal).

`test_v3.py` (26) y `test_git_bd.py` (28) siguen pasando sin cambios de
comportamiento: **sin regresión** en sincronización ni en generación de
entregables.
