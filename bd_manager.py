#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 bd_manager.py  --  Base de Datos centralizada en GitHub (v3.1.0)
================================================================================
La BD de fichas tecnicas ya NO vive en OneDrive: vive en el repositorio del app,
en la subcarpeta ``BD_Submittals/``, y se sincroniza con git/GitHub.

    github.com/adrianix360/generador-submittals
        BD_Submittals/
            indice.json                 <- catalogo de todas las fichas
            ARQ/  ESTR/  MEC/  ELEC/    <- PDFs de las fichas, por categoria
            Proyectos/<Nombre>/         <- submittal_proyecto.json (metadatos)

El app trabaja sobre una copia local propia
(``%LOCALAPPDATA%/GeneradorSubmittals/bd_repo``, *sparse checkout* de
``BD_Submittals/``), nunca sobre la carpeta de desarrollo del usuario.

Cambios de v3.1.0 (la BD paso de OneDrive a GitHub):
  - ELIMINADO el archivo ``.lock`` y todo el control de acceso secuencial.
    Git resuelve la concurrencia: si dos PCs suben cambios, se fusionan.
  - ELIMINADA la deteccion de OneDrive.
  - NUEVO: ``sincronizar()`` / ``git_pull()`` / ``git_push()`` / ``git_status()``
    / ``git_merge_conflict_handler()`` / ``sync_indice()``.
  - NUEVO: seguimiento de cambios pendientes de subir (modo offline).
  - NUEVO: ``fecha_modificacion`` en cada ficha (decide quien gana un conflicto).

Cambios de v3.2.0 (nomenclatura inteligente):
  - NUEVO campo ``nombre_ficha``: nombre descriptivo y unico generado por
    ``nomenclatura.py`` (ej. ``TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" -
    MultiGroup``). El PDF se guarda con ese nombre, asi la carpeta de la BD se
    puede leer sin abrir el indice.
  - NUEVO: deteccion de fichas repetidas por nombre (``buscar_por_nombre``) y
    ``reemplazar_pdf_ficha()`` para corregir una ficha mal cargada.
  - ``editar_ficha()`` regenera el nombre al cambiar los datos, salvo que el
    usuario lo haya escrito a mano (``nombre_ficha_manual``).
  - Se CONSERVA el soft delete: el borrado logico es lo que permite fusionar dos
    BDs sin resucitar fichas eliminadas. Lo que faltaba no era borrar, era poder
    CORREGIR una ficha; eso es lo que agrega esta version.

Se conserva sin cambios de comportamiento: validacion de fichas, alta/edicion/
soft delete, busqueda fuzzy, cache local (2 GB FIFO), y toda la construccion de
submittals que alimenta el motor de caratulas de v2.6.

``BDManager`` sigue siendo utilizable de forma aislada (sin red): si se le pasa
``bd_root`` explicito y ningun ``sync``, trabaja como gestor de una carpeta local
y los metodos de git son no-op. Eso mantiene las pruebas simples.
================================================================================
"""

import os
import re
import json
import time
import base64
import shutil
import socket
import hashlib
import logging
import unicodedata
from pathlib import Path
from datetime import datetime

import fuzzy_search
import git_bd
import nomenclatura

# Se re-exporta para que el resto del sistema use un solo modulo (bd_manager).
generar_nombre_ficha_unico = nomenclatura.generar_nombre_ficha_unico
analizar_nomenclatura = nomenclatura.analizar
clave_unicidad = nomenclatura.clave_unicidad

# --------------------------------------------------------------------------
# CONSTANTES
# --------------------------------------------------------------------------
VERSION = "3.2.0"
VERSIONES_INDICE_ACEPTADAS = ("3.",)   # cualquier 3.x

# Categoria (codigo) -> carpeta "madre" del layout v2.6
CATEGORIAS = {
    "ARQ": "ARQUITECTONICOS",
    "ESTR": "ESTRUCTURALES",
    "MEC": "MECANICOS",
    "ELEC": "ELECTRICOS",
}
# Carpeta madre -> nombre singular usado en el compilado por disciplina (v2.6)
DISCIPLINA_SINGULAR = {
    "ARQUITECTONICOS": "ARQUITECTONICO",
    "ESTRUCTURALES": "ESTRUCTURAL",
    "MECANICOS": "MECANICO",
    "ELECTRICOS": "ELECTRICO",
}

NOMBRE_BD = "BD_Submittals"
NOMBRE_INDICE = "indice.json"
NOMBRE_PROYECTOS = "Proyectos"
NOMBRE_SUBMITTAL_JSON = "submittal_proyecto.json"

CACHE_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
REINTENTOS_LECTURA = 2
ESPERA_REINTENTO_SEG = 2

ESTADO_ACTIVO = "activo"
ESTADO_INACTIVO = "inactivo"

CAMPOS_OBLIGATORIOS_FICHA = ("nombre_material", "marca", "categoria")
CAMPOS_PROCEDIMIENTO = ("numero_procedimiento", "institucion", "detalle", "plazo", "monto")


# --------------------------------------------------------------------------
# EXCEPCIONES
# --------------------------------------------------------------------------
class BDError(Exception):
    """Error generico de la Base de Datos."""


# Se re-exportan para que la GUI maneje un solo modulo.
SyncError = git_bd.SyncError
SinConexionError = git_bd.SinConexionError
AutenticacionError = git_bd.AutenticacionError
RepoNoEncontradoError = git_bd.RepoNoEncontradoError


# --------------------------------------------------------------------------
# HELPERS DE TIEMPO / TEXTO
# --------------------------------------------------------------------------
def ahora_iso():
    """Marca de tiempo ISO local (segundos)."""
    return datetime.now().replace(microsecond=0).isoformat()


def _parse_iso(s):
    return git_bd.parse_iso(s)


def sanitizar_nombre(nombre):
    """Reemplaza caracteres invalidos de Windows para nombres de archivo."""
    s = str(nombre or "").replace('"', "in").replace("/", "-").replace("\\", "-")
    s = re.sub(r"[:*?<>|]", "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or "ficha"


def _slug(texto):
    """Slug simple (sin acentos, con guiones) para nombres de archivo."""
    s = unicodedata.normalize("NFD", str(texto or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^0-9A-Za-z]+", "-", s).strip("-")
    return s or "ficha"


def sha256_file(path, corto=True):
    """SHA-256 de un archivo. ``corto`` -> primeros 16 caracteres."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    d = h.hexdigest()
    return d[:16] if corto else d


