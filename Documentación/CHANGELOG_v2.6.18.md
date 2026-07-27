# CHANGELOG — Generador de Submittals ES v2.6.18

Fecha: 24 de julio de 2026

## Carátulas editables (campos de formulario en el PDF)

Ahora **ambas carátulas** (Clásica y Ministerio de Salud) se generan como PDF
con **campos de formulario editables** sobre cada dato. Así se puede corregir
un valor a mano, en cualquier lector de PDF (Adobe, Edge, Chrome…), sin tener
que volver a generar la carátula con la app.

### Cómo funciona
- Cada valor (consecutivo, nombre comercial, fabricante, descripción,
  normativa, observaciones, y en la del Ministerio también los datos del
  proyecto/responsable y la sección de respuesta) queda dentro de un **cuadro
  de texto editable**, ya precargado con su valor.
- Se hace clic en el dato, se corrige y se guarda el PDF — sin pasar de nuevo
  por la aplicación.
- El aspecto visual es idéntico al de antes: el HTML dibuja las cajas y
  etiquetas, y el valor va dentro del campo (no queda texto "quemado" detrás,
  así que al editar no aparece nada duplicado).
- Se conserva el tamaño de una sola página y el estilo (fuente, color y
  alineación de cada campo se toman del propio diseño de la carátula).

### Detalles técnicos
- El motor de render (Playwright/Chromium) mide la posición real de cada caja
  **en modo impresión** (que es distinta a la de pantalla) y, con PyMuPDF
  (fitz), coloca un campo de texto AcroForm sobre cada una.
- Los **compilados** (`-CMP.pdf`) ahora fusionan la carátula con
  `append(...)` en vez de `add_page(...)`, para **no perder** los campos
  editables al unir la carátula con las fichas.
- Si PyMuPDF no estuviera disponible o algo fallara, la carátula se genera en
  su versión plana anterior (no editable) como respaldo, sin interrumpir el
  proceso.
- Solo aplica al motor Playwright (recomendado). Con los motores de respaldo
  (weasyprint/pdfkit) la carátula sale plana, como antes.
