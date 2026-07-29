#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 fuzzy_search.py  --  Busqueda con tolerancia (Generador de Submittals ES v3)
================================================================================
Busqueda "fuzzy" (tolerante a errores de tipeo, orden de palabras y acentos)
sobre el campo ``search_keywords`` de las fichas de la Base de Datos.

Reglas de negocio (v3.3.3):
  - Similitud minima aceptada: 40 % (``UMBRAL_MINIMO = 0.4``).
  - Devuelve como maximo los 12 mejores resultados (``TOP_N = 12``), ordenados
    de mayor a menor similitud.
  - Filtros opcionales por ``categoria`` (ARQ/ESTR/MEC/ELEC) y por ``marca``.
  - Solo considera fichas con ``estado == "activo"`` (las de soft-delete se
    ignoran).

No usa dependencias externas: solo la biblioteca estandar (``difflib``,
``unicodedata``). Asi el modulo puede probarse de forma aislada y es liviano.
================================================================================
"""

import re
import unicodedata
from difflib import SequenceMatcher

# --------------------------------------------------------------------------
# CONSTANTES DE NEGOCIO
# --------------------------------------------------------------------------
UMBRAL_MINIMO = 0.4   # 40 % de similitud minima para aparecer en resultados
TOP_N = 12            # maximo de sugerencias devueltas
ESTADO_ACTIVO = "activo"

# Umbral por token: un token de la consulta cuenta como "coincidencia real" solo
# si es igual/subcadena de una palabra clave, o si su parecido supera este valor.
# Evita falsos positivos entre palabras cortas parecidas (p.ej. "cemento" vs
# "metalco", que SequenceMatcher puntua ~0.57 pero NO son el mismo material).
# Bajado de 0.8 a 0.72 (v3.3.3) para tolerar mas errores de tipeo reales
# ("estrucutral" ~0.94, "cocreto" ~0.86) sin cruzar el falso positivo de arriba.
PER_TOKEN_GATE = 0.72


# --------------------------------------------------------------------------
# NORMALIZACION DE TEXTO
# --------------------------------------------------------------------------
def normalizar(texto):
    """Normaliza un texto para comparar: minusculas, sin acentos, sin signos
    y con los espacios colapsados.

    Ej: ``"Tubo  Estructural 150x100"`` -> ``"tubo estructural 150x100"``.
    """
    if texto is None:
        return ""
    s = str(texto).lower().strip()
    # Quitar acentos/diacriticos (NFD + descartar marcas de combinacion).
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Cambiar cualquier separador no alfanumerico por espacio.
    s = re.sub(r"[^0-9a-z]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenizar(texto):
    """Devuelve la lista de tokens (palabras/numeros) de un texto normalizado."""
    n = normalizar(texto)
    return n.split() if n else []


# --------------------------------------------------------------------------
# PUNTAJE DE SIMILITUD
# --------------------------------------------------------------------------
def _ratio(a, b):
    """Similitud 0..1 entre dos cadenas (SequenceMatcher)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _match_token(qt, kt):
    """Fuerza de coincidencia (0..1) entre un token de la consulta ``qt`` y un
    token candidato ``kt``, con guardas de longitud para no dar match total a
    tokens basura.

    Historia del bug (v3.3.7 y antes): se usaba ``qt in kt or kt in qt`` sin
    guardas. Un token corto del candidato ("e", "x", un digito suelto) es
    subcadena de casi cualquier consulta, asi que ``kt in qt`` daba 1.0 y toda
    ficha puntuaba 100% -- el buscador devolvia tubos al buscar "interruptor".

    Reglas (de mas a menos fuerte):
      * igual                       -> 1.00
      * uno prefijo del otro        -> 0.92  (buscar "inter" encuentra
                                              "interruptor"; requiere >= 2 chars)
      * ``qt`` subcadena de ``kt``  -> 0.80  (requiere qt >= 3 chars)
      * ratio de similitud >= gate  -> el ratio (tolera errores de tipeo)
      * si no                        -> 0.0
    """
    if not qt or not kt:
        return 0.0
    if qt == kt:
        return 1.0
    # Prefijo: el token mas corto debe tener >= 3 chars. Sin este piso, un
    # token de 1 letra ("a", "e", "x") era prefijo de casi cualquier consulta
    # ("apagador".startswith("a")) y daba match casi total contra fichas sin
    # relacion.
    if min(len(qt), len(kt)) >= 3 and (kt.startswith(qt) or qt.startswith(kt)):
        return 0.92
    if len(qt) >= 3 and qt in kt:
        return 0.80
    r = _ratio(qt, kt)
    return r if r >= PER_TOKEN_GATE else 0.0


