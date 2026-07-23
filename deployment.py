#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 deployment.py  —  Script de PUBLICACION (solo para el desarrollador)
================================================================================
 Uso:
     python deployment.py 2.5.4 "Fix documentos tecnicos"
   o interactivo:
     python deployment.py

 Hace, en orden (cada paso es tolerante a fallos y se puede saltar con flags):
   1. Actualiza el numero de version en submitals_gui.py y generate_caratulas.py
      (constante VERSION = "x.y.z") y en submitals_config.json.
   2. (Opcional) Ejecuta tests rapidos: TESTS_RAPIDOS.py si existe.
   3. Calcula SHA-256 de los archivos versionados.
   4. Genera/actualiza VERSION.json (con hashes + URLs del repo).
   5. (Opcional) Compila el .exe con PyInstaller (submitals.spec o flags).
   6. git add / commit / push.
   7. (Opcional) Crea Release en GitHub con el .exe (gh CLI o PyGithub).

 Flags:
   --no-tests      salta los tests
   --build         compila el .exe (por defecto NO compila)
   --release       crea el Release de GitHub con el .exe (requiere --build)
   --no-git        no hace commit/push
================================================================================
"""

import os
import re
import sys
import json
import hashlib
import argparse
import subprocess
from pathlib import Path

# ------------------------------------------------------------------ CONFIG --
REPO_SLUG = "adrianix360/generador-submittals"   # <-- igual que en auto_updater.py
BRANCH = "main"
BASE = Path(__file__).resolve().parent

# Archivos que se versionan (entran en VERSION.json). Rutas relativas.
ARCHIVOS_VERSIONADOS = [
    ("submitals_gui.py", "python"),
    ("generate_caratulas.py", "python"),
    ("auto_updater.py", "python"),
    ("requirements.txt", "requirements"),
    ("template_caratula.html", "html"),
    ("template_ministerio_salud.html", "html"),
]
EXE_NOMBRE = "GeneradorSubmittalsES.exe"


def raw_url(rel):
    return f"https://raw.githubusercontent.com/{REPO_SLUG}/{BRANCH}/{rel}"


def release_url(version, nombre):
    return f"https://github.com/{REPO_SLUG}/releases/download/v{version}/{nombre}"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def _run(cmd, **kw):
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(BASE), **kw)


# --------------------------------------------------- 1. bump de version ----
def bump_version(version):
    cambios = []
    for archivo in ("submitals_gui.py", "generate_caratulas.py"):
        p = BASE / archivo
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        nuevo = re.sub(r'(VERSION\s*=\s*")[^"]+(")', rf'\g<1>{version}\g<2>', txt, count=1)
        if nuevo != txt:
            p.write_text(nuevo, encoding="utf-8")
            cambios.append(archivo)
    cfg = BASE / "submitals_config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            data["version"] = version
            cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            cambios.append("submitals_config.json")
        except Exception:
            pass
    print(f"  version -> {version}  (actualizada en: {', '.join(cambios) or 'nada'})")


# --------------------------------------------------- 2. tests --------------
def correr_tests():
    t = BASE / "TESTS_RAPIDOS.py"
    if not t.exists():
        print("  (no hay TESTS_RAPIDOS.py; se omite)")
        return True
    r = _run([sys.executable, str(t)])
    return r.returncode == 0


# --------------------------------------------------- 3-4. VERSION.json -----
def generar_version_json(version, changelog, incluir_exe):
    archivos = {}
    for rel, tipo in ARCHIVOS_VERSIONADOS:
        p = BASE / rel
        if not p.exists():
            print(f"  aviso: falta {rel}, se omite")
            continue
        archivos[rel] = {"hash": sha256_file(p), "url": raw_url(rel), "tipo": tipo}
    if incluir_exe:
        exe = BASE / "dist" / EXE_NOMBRE
        if exe.exists():
            archivos[EXE_NOMBRE] = {
                "hash": sha256_file(exe),
                "url": release_url(version, EXE_NOMBRE),
                "tipo": "ejecutable", "requerido": False,
            }
    data = {
        "version": version,
        "tipo_actualizacion": "ejecutable" if incluir_exe else "codigo",
        "fecha": __import__("datetime").date.today().isoformat(),
        "changelog": changelog,
        "archivos": archivos,
        "instrucciones_auto_actualizar": {
            "si_solo_python": "Descarga los .py/.html cambiados (segundos).",
            "si_requirements_cambio": "Descarga requirements.txt + pip install.",
            "si_cambios_mayores": "Descargar el .exe nuevo (opcional).",
        },
    }
    (BASE / "VERSION.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  VERSION.json generado ({len(archivos)} archivos con hash)")


# --------------------------------------------------- 5. build exe ----------
def compilar_exe():
    spec = BASE / "submitals.spec"
    if spec.exists():
        r = _run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec)])
    else:
        r = _run([sys.executable, "-m", "PyInstaller", "--onefile", "--windowed",
                  "--name", "GeneradorSubmittalsES",
                  "--collect-all", "playwright", "--collect-all", "jinja2",
                  "--collect-all", "pypdf", "--collect-all", "fitz",
                  "--collect-all", "bs4",
                  "--add-data", "template_caratula.html;.",
                  "--add-data", "template_ministerio_salud.html;.",
                  "--add-data", "Tabla visual refresh/assets/logo_es_crop.png;Tabla visual refresh/assets",
                  "--add-data", "Tabla visual refresh/assets/ministerio_salud_banner.png;Tabla visual refresh/assets",
                  "submitals_gui.py"])
    return r.returncode == 0


# --------------------------------------------------- 6. git ----------------
def git_push(version, changelog):
    _run(["git", "add", "-A"])
    _run(["git", "commit", "-m", f"v{version}: {changelog}"])
    r = _run(["git", "push"])
    return r.returncode == 0


# --------------------------------------------------- 7. release ------------
def crear_release(version):
    from shutil import which
    exe = BASE / "dist" / EXE_NOMBRE
    if not exe.exists():
        print("  aviso: no hay dist/.exe; se omite Release")
        return False
    if which("gh"):
        r = _run(["gh", "release", "create", f"v{version}", str(exe),
                  "--title", f"v{version}", "--notes", f"Release v{version}"])
        return r.returncode == 0
    print("  aviso: no se encontro 'gh' (GitHub CLI). Suba el .exe manualmente a\n"
          f"  https://github.com/{REPO_SLUG}/releases/new?tag=v{version}")
    return False


# --------------------------------------------------- MAIN ------------------
def main():
    ap = argparse.ArgumentParser(description="Publicar una version del Generador de Submittals.")
    ap.add_argument("version", nargs="?", help="ej: 2.5.4")
    ap.add_argument("changelog", nargs="?", help="descripcion de cambios")
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--no-git", action="store_true")
    args = ap.parse_args()

    version = args.version or input("Version nueva (ej 2.5.4): ").strip()
    changelog = args.changelog or input("Descripcion de cambios: ").strip()
    if not version:
        print("ERROR: falta la version."); sys.exit(1)

    if "tu-usuario" in REPO_SLUG:
        print("ADVERTENCIA: edite REPO_SLUG en deployment.py y auto_updater.py "
              "con su repo real antes de publicar.\n")

    print(f"\n=== Publicando v{version} ===")
    print("1) Bump de version"); bump_version(version)

    if not args.no_tests:
        print("2) Tests");
        if not correr_tests():
            print("   ❌ Tests fallaron. Se detiene la publicacion."); sys.exit(1)

    print("3-4) VERSION.json"); generar_version_json(version, changelog, incluir_exe=args.build)

    if args.build:
        print("5) Compilando .exe")
        if not compilar_exe():
            print("   ❌ Compilacion fallo."); sys.exit(1)
        # recalcular VERSION.json con hash real del exe
        generar_version_json(version, changelog, incluir_exe=True)

    if not args.no_git:
        print("6) git commit/push")
        git_push(version, changelog)

    if args.release:
        print("7) GitHub Release")
        crear_release(version)

    print(f"\n✅ v{version} publicada. Los usuarios veran la actualizacion al abrir la app.")


if __name__ == "__main__":
    main()
