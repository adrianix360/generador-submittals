#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 nomenclatura.py  --  Nombres descriptivos y unicos de fichas tecnicas (v3.2.0)
================================================================================
Problema que resuelve: nombres como "Tuberia Estructural" o
"TUBO RECTANGULAR e INDUSTRIAL" no permiten saber QUE ficha es cual.

CRITERIO DE DISENO (definido por el usuario):
    "Lo importante es que una persona con bajo conocimiento tecnico logre
     distinguir que material es."

De ahi salen las reglas, que son distintas segun la FAMILIA del material:

  TUBOS Y PERFILES      -> forma + dimensiones + calibre
      TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup
      TUBO ESTRUCTURAL RECTANGULAR 6" x 2" CH 13 - MultiGroup

  ACABADOS POR AREA     -> dimensiones + unidad
      CERAMICA PORCELANATO 60 x 60 cm - Porcelanato Plus

  AGREGADOS Y COMUNES   -> presentacion (lo que se compra)
      CEMENTO HIDRAULICO SACO 50 kg - Holcim
      PINTURA ACRILICA BLANCO CUBETA 5 gal - Sur

  ELECTRICOS            -> tipo y/o modelo
      BREAKER TERMOMAGNETICO 2P 60 A QO260 - Schneider
      CABLE THHN #12 AWG - Viakon

  MECANICOS             -> diametro + designacion
      TUBERIA PVC SDR 26 4" - Amanco

