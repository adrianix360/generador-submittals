# CHANGELOG — Generador de Submittals ES v2.6.14

Fecha: 24 de julio de 2026

## Fix: páginas casi en blanco en la carátula

- El fix de v2.6.13 (dimensionar la carátula dinámicamente al alto real del
  contenido) tenía un error: generaba páginas enormes casi en blanco, con el
  contenido real visible solo en una franja pequeña arriba y el resto de la
  hoja vacío.
- Causa: el alto se medía con `document.body.scrollHeight` **después** de
  activar el modo impresión. En modo impresión, el `@page` del CSS (que en
  v2.6.13 se agrandó como respaldo para otros motores de PDF) define una
  caja de página de gran tamaño; Chromium hace que el `body` ocupe el alto
  completo de esa caja en modo impresión, en vez del alto real del
  contenido — por eso la medición salía enorme.
- Corrección: el alto ahora se mide en **modo pantalla**, antes de cambiar a
  impresión, y directamente sobre el elemento de la hoja (`.om-sheet` para la
  carátula clásica, `.ms-sheet` para la del Ministerio de Salud) en vez del
  `body` completo. Esto refleja el contenido real sin importar el tamaño del
  `@page`, y solo puede quedar unos pocos píxeles de más (nunca de menos) por
  pequeñas diferencias de márgenes entre pantalla e impresión.
