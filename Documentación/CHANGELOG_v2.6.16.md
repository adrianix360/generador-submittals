# CHANGELOG — Generador de Submittals ES v2.6.16

Fecha: 24 de julio de 2026

## Columna "Proveedor" en la Guía interna de materiales

- Cada hoja de "Guía interna materiales.xlsx" (Arquitectónicos, Estructurales,
  Mecánicos, Eléctricos) ahora incluye una sexta columna, "Proveedor".
- Es de llenado **manual**: la app nunca escribe un valor en ella, porque
  depende del stock de cada proveedor y no se puede automatizar.
- Como este Excel se regenera por completo cada vez que se actualiza la guía,
  si el archivo ya existía se leen primero los valores que el usuario haya
  escrito en "Proveedor" (emparejando filas por Consecutivo) y se vuelven a
  colocar en el archivo nuevo, para que no se pierdan al actualizar.
