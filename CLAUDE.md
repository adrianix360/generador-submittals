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
