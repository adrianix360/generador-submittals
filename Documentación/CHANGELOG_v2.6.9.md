# CHANGELOG — Generador de Submittals ES v2.6.9

Fecha: 23 de julio de 2026

## Excel interno vs. excel de entrega

- El excel de uso interno de oficina se renombró a **"Guía interna
  materiales.xlsx"** (antes "Guía Materiales.xlsx"). Sigue generándose igual
  que antes: una hoja por disciplina con Consecutivo, Familia, Descripción,
  Normativa y Estado.
- Al exportar la versión final ("COMPILADO FINAL SUBMITTAL") ya no se copia
  el excel interno. En su lugar se genera **"Guía Submittal.xlsx"**, pensado
  para entregar a la administración del contrato:
  - Una hoja por carpeta madre (Arquitectónicos, Estructurales, Mecánicos,
    Eléctricos).
  - Solo 4 columnas: Consecutivo, Descripción (nombre de la carpeta de cada
    material), Aprobación y Observaciones (estas dos últimas en blanco, para
    que las complete la administración).
  - Sin datos internos (familia/marca, normativa, estado).