--------------------------------------------------------------------------------
DOS REGLAS QUE SE APARTAN DEL PLAN ORIGINAL (y por que)
--------------------------------------------------------------------------------
1. La NORMATIVA no entra en el nombre. El plan original la incluia en un ejemplo
   ("TUBERIA DE ACERO ASTM A53") y la omitia en otro ("TUBO ESTRUCTURAL CUADRADO
   8x8x3/16", que tiene ASTM A500M). Se resolvio por indicacion del usuario: las
   normas formales (ASTM, ISO, INTE, ANSI, DIN, NFPA, UL...) se quedan en su
   campo y en la busqueda, no en el nombre; no ayudan a alguien sin formacion
   tecnica a distinguir el material.
   SI entran las DESIGNACIONES DE PRODUCTO (CH 13, SDR 26, SCH 40, #12 AWG,
   60 A, 2P...), porque son justamente lo que distingue una ficha de otra.

2. Las unidades no se inventan: se conserva la que traiga la ficha. Si el origen
   no dice unidad, se escriben los numeros solos. Excepcion razonable: un valor
   con fraccion de pulgada tipica (3/16, 1/2, 1 1/4...) implica pulgadas.
   Convencion de escritura: la pulgada se repite en cada medida
   (8" x 8" x 3/16") y las unidades con letras se escriben una sola vez al final
   (60 x 60 cm), que es como se leen en obra.

Solo biblioteca estandar. Importable y probable de forma aislada.
================================================================================
"""

import re
import math
import unicodedata
from fractions import Fraction

VERSION = "3.2.0"

# --------------------------------------------------------------------------
# VOCABULARIO
# --------------------------------------------------------------------------
# Normas formales: NO van en el nombre (ver nota 1 del encabezado).
# OJO: "EN" y "BS" quedan FUERA de la lista a proposito. "EN" es la preposicion
# mas comun del espanol y borraba texto util: "disponible en 12 AWG" se quedaba
# sin el calibre. El costo de no reconocer la norma europea EN es mucho menor que
# el de mutilar la descripcion.
NORMATIVAS = (
    "ASTM", "ISO", "INTE", "ANSI", "DIN", "NFPA", "UL", "AWWA", "ACI", "AISI",
    "NTC", "COVENIN", "NOM", "ASME", "API", "JIS", "SSPC", "NEMA",
)
RE_NORMATIVA = re.compile(
    r"\b(?:" + "|".join(NORMATIVAS) + r")\s*[-/]?\s*[A-Z]?\d+[A-Za-z0-9./-]*\b", re.I)

# Formas de perfileria (aparecen en descripcion_corta o tipo_producto).
FORMAS = {
    "cuadrado": "CUADRADO", "cuadrada": "CUADRADO",
    "rectangular": "RECTANGULAR", "rectangulo": "RECTANGULAR",
    "redondo": "REDONDO", "redonda": "REDONDO", "circular": "REDONDO",
    "ovalado": "OVALADO", "hexagonal": "HEXAGONAL",
}

# Palabras que indican familia (se buscan normalizadas, sin acentos).
PISTAS_TUBO = ("tubo", "tuberia", "perfil", "perling", "angular", "canal",
               "viga", "varilla", "platina", "lamina", "malla", "cercha")
PISTAS_AREA = ("ceramica", "porcelanato", "piso", "azulejo", "enchape",
               "baldosa", "laminado", "alfombra", "cielo", "gypsum", "panel")
PISTAS_AGREGADO = ("cemento", "mortero", "concreto", "arena", "piedra", "lastre",
                   "cal", "yeso", "pintura", "sellador", "adhesivo", "bondex",
                   "fragua", "aditivo", "impermeabilizante", "diluyente",
                   "thinner", "barniz", "esmalte")
PISTAS_ELEC = ("cable", "breaker", "disyuntor", "interruptor", "tomacorriente",
               "luminaria", "lampara", "led", "tablero", "panel electrico",
               "conduit", "canaleta", "transformador", "contactor", "sensor",
               "apagador", "bombillo", "reflector")
# "unidad", "toma" y "aire" quedan fuera: son demasiado comunes en prosa
# ("precio por unidad", "toma en cuenta", "al aire libre") y arrastraban fichas
# a la familia equivocada.
PISTAS_MEC = ("valvula", "bomba", "aire acondicionado", "ducto", "difusor",
              "rejilla", "condensador", "evaporador", "compresor", "termostato",
              "sifon", "trampa", "extractor", "inodoro", "lavatorio")

FAMILIA_TUBO = "tubo_perfil"
FAMILIA_AREA = "acabado_area"
FAMILIA_AGREGADO = "agregado"
FAMILIA_ELEC = "electrico"
FAMILIA_MEC = "mecanico"
FAMILIA_GENERICA = "generico"

# Presentacion comercial (lo que se compra): "SACO 50 kg", "CUBETA 5 gal"...
ENVASES = {
    "saco": "SACO", "sacos": "SACO", "bolsa": "BOLSA", "bolsas": "BOLSA",
    "cubeta": "CUBETA", "cubetas": "CUBETA", "balde": "BALDE",
    "galon": "GALON", "galones": "GALON", "gal": "GALON",
    "tarro": "TARRO", "lata": "LATA", "rollo": "ROLLO", "rollos": "ROLLO",
    "caja": "CAJA", "paleta": "PALETA", "tonel": "TONEL", "estanon": "ESTANON",
    "barra": "BARRA", "unidad": "UNIDAD", "juego": "JUEGO", "par": "PAR",
}
UNIDADES_MEDIDA = {
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogramos": "kg",
    "lb": "lb", "lbs": "lb", "libras": "lb", "g": "g", "gr": "g",
    "l": "L", "lt": "L", "lts": "L", "litro": "L", "litros": "L",
    "gal": "gal", "galon": "gal", "galones": "gal", "ml": "ml",
    "m2": "m2", "m3": "m3", "ml2": "m2", "m": "m", "cm": "cm", "mm": "mm",
    "un": "un", "uds": "un", "pzas": "un",
}

# Designaciones de producto: SI van en el nombre.
# Cada entrada es (orden_de_lectura, patron, formato). El orden es como se leen
# en obra: primero polos/amperaje de un electrico, luego calibres y series.
# Los simbolos de una letra (A, V, W, P) exigen MAYUSCULA para no confundir
# "60 a" de una frase con 60 amperios; la forma escrita ("60 amperios") si es
# insensible a mayusculas.
# El guardia ``(?!\s*\d)`` de los amperios evita leer un RANGO como designacion:
# en "espesor de 20 A 30 mm" la "A" es la preposicion, no amperios.
PATRONES_DESIGNACION = (
    (1, re.compile(r"\b(\d)\s*(?:P\b|(?i:polos?)\b)"), lambda m: f"{m.group(1)}P"),
    (2, re.compile(r"\b(\d{1,3})\s*(?:A\b(?!\s*\d)|(?i:amp(?:erios?|s)?)\b)"),
     lambda m: f"{m.group(1)} A"),
    (3, re.compile(r"\b(\d{1,3})\s*(?:V\b(?!\s*\d)|(?i:volt(?:s|ios?)?)\b)"),
     lambda m: f"{m.group(1)} V"),
    (4, re.compile(r"\b(\d{1,4})\s*(?:W\b(?!\s*\d)|(?i:watts?)\b)"),
     lambda m: f"{m.group(1)} W"),
    (5, re.compile(r"\bC\.?H\.?\s*(\d{1,2})\b", re.I), lambda m: f"CH {m.group(1)}"),
    (5, re.compile(r"\bcal(?:ibre)?\.?\s*(\d{1,2})\b", re.I), lambda m: f"CH {m.group(1)}"),
    # Calibre de lamina escrito a la tica: "#26", "# 24".
    (5, re.compile(r"#\s*([12]\d|3[0-2])\b(?!\s*AWG)", re.I), lambda m: f"CH {m.group(1)}"),
    (6, re.compile(r"\bSDR\s*[-]?\s*(\d{1,3})\b", re.I), lambda m: f"SDR {m.group(1)}"),
    (7, re.compile(r"\b(?:SCH|schedule|c[eé]dula)\s*[-]?\s*(\d{1,3})\b", re.I),
     lambda m: f"SCH {m.group(1)}"),
    # AWG admite los calibres gruesos 1/0, 2/0, 4/0 ("cero, dos ceros...").
    (8, re.compile(r"#?\s*(\d{1,2}/0|\d{1,2})\s*AWG\b", re.I),
     lambda m: f"#{m.group(1)} AWG"),
    # 'grado'/'clase' exigen al menos un digito: si no, capturaban la palabra
    # siguiente ("grado de humedad" -> "GRADO DE").
    (9, re.compile(r"\bgrado\s+([A-Z]?\d+[A-Z0-9]{0,3})\b", re.I),
     lambda m: f"GRADO {m.group(1).upper()}"),
    (10, re.compile(r"\bclase\s+([A-Z]?\d+[A-Z0-9]{0,3})\b", re.I),
     lambda m: f"CLASE {m.group(1).upper()}"),
    (11, re.compile(r"\bT\s*(\d)\b(?=.*(?:led|fluor))", re.I), lambda m: f"T{m.group(1)}"),
)

# Codigo de modelo: letras+numeros juntos (QO260, 4RB-2075...). Se pide al menos
# una letra y dos digitos para no confundirlo con una medida.
RE_MODELO = re.compile(r"\b(?=[A-Z0-9-]{4,18}\b)(?=[A-Z0-9-]*\d\d)[A-Z][A-Z0-9-]*\b")

# Unidades que pueden venir pegadas a un numero dentro de una medida.
UNIDAD_DIM = r"(?:\"|''|”|pulg\.?|plg\.?|in\b|mm\b|cm\b|m\b|ø)"
# Un numero de medida. El ORDEN de las alternativas importa: la fraccion va
# primero, si no "3/16" se leeria como "3" (la alternancia de re es perezosa,
# se queda con la primera que calza).
NUM_DIM = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?)"
RE_GRUPO_DIM = re.compile(
    r"(" + NUM_DIM + r")\s*" + UNIDAD_DIM + r"?"
    r"(?:\s*[x×*]\s*" + NUM_DIM + r"\s*" + UNIDAD_DIM + r"?)+", re.I)
RE_MEDIDA_SUELTA = re.compile(
    r"(?:ø|Ø|diam(?:etro)?\.?\s*)\s*(" + NUM_DIM + r")\s*" + UNIDAD_DIM + r"?", re.I)

DENOMINADORES_PULGADA = (2, 4, 8, 16, 32, 64)

# Algunas marcas usan UNA sola ficha tecnica para todo un lineal de productos
# (ej: tubos Amanco, bloques Bloquera PC), sin una medida unica que las
# distinga. "MULTIPLE"/"MULTIPLES" en el campo de dimensiones/medidas se
# acepta como valor valido (cuenta como distintivo) en vez de exigir una
# medida numerica que esa ficha no tiene.
RE_MULTIPLE = re.compile(r"\bmultiples?\b")


# --------------------------------------------------------------------------
# HELPERS DE TEXTO
# --------------------------------------------------------------------------
def sin_acentos(texto):
    s = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def normalizar(texto):
    """Minusculas, sin acentos, sin signos, espacios colapsados."""
    s = sin_acentos(texto).lower()
    s = re.sub(r"[^0-9a-z]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(texto):
    n = normalizar(texto)
    return n.split() if n else []


def _limpiar_conectores(texto):
    """Quita conectores sueltos que ensucian los nombres extraidos por OCR.

    "TUBO RECTANGULAR e INDUSTRIAL" -> "TUBO RECTANGULAR INDUSTRIAL"
    (la "e" es un artefacto de la extraccion, no parte del nombre).
    """
    s = re.sub(r"\s+[eyoóu]\s+", " ", str(texto or ""), flags=re.I)
    s = re.sub(r"\s+(?:de|del|la|el|los|las)\s+(?=\d)", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def quitar_normativas(texto):
    """Elimina las normas formales de un texto (no van en el nombre)."""
    return re.sub(r"\s+", " ", RE_NORMATIVA.sub(" ", str(texto or ""))).strip()


# Calibres escritos pegados al nombre: "LAMINA ESMALTADA #26", "BANDEJA CAL.24".
# Se quitan del nombre base porque ``detectar_designaciones`` los vuelve a poner
# normalizados ("CH 26"); si no, salia "LAMINA ESMALTADA #26 CH 26".
RE_CALIBRE_EN_NOMBRE = re.compile(
    r"\s*(?:#\s*(?:[12]\d|3[0-2])\b(?!\s*AWG)|\bCAL(?:IBRE)?\.?\s*\d{1,2}\b"
    r"|\bC\.H\.?\s*\d{1,2}\b)", re.I)


def quitar_calibre(texto):
    return re.sub(r"\s+", " ", RE_CALIBRE_EN_NOMBRE.sub(" ", str(texto or ""))).strip()


# --------------------------------------------------------------------------
# DIMENSIONES
# --------------------------------------------------------------------------
def decimal_a_fraccion(valor, denominadores=DENOMINADORES_PULGADA, tolerancia=1e-4):
    """0.1875 -> '3/16'. Devuelve ``None`` si no cae en una fraccion tipica.

    Se usa para escribir espesores y medidas en pulgadas como se leen en obra
    (3/16" y no 0.1875").
    """
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    # inf/NaN llegan si el JSON del OCR trae Infinity o NaN (json.loads los
    # acepta): sin este guardia, int(v) lanzaria y el traceback saldria a la cara
    # del usuario en pleno formulario.
    if not math.isfinite(v) or v <= 0:
        return None
    entero = int(v)
    resto = v - entero
    if abs(resto) < tolerancia:
        return str(entero)
    for d in denominadores:
        n = round(resto * d)
        if n and abs(resto - n / d) < tolerancia:
            f = Fraction(n, d)
            frac = f"{f.numerator}/{f.denominator}"
            return f"{entero} {frac}" if entero else frac
    return None


def _es_numero(valor):
    """True si el valor se puede leer como una medida numerica finita."""
    try:
        s = str(valor).strip().replace(",", ".")
        if "/" in s:
            return bool(re.fullmatch(r"\d+(?:\s+\d+)?/\d+", s))
        return math.isfinite(float(s))
    except (TypeError, ValueError):
        return False


def _es_pulgada(unidad):
    return bool(unidad) and unidad.strip().lower() in ('"', "''", "”", "pulg",
                                                       "pulg.", "plg", "plg.", "in")


def _formatear_numero(crudo):
    """Normaliza un numero de medida conservando fracciones ('3/16', '2 1/2')."""
    s = str(crudo).strip().replace(",", ".")
    if "/" in s:
        return re.sub(r"\s+", " ", s)
    try:
        v = float(s)
    except (TypeError, ValueError):
        return s
    if not math.isfinite(v):
        return ""
    if abs(v - int(v)) < 1e-9:
        return str(int(v))
    return ("%g" % v)


def _partes_de_grupo(grupo):
    """Separa '8"x8"x3/16"' en [('8', '\"'), ('8', '\"'), ('3/16', '\"')]."""
    partes = []
    # La X mayuscula tambien separa: los nombres de las fichas suelen venir en
    # mayusculas ("100X100X2 mm"). Sin esto no se detectaba NINGUNA dimension.
    for trozo in re.split(r"[xX×*]", grupo):
        trozo = trozo.strip()
        if not trozo:
            continue
        m = re.match(r"^(" + NUM_DIM + r")\s*(.*)$", trozo)
        if not m:
            continue
        unidad = m.group(2).strip().rstrip(".").lower()
        partes.append((m.group(1), unidad))
    return partes


def formatear_dimensiones(origen):
    """Devuelve las dimensiones escritas de forma legible, o ``""``.

    Acepta:
      * texto libre: ``'8"x8"x3/16"'``, ``'150x100x1.5 mm'``, ``'60x60'``
      * dict (``dimensiones_detectadas``): ``{'ancho': 8, 'largo': 8,
        'espesor': 0.1875}``
      * la palabra ``'MULTIPLE'``/``'MULTIPLES'`` (una ficha para todo un
        lineal de productos, sin medida unica): se devuelve tal cual, en
        mayusculas.

    Convencion: la pulgada se repite en cada medida (``8" x 8" x 3/16"``); las
    unidades con letras se escriben una sola vez al final (``60 x 60 cm``).
    """
    if not origen:
        return ""
    if isinstance(origen, dict):
        return _formatear_dim_dict(origen)
    if RE_MULTIPLE.search(normalizar(origen)):
        return "MULTIPLE"

    texto = str(origen)
    m = RE_GRUPO_DIM.search(texto)
    if not m:
        return _formatear_medida_unica(texto)

    partes = _partes_de_grupo(m.group(0))
    if len(partes) < 2:
        return ""
    unidades = [u for _n, u in partes if u]
    pulgadas = any(_es_pulgada(u) for u in unidades)
    # Una fraccion suelta sin unidad tambien implica pulgadas.
    if not unidades and any("/" in n for n, _u in partes):
        pulgadas = True

    if pulgadas:
        return " x ".join(f'{_formatear_numero(n)}"' for n, _u in partes)

    numeros = " x ".join(_formatear_numero(n) for n, _u in partes)
    if unidades:
        # Unidad comun (la ultima declarada manda: "150x100x1.5 mm").
        unidad = UNIDADES_MEDIDA.get(unidades[-1], unidades[-1])
        return f"{numeros} {unidad}"
    return numeros


def _es_rango(texto):
    """True si el texto describe un RANGO ('de 400 a 500 mm', '20 a 30 mm').

    Un rango no es una dimension: ponerlo en el nombre haria creer que la ficha
    es de la medida mayor.
    """
    return bool(re.search(r"\d+\s*(?:a|hasta)\s+\d+\s*" + UNIDAD_DIM, texto, re.I))


def _formatear_medida_unica(texto):
    """Una sola medida: ``'4"'``, ``'Ø 2 1/2"'``, ``'12 mm'``.

    Se exige unidad explicita (o el prefijo de diametro) a proposito: un numero
    solo, sin unidad, dentro de un texto libre suele ser cualquier cosa menos una
    dimension, y meterlo en el nombre confundiria mas de lo que ayuda.
    """
    if _es_rango(texto):
        return ""
    s = RE_MEDIDA_SUELTA.search(texto)
    if s:
        cola = texto[s.end(1):s.end()].strip().lower().rstrip(".")
        num = _formatear_numero(s.group(1))
        if _es_pulgada(cola) or not cola:
            return f'{num}"'
        return f"{num} {UNIDADES_MEDIDA.get(cola, cola)}"
    m = re.search(r"(?<![\d.,/])(" + NUM_DIM + r")\s*" + UNIDAD_DIM, texto, re.I)
    if not m:
        return ""
    unidad = m.group(0)[len(m.group(1)):].strip().lower().rstrip(".")
    num = _formatear_numero(m.group(1))
    if _es_pulgada(unidad):
        return f'{num}"'
    return f"{num} {UNIDADES_MEDIDA.get(unidad, unidad)}".strip()


def _formatear_dim_dict(d):
    """Formatea el dict ``dimensiones_detectadas``.

    Orden canonico: diametro, ancho, largo/alto, espesor, y luego cualquier otra
    clave. Si algun valor cae en una fraccion tipica de pulgada, se asume que
    todas las medidas estan en pulgadas (ver nota 2 del encabezado).
    """
    # Lista blanca: solo estas claves son medidas. Si se aceptara cualquier clave
    # del dict, un metadato del OCR ("confianza": 0.97) entraria como dimension.
    orden = ("diametro", "ancho", "largo", "alto", "altura", "profundidad",
             "espesor", "calibre")
    claves = [k for k in orden
              if k in d and d[k] not in (None, "", 0) and _es_numero(d[k])]
    if not claves:
        return ""

    unidad = str(d.get("unidad") or d.get("unidades") or "").strip().lower()
    valores = [d[k] for k in claves]

    fracciones = [decimal_a_fraccion(v) for v in valores]
    hay_fraccion = any(f and "/" in f for f in fracciones)
    pulgadas = _es_pulgada(unidad) or (not unidad and hay_fraccion)

    if pulgadas:
        salida = []
        for v, f in zip(valores, fracciones):
            salida.append(f'{f}"' if f else f'{_formatear_numero(v)}"')
        return " x ".join(salida)

    numeros = " x ".join(_formatear_numero(v) for v in valores)
    if unidad:
        return f"{numeros} {UNIDADES_MEDIDA.get(unidad, unidad)}"
    return numeros


# --------------------------------------------------------------------------
# DETECCION DE RASGOS
# --------------------------------------------------------------------------
def detectar_familia(metadata):
    """Familia del material, para saber QUE dato lo distingue."""
    texto = normalizar(" ".join(str(metadata.get(c, "") or "") for c in (
        "nombre_material", "tipo_producto", "descripcion_corta", "especificacion")))
    cat = str(metadata.get("categoria", "")).strip().upper()
    # El nombre del material manda sobre la descripcion: una ficha de tubo que
    # menciona "galvanizado en caliente" es un tubo, no un agregado.
    nombre = normalizar(metadata.get("nombre_material", ""))
    for fuente in (nombre, texto):
        if not fuente:
            continue
        for pistas, familia in ((PISTAS_TUBO, FAMILIA_TUBO),
                                (PISTAS_AREA, FAMILIA_AREA),
                                (PISTAS_ELEC, FAMILIA_ELEC),
                                (PISTAS_MEC, FAMILIA_MEC),
                                (PISTAS_AGREGADO, FAMILIA_AGREGADO)):
            for p in pistas:
                # El \b de cierre (con plural opcional) es imprescindible: sin el,
                # la pista "cal" capturaba "calibre", "calidad" y "caliente".
                if re.search(rf"\b{re.escape(p)}(?:es|s)?\b", fuente):
                    return familia
    if cat == "ELEC":
        return FAMILIA_ELEC
    if cat == "MEC":
        return FAMILIA_MEC
    if cat == "ESTR":
        return FAMILIA_TUBO
    return FAMILIA_GENERICA


def detectar_forma(metadata):
    texto = normalizar(" ".join(str(metadata.get(c, "") or "") for c in (
        "descripcion_corta", "tipo_producto", "especificacion", "nombre_material")))
    for clave, etiqueta in FORMAS.items():
        if re.search(rf"\b{clave}\b", texto):
            return etiqueta
    return ""


def detectar_presentacion(metadata):
    """'SACO 50 kg', 'CUBETA 5 gal': lo que distingue a un agregado."""
    texto = sin_acentos(" ".join(str(metadata.get(c, "") or "") for c in (
        "descripcion_corta", "especificacion", "dimensiones", "tipo_producto",
        "presentacion")))
    envases = "|".join(sorted(ENVASES, key=len, reverse=True))
    m = re.search(rf"\b({envases})\b\s*(?:de\s*)?(\d+(?:[.,]\d+)?)?\s*([A-Za-z]{{1,3}}\d?)?",
                  texto, re.I)
    if m:
        envase = ENVASES.get(m.group(1).lower(), m.group(1).upper())
        cantidad = _formatear_numero(m.group(2)) if m.group(2) else ""
        unidad = UNIDADES_MEDIDA.get((m.group(3) or "").lower(), "")
        return " ".join(x for x in (envase, cantidad, unidad) if x).strip()
    # Sin envase explicito: una cantidad con unidad tambien sirve ("25 kg").
    # El guardia ``(?![/\d])`` descarta las unidades COMPUESTAS, que son
    # resistencias, no presentaciones: "concreto 210 kg/cm2" no es un saco de
    # 210 kg.
    m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(kg|kgs|lb|lbs|l|lt|lts|litros?|gal|"
                  r"galones?|m2|m3)\b(?![/\d])", texto, re.I)
    if m:
        return f"{_formatear_numero(m.group(1))} {UNIDADES_MEDIDA.get(m.group(2).lower(), m.group(2))}"
    # Ultimo recurso: la unidad de venta sola ("m3" para arena o lastre). Solo se
    # aceptan unidades inequivocas; "m" o "un" se descartan por ambiguas, y se
    # excluyen de nuevo las compuestas ("210 kg/cm2").
    m = re.search(r"\b(m2|m3|kg|lb|gal|ton(?:elada)?s?|litros?)\b(?![/\d])",
                  texto, re.I)
    if m:
        return UNIDADES_MEDIDA.get(m.group(1).lower(), m.group(1).lower())
    return ""


def detectar_designaciones(metadata, limite=3):
    """'CH 13', 'SDR 26', '#12 AWG', '60 A', '2P': designaciones de producto.

    Se excluyen antes las normas formales para no confundir 'ASTM A500M' con una
    designacion.
    """
    crudo = " ".join(str(metadata.get(c, "") or "") for c in (
        "descripcion_corta", "especificacion", "tipo_producto", "nombre_material",
        "dimensiones"))
    texto = quitar_normativas(sin_acentos(crudo))
    encontradas = []
    for orden, patron, formato in PATRONES_DESIGNACION:
        m = patron.search(texto)
        if not m:
            continue
        valor = formato(m)
        if valor not in [v for _o, v in encontradas]:
            encontradas.append((orden, valor))
    encontradas.sort(key=lambda x: x[0])
    return [v for _o, v in encontradas][:limite]


def detectar_modelo(metadata):
    """Codigo de modelo (QO260, 4RB-2075): lo que distingue un electrico."""
    crudo = " ".join(str(metadata.get(c, "") or "") for c in (
        "modelo", "especificacion", "tipo_producto", "descripcion_corta"))
    texto = quitar_normativas(sin_acentos(crudo)).upper()
    marca = normalizar(metadata.get("marca", ""))
    for m in RE_MODELO.finditer(texto):
        cand = m.group(0)
        if normalizar(cand) == marca:
            continue
        if re.fullmatch(r"\d+[A-Z]{0,2}", cand):       # es una medida, no un modelo
            continue
        if any(cand == d.replace(" ", "") for d in detectar_designaciones(metadata)):
            continue
        return cand
    return ""


# --------------------------------------------------------------------------
# NOMBRE DE LA FICHA
# --------------------------------------------------------------------------
def analizar(metadata):
    """Analiza la ficha y devuelve el nombre propuesto + el detalle del analisis.

    Claves devueltas: ``nombre``, ``familia``, ``base``, ``forma``,
    ``dimensiones``, ``designaciones``, ``presentacion``, ``modelo``, ``marca``,
    ``suficiente`` (bool) y ``faltantes`` (lista de textos para el usuario).
    """
    metadata = dict(metadata or {})
    marca = str(metadata.get("marca", "") or "").strip()
    sin_medidas = bool(metadata.get("sin_medidas"))

    # 1. Base: el nombre del material, sin normas, sin conectores sueltos y sin
    #    las dimensiones (se vuelven a agregar ya formateadas).
    bruto = _limpiar_conectores(
        quitar_calibre(quitar_normativas(metadata.get("nombre_material", ""))))
    dim_en_nombre = ""
    m = RE_GRUPO_DIM.search(bruto)
    if m:
        dim_en_nombre = m.group(0)
        bruto = (bruto[:m.start()] + " " + bruto[m.end():])
    bruto = re.sub(r"[,;]+", " ", bruto)
    base = re.sub(r"\s+", " ", bruto).strip().upper()

    # 2. Rasgos que distinguen segun la familia.
    familia = detectar_familia(metadata)
    forma = detectar_forma(metadata)
    dimensiones = (formatear_dimensiones(metadata.get("dimensiones_detectadas"))
                   or formatear_dimensiones(metadata.get("dimensiones"))
                   or formatear_dimensiones(dim_en_nombre)
                   or formatear_dimensiones(metadata.get("descripcion_corta")))
    designaciones = detectar_designaciones(metadata)
    presentacion = (detectar_presentacion(metadata)
                    if familia in (FAMILIA_AGREGADO, FAMILIA_GENERICA) else "")
    modelo = detectar_modelo(metadata) if familia in (FAMILIA_ELEC, FAMILIA_MEC) else ""

    # 3. Armado, sin repetir lo que ya dice la base.
    ya = set(_tokens(base))

    def nuevo(fragmento):
        """True si el fragmento aporta algo que la base no diga ya."""
        t = _tokens(fragmento)
        return bool(t) and not set(t).issubset(ya)

    partes = [base]
    if forma and nuevo(forma):
        partes.append(forma)
        ya.update(_tokens(forma))
    for fragmento in (dimensiones, *designaciones, presentacion, modelo):
        if fragmento and nuevo(fragmento):
            partes.append(fragmento)
            ya.update(_tokens(fragmento))

    nombre = re.sub(r"\s+", " ", " ".join(p for p in partes if p)).strip()
    if marca:
        nombre = f"{nombre} - {marca}" if nombre else marca

    # 4. ¿Alcanza para distinguirla de otra ficha parecida?
    #    Una presentacion SIN cantidad ("SACO" a secas) va en el nombre pero no
    #    cuenta como distintiva: un saco de 25 kg y otro de 50 kg se seguirian
    #    confundiendo.
    presentacion_util = presentacion if re.search(r"\d", presentacion or "") else ""
    distintivos = [x for x in (dimensiones, presentacion_util, modelo,
                               *designaciones) if x]
    faltantes = []
    if not distintivos and not sin_medidas:
        faltantes.append(_que_falta(familia))
    if not base:
        faltantes.insert(0, "Falta el nombre del material.")
    if not marca:
        faltantes.append("Falta la marca.")

    return {
        "nombre": nombre,
        "familia": familia,
        "base": base,
        "forma": forma,
        "dimensiones": dimensiones,
        "designaciones": designaciones,
        "presentacion": presentacion,
        "modelo": modelo,
        "marca": marca,
        "distintivos": distintivos,
        "sin_medidas": sin_medidas,
        "suficiente": not faltantes,
        "faltantes": faltantes,
    }


def _que_falta(familia):
    """Mensaje concreto de que dato pedirle al usuario."""
    return {
        FAMILIA_TUBO: "Faltan las dimensiones (ej: 8\"x8\"x3/16\") o el calibre "
                      "(ej: CH 13): sin eso no se distingue de otro tubo.",
        FAMILIA_AREA: "Faltan las dimensiones con su unidad (ej: 60x60 cm).",
        FAMILIA_AGREGADO: "Falta la presentacion (ej: saco 50 kg, cubeta 5 gal).",
        FAMILIA_ELEC: "Falta el tipo o el modelo (ej: 2P 60 A, QO260, #12 AWG).",
        FAMILIA_MEC: "Falta el diametro o la designacion (ej: 4\", SDR 26).",
    }.get(familia,
          "Faltan datos que distingan la ficha: dimensiones, presentacion o modelo.")


def generar_nombre_ficha_unico(metadata):
    """Genera un nombre unico y descriptivo para una ficha tecnica.

    Parametros
    ----------
    metadata : dict
        Campos usados (todos opcionales salvo ``nombre_material``):
          - ``nombre_material``  : "Tubo Estructural"
          - ``marca``            : "MultiGroup"
          - ``categoria``        : ARQ / ESTR / MEC / ELEC
          - ``descripcion_corta``: "8x8x3/16, cuadrado"
          - ``dimensiones``      : "8\"x8\"x3/16\"" (texto libre del OCR)
          - ``dimensiones_detectadas`` : {"ancho": 8, "largo": 8, "espesor": 0.1875}
          - ``especificacion`` / ``tipo_producto`` / ``modelo``
          - ``normativa``        : se ignora a proposito (ver encabezado)

    Retorna
    -------
    str
        ``"[MATERIAL] [FORMA] [DIMENSIONES] [DESIGNACION] - [MARCA]"``, por
        ejemplo ``'TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup'``.

    El nombre es descriptivo, buscable (entra en ``search_keywords``) y unico
    para una combinacion material + marca + especificaciones. Para saber SI
    alcanza para distinguirla, use ``analizar()``, que devuelve ``suficiente`` y
    ``faltantes``.
    """
    return analizar(metadata)["nombre"]


def nombre_sin_marca(nombre_ficha, marca=""):
    """Quita el sufijo `` - MARCA`` del nombre.

    Se usa en las caratulas y en los Excel, donde la marca ya tiene su propia
    columna: ahi conviene ``TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16"`` en vez de
    repetir la marca. Sigue siendo inequivoco, que es el objetivo.
    """
    n = str(nombre_ficha or "").strip()
    m = str(marca or "").strip()
    if m and n.lower().endswith(f" - {m.lower()}"):
        return n[: -(len(m) + 3)].strip()
    partes = n.rsplit(" - ", 1)
    if len(partes) == 2 and partes[1] and len(partes[1]) <= 40:
        return partes[0].strip()
    return n


def clave_unicidad(nombre_ficha):
    """Clave normalizada para detectar nombres repetidos.

    ``'TUBO ESTRUCTURAL 8" x 8" - MultiGroup'`` y
    ``'tubo estructural 8x8 - multigroup'`` comparten clave: se ignoran
    mayusculas, acentos, comillas y el espaciado alrededor de la "x" de las
    medidas, que es justo donde cada persona escribe distinto.
    """
    s = normalizar(nombre_ficha)
    return re.sub(r"(?<=\d)\s*x\s*(?=\d)", "x", s)


def slug_archivo(nombre_ficha, maximo=110):
    """Nombre de archivo seguro (y legible) a partir del nombre de la ficha.

    ``'TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup'``
    -> ``'TUBO-ESTRUCTURAL-CUADRADO-8x8x3-16-MultiGroup'``
    """
    s = sin_acentos(nombre_ficha)
    s = s.replace('"', "").replace("''", "").replace("”", "")
    s = re.sub(r"[/\\]", "-", s)
    s = re.sub(r"[^0-9A-Za-z]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return (s[:maximo].rstrip("-") or "ficha")


if __name__ == "__main__":
    ejemplos = [
        {"nombre_material": "Tubo Estructural", "marca": "MultiGroup",
         "categoria": "ESTR", "descripcion_corta": "8x8x3/16, cuadrado",
         "normativa": "ASTM A500M",
         "dimensiones_detectadas": {"ancho": 8, "largo": 8, "espesor": 0.1875}},
        {"nombre_material": "Tubo Rectangular e Industrial", "marca": "Macopa",
         "categoria": "ESTR", "descripcion_corta": "industrial"},
        {"nombre_material": "Ceramica Porcelanato", "marca": "Porcelanato Plus",
         "categoria": "ARQ", "dimensiones": "60x60 cm"},
        {"nombre_material": "Tubo Estructural Rectangular", "marca": "MultiGroup",
         "categoria": "ESTR", "dimensiones": '6"x2"', "especificacion": "CH13"},
        {"nombre_material": "Cemento Hidraulico", "marca": "Holcim",
         "categoria": "ESTR", "descripcion_corta": "saco de 50 kg"},
        {"nombre_material": "Breaker Termomagnetico", "marca": "Schneider",
         "categoria": "ELEC", "especificacion": "2 polos 60 A modelo QO260"},
        {"nombre_material": "Tuberia PVC", "marca": "Amanco", "categoria": "MEC",
         "dimensiones": '4"', "especificacion": "SDR 26"},
    ]
    for e in ejemplos:
        a = analizar(e)
        marca_ok = "OK " if a["suficiente"] else "REV"
        print(f"[{marca_ok}] {a['nombre']}")
        if not a["suficiente"]:
            print(f"        -> {a['faltantes'][0]}")