# --------------------------------------------------------------------------
# (DES)OFUSCADO DE SECRETOS  (base64, compatible con v2.6)
# --------------------------------------------------------------------------
# NOTA DE SEGURIDAD: base64 NO es cifrado, es ofuscacion. Se mantiene por
# compatibilidad con el config de v2.6. Para el token de GitHub use un
# Fine-grained PAT limitado a ESTE repositorio y con permiso Contents: write,
# de modo que su filtracion no exponga nada mas.
def cifrar_api_key(key):
    try:
        return base64.b64encode(str(key).encode("utf-8")).decode("ascii")
    except Exception:
        return ""


def descifrar_api_key(enc):
    try:
        return base64.b64decode(str(enc).encode("ascii")).decode("utf-8")
    except Exception:
        return ""


cifrar_secreto = cifrar_api_key
descifrar_secreto = descifrar_api_key


# --------------------------------------------------------------------------
# RUTAS DEL SISTEMA
# --------------------------------------------------------------------------
def dir_appdata():
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / "GeneradorSubmittals"
    p.mkdir(parents=True, exist_ok=True)
    return p


def dir_cache():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    p = Path(base) / "GeneradorSubmittals" / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def dir_bd_local():
    """Carpeta base donde vive la copia local de la BD (clon o espejo).

    Es intencional que NO sea la carpeta del proyecto: asi un ``git pull`` de la
    BD nunca choca con cambios de codigo sin confirmar.
    """
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    p = Path(base) / "GeneradorSubmittals"
    p.mkdir(parents=True, exist_ok=True)
    return p


# --------------------------------------------------------------------------
# CONFIG  (%APPDATA%/GeneradorSubmittals/config.json)
# --------------------------------------------------------------------------
CONFIG_DEFECTO = {
    "version": VERSION,
    "bd_local": "",                # vacio -> dir_bd_local()
    "github": {
        "repo": git_bd.REPO_DEFECTO,
        "branch": git_bd.RAMA_DEFECTO,
        "subdir": NOMBRE_BD,
        "token_encrypted": "",     # PAT por usuario (base64, ver nota arriba)
        "usuario": "",
        "email": "",
        "modo": git_bd.MODO_AUTO,  # auto | git | rest
        "auto_pull": True,
        "auto_push": True,
    },
    "api": {"openai_key_encrypted": "", "ultima_validacion": ""},
    "cache": {"max_bytes": CACHE_MAX_BYTES, "ultima_limpieza": ""},
    "ui": {"caratula_seleccionada": "clasica", "carpetas_recientes": []},
}


def cargar_config(config_dir=None):
    """Carga la config combinada con los valores por defecto."""
    cdir = Path(config_dir) if config_dir else dir_appdata()
    path = cdir / "config.json"
    cfg = json.loads(json.dumps(CONFIG_DEFECTO))
    try:
        disco = json.loads(path.read_text(encoding="utf-8"))
        for k, v in disco.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    except Exception:
        pass
    # Migracion silenciosa: el 'bd_root' de OneDrive de v3.0.0 ya no aplica.
    cfg.pop("bd_root", None)
    return cfg


def guardar_config(cfg, config_dir=None):
    cdir = Path(config_dir) if config_dir else dir_appdata()
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "config.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def obtener_api_key(cfg=None, config_dir=None, fallback_config_v26=None):
    """API key de OpenAI: entorno -> config v3 -> config v2.6."""
    env = os.environ.get("OPENAI_API_KEY", "").strip()
    if env:
        return env
    if cfg is None:
        cfg = cargar_config(config_dir)
    enc = cfg.get("api", {}).get("openai_key_encrypted", "")
    if enc:
        k = descifrar_api_key(enc)
        if k:
            return k
    if fallback_config_v26:
        try:
            v26 = json.loads(Path(fallback_config_v26).read_text(encoding="utf-8"))
            return descifrar_api_key(v26.get("api", {}).get("openai_key_encrypted", ""))
        except Exception:
            pass
    return ""


def obtener_token_github(cfg=None, config_dir=None):
    """Token de GitHub: entorno ``GITHUB_TOKEN`` -> config (base64)."""
    env = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if env:
        return env
    if cfg is None:
        cfg = cargar_config(config_dir)
    return descifrar_secreto(cfg.get("github", {}).get("token_encrypted", ""))


def guardar_token_github(token, cfg=None, config_dir=None):
    """Guarda el PAT del usuario en su config local y lo devuelve."""
    cfg = cfg if cfg is not None else cargar_config(config_dir)
    cfg.setdefault("github", {})["token_encrypted"] = cifrar_secreto((token or "").strip())
    guardar_config(cfg, config_dir)
    return cfg


def crear_sync(cfg=None, config_dir=None, cache_dir=None, logger=None):
    """Construye el ``GitSync`` a partir de la configuracion del usuario."""
    cfg = cfg if cfg is not None else cargar_config(config_dir)
    gh = cfg.get("github", {}) or {}
    base = Path(cfg.get("bd_local") or dir_bd_local())
    return git_bd.GitSync(
        base_dir=base,
        repo_slug=gh.get("repo") or git_bd.REPO_DEFECTO,
        rama=gh.get("branch") or git_bd.RAMA_DEFECTO,
        subdir=gh.get("subdir") or NOMBRE_BD,
        token=obtener_token_github(cfg),
        usuario=gh.get("usuario") or socket.gethostname(),
        email=gh.get("email") or "",
        modo=gh.get("modo") or git_bd.MODO_AUTO,
        cache_dir=Path(cache_dir) if cache_dir else dir_cache(),
        logger=logger,
    )


# --------------------------------------------------------------------------
# VALIDACION DEL INDICE
# --------------------------------------------------------------------------
def validar_indice(data):
    """Comprueba la integridad de ``indice.json`` tras sincronizar.

    Devuelve ``(ok, errores)``. No corrige nada: quien llama decide si usa el
    respaldo en cache.
    """
    errores = []
    if not isinstance(data, dict):
        return (False, ["El indice no es un objeto JSON"])
    ver = str(data.get("version", ""))
    if ver and not ver.startswith(VERSIONES_INDICE_ACEPTADAS):
        errores.append(f"Version de indice no soportada: {ver}")
    fichas = data.get("fichas")
    if fichas is None:
        errores.append("El indice no tiene la clave 'fichas'")
    elif not isinstance(fichas, list):
        errores.append("'fichas' debe ser una lista")
    else:
        ids = set()
        for i, f in enumerate(fichas):
            if not isinstance(f, dict):
                errores.append(f"Ficha #{i} no es un objeto")
                continue
            fid = f.get("id")
            if not fid:
                errores.append(f"Ficha #{i} sin 'id'")
            elif fid in ids:
                errores.append(f"'id' duplicado en el indice: {fid}")
            else:
                ids.add(fid)
            for campo in CAMPOS_OBLIGATORIOS_FICHA:
                if not str(f.get(campo, "")).strip():
                    errores.append(f"Ficha {fid or i} sin '{campo}'")
            if not str(f.get("ruta_pdf", "")).strip():
                errores.append(f"Ficha {fid or i} sin 'ruta_pdf'")
    return (len(errores) == 0, errores)


