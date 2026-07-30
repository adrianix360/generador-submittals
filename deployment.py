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
   1. Actualiza el numero de version en submitals_gui_v3.py, submitals_gui.py,
      generate_caratulas.py (constante VERSION = "x.y.z"), submitals_config.json
      y GeneradorSubmittalsES.iss (AppVersion / OutputBaseFilename).
   2. (Opcional) Ejecuta tests rapidos: TESTS_RAPIDOS.py si existe.
   3. Calcula SHA-256 de los archivos versionados.
   4. Genera/actualiza VERSION.json (con hashes + URLs del repo).
   5. (Opcional) Compila GeneradorSubmittalsES_v3.exe con PyInstaller
      (GeneradorSubmittalsES_v3.spec) y luego el INSTALADOR con Inno Setup
      (GeneradorSubmittalsES.iss) -- ese instalador, no el .exe suelto, es lo
      que se comparte con usuarios nuevos: deja accesos directos en el Menu
      Inicio/Escritorio y entrada en "Agregar o quitar programas", sin pedirle
      a nadie que ande buscando un .exe. El .exe suelto SI sigue subiendose al
      Release (sin el, el auto-actualizador no tiene que descargar para el
      swap en caliente de instalaciones existentes).
   6. git add / commit / push.
   7. (Opcional) Crea Release en GitHub con el .exe + el instalador (gh CLI),
      sube cada asset con verificacion de hash post-subida y, al final,
      vuelve a leer el Release ya publicado para confirmar que NINGUN asset
      quedo corrupto o pisado por otro proceso (ej. el workflow de CI de
      GitHub Actions) antes de dar la publicacion por buena.

 Flags:
   --no-tests      salta los tests
   --build         compila el .exe y el instalador (por defecto NO compila)
   --release       crea el Release de GitHub con el .exe (requiere --build)
   --no-git        no hace commit/push
