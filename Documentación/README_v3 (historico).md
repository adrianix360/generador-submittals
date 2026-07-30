# Generador de Submittals ES — v3.2.0

Base de Datos centralizada **en GitHub** con fichas técnicas reutilizables y
**nombres descriptivos únicos**.
**Coexiste con v2.6 sin modificarlo** (la generación desde carpetas sigue igual).

> **v3.0.0 → v3.1.0:** la BD se movió de OneDrive a GitHub. Desapareció el
> archivo `.lock` y el diálogo de "forzar acceso": git resuelve la concurrencia y
> los conflictos se fusionan automáticamente sin perder datos.
>
> **v3.1.0 → v3.2.0:** cada ficha recibe un nombre descriptivo y único
> (`TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup`), revisable antes de
> guardar. Y se pueden **corregir** fichas ya cargadas: editar sus datos,
> regenerar el nombre o reemplazar el PDF.

## Módulos

| Archivo | Rol |
|---|---|
| `submitals_gui_v3.py` | Interfaz principal (menú 2×2) + orquestación de entregables. |
| `bd_manager.py` | BD: índice, fichas, caché, submittals, sincronización. |
| `git_bd.py` | Transporte sobre GitHub (git o API REST) + fusión de conflictos. |
| `nomenclatura.py` | **Nuevo (v3.2.0).** Nombres descriptivos por familia de material. |
| `fuzzy_search.py` | Búsqueda tolerante (umbral 50 %, top 5, filtros). |
| `ocr_extractor.py` | Extracción de fichas: OpenAI Vision → OCR → manual. Sin cambios. |
| `updater_gh.py` | Auto-updater v2.6.7 + sincronización de la BD en una sola operación. |

## Instalar y ejecutar

```bash
pip install -r requirements.txt
python -m playwright install chromium      # para las carátulas
python submitals_gui_v3.py
```