# ==========================================================================
# GESTOR PRINCIPAL DE LA BD
# ==========================================================================
class BDManager:
    """Gestiona la BD de fichas sincronizada con GitHub.

    Tres formas de construirlo:
      * ``BDManager()``                       -> usa la config del usuario y crea
                                                 el ``GitSync`` (modo normal).
      * ``BDManager(bd_root=carpeta)``         -> carpeta local, sin red (pruebas).
      * ``BDManager(sync=mi_sync)``            -> con un ``GitSync`` ya construido.
    """

    def __init__(self, bd_root=None, cache_dir=None, config_dir=None, logger=None,
                 sync=None, con_sync=None):
        self.config_dir = Path(config_dir) if config_dir else dir_appdata()
        self.cfg = cargar_config(self.config_dir)
        self.cache_dir = Path(cache_dir) if cache_dir else dir_cache()
        self.log = logger or logging.getLogger("bd_manager")

        # ¿Se debe sincronizar con GitHub?
        if con_sync is None:
            con_sync = sync is not None or bd_root is None

        if sync is not None:
            self.sync = sync
        elif con_sync:
            self.sync = crear_sync(self.cfg, self.config_dir, self.cache_dir, self.log)
        else:
            self.sync = None

        if bd_root:
            self.bd_root = Path(bd_root)
        elif self.sync is not None:
            self.bd_root = Path(self.sync.bd_root)
        else:
            self.bd_root = dir_bd_local() / NOMBRE_BD

        self.indice_path = self.bd_root / NOMBRE_INDICE
        self.proyectos_dir = self.bd_root / NOMBRE_PROYECTOS
        self.cache_indice = self.cache_dir / "indice_cache.json"
        self.pendientes_path = self.cache_dir / "pendientes.json"

        self.usando_cache = False        # True si el indice se leyo del cache
        self.pendientes = self._cargar_pendientes()
        self.ultimo_resumen_sync = {}

    # ================================================================ setup
    def inicializar_bd(self):
        """Crea la estructura de carpetas de la BD si no existe."""
        self.bd_root.mkdir(parents=True, exist_ok=True)
        self.proyectos_dir.mkdir(parents=True, exist_ok=True)
        for cat in CATEGORIAS:
            (self.bd_root / cat).mkdir(parents=True, exist_ok=True)
        if not self.indice_path.exists():
            self._guardar_indice({"version": VERSION,
                                  "ultima_actualizacion": ahora_iso(),
                                  "fichas": []})

    def bd_disponible(self):
        """True si la copia local de la BD es accesible."""
        try:
            return self.bd_root.exists() and os.access(self.bd_root, os.R_OK)
        except Exception:
            return False

    # ======================================================== SINCRONIZACION
    def sincronizar(self, mensaje_local=None):
        """``git pull`` de la BD: trae el indice y las fichas nuevas de GitHub.

        Nunca lanza por problemas de red: si no hay conexion se sigue trabajando
        con la copia local (``resumen['offline'] is True``).
        """
        if self.sync is None:
            return {"desactivado": True}
        msg = mensaje_local or f"BD: cambios locales de {socket.gethostname()}"
        r = self.sync.pull(mensaje_local=msg)
        # El clon puede haber creado la carpeta justo ahora.
        self.bd_root = Path(self.sync.bd_root)
        self.indice_path = self.bd_root / NOMBRE_INDICE
        self.proyectos_dir = self.bd_root / NOMBRE_PROYECTOS
        self.ultimo_resumen_sync = r
        if not r.get("offline") and not r.get("error"):
            self.pendientes = set()
            self._guardar_pendientes()
        return r

    # Alias explicitos pedidos por la especificacion -----------------------
    def git_pull(self, mensaje_local=None):
        """Alias de ``sincronizar()``."""
        return self.sincronizar(mensaje_local=mensaje_local)

    def git_push(self, descripcion="actualizar BD"):
        """Confirma y sube los cambios locales a GitHub.

        Si hay conflicto, el transporte lo resuelve solo (fusion por registro) y
        reintenta el push. Devuelve el resumen.
        """
        if self.sync is None:
            return {"desactivado": True}
        r = self.sync.push(mensaje=f"BD: {descripcion}")
        self.ultimo_resumen_sync = r
        if r.get("subido"):
            self.pendientes = set()
            self._guardar_pendientes()
        return r

    def git_status(self):
        """Estado de sincronizacion (para la barra de estado de la GUI)."""
        if self.sync is None:
            return {"desactivado": True, "backend": "local", "offline": False,
                    "pendientes": len(self.pendientes)}
        e = self.sync.estado()
        e["pendientes"] = max(int(e.get("pendientes", 0) or 0), len(self.pendientes))
        return e

    def git_merge_conflict_handler(self):
        """Resuelve manualmente un merge en curso (normalmente no hace falta:
        ``sincronizar()`` y ``git_push()`` ya lo llaman solos)."""
        if self.sync is None:
            return {"desactivado": True}
        t = getattr(self.sync, "t", None)
        if hasattr(t, "resolver_conflictos"):
            return t.resolver_conflictos()
        return {"soportado": False}

    def texto_estado_sync(self):
        if self.sync is None:
            return "BD local (sin sincronizacion)"
        return self.sync.texto_estado()

    def sync_indice(self):
        """Sincroniza, valida la integridad del indice y lo devuelve.

        Si el indice descargado no pasa la validacion, se conserva el respaldo
        en cache y se marca ``usando_cache``.
        """
        resumen = self.sincronizar()
        self.inicializar_bd()
        data = self.cargar_indice()
        ok, errores = validar_indice(data)
        if not ok:
            self.log.error("Indice invalido tras sincronizar: %s", errores[:5])
            respaldo = self._leer_cache_indice()
            if respaldo is not None:
                self.usando_cache = True
                data = respaldo
            resumen = dict(resumen)
            resumen["indice_invalido"] = errores
        else:
            data.setdefault("rama_actual", (resumen.get("rama")
                                            or self.git_status().get("rama", "")))
            data["ultima_sincronizacion_git"] = ahora_iso()
            self._respaldar_indice_cache(data)
        resumen = dict(resumen)
        resumen["fichas"] = len(data.get("fichas", []))
        self.ultimo_resumen_sync = resumen
        return data, resumen

    # ------------------------------------------------- cambios pendientes
    def _cargar_pendientes(self):
        try:
            return set(json.loads(self.pendientes_path.read_text(encoding="utf-8")))
        except Exception:
            return set()

    def _guardar_pendientes(self):
        try:
            self.pendientes_path.parent.mkdir(parents=True, exist_ok=True)
            self.pendientes_path.write_text(
                json.dumps(sorted(self.pendientes), ensure_ascii=False),
                encoding="utf-8")
        except Exception:
            pass

    def marcar_pendiente(self, ruta_rel):
        """Registra que un archivo de la BD cambio y falta subirlo."""
        self.pendientes.add(str(ruta_rel).replace("\\", "/"))
        self._guardar_pendientes()

    def hay_cambios_sin_subir(self):
        if self.pendientes:
            return True
        try:
            return bool(self.git_status().get("pendientes"))
        except Exception:
            return False

    # ============================================================== indice
    def cargar_indice(self):
        """Carga ``indice.json`` con reintentos; ante fallo usa el cache local y
        marca ``usando_cache``."""
        self.usando_cache = False
        ultimo_error = None
        for intento in range(1, REINTENTOS_LECTURA + 1):
            try:
                if not self.indice_path.exists():
                    return {"version": VERSION, "ultima_actualizacion": ahora_iso(),
                            "fichas": []}
                data = json.loads(self.indice_path.read_text(encoding="utf-8"))
                if "fichas" not in data:
                    data["fichas"] = []
                self._respaldar_indice_cache(data)
                return data
            except Exception as e:
                ultimo_error = e
                self.log.warning("Lectura de indice fallo (intento %d/%d): %s",
                                 intento, REINTENTOS_LECTURA, e)
                time.sleep(ESPERA_REINTENTO_SEG)

        respaldo = self._leer_cache_indice()
        if respaldo is not None:
            self.usando_cache = True
            self.log.warning("Usando indice desde CACHE: %s", ultimo_error)
            return respaldo
        raise BDError(f"No se pudo leer el indice de la BD: {ultimo_error}")

    def _leer_cache_indice(self):
        if not self.cache_indice.exists():
            return None
        try:
            data = json.loads(self.cache_indice.read_text(encoding="utf-8"))
            data.setdefault("fichas", [])
            return data
        except Exception:
            return None

    def _respaldar_indice_cache(self, data):
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_indice.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _guardar_indice(self, data):
        """Escribe el indice de forma atomica (tmp + replace) y lo marca como
        pendiente de subir."""
        data["version"] = VERSION
        data["ultima_actualizacion"] = ahora_iso()
        if self.sync is not None:
            est = {}
            try:
                est = self.sync.estado()
            except Exception:
                pass
            data.setdefault("rama_actual", est.get("rama", ""))
            if est.get("ultima_sync"):
                data["ultima_sincronizacion_git"] = est["ultima_sync"]
        self.bd_root.mkdir(parents=True, exist_ok=True)
        tmp = self.indice_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.indice_path)
        self._respaldar_indice_cache(data)
        self.marcar_pendiente(NOMBRE_INDICE)

    def listar_fichas(self, incluir_inactivas=False):
        """Lista las fichas del indice (por defecto solo activas)."""
        data = self.cargar_indice()
        fichas = data.get("fichas", [])
        if incluir_inactivas:
            return fichas
        return [f for f in fichas if f.get("estado", ESTADO_ACTIVO) == ESTADO_ACTIVO]

    def obtener_ficha(self, id_ficha, incluir_inactivas=True):
        for f in self.listar_fichas(incluir_inactivas=incluir_inactivas):
            if f.get("id") == id_ficha:
                return f
        return None

    def resumen_por_categoria(self):
        """Cuenta de fichas activas por categoria."""
        conteo = {c: 0 for c in CATEGORIAS}
        total = 0
        for f in self.listar_fichas():
            cat = str(f.get("categoria", "")).upper()
            if cat in conteo:
                conteo[cat] += 1
            total += 1
        conteo["TOTAL"] = total
        return conteo

    # ----------------------------------------------------------- busqueda
    def buscar(self, query, categoria=None, marca=None, top_n=fuzzy_search.TOP_N):
        """Busqueda fuzzy sobre las fichas activas (ver ``fuzzy_search``)."""
        return fuzzy_search.buscar(query, self.listar_fichas(),
                                   categoria=categoria, marca=marca, top_n=top_n)

    # =============================================================== fichas
    def _validar_ficha(self, datos, pdf_src):
        """Valida los campos y el PDF antes de cargar una ficha."""
        errores = []
        for campo in CAMPOS_OBLIGATORIOS_FICHA:
            if not str(datos.get(campo, "")).strip():
                errores.append(f"Falta campo obligatorio: {campo}")
        cat = str(datos.get("categoria", "")).strip().upper()
        if cat and cat not in CATEGORIAS:
            errores.append(f"Categoria invalida: {cat} (use {', '.join(CATEGORIAS)})")
        p = Path(pdf_src)
        if not p.exists() or p.stat().st_size == 0:
            errores.append(f"PDF invalido o vacio: {pdf_src}")
        else:
            try:
                with open(p, "rb") as f:
                    cabecera = f.read(5)
                if p.suffix.lower() == ".pdf" and not cabecera.startswith(b"%PDF"):
                    errores.append("El archivo no parece un PDF valido (sin cabecera %PDF)")
            except Exception as e:
                errores.append(f"No se pudo leer el PDF: {e}")
        return errores

    def agregar_ficha(self, pdf_src, datos, subir=False):
        """Agrega una ficha nueva a la BD local.

        El nombre descriptivo (``nombre_ficha``) se genera solo con
        ``nomenclatura.generar_nombre_ficha_unico()``, salvo que ``datos`` ya
        traiga uno (el usuario lo edito en el preview). El PDF se guarda con ese
        nombre, para poder identificarlo sin abrir el indice.

        Con ``subir=True`` hace ``git_push()`` al terminar.

        Devuelve la ficha creada. Lanza ``BDError`` si la validacion falla.
        """
        errores = self._validar_ficha(datos, pdf_src)
        if errores:
            raise BDError("Ficha invalida:\n - " + "\n - ".join(errores))

        cat = str(datos["categoria"]).strip().upper()
        self.bd_root.mkdir(parents=True, exist_ok=True)
        (self.bd_root / cat).mkdir(parents=True, exist_ok=True)

        nombre_ficha = str(datos.get("nombre_ficha", "") or "").strip()
        manual = bool(nombre_ficha)
        if not nombre_ficha:
            nombre_ficha = nomenclatura.generar_nombre_ficha_unico(datos)

        base_nombre = nomenclatura.slug_archivo(nombre_ficha)
        # Se CONSERVA la extension original. Guardar un .jpg como ".pdf" hacia
        # que el compilado no pudiera anexarlo (pypdf falla y el aviso se pierde
        # en el log): el CMP salia con la caratula sola. Con la extension real,
        # el motor de v2.6 convierte la imagen a PDF al compilar.
        sufijo = Path(pdf_src).suffix.lower() or ".pdf"
        destino_rel = f"{cat}/{base_nombre}{sufijo}"
        destino_abs = self.bd_root / cat / f"{base_nombre}{sufijo}"
        n = 1
        while destino_abs.exists():
            n += 1
            destino_rel = f"{cat}/{base_nombre}-{n}{sufijo}"
            destino_abs = self.bd_root / cat / f"{base_nombre}-{n}{sufijo}"
        shutil.copy2(pdf_src, destino_abs)

        ficha = {
            "id": _nuevo_id(),
            "nombre_ficha": nombre_ficha,
            "nombre_ficha_manual": manual,
            "nombre_material": str(datos.get("nombre_material", "")).strip(),
            "marca": str(datos.get("marca", "")).strip(),
            "categoria": cat,
            "tipo_producto": str(datos.get("tipo_producto", "")).strip(),
            "dimensiones": str(datos.get("dimensiones", "")).strip(),
            "sin_medidas": bool(datos.get("sin_medidas", False)),
            "especificacion": str(datos.get("especificacion", "")).strip(),
            "normativa": str(datos.get("normativa", "SIN ESPECIFICAR")).strip() or "SIN ESPECIFICAR",
            "descripcion_corta": str(datos.get("descripcion_corta", "")).strip(),
            "aspectos_adicionales": str(datos.get("aspectos_adicionales", "")).strip(),
            "search_keywords": "",
            "ruta_pdf": destino_rel,
            "hash_archivo": sha256_file(destino_abs),
            "fecha_carga": datetime.now().strftime("%Y-%m-%d"),
            "fecha_modificacion": ahora_iso(),
            "cargada_por": socket.gethostname(),
            "estado": ESTADO_ACTIVO,
        }
        ficha["search_keywords"] = fuzzy_search.generar_search_keywords(ficha)

        data = self.cargar_indice()
        data.setdefault("fichas", []).append(ficha)
        self._guardar_indice(data)
        self.marcar_pendiente(destino_rel)
        self.log.info("Ficha agregada: %s -> %s", ficha["nombre_ficha"], destino_rel)
        if subir:
            self.git_push(f"agregar ficha {ficha['nombre_ficha']}")
        return ficha

    def actualizar_ficha(self, id_ficha, cambios, subir=False, regenerar_nombre=None):
        """Actualiza campos de una ficha, recalcula el nombre y las keywords.

        ``regenerar_nombre``:
          * ``None`` (defecto) -> se regenera salvo que el nombre sea manual o
            venga uno nuevo en ``cambios``.
          * ``True``  -> se regenera siempre (boton "Regenerar nombre").
          * ``False`` -> no se toca el nombre.
        """
        data = self.cargar_indice()
        for f in data.get("fichas", []):
            if f.get("id") != id_ficha:
                continue
            nombre_explicito = str(cambios.get("nombre_ficha", "") or "").strip()
            for k, v in cambios.items():
                if k in ("id", "ruta_pdf", "hash_archivo"):
                    continue  # inmutables desde aqui
                f[k] = v
            if nombre_explicito:
                f["nombre_ficha"] = nombre_explicito
                f["nombre_ficha_manual"] = True
            elif regenerar_nombre or (regenerar_nombre is None
                                      and not f.get("nombre_ficha_manual")):
                f["nombre_ficha"] = nomenclatura.generar_nombre_ficha_unico(f)
                f["nombre_ficha_manual"] = False
            f["search_keywords"] = fuzzy_search.generar_search_keywords(f)
            f["fecha_modificacion"] = ahora_iso()
            self._guardar_indice(data)
            if subir:
                self.git_push(f"actualizar ficha {f.get('nombre_ficha', id_ficha)}")
            return f
        raise BDError(f"Ficha no encontrada: {id_ficha}")

    # Alias explicito: en la interfaz la accion se llama "Editar ficha".
    editar_ficha = actualizar_ficha

    def reemplazar_pdf_ficha(self, id_ficha, pdf_src, subir=False):
        """Reemplaza el archivo de una ficha conservando su ``id`` y su nombre.

        Es la salida para una ficha bien identificada pero con el archivo
        equivocado: se corrige sin romper los submittals que ya la referencian
        (apuntan al ``id``, no a la ruta).

        Valida igual que un alta. Si el archivo nuevo tiene otra extension
        (por ejemplo se sube un .pdf donde antes habia un .jpg), la ruta se
        ajusta: dejar la extension vieja rompia el compilado.
        """
        data = self.cargar_indice()
        for f in data.get("fichas", []):
            if f.get("id") != id_ficha:
                continue
            errores = self._validar_ficha(f, pdf_src)
            # Los campos de la ficha ya estaban validados; aqui solo interesa el
            # archivo.
            errores = [e for e in errores if "PDF" in e or "archivo" in e.lower()]
            if errores:
                raise BDError("Archivo invalido:\n - " + "\n - ".join(errores))

            p = Path(pdf_src)
            ruta_vieja = f["ruta_pdf"]
            sufijo_nuevo = p.suffix.lower() or Path(ruta_vieja).suffix
            ruta_rel = str(Path(ruta_vieja).with_suffix(sufijo_nuevo).as_posix())
            destino = self.bd_root / ruta_rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, destino)
            if ruta_rel != ruta_vieja:
                try:
                    (self.bd_root / ruta_vieja).unlink()
                except Exception:
                    pass
                f["ruta_pdf"] = ruta_rel
                self.marcar_pendiente(ruta_vieja)
            f["hash_archivo"] = sha256_file(destino)
            f["fecha_modificacion"] = ahora_iso()
            self._guardar_indice(data)
            self.marcar_pendiente(ruta_rel)
            # Invalidar la copia en cache (el tamano puede coincidir).
            for rel in {ruta_vieja, ruta_rel}:
                try:
                    (self.cache_dir / rel).unlink()
                except Exception:
                    pass
            self.log.info("Archivo reemplazado en %s", self.nombre_de(f))
            if subir:
                self.git_push(f"reemplazar archivo de {self.nombre_de(f)}")
            return f
        raise BDError(f"Ficha no encontrada: {id_ficha}")

    # ------------------------------------------------- nombres / duplicados
    def buscar_por_nombre(self, nombre_ficha, excluir_id=None,
                          incluir_inactivas=True):
        """Devuelve la ficha cuyo nombre coincide (normalizado), o ``None``.

        Es la comprobacion de duplicados: ``'TUBO ESTRUCTURAL 8" x 8" -
        MultiGroup'`` y ``'tubo estructural 8x8 - multigroup'`` son el mismo.
        """
        clave = nomenclatura.clave_unicidad(nombre_ficha)
        if not clave:
            return None
        for f in self.listar_fichas(incluir_inactivas=incluir_inactivas):
            if excluir_id and f.get("id") == excluir_id:
                continue
            if nomenclatura.clave_unicidad(self.nombre_de(f)) == clave:
                return f
        return None

    @staticmethod
    def nombre_de(ficha):
        """Nombre a mostrar de una ficha. Si es de una version anterior y no
        tiene ``nombre_ficha``, se genera al momento (sin escribir en la BD)."""
        n = str(ficha.get("nombre_ficha", "") or "").strip()
        if n:
            return n
        return nomenclatura.generar_nombre_ficha_unico(ficha)

    def fichas_sin_nombre(self):
        """Fichas anteriores a v3.2.0 que todavia no tienen ``nombre_ficha``."""
        return [f for f in self.listar_fichas(incluir_inactivas=True)
                if not str(f.get("nombre_ficha", "") or "").strip()]

    def migrar_nombres_ficha(self, subir=False):
        """Genera y guarda ``nombre_ficha`` en las fichas que no lo tengan.

        Idempotente: si no hay nada que migrar, no toca el indice.
        """
        data = self.cargar_indice()
        cambiadas = 0
        for f in data.get("fichas", []):
            if str(f.get("nombre_ficha", "") or "").strip():
                continue
            f["nombre_ficha"] = nomenclatura.generar_nombre_ficha_unico(f)
            f["nombre_ficha_manual"] = False
            f["search_keywords"] = fuzzy_search.generar_search_keywords(f)
            # A proposito NO se toca 'fecha_modificacion': es lo que decide quien
            # gana al fusionar dos BDs, y esta migracion es cosmetica. Si otra PC
            # edito la misma ficha de verdad, su version debe ganar.
            cambiadas += 1
        if cambiadas:
            self._guardar_indice(data)
            self.log.info("Nombres generados para %d ficha(s)", cambiadas)
            if subir:
                self.git_push(f"generar nombre de {cambiadas} ficha(s)")
        return cambiadas

    def proyectos_que_usan(self, id_ficha):
        """Proyectos guardados en la BD que referencian esta ficha.

        Se usa para avisar antes de desactivar una ficha: esos submittals
        fallarian la validacion al regenerarse.
        """
        salida = []
        for p in self.listar_proyectos():
            try:
                d = json.loads((Path(p["carpeta_bd"]) / NOMBRE_SUBMITTAL_JSON)
                               .read_text(encoding="utf-8"))
            except Exception:
                continue
            for m in d.get("materiales_seleccionados", []) or []:
                if m.get("id_ficha_bd") == id_ficha:
                    salida.append({"nombre_proyecto": d.get("nombre_proyecto", p["nombre_proyecto"]),
                                   "consecutivo": m.get("consecutivo", "")})
                    break
        return salida

    def soft_delete_ficha(self, id_ficha, subir=False):
        """*Soft delete*: marca la ficha como ``inactivo`` SIN borrar el PDF.

        Es importante que el borrado sea logico: al fusionar dos BDs nunca hay
        que decidir si un registro ausente fue borrado o es nuevo.
        """
        data = self.cargar_indice()
        for f in data.get("fichas", []):
            if f.get("id") == id_ficha:
                f["estado"] = ESTADO_INACTIVO
                f["fecha_modificacion"] = ahora_iso()
                f["desactivada_por"] = socket.gethostname()
                self._guardar_indice(data)
                self.log.info("Ficha marcada inactiva (soft delete): %s",
                              f.get("nombre_ficha", id_ficha))
                if subir:
                    self.git_push(f"desactivar ficha {self.nombre_de(f)}")
                return True
        return False

    def reactivar_ficha(self, id_ficha, subir=False):
        """Vuelve a activar una ficha desactivada.

        Es el complemento del soft delete: si se desactivo por error, se
        recupera. Con hard delete esto no seria posible.
        """
        data = self.cargar_indice()
        for f in data.get("fichas", []):
            if f.get("id") == id_ficha:
                f["estado"] = ESTADO_ACTIVO
                f["fecha_modificacion"] = ahora_iso()
                self._guardar_indice(data)
                if subir:
                    self.git_push(f"reactivar ficha {self.nombre_de(f)}")
                return True
        return False

    # ================================================================ cache
    def ruta_local_ficha(self, ficha):
        """Ruta LOCAL (en cache) del PDF de la ficha, copiandolo desde la BD si
        hace falta. Con el backend REST, primero lo descarga bajo demanda."""
        ruta_rel = ficha.get("ruta_pdf", "")
        if not ruta_rel:
            raise BDError("La ficha no tiene ruta_pdf")
        origen = self.bd_root / ruta_rel
        destino = self.cache_dir / ruta_rel
        destino.parent.mkdir(parents=True, exist_ok=True)

        if not origen.exists() and self.sync is not None:
            try:
                if self.sync.necesita_descarga_diferida():
                    origen = Path(self.sync.asegurar_archivo(ruta_rel))
            except Exception as e:
                self.log.warning("No se pudo descargar '%s': %s", ruta_rel, e)

        necesita_copia = True
        if destino.exists() and origen.exists():
            try:
                # Comparar por HASH, no por tamano: al reemplazar el archivo de
                # una ficha el tamano puede coincidir y se seguiria usando la
                # copia vieja del cache. El hash de la ficha ya esta calculado.
                esperado = ficha.get("hash_archivo")
                if esperado:
                    necesita_copia = sha256_file(destino) != esperado
                else:
                    necesita_copia = destino.stat().st_size != origen.stat().st_size
            except Exception:
                necesita_copia = True

        if necesita_copia:
            if not origen.exists():
                if destino.exists():
                    return destino          # copia en cache: modo offline
                raise BDError(f"Ficha no disponible en la BD: {ruta_rel}")
            shutil.copy2(origen, destino)
            self.limpiar_cache_si_excede()
        return destino

    def tamano_cache(self):
        total = 0
        for root, _dirs, files in os.walk(self.cache_dir):
            for nombre in files:
                if nombre in ("indice_cache.json", "pendientes.json", "rest_state.json",
                              "indice_base.json"):
                    continue
                try:
                    total += (Path(root) / nombre).stat().st_size
                except Exception:
                    pass
        return total

    def limpiar_cache_si_excede(self, max_bytes=CACHE_MAX_BYTES):
        """Si el cache supera ``max_bytes``, borra los PDFs mas antiguos (FIFO)
        hasta quedar por debajo. Devuelve la cantidad de archivos borrados."""
        protegidos = {"indice_cache.json", "pendientes.json", "rest_state.json",
                      "indice_base.json"}
        archivos = []
        for root, _dirs, files in os.walk(self.cache_dir):
            for nombre in files:
                if nombre in protegidos:
                    continue
                p = Path(root) / nombre
                try:
                    st = p.stat()
                    archivos.append((p, st.st_mtime, st.st_size))
                except Exception:
                    pass
        total = sum(a[2] for a in archivos)
        if total <= max_bytes:
            return 0
        archivos.sort(key=lambda a: a[1])  # mas antiguos primero
        borrados = 0
        for p, _mtime, size in archivos:
            if total <= max_bytes:
                break
            try:
                p.unlink()
                total -= size
                borrados += 1
            except Exception:
                pass
        self.cfg.setdefault("cache", {})["ultima_limpieza"] = ahora_iso()
        return borrados

    # =====================================================================
    # SUBMITTALS / PROYECTOS
    # =====================================================================
    def carpeta_proyecto(self, nombre_proyecto):
        return self.proyectos_dir / sanitizar_nombre(nombre_proyecto)

    def guardar_submittal(self, proyecto, destino=None):
        """Guarda ``submittal_proyecto.json`` en la BD (metadatos) y, si se
        indica, tambien en la carpeta de entregables.

        Solo se versionan los METADATOS: las caratulas, los CMP y los Excel se
        quedan en la carpeta local del usuario y se regeneran cuando hace falta.
        Versionarlos haria crecer el repositorio cientos de MB por proyecto.
        """
        proyecto.setdefault("id_proyecto", _nuevo_id())
        proyecto.setdefault("fecha_creacion", datetime.now().strftime("%Y-%m-%d"))
        proyecto["ultima_actualizacion"] = ahora_iso()
        proyecto["actualizado_por"] = socket.gethostname()

        carpeta = self.carpeta_proyecto(proyecto.get("nombre_proyecto", "Proyecto"))
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / NOMBRE_SUBMITTAL_JSON).write_text(
            json.dumps(proyecto, ensure_ascii=False, indent=2), encoding="utf-8")
        self.marcar_pendiente(f"{NOMBRE_PROYECTOS}/{carpeta.name}/{NOMBRE_SUBMITTAL_JSON}")
        if destino:
            Path(destino).mkdir(parents=True, exist_ok=True)
            (Path(destino) / NOMBRE_SUBMITTAL_JSON).write_text(
                json.dumps(proyecto, ensure_ascii=False, indent=2), encoding="utf-8")
        return carpeta / NOMBRE_SUBMITTAL_JSON

    @staticmethod
    def cargar_submittal(carpeta):
        """Carga ``submittal_proyecto.json`` de una carpeta."""
        p = Path(carpeta) / NOMBRE_SUBMITTAL_JSON
        if not p.exists():
            raise BDError(f"No se encontro {NOMBRE_SUBMITTAL_JSON} en {carpeta}")
        return json.loads(p.read_text(encoding="utf-8"))

    def listar_proyectos(self):
        """Proyectos guardados en la BD (para abrir uno existente sin buscar la
        carpeta a mano)."""
        salida = []
        if not self.proyectos_dir.is_dir():
            return salida
        for sub in sorted(self.proyectos_dir.iterdir()):
            p = sub / NOMBRE_SUBMITTAL_JSON
            if not p.exists():
                continue
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            salida.append({
                "nombre_proyecto": d.get("nombre_proyecto", sub.name),
                "carpeta_bd": str(sub),
                "ruta_entregables": d.get("ruta_entregables", ""),
                "ultima_actualizacion": d.get("ultima_actualizacion", ""),
                "materiales": len(d.get("materiales_seleccionados", [])),
            })
        salida.sort(key=lambda x: x.get("ultima_actualizacion", ""), reverse=True)
        return salida

    def validar_proyecto(self, proyecto):
        """Valida un submittal antes de generar entregables.

        Devuelve ``(ok, errores)``.
        """
        errores = []
        materiales = proyecto.get("materiales_seleccionados", [])
        if not materiales:
            errores.append("El submittal no tiene materiales (minimo 1).")

        datos = proyecto.get("datos_procedimiento", {})
        faltan = [c for c in CAMPOS_PROCEDIMIENTO if not str(datos.get(c, "")).strip()]
        if faltan:
            errores.append("Faltan datos del proyecto: " + ", ".join(faltan))

        activas = {f["id"] for f in self.listar_fichas()}
        for m in materiales:
            fid = m.get("id_ficha_bd")
            if fid not in activas:
                errores.append(
                    f"Ficha no disponible/activa en BD para {m.get('consecutivo', '?')} "
                    f"- {m.get('nombre_material', '?')}")
        return (len(errores) == 0, errores)

    def construir_datos_materiales(self, proyecto, destino):
        """Construye el dict ``datos_materiales.json`` (esquema v2.6) que
        alimenta ``generate_caratulas.process_material``."""
        materiales = []
        fichas_idx = {f["id"]: f for f in self.listar_fichas()}
        for m in proyecto.get("materiales_seleccionados", []):
            ficha = fichas_idx.get(m.get("id_ficha_bd"), {})
            cons = m.get("consecutivo", "")
            cat = str(m.get("categoria") or ficha.get("categoria", "")).upper()
            carpeta_madre = CATEGORIAS.get(cat, cat)
            nombre = m.get("nombre_material") or ficha.get("nombre_material", "")
            marcas = _marcas_material(m, ficha)
            ruta_carpeta = str(Path(destino) / carpeta_madre /
                               (sanitizar_nombre(f"{cons}-{nombre}")))
            materiales.append({
                "consecutivo": cons,
                "nombre": nombre,
                "categoria": cat,
                "marca": marcas or "POR DEFINIR",
                "descripcion": ficha.get("descripcion_corta", ""),
                "normativa": ficha.get("normativa", "SIN ESPECIFICAR"),
                "aspectos_adicionales": (_texto_aspectos(m, ficha)
                                        or ficha.get("aspectos_adicionales", "")),
                "documentos_encontrados": [Path(ficha.get("ruta_pdf", "")).name] if ficha else [],
                "compilado_generado": None,
                "estado": "FICHA_DISPONIBLE",
                "carpeta_vacia": False,
                "ruta_carpeta": ruta_carpeta,
            })
        materiales.sort(key=lambda x: _clave_orden(x["consecutivo"]))
        return {
            "resumen": {"total": len(materiales),
                        "fichas_disponibles": len(materiales)},
            "materiales": materiales,
        }

    def materializar_proyecto(self, proyecto, destino):
        """Prepara la carpeta ``destino``: arbol de carpetas, copia de los PDFs
        de las fichas (desde el cache local) y los JSON de trabajo."""
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        data = self.construir_datos_materiales(proyecto, destino)
        fichas_idx = {f["id"]: f for f in self.listar_fichas()}

        # Se empareja por CONSECUTIVO, no por posicion: ``data["materiales"]``
        # viene ordenado y ``materiales_seleccionados`` no necesariamente (un JSON
        # editado a mano bastaba para copiar el PDF a la carpeta de otro material).
        por_consecutivo = {str(m.get("consecutivo", "")): m
                           for m in proyecto.get("materiales_seleccionados", [])}
        for mat in data["materiales"]:
            carpeta = Path(mat["ruta_carpeta"])
            carpeta.mkdir(parents=True, exist_ok=True)
            m = por_consecutivo.get(str(mat.get("consecutivo", "")), {})
            ficha = fichas_idx.get(m.get("id_ficha_bd"))
            if ficha:
                try:
                    pdf_local = self.ruta_local_ficha(ficha)
                    shutil.copy2(pdf_local, carpeta / Path(ficha["ruta_pdf"]).name)
                except Exception as e:
                    self.log.error("No se pudo copiar ficha %s: %s", mat.get("consecutivo"), e)

        json_path = destino / "datos_materiales.json"
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        proyecto["ruta_entregables"] = str(destino)
        self.guardar_submittal(proyecto, destino=destino)
        return json_path


