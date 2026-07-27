#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 git_bd.py  --  Transporte de la Base de Datos sobre GitHub (v3.2.0)
================================================================================
Reemplaza a OneDrive como medio de sincronizacion de la BD de fichas. La BD vive
en el MISMO repositorio del app, en la subcarpeta ``BD_Submittals/``:

    github.com/adrianix360/generador-submittals
        BD_Submittals/
            indice.json
            ARQ/ ESTR/ MEC/ ELEC/     <- PDFs de las fichas
            Proyectos/<Nombre>/submittal_proyecto.json

IMPORTANTE: el app NUNCA trabaja sobre la carpeta de desarrollo del usuario.
Clona el repositorio aparte, en

    %LOCALAPPDATA%/GeneradorSubmittals/bd_repo

con *sparse checkout* limitado a ``BD_Submittals/``. Asi un ``git pull`` de la
BD no puede chocar con cambios de codigo sin confirmar.

--------------------------------------------------------------------------------
DOS BACKENDS (modo hibrido, se elige solo)
--------------------------------------------------------------------------------
  * ``GitTransporte``  : usa el ejecutable ``git`` (subprocess, sin GitPython).
                         Es el camino preferido si ``git`` esta instalado.
  * ``RestTransporte`` : usa la API REST de GitHub (solo biblioteca estandar).
                         Para PCs sin git (por ejemplo el .exe empaquetado).
Ambos exponen la misma interfaz: ``inicializar / pull / push / estado``.

--------------------------------------------------------------------------------
CONFLICTOS: NUNCA SE PIERDEN DATOS
--------------------------------------------------------------------------------
Una estrategia ``-X ours`` a nivel de archivo BORRARIA las fichas cargadas por
la otra PC. Por eso ``indice.json`` se fusiona a nivel de REGISTRO:

  - Union de ``fichas`` por ``id`` (lo que existe en cualquiera de los dos lados
    sobrevive siempre).
  - Si un mismo ``id`` cambio en ambos lados, gana el registro con
    ``fecha_modificacion`` mas reciente.
  - Si dos PCs subieron un PDF distinto con el mismo nombre, se conservan LOS
    DOS: el remoto mantiene el nombre y el local se renombra a ``<nombre>-2.pdf``
    (y su ficha en el indice se reapunta al nombre nuevo).
  - ``submittal_proyecto.json``: gana el de ``ultima_actualizacion`` mas
    reciente (los entregables se regeneran, no se versionan).

Sin dependencias externas: solo biblioteca estandar.
================================================================================
"""

import os
import json
import base64
import shutil
import socket
import hashlib
import logging
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime

VERSION = "3.2.0"

API_BASE = "https://api.github.com"
TIMEOUT_GIT = 240          # seg: clone inicial de la BD puede tardar
TIMEOUT_HTTP = 60
MAX_REINTENTOS_PUSH = 3

MODO_GIT = "git"
MODO_REST = "rest"
MODO_AUTO = "auto"

REPO_DEFECTO = "adrianix360/generador-submittals"
RAMA_DEFECTO = "main"
SUBDIR_DEFECTO = "BD_Submittals"

NOMBRE_INDICE = "indice.json"


# --------------------------------------------------------------------------
# EXCEPCIONES
# --------------------------------------------------------------------------
class SyncError(Exception):
    """Error generico de sincronizacion."""


class SinConexionError(SyncError):
    """No se pudo contactar GitHub (sin internet, DNS, proxy...)."""


class AutenticacionError(SyncError):
    """Falta el token o no tiene permiso de escritura."""


class RepoNoEncontradoError(SyncError):
    """El repositorio o la rama no existen (o el token no los ve)."""


# --------------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------------
def ahora_iso():
    return datetime.now().replace(microsecond=0).isoformat()


def parse_iso(s):
    """ISO -> datetime naive; ``None`` si no se puede interpretar."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", ""))
    except Exception:
        return None


def sha256_bytes(datos, corto=True):
    d = hashlib.sha256(datos).hexdigest()
    return d[:16] if corto else d