No hay dependencias nuevas de pip. Para el modo preferido hace falta
**Git for Windows** (https://git-scm.com/download/win); si no está instalado, el
programa sincroniza por la API REST de GitHub sin avisar de nada.

### Primer arranque en una PC nueva

1. Abrir el programa → **⚙️ Configurar GitHub**.
2. Pegar un **Personal Access Token**. Se crea en
   https://github.com/settings/tokens → *Fine-grained token* → repositorio
   `adrianix360/generador-submittals` → permiso **Contents: Read and write**.
3. **🔄 Sincronizar ahora**. La primera vez clona la BD (puede tardar un poco).

Cada usuario usa su propio token: así los commits identifican quién cargó qué, y
si un token se filtra se revoca solo ese.

## Arquitectura de almacenamiento

```
github.com/adrianix360/generador-submittals        (un solo repositorio)
  BD_Submittals/
    indice.json                 catálogo de fichas
    ARQ/ ESTR/ MEC/ ELEC/       PDFs de las fichas, por categoría
    Proyectos/<Nombre>/         submittal_proyecto.json  (SOLO metadatos)

%LOCALAPPDATA%/GeneradorSubmittals/bd_repo/   clon de trabajo de la BD
%LOCALAPPDATA%/GeneradorSubmittals/cache/     PDFs en caché (FIFO, máx 2 GB)
%APPDATA%/GeneradorSubmittals/config.json     token de GitHub + API key OpenAI
```

Tres decisiones importantes:

- **El programa nunca trabaja sobre su carpeta de desarrollo.** Clona el
  repositorio aparte, en `%LOCALAPPDATA%`, con *sparse checkout* de
  `BD_Submittals/`. Así un `git pull` de la BD no puede chocar con cambios de
  código sin confirmar.
- **De los proyectos solo se versionan los metadatos.** Las carátulas, los CMP y
  los Excel se quedan en la carpeta local y se regeneran. Versionarlos haría
  crecer el repositorio cientos de MB por proyecto, y GitHub rechaza archivos de
  más de 100 MB.
- **El `.gitignore` re-incluye solo los PDFs de la BD.** Las reglas de v2.6
  ignoran `*.pdf` para no subir documentos de obra; las cuatro carpetas de
  categoría de `BD_Submittals/` son la excepción.

## Flujos

1. **Abrir el programa** — `sync_indice()` en segundo plano: pull, validación de
   integridad del índice, y la barra de estado muestra
   *"Última sincronización: hace 2 min"*.
2. **Generar desde BD** — datos del proyecto → destino → buscar/agregar
   materiales → *Generar entregables* → push de los metadatos.
3. **Cargar ficha a BD** — selecciona PDFs → extracción automática → **revisa el
   nombre generado** (puede editarlo) → guarda y sube a GitHub.
4. **Gestionar BD** — buscar, filtrar, **editar ficha**, **reemplazar PDF**,
   desactivar y reactivar → push.

## Nomenclatura de fichas (v3.2.0)

El nombre se genera según lo que distingue a cada familia de material, con un
criterio simple: que alguien sin formación técnica sepa cuál es cuál.

| Familia | Qué la distingue | Ejemplo |
|---|---|---|
| Tubos y perfiles | forma + dimensiones + calibre | `TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup` |
| Acabados por área | dimensiones + unidad | `CERÁMICA PORCELANATO 60 x 60 cm - Porcelanato Plus` |
| Agregados y comunes | presentación | `CEMENTO HIDRÁULICO SACO 50 kg - Holcim` |
| Eléctricos | tipo y/o modelo | `BREAKER TERMOMAGNÉTICO 2P 60 A QO260 - Schneider` |
| Mecánicos | diámetro + designación | `TUBERÍA PVC 4" SDR 26 - Amanco` |

Tres reglas, por si el resultado sorprende:

- **La normativa no entra en el nombre** (ASTM, ISO, INTE…). Queda en su campo y
  en la búsqueda. Sí entran las designaciones de producto (`CH 13`, `SDR 26`,
  `#12 AWG`, `60 A`), que son las que diferencian una ficha de otra.
- **Las unidades no se inventan:** se conserva la que traiga la ficha. Una
  fracción de pulgada (`3/16`) sí implica pulgadas. La pulgada se repite en cada
  medida; las unidades con letras se escriben una vez al final.
- **Si el nombre no distingue la ficha, no se puede guardar.** El preview dice
  qué dato falta según la familia. Se puede escribir el nombre a mano si el
  sistema no logra armarlo.

El PDF se guarda con ese nombre, así la carpeta de la BD se lee sin abrir el
índice. En carátulas y Excel el material aparece con el nombre **sin la marca**
(que ya tiene su propia columna).

### Corregir una ficha en vez de borrarla

El borrado sigue siendo **lógico y reversible** (`estado: inactivo`, el PDF no se
toca): es lo que permite fusionar dos BDs sin resucitar fichas eliminadas. Lo que
faltaba no era borrar, era corregir:

| Acción | Cuándo usarla |
|---|---|
| **✏️ Editar ficha** | Datos mal extraídos. Regenera el nombre. |
| **📄 Reemplazar PDF** | Ficha bien identificada, archivo equivocado. Conserva el nombre y las referencias de los submittals. |
| **🗑️ Desactivar** | Ficha que ya no se usa. Avisa si algún submittal la referencia. |
| **♻️ Reactivar** | Se desactivó por error. |

Si el nombre de una ficha nueva ya existe, el programa muestra la existente y
ofrece usarla, reemplazar su PDF o guardar la nueva como variante.

## Concurrencia: qué pasa si dos PCs trabajan a la vez

No hay turnos ni bloqueos. El programa reintenta y fusiona:

1. PC1 hace push → OK.
2. PC2 hace push sobre un remoto que ya se movió → rechazado.
3. El programa hace fetch + merge, resuelve el conflicto y reintenta el push.
4. Avisa: *"Conflicto resuelto y sincronizado"*.

La resolución **nunca pierde datos**. Una estrategia `-X ours` a nivel de archivo
borraría las fichas de la otra PC, así que `indice.json` se fusiona a nivel de
**registro**:

| Situación | Resolución |
|---|---|
| Ficha nueva en un solo lado | Se conserva siempre (unión por `id`). |
| Mismo `id` editado en ambos lados | Gana el de `fecha_modificacion` más reciente. |
| Ficha ausente en el remoto | Se conserva: el borrado es lógico (`estado: inactivo`), nunca físico. |
| Dos PDFs distintos con el mismo nombre | Se conservan los dos: el remoto mantiene el nombre, el local pasa a `<nombre>-2.pdf` y su ficha se reapunta. |
| `submittal_proyecto.json` en ambos | Gana el de `ultima_actualizacion` más reciente. |

## Modo sin conexión

Si no hay internet, el programa sigue funcionando contra la copia local y avisa
*"📡 Sin conexión — trabajando con la copia local"*. Los cambios quedan
confirmados localmente y se suben al reconectar (botón *Subir cambios
pendientes*, o al cerrar el programa, que pregunta).

Si el índice descargado no pasa la validación de integridad, se usa el respaldo
en caché y se avisa en lugar de trabajar con datos corruptos.

## Reutilización de v2.6

Al generar, v3 arma la estructura de carpetas + `datos_materiales.json` (esquema
v2.6) y usa el motor existente: carátulas con `generate_caratulas.py`,
compilados CMP por material y por disciplina, y los dos Excel de guía. El
resultado es idéntico al de v2.6.

## Credenciales

| Secreto | Orden de prioridad |
|---|---|
| OpenAI | `OPENAI_API_KEY` → `config.json` v3 (base64) → `submitals_config.json` v2.6 |
| GitHub | `GITHUB_TOKEN` / `GH_TOKEN` → `config.json` v3 (base64) |

`config.json` vive en `%APPDATA%`, fuera del repositorio. **base64 es ofuscación,
no cifrado**: use un token *fine-grained* limitado a este repositorio con
permiso `Contents: write`, para que su filtración no exponga nada más.

## Pruebas

```bash
python -m unittest test_v3 test_git_bd test_nomenclatura -v      # 115 pruebas
```

- `test_v3.py` (26) — fuzzy, `search_keywords`, soft delete, validaciones, caché
  FIFO, credenciales, cambios pendientes; y con **fichas reales** del proyecto:
  alta + búsqueda, submittal completo (materialización + CMP + Excel), índice
  ilegible → caché, extracción OCR.
- `test_nomenclatura.py` (61) — los casos de la especificación, una familia por
  tipo de material, dimensiones (fracciones, pulgadas vs métricas, medida única,
  dict), bordes (dimensiones ya en el nombre, normativas, ficha vacía, números
  que no son medidas), integración con la BD (nombre manual, regeneración,
  duplicados, reemplazo de archivo, migración de fichas antiguas) y una prueba de
  regresión por cada bug que apareció al pasar el generador por las **71 fichas
  reales** del proyecto.
- `test_git_bd.py` (28) — **no necesita internet**. Monta un repositorio *bare*
  local que hace de GitHub y dos clones que hacen de PC1 y PC2, con git de
  verdad; y un GitHub en memoria para el backend REST. Cubre: sincronización
  normal (PC1 carga → PC2 ve), conflicto de índice conservando las dos fichas,
  colisión de nombres de PDF, edición simultánea de la misma ficha, metadatos de
  proyecto entre PCs, sin conexión → sube al reconectar, push rechazado →
  reintenta, repo inaccesible, y que el token nunca aparezca en los mensajes.

Las carátulas requieren Playwright/Chromium, por eso las pruebas de entregables
corren con `con_caratulas=False`.

## Nota sobre `VERSION.json`

El `VERSION.json` que usa el auto-updater v2.6 **no se tocó**: subirlo a 3.x
mientras el repositorio remoto sigue en 2.x haría que el updater intente
"restaurar" archivos antiguos por diferencia de hash. La versión v3 se documenta
en `VERSION_v3.json`. Actualice `VERSION.json` solo cuando el repositorio ya
contenga la v3.