# --------------------------------------------------------------------------
# HELPERS DE MODULO
# --------------------------------------------------------------------------
def _nuevo_id():
    import uuid
    return str(uuid.uuid4())


def _clave_orden(consec):
    """Ordena consecutivos tipo ARQ01, ESTR02... por categoria y numero."""
    orden = {"ARQ": 0, "ESTR": 1, "MEC": 2, "ELEC": 3}
    m = re.match(r"([A-Za-z]+)(\d+)", str(consec or ""))
    if not m:
        return (99, 0)
    return (orden.get(m.group(1).upper(), 98), int(m.group(2)))


def _marcas_material(material, ficha):
    """Marca principal + marcas alternativas separadas por ' / ' (formato v2.6)."""
    marcas = []
    principal = material.get("marca") or ficha.get("marca", "")
    if principal:
        marcas.append(str(principal).strip())
    for alt in material.get("marcas_alternativas", []) or []:
        alt = str(alt).strip()
        if alt and alt not in marcas:
            marcas.append(alt)
    return " / ".join(marcas)


def _texto_aspectos(material, ficha):
    """Texto de 'aspectos_adicionales' cuando hay marcas alternativas
    justificadas por stock (plantilla 'MISMA_FAMILIA_DISTINTA_MARCA' de v2.6)."""
    alternativas = material.get("marcas_alternativas", []) or []
    if material.get("justificacion_stock") and alternativas:
        n = 1 + len(alternativas)
        return (
            f"Se adjuntan {n} fichas tecnicas de distintas marcas comerciales que "
            "corresponden al mismo tipo de producto. Debido a posibles limitaciones "
            f"de existencias en el mercado, se solicita la aprobacion de las {n} marcas "
            "incluidas en este submittal, de manera que, ante una eventual falta de "
            "stock de alguna de ellas al momento de la instalacion, se cuente con la "
            "aprobacion previa para emplear cualquiera de las marcas alternativas aqui "
            "presentadas, garantizando en todos los casos el cumplimiento de los "
            "estandares de calidad y seguridad requeridos para la obra."
        )
    return ""