================================================================================
"""

import os
import re
import sys
import json
import shutil
import hashlib
import argparse
import tempfile
import subprocess
from pathlib import Path

# La consola de Windows por defecto usa cp1252, que no puede imprimir los
# emojis (✅❌) de los mensajes de progreso; sin esto el script crashea con
# UnicodeEncodeError justo al final, despues de ya haber hecho todo el trabajo.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ------------------------------------------------------------------ CONFIG --
REPO_SLUG = "adrianix360/generador-submittals"   # <-- igual que en auto_updater.py
BRANCH = "main"
BASE = Path(__file__).resolve().parent

# Archivos que se versionan (entran en VERSION.json). Rutas relativas.
ARCHIVOS_VERSIONADOS = [
    ("submitals_gui_v3.py", "python"),
    ("bd_manager.py", "python"),
    ("git_bd.py", "python"),
    ("fuzzy_search.py", "python"),
    ("nomenclatura.py", "python"),
    ("ocr_extractor.py", "python"),
    ("updater_gh.py", "python"),
    ("generate_caratulas.py", "python"),
    ("auto_updater.py", "python"),
    ("requirements.txt", "requirements"),
    ("template_caratula.html", "html"),
    ("template_ministerio_salud.html", "html"),
]
# Ejecutable principal distribuido (v3). El .exe v2.6 (GeneradorSubmittalsES.exe)
# se compila/publica aparte: es el hermano legado que lanza "Generar desde
# carpetas (v2.6)" y no participa del auto-updater.
EXE_NOMBRE = "GeneradorSubmittalsES_v3.exe"
EXE_SPEC = "GeneradorSubmittalsES_v3.spec"
# Hermano legado: no lo compila este script (lo deja opcionalmente el
# workflow manual de CI o una compilacion aparte), pero SI se verifica si hay
# una copia local en dist/ cuando se audita el Release al final.
EXE_V26_NOMBRE = "GeneradorSubmittalsES.exe"

# Instalador Inno Setup (per-usuario, sin UAC): lo que se comparte para
# instalaciones nuevas. Se compila DESPUES del .exe (su [Files] lo empaqueta).
INSTALLER_ISS = "GeneradorSubmittalsES.iss"
INSTALLER_DIR = "Instalador"


def _instalador_nombre(version):
    return f"GeneradorSubmittalsES_Setup_v{version}.exe"


def _iscc():
    """Ubica ISCC.exe (compilador de Inno Setup); None si no esta instalado."""
    exe = shutil.which("ISCC.exe") or shutil.which("iscc")
    if exe:
        return exe
    candidatos = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
    ]
    for c in candidatos:
        if c.exists():
            return str(c)
    return None


def raw_url(rel):
    return f"https://raw.githubusercontent.com/{REPO_SLUG}/{BRANCH}/{rel}"


def release_url(version, nombre):
    return f"https://github.com/{REPO_SLUG}/releases/download/v{version}/{nombre}"


def sha256_file(path, texto=False):
    """Hash SHA-256 de un archivo local.

    ``texto=True`` normaliza CRLF->LF antes de hashear: git normaliza los
    saltos de linea a LF en el blob remoto (autocrlf), asi que en un checkout
    Windows (CRLF) el archivo en disco no comparte hash con lo que
    ``raw.githubusercontent.com`` sirve si no se normaliza igual aqui. El
    auto-actualizador (``auto_updater.py``) hace la misma normalizacion al
    leer sus archivos locales, para que ambos lados comparen lo mismo.
    """
    with open(path, "rb") as f:
        data = f.read()
    if texto:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _run(cmd, **kw):
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(BASE), **kw)


# --------------------------------------------------- 1. bump de version ----
def bump_version(version):
    cambios = []
    for archivo in ("submitals_gui_v3.py", "submitals_gui.py", "generate_caratulas.py"):
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
    iss = BASE / INSTALLER_ISS
    if iss.exists():
        txt = iss.read_text(encoding="utf-8")
        nuevo = re.sub(r'(AppVersion=)\S+', rf'\g<1>{version}', txt, count=1)
        nuevo = re.sub(r'(OutputBaseFilename=GeneradorSubmittalsES_Setup_v)\S+',
                       rf'\g<1>{version}', nuevo, count=1)
        if nuevo != txt:
            iss.write_text(nuevo, encoding="utf-8")
            cambios.append(INSTALLER_ISS)
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
        archivos[rel] = {"hash": sha256_file(p, texto=True), "url": raw_url(rel), "tipo": tipo}
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
    spec = BASE / EXE_SPEC
    if not spec.exists():
        print(f"   ERROR: no se encontro {EXE_SPEC}")
        return False
    r = _run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec)])
    return r.returncode == 0


def compilar_installer(version):
    """Empaqueta dist/<exe> en un instalador Inno Setup (per-usuario, sin
    UAC). Devuelve la ruta al .exe generado, o None si no se pudo (falta
    Inno Setup, o el .iss no existe) -- nunca detiene la publicacion: el
    Release sigue sirviendo el .exe suelto para el auto-updater."""
    iss = BASE / INSTALLER_ISS
    if not iss.exists():
        print(f"  aviso: no se encontro {INSTALLER_ISS}; se omite el instalador")
        return None
    iscc = _iscc()
    if not iscc:
        print("  aviso: no se encontro ISCC.exe (Inno Setup); se omite el instalador.\n"
              "  Instalelo con: winget install JRSoftware.InnoSetup")
        return None
    r = _run([iscc, str(iss)])
    if r.returncode != 0:
        print("   ERROR: fallo la compilacion del instalador (ISCC).")
        return None
    salida = BASE / INSTALLER_DIR / _instalador_nombre(version)
    if not salida.exists():
        print(f"  aviso: ISCC no genero {salida.name} donde se esperaba.")
        return None
    print(f"  Instalador generado: {salida}")
    return salida


# --------------------------------------------------- 6. git ----------------
def git_push(version, changelog, intentos=5):
    """Commitea y sube a origin/main, reintentando con fetch+rebase si el
    push es rechazado.

    El repositorio recibe pushes de datos (BD_Submittals: fichas/submittals)
    desde varias PCs en tiempo real, ademas de este push de codigo. Un solo
    intento fallaba justo cuando alguien mas subia algo a la vez: el commit
    quedaba local nada mas y ``crear_release()`` igual creaba el Release con
    un tag apuntando al commit VIEJO del remoto (sin el codigo nuevo), no al
    commit real que se acababa de compilar y hashear en VERSION.json.
    """
    _run(["git", "add", "-A"])
    _run(["git", "commit", "-m", f"v{version}: {changelog}"])
    for intento in range(1, intentos + 1):
        r = _run(["git", "push"])
        if r.returncode == 0:
            return True
        print(f"  push rechazado (intento {intento}/{intentos}); "
              f"haciendo fetch + rebase y reintentando…")
        _run(["git", "fetch", "origin"])
        rb = _run(["git", "rebase", "origin/main"])
        if rb.returncode != 0:
            print("  ERROR: rebase con conflictos; se detiene (resolver a mano).")
            return False
    print(f"  ERROR: no se pudo subir el commit tras {intentos} intento(s).")
    return False


# --------------------------------------------------- 7. release ------------
def _subir_asset_verificado(tag, ruta, intentos=2):
    """Sube un asset al Release y lo verifica DESCARGANDOLO de nuevo.

    Subir el .exe y el instalador juntos en un solo ``gh release create``
    corrompio (trunco) el asset mas grande en varias publicaciones (~150 MB).
    Verificar solo el ``digest`` que reporta la API justo despues de subir NO
    alcanza: en una publicacion el digest coincidio en el momento y, al
    volver a descargar el archivo mas tarde, el contenido real ya no
    coincidia (aparente inconsistencia eventual de GitHub con assets
    grandes). La unica verificacion confiable es volver a descargar el
    archivo y comparar su hash con el local.
    """
    hash_local = sha256_file(ruta)
    tag_version = version_tag(tag)
    for intento in range(1, intentos + 1):
        r = _run(["gh", "release", "upload", f"v{tag_version}", str(ruta), "--clobber"])
        if r.returncode != 0:
            print(f"  intento {intento}/{intentos}: 'gh release upload' fallo")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["gh", "release", "download", f"v{tag_version}", "--repo", REPO_SLUG,
                 "--dir", tmp, "--clobber", "--pattern", ruta.name],
                cwd=str(BASE), capture_output=True, text=True)
            descargado = Path(tmp) / ruta.name
            hash_remoto = sha256_file(descargado) if descargado.exists() else ""
        if hash_remoto == hash_local:
            print(f"  {ruta.name}: subido y verificado con descarga real (hash coincide)")
            return True
        print(f"  intento {intento}/{intentos}: {ruta.name} bajo con hash distinto "
              f"al local al volver a descargarlo (subida corrupta); reintentando…")
    print(f"  ERROR: no se pudo subir {ruta.name} con el hash correcto tras "
          f"{intentos} intento(s).")
    return False


def version_tag(version_o_tag):
    """Acepta version ('3.3.4') o tag ('v3.3.4') y devuelve solo 'X.Y.Z'."""
    return version_o_tag[1:] if version_o_tag.startswith("v") else version_o_tag


def verificar_release_completo(version):
    """Ultima comprobacion antes de anunciar el Release como listo: vuelve a
    leer el estado REAL y actual de TODOS los assets ya publicados (``gh
    release view``) y compara su digest contra el hash local de cada archivo
    conocido (exe v3, exe v2.6 hermano si hay copia local, instalador).

    Por que hace falta ADEMAS de ``_subir_asset_verificado`` (que ya
    descarga y compara justo despues de cada subida): esta app tiene un
    workflow de GitHub Actions que tambien puede escribir al mismo Release
    (ver ``.github/workflows/release.yml``). En la publicacion de v3.3.7 el
    CI termino de subir su propio build del .exe v3 DESPUES de que este
    script ya habia subido y verificado el suyo -- la comprobacion
    "inmediatamente despues de subir" habia pasado en su momento, pero el
    asset quedo pisado en silencio minutos mas tarde con un binario de hash
    distinto al que quedo escrito en VERSION.json. Una verificacion que solo
    mira el momento de la subida no detecta eso: hay que revisar el estado
    FINAL en GitHub, como ultimo paso, despues de que ya no deberia haber mas
    escrituras en curso.

    Devuelve ``(ok, problemas)``; ``problemas`` es una lista de strings
    listos para imprimir (archivo, hash esperado vs. publicado)."""
    tag = f"v{version_tag(version)}"
    r = subprocess.run(
        ["gh", "release", "view", tag, "--repo", REPO_SLUG, "--json", "assets"],
        cwd=str(BASE), capture_output=True, text=True)
    if r.returncode != 0:
        return False, [f"no se pudo leer el Release {tag} para verificarlo: "
                        f"{(r.stderr or r.stdout).strip()}"]
    try:
        assets = json.loads(r.stdout).get("assets", [])
    except Exception as e:
        return False, [f"la respuesta de 'gh release view' no es JSON valido: {e}"]

    digest_por_nombre = {}
    for a in assets:
        digest = (a.get("digest") or "").strip()
        digest_por_nombre[a.get("name", "")] = (
            digest.split(":", 1)[1] if ":" in digest else digest)

    candidatos = {
        EXE_NOMBRE: BASE / "dist" / EXE_NOMBRE,
        EXE_V26_NOMBRE: BASE / "dist" / EXE_V26_NOMBRE,
        _instalador_nombre(version): BASE / INSTALLER_DIR / _instalador_nombre(version),
    }

    problemas = []
    revisados = 0
    for nombre, ruta_local in candidatos.items():
        if not ruta_local.exists():
            continue  # sin build local de este archivo, no hay contra que comparar
        digest_remoto = digest_por_nombre.get(nombre)
        if digest_remoto is None:
            problemas.append(f"{nombre}: hay build local pero NO aparece subido en el Release {tag}")
            continue
        if not digest_remoto:
            problemas.append(f"{nombre}: el Release no reporta digest (no se puede verificar)")
            continue
        hash_local = sha256_file(ruta_local)
        revisados += 1
        if hash_local != digest_remoto:
            problemas.append(
                f"{nombre}: el hash publicado ({digest_remoto[:16]}...) NO coincide "
                f"con el build local ({hash_local[:16]}...) -- el asset en GitHub "
                f"quedo corrupto o fue pisado por otro proceso (ej. el workflow de CI)")

    if problemas:
        return False, problemas
    print(f"  Verificacion final: {revisados} asset(s) revisado(s) contra el Release "
          f"publicado, todos coinciden con el build local.")
    return True, []


def crear_release(version):
    """Sube AMBOS artefactos al Release: el .exe suelto (lo descarga el
    auto-updater para el swap en caliente de instalaciones existentes) y el
    instalador (lo que se comparte para instalar de cero -- deja accesos
    directos y entrada de desinstalacion, en vez de un .exe suelto que hay
    que andar buscando).

    Los assets se suben DE A UNO con verificacion de hash (ver
    ``_subir_asset_verificado``): subirlos juntos en la creacion del Release
    corrompio el binario mas grande en mas de una publicacion."""
    exe = BASE / "dist" / EXE_NOMBRE
    instalador = BASE / INSTALLER_DIR / _instalador_nombre(version)
    activos = [p for p in (exe, instalador) if p.exists()]
    if not activos:
        print("  aviso: no hay .exe ni instalador; se omite Release")
        return False
    if shutil.which("gh"):
        # --target <sha exacto>: si se usara el nombre de rama ("main"), un
        # push de otra PC llegando justo entre el commit y este paso haria que
        # el tag apunte al commit de ESE OTRO push, no al codigo recien
        # compilado y hasheado en VERSION.json.
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(BASE),
                             capture_output=True, text=True).stdout.strip()
        r = _run(["gh", "release", "create", f"v{version}", "--target", sha,
                  "--title", f"v{version}", "--notes", f"Release v{version}"])
        if r.returncode != 0:
            return False
        ok = True
        for p in activos:
            ok = _subir_asset_verificado(version, p) and ok
        if ok and instalador.exists():
            print(f"  Instalador para compartir: "
                  f"https://github.com/{REPO_SLUG}/releases/download/v{version}/"
                  f"{instalador.name}")
        if not ok:
            return False
        print("  Verificando integridad final del Release (contra posibles "
              "sobrescrituras posteriores, ej. el workflow de CI)…")
        ok_final, problemas = verificar_release_completo(version)
        if not ok_final:
            print("   ❌ El Release quedo con archivo(s) inconsistentes:")
            for p_ in problemas:
                print(f"      - {p_}")
            return False
        return True
    print("  aviso: no se encontro 'gh' (GitHub CLI). Suba los archivos manualmente a\n"
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
        print("5b) Compilando instalador (Inno Setup)")
        compilar_installer(version)

    subido = True
    if not args.no_git:
        print("6) git commit/push")
        subido = git_push(version, changelog)
        if not subido:
            print("   ❌ No se pudo subir el commit; se omite el Release "
                  "(el tag quedaria apuntando a un commit viejo).")

    if args.release:
        if subido:
            print("7) GitHub Release")
            if not crear_release(version):
                print("\n❌ El Release NO quedo verificado (ver errores arriba). "
                      "No se confirma la publicacion todavia.")
                sys.exit(1)
        else:
            sys.exit(1)

    print(f"\n✅ v{version} publicada. Los usuarios veran la actualizacion al abrir la app.")


if __name__ == "__main__":
    main()
