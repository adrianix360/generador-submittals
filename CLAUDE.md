# Instrucciones para Claude en este proyecto

Este archivo se lee automáticamente al inicio de cada sesión de Claude Code en
este directorio. Las siguientes reglas aplican a **todos los cambios**, sin
importar el tamaño o la instrucción específica que las origine.

## 1. Todo cambio va a un changelog

Después de modificar código, siempre se debe dejar constancia en un changelog
— **no es opcional a menos que el usuario lo indique explícitamente** en esa
misma instrucción (p. ej. "no actualices el changelog esta vez").

Convención de este proyecto:

- Los changelogs de versión viven en `Documentación/CHANGELOG_vX.Y.Z.md`
  (ver ejemplos existentes para el formato: problema, solución, tabla de
  cambios, pruebas).
- `VERSION.json` tiene un campo `"changelog"` de una línea que resume la
  versión actual — actualízalo también si el cambio corresponde a un
  incremento de versión.
- Si el cambio es menor y no amerita una nueva versión, igual debe quedar
  registrado (aunque sea una entrada breve) para mantener trazabilidad de qué
  se hizo y cuándo.
- Nunca cierres una tarea de código sin haber creado o actualizado la entrada
  correspondiente. Si terminaste una sesión de cambios sin hacerlo, es un
  error a corregir antes de continuar.

## 2. Pedir permiso para salirse del alcance

Si mientras se trabaja en algo aparece la necesidad de modificar archivos,
funciones o comportamiento que **no** fueron pedidos explícitamente en la
instrucción actual:

- Detente y pide permiso antes de tocarlo.
- Explica brevemente qué se modificaría y **qué riesgo tiene** (p. ej. "esto
  también afecta la generación de carátulas de otros módulos" o "cambia el
  formato del índice y podría romper compatibilidad con fichas viejas").
- No asumas que una autorización previa para un cambio cubre cambios
  adicionales fuera de ese alcance, aunque parezcan relacionados.

## 3. La base de datos no se toca sin permiso explícito

Nunca se debe alterar la base de datos (`BD_Submittals/`, el índice de
fichas, `datos_materiales.json`, o cualquier dato ya cargado por el usuario)
ni hacer nada que pueda ponerla en riesgo — incluyendo migraciones, scripts
de limpieza, cambios de esquema, hard deletes, o cualquier operación
irreversible sobre datos reales — **a menos que el usuario lo pida
explícitamente** en esa instrucción.

Esto incluye evitar operaciones "de prueba" contra la BD real: si se necesita
probar algo, usar datos de prueba o una copia, no la base en uso.

## 4. Prioridades de diseño

Ante cualquier decisión de diseño o implementación, en este orden:

- **Experiencia de usuario**: que el resultado sea claro y fácil de usar para
  alguien sin conocimiento técnico profundo (criterio ya usado en este
  proyecto, ver `Documentación/CHANGELOG_v3.2.0.md`).
- **Facilidad de uso de la app**: preferir la solución que requiera menos
  pasos, menos configuración y menos posibilidad de error del usuario.
- **Compatibilidad**: tanto de la app (que siga funcionando con datos e
  instalaciones anteriores) como de los datos generados (que las fichas,
  índices y entregables previos sigan siendo válidos y legibles).

Cuando estas prioridades entren en conflicto con "la forma más simple de
programarlo", gana la prioridad de diseño, no la comodidad de implementación.

## 5. Compilar y publicar una versión (build + release)

Cuando se pida "compilar", "generar el instalador", "publicar una versión",
"subir a GitHub" o equivalente, el protocolo único y completo es
`deployment.py` (raíz del proyecto) — no armar los pasos a mano ni improvisar
comandos sueltos de PyInstaller/ISCC/git/gh. Seguir esto en orden:

1. **Versión**: el siguiente consecutivo a `VERSION.json` (campo
   `"version"`). Si ya existe un `Documentación/CHANGELOG_vX.Y.Z.md` marcado
   "en trabajo" (ver sección 1), esa es la versión a usar — no inventar una
   distinta.
2. **Antes de compilar**, revisar `git status`: si hay archivos que no
   deberían ir al repo (salidas de herramientas/skills como `graphify-out/`,
   cachés, temporales), agregarlos a `.gitignore` ANTES de correr el script —
   `deployment.py` hace `git add -A` y no filtra nada por su cuenta.
3. **Changelog/commit**: redactar UN resumen en un solo párrafo (sin saltos
   de línea, sin bullets ni markdown), en español, que sirva a la vez como
   mensaje de commit y como campo `"changelog"` de `VERSION.json` — así son
   los commits existentes del repo (ver `git log`).
4. **`gh` (GitHub CLI)**: si `gh auth status` falla por no encontrarse en el
   PATH de la sesión, no asumir que no está instalado — buscarlo en
   `C:\Program Files\GitHub CLI\gh.exe` y agregar esa carpeta al `$env:Path`
   del proceso donde se va a correr `deployment.py`.
5. **Ejecutar**:
   `python deployment.py X.Y.Z "resumen de un párrafo" --build --release`
   Esto hace TODO en el orden correcto: bump de versión en los archivos
   correspondientes, tests (si existe `TESTS_RAPIDOS.py`), `VERSION.json` con
   hashes, compila el `.exe` (PyInstaller) y el instalador (Inno Setup vía
   `ISCC.exe`), commit + push (con reintento fetch+rebase si lo rechazan por
   sync concurrente de la BD desde otra PC), y crea el Release en GitHub
   subiendo exe + instalador con verificación de hash por descarga real.
6. Esto tarda (PyInstaller con pandas/numpy + subida/verificación de assets
   de ~100-300 MB puede llevar 10-20 minutos): correrlo en background y
   esperar la notificación, no bloquear ni cortar por parecer lento.
7. **Verificación final obligatoria, siempre, sin excepción**: comparar el
   hash de `VERSION.json` (`archivos["GeneradorSubmittalsES_v3.exe"]["hash"]`)
   contra el digest real publicado en el Release
   (`gh release view vX.Y.Z --json assets`). Si no coinciden, volver a subir
   el exe local (`gh release upload vX.Y.Z dist\GeneradorSubmittalsES_v3.exe
   --clobber`) y verificar de nuevo. Nunca dar la publicación por buena solo
   porque el script terminó sin errores — puede reportar "verificado" y
   quedar pisado después por una causa externa (ver punto 8).
8. **`.github/workflows/release.yml` es SOLO MANUAL** (`workflow_dispatch`),
   a propósito — no reactivar su disparo automático por push de tag. Si se
   dispara, compila su propio `.exe` en un entorno distinto (Python 3.11 en
   el runner de GitHub) y lo sube al mismo Release con un hash distinto al
   que calculó `deployment.py` localmente; eso corrompió la consistencia del
   Release de v3.3.7 (detectado y corregido). Si alguna vez se dispara a
   mano como respaldo de emergencia, hay que recordar re-subir el build
   local después para que el Release quede consistente con `VERSION.json`.
