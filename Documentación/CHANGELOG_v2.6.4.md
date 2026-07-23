# CHANGELOG — Generador de Submittals ES

## v2.6.4 (2026-07-21) — Elaborado por Adrián Castro

### 🐛 Fix: marcas distintas tratadas como si fueran la misma (logo solo en imagen)
Reportado por la usuaria: en la carpeta de tubos estructurales (ESTR23/ESTR24),
las fichas de **MultiGroup** y **Metalco** se estaban tratando como si fueran
del mismo proveedor.

**Causa raíz encontrada:** el nombre "METALCO" en esa ficha (`FT_Perfil-C-...pdf`)
aparece **únicamente como logo gráfico en la portada**, no como texto
seleccionable — se confirmó extrayendo el texto completo del PDF (1779
caracteres) y verificando que la palabra "METALCO" no aparece en ningún lugar,
y renderizando la portada como imagen para comprobar visualmente que el logo
sí está ahí, pero solo como gráfico. Como `analizar_relacion_fichas()` solo
recibía el texto extraído (sin logos), la IA nunca "veía" la segunda marca y
asumía que ambas fichas eran del mismo fabricante (MultiGroup).

Corrección en `submitals_gui.py`:
- **Nueva imagen de portada enviada a OpenAI Vision** (`_render_portada_b64()`):
  se renderiza la primera página de cada ficha (cuando hay 2+ en una carpeta) y
  se envía junto con el texto a `gpt-4o` (el mismo `VISION_MODEL` ya presente en
  el proyecto, sin agregar otro proveedor), para que la IA pueda leer logos que
  no están en el texto. Se activa únicamente cuando hay 2+ fichas en la carpeta,
  para no encarecer el flujo normal de una sola ficha.
- **Salvaguarda determinista** (`_marcas_claramente_distintas()`): si la IA
  identificó 2+ nombres de marca claramente distintos pero aun así clasificó
  como `MISMO_PROVEEDOR` (inconsistencia), se corrige automáticamente a
  `MISMA_FAMILIA_DISTINTA_MARCA` sin necesidad de una nueva consulta.
- Prompt (`PROMPT_RELACION_FICHAS`) reforzado con una regla explícita: si se
  identifican 2+ marcas distintas (en texto o en el logo de portada), **nunca**
  clasificar como `MISMO_PROVEEDOR`.
- Validado con las fichas REALES de ESTR23 (antes clasificaba mal: marca única
  "MultiGroup"; ahora identifica correctamente `['MultiGroup', 'Metalco']` y
  clasifica `MISMA_FAMILIA_DISTINTA_MARCA`). Se corrigieron los datos de
  ESTR23 y ESTR24 en `datos_materiales.json` y se regeneraron sus carátulas.
- Pruebas de regresión: casos de mismo proveedor y de discrepancia
  (clavos vs. tubería PVC) siguen clasificando igual que antes.

### ✨ Redacción mejorada para "distintas marcas" (aprobación previa por stock)
A pedido de la usuaria, el texto de "Aspectos adicionales" para el caso de
marcas distintas ahora enfatiza el mecanismo de **aprobación previa**: se
solicita la aprobación de las N marcas incluidas en el submittal para poder
instalar cualquiera de ellas ante una eventual falta de stock, sin necesidad de
un nuevo trámite de aprobación en obra.

- Antes: *"...existe la posibilidad de utilizar cualquiera de las marcas... "*
- Ahora: *"Debido a posibles limitaciones de existencias en el mercado, se
  solicita la aprobación de las N marcas incluidas en este submittal, de manera
  que, ante una eventual falta de stock de alguna de ellas al momento de la
  instalación, se cuente con la aprobación previa para emplear cualquiera de
  las marcas alternativas aquí presentadas..."*

### ✅ Sin regresión
Detección de duplicados, borrado total (con JSON), fichas incompletas,
Playwright/render y Excel: intactos.
