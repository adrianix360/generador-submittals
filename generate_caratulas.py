#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 generate_caratulas.py
 Genera caratulas PDF de submittals a partir de datos_materiales.json,
 usando el template Jinja2 template_caratula.html.
================================================================================

INSTALACION (una sola vez)
--------------------------------------------------------------------------------
 1) Python 3.9 o superior.
 2) Librerias:
        pip install jinja2 pypdf playwright
 3) Motor de render (RECOMENDADO: Playwright / Chromium; NO requiere admin
    ni librerias del sistema, y renderiza identico a Chrome):
        pip install playwright
        python -m playwright install chromium
    (el segundo comando descarga Chromium al perfil del usuario, una sola vez)

    El script intenta los motores en este orden y usa el primero que funcione:
        1. playwright  (Chromium headless)  <-- recomendado en Windows
        2. weasyprint  (requiere GTK en Windows; suele fallar sin el)
        3. pdfkit      (requiere el binario wkhtmltopdf en el PATH o
                        WKHTMLTOPDF_PATH; https://wkhtmltopdf.org/downloads.html)

    Basta con tener UNO instalado. Con Playwright no necesita nada mas.

USO
--------------------------------------------------------------------------------
        python generate_caratulas.py
        python generate_caratulas.py --json datos_materiales.json
================================================================================
"""

import os
import re
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

# --------------------------------------------------------------------------
# CONFIGURACION
# --------------------------------------------------------------------------
BASE_DIR      = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "template_caratula.html"
LOGO_PATH     = BASE_DIR / "Tabla visual refresh" / "assets" / "logo_es_crop.png"
DEFAULT_JSON  = BASE_DIR / "datos_materiales.json"
LOG_PATH      = BASE_DIR / "generate_caratulas.log"
REPORT_PATH   = BASE_DIR / "generate_caratulas_report.txt"

REQUIRED_FIELDS = ["consecutivo", "nombre", "marca", "descripcion",
                   "estado", "carpeta_vacia", "ruta_carpeta"]
NONEMPTY_TEXT   = ["consecutivo", "nombre", "marca", "descripcion"]
ESTADO_OK       = "FICHA_DISPONIBLE"
MAX_DESC        = 200

# Si usa pdfkit y wkhtmltopdf NO esta en PATH, indique el .exe:
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"

LOGO_URI = ""  # se asigna en main()

# --------------------------------------------------------------------------
# LOGGING  ->  [TIMESTAMP] [NIVEL] [CONSECUTIVO] [MENSAJE]
# --------------------------------------------------------------------------
logger = logging.getLogger("caratulas")
logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(consec)s %(message)s",
                         "%Y-%m-%d %H:%M:%S")


class _CtxFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "consec"):
            record.consec = "-"
        return True


for _h in (logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),
           logging.StreamHandler(sys.stdout)):
    _h.setFormatter(_fmt)
    _h.addFilter(_CtxFilter())
    logger.addHandler(_h)


def log(level, msg, consec="-"):
    logger.log(level, msg, extra={"consec": consec})


# --------------------------------------------------------------------------
# ACUMULADORES PARA EL REPORTE
# --------------------------------------------------------------------------
stats = {
    "total": 0, "vacias": 0, "incompletas": 0, "procesados": 0,
    "existentes": 0, "ok": 0, "fallidos": 0, "criticos": 0,
    "motor_fallback": 0,   # v2.6.2: cuantas caratulas NO usaron el motor preferido
}
lst_vacias, lst_incompletas, lst_generados = [], [], []
lst_existentes = []   # (consecutivo, nombre_archivo)  ya tenian caratula
lst_errores = []   # (consecutivo, detalle)


# --------------------------------------------------------------------------
# AUTO-CORRECCION / HELPERS
# --------------------------------------------------------------------------
def sanitize_filename(name):
    """Reemplaza caracteres invalidos de Windows en el nombre de archivo."""
    s = name.replace('"', 'in').replace('/', '-').replace('\\', '-')
    s = re.sub(r'[:*?<>|]', '-', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def to_absolute(ruta):
    """Convierte ruta relativa a absoluta bajo BASE_DIR."""
    p = Path(ruta)
    if not p.is_absolute():
        p = BASE_DIR / ruta
    return p


def file_uri(path):
    """Devuelve file:/// URL-encoded (maneja espacios)."""
    return Path(path).resolve().as_uri()


def truncate_desc(desc, consec):
    if len(desc) <= MAX_DESC:
        return desc
    cut = desc[:MAX_DESC]
    m = max(cut.rfind('.'), cut.rfind(' '))
    if m > 0:
        cut = cut[:m]
    log(logging.INFO, f"Descripcion truncada para {consec} ({len(desc)}->{len(cut)} car.)", consec)
    return cut.rstrip() + "..."


# --------------------------------------------------------------------------
# MOTORES DE RENDER
# --------------------------------------------------------------------------
def render_playwright(html, out_path):
    """Motor recomendado: Chromium headless. Renderiza identico a Chrome."""
    import tempfile
    from playwright.sync_api import sync_playwright
    fd, tmp_name = tempfile.mkstemp(suffix=".html", dir=str(BASE_DIR))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_text(html, encoding="utf-8")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(tmp.as_uri(), wait_until="networkidle")
                page.pdf(path=str(out_path), format="Letter",
                         print_background=True,
                         margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            finally:
                browser.close()
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass


def render_pdfkit(html, out_path):
    import pdfkit
    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH) if WKHTMLTOPDF_PATH else None
    options = {
        "page-size": "Letter",
        "margin-top": "0", "margin-bottom": "0",
        "margin-left": "0", "margin-right": "0",
        "dpi": "300", "image-dpi": "300",
        "encoding": "UTF-8",
        "enable-local-file-access": None,
        "quiet": "",
    }
    pdfkit.from_string(html, str(out_path), options=options, configuration=config)


def render_weasyprint(html, out_path):
    from weasyprint import HTML
    HTML(string=html, base_url=str(BASE_DIR)).write_pdf(str(out_path))


def available_engines():
    """Motores disponibles, en orden de preferencia. Playwright primero."""
    eng = []
    try:
        import playwright.sync_api  # noqa
        eng.append(("playwright", render_playwright))
    except Exception:
        pass
    for name, fn in (("weasyprint", render_weasyprint), ("pdfkit", render_pdfkit)):
        try:
            __import__(name)
            eng.append((name, fn))
        except Exception:
            pass
    return eng


# --------------------------------------------------------------------------
# VERIFICACION DE INTEGRIDAD DEL PDF
# --------------------------------------------------------------------------
def pdf_is_valid(path):
    """True si el PDF existe, pesa > 0 y abre correctamente."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        from pypdf import PdfReader
        r = PdfReader(str(path))
        return len(r.pages) > 0
    except Exception:
        try:
            data = path.read_bytes()
            return data.startswith(b"%PDF") and b"%%EOF" in data[-1024:]
        except Exception:
            return False


# --------------------------------------------------------------------------
# CRITICO -> detiene ejecucion
# --------------------------------------------------------------------------
def die(msg):
    stats["criticos"] += 1
    log(logging.CRITICAL, msg)
    write_report(critical_msg=msg)
    sys.exit(1)


# --------------------------------------------------------------------------
# PROCESAR UN MATERIAL
# --------------------------------------------------------------------------
def process_material(item, template, engines, extra_ctx=None):
    consec = str(item.get("consecutivo", "?")).strip() or "?"

    faltantes = [f for f in REQUIRED_FIELDS if f not in item]
    if faltantes:
        stats["incompletas"] += 1
        lst_incompletas.append((consec, f"faltan campos: {', '.join(faltantes)}"))
        log(logging.WARNING, f"[OMITIDO] faltan campos {faltantes}", consec)
        return

    if item["carpeta_vacia"] is True:
        stats["vacias"] += 1
        lst_vacias.append((consec, item.get("nombre", "")))
        log(logging.WARNING, "[SALTADO] carpeta vacia", consec)
        return

    # v2.6.2: una ficha incompleta (o con campos vacios) YA NO se omite. Se
    # genera la caratula con los datos que si se pudieron extraer, dejando en
    # blanco lo que falte (nunca se inventa informacion) -- se necesita la
    # caratula fisica para el submittal aunque la ficha no se haya podido leer
    # del todo. Queda registro en el reporte/log de que estaba incompleta.
    ficha_incompleta = str(item.get("estado")) != ESTADO_OK
    if ficha_incompleta:
        stats["incompletas"] += 1
        lst_incompletas.append((consec, f"estado='{item.get('estado')}' "
                                        "(caratula generada con datos parciales)"))
        log(logging.WARNING, f"[AVISO] ficha incompleta (estado='{item.get('estado')}'); "
                             "se genera la caratula con los datos disponibles", consec)

    vacios = [f for f in NONEMPTY_TEXT if not str(item.get(f, "")).strip()]
    if vacios:
        if not ficha_incompleta:
            stats["incompletas"] += 1
            lst_incompletas.append((consec, f"campos vacios: {', '.join(vacios)} "
                                            "(caratula generada con datos parciales)"))
        log(logging.WARNING, f"[AVISO] campo(s) vacio(s) {vacios}; "
                             "se genera la caratula igual", consec)

    carpeta = to_absolute(item["ruta_carpeta"])
    try:
        if not carpeta.exists():
            carpeta.mkdir(parents=True, exist_ok=True)
            log(logging.INFO, f"Carpeta creada (no existia): {carpeta}", consec)
        if not os.access(carpeta, os.W_OK):
            raise PermissionError(f"sin permiso de escritura en {carpeta}")
    except Exception as e:
        stats["fallidos"] += 1
        lst_errores.append((consec, f"carpeta: {e}"))
        log(logging.ERROR, f"No se pudo preparar carpeta: {e}", consec)
        return

    # -- MODO INCREMENTAL: si la carpeta YA contiene una caratula, se salta
    ya = [p for p in carpeta.glob("*.pdf") if p.name.upper().startswith("CARATULA")]
    if ya:
        stats["existentes"] += 1
        lst_existentes.append((consec, ya[0].name))
        log(logging.INFO, f"[SALTADO] ya tiene caratula: {ya[0].name}", consec)
        return

    stats["procesados"] += 1

    descripcion = truncate_desc(str(item["descripcion"]).strip(), consec)

    def _vaciar(v):
        s = str(v if v is not None else "").strip()
        return "" if s.upper() in ("SIN ESPECIFICAR", "POR DEFINIR") else s

    try:
        ctx = {
            "consecutivo": str(item["consecutivo"]).strip(),
            "nombre_comercial": _vaciar(item["nombre"]),
            "fabricante": _vaciar(item["marca"]),
            "descripcion_tecnica": _vaciar(descripcion),
            "normativa": _vaciar(item.get("normativa", "")),
            "aspectos_adicionales": _vaciar(item.get("aspectos_adicionales", "")),
            "logo_path": LOGO_URI,
        }
        # v2.3: contexto extra (p.ej. carATULA del Ministerio: datos de proyecto,
        # logo_ministerio, version="v1", registro=consecutivo, etc.)
        if extra_ctx:
            for k, v in extra_ctx.items():
                ctx[k] = _vaciar(v) if isinstance(v, str) else v
        html = template.render(**ctx)
    except Exception as e:
        stats["fallidos"] += 1
        lst_errores.append((consec, f"Jinja2: {e}"))
        log(logging.ERROR, f"Error Jinja2: {e}", consec)
        return

    fname = sanitize_filename(f"CARATULA {consec}-{item['nombre']}") + ".pdf"
    out_path = carpeta / fname

    used_engine = None
    last_err = None
    for name, fn in engines:
        try:
            fn(html, out_path)
            used_engine = name
            break
        except Exception as e:
            last_err = e
            log(logging.WARNING, f"Motor {name} fallo, intentando siguiente: {e}", consec)
    if used_engine is None:
        stats["fallidos"] += 1
        lst_errores.append((consec, f"PDF: {last_err}"))
        log(logging.ERROR, f"Error PDF: todos los motores fallaron ({last_err})", consec)
        return

    if not pdf_is_valid(out_path):
        log(logging.WARNING, f"PDF invalido/vacio con {used_engine}; reintentando otro motor", consec)
        try:
            if out_path.exists():
                out_path.unlink()
        except Exception:
            pass
        retried = False
        for name, fn in engines:
            if name == used_engine:
                continue
            try:
                fn(html, out_path)
                if pdf_is_valid(out_path):
                    retried = True
                    used_engine = name
                    break
            except Exception as e:
                last_err = e
        if not retried:
            try:
                if out_path.exists():
                    out_path.unlink()
            except Exception:
                pass
            stats["fallidos"] += 1
            lst_errores.append((consec, "PDF corrupto/vacio tras reintento"))
            log(logging.ERROR, "PDF corrupto o vacio; eliminado", consec)
            return

    stats["ok"] += 1
    lst_generados.append((consec, str(out_path)))
    log(logging.INFO, f"PDF generado exitosamente ({used_engine}) -> {out_path.name}", consec)

    # v2.6.2: si el motor preferido (Playwright) no se pudo usar, se genero con
    # un motor de respaldo (pdfkit/weasyprint) que renderiza peor el CSS
    # moderno de la plantilla (flexbox/grid) -> se cuenta para avisar al final,
    # en vez de que quede enterrado solo en el log linea por linea.
    if engines and used_engine != engines[0][0]:
        stats["motor_fallback"] += 1


# --------------------------------------------------------------------------
# REPORTE FINAL
# --------------------------------------------------------------------------
def write_report(critical_msg=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    L = []
    L.append("REPORTE DE GENERACION DE CARATULAS")
    L.append(f"Fecha: {ts}")
    L.append(f"Directorio base: {BASE_DIR}")
    L.append("")
    L.append("ESTADISTICAS:")
    L.append(f"  Total de materiales en JSON:             {stats['total']}")
    L.append(f"  Materiales con carpeta vacia (saltados): {stats['vacias']}")
    L.append(f"  Materiales con ficha incompleta:         {stats['incompletas']}")
    L.append(f"  Materiales procesados:                   {stats['procesados']}")
    L.append(f"  Saltados (ya tenian caratula):           {stats['existentes']}")
    L.append(f"  PDFs generados exitosamente:             {stats['ok']}")
    L.append(f"  PDFs fallidos:                           {stats['fallidos']}")
    L.append(f"  Errores criticos:                        {stats['criticos']}")
    if stats.get("motor_fallback"):
        L.append(f"  ⚠ PDFs generados con motor de respaldo:  {stats['motor_fallback']} "
                "(Playwright/Chromium fallo; revise 'python -m playwright install chromium')")
    L.append("")
    L.append("ERRORES CRITICOS:")
    L.append(f"  {critical_msg}" if critical_msg else "  (ninguno)")
    L.append("")
    L.append("MATERIALES SALTADOS (CARPETA VACIA):")
    L += [f"  - {c} {n}" for c, n in lst_vacias] or ["  (ninguno)"]
    L.append("")
    L.append("MATERIALES OMITIDOS (FICHA INCOMPLETA):")
    L += [f"  - {c}: {d}" for c, d in lst_incompletas] or ["  (ninguno)"]
    L.append("")
    L.append("SALTADOS (YA TENIAN CARATULA):")
    L += [f"  - {c}: {n}" for c, n in lst_existentes] or ["  (ninguno)"]
    L.append("")
    L.append("ERRORES NO CRITICOS DURANTE PROCESAMIENTO:")
    L += [f"  - {c}: {d}" for c, d in lst_errores] or ["  (ninguno)"]
    L.append("")
    esperados = stats["procesados"]
    L.append("COMPARACION JSON vs PDFs:")
    L.append(f"  Debieron generar PDF: {esperados} | Generados: {stats['ok']}")
    if esperados != stats["ok"]:
        faltaron = {c for c, _ in lst_errores}
        L.append(f"  Faltaron: {', '.join(sorted(faltaron)) or '-'}")
    L.append("")
    L.append("ARCHIVO DE LOG COMPLETO:")
    L.append(f"  Ver: {LOG_PATH}")
    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Genera caratulas PDF de submittals.")
    ap.add_argument("--json", default=str(DEFAULT_JSON))
    args = ap.parse_args()

    log(logging.INFO, "=== INICIO generate_caratulas ===")

    if not BASE_DIR.exists():
        die(f"ERROR: Directorio base no existe: {BASE_DIR}")

    try:
        import jinja2  # noqa
    except ImportError:
        die("ERROR: Instala con: pip install jinja2 pypdf playwright")

    engines = available_engines()
    if not engines:
        die("ERROR: No hay motor de PDF. Instala: pip install playwright && python -m playwright install chromium")
    log(logging.INFO, f"Motores disponibles: {', '.join(n for n, _ in engines)}")

    json_path = Path(args.json)
    if not json_path.exists():
        die(f"ERROR: {json_path.name} no encontrado en {json_path}")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"ERROR: {json_path.name} no es un JSON valido. Linea: {e.lineno}, col {e.colno}: {e.msg}")
    materiales = data.get("materiales") if isinstance(data, dict) else data
    if not isinstance(materiales, list):
        die("ERROR: el JSON debe contener un array 'materiales'.")
    stats["total"] = len(materiales)
    log(logging.INFO, f"JSON cargado: {len(materiales)} material(es)")

    if not TEMPLATE_PATH.exists():
        die(f"ERROR: template_caratula.html no encontrado en {TEMPLATE_PATH}")
    tpl_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    if not tpl_text.strip() or "<html" not in tpl_text.lower():
        die("ERROR: template_caratula.html esta corrupto o vacio")
    from jinja2 import Template
    try:
        template = Template(tpl_text)
    except Exception as e:
        die(f"ERROR: template_caratula.html invalido: {e}")

    if not LOGO_PATH.exists():
        die(f"ERROR: Logo no encontrado en {LOGO_PATH}")
    global LOGO_URI
    LOGO_URI = file_uri(LOGO_PATH)
    log(logging.INFO, f"Logo OK -> {LOGO_URI}")

    for item in materiales:
        try:
            process_material(item, template, engines)
        except Exception as e:
            c = str(item.get("consecutivo", "?"))
            stats["fallidos"] += 1
            lst_errores.append((c, f"inesperado: {e}"))
            log(logging.ERROR, f"Error inesperado: {e}", c)

    write_report()
    log(logging.INFO, "--------------------------------------------------")
    log(logging.INFO, f"RESUMEN: {stats['ok']} OK | {stats['existentes']} ya-existentes | "
                      f"{stats['fallidos']} fallidos | {stats['vacias']} vacias | "
                      f"{stats['incompletas']} incompletas | {stats['total']} total")
    log(logging.INFO, f"Reporte -> {REPORT_PATH}")
    log(logging.INFO, "=== FIN generate_caratulas ===")


if __name__ == "__main__":
    main()