def puntuar(query, texto):
    """Similitud (0..1) entre la consulta y un texto candidato (el
    ``search_keywords`` de la ficha, o un campo suelto como el nombre).

    Estrategia (pensada para que la MEJOR coincidencia quede de primera):
      1. *Cobertura de tokens*: promedio, sobre los tokens de la consulta, de
         la mejor fuerza de coincidencia (``_match_token``) contra los tokens
         del candidato. Un token de la consulta sin ninguna coincidencia real
         aporta 0, asi que "interruptor" ya NO puntua contra un tubo.
      2. *Bonus de frase* (desempata y sube la coincidencia literal): si el
         texto es exactamente la consulta, empieza con ella, o la contiene como
         subcadena contigua, se suma un extra. Asi "tubo 150" prioriza el que
         dice literalmente "tubo 150" sobre uno que solo comparte tokens.
    """
    q_norm = normalizar(query)
    k_norm = normalizar(texto)
    if not q_norm or not k_norm:
        return 0.0

    q_tokens = q_norm.split()
    k_tokens = k_norm.split()
    if not q_tokens or not k_tokens:
        return 0.0

    suma_mejor = sum(max((_match_token(qt, kt) for kt in k_tokens), default=0.0)
                     for qt in q_tokens)
    cobertura = suma_mejor / len(q_tokens)

    if k_norm == q_norm:
        bonus = 0.30
    elif k_norm.startswith(q_norm):
        bonus = 0.20
    elif q_norm in k_norm:
        bonus = 0.12
    else:
        bonus = 0.0

    return min(1.0, cobertura * 0.85 + bonus)


# --------------------------------------------------------------------------
# BUSQUEDA
# --------------------------------------------------------------------------
# Campos contra los que se puntua la consulta, con su peso. El nombre y el
# material pesan mas que las palabras clave crudas: asi el que dice literalmente
# lo buscado en su nombre queda de primero, no uno que solo lo tiene enterrado
# en keywords. La puntuacion final de la ficha es el MAXIMO ponderado entre
# campos (basta con que UN campo coincida fuerte).
_CAMPOS_PUNTAJE = (
    ("nombre_ficha", 1.00),
    ("nombre_material", 1.00),
    ("marca", 0.95),
    ("sinonimos", 0.95),
    ("tipo_producto", 0.85),
    ("especificacion", 0.85),
    ("dimensiones", 0.80),
    ("search_keywords", 0.75),
)


def _puntaje_ficha(query, ficha):
    """Mejor puntaje ponderado de la consulta contra los campos de la ficha."""
    mejor = 0.0
    for campo, peso in _CAMPOS_PUNTAJE:
        val = ficha.get(campo)
        if not val:
            continue
        s = puntuar(query, val) * peso
        if s > mejor:
            mejor = s
    return mejor


def _pasa_filtro(ficha, campos, texto):
    """True si ``texto`` (normalizado, por tokens) esta contenido en alguno de
    los ``campos`` de la ficha. Filtro literal tolerante (sin acentos, sin
    importar el orden), usado por los filtros de marca / modelo / nombre."""
    if not texto:
        return True
    objetivo = " ".join(normalizar(ficha.get(c, "")) for c in campos)
    return all(tok in objetivo for tok in normalizar(texto).split())


