#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 updater_gh.py  --  Actualizacion desde GitHub (Generador Submittals ES v3)
================================================================================
Conserva el sistema de auto-actualizacion de v2.6.7 (``auto_updater.py``): NO
lo reemplaza, lo envuelve. Compara ``VERSION.json`` remoto (GitHub) contra los
archivos locales por hash SHA-256 y descarga solo lo que cambio.

Se expone una API pequena y estable para que ``submitals_gui_v3`` la use sin
depender de los detalles internos de ``auto_updater``:

    updater_gh.hay_actualizacion(logf) -> dict
    updater_gh.aplicar(info, progreso, logf) -> (ok, mensaje, requiere_reinicio)
    updater_gh.reiniciar()
    updater_gh.configurado() -> bool

Si ``auto_updater`` no esta disponible (o no esta configurado el repo), todas
las funciones degradan de forma segura (no lanzan).
================================================================================
"""

import logging

log = logging.getLogger("updater_gh")


def _au():
    """Importa auto_updater de forma perezosa; None si no esta disponible."""
    try:
        import auto_updater
        return auto_updater
    except Exception as e:
        log.warning("auto_updater no disponible: %s", e)
        return None


def configurado():
    """True si el repositorio de actualizaciones esta configurado."""
    au = _au()
    return bool(au and au.configurado())


def version_local():
    au = _au()
    if not au:
        return ""
    try:
        return au.leer_version_local().get("version", "")
    except Exception:
        return ""


def hay_actualizacion(logf=None):
    """Verifica si hay una actualizacion disponible.

    Devuelve el dict de ``auto_updater.verificar_actualizacion`` (con claves
    ``disponible``, ``version_local``, ``version_remota``, ``changelog``,
    ``archivos``, ``requiere_pip``, ``requiere_exe``, ``error``). Nunca lanza.
    """
    au = _au()
    if not au:
        return {"disponible": False, "error": "Modulo de actualizacion no disponible",
                "archivos": [], "version_local": "", "version_remota": ""}
    if not au.configurado():
        return {"disponible": False, "error": "Auto-actualizacion no configurada",
                "archivos": [], "version_local": au.leer_version_local().get("version", ""),
                "version_remota": ""}
    try:
        return au.verificar_actualizacion(logf=logf)
    except Exception as e:
        return {"disponible": False, "error": f"Error al verificar: {e}",
                "archivos": [], "version_local": "", "version_remota": ""}


def aplicar(info, progreso=None, logf=None):
    """Descarga y aplica una actualizacion de codigo (.py/.html/requirements).

    Devuelve ``(ok: bool, mensaje: str, requiere_reinicio: bool)``.
    """
    au = _au()
    if not au:
        return (False, "Modulo de actualizacion no disponible", False)
    try:
        return au.aplicar_actualizacion(info, progreso=progreso, logf=logf)
    except Exception as e:
        return (False, f"Error al aplicar actualizacion: {e}", False)


def preparar_exe(info, progreso=None, logf=None):
    """(Modo empaquetado) descarga el nuevo .exe y prepara el swap al cerrar."""
    au = _au()
    if not au:
        return (False, "Modulo de actualizacion no disponible")
    try:
        return au.descargar_exe_y_preparar_swap(info, progreso=progreso, logf=logf)
    except Exception as e:
        return (False, f"Error al preparar el ejecutable: {e}")


def aplicar_y_sincronizar(info, bd=None, progreso=None, logf=None):
    """Actualiza el app Y sincroniza la BD en una sola operacion (v3.1.0).

    El codigo y la BD viven en el mismo repositorio, asi que conviene dejar los
    dos al dia a la vez. Tras aplicar la actualizacion se hace ``sync_indice()``
    (pull + validacion de integridad del indice).

    Devuelve ``(ok, mensaje, requiere_reinicio, resumen_bd)``.
    """
    ok, mensaje, reinicio = aplicar(info, progreso=progreso, logf=logf)
    resumen = {}
    if bd is not None:
        try:
            _data, resumen = bd.sync_indice()
            if resumen.get("indice_invalido"):
                mensaje += ("\n\nAVISO: el indice de la BD no paso la validacion; "
                            "se esta usando la copia local.")
            elif resumen.get("offline"):
                mensaje += "\n\nLa BD no se pudo sincronizar (sin conexion)."
            else:
                mensaje += f"\n\nBD sincronizada: {resumen.get('fichas', 0)} fichas."
        except Exception as e:
            log.error("No se pudo sincronizar la BD tras actualizar: %s", e)
            mensaje += f"\n\nAVISO: la BD no se sincronizo ({e})."
    return (ok, mensaje, reinicio, resumen)


def lanzar_swap():
    """(Modo empaquetado) instala el .exe descargado y cierra la app.

    Debe llamarse solo despues de ``preparar_exe`` haber devuelto ok=True.
    Ejecuta el .bat que reemplaza el .exe y termina el proceso actual para
    soltar el archivo (no retorna).
    """
    au = _au()
    if au:
        au.lanzar_swap_y_salir()


def reiniciar():
    """Reinicia la app (modo Python) tras aplicar una actualizacion."""
    au = _au()
    if au:
        try:
            au.reiniciar_app()
        except Exception as e:
            log.error("No se pudo reiniciar: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("configurado:", configurado(), "| version local:", version_local())
    print(hay_actualizacion(logf=print))