def git_disponible():
    """True si el ejecutable ``git`` esta instalado y responde."""
    if not shutil.which("git"):
        return False
    try:
        r = subprocess.run(["git", "--version"], capture_output=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


# Ruta tipica donde Git for Windows queda instalado. winget actualiza el PATH
# del sistema, pero el PROCESO ya arrancado (este) no lo ve hasta una sesion
# nueva; se agrega esta carpeta al PATH en memoria para poder usar git de una
# vez, sin pedirle al usuario que reinicie el programa.
_GIT_CMD_DEFECTO = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "cmd"


def instalar_git_si_falta(logf=None):
    """Instala Git for Windows con winget si el ejecutable no esta disponible.

    Igual que el bootstrap de Tesseract-OCR (v2.6.8): winget instala un binario
    del SISTEMA operativo, no un paquete de este interprete, asi que funciona
    igual empaquetado como .exe (PyInstaller) o corriendo desde codigo fuente.
    Sin git, la BD sigue funcionando por la API REST de GitHub (mas lenta); esto
    solo mejora esa experiencia, nunca es obligatorio para que el programa ande.

    Devuelve ``True`` si al terminar ``git`` esta disponible (ya lo estaba o se
    instalo ahora), ``False`` si no se pudo.
    """
    logf = logf or (lambda *_a, **_k: None)
    if git_disponible():
        return True

    winget = shutil.which("winget")
    if not winget:
        logf("Git no esta instalado y 'winget' no esta disponible en esta PC; "
             "instalelo manualmente desde https://git-scm.com/download/win")
        return False

    logf("Git no encontrado; instalando con winget (puede tardar un momento)...")
    try:
        subprocess.run(
            [winget, "install", "--id", "Git.Git", "-e", "--silent",
             "--accept-package-agreements", "--accept-source-agreements"],
            timeout=300, check=True, capture_output=True)
    except Exception as e:
        logf(f"No se pudo instalar Git automaticamente: {str(e)[:200]}\n"
             "Instalelo manualmente desde https://git-scm.com/download/win")
        return False

    if git_disponible():
        logf("Git instalado correctamente.")
        return True

    # winget ya lo dejo en disco, pero el PATH de este proceso es el de antes
    # de instalar: se agrega la carpeta tipica a mano para esta sesion.
    if (_GIT_CMD_DEFECTO / "git.exe").exists():
        os.environ["PATH"] = str(_GIT_CMD_DEFECTO) + os.pathsep + os.environ.get("PATH", "")
        if git_disponible():
            logf("Git instalado correctamente.")
            return True

    logf("winget termino pero no se encontro git.exe; puede hacer falta "
         "reiniciar el programa (o la PC) para que tome efecto.")
    return False


def _json_tolerante(datos, defecto=None):
    """Interpreta JSON aceptando bytes/str vacios o corruptos."""
    if datos is None:
        return defecto
    if isinstance(datos, bytes):
        try:
            datos = datos.decode("utf-8")
        except Exception:
            return defecto
    datos = datos.strip()
    if not datos:
        return defecto
    try:
        return json.loads(datos)
    except Exception:
        return defecto


def _indice_vacio():
    return {"version": VERSION, "ultima_actualizacion": ahora_iso(), "fichas": []}


# --------------------------------------------------------------------------
# FUSION DEL INDICE A NIVEL DE REGISTRO
# --------------------------------------------------------------------------
def _ts_ficha(f):
    """Marca de tiempo de una ficha para decidir quien gana un conflicto."""
    for clave in ("fecha_modificacion", "ultima_actualizacion", "fecha_carga"):
        dt = parse_iso(f.get(clave))
        if dt:
            return dt
    return datetime.min


def merge_indices(base, nuestro, suyo, renombres=None):
    """Fusiona dos versiones de ``indice.json`` SIN perder fichas.

    ``base`` es el ancestro comun (puede ser ``None``). ``nuestro`` es la version
    local y ``suyo`` la remota. ``renombres`` es la lista devuelta por la
    resolucion de PDFs en conflicto: ``[{"ruta", "hash", "nueva"}]``.

    Devuelve ``(indice_fusionado, resumen)``.
    """
    base = base or {}
    nuestro = nuestro or _indice_vacio()
    suyo = suyo or _indice_vacio()

    f_base = {f.get("id"): f for f in base.get("fichas", []) or [] if f.get("id")}
    f_nuestro = {f.get("id"): f for f in nuestro.get("fichas", []) or [] if f.get("id")}

    resumen = {"remotas_nuevas": 0, "locales_conservadas": 0,
               "conflictos": 0, "gano_local": 0, "gano_remoto": 0}

    salida = []
    vistos = set()

    # 1) Recorrer el lado remoto (mantiene su orden como base estable).
    for f in suyo.get("fichas", []) or []:
        fid = f.get("id")
        if not fid:
            salida.append(f)
            continue
        vistos.add(fid)
        mio = f_nuestro.get(fid)
        if mio is None:
            salida.append(f)
            if fid not in f_base:
                resumen["remotas_nuevas"] += 1
            continue
        if mio == f:
            salida.append(f)
            continue
        # Mismo id modificado en ambos lados -> gana el mas reciente.
        resumen["conflictos"] += 1
        if _ts_ficha(mio) > _ts_ficha(f):
            salida.append(mio)
            resumen["gano_local"] += 1
        else:
            salida.append(f)
            resumen["gano_remoto"] += 1

    # 2) Agregar las fichas que solo existen localmente.
    #    Nota: la BD nunca borra registros (el borrado es logico, estado
    #    'inactivo'), por lo que una ficha ausente en remoto siempre se conserva.
    for f in nuestro.get("fichas", []) or []:
        fid = f.get("id")
        if fid and fid in vistos:
            continue
        salida.append(f)
        resumen["locales_conservadas"] += 1

    fusionado = dict(suyo)
    fusionado.update({
        "version": nuestro.get("version") or suyo.get("version") or VERSION,
        "fichas": salida,
        "ultima_actualizacion": max(
            [x for x in (nuestro.get("ultima_actualizacion"),
                         suyo.get("ultima_actualizacion")) if x] or [ahora_iso()]),
        "ultima_sincronizacion_git": ahora_iso(),
    })
    if renombres:
        aplicar_renombres(fusionado, renombres)
    return fusionado, resumen


def aplicar_renombres(indice, renombres):
    """Reapunta ``ruta_pdf`` de las fichas cuyo PDF hubo que renombrar por
    colision de nombre. Se identifica la ficha por ``hash_archivo``, que es
    unico por contenido."""
    if not renombres:
        return indice
    for r in renombres:
        ruta, h, nueva = r.get("ruta"), r.get("hash"), r.get("nueva")
        for f in indice.get("fichas", []) or []:
            if f.get("ruta_pdf") == ruta and f.get("hash_archivo") == h:
                f["ruta_pdf"] = nueva
                f["fecha_modificacion"] = ahora_iso()
    return indice


def _nombre_libre(carpeta, nombre_archivo, ocupados=()):
    """Devuelve un nombre de archivo libre en ``carpeta`` a partir de
    ``nombre_archivo`` (``ficha.pdf`` -> ``ficha-2.pdf``)."""
    p = Path(nombre_archivo)
    base, ext = p.stem, p.suffix
    n = 1
    candidato = nombre_archivo
    while (Path(carpeta) / candidato).exists() or candidato in ocupados:
        n += 1
        candidato = f"{base}-{n}{ext}"
    return candidato


# ==========================================================================
# BACKEND 1: EJECUTABLE GIT
# ==========================================================================
class GitTransporte:
    """Sincroniza ``BD_Submittals/`` usando el ejecutable ``git``.

    No usa GitPython a proposito: una dependencia menos para empaquetar el .exe
    y el mismo comportamiento (GitPython tambien invoca el binario de git).
    """

    backend = MODO_GIT

    def __init__(self, repo_dir, repo_slug=REPO_DEFECTO, rama=RAMA_DEFECTO,
                 subdir=SUBDIR_DEFECTO, token="", usuario="", email="", logger=None,
                 url=""):
        self.repo_dir = Path(repo_dir)
        self.repo_slug = repo_slug
        # ``url`` permite apuntar a otro remoto (por ejemplo un repositorio local
        # en las pruebas, que no necesita red ni token).
        self.url = str(url or "")
        self.rama = rama or RAMA_DEFECTO
        self.subdir = subdir or SUBDIR_DEFECTO
        self.token = (token or "").strip()
        self.usuario = usuario or socket.gethostname()
        self.email = email or f"{socket.gethostname()}@generador-submittals.local"
        self.log = logger or logging.getLogger("git_bd")

    # ------------------------------------------------------------ rutas
    @property
    def bd_root(self):
        return self.repo_dir / self.subdir

    @property
    def indice_rel(self):
        return f"{self.subdir}/{NOMBRE_INDICE}"

    @property
    def url_publica(self):
        return self.url or f"https://github.com/{self.repo_slug}.git"

    def _url_auth(self):
        """URL con token, usada SOLO en la linea de comandos de fetch/push.
        Nunca se guarda en ``.git/config`` para no dejar el token en disco."""
        if self.url:
            return self.url            # remoto explicito (local en pruebas)
        if self.token:
            return f"https://x-access-token:{self.token}@github.com/{self.repo_slug}.git"
        return self.url_publica

    def _requiere_token(self):
        """Solo GitHub por HTTPS necesita token; un remoto local no."""
        return not self.url

    def _ocultar(self, texto):
        """Quita el token de cualquier texto antes de registrarlo."""
        t = str(texto or "")
        if self.token:
            t = t.replace(self.token, "***")
        return t

    # ------------------------------------------------------- ejecucion
    def _git(self, args, cwd=None, binario=False, check=True, timeout=TIMEOUT_GIT,
             identidad=False):
        """Ejecuta git de forma NO interactiva (sin pedir credenciales)."""
        base = ["git", "-c", "credential.helper=", "-c", "core.autocrlf=false"]
        if identidad:
            base += ["-c", f"user.name={self.usuario}", "-c", f"user.email={self.email}"]
        cmd = base + list(args)
        env = dict(os.environ)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "never"
        env["LC_ALL"] = "C"
        try:
            r = subprocess.run(cmd, cwd=str(cwd or self.repo_dir), env=env,
                               capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise SinConexionError("git no respondio (timeout). Revise la conexion.")
        except FileNotFoundError:
            raise SyncError("git no esta instalado en esta PC.")
        if not binario:
            r.stdout = r.stdout.decode("utf-8", "replace")
            r.stderr = r.stderr.decode("utf-8", "replace")
        if check and r.returncode != 0:
            salida = r.stderr if isinstance(r.stderr, str) else ""
            self._clasificar_error(salida)
            raise SyncError(self._ocultar(f"git {' '.join(args[:2])} fallo: {salida.strip()}"))
        return r

    def _clasificar_error(self, texto):
        """Distingue sin-conexion de credenciales/permiso invalidos.

        OJO: el mensaje clasico de git cuando el token NO tiene permiso de
        escritura es ``fatal: unable to access '...': The requested URL
        returned error: 403`` -- que contiene la frase "unable to access"
        usada para detectar problemas de RED. Por eso las credenciales/permiso
        se revisan ANTES que la heuristica de red: si no, un push rechazado
        por falta de permiso siempre se reportaba (incorrectamente) como "sin
        conexion", y el usuario nunca veia el aviso real para renovar el token.
        """
        t = (texto or "").lower()
        if ("authentication failed" in t or "could not read username" in t
                or "invalid username or token" in t or "permission denied" in t
                or "permission to" in t
                or (("403" in t or "401" in t) and "github" in t)):
            raise AutenticacionError(
                "GitHub rechazo las credenciales. Configure un token con permiso "
                "de escritura sobre el repositorio.")
        if ("repository not found" in t
                or "does not appear to be a git repository" in t
                or "could not read from remote repository" in t
                or ("not found" in t and "remote" in t)):
            raise RepoNoEncontradoError(
                f"No se pudo acceder al repositorio {self.repo_slug}. Revise el "
                f"nombre del repositorio, la rama '{self.rama}' y los permisos "
                f"del token.")
        if ("could not resolve host" in t or "unable to access" in t
                or "failed to connect" in t or "timed out" in t
                or "network is unreachable" in t or "proxy" in t):
            raise SinConexionError("Sin conexion a GitHub.")

    # ------------------------------------------------------ inicializacion
    def preparado(self):
        return (self.repo_dir / ".git").is_dir()

    def inicializar(self):
        """Clona el repo (sparse, solo ``BD_Submittals/``) si hace falta."""
        if self.preparado():
            self.bd_root.mkdir(parents=True, exist_ok=True)
            return False
        self.repo_dir.parent.mkdir(parents=True, exist_ok=True)
        if self.repo_dir.exists() and any(self.repo_dir.iterdir()):
            # Carpeta a medio crear de un intento anterior: empezar limpio.
            shutil.rmtree(self.repo_dir, ignore_errors=True)

        padre = self.repo_dir.parent
        destino = str(self.repo_dir)
        intentos = [
            ["clone", "--no-tags", "--single-branch", "--branch", self.rama,
             "--filter=blob:none", "--sparse", self._url_auth(), destino],
            ["clone", "--no-tags", "--single-branch", "--branch", self.rama,
             self._url_auth(), destino],
        ]
        ultimo = None
        for args in intentos:
            r = self._git(args, cwd=padre, check=False, timeout=TIMEOUT_GIT)
            if r.returncode == 0:
                break
            ultimo = r.stderr
            shutil.rmtree(self.repo_dir, ignore_errors=True)
        else:
            # Ningun clone funciono: puede ser repo vacio o sin la rama.
            self._clasificar_error(ultimo or "")
            self._init_local()
            return True

        # Limitar el checkout a la subcarpeta de la BD (si git lo soporta).
        r = self._git(["sparse-checkout", "set", self.subdir], check=False)
        if r.returncode != 0:
            self.log.info("sparse-checkout no disponible; se usa checkout completo")
        # Dejar el remoto SIN token en disco.
        self._git(["remote", "set-url", "origin", self.url_publica], check=False)
        self.bd_root.mkdir(parents=True, exist_ok=True)
        self.log.info("BD clonada en %s", self.repo_dir)
        return True

    def _init_local(self):
        """Crea un repo local vacio apuntando al remoto (repo remoto sin commits
        o sin la rama pedida)."""
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        r = self._git(["init", "-b", self.rama], check=False)
        if r.returncode != 0:
            self._git(["init"], check=False)
            self._git(["checkout", "-b", self.rama], check=False)
        self._git(["remote", "add", "origin", self.url_publica], check=False)
        self.bd_root.mkdir(parents=True, exist_ok=True)
        self.log.warning("Repo local inicializado sin clonar (remoto vacio o sin rama %s)",
                         self.rama)

    # ------------------------------------------------------------ estado
    def _tiene_commits(self):
        return self._git(["rev-parse", "--verify", "HEAD"], check=False).returncode == 0

    def _tiene_remoto(self):
        return self._git(["rev-parse", "--verify", f"refs/remotes/origin/{self.rama}"],
                         check=False).returncode == 0

    def _sucio(self):
        r = self._git(["status", "--porcelain", "--", self.subdir], check=False)
        return bool((r.stdout or "").strip())

    def _adelante_atras(self):
        if not (self._tiene_commits() and self._tiene_remoto()):
            return (0, 0)
        r = self._git(["rev-list", "--left-right", "--count",
                       f"HEAD...refs/remotes/origin/{self.rama}"], check=False)
        try:
            a, b = (r.stdout or "0\t0").split()
            return (int(a), int(b))
        except Exception:
            return (0, 0)

    def _fecha_ultimo_commit(self):
        r = self._git(["log", "-1", "--format=%cI"], check=False)
        return (r.stdout or "").strip()

    def estado(self):
        """Resumen para la interfaz."""
        autenticado = bool(self.token) or not self._requiere_token()
        if not self.preparado():
            return {"backend": self.backend, "listo": False, "rama": self.rama,
                    "pendientes": 0, "adelante": 0, "atras": 0, "ultimo_commit": "",
                    "autenticado": autenticado}
        adelante, atras = self._adelante_atras()
        return {"backend": self.backend, "listo": True, "rama": self.rama,
                "pendientes": 1 if self._sucio() else 0,
                "adelante": adelante, "atras": atras,
                "ultimo_commit": self._fecha_ultimo_commit(),
                "autenticado": autenticado}

    # -------------------------------------------------------------- commit
    def _commit_local(self, mensaje):
        """Confirma lo que haya pendiente en ``BD_Submittals/``.
        Devuelve True si se creo un commit."""
        self._git(["add", "-A", "--", self.subdir], check=False)
        r = self._git(["diff", "--cached", "--quiet", "--", self.subdir], check=False)
        if r.returncode == 0:
            return False   # nada staged
        self._git(["commit", "-m", mensaje], identidad=True)
        return True

    # ---------------------------------------------------------------- pull
    def fetch(self):
        r = self._git(["fetch", "--no-tags", self._url_auth(),
                       f"+refs/heads/{self.rama}:refs/remotes/origin/{self.rama}"],
                      check=False)
        if r.returncode != 0:
            self._clasificar_error(r.stderr)
            raise SyncError(self._ocultar(f"fetch fallo: {(r.stderr or '').strip()}"))
        return True

    def pull(self, mensaje_local="BD: cambios locales pendientes"):
        """Sincroniza desde GitHub. Devuelve un resumen dict.

        Antes de fusionar confirma los cambios locales, para que un merge nunca
        pise trabajo sin guardar.
        """
        resumen = {"backend": self.backend, "clonado": False, "commit_local": False,
                   "recibidos": 0, "conflictos": 0, "detalle_merge": {}, "offline": False}
        resumen["clonado"] = self.inicializar()
        resumen["commit_local"] = self._commit_local(mensaje_local)

        self.fetch()
        if not self._tiene_remoto():
            return resumen               # remoto sin la rama todavia
        if not self._tiene_commits():
            self._git(["reset", "--hard", f"refs/remotes/origin/{self.rama}"])
            self.bd_root.mkdir(parents=True, exist_ok=True)
            resumen["recibidos"] = 1
            return resumen

        _adelante, atras = self._adelante_atras()
        if atras == 0:
            return resumen
        resumen["recibidos"] = atras

        r = self._git(["merge", "--no-edit", f"refs/remotes/origin/{self.rama}"],
                      check=False, identidad=True)
        if r.returncode != 0:
            conflictos = self.resolver_conflictos()
            resumen["conflictos"] = conflictos["archivos"]
            resumen["detalle_merge"] = conflictos
        return resumen

    # ---------------------------------------------------- conflictos
    def _stage(self, n, ruta):
        """Contenido de una etapa del merge (1=base, 2=nuestro, 3=suyo)."""
        r = self._git(["show", f":{n}:{ruta}"], binario=True, check=False)
        return r.stdout if r.returncode == 0 else None

    def resolver_conflictos(self):
        """Resuelve TODOS los conflictos del merge en curso sin perder datos y
        confirma el resultado. Devuelve un resumen dict."""
        r = self._git(["diff", "--name-only", "--diff-filter=U"], check=False)
        archivos = [a.strip() for a in (r.stdout or "").splitlines() if a.strip()]
        info = {"archivos": len(archivos), "renombres": [], "indice": {},
                "proyectos": 0, "otros": 0, "lista": archivos}
        if not archivos:
            return info

        renombres = []
        # El indice se resuelve al final: necesita saber los renombres de PDFs.
        otros = [a for a in archivos if a != self.indice_rel]
        for a in otros:
            bajo = a.lower()
            if bajo.endswith(".pdf"):
                renombres += self._resolver_binario(a)
            elif bajo.endswith(".json"):
                self._resolver_json_proyecto(a)
                info["proyectos"] += 1
            else:
                self._preferir_nuestro(a)
                info["otros"] += 1

        info["renombres"] = renombres
        if self.indice_rel in archivos:
            info["indice"] = self._resolver_indice(self.indice_rel, renombres)

        # Confirmar el merge resuelto.
        self._git(["add", "-A", "--", self.subdir], check=False)
        c = self._git(["commit", "--no-edit"], check=False, identidad=True)
        if c.returncode != 0:
            self._git(["commit", "-m", "BD: conflicto resuelto automaticamente"],
                      check=False, identidad=True)
        self.log.warning("Conflicto resuelto automaticamente: %s", info)
        return info

    def _escribir(self, rel, datos):
        p = self.repo_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(datos)
        self._git(["add", "--", rel], check=False)

    def _resolver_binario(self, rel):
        """PDF en conflicto: se conservan las dos versiones (la remota mantiene
        el nombre; la local pasa a ``<nombre>-N.pdf``)."""
        nuestro = self._stage(2, rel)
        suyo = self._stage(3, rel)
        if nuestro is None or suyo is None:
            # add/delete: conservar la version que exista.
            self._escribir(rel, nuestro if nuestro is not None else suyo)
            return []
        if sha256_bytes(nuestro) == sha256_bytes(suyo):
            self._escribir(rel, suyo)
            return []
        p = Path(rel)
        carpeta = (self.repo_dir / p.parent)
        self._escribir(rel, suyo)
        nuevo_nombre = _nombre_libre(carpeta, p.name)
        nuevo_rel = f"{p.parent.as_posix()}/{nuevo_nombre}"
        self._escribir(nuevo_rel, nuestro)
        self.log.warning("PDF duplicado '%s': la copia local se guardo como '%s'",
                         rel, nuevo_rel)
        return [{"ruta": self._ruta_ficha(rel), "hash": sha256_bytes(nuestro),
                 "nueva": self._ruta_ficha(nuevo_rel)}]

    def _ruta_ficha(self, rel):
        """``BD_Submittals/ESTR/x.pdf`` -> ``ESTR/x.pdf`` (formato de ruta_pdf)."""
        pref = f"{self.subdir}/"
        return rel[len(pref):] if rel.startswith(pref) else rel

    def _resolver_json_proyecto(self, rel):
        """``submittal_proyecto.json``: gana la version mas reciente."""
        nuestro = _json_tolerante(self._stage(2, rel))
        suyo = _json_tolerante(self._stage(3, rel))
        if nuestro is None:
            self._escribir(rel, json.dumps(suyo or {}, ensure_ascii=False, indent=2).encode("utf-8"))
            return
        if suyo is None:
            self._escribir(rel, json.dumps(nuestro, ensure_ascii=False, indent=2).encode("utf-8"))
            return
        t_n = parse_iso(nuestro.get("ultima_actualizacion")) or datetime.min
        t_s = parse_iso(suyo.get("ultima_actualizacion")) or datetime.min
        gana = nuestro if t_n >= t_s else suyo
        self._escribir(rel, json.dumps(gana, ensure_ascii=False, indent=2).encode("utf-8"))

    def _preferir_nuestro(self, rel):
        nuestro = self._stage(2, rel)
        suyo = self._stage(3, rel)
        self._escribir(rel, nuestro if nuestro is not None else (suyo or b""))

    def _resolver_indice(self, rel, renombres):
        base = _json_tolerante(self._stage(1, rel))
        nuestro = _json_tolerante(self._stage(2, rel), _indice_vacio())
        suyo = _json_tolerante(self._stage(3, rel), _indice_vacio())
        fusionado, resumen = merge_indices(base, nuestro, suyo, renombres)
        self._escribir(rel, json.dumps(fusionado, ensure_ascii=False, indent=2).encode("utf-8"))
        return resumen

    # ---------------------------------------------------------------- push
    def push(self, mensaje="BD: actualizar", archivos=None):
        """Confirma y sube. Ante rechazo por no-fast-forward hace pull (con
        resolucion automatica) y reintenta."""
        resumen = {"backend": self.backend, "commit": False, "subido": False,
                   "reintentos": 0, "conflictos": 0, "nada_que_subir": False}
        self.inicializar()
        resumen["commit"] = self._commit_local(mensaje)

        if not self._tiene_commits():
            resumen["nada_que_subir"] = True
            return resumen

        if not self.token and self._requiere_token():
            raise AutenticacionError(
                "Falta el token de GitHub: sin el no se pueden subir cambios.")

        for intento in range(1, MAX_REINTENTOS_PUSH + 1):
            r = self._git(["push", self._url_auth(),
                           f"HEAD:refs/heads/{self.rama}"], check=False)
            if r.returncode == 0:
                resumen["subido"] = True
                resumen["reintentos"] = intento - 1
                return resumen
            texto = (r.stderr or "").lower()
            rechazo = ("non-fast-forward" in texto or "fetch first" in texto
                       or "rejected" in texto or "stale info" in texto)
            if not rechazo or intento == MAX_REINTENTOS_PUSH:
                self._clasificar_error(r.stderr)
                raise SyncError(self._ocultar(f"push fallo: {(r.stderr or '').strip()}"))
            self.log.info("push rechazado (intento %d): sincronizando y reintentando", intento)
            p = self.pull(mensaje_local=mensaje)
            resumen["conflictos"] += p.get("conflictos", 0)
        return resumen


# ==========================================================================
# BACKEND 2: API REST DE GITHUB  (para PCs sin git)
# ==========================================================================
class RestTransporte:
    """Sincroniza ``BD_Submittals/`` con la API REST de GitHub.

    No necesita git instalado ni dependencias externas (usa ``urllib``). El
    control de concurrencia es optimista: los commits se crean con la Data API
    y, si el ``ref`` se movio mientras trabajabamos, se vuelve a fusionar el
    indice a nivel de registro y se reintenta.
    """

    backend = MODO_REST

    def __init__(self, base_dir, repo_slug=REPO_DEFECTO, rama=RAMA_DEFECTO,
                 subdir=SUBDIR_DEFECTO, token="", usuario="", email="",
                 estado_path=None, logger=None):
        self.base_dir = Path(base_dir)              # espejo local del repo
        self.repo_slug = repo_slug
        self.rama = rama or RAMA_DEFECTO
        self.subdir = subdir or SUBDIR_DEFECTO
        self.token = (token or "").strip()
        self.usuario = usuario or socket.gethostname()
        self.email = email or f"{socket.gethostname()}@generador-submittals.local"
        self.log = logger or logging.getLogger("git_bd")
        self.estado_path = Path(estado_path) if estado_path else (
            self.base_dir.parent / "rest_state.json")
        self._estado = self._cargar_estado()

    # ------------------------------------------------------------ rutas
    @property
    def bd_root(self):
        return self.base_dir / self.subdir

    @property
    def indice_rel(self):
        return f"{self.subdir}/{NOMBRE_INDICE}"

    def _cargar_estado(self):
        d = _json_tolerante(
            self.estado_path.read_bytes() if self.estado_path.exists() else None, {})
        d.setdefault("blobs", {})       # ruta -> sha del blob remoto
        d.setdefault("commit", "")      # ultimo commit visto
        return d

    def _guardar_estado(self):
        try:
            self.estado_path.parent.mkdir(parents=True, exist_ok=True)
            self.estado_path.write_text(
                json.dumps(self._estado, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    @property
    def _base_indice(self):
        """Copia del indice remoto tal como se vio en el ultimo pull: sirve de
        ancestro comun para fusionar."""
        return self.estado_path.parent / "indice_base.json"

    # -------------------------------------------------------------- HTTP
    def _req(self, metodo, ruta, cuerpo=None, raw=False):
        url = ruta if ruta.startswith("http") else f"{API_BASE}{ruta}"
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        cab = {"Accept": "application/vnd.github.raw" if raw
                         else "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": f"GeneradorSubmittals/{VERSION}"}
        if datos is not None:
            cab["Content-Type"] = "application/json"
        if self.token:
            cab["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=datos, headers=cab, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_HTTP) as resp:
                bruto = resp.read()
                if raw:
                    return bruto, resp.status
                return (_json_tolerante(bruto, {}) if bruto else {}), resp.status
        except urllib.error.HTTPError as e:
            cuerpo_err = ""
            try:
                cuerpo_err = e.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
            if e.code in (401, 403):
                raise AutenticacionError(
                    f"GitHub rechazo la peticion ({e.code}). Revise el token y sus "
                    f"permisos. {cuerpo_err}")
            if e.code == 404:
                raise RepoNoEncontradoError(
                    f"No encontrado en GitHub: {ruta} ({self.repo_slug}/{self.rama})")
            if e.code in (409, 422):
                return {"_conflicto": True, "_detalle": cuerpo_err}, e.code
            raise SyncError(f"GitHub respondio {e.code}: {cuerpo_err}")
        except urllib.error.URLError as e:
            raise SinConexionError(f"Sin conexion a GitHub: {e.reason}")
        except TimeoutError:
            raise SinConexionError("GitHub no respondio (timeout).")

    # -------------------------------------------------------- lectura
    def inicializar(self):
        creado = not self.bd_root.exists()
        self.bd_root.mkdir(parents=True, exist_ok=True)
        return creado

    def _ref_remoto(self):
        d, _ = self._req("GET", f"/repos/{self.repo_slug}/git/ref/heads/{self.rama}")
        return (d.get("object") or {}).get("sha", "")

    def _arbol_remoto(self, commit_sha):
        d, _ = self._req("GET", f"/repos/{self.repo_slug}/git/commits/{commit_sha}")
        tree = (d.get("tree") or {}).get("sha", "")
        if not tree:
            return {}, ""
        t, _ = self._req("GET", f"/repos/{self.repo_slug}/git/trees/{tree}?recursive=1")
        salida = {}
        for e in t.get("tree", []) or []:
            if e.get("type") == "blob" and str(e.get("path", "")).startswith(self.subdir + "/"):
                salida[e["path"]] = e.get("sha", "")
        return salida, tree

    def _descargar_blob(self, sha):
        bruto, _ = self._req("GET", f"/repos/{self.repo_slug}/git/blobs/{sha}", raw=True)
        if isinstance(bruto, bytes) and bruto[:1] == b"{":
            d = _json_tolerante(bruto, {})
            if d.get("encoding") == "base64":
                return base64.b64decode(d.get("content", ""))
        return bruto

    def asegurar_archivo(self, rel):
        """Descarga bajo demanda un archivo de la BD (por ejemplo el PDF de una
        ficha) si no esta en el espejo local."""
        destino = self.base_dir / rel
        if destino.exists():
            return destino
        sha = self._estado["blobs"].get(rel)
        if not sha:
            raise SyncError(f"'{rel}' no existe en la BD remota.")
        datos = self._descargar_blob(sha)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
        return destino

    def pull(self, mensaje_local=None):
        """Descarga ``indice.json`` y los metadatos de proyectos; los PDFs se
        traen bajo demanda (``asegurar_archivo``)."""
        resumen = {"backend": self.backend, "clonado": self.inicializar(),
                   "commit_local": False, "recibidos": 0, "conflictos": 0,
                   "detalle_merge": {}, "offline": False}
        commit = self._ref_remoto()
        blobs, _tree = self._arbol_remoto(commit)

        previos = self._estado.get("blobs", {})
        cambiados = [r for r, s in blobs.items()
                     if previos.get(r) != s or not (self.base_dir / r).exists()]
        # Traer siempre los JSON (livianos); los PDF quedan diferidos.
        for rel in cambiados:
            if not rel.lower().endswith(".json"):
                continue
            datos = self._descargar_blob(blobs[rel])
            destino = self.base_dir / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            if rel == self.indice_rel:
                remoto = _json_tolerante(datos, _indice_vacio())
                local = _json_tolerante(
                    destino.read_bytes() if destino.exists() else None)
                base = _json_tolerante(
                    self._base_indice.read_bytes() if self._base_indice.exists() else None)
                if local and local != remoto:
                    fusionado, det = merge_indices(base, local, remoto)
                    resumen["detalle_merge"] = det
                    resumen["conflictos"] = det.get("conflictos", 0)
                    destino.write_text(json.dumps(fusionado, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
                else:
                    destino.write_bytes(datos)
                # Guardar el ancestro comun para el proximo merge.
                self._base_indice.parent.mkdir(parents=True, exist_ok=True)
                self._base_indice.write_bytes(datos)
            else:
                destino.write_bytes(datos)
            resumen["recibidos"] += 1

        self._estado["blobs"] = blobs
        self._estado["commit"] = commit
        self._guardar_estado()
        return resumen

    # -------------------------------------------------------- escritura
    def _archivos_locales(self):
        """Todos los archivos versionables del espejo local (rutas relativas)."""
        salida = {}
        for root, _dirs, files in os.walk(self.bd_root):
            for nombre in files:
                if nombre.startswith(".") or nombre.endswith(".tmp"):
                    continue
                p = Path(root) / nombre
                rel = p.relative_to(self.base_dir).as_posix()
                salida[rel] = p
        return salida

    def push(self, mensaje="BD: actualizar", archivos=None):
        """Sube los cambios locales en un solo commit (blobs -> tree -> commit
        -> ref). Reintenta fusionando si el ref se movio."""
        resumen = {"backend": self.backend, "commit": False, "subido": False,
                   "reintentos": 0, "conflictos": 0, "nada_que_subir": False}
        self.inicializar()
        if not self.token:
            raise AutenticacionError(
                "Falta el token de GitHub: sin el no se pueden subir cambios.")

        for intento in range(1, MAX_REINTENTOS_PUSH + 1):
            commit_base = self._ref_remoto()
            blobs_remotos, tree_base = self._arbol_remoto(commit_base)
            locales = self._archivos_locales()

            # Renombrar PDFs locales que choquen con uno remoto distinto.
            renombres = []
            for rel, p in list(locales.items()):
                if not rel.lower().endswith(".pdf"):
                    continue
                sha_remoto = blobs_remotos.get(rel)
                if not sha_remoto or self._estado["blobs"].get(rel) == sha_remoto:
                    continue
                remoto = self._descargar_blob(sha_remoto)
                mio = p.read_bytes()
                if sha256_bytes(remoto) == sha256_bytes(mio):
                    continue
                nuevo = _nombre_libre(p.parent, p.name, ocupados=set(locales))
                nueva_p = p.parent / nuevo
                p.rename(nueva_p)
                nuevo_rel = nueva_p.relative_to(self.base_dir).as_posix()
                (self.base_dir / rel).write_bytes(remoto)
                locales[nuevo_rel] = nueva_p
                renombres.append({"ruta": self._ruta_ficha(rel),
                                  "hash": sha256_bytes(mio),
                                  "nueva": self._ruta_ficha(nuevo_rel)})

            # Fusionar el indice contra el remoto actual.
            idx_local_p = self.base_dir / self.indice_rel
            if self.indice_rel in blobs_remotos:
                remoto_idx = _json_tolerante(
                    self._descargar_blob(blobs_remotos[self.indice_rel]), _indice_vacio())
            else:
                remoto_idx = _indice_vacio()
            local_idx = _json_tolerante(
                idx_local_p.read_bytes() if idx_local_p.exists() else None, _indice_vacio())
            base_idx = _json_tolerante(
                self._base_indice.read_bytes() if self._base_indice.exists() else None)
            fusionado, det = merge_indices(base_idx, local_idx, remoto_idx, renombres)
            resumen["conflictos"] += det.get("conflictos", 0)
            idx_local_p.parent.mkdir(parents=True, exist_ok=True)
            idx_local_p.write_text(json.dumps(fusionado, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
            locales[self.indice_rel] = idx_local_p

            # Solo subir lo que realmente cambio.
            entradas = []
            for rel, p in sorted(locales.items()):
                datos = p.read_bytes()
                sha_blob, _ = self._req(
                    "POST", f"/repos/{self.repo_slug}/git/blobs",
                    {"content": base64.b64encode(datos).decode("ascii"),
                     "encoding": "base64"})
                sha_nuevo = sha_blob.get("sha")
                if not sha_nuevo:
                    raise SyncError(f"GitHub no devolvio sha para '{rel}'")
                if blobs_remotos.get(rel) == sha_nuevo:
                    continue
                entradas.append({"path": rel, "mode": "100644", "type": "blob",
                                 "sha": sha_nuevo})
            if not entradas:
                resumen["nada_que_subir"] = True
                self._estado["blobs"] = blobs_remotos
                self._estado["commit"] = commit_base
                self._guardar_estado()
                return resumen

            cuerpo_tree = {"tree": entradas}
            if tree_base:
                cuerpo_tree["base_tree"] = tree_base
            t, _ = self._req("POST", f"/repos/{self.repo_slug}/git/trees", cuerpo_tree)
            nuevo_tree = t.get("sha")
            if not nuevo_tree:
                raise SyncError("GitHub no devolvio el arbol nuevo")

            cuerpo_commit = {
                "message": mensaje, "tree": nuevo_tree,
                "author": {"name": self.usuario, "email": self.email,
                           "date": datetime.now().astimezone().isoformat()},
            }
            if commit_base:
                cuerpo_commit["parents"] = [commit_base]
            c, _ = self._req("POST", f"/repos/{self.repo_slug}/git/commits", cuerpo_commit)
            nuevo_commit = c.get("sha")
            if not nuevo_commit:
                raise SyncError("GitHub no devolvio el commit nuevo")

            r, code = self._req("PATCH",
                                f"/repos/{self.repo_slug}/git/refs/heads/{self.rama}",
                                {"sha": nuevo_commit, "force": False})
            if not r.get("_conflicto"):
                resumen["subido"] = True
                resumen["commit"] = True
                resumen["reintentos"] = intento - 1
                blobs, _ = self._arbol_remoto(nuevo_commit)
                self._estado["blobs"] = blobs
                self._estado["commit"] = nuevo_commit
                self._guardar_estado()
                if idx_local_p.exists():
                    self._base_indice.write_bytes(idx_local_p.read_bytes())
                return resumen
            self.log.info("ref movido (intento %d/%d): refusionando y reintentando",
                          intento, MAX_REINTENTOS_PUSH)
        raise SyncError("No se pudo subir a GitHub tras varios reintentos "
                        "(otra PC esta subiendo cambios al mismo tiempo).")

    def _ruta_ficha(self, rel):
        pref = f"{self.subdir}/"
        return rel[len(pref):] if rel.startswith(pref) else rel

    def estado(self):
        idx = self.base_dir / self.indice_rel
        return {"backend": self.backend, "listo": self.bd_root.exists(),
                "rama": self.rama, "pendientes": 0, "adelante": 0, "atras": 0,
                "ultimo_commit": self._estado.get("commit", ""),
                "autenticado": bool(self.token),
                "indice_local": idx.exists()}


# ==========================================================================
# FACHADA: elige backend, recuerda estado, degrada a modo offline
# ==========================================================================
class GitSync:
    """Punto unico de sincronizacion que usa ``bd_manager``.

    Elige el backend segun ``modo`` (``auto`` -> git si esta instalado, si no
    REST) y absorbe los errores de red para permitir el modo offline: si no hay
    conexion, la app sigue trabajando contra la copia local y sincroniza al
    reconectar.
    """

    def __init__(self, base_dir, repo_slug=REPO_DEFECTO, rama=RAMA_DEFECTO,
                 subdir=SUBDIR_DEFECTO, token="", usuario="", email="",
                 modo=MODO_AUTO, cache_dir=None, logger=None, url=""):
        self.base_dir = Path(base_dir)
        self.log = logger or logging.getLogger("git_bd")
        self.modo_pedido = modo or MODO_AUTO
        cache_dir = Path(cache_dir) if cache_dir else self.base_dir

        usar_git = (self.modo_pedido == MODO_GIT or
                    (self.modo_pedido == MODO_AUTO and git_disponible()))
        # Si ya existe un clon, se respeta aunque git deje de estar disponible.
        if (self.base_dir / "bd_repo" / ".git").is_dir() and git_disponible():
            usar_git = True

        if usar_git:
            self.t = GitTransporte(self.base_dir / "bd_repo", repo_slug, rama, subdir,
                                   token, usuario, email, logger=self.log, url=url)
        else:
            self.t = RestTransporte(self.base_dir / "bd_local", repo_slug, rama, subdir,
                                    token, usuario, email,
                                    estado_path=cache_dir / "rest_state.json",
                                    logger=self.log)
        self.offline = False
        self.ultimo_error = ""
        self.ultima_sync = ""
        self.ultimo_push = ""
        self.ultimo_resumen = {}

    # ------------------------------------------------------------ props
    @property
    def backend(self):
        return self.t.backend

    @property
    def bd_root(self):
        return self.t.bd_root

    @property
    def token(self):
        return self.t.token

    def set_token(self, token):
        self.t.token = (token or "").strip()

    def necesita_descarga_diferida(self):
        """True si los PDFs se bajan bajo demanda (backend REST)."""
        return isinstance(self.t, RestTransporte)

    def asegurar_archivo(self, rel_bd):
        """Garantiza que un archivo de la BD exista localmente. ``rel_bd`` es
        relativo a ``BD_Submittals/`` (ej. ``ESTR/tubo.pdf``)."""
        if not self.necesita_descarga_diferida():
            return self.bd_root / rel_bd
        return self.t.asegurar_archivo(f"{self.t.subdir}/{rel_bd}")

    # ------------------------------------------------------------ acciones
    def pull(self, mensaje_local="BD: cambios locales pendientes"):
        """Sincroniza desde GitHub. NUNCA lanza por problemas de red: marca
        ``offline`` y devuelve el resumen."""
        try:
            r = self.t.pull(mensaje_local=mensaje_local)
            self.offline = False
            self.ultimo_error = ""
            self.ultima_sync = ahora_iso()
            self.ultimo_resumen = r
            return r
        except (SinConexionError, RepoNoEncontradoError) as e:
            self.offline = True
            self.ultimo_error = str(e)
            self.log.warning("Sin sincronizar (offline): %s", e)
            return {"backend": self.backend, "offline": True, "error": str(e),
                    "recibidos": 0, "conflictos": 0}
        except AutenticacionError as e:
            self.ultimo_error = str(e)
            self.log.warning("Sin sincronizar (auth): %s", e)
            return {"backend": self.backend, "offline": False, "error": str(e),
                    "recibidos": 0, "conflictos": 0, "auth": True}
        except SyncError as e:
            self.ultimo_error = str(e)
            self.log.error("Error de sincronizacion: %s", e)
            return {"backend": self.backend, "offline": False, "error": str(e),
                    "recibidos": 0, "conflictos": 0}

    def push(self, mensaje="BD: actualizar", archivos=None):
        """Sube cambios. Devuelve el resumen; si falla por red deja los cambios
        confirmados localmente y marca ``offline`` (se subiran al reconectar)."""
        try:
            r = self.t.push(mensaje=mensaje, archivos=archivos)
            if r.get("subido"):
                self.ultimo_push = ahora_iso()
                self.ultima_sync = self.ultimo_push
                self.offline = False
                self.ultimo_error = ""
            self.ultimo_resumen = r
            return r
        except (SinConexionError, RepoNoEncontradoError) as e:
            self.offline = True
            self.ultimo_error = str(e)
            self.log.warning("Cambios guardados localmente, sin subir: %s", e)
            return {"backend": self.backend, "subido": False, "offline": True,
                    "error": str(e), "conflictos": 0}
        except AutenticacionError as e:
            self.ultimo_error = str(e)
            return {"backend": self.backend, "subido": False, "offline": False,
                    "auth": True, "error": str(e), "conflictos": 0}
        except SyncError as e:
            self.ultimo_error = str(e)
            self.log.error("push fallo: %s", e)
            return {"backend": self.backend, "subido": False, "offline": False,
                    "error": str(e), "conflictos": 0}

    def estado(self):
        try:
            e = dict(self.t.estado())
        except Exception as ex:
            e = {"backend": self.backend, "listo": False, "error": str(ex)}
        e.update({"offline": self.offline, "ultima_sync": self.ultima_sync,
                  "ultimo_push": self.ultimo_push,
                  "ultimo_error": self.ultimo_error,
                  "modo_pedido": self.modo_pedido})
        return e

    def texto_estado(self):
        """Linea corta para la barra de estado de la GUI."""
        e = self.estado()
        if e.get("offline"):
            return "📡 Sin conexión — trabajando con la copia local"
        if self.ultimo_error and not self.ultima_sync:
            return f"⚠️ {self.ultimo_error[:70]}"
        if not e.get("autenticado"):
            return "🔑 Sin token: solo lectura"
        if self.ultimo_push:
            return f"☁️ Última subida: {_hace(self.ultimo_push)}"
        if self.ultima_sync:
            return f"🔄 Última sincronización: {_hace(self.ultima_sync)}"
        return "⏳ Sin sincronizar todavía"


def _hace(iso):
    """'hace 2 min' a partir de una marca ISO."""
    dt = parse_iso(iso)
    if not dt:
        return "—"
    seg = int((datetime.now() - dt).total_seconds())
    if seg < 60:
        return "hace segundos"
    if seg < 3600:
        return f"hace {seg // 60} min"
    if seg < 86400:
        return f"hace {seg // 3600} h"
    return dt.strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------
# CLI de diagnostico
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Diagnostico de sincronizacion de la BD")
    ap.add_argument("--base", default=str(Path.home() / ".generador_submittals"))
    ap.add_argument("--repo", default=REPO_DEFECTO)
    ap.add_argument("--rama", default=RAMA_DEFECTO)
    ap.add_argument("--modo", default=MODO_AUTO, choices=[MODO_AUTO, MODO_GIT, MODO_REST])
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    ap.add_argument("--pull", action="store_true")
    a = ap.parse_args()

    print("git instalado:", git_disponible())
    s = GitSync(a.base, a.repo, a.rama, token=a.token, modo=a.modo)
    print("backend:", s.backend, "| bd_root:", s.bd_root)
    if a.pull:
        print("pull:", s.pull())
    print("estado:", json.dumps(s.estado(), ensure_ascii=False, indent=2))
    print(s.texto_estado())
