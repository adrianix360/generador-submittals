# CHANGELOG — Generador de Submittals ES v2.6.17

Fecha: 24 de julio de 2026

## Consecutivo inicial por disciplina (función remedial / temporal)

> ⚠️ Esta función es un remedio puntual, **no forma parte del diseño
> definitivo**. Resuelve el caso de un proyecto cuya lista de submittals debe
> continuar la numeración de otra lista previa (hecha sin la app) en vez de
> reiniciarla.

- En la sección **🔢 CONSECUTIVO INICIAL (temporal)** se puede indicar, por
  cada disciplina (ARQ, ESTR, MEC, ELEC), el número desde el cual arranca su
  consecutivo. Ejemplo: si ARQ se pone en **35**, la primera carpeta ARQ sale
  como **ARQ35**, la siguiente **ARQ36**, y así sucesivamente.
- La numeración es **en secuencia**: se ignora el número que traiga el nombre
  de la carpeta y se numera en orden desde el inicio indicado (si hay huecos,
  como ARQ01, ARQ03, ARQ07, quedan igual ARQ35, ARQ36, ARQ37).
- El **nombre de las carpetas NO cambia**; solo cambia el consecutivo que se
  imprime en la carátula, el nombre del compilado (`-CMP.pdf`) y el Excel.
- Las disciplinas cuyo campo se deje **vacío** conservan la numeración normal
  de siempre.
- Para no dejar la renumeración activada por descuido en otro proyecto, los
  campos **no se guardan** en la configuración: arrancan vacíos en cada
  sesión. Antes de generar, la app pide confirmación mostrando qué disciplinas
  se van a renumerar.
- Recordatorio importante: para reemplazar carátulas/compilados ya generados
  con el número anterior, hay que tener activo **"Forzar regeneración"**; de lo
  contrario la app respeta las carátulas existentes y no las vuelve a crear.