# --------------------------------------------------------------------------
# CLI: inicializar / diagnosticar la BD sin abrir la GUI
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Utilidades de la BD de submittals")
    ap.add_argument("--token", help="Guardar el PAT de GitHub en la config local")
    ap.add_argument("--repo", help="Cambiar el repositorio (usuario/repo)")
    ap.add_argument("--sync", action="store_true", help="Sincronizar y validar el indice")
    ap.add_argument("--estado", action="store_true", help="Mostrar el estado")
    ap.add_argument("--migrar-nombres", action="store_true",
                    help="Generar nombre_ficha en las fichas que no lo tengan")
    a = ap.parse_args()

    cfg = cargar_config()
    if a.repo:
        cfg.setdefault("github", {})["repo"] = a.repo
        guardar_config(cfg)
        print("repo:", a.repo)
    if a.token:
        guardar_token_github(a.token, cfg)
        print("Token guardado en", dir_appdata() / "config.json")

    m = BDManager()
    print("backend:", m.git_status().get("backend"), "| BD:", m.bd_root)
    if a.sync:
        data, resumen = m.sync_indice()
        print("resumen:", json.dumps(resumen, ensure_ascii=False, indent=2))
        print("fichas:", len(data.get("fichas", [])))
    if a.migrar_nombres:
        n = m.migrar_nombres_ficha()
        print(f"nombres generados: {n}")
        for f in m.listar_fichas(incluir_inactivas=True):
            print("  -", m.nombre_de(f))
    if a.estado or not (a.sync or a.token or a.repo):
        print(json.dumps(m.git_status(), ensure_ascii=False, indent=2))
        print(m.texto_estado_sync())
