# CHANGELOG — Generador de Submittals ES

## v2.6.1 (2026-07-21) — Elaborado por Adrián Castro

### 🐛 Fix: falsos positivos en "Detectar Duplicados" (materiales distintos por tamaño/tipo)
Reportado por la usuaria con capturas reales: el detector marcaba como
"duplicados" materiales de la misma marca/familia y normativa pero de **tamaño
o tipo distinto** — ej. costanera MultiGroup 3"x2" (75x50mm) agrupada con la de
4"x2" (100x50mm) al 97% de similitud; uniones/codos/reducciones/yee PVC Wavin de
distinto diámetro (50mm, 100mm, 150mm) agrupados entre sí al 83-89%. Causa: la
descripción de fichas de la misma familia comparte mucho texto de plantilla
(marca, "Cédula 40", normativa "NMX-E-031", frases de unión cementada, etc.), y
ese texto compartido dominaba el cálculo de similitud (`difflib`), ocultando que
la medida/diámetro específico era distinto.

Corrección en `detectar_duplicados()` (`submitals_gui.py`):
- **Veto duro por dimensiones** (`_extraer_dimensiones()` /
  `_dimensiones_compatibles()`): se extraen las medidas del nombre+descripción
  (patrones `50MM`, `2IN`, `3"`, `70x1.5`, `3/4`, etc.); si dos materiales tienen
  medidas detectadas y **difieren**, NUNCA se marcan como duplicados, sin
  importar qué tan parecido sea el resto del texto.
- **Umbral de similitud más estricto**: `UMBRAL_DUPLICADO` 0.82 → **0.95**;
  `UMBRAL_DUPLICADO_MISMO_NOMBRE` (cuando dos carpetas comparten nombre) 0.60 →
  **0.75**. Ahora solo coincidencias casi textuales (la misma ficha, releída dos
  veces) se marcan como posible duplicado.
- **Agrupamiento por "clique" en vez de "estrella"**: antes, un material se
  sumaba a un grupo si coincidía solo con el primer material del grupo (el
  "ancla"), permitiendo cadenas de similitud que terminaban agrupando
  materiales que en realidad NUNCA se compararon entre sí directamente (ej.
  `MEC08`+`MEC10`+`MEC12`+`MEC14`+`MEC15` aparecían juntos en un solo grupo).
  Ahora un material solo entra a un grupo si coincide (dimensiones + similitud)
  con **todos** los materiales ya presentes en ese grupo.
- Validado reconstruyendo los 4 grupos exactos de la captura reportada (costanera
  MultiGroup, uniones/codos/reducciones/yee PVC Wavin): los 4 grupos falsos
  desaparecen (0 grupos detectados) con la corrección; se agregaron pruebas de
  regresión confirmando que un duplicado real (misma ficha en dos carpetas, con
  o sin el mismo nombre de carpeta) se sigue detectando correctamente, y que el
  veto por dimensiones aplica incluso cuando el nombre de carpeta es idéntico.

### ✅ Sin regresión
`resolver_duplicados()` (cuarentena, reordenamiento de consecutivos, limpieza de
carátulas/compilados obsoletos) no se modificó; solo cambió el criterio de
detección previo a mostrarle el diálogo al usuario.
