# CHANGELOG — Generador de Submittals ES

## v2.6.3 (2026-07-21) — Elaborado por Adrián Castro

### 🔧 "Borrar Carátulas y Compilados" ahora también elimina el JSON
El botón **🗑️ Borrar Carátulas y Compilados (empezar de 0)** (v2.6.2) dejaba
intacto `datos_materiales.json`, argumentando que los datos ya extraídos con
ChatGPT no debían perderse. Corregido a pedido: para que "empezar de 0" sea
realmente de cero, ahora también elimina `datos_materiales.json`.

- `borrar_caratulas_y_compilados()`: además de carátulas/compilados, borra
  `datos_materiales.json` de la carpeta base (si existe); devuelve
  `json_eliminado: bool` en el resultado. Sigue sin tocar las fichas técnicas
  originales de cada carpeta.
- El diálogo de confirmación ahora advierte explícitamente que el JSON se
  eliminará y que la próxima generación deberá volver a leer todas las fichas
  con ChatGPT (vuelve a consumir la API de OpenAI) — antes decía lo contrario.
- Al completarse el borrado, la GUI vuelve automáticamente al modo **"generar
  JSON automático"** (el modo "usar JSON existente" quedaría apuntando a un
  archivo borrado), lista para regenerar todo desde cero con un clic en
  GENERAR.
- Validado: se confirma que el JSON se elimina cuando existe, que las fichas
  técnicas originales permanecen intactas, y que ejecutar la función una
  segunda vez (sin JSON presente) no produce error.

### ✅ Sin regresión
El resto del comportamiento del botón (borrado de `CARATULA*.pdf`,
`*-CMP.pdf` y `CMP SUBMITTAL *.pdf`, confirmación previa, reporte de
resultados) no cambió.
