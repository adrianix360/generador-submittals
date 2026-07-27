#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 ocr_extractor.py  --  Extraccion de datos de fichas (Generador Submittals v3)
================================================================================
Extrae los datos de una ficha tecnica (PDF o imagen) para cargarla a la BD.

Cascada de metodos (de mayor a menor precision):
  1. **OpenAI Vision (gpt-4o)** — lee las imagenes de la ficha y devuelve los
     campos en JSON estructurado. Usa la API key desde config/entorno.
  2. **OCR avanzado (Tesseract, v2.6.8)** — si Vision falla o no hay API key:
     rasteriza/lee el texto y, si hay API key, lo estructura con un modelo de
     texto (gpt-4o-mini). Si no, devuelve el texto crudo como pista.
  3. **Manual** — si ambos fallan, devuelve un formulario vacio marcado con
     ``_requiere_manual = True`` para que el usuario complete los datos.

Campos devueltos (dict): ``nombre_material, marca, categoria, tipo_producto,
dimensiones, especificacion, normativa, descripcion_corta`` + metadatos
(``_metodo``, ``_requiere_manual``, ``_evidencias``, ``_error``).

Todas las dependencias pesadas (openai, PyMuPDF/fitz, pytesseract, PIL) se
importan de forma PEREZOSA dentro de las funciones, para que el modulo se pueda
importar y probar aunque no esten instaladas.
================================================================================
"""

import io
import os
import json
import base64
import logging
from pathlib import Path

log = logging.getLogger("ocr_extractor")

MODELO_VISION = "gpt-4o"
MODELO_TEXTO = "gpt-4o-mini"
IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")
MAX_PAGINAS = 3          # paginas a analizar de un PDF
SIN_ESP = "SIN ESPECIFICAR"

CAMPOS_SALIDA = ("nombre_material", "marca", "categoria", "tipo_producto",
                 "dimensiones", "especificacion", "normativa", "descripcion_corta")

# --------------------------------------------------------------------------
# PROMPTS
# --------------------------------------------------------------------------
PROMPT_SISTEMA = (
    "Eres un experto en materiales de construccion, normativas tecnicas y "
    "traduccion tecnica. Analiza la ficha tecnica y extrae los datos del "
    "material. Si la ficha no esta en espanol, traduce al espanol con precision "
    "tecnica. No inventes datos: si un dato no es legible o no aparece, usalo "
    "vacio (o 'SIN ESPECIFICAR' para la normativa). La categoria debe ser una "
    "de: ARQ (arquitectonico), ESTR (estructural), MEC (mecanico), ELEC "
    "(electrico)."
)

PROMPT_INSTRUCCION = (
    "Extrae y responde UNICAMENTE en JSON valido (sin markdown), con estas "
    "claves exactas:\n"
    '{"nombre_material": "string", "marca": "string (fabricante principal; '
    "'SIN ESPECIFICAR' si no aparece)\", \"categoria\": \"ARQ|ESTR|MEC|ELEC\", "
    '"tipo_producto": "string breve", "dimensiones": "string (ej 150x100x1.5) '
    'o vacio", "especificacion": "string breve o vacio", "normativa": "todas '
    "las normas separadas por coma, orden alfabetico, sin duplicados; 'SIN "
    "ESPECIFICAR' si no hay\", \"descripcion_corta\": \"descripcion tecnica del "
    'producto en espanol, maximo 200 caracteres"}'
)


# --------------------------------------------------------------------------
# API KEY
# --------------------------------------------------------------------------
def _resolver_api_key(api_key=None):
    """Devuelve la API key: la explicita, o la de bd_manager (env/config)."""
    if api_key:
        return api_key.strip()
    try:
        import bd_manager
        # Fallback a la config v2.6 si existe junto al modulo.
        v26 = Path(__file__).resolve().parent / "submitals_config.json"
        return bd_manager.obtener_api_key(
            fallback_config_v26=str(v26) if v26.exists() else None)
    except Exception:
        return os.environ.get("OPENAI_API_KEY", "").strip()


# --------------------------------------------------------------------------
# CONVERSION A IMAGENES
# --------------------------------------------------------------------------
def _pdf_a_imagenes_b64(path, max_paginas=MAX_PAGINAS):
    """Rasteriza las primeras paginas de un PDF a PNG base64 (usa PyMuPDF)."""
    import fitz  # PyMuPDF (perezoso)
    imagenes = []
    doc = fitz.open(str(path))
    try:
        for i, page in enumerate(doc):
            if i >= max_paginas:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # ~150 dpi
            imagenes.append(base64.b64encode(pix.tobytes("png")).decode("ascii"))
    finally:
        doc.close()
    return imagenes


def _imagen_a_b64(path):
    """Codifica una imagen a PNG base64 (normaliza formato con PIL)."""
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _rutas_a_imagenes_b64(rutas, max_paginas=MAX_PAGINAS):
    imgs = []
    for r in rutas:
        ext = Path(r).suffix.lower()
        if ext == ".pdf":
            imgs.extend(_pdf_a_imagenes_b64(r, max_paginas))
        elif ext in IMG_EXT:
            imgs.append(_imagen_a_b64(r))
    return imgs


# --------------------------------------------------------------------------
# METODO 1: OPENAI VISION
# --------------------------------------------------------------------------
def extraer_con_vision(rutas, api_key):
    """Extrae datos usando OpenAI Vision (gpt-4o). Devuelve dict de campos.
    Lanza excepcion si falla (para permitir el fallback)."""
    from openai import OpenAI
    imagenes = _rutas_a_imagenes_b64(rutas)
    if not imagenes:
        raise RuntimeError("No se pudieron obtener imagenes de la(s) ficha(s)")

    contenido = [{"type": "text", "text": PROMPT_INSTRUCCION}]
    for b64 in imagenes:
        contenido.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=MODELO_VISION,
        messages=[
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": contenido},
        ],
        temperature=0.2,
        max_tokens=600,
        response_format={"type": "json_object"},
    )
    data = _parse_json(resp.choices[0].message.content)
    data["_metodo"] = "openai_vision"
    return _normalizar(data)


# --------------------------------------------------------------------------
# METODO 2: OCR (Tesseract v2.6.8) + estructuracion opcional con texto
# --------------------------------------------------------------------------
def ocr_texto(rutas):
    """Extrae texto crudo de las fichas usando pypdf y/o Tesseract."""
    partes = []
    for r in rutas:
        ext = Path(r).suffix.lower()
        try:
            if ext == ".pdf":
                partes.append(_texto_pdf(r))
            elif ext in IMG_EXT:
                partes.append(_ocr_imagen(r))
        except Exception as e:
            log.warning("OCR fallo en %s: %s", r, e)
    return "\n".join(p for p in partes if p).strip()


def _texto_pdf(path):
    """Texto embebido del PDF (pypdf); si es muy corto, OCR de las paginas."""
    texto = ""
    try:
        from pypdf import PdfReader
        r = PdfReader(str(path))
        texto = "\n".join((p.extract_text() or "") for p in r.pages)
    except Exception:
        texto = ""
    if len(texto.strip()) >= 40:
        return texto
    # Escaneado -> OCR de las paginas rasterizadas.
    try:
        import fitz
        from PIL import Image
        import pytesseract
        doc = fitz.open(str(path))
        out = []
        try:
            for i, page in enumerate(doc):
                if i >= MAX_PAGINAS:
                    break
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                im = Image.open(io.BytesIO(pix.tobytes("png")))
                out.append(pytesseract.image_to_string(im, lang="spa+eng"))
        finally:
            doc.close()
        return "\n".join(out)
    except Exception:
        return texto


def _ocr_imagen(path):
    from PIL import Image
    import pytesseract
    with Image.open(path) as im:
        return pytesseract.image_to_string(im.convert("RGB"), lang="spa+eng")


def extraer_con_ocr(rutas, api_key=None):
    """Fallback OCR: extrae texto y, si hay API key, lo estructura con un modelo
    de texto (gpt-4o-mini). Sin API key, devuelve el texto como pista y marca
    revision manual."""
    texto = ocr_texto(rutas)
    if not texto:
        raise RuntimeError("OCR no obtuvo texto de la(s) ficha(s)")

    if api_key:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=MODELO_TEXTO,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA},
                {"role": "user", "content": PROMPT_INSTRUCCION +
                 "\n\nTEXTO DE LA FICHA (via OCR):\n" + texto[:6000]},
            ],
            temperature=0.2,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        data = _parse_json(resp.choices[0].message.content)
        data["_metodo"] = "ocr+texto"
        data["_requiere_manual"] = True  # OCR es menos confiable: revisar
        return _normalizar(data)

    # Sin API key: solo pista de texto para llenar manual.
    base = _vacio()
    base["_metodo"] = "ocr_sin_ia"
    base["_requiere_manual"] = True
    base["_texto_ocr"] = texto[:2000]
    return base


# --------------------------------------------------------------------------
# ORQUESTADOR
# --------------------------------------------------------------------------
def extraer(rutas, api_key=None, categoria_sugerida=None):
    """Extrae los datos de una ficha aplicando la cascada Vision -> OCR ->
    manual. ``rutas`` puede ser un str o una lista (varios documentos del mismo
    material). Siempre devuelve un dict (nunca lanza)."""
    if isinstance(rutas, (str, Path)):
        rutas = [rutas]
    rutas = [str(r) for r in rutas if Path(r).exists()]
    if not rutas:
        r = _vacio()
        r["_metodo"] = "manual"
        r["_requiere_manual"] = True
        r["_error"] = "No se encontraron archivos"
        return r

    key = _resolver_api_key(api_key)

    # 1) Vision
    if key:
        try:
            data = extraer_con_vision(rutas, key)
            if categoria_sugerida and not data.get("categoria"):
                data["categoria"] = categoria_sugerida.upper()
            return data
        except Exception as e:
            log.warning("Vision fallo, se intenta OCR: %s", e)

    # 2) OCR (con o sin IA de texto)
    try:
        data = extraer_con_ocr(rutas, api_key=key or None)
        if categoria_sugerida and not data.get("categoria"):
            data["categoria"] = categoria_sugerida.upper()
        return data
    except Exception as e:
        log.warning("OCR fallo, se pasa a manual: %s", e)

    # 3) Manual
    r = _vacio()
    r["_metodo"] = "manual"
    r["_requiere_manual"] = True
    r["_error"] = "No se pudo extraer automaticamente; complete manualmente"
    if categoria_sugerida:
        r["categoria"] = categoria_sugerida.upper()
    return r


# --------------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------------
def _parse_json(texto):
    """Extrae el primer objeto JSON del texto (tolerante a markdown)."""
    if not texto:
        return {}
    s = texto.strip()
    ini, fin = s.find("{"), s.rfind("}")
    if ini >= 0 and fin > ini:
        s = s[ini:fin + 1]
    try:
        return json.loads(s)
    except Exception:
        return {}


def _vacio():
    d = {c: "" for c in CAMPOS_SALIDA}
    d["normativa"] = SIN_ESP
    d["_evidencias"] = []
    return d


def _normalizar(data):
    """Garantiza todas las claves de salida y limpia valores."""
    out = _vacio()
    for c in CAMPOS_SALIDA:
        v = data.get(c, "")
        out[c] = str(v).strip() if v is not None else ""
    if not out["normativa"]:
        out["normativa"] = SIN_ESP
    cat = out["categoria"].upper()
    out["categoria"] = cat if cat in ("ARQ", "ESTR", "MEC", "ELEC") else ""
    if len(out["descripcion_corta"]) > 200:
        out["descripcion_corta"] = out["descripcion_corta"][:197].rstrip() + "..."
    # Propagar metadatos.
    for meta in ("_metodo", "_requiere_manual", "_error", "_texto_ocr"):
        if meta in data:
            out[meta] = data[meta]
    out.setdefault("_requiere_manual", False)
    ev = data.get("_evidencias") or data.get("evidencias")
    out["_evidencias"] = ev if isinstance(ev, list) else []
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(extraer(sys.argv[1:]), ensure_ascii=False, indent=2))
    else:
        print("Uso: python ocr_extractor.py ficha1.pdf [ficha2.pdf ...]")
