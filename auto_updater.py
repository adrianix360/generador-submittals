#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 auto_updater.py  —  Auto-actualizacion HIBRIDA (Generador de Submittals)
================================================================================
 Estrategia:
   - Compara VERSION.json remoto (GitHub) contra los archivos locales usando
     hash SHA-256 -> descarga SOLO lo que cambio.
   - Si cambian archivos .py / .html  -> descarga ligera (KB), reinicio de la app.
   - Si cambia requirements.txt        -> ademas ejecuta pip install.
   - Si cambia el .exe (modo empaquetado) -> avisa y ofrece descargarlo (grande).

 IMPORTANTE (arquitectura):
   - Reemplazar los .py solo TIENE EFECTO si la app corre DESDE PYTHON
     (no empaquetada). En un .exe de PyInstaller el codigo va embebido, por lo
     que ahi el unico camino real es reemplazar el .exe.
   - Este modulo NO depende de tkinter: expone funciones puras. La GUI decide
     cuando llamarlas y como mostrar el progreso.

 Config: editar REPO_SLUG / BRANCH abajo. Mientras contenga "tu-usuario" se
 considera NO configurado y las verificaciones son no-op (no fallan).
================================================================================
"""

import os
import sys
import json
import time
import shutil
import hashlib
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIGURACION (EDITAR)
# ---------------------------------------------------------------------------
REPO_SLUG = "adrianix360/generador-submittals"   # <-- PONER el repo real
BRANCH = "main"
TIMEOUT = 15
REINTENTOS = 3

# Archivos de CODIGO que se pueden actualizar/reemplazar de forma segura.
ARCHIVOS_CODIGO = {
    "submitals_gui.py", "generate_caratulas.py", "auto_updater.py",
    "requirements.txt", "VERSION.json",
    "template_caratula.html", "template_ministerio_salud.html",
}
# Recursos en subcarpeta (rutas relativas con "/").
ARCHIVOS_CODIGO_REL = {
    "template_caratula.html", "template_ministerio_salud.html",
}
# NUNCA se reemplazan (datos del usuario / config).
NO_TOCAR = {"datos_materiales.json", "submitals_config.json",
            "generate_caratulas.log", "generate_caratulas_report.txt"}

EXE_NOMBRE = "GeneradorSubmittalsES.exe"


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _raw_base():
    return f"https://raw.githubusercontent.com/{REPO_SLUG}/{BRANCH}/"


def version_url():
    return _raw_base() + "VERSION.json"


def configurado():
    return "tu-usuario" not in REPO_SLUG and "/" in REPO_SLUG


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _http_get_json(url, timeout=TIMEOUT):
    import requests
    r = requests.get(url, timeout=timeout, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    return r.json()


def _http_get_bytes(url, timeout=TIMEOUT):
    import requests
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def leer_version_local():
    """Devuelve el dict de VERSION.json local (o {} si no existe)."""
    p = app_dir() / "VERSION.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# VERIFICACION
# ---------------------------------------------------------------------------
def verificar_actualizacion(logf=None):
    """
    Devuelve un dict:
      {
        "disponible": bool,
        "version_local": str, "version_remota": str,
        "changelog": str,
        "archivos": [ {nombre,url,tipo,hash} ... ]  # SOLO los que cambiaron
        "requiere_pip": bool,       # cambio requirements.txt
        "requiere_exe": bool,       # (modo .exe) cambio el ejecutable
        "error": str|None,
      }
    Nunca lanza excepcion: ante error devuelve disponible=False y "error".
    """
    res = {"disponible": False, "version_local": "", "version_remota": "",
           "changelog": "", "archivos": [], "requiere_pip": False,
           "requiere_exe": False, "error": None}
    if not configurado():
        res["error"] = "Auto-actualizacion no configurada (edite REPO_SLUG)."
        return res
    try:
        remoto = _http_get_json(version_url())
    except Exception as e:
        res["error"] = f"No se pudo verificar actualizaciones: {str(e)[:120]}"
        if logf:
            logf(res["error"])
        return res

    local = leer_version_local()
    res["version_local"] = local.get("version", "")
    res["version_remota"] = remoto.get("version", "")
    res["changelog"] = remoto.get("changelog", "")

    frozen = getattr(sys, "frozen", False)
    base = app_dir()
    for nombre, info in (remoto.get("archivos") or {}).items():
        hash_remoto = (info or {}).get("hash", "")
        tipo = (info or {}).get("tipo", "")
        if nombre in NO_TOCAR:
            continue
        # El .exe solo aplica en modo empaquetado
        if tipo == "ejecutable" or nombre.lower().endswith(".exe"):
            if frozen:
                local_exe = base / nombre
                h = sha256_file(local_exe) if local_exe.exists() else ""
                if hash_remoto and h != hash_remoto:
                    res["requiere_exe"] = True
                    res["archivos"].append({"nombre": nombre, **info})
            continue
        # En modo .exe (frozen) los .py embebidos no se pueden actualizar en vivo:
        # se ignoran salvo que tambien exista un .exe nuevo (manejado arriba).
        if frozen:
            continue
        # Modo Python: comparar hash local
        ruta = base / nombre
        h = sha256_file(ruta) if ruta.exists() else ""
        if hash_remoto and h != hash_remoto:
            res["archivos"].append({"nombre": nombre, **info})
            if nombre == "requirements.txt":
                res["requiere_pip"] = True

    res["disponible"] = bool(res["archivos"]) or res["requiere_exe"]
    return res


# ---------------------------------------------------------------------------
# DESCARGA + VALIDACION
# ---------------------------------------------------------------------------
def _descargar_con_retry(url, hash_esperado, logf=None):
    ultimo = None
    for intento in range(1, REINTENTOS + 1):
        try:
            data = _http_get_bytes(url)
            if hash_esperado and sha256_bytes(data) != hash_esperado:
                raise ValueError("hash no coincide (descarga corrupta)")
            return data
        except Exception as e:
            ultimo = e
            if logf:
                logf(f"  intento {intento}/{REINTENTOS} fallo: {str(e)[:80]}")
            time.sleep(1.5 * intento)
    raise RuntimeError(f"no se pudo descargar {url} ({ultimo})")


def aplicar_actualizacion(info, progreso=None, logf=None):
    """
    Descarga y reemplaza atomicamente los archivos de codigo cambiados.
    Hace backup .bak y rollback si algo falla. Si cambio requirements.txt,
    ejecuta pip install.
    Devuelve: (ok: bool, mensaje: str, requiere_reinicio: bool)
    NO reinicia la app (eso lo decide la GUI).
    """
    def _prog(p, txt):
        if progreso:
            progreso(p, txt)
        if logf:
            logf(f"[{p:3d}%] {txt}")

    archivos = [a for a in info.get("archivos", [])
                if (a.get("tipo") != "ejecutable"
                    and not a["nombre"].lower().endswith(".exe"))]
    if not archivos:
        return True, "No hay archivos de codigo para actualizar.", False

    base = app_dir()
    descargados = {}          # nombre -> bytes
    total = len(archivos) + (1 if info.get("requiere_pip") else 0) + 1

    # 1) Descargar TODO a memoria y validar hash (antes de tocar nada)
    for i, a in enumerate(archivos, 1):
        _prog(int(i * 60 / max(len(archivos), 1)), f"Descargando {a['nombre']}…")
        try:
            descargados[a["nombre"]] = _descargar_con_retry(a["url"], a.get("hash", ""), logf)
        except Exception as e:
            return False, f"Descarga fallida ({a['nombre']}): {e}", False

    # 2) Backup + reemplazo atomico
    backups = {}
    try:
        for nombre, data in descargados.items():
            destino = base / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            if destino.exists():
                bak = destino.with_suffix(destino.suffix + ".bak")
                shutil.copy2(destino, bak)
                backups[destino] = bak
            tmp = destino.with_suffix(destino.suffix + ".nuevo")
            tmp.write_bytes(data)
            os.replace(tmp, destino)     # atomico
        _prog(75, "Archivos reemplazados.")
    except Exception as e:
        # rollback
        for destino, bak in backups.items():
            try:
                shutil.copy2(bak, destino)
            except Exception:
                pass
        return False, f"Error al reemplazar archivos (rollback aplicado): {e}", False

    # 3) pip install si cambio requirements.txt
    if info.get("requiere_pip"):
        _prog(85, "Instalando dependencias (pip)…")
        try:
            _pip_install_requirements()
        except Exception as e:
            # No hace rollback del codigo: se informa y se sigue.
            _prog(95, "Aviso: pip fallo.")
            return (True,
                    "Actualizacion aplicada, pero faltan dependencias. Ejecute:\n"
                    "pip install -r requirements.txt\nDetalle: " + str(e)[:150],
                    True)

    # 4) limpiar .bak
    for bak in backups.values():
        try:
            bak.unlink()
        except Exception:
            pass
    _prog(100, "Actualizacion completada.")
    return True, "Actualizacion aplicada correctamente.", True


def _pip_install_requirements():
    """pip install -r requirements.txt. NO usa sys.executable si esta frozen
    (evitaria relanzar el .exe). En modo Python usa sys.executable."""
    if getattr(sys, "frozen", False):
        # En .exe no aplica (no se actualizan .py). Se busca un python del sistema.
        py = shutil.which("python") or shutil.which("py")
        if not py:
            raise RuntimeError("No hay Python en el sistema para instalar dependencias.")
        cmd = [py, "-m", "pip", "install", "-r", "requirements.txt"]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    subprocess.check_call(cmd, cwd=str(app_dir()))


# ---------------------------------------------------------------------------
# EXE (modo empaquetado): descarga con swap por .bat
# ---------------------------------------------------------------------------
def descargar_exe_y_preparar_swap(info, progreso=None, logf=None):
    """Descarga el nuevo .exe a un temporal y crea un .bat que, al cerrar la app,
    reemplaza el .exe y lo relanza. Devuelve (ok, mensaje). Solo Windows."""
    exe_info = next((a for a in info.get("archivos", [])
                     if a.get("tipo") == "ejecutable" or a["nombre"].lower().endswith(".exe")), None)
    if not exe_info:
        return False, "No hay .exe nuevo en la actualizacion."
    base = app_dir()
    destino = base / exe_info["nombre"]
    nuevo = base / (exe_info["nombre"] + ".nuevo")
    try:
        data = _descargar_con_retry(exe_info["url"], exe_info.get("hash", ""), logf)
        nuevo.write_bytes(data)
    except Exception as e:
        return False, f"No se pudo descargar el ejecutable: {e}"
    bat = base / "_actualizar_exe.bat"
    bat.write_text(
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'move /y "{nuevo.name}" "{destino.name}" >nul\r\n'
        f'start "" "{destino.name}"\r\n'
        'del "%~f0"\r\n', encoding="utf-8")
    return True, ("El nuevo ejecutable se descargo. Al cerrar la app se instalara "
                  "automaticamente y se reabrira.")


def lanzar_swap_y_salir():
    """Ejecuta el .bat de swap del .exe y cierra la app."""
    bat = app_dir() / "_actualizar_exe.bat"
    if bat.exists():
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(app_dir()),
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    os._exit(0)


# ---------------------------------------------------------------------------
# REINICIO (modo Python)
# ---------------------------------------------------------------------------
def reiniciar_app():
    """Reinicia el proceso una sola vez (no genera bucle)."""
    try:
        if getattr(sys, "frozen", False):
            os.execv(sys.executable, [sys.executable])
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        # Fallback: informar al usuario que reinicie manualmente.
        pass


# ---------------------------------------------------------------------------
# Uso directo (diagnostico)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("REPO_SLUG:", REPO_SLUG, "| configurado:", configurado())
    r = verificar_actualizacion(logf=print)
    print(json.dumps({k: v for k, v in r.items() if k != "archivos"}, ensure_ascii=False, indent=2))
    print("archivos a actualizar:", [a["nombre"] for a in r["archivos"]])
