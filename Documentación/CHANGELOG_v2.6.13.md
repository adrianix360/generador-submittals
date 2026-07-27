# CHANGELOG — Generador de Submittals ES v2.6.13

Fecha: 24 de julio de 2026

## Fix: carátula cortada y botones de compilado

- **Carátula clásica cortada**: al agregar los nuevos datos de procedimiento
  (v2.6.12), el contenido total superaba una hoja tamaño carta y Chromium
  generaba la carátula en 2 páginas. El compilado individual de cada
  material solo conservaba la primera página (para evitar una segunda hoja
  en blanco que a veces agregaba Chromium), así que el resto del contenido
  quedaba fuera del PDF final.
- Como esta carátula nunca se imprime en papel, la corrección fue dimensionar
  el PDF dinámicamente al alto real del contenido en vez de forzar tamaño
  carta: ahora siempre ocupa una sola hoja completa, sin importar cuántos
  campos o cuán larga sea la observación de un material.
- **"📦 Generar Compilados" (por disciplina) y "Entrega final" no
  funcionaban**: no eran fallas independientes, sino un efecto secundario de
  la misma causa — las carátulas partidas en 2 páginas producían compilados
  con contenido incompleto o páginas de más. Al corregir el tamaño de la
  carátula, ambos botones vuelven a generar los archivos completos y
  correctos.
- Los motores de PDF de respaldo (weasyprint, pdfkit, usados solo si
  Playwright/Chromium no está disponible) también reciben una hoja más alta
  que carta como salvaguarda adicional.
- La carátula del Ministerio de Salud no se modificó (su contenido/diseño no
  se puede tocar); solo se beneficia del mismo motor de render más robusto.

**Corrección adicional tras verificación:** una revisión adversarial de este
mismo fix encontró dos problemas más, ya corregidos:
- El ancho real de la hoja se medía mal (tomaba el viewport por defecto de
  Playwright, 1280px, en vez de los 816px/8.5in reales del diseño), lo que
  generaba páginas ~13 pulgadas de ancho con márgenes en blanco a los lados.
  Ahora el viewport se fija a 816px antes de renderizar.
- El límite de altura usado como respaldo para el motor de PDF (que además
  Chromium usa para decidir dónde cortar el contenido en páginas,
  independientemente del alto exacto que luego se le pide al PDF) era
  demasiado bajo: una carátula con varios campos de texto libre muy extensos
  combinados podía volver a partirse en 2 páginas. Se amplió ese límite a un
  valor que ninguna carátula real alcanza.
- De paso se corrigió otro error (no reportado, encontrado en la misma
  verificación): generar el Excel interno o el de entrega con un JSON sin
  ningún material válido en ninguna disciplina producía un error interno de
  la librería de Excel; ahora devuelve un mensaje claro.

**Importante:** las carátulas que ya se generaron mientras existía este error
seguirán siendo de 2 páginas y cortadas — no se corrigen solas. Para
regenerarlas con el tamaño correcto hay que usar "Forzar (sobreescribir)" o
borrar esas carátulas antes de volver a generar.