def buscar(query, fichas, categoria=None, marca=None, modelo=None, nombre=None,
           umbral=UMBRAL_MINIMO, top_n=TOP_N, incluir_inactivas=False):
    """Busca ``query`` dentro de una lista de fichas (dicts del indice).

    Parametros
    ----------
    query : str
        Texto a buscar (p. ej. ``"tubo 150"``). Si viene vacio pero hay algun
        filtro (categoria/marca/modelo/nombre), se listan TODAS las fichas que
        pasan los filtros (sin puntuar), ordenadas por nombre -- util para
        explorar el catalogo aplicando solo filtros.
    fichas : list[dict]
        Fichas del indice.
    categoria : str | None
        Filtra por categoria exacta (ARQ/ESTR/MEC/ELEC).
    marca : str | None
        Filtra por marca (subcadena tolerante).
    modelo : str | None
        Filtra por modelo/especificacion/tipo/dimensiones (subcadena tolerante).
    nombre : str | None
        Filtra por nombre de la ficha / material (subcadena tolerante).
    umbral : float
        Similitud minima para aparecer cuando hay texto de busqueda.
    top_n : int
        Maximo de resultados.
    incluir_inactivas : bool
        Si ``False`` (defecto) ignora fichas con ``estado != "activo"``.

    Retorna
    -------
    list[dict]
        Copias de las fichas que pasan, ordenadas de mayor a menor coincidencia
        (y, a igual puntaje, nombre mas corto/especifico primero). Cada una
        trae ``_similitud`` (float). Con consulta vacia, ``_similitud`` va en 0.
    """
    cat = (categoria or "").strip().upper() or None
    q = str(query or "").strip()

    def _filtros_ok(ficha):
        if not incluir_inactivas and ficha.get("estado", ESTADO_ACTIVO) != ESTADO_ACTIVO:
            return False
        if cat and str(ficha.get("categoria", "")).strip().upper() != cat:
            return False
        if not _pasa_filtro(ficha, ("marca",), marca):
            return False
        if not _pasa_filtro(ficha, ("especificacion", "tipo_producto", "dimensiones",
                                    "nombre_ficha", "nombre_material"), modelo):
            return False
        if not _pasa_filtro(ficha, ("nombre_ficha", "nombre_material"), nombre):
            return False
        return True

    candidatas = [f for f in (fichas or []) if _filtros_ok(f)]

    # Sin texto de busqueda: se listan todas las que pasan filtros, por nombre.
    if not q:
        candidatas.sort(key=lambda f: normalizar(f.get("nombre_ficha") or f.get("nombre_material", "")))
        salida = []
        for f in candidatas[:top_n]:
            item = dict(f)
            item["_similitud"] = 0.0
            salida.append(item)
        return salida

    resultados = []
    for ficha in candidatas:
        score = _puntaje_ficha(q, ficha)
        if score >= umbral:
            item = dict(ficha)
            item["_similitud"] = round(score, 4)
            resultados.append(item)

    # Orden: mayor puntaje primero; a igual puntaje, nombre mas corto (mas
    # especifico) y luego alfabetico -- desempate estable y predecible.
    resultados.sort(key=lambda f: (
        -f["_similitud"],
        len(normalizar(f.get("nombre_ficha") or f.get("nombre_material", ""))),
        normalizar(f.get("nombre_ficha") or f.get("nombre_material", "")),
    ))
    return resultados[:top_n]


# --------------------------------------------------------------------------
# GENERACION DE search_keywords
# --------------------------------------------------------------------------
def generar_search_keywords(ficha):
    """Construye el string ``search_keywords`` a partir de los campos de una
    ficha. Concatena los campos relevantes, los normaliza y elimina tokens
    duplicados conservando el orden.

    Campos usados: nombre_ficha, nombre_material, marca, categoria,
    tipo_producto, dimensiones, especificacion, normativa, descripcion_corta,
    sinonimos.

    ``nombre_ficha`` (v3.2.0) va primero para que el nombre descriptivo completo
    sea buscable: quien busca "tubo 8" debe encontrar
    ``TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup``.

    ``sinonimos`` (v3.3.7) es texto libre que el usuario escribe al cargar o
    editar la ficha (ej: "apagador, breaker" para un interruptor), para que
    la busqueda encuentre la ficha por un nombre distinto al tecnico.
    """
    campos = [
        ficha.get("nombre_ficha", ""),
        ficha.get("nombre_material", ""),
        ficha.get("marca", ""),
        ficha.get("categoria", ""),
        ficha.get("tipo_producto", ""),
        ficha.get("dimensiones", ""),
        ficha.get("especificacion", ""),
        ficha.get("normativa", ""),
        ficha.get("descripcion_corta", ""),
        ficha.get("sinonimos", ""),
    ]
    tokens = []
    vistos = set()
    for campo in campos:
        for tok in tokenizar(campo):
            if tok not in vistos:
                vistos.add(tok)
                tokens.append(tok)
    return " ".join(tokens)


if __name__ == "__main__":
    # Demostracion rapida
    demo = [
        {"nombre_material": "Tubo Estructural 150x100x1.5", "marca": "MultiGroup",
         "categoria": "ESTR", "dimensiones": "150x100x1.5", "normativa": "ASTM A500M",
         "search_keywords": "tubo estructural 150x100x1.5 multigroup astm a500m", "estado": "activo"},
        {"nombre_material": "Tubo Estructural 152x100x1.5", "marca": "Metalco",
         "categoria": "ESTR", "search_keywords": "tubo estructural 152x100x1.5 metalco", "estado": "activo"},
        {"nombre_material": "Cemento", "marca": "Holcim", "categoria": "ESTR",
         "search_keywords": "cemento holcim hidraulico", "estado": "activo"},
    ]
    for r in buscar("tubo 150", demo):
        print(f"{r['_similitud']:.2f}  {r['nombre_material']} ({r['marca']})")
