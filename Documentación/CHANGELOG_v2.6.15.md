# CHANGELOG — Generador de Submittals ES v2.6.15

Fecha: 24 de julio de 2026

## Fix definitivo del tamaño de la carátula

- Los dos intentos anteriores (v2.6.13 y v2.6.14) seguían produciendo
  carátulas con problemas de tamaño porque no atacaban la causa de fondo:
  Chromium decide **dónde cortar el contenido en páginas** según el `@page`
  del CSS, de forma completamente independiente al ancho/alto que se le pide
  a `page.pdf()` — ese parámetro solo define el tamaño físico de cada página
  ya recortada, no evita el recorte en sí.
- La plantilla trae un `@page` con un tamaño fijo, usado como respaldo para
  otros motores de PDF (weasyprint). Mientras ese tamaño no coincidiera
  **exactamente** con el alto real del contenido de cada carátula, Chromium
  seguía partiendo el contenido en varias páginas (si el `@page` era más
  chico que el contenido) o dejando la página con espacio en blanco de más
  (si el `@page` era mucho más grande que el contenido).
- Corrección definitiva: justo antes de generar el PDF, ahora se mide el
  alto real del contenido y se **inyecta un `@page` con ese mismo alto
  exacto** (en vez de usar un tamaño fijo de respaldo para este motor). Al
  coincidir siempre el tamaño de página con el contenido real, Chromium ya
  no tiene ningún motivo para paginar de más ni para dejar espacio de sobra:
  la carátula queda siempre en una sola página, ajustada a su contenido,
  sin importar cuántos campos u observaciones tenga.
