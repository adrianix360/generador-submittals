# CHANGELOG — Generador de Submittals ES v2.6.8

Fecha: 23 de julio de 2026

## Lectura robusta de imágenes degradadas

- Se mide resolución, contraste y nitidez antes de leer una ficha en imagen.
- Las imágenes de mala calidad se amplían y mejoran en memoria; los originales
  nunca se modifican.
- El OCR compara la imagen original, una versión ampliada y una versión binaria,
  conservando saltos de línea para no aplanar las tablas técnicas.
- OpenAI Vision recibe la imagen original, la versión mejorada y tres
  acercamientos con resolución completa.
- La extracción se procesa con `gpt-5.6-sol`; si la cuenta no tiene acceso, la
  aplicación prueba automáticamente modelos alternativos.
- Una segunda lectura visual audita y corrige marca, descripción y normativa.
- El JSON guarda el modelo utilizado, métricas de calidad, confianza, evidencias
  visibles y una bandera de revisión manual.
- Si Vision no está disponible, la aplicación continúa con OCR y el modelo de
  texto, dejando la extracción marcada para revisión.

## Validación

La imagen de prueba de 562 × 471 píxeles fue detectada como degradada y el
resultado final verificado fue:

- Marca: `SIN ESPECIFICAR`
- Descripción: arandela plana estructural F436 tipo 1, negra o galvanizada en
  caliente.
- Normativa: `ASTM F436`
- Confianza: alta en los tres campos.
