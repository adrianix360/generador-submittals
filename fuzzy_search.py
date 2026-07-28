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


def puntuar(query, search_keywords):
    """Calcula la similitud (0..1) entre la consulta y los ``search_keywords``
    de una ficha.

    Estrategia:
      1. *Cobertura de tokens* (senal principal): fraccion de tokens de la
         consulta que tienen una coincidencia REAL con alguna palabra clave.
         Cuenta como real si el token es igual/subcadena de una palabra o si su
         parecido supera ``PER_TOKEN_GATE`` (0.8). Esto evita que palabras
         cortas casi-anagramas ("cemento" vs "metalco") se cuelen como match.
      2. *Parecido promedio y global* (senal secundaria, para ordenar): mejor
         ratio promedio por token y SequenceMatcher sobre las cadenas completas.

    Resultado final = 0.8 * cobertura + 0.2 * max(promedio, global). Asi una
    consulta corta cuyos tokens aparecen todos ("tubo 150") puntua ~1.0, y una
    consulta sin coincidencias reales queda muy por debajo del umbral.
    """
    q_norm = normalizar(query)
    k_norm = normalizar(search_keywords)
    if not q_norm or not k_norm:
        return 0.0

    q_tokens = q_norm.split()
    k_tokens = k_norm.split()
    if not q_tokens or not k_tokens:
        return 0.0

    coincidencias = 0
    suma_mejor = 0.0
    for qt in q_tokens:
        mejor = 0.0
        for kt in k_tokens:
            if qt == kt or qt in kt or kt in qt:
                mejor = 1.0
                break
            r = _ratio(qt, kt)
            if r > mejor:
                mejor = r
        suma_mejor += mejor
        if mejor >= PER_TOKEN_GATE:
            coincidencias += 1

    cobertura = coincidencias / len(q_tokens)
    promedio = suma_mejor / len(q_tokens)
    global_score = _ratio(q_norm, k_norm)

    return cobertura * 0.8 + max(promedio, global_score) * 0.2


# --------------------------------------------------------------------------
# BUSQUEDA
# --------------------------------------------------------------------------
def buscar(query, fichas, categoria=None, marca=None,
           umbral=UMBRAL_MINIMO, top_n=TOP_N, incluir_inactivas=False):
    """Busca ``query`` dentro de una lista de fichas (dicts del indice).

    Parametros
    ----------
    query : str
        Texto a buscar (p. ej. ``"tubo 150"``).
    fichas : list[dict]
        Fichas del indice; cada una debe tener ``search_keywords`` y, para el
        filtrado, ``categoria`` / ``marca`` / ``estado``.
    categoria : str | None
        Si se indica, solo devuelve fichas de esa categoria (ARQ/ESTR/...).
    marca : str | None
        Si se indica, solo devuelve fichas cuya marca contenga ese texto
        (comparacion tolerante).
    umbral : float
        Similitud minima (por defecto 0.5 = 50 %).
    top_n : int
        Maximo de resultados (por defecto 5).
    incluir_inactivas : bool
        Si ``False`` (defecto) ignora fichas con ``estado != "activo"``.

    Retorna
    -------
    list[dict]
        Lista de resultados ordenada de mayor a menor similitud. Cada elemento
        es la ficha original con una clave adicional ``_similitud`` (float).
    """
    if not query or not str(query).strip():
        return []

    cat = (categoria or "").strip().upper() or None
    marca_norm = normalizar(marca) if marca else None

    resultados = []
    for ficha in fichas or []:
        if not incluir_inactivas and ficha.get("estado", ESTADO_ACTIVO) != ESTADO_ACTIVO:
            continue
        if cat and str(ficha.get("categoria", "")).strip().upper() != cat:
            continue
        if marca_norm and marca_norm not in normalizar(ficha.get("marca", "")):
            continue

        score = puntuar(query, ficha.get("search_keywords", ""))
        if score >= umbral:
            item = dict(ficha)
            item["_similitud"] = round(score, 4)
            resultados.append(item)

    resultados.sort(key=lambda f: f["_similitud"], reverse=True)
    return resultados[:top_n]


# --------------------------------------------------------------------------
# GENERACION DE search_keywords
# --------------------------------------------------------------------------
def generar_search_keywords(ficha):
    """Construye el string ``search_keywords`` a partir de los campos de una
    ficha. Concatena los campos relevantes, los normaliza y elimina tokens
    duplicados conservando el orden.

    Campos usados: nombre_ficha, nombre_material, marca, categoria,
    tipo_producto, dimensiones, especificacion, normativa, descripcion_corta.

    ``nombre_ficha`` (v3.2.0) va primero para que el nombre descriptivo completo
    sea buscable: quien busca "tubo 8" debe encontrar
    ``TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup``.
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
