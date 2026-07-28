#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 submitals_gui_v3.py  --  Interfaz principal v3.1.0 (Generador de Submittals ES)
================================================================================
Interfaz de la version 3, basada en una **Base de Datos centralizada en GitHub**
de fichas reutilizables. Coexiste con el sistema v2.6 (generacion desde carpetas)
sin modificarlo.

Menu principal (2x2):
   [ Generar desde BD ]        [ Abrir submittal existente ]
   [ Cargar ficha a BD ]       [ Gestionar BD ]

Este archivo contiene DOS partes:
  A) Funciones de ORQUESTACION de entregables (sin tkinter): reutilizan el motor
     de carATulas v2.6 (``generate_caratulas.py``) y replican la compilacion de
     CMPs/Excel con ``pypdf``/``openpyxl``. Son importables y testeables solas.
  B) La GUI (tkinter), que solo se carga si tkinter esta disponible.

Sincronizacion (v3.1.0, reemplaza a OneDrive):
  - Al abrir: ``sync_indice()`` (git pull) en segundo plano, con barra de estado.
  - Al cargar fichas o generar un submittal: ``git_push()``.
  - Los conflictos se resuelven solos (fusion por registro) y se avisa al usuario.
  - Sin conexion: se trabaja con la copia local y se sube al reconectar.
  - YA NO EXISTE el ``.lock`` ni el dialogo de "forzar acceso": git se encarga.
================================================================================
"""

import os
import re
import sys
import json
import shutil
import logging
import threading
import importlib.util
from pathlib import Path

import bd_manager
import fuzzy_search
import git_bd
import nomenclatura
import ocr_extractor
import updater_gh

VERSION = "3.2.1"
BASE_DIR = Path(__file__).resolve().parent
PIN_MODO_DEV = "9119"

# Colores tema (refresh visual v3.3.0: paleta azul/naranja, WCAG AA)
AZUL_ES = "#2563EB"          # Primary
AZUL_CLARO = "#3B82F6"       # Secondary (hover/acentos)
NARANJA_CTA = "#F97316"      # Accent / CTA principal ("Generar", acciones clave)
GRIS_BG = "#F8FAFC"          # Background
GRIS_TEXTO = "#1E293B"       # Foreground (texto principal)
GRIS_TEXTO_SUAVE = "#475569"  # texto secundario/ayuda
BORDE_SUAVE = "#CBD5E1"      # bordes de tarjetas ("vidrio" en modo claro)
ROJO_ES = "#DC2626"          # Danger (errores, acciones destructivas)
VERDE_OK = "#16A34A"         # Success

IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")

# Plantilla -> (archivo, logo relativo, clave de contexto del logo)
CARATULAS = {
    "clasica": ("template_caratula.html",
                "Tabla visual refresh/assets/logo_es_crop.png", "logo_path"),
    "ministerio_salud": ("template_ministerio_salud.html",
                         "Tabla visual refresh/assets/ministerio_salud_banner.png",
                         "logo_ministerio"),
}

# --------------------------------------------------------------------------
# LOGGING
# --------------------------------------------------------------------------
LOG_PATH = bd_manager.dir_appdata() / "app.log"
logger = logging.getLogger("submitals_v3")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    try:
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
    except Exception:
        pass


# ==========================================================================
# PARTE A) ORQUESTACION DE ENTREGABLES  (reutiliza el motor v2.6)
# ==========================================================================
def _cargar_motor(base_dir=BASE_DIR):
    """Carga ``generate_caratulas.py`` como modulo (import dinamico, igual que
    hace la GUI v2.6). Devuelve el modulo ``gc``."""
    ruta = Path(base_dir) / "generate_caratulas.py"
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontro el motor de carATulas: {ruta}")
    spec = importlib.util.spec_from_file_location("generate_caratulas", str(ruta))
    gc = importlib.util.module_from_spec(spec)
    sys.modules["generate_caratulas"] = gc
    spec.loader.exec_module(gc)
    return gc


def _ctx_proyecto(tipo, proyecto, item):
    """Construye el contexto de proyecto para la plantilla de carATula."""
    dp = proyecto.get("datos_procedimiento", {}) or {}
    if tipo == "ministerio_salud":
        proj = proyecto.get("datos_proyecto", {}) or {}
        return {
            "proyecto": proj.get("proyecto", dp.get("detalle", "")),
            "cliente": proj.get("cliente", dp.get("institucion", "")),
            "contrato": proj.get("contrato", dp.get("numero_procedimiento", "")),
            "monto": proj.get("monto", dp.get("monto", "")),
            "plazo": proj.get("plazo", dp.get("plazo", "")),
            "nombre_cargo": proj.get("nombre_cargo", ""),
            "fecha": proj.get("fecha", ""),
            "fecha_emision": proj.get("fecha_emision", ""),
            "fecha_revision": proj.get("fecha_revision", ""),
            "registro": item.get("consecutivo", ""),
            "revisa": proj.get("revisa", ""),
            "version": proj.get("version", "v1"),
            "documentacion_tecnica": "",
            "observaciones_material": item.get("aspectos_adicionales", ""),
            "observaciones_respuesta": "",
            "estado": "",
        }
    # clasica
    return {
        "numero_procedimiento": dp.get("numero_procedimiento", ""),
        "nombre_institucion": dp.get("institucion", ""),
        "detalle_procedimiento": dp.get("detalle", ""),
        "duracion_contrato": dp.get("plazo", ""),
        "monto": dp.get("monto", ""),
    }


def generar_caratulas(base_dir, datos, tipo, proyecto, log=print):
    """Genera la carATula PDF de cada material usando el motor v2.6."""
    from jinja2 import Template
    gc = _cargar_motor(base_dir)
    engines = gc.available_engines()
    if not engines:
        raise RuntimeError("No hay motor de PDF (instale playwright + chromium)")

    tpl_rel, logo_rel, logo_key = CARATULAS.get(tipo, CARATULAS["clasica"])
    tpl_text = (Path(base_dir) / tpl_rel).read_text(encoding="utf-8")
    template = Template(tpl_text)

    logo_file = Path(base_dir) / logo_rel
    if logo_file.exists():
        gc.LOGO_URI = gc.file_uri(logo_file)
    else:
        gc.LOGO_URI = ""
        log(f"AVISO: logo no encontrado ({logo_rel}); se genera sin logo")

    ok = 0
    for item in datos["materiales"]:
        extra = _ctx_proyecto(tipo, proyecto, item)
        if tipo == "ministerio_salud":
            extra["logo_ministerio"] = gc.LOGO_URI
        try:
            gc.process_material(item, template, engines, extra_ctx=extra)
            ok += 1
        except Exception as e:
            log(f"ERROR carATula {item.get('consecutivo')}: {e}")
    log(f"CarATulas generadas: {ok}/{len(datos['materiales'])}")
    return ok


# --- Compilacion de PDFs (pypdf), replicando la logica de v2.6 ---------------
def imagen_a_pdf_reader(path):
    """Convierte una imagen a un PdfReader de una pagina (via PIL)."""
    import io
    from PIL import Image
    from pypdf import PdfReader
    with Image.open(path) as im:
        im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="PDF", resolution=150.0)
    buf.seek(0)
    return PdfReader(buf)


def generar_compilado(caratula_path, doc_paths, out_path, log=print):
    """Une la carATula (solo 1a pagina, conservando campos editables) con las
    fichas de la carpeta -> PDF ``-CMP.pdf``. Replica ``generar_compilado`` v2.6.
    """
    from pypdf import PdfWriter, PdfReader
    w = PdfWriter()
    if caratula_path and Path(caratula_path).exists():
        try:
            w.append(PdfReader(str(caratula_path)), pages=(0, 1))
        except Exception:
            w.add_page(PdfReader(str(caratula_path)).pages[0])
    anexados = 0
    for d in sorted(doc_paths, key=lambda x: x.name.lower()):
        ext = d.suffix.lower()
        try:
            if ext == ".pdf":
                w.append(PdfReader(str(d)))
                anexados += 1
            elif ext in IMG_EXT:
                w.append(imagen_a_pdf_reader(d))
                anexados += 1
        except Exception as e:
            log(f"AVISO: no se anexo '{d.name}' ({e})")
    tmp = out_path.with_suffix(".cmp.tmp")
    with open(tmp, "wb") as f:
        w.write(f)
    os.replace(tmp, out_path)
    w.close()
    return anexados


def _docs_carpeta(carpeta):
    """Documentos anexables de una carpeta (excluye carATula y compilados)."""
    out = []
    for p in sorted(carpeta.iterdir()):
        if not p.is_file():
            continue
        up = p.name.upper()
        if up.startswith("CARATULA") or up.endswith("-CMP.PDF"):
            continue
        if p.suffix.lower() == ".pdf" or p.suffix.lower() in IMG_EXT:
            out.append(p)
    return out


def compilar_cmps(datos, log=print):
    """Genera el ``-CMP.pdf`` de cada material (carATula + fichas)."""
    total = 0
    for mat in datos["materiales"]:
        carpeta = Path(mat["ruta_carpeta"])
        if not carpeta.is_dir():
            continue
        caratulas = sorted(carpeta.glob("CARATULA*.pdf"))
        caratula = caratulas[0] if caratulas else None
        docs = _docs_carpeta(carpeta)
        nombre = bd_manager.sanitizar_nombre(f"{mat['consecutivo']}-{mat['nombre']}-CMP") + ".pdf"
        out = carpeta / nombre
        try:
            generar_compilado(caratula, docs, out, log=log)
            mat["compilado_generado"] = nombre
            total += 1
        except Exception as e:
            log(f"ERROR CMP {mat['consecutivo']}: {e}")
    log(f"CMPs por material generados: {total}")
    return total


def compilar_disciplinas(destino, log=print):
    """Genera ``CMP SUBMITTAL <DISCIPLINA>.pdf`` por cada carpeta madre presente.
    Replica ``compilar_por_disciplina`` v2.6."""
    from pypdf import PdfWriter, PdfReader
    destino = Path(destino)
    generados = []
    for cat, madre in bd_manager.CATEGORIAS.items():
        carpeta_disc = destino / madre
        if not carpeta_disc.is_dir():
            continue
        entradas = []
        for sub in sorted(carpeta_disc.iterdir()):
            if not sub.is_dir():
                continue
            m = re.match(rf"^({cat})(\d+)-(.*)$", sub.name)
            if m:
                entradas.append((int(m.group(2)), sub))
        entradas.sort(key=lambda e: e[0])
        if not entradas:
            continue
        w = PdfWriter()
        procesados = 0
        for _n, sub in entradas:
            caratulas = sorted(sub.glob("CARATULA*.pdf"))
            if not caratulas:
                log(f"AVISO {madre}: '{sub.name}' sin carATula, se omite")
                continue
            try:
                w.append(PdfReader(str(caratulas[0])))
            except Exception as e:
                log(f"AVISO {madre}: carATula ilegible en '{sub.name}' ({e})")
                continue
            for d in _docs_carpeta(sub):
                try:
                    if d.suffix.lower() == ".pdf":
                        w.append(PdfReader(str(d)))
                    elif d.suffix.lower() in IMG_EXT:
                        w.append(imagen_a_pdf_reader(d))
                except Exception as e:
                    log(f"AVISO {madre}: no se anexo '{sub.name}/{d.name}' ({e})")
            procesados += 1
        if procesados == 0:
            w.close()
            continue
        singular = bd_manager.DISCIPLINA_SINGULAR.get(madre, madre)
        out = carpeta_disc / f"CMP SUBMITTAL {singular}.pdf"
        tmp = out.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            w.write(f)
        os.replace(tmp, out)
        w.close()
        generados.append(out.name)
    log(f"Compilados por disciplina: {', '.join(generados) or '(ninguno)'}")
    return generados


# --- Excel (openpyxl), replicando columnas de v2.6 ---------------------------
def _agrupar_por_disciplina(materiales):
    nombres = {"ARQ": "Arquitectónicos", "ESTR": "Estructurales",
               "MEC": "Mecánicos", "ELEC": "Eléctricos"}
    grupos = {}
    for it in materiales:
        pref = re.sub(r"\d.*", "", str(it.get("consecutivo", ""))).upper()
        grupos.setdefault(nombres.get(pref, pref or "Otros"), []).append(it)
    return grupos


def generar_excel_submittal(datos, destino):
    """``Guía Submittal.xlsx`` (para administracion): Consecutivo | Descripción |
    Aprobación | Observaciones (las 2 ultimas en blanco)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    grupos = _agrupar_por_disciplina(datos["materiales"])
    if not any(grupos.values()):
        return {"exitoso": False, "error": "Sin materiales"}
    wb = Workbook(); wb.remove(wb.active)
    hfill = PatternFill("solid", fgColor="4472C4")
    hfont = Font(color="FFFFFF", bold=True)
    halign = Alignment(horizontal="center")
    for hoja, items in grupos.items():
        ws = wb.create_sheet(title=hoja[:31])
        for col, h in enumerate(["Consecutivo", "Descripción", "Aprobación", "Observaciones"], 1):
            c = ws.cell(row=1, column=col, value=h)
            c.fill = hfill; c.font = hfont; c.alignment = halign
        for i, it in enumerate(items, 2):
            ws.cell(row=i, column=1, value=it.get("consecutivo", ""))
            ws.cell(row=i, column=2, value=it.get("nombre", ""))
        for col, w in zip("ABCD", (15, 60, 20, 40)):
            ws.column_dimensions[col].width = w
    out = Path(destino) / "Guía Submittal.xlsx"
    wb.save(out)
    return {"exitoso": True, "archivo": str(out), "total_materiales": len(datos["materiales"])}


def generar_excel_materiales(datos, destino):
    """``Guía interna materiales.xlsx``: Consecutivo | Familia | Descripción |
    Normativa | Estado | Proveedor."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    grupos = _agrupar_por_disciplina(datos["materiales"])
    if not any(grupos.values()):
        return {"exitoso": False, "error": "Sin materiales"}
    wb = Workbook(); wb.remove(wb.active)
    hfill = PatternFill("solid", fgColor="4472C4")
    hfont = Font(color="FFFFFF", bold=True)
    halign = Alignment(horizontal="center")
    for hoja, items in grupos.items():
        ws = wb.create_sheet(title=hoja[:31])
        for col, h in enumerate(["Consecutivo", "Familia", "Descripción", "Normativa",
                                 "Estado", "Proveedor"], 1):
            c = ws.cell(row=1, column=col, value=h)
            c.fill = hfill; c.font = hfont; c.alignment = halign
        for i, it in enumerate(items, 2):
            ws.cell(row=i, column=1, value=it.get("consecutivo", ""))
            ws.cell(row=i, column=2, value=it.get("marca", ""))
            ws.cell(row=i, column=3, value=it.get("nombre", ""))
            ws.cell(row=i, column=4, value=it.get("normativa", "SIN ESPECIFICAR"))
            estado = "DISPONIBLE" if (it.get("estado") == "FICHA_DISPONIBLE"
                                      and not it.get("carpeta_vacia")) else "FALTANTE"
            ws.cell(row=i, column=5, value=estado)
        for col, w in zip("ABCDEF", (15, 25, 60, 30, 15, 25)):
            ws.column_dimensions[col].width = w
    out = Path(destino) / "Guía interna materiales.xlsx"
    wb.save(out)
    return {"exitoso": True, "archivo": str(out), "total_materiales": len(datos["materiales"])}


def limpiar_entregables(destino, log=print):
    """Borra carATulas, CMPs por material y compilados/Excel previos para poder
    regenerar TODO limpiamente (usado al editar un submittal)."""
    destino = Path(destino)
    for patron in ("Guía Submittal.xlsx", "Guía interna materiales.xlsx"):
        p = destino / patron
        if p.exists():
            try: p.unlink()
            except Exception: pass
    for madre in bd_manager.CATEGORIAS.values():
        cm = destino / madre
        if not cm.is_dir():
            continue
        for p in cm.glob("CMP SUBMITTAL *.pdf"):
            try: p.unlink()
            except Exception: pass
        for sub in cm.iterdir():
            if not sub.is_dir():
                continue
            for p in list(sub.glob("CARATULA*.pdf")) + list(sub.glob("*-CMP.pdf")):
                try: p.unlink()
                except Exception: pass
    log("Entregables previos limpiados")


def generar_entregables(bd, proyecto, destino, tipo="clasica", log=print,
                        con_caratulas=True, limpiar=True):
    """Pipeline completo de generacion de entregables desde la BD:

      1. Valida el submittal.
      2. Materializa la carpeta destino (arbol + copia de fichas + JSONs).
      3. (opcional) Genera carATulas con el motor v2.6.
      4. Compila los CMP por material.
      5. Compila los CMP por disciplina.
      6. Genera los dos Excel.

    Devuelve un dict con el resultado. Lanza ``bd_manager.BDError`` si la
    validacion falla.
    """
    ok, errores = bd.validar_proyecto(proyecto)
    if not ok:
        raise bd_manager.BDError("Validacion fallida:\n - " + "\n - ".join(errores))

    destino = Path(destino)
    if limpiar and destino.exists():
        limpiar_entregables(destino, log=log)

    json_path = bd.materializar_proyecto(proyecto, destino)
    datos = json.loads(json_path.read_text(encoding="utf-8"))
    log(f"Materializado en {destino} ({len(datos['materiales'])} materiales)")

    if con_caratulas:
        generar_caratulas(destino if (destino / "generate_caratulas.py").exists() else BASE_DIR,
                          datos, tipo, proyecto, log=log)

    compilar_cmps(datos, log=log)
    compilar_disciplinas(destino, log=log)
    r1 = generar_excel_submittal(datos, destino)
    r2 = generar_excel_materiales(datos, destino)

    # Persistir estado del submittal
    proyecto["entregables_generados"] = True
    proyecto["tipo_caratula"] = tipo
    bd.guardar_submittal(proyecto, destino=destino)
    # Reescribir datos_materiales con compilado_generado actualizado
    json_path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"destino": str(destino), "materiales": len(datos["materiales"]),
            "excel_submittal": r1.get("exitoso"), "excel_materiales": r2.get("exitoso")}


# ==========================================================================
# PARTE B) GUI (tkinter)
# ==========================================================================
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    try:
        import customtkinter as ctk
    except ImportError:
        # Dependencia nueva del refresh visual v3.3.0: si falta, se instala
        # sola (solo tiene sentido corriendo el .py con un interprete real;
        # el .exe empaquetado ya la trae incluida via el .spec de PyInstaller).
        if getattr(sys, "frozen", False):
            raise
        import subprocess
        print("Instalando dependencia 'customtkinter' (primera vez)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "customtkinter"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        import customtkinter as ctk
    _TK_OK = True
except Exception:
    _TK_OK = False


if _TK_OK:

    # -------------------------------------------------------------------
    # Sistema de diseno v3.3.0: modo claro fijo (ver AVOID en el spec: nada
    # de modo oscuro por defecto), tipografia Inter con reserva a Segoe UI
    # si el sistema no la tiene instalada.
    # -------------------------------------------------------------------
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    FUENTE = "Segoe UI"
    try:
        import tkinter.font as _tkfont
        _r = tk.Tk()
        _r.withdraw()
        if "Inter" in _tkfont.families():
            FUENTE = "Inter"
        _r.destroy()
    except Exception:
        pass

    def _fuente(size=11, weight="normal"):
        """Fuente del sistema de diseno (``CTkFont``: escala con el DPI)."""
        return ctk.CTkFont(family=FUENTE, size=size, weight=weight)

    def _configurar_estilo_ttk():
        """Reskin del ``ttk.Treeview`` (unico widget ttk que sigue en uso;
        CustomTkinter no trae reemplazo) a la paleta nueva."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", background="white", fieldbackground="white",
                        foreground=GRIS_TEXTO, rowheight=26, borderwidth=0,
                        font=(FUENTE, 10))
        style.configure("Treeview.Heading", background=AZUL_ES, foreground="white",
                        font=(FUENTE, 10, "bold"), relief="flat")
        style.map("Treeview.Heading", background=[("active", AZUL_CLARO)])
        style.map("Treeview", background=[("selected", AZUL_CLARO)],
                  foreground=[("selected", "white")])

    # Color de "hover" de cada color solido del tema (mismo tono, mas oscuro).
    _HOVER = {AZUL_ES: "#1D4ED8", AZUL_CLARO: "#2563EB", NARANJA_CTA: "#EA580C",
             ROJO_ES: "#B91C1C", VERDE_OK: "#15803D", "white": "#F1F5F9"}

    def _tarjeta(parent, **kw):
        """Frame estilo 'tarjeta': fondo blanco, esquinas redondeadas y borde
        sutil. Es la aproximacion de Glassmorphism que CustomTkinter puede dar
        sin blur real (Tkinter no soporta backdrop-filter)."""
        kw.setdefault("fg_color", "white")
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", BORDE_SUAVE)
        return ctk.CTkFrame(parent, **kw)

    def _boton(parent, text, command, color=AZUL_ES, texto_color="white",
              ancho=140, alto=36, **kw):
        """Boton estandar del sistema de diseno (esquinas redondeadas, hover
        suave, tipografia consistente)."""
        return ctk.CTkButton(parent, text=text, command=command, fg_color=color,
                             hover_color=_HOVER.get(color, color),
                             text_color=texto_color, width=ancho, height=alto,
                             corner_radius=10, font=_fuente(11, "bold"), **kw)

    def _boton_secundario(parent, text, command, ancho=140, alto=32, **kw):
        """Boton de accion secundaria: contorno azul sobre fondo blanco."""
        return ctk.CTkButton(parent, text=text, command=command,
                             fg_color="white", hover_color="#EFF6FF",
                             text_color=AZUL_ES, border_width=1,
                             border_color=AZUL_ES, width=ancho, height=alto,
                             corner_radius=10, font=_fuente(11), **kw)

    def _traer_al_frente(win):
        """Fuerza que una ventana nueva quede al frente y con el foco.

        En Windows, un Toplevel recien creado a veces aparece detras de la
        ventana principal (el usuario "pierde" la ventana que tenia abierta).
        lift()/focus_force() no siempre alcanzan; el truco de -topmost
        momentaneo si funciona de forma consistente.
        """
        win.lift()
        win.attributes("-topmost", True)
        win.after_idle(lambda: win.attributes("-topmost", False))
        win.focus_force()

    class DatosProyectoDialog(ctk.CTkToplevel):
        """Dialogo para capturar los datos del procedimiento (obligatorios)."""

        def __init__(self, master, datos=None):
            super().__init__(master)
            self.title("Datos del Proyecto")
            self.resultado = None
            self.configure(fg_color=GRIS_BG, padx=16, pady=16)
            self.grab_set()
            datos = datos or {}
            campos = [
                ("numero_procedimiento", "Número de procedimiento"),
                ("institucion", "Institución"),
                ("detalle", "Detalle"),
                ("plazo", "Plazo"),
                ("monto", "Monto"),
            ]
            tarjeta = _tarjeta(self)
            tarjeta.pack(fill="both", expand=True, padx=4, pady=4)
            ctk.CTkLabel(tarjeta, text="Datos del Proyecto", font=_fuente(14, "bold"),
                        text_color=GRIS_TEXTO).grid(
                row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 10))
            self.vars = {}
            for i, (clave, etiqueta) in enumerate(campos, start=1):
                ctk.CTkLabel(tarjeta, text=etiqueta + ":", text_color=GRIS_TEXTO).grid(
                    row=i, column=0, sticky="e", pady=4, padx=(16, 6))
                v = tk.StringVar(value=datos.get(clave, ""))
                ctk.CTkEntry(tarjeta, textvariable=v, width=280, height=32,
                            corner_radius=8, border_color=BORDE_SUAVE).grid(
                    row=i, column=1, pady=4, padx=(0, 16))
                self.vars[clave] = v
            barra = ctk.CTkFrame(tarjeta, fg_color="transparent")
            barra.grid(row=len(campos) + 1, column=0, columnspan=2, pady=(14, 16))
            _boton(barra, "Guardar", self._guardar, color=AZUL_ES).pack(side="left", padx=6)
            _boton_secundario(barra, "Cancelar", self.destroy).pack(side="left", padx=6)
            _traer_al_frente(self)

        def _guardar(self):
            datos = {k: v.get().strip() for k, v in self.vars.items()}
            faltan = [k for k in bd_manager.CAMPOS_PROCEDIMIENTO if not datos.get(k)]
            if faltan:
                messagebox.showwarning("Datos incompletos",
                                       "Complete todos los campos:\n" + ", ".join(faltan))
                return
            self.resultado = datos
            self.destroy()


    class _PinDialog(ctk.CTkToplevel):
        """Pide un PIN enmascarado (reemplaza ``simpledialog.askstring`` con
        ``show='*'``, que CustomTkinter no ofrece de forma nativa)."""

        def __init__(self, master, titulo, mensaje):
            super().__init__(master)
            self.title(titulo)
            self.resultado = None
            self.configure(fg_color=GRIS_BG, padx=16, pady=16)
            self.resizable(False, False)
            self.grab_set()
            tarjeta = _tarjeta(self)
            tarjeta.pack(fill="both", expand=True)
            ctk.CTkLabel(tarjeta, text=mensaje, text_color=GRIS_TEXTO,
                        font=_fuente(11)).pack(padx=18, pady=(18, 8))
            self.v_pin = tk.StringVar()
            e = ctk.CTkEntry(tarjeta, textvariable=self.v_pin, show="*", width=200,
                             height=32, corner_radius=8, border_color=BORDE_SUAVE,
                             justify="center")
            e.pack(padx=18, pady=4)
            e.bind("<Return>", lambda _ev: self._ok())
            barra = ctk.CTkFrame(tarjeta, fg_color="transparent")
            barra.pack(pady=(12, 18))
            _boton(barra, "Aceptar", self._ok, color=AZUL_ES, ancho=110).pack(
                side="left", padx=6)
            _boton_secundario(barra, "Cancelar", self.destroy, ancho=110).pack(
                side="left", padx=6)
            _traer_al_frente(self)
            e.focus_set()

        def _ok(self):
            self.resultado = self.v_pin.get()
            self.destroy()


    class TablaMateriales(ctk.CTkFrame):
        """Tabla reutilizable de materiales seleccionados con agregar/editar/
        eliminar y renumeracion automatica de consecutivos."""

        def __init__(self, master, bd, materiales=None):
            super().__init__(master, fg_color="transparent")
            self.bd = bd
            self.materiales = list(materiales or [])
            self._build()
            self._refrescar()

        def _build(self):
            # Barra de busqueda
            top = ctk.CTkFrame(self, fg_color="transparent")
            top.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(top, text="Buscar material:", text_color=GRIS_TEXTO,
                        font=_fuente(11)).pack(side="left")
            self.var_busq = tk.StringVar()
            e = ctk.CTkEntry(top, textvariable=self.var_busq, width=280, height=32,
                             corner_radius=8, border_color=BORDE_SUAVE)
            e.pack(side="left", padx=6)
            e.bind("<KeyRelease>", lambda _ev: self._sugerir())
            _boton(top, "＋ Cargar ficha nueva a BD", self._cargar_ficha,
                  color=AZUL_CLARO, ancho=200).pack(side="right")

            self.lst = tk.Listbox(self, height=5, font=(FUENTE, 10),
                                  bg="white", fg=GRIS_TEXTO,
                                  selectbackground=AZUL_CLARO, selectforeground="white",
                                  relief="solid", borderwidth=1,
                                  highlightthickness=1, highlightbackground=BORDE_SUAVE,
                                  highlightcolor=AZUL_ES)
            self.lst.pack(fill="x")
            self.lst.bind("<Double-Button-1>", lambda _ev: self._agregar_seleccion())

            self.tree = ttk.Treeview(self, columns=("cons", "nombre", "marca"),
                                     show="headings", height=10)
            for c, t, w in (("cons", "Consecutivo", 90), ("nombre", "Nombre", 320),
                            ("marca", "Marca", 180)):
                self.tree.heading(c, text=t); self.tree.column(c, width=w)
            self.tree.pack(fill="both", expand=True, pady=8)

            bar = ctk.CTkFrame(self, fg_color="transparent")
            bar.pack(fill="x")
            _boton_secundario(bar, "Editar marca(s)", self._editar, ancho=140).pack(
                side="left", padx=4)
            _boton(bar, "Eliminar", self._eliminar, color=ROJO_ES, ancho=110).pack(
                side="left", padx=4)
            self._sug = []

        def _sugerir(self):
            q = self.var_busq.get().strip()
            self.lst.delete(0, "end")
            self._sug = self.bd.buscar(q) if q else []
            for r in self._sug:
                # Se muestra el nombre descriptivo completo: es lo que permite
                # distinguir dos fichas del mismo material.
                self.lst.insert("end", f"{bd_manager.BDManager.nombre_de(r)}  ·  "
                                       f"{r['categoria']}  ({int(r['_similitud']*100)}%)")
            if q and not self._sug:
                self.lst.insert("end", "❌ No encontrado — use 'Cargar ficha nueva a BD'")

        def _agregar_seleccion(self):
            sel = self.lst.curselection()
            if not sel or sel[0] >= len(self._sug):
                return
            ficha = self._sug[sel[0]]
            cat = ficha["categoria"]
            cons = self._siguiente_consecutivo(cat)
            # El material hereda el nombre descriptivo SIN la marca (la marca ya
            # tiene su propia columna en carátulas y Excel). Así dos tubos del
            # mismo tipo no aparecen como dos filas idénticas.
            nombre = nomenclatura.nombre_sin_marca(
                bd_manager.BDManager.nombre_de(ficha), ficha.get("marca", ""))
            self.materiales.append({
                "consecutivo": cons, "id_ficha_bd": ficha["id"],
                "nombre_material": nombre or ficha["nombre_material"],
                "marca": ficha["marca"],
                "categoria": cat, "marcas_alternativas": [], "justificacion_stock": False,
            })
            self.var_busq.set(""); self._sugerir(); self._refrescar()

        def _siguiente_consecutivo(self, cat):
            nums = [int(re.match(rf"{cat}(\d+)", m["consecutivo"]).group(1))
                    for m in self.materiales
                    if re.match(rf"{cat}(\d+)", m.get("consecutivo", ""))]
            return f"{cat}{(max(nums) + 1 if nums else 1):02d}"

        def _renumerar(self):
            contadores = {}
            for m in sorted(self.materiales, key=lambda x: bd_manager._clave_orden(x["consecutivo"])):
                cat = m["categoria"]
                contadores[cat] = contadores.get(cat, 0) + 1
                m["consecutivo"] = f"{cat}{contadores[cat]:02d}"

        def _refrescar(self):
            self._renumerar()
            self.materiales.sort(key=lambda x: bd_manager._clave_orden(x["consecutivo"]))
            for i in self.tree.get_children():
                self.tree.delete(i)
            for m in self.materiales:
                marca = bd_manager._marcas_material(m, {})
                self.tree.insert("", "end", iid=m["consecutivo"],
                                 values=(m["consecutivo"], m["nombre_material"], marca))

        def _sel_material(self):
            sel = self.tree.selection()
            if not sel:
                return None
            return next((m for m in self.materiales if m["consecutivo"] == sel[0]), None)

        def _editar(self):
            m = self._sel_material()
            if not m:
                return
            alt = ", ".join(m.get("marcas_alternativas", []))
            top = ctk.CTkToplevel(self)
            top.title("Editar marcas"); top.grab_set()
            top.configure(fg_color=GRIS_BG, padx=14, pady=14)
            tarjeta = _tarjeta(top); tarjeta.pack(fill="both", expand=True)
            ctk.CTkLabel(tarjeta, text=f"{m['consecutivo']} — {m['nombre_material']}",
                        font=_fuente(11, "bold"), text_color=GRIS_TEXTO).grid(
                row=0, column=0, columnspan=2, padx=16, pady=(16, 10))
            ctk.CTkLabel(tarjeta, text="Marca principal:", text_color=GRIS_TEXTO).grid(
                row=1, column=0, sticky="e", pady=4, padx=(16, 6))
            v_p = tk.StringVar(value=m["marca"])
            ctk.CTkEntry(tarjeta, textvariable=v_p, width=220, height=32,
                        corner_radius=8, border_color=BORDE_SUAVE).grid(
                row=1, column=1, padx=(0, 16))
            ctk.CTkLabel(tarjeta, text="Marcas alternativas (coma):",
                        text_color=GRIS_TEXTO).grid(row=2, column=0, sticky="e",
                                                    pady=4, padx=(16, 6))
            v_a = tk.StringVar(value=alt)
            ctk.CTkEntry(tarjeta, textvariable=v_a, width=220, height=32,
                        corner_radius=8, border_color=BORDE_SUAVE).grid(
                row=2, column=1, padx=(0, 16))
            v_s = tk.BooleanVar(value=m.get("justificacion_stock", False))
            ctk.CTkCheckBox(tarjeta, text="Justificar por stock (marcas alternativas aprobadas)",
                           variable=v_s, text_color=GRIS_TEXTO,
                           fg_color=AZUL_ES, hover_color=_HOVER[AZUL_ES]).grid(
                row=3, column=0, columnspan=2, sticky="w", padx=16, pady=4)

            def _ok():
                m["marca"] = v_p.get().strip()
                m["marcas_alternativas"] = [a.strip() for a in v_a.get().split(",") if a.strip()]
                m["justificacion_stock"] = v_s.get()
                top.destroy(); self._refrescar()
            _boton(tarjeta, "Confirmar", _ok, color=AZUL_ES).grid(
                row=4, column=0, columnspan=2, pady=(12, 16))
            _traer_al_frente(top)

        def _eliminar(self):
            m = self._sel_material()
            if m and messagebox.askyesno("Eliminar", f"¿Quitar {m['consecutivo']} — {m['nombre_material']}?"):
                self.materiales.remove(m); self._refrescar()

        def _cargar_ficha(self):
            VentanaCargarFicha(self.winfo_toplevel(), self.bd,
                               al_terminar=lambda: (self._sugerir()))


    class VentanaCargarFicha(ctk.CTkToplevel):
        """Flujo 3: cargar una o varias fichas a la BD (con extraccion OCR/IA)."""

        def __init__(self, master, bd, al_terminar=None):
            super().__init__(master)
            self.bd = bd; self.al_terminar = al_terminar
            self._cancelado = False
            self._cerrada = False
            self._procesando = False
            self._prog_max = 1
            self.title("Cargar ficha(s) a la BD")
            self.configure(fg_color=GRIS_BG, padx=16, pady=16)
            self.grab_set()
            tarjeta = _tarjeta(self); tarjeta.pack(fill="both", expand=True, padx=4, pady=4)
            ctk.CTkLabel(tarjeta, text="Cargar fichas técnicas a la Base de Datos",
                        font=_fuente(13, "bold"), text_color=GRIS_TEXTO).pack(
                anchor="w", padx=18, pady=(18, 0))
            botones = ctk.CTkFrame(tarjeta, fg_color="transparent")
            botones.pack(anchor="w", padx=18, pady=8)
            self.btn_archivos = _boton(botones, "Seleccionar archivo(s)…",
                                       self._seleccionar, color=AZUL_ES, ancho=190)
            self.btn_archivos.pack(side="left")
            self.btn_carpetas = _boton(botones, "Seleccionar carpeta(s)…",
                                       self._seleccionar_carpetas, color=AZUL_ES, ancho=190)
            self.btn_carpetas.pack(side="left", padx=(8, 0))
            self.btn_cancelar = _boton(botones, "⛔ Cancelar extracción",
                                       self._cancelar, color=ROJO_ES, ancho=170)
            self.btn_cancelar.configure(state="disabled")
            self.btn_cancelar.pack(side="left", padx=(8, 0))
            self.prog = ctk.CTkProgressBar(tarjeta, height=10, corner_radius=5,
                                           progress_color=AZUL_ES)
            self.prog.set(0)
            self.prog.pack(fill="x", padx=18, pady=4)
            self.txt = ctk.CTkTextbox(tarjeta, height=280, corner_radius=10,
                                      fg_color="#0F172A", text_color="#4ADE80",
                                      font=("Consolas", 10))
            self.txt.pack(fill="both", expand=True, padx=18, pady=(4, 8))
            self.btn_cerrar = _boton_secundario(tarjeta, "Cerrar", self._on_close, ancho=120)
            self.btn_cerrar.pack(pady=(0, 18))
            self.protocol("WM_DELETE_WINDOW", self._on_close)
            _traer_al_frente(self)

        def _on_close(self):
            if self._procesando:
                if not messagebox.askyesno(
                        "Cancelar extracción",
                        "Hay una extracción en curso. ¿Cancelarla y cerrar la ventana?"):
                    return
                self._cancelado = True
            self._cerrada = True
            self.destroy()

        def _cancelar(self):
            self._cancelado = True
            self.btn_cancelar.config(state="disabled")
            self._log("\n⛔ Cancelando… se detendrá después del archivo en curso.")

        def _log(self, msg):
            self.txt.insert("end", msg + "\n"); self.txt.see("end"); self.update_idletasks()

        EXTENSIONES = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff")

        def _seleccionar(self):
            rutas = filedialog.askopenfilenames(
                title="Fichas técnicas",
                filetypes=[("Fichas", "*.pdf *.png *.jpg *.jpeg *.tif *.tiff"), ("Todos", "*.*")])
            if not rutas:
                return
            self._procesar_archivos(rutas)

        def _seleccionar_carpetas(self):
            """Elige varias carpetas (una a la vez) y extrae todas las fichas
            técnicas que encuentre dentro de ellas, incluidas subcarpetas."""
            carpetas = []
            while True:
                titulo = "Seleccione una carpeta con fichas técnicas"
                if carpetas:
                    titulo += f"  (ya elegidas: {len(carpetas)} — Cancelar para terminar)"
                c = filedialog.askdirectory(title=titulo)
                if not c:
                    break
                carpetas.append(c)

            if not carpetas:
                return

            rutas = []
            for c in carpetas:
                rutas.extend(str(p) for p in Path(c).rglob("*")
                             if p.is_file() and p.suffix.lower() in self.EXTENSIONES)

            if not rutas:
                messagebox.showinfo(
                    "Sin fichas",
                    f"No se encontraron archivos de ficha (PDF/imagen) en "
                    f"{len(carpetas)} carpeta(s) seleccionada(s).")
                return

            self._log(f"📁 {len(carpetas)} carpeta(s) escaneada(s) — "
                      f"{len(rutas)} ficha(s) encontrada(s).")
            self._procesar_archivos(rutas)

        def _procesar_archivos(self, rutas):
            self._rutas = list(rutas)
            self._indice = 0
            self._ok = self._adv = self._fallo = 0
            self._cancelado = False
            self._procesando = True
            self._prog_max = len(self._rutas) or 1
            self.prog.set(0)
            self.btn_archivos.config(state="disabled")
            self.btn_carpetas.config(state="disabled")
            self.btn_cancelar.config(state="normal")
            self._procesar_siguiente()

        def _procesar_siguiente(self):
            if self._cerrada:
                return
            if self._cancelado or self._indice >= len(self._rutas):
                self._finalizar_lote()
                return

            r = self._rutas[self._indice]
            i = self._indice + 1
            self._indice += 1
            self._log(f"[{i}/{len(self._rutas)}] {Path(r).name} — extrayendo…")

            def trabajo():
                try:
                    datos, error = ocr_extractor.extraer([r]), None
                except Exception as e:
                    datos, error = None, e
                if self._cerrada:
                    return
                try:
                    self.after(0, lambda: self._tras_extraer(r, i, datos, error))
                except tk.TclError:
                    pass

            threading.Thread(target=trabajo, daemon=True).start()

        def _tras_extraer(self, r, i, datos, error):
            if self._cerrada:
                return
            if self._cancelado:
                self._finalizar_lote()
                return

            if error is not None:
                self._fallo += 1
                self._log(f"   ❌ {error}")
            else:
                res = self._preview(r, datos)
                accion = res.get("accion", "omitir")

                if accion == "omitir":
                    self._log("   (omitido)")
                elif accion == "usar_existente":
                    f = res["ficha"]
                    self._log(f"   ↩️ ya existía: {self.bd.nombre_de(f)}")
                elif accion == "reemplazar":
                    f = res["ficha"]
                    try:
                        self.bd.reemplazar_pdf_ficha(f["id"], r)
                        self._ok += 1
                        self._log(f"   🔁 PDF reemplazado en {self.bd.nombre_de(f)}")
                    except Exception as e:
                        self._fallo += 1; self._log(f"   ❌ {e}")
                else:
                    d = res.get("datos") or {}
                    try:
                        ficha = self.bd.agregar_ficha(r, d)
                        if d.get("_requiere_manual"):
                            self._adv += 1
                            self._log(f"   ⚠️ cargada (revisada a mano): {ficha['nombre_ficha']}")
                        else:
                            self._ok += 1
                            self._log(f"   ✅ {ficha['nombre_ficha']}")
                    except Exception as e:
                        self._fallo += 1; self._log(f"   ❌ {e}")

            self.prog.set(i / self._prog_max)
            self._procesar_siguiente()

        def _finalizar_lote(self):
            self._procesando = False
            self.btn_archivos.config(state="normal")
            self.btn_carpetas.config(state="normal")
            self.btn_cancelar.config(state="disabled")
            if self._cancelado:
                self._log(f"\n⛔ Extracción cancelada por el usuario "
                          f"({self._indice}/{len(self._rutas)} archivo(s) revisados).")
            self._log(f"\nResultado: ✅ {self._ok} ok · ⚠️ {self._adv} advertencias · "
                      f"❌ {self._fallo} fallos")
            if self._ok + self._adv:
                self._subir(self._ok + self._adv)
            if self.al_terminar:
                self.al_terminar()

        def _subir(self, cantidad):
            """Sube las fichas nuevas a GitHub (Flujo 2, paso 6)."""
            self._log("\n🔄 Subiendo a GitHub…")
            r = self.bd.git_push(f"agregar {cantidad} ficha(s) desde "
                                 f"{bd_manager.socket.gethostname()}")
            if r.get("desactivado"):
                self._log("   (sincronización desactivada: BD local)")
            elif r.get("subido"):
                extra = (f" · {r['conflictos']} conflicto(s) resuelto(s)"
                         if r.get("conflictos") else "")
                self._log(f"   ✅ Cambios subidos a GitHub{extra}")
            elif r.get("offline"):
                self._log("   📡 Sin conexión: las fichas quedaron guardadas y se "
                          "subirán al reconectar")
            elif r.get("auth"):
                self._log("   🔑 Falta el token de GitHub: use '⚙️ Configuración' "
                          "en la ventana principal")
            elif r.get("nada_que_subir"):
                self._log("   (sin cambios por subir)")
            else:
                self._log(f"   ⚠️ No se pudo subir: {r.get('error', 'error desconocido')}")

        def _preview(self, ruta, datos):
            """Abre el formulario de revisión y devuelve la acción elegida."""
            d = DialogoRevisarFicha(self, self.bd, ruta, datos)
            self.wait_window(d)
            return d.resultado


    class DialogoRevisarFicha(ctk.CTkToplevel):
        """Revisión de una ficha antes de guardarla (Mejora 1, paso 4).

        Muestra el NOMBRE AUTO-GENERADO arriba, editable, y lo recalcula solo
        mientras el usuario no lo escriba a mano. Antes de guardar:

          * exige los campos obligatorios;
          * exige que el nombre sea distinguible (dimensiones, presentación o
            modelo), para que no vuelvan a entrar fichas como "Tubería
            Estructural" que no se pueden diferenciar;
          * si el nombre ya existe en la BD, ofrece usar la ficha existente,
            reemplazar su PDF o guardar esta como variante.
        """

        CAMPOS = [
            ("nombre_material", "Nombre del material"),
            ("marca", "Marca"),
            ("categoria", "Categoría (ARQ/ESTR/MEC/ELEC)"),
            ("dimensiones", "Dimensiones (ej: 8\"x8\"x3/16\", 60x60 cm)"),
            ("tipo_producto", "Tipo / forma (ej: cuadrado, rectangular)"),
            ("especificacion", "Especificación / modelo (ej: CH 13, QO260)"),
            ("normativa", "Normativa (no entra en el nombre)"),
            ("descripcion_corta", "Descripción corta / presentación"),
        ]

        def __init__(self, master, bd, ruta, datos, titulo=None, es_edicion=False):
            super().__init__(master)
            self.bd = bd
            self.datos_origen = dict(datos or {})
            self.es_edicion = es_edicion
            self.resultado = {"accion": "omitir"}
            self._nombre_auto = ""
            self._nombre_editado = bool(self.datos_origen.get("nombre_ficha_manual"))
            self.title(titulo or f"Revisar: {Path(ruta).name if ruta else 'ficha'}")
            self.configure(fg_color=GRIS_BG, padx=16, pady=14)
            self.grab_set()
            self._construir()
            self._recalcular()
            _traer_al_frente(self)

        # ------------------------------------------------------------ armado
        def _construir(self):
            tarjeta = _tarjeta(self)
            tarjeta.pack(fill="both", expand=True, padx=4, pady=4)
            tarjeta.grid_columnconfigure(1, weight=1)
            pad = dict(padx=16)
            fila = 0
            if not self.es_edicion:
                metodo = self.datos_origen.get("_metodo", "?")
                manual = self.datos_origen.get("_requiere_manual")
                ctk.CTkLabel(tarjeta, text=f"Método de extracción: {metodo}"
                            + ("  ·  revise los datos" if manual else ""),
                            justify="left",
                            text_color=(ROJO_ES if manual else VERDE_OK)).grid(
                    row=fila, column=0, columnspan=3, sticky="w", **pad, pady=(16, 0))
                fila += 1

            ctk.CTkLabel(tarjeta, text="Nombre de la ficha (se genera solo):",
                        font=_fuente(11, "bold"), text_color=GRIS_TEXTO).grid(
                row=fila, column=0, columnspan=3, sticky="w", **pad, pady=(16, 2))
            fila += 1
            # Si la ficha ya trae un nombre escrito a mano, se muestra tal cual
            # (no se regenera solo: para eso está el botón Regenerar).
            self.v_nombre = tk.StringVar(
                value=str(self.datos_origen.get("nombre_ficha", "") or ""))
            e = ctk.CTkEntry(tarjeta, textvariable=self.v_nombre, height=34,
                             corner_radius=8, border_color=BORDE_SUAVE,
                             font=_fuente(11, "bold"), text_color=AZUL_ES)
            e.grid(row=fila, column=0, columnspan=2, sticky="we", padx=(16, 6))
            e.bind("<KeyRelease>", self._nombre_a_mano)
            _boton_secundario(tarjeta, "↻ Regenerar", self._regenerar, ancho=120).grid(
                row=fila, column=2, padx=(0, 16))
            fila += 1

            self.lbl_aviso = ctk.CTkLabel(tarjeta, text="", justify="left",
                                          wraplength=560, text_color=GRIS_TEXTO)
            self.lbl_aviso.grid(row=fila, column=0, columnspan=3, sticky="w",
                                padx=16, pady=(4, 8))
            fila += 1

            self.vars = {}
            for clave, etiqueta in self.CAMPOS:
                ctk.CTkLabel(tarjeta, text=etiqueta + ":", text_color=GRIS_TEXTO).grid(
                    row=fila, column=0, sticky="e", pady=3, padx=(16, 6))
                v = tk.StringVar(value=str(self.datos_origen.get(clave, "") or ""))
                ent = ctk.CTkEntry(tarjeta, textvariable=v, height=32,
                                   corner_radius=8, border_color=BORDE_SUAVE)
                ent.grid(row=fila, column=1, columnspan=2, sticky="we", pady=3,
                        padx=(0, 16))
                ent.bind("<KeyRelease>", lambda _ev: self._recalcular())
                self.vars[clave] = v
                fila += 1
                if clave == "dimensiones":
                    self.v_sin_medidas = tk.BooleanVar(
                        value=bool(self.datos_origen.get("sin_medidas")))
                    ctk.CTkCheckBox(
                        tarjeta, variable=self.v_sin_medidas, command=self._recalcular,
                        text="Este material no tiene medidas/dimensiones "
                             "(ej: sacos, cubetas, unidades).",
                        text_color=GRIS_TEXTO, fg_color=AZUL_ES,
                        hover_color=_HOVER[AZUL_ES]
                    ).grid(row=fila, column=1, columnspan=2, sticky="w", padx=(0, 16))
                    fila += 1

            barra = ctk.CTkFrame(tarjeta, fg_color="transparent")
            barra.grid(row=fila, column=0, columnspan=3, pady=(12, 16))
            self.btn_ok = _boton(barra, "✅ Confirmar y guardar", self._confirmar,
                                 color=VERDE_OK, ancho=220)
            self.btn_ok.pack(side="left", padx=6)
            _boton_secundario(barra, "Cancelar" if self.es_edicion else "Omitir",
                             self.destroy, ancho=120).pack(side="left", padx=6)

        # -------------------------------------------------------- nomenclatura
        def _datos_actuales(self):
            d = dict(self.datos_origen)
            d.update({k: v.get().strip() for k, v in self.vars.items()})
            d["categoria"] = d.get("categoria", "").strip().upper()
            d["sin_medidas"] = bool(self.v_sin_medidas.get())
            return d

        def _nombre_a_mano(self, _ev=None):
            """Si el usuario CAMBIA el nombre, deja de regenerarse solo.

            Se compara contra el último valor autogenerado en vez de reaccionar a
            cualquier tecla: con una flecha, un Tab o un Ctrl se marcaba como
            "manual" un nombre que en realidad no se había tocado, y entonces ya
            no se volvía a regenerar nunca.
            """
            self._nombre_editado = self.v_nombre.get().strip() != self._nombre_auto
            self._recalcular(solo_aviso=True)

        def _regenerar(self):
            self._nombre_editado = False
            self._recalcular()

        def _recalcular(self, solo_aviso=False):
            d = self._datos_actuales()
            self.analisis = nomenclatura.analizar(d)
            self._nombre_auto = self.analisis["nombre"]
            if not solo_aviso and not self._nombre_editado:
                self.v_nombre.set(self._nombre_auto)
            self._pintar_aviso()

        def _pintar_aviso(self):
            if self._suficiente():
                if self.v_sin_medidas.get() and not self.analisis["distintivos"]:
                    texto = ("✔ Marcado como material sin medidas/dimensiones: "
                             "se guardará así.")
                else:
                    texto = "✔ El nombre distingue esta ficha de otras similares."
                self.lbl_aviso.configure(text=texto, text_color=VERDE_OK)
                self.btn_ok.configure(state="normal")
                return
            self.lbl_aviso.configure(
                text="⚠ " + " ".join(self.analisis["faltantes"])
                     + "\nComplete el dato que falta (o escriba el nombre a mano) "
                       "para poder guardar.",
                text_color=ROJO_ES)
            self.btn_ok.configure(state="disabled")

        def _suficiente(self):
            """¿El nombre permite distinguir la ficha?

            Vale si el análisis encontró algo distintivo (dimensiones,
            presentación, designación o modelo) o si el usuario escribió un
            nombre a mano que sí lo tiene: la persona sabe más que la heurística.
            """
            if self.analisis["suficiente"]:
                return True
            nombre = self.v_nombre.get().strip()
            if not nombre or not self._nombre_editado:
                return False
            if not self.analisis["base"] or not self.analisis["marca"]:
                return False
            return bool(re.search(r"\d", nombre)) or len(nombre.split()) >= 5

        # ------------------------------------------------------------ guardar
        def _confirmar(self):
            d = self._datos_actuales()
            faltan = [c for c in bd_manager.CAMPOS_OBLIGATORIOS_FICHA if not d.get(c)]
            if faltan:
                messagebox.showwarning("Faltan datos",
                                       "Campos obligatorios: " + ", ".join(faltan))
                return
            if d["categoria"] not in bd_manager.CATEGORIAS:
                messagebox.showwarning("Categoría", "Use ARQ, ESTR, MEC o ELEC")
                return
            if not self._suficiente():
                messagebox.showwarning("Ficha indistinguible",
                                       "\n".join(self.analisis["faltantes"]))
                return

            escrito = self.v_nombre.get().strip()
            if not escrito:
                # Campo vacío: vuelve a mandar el nombre automático (y NO se
                # marca como manual, que era el error).
                escrito = self.analisis["nombre"]
                self._nombre_editado = False
            nombre = escrito
            d["nombre_ficha"] = nombre if self._nombre_editado else ""
            d["_requiere_manual"] = self.datos_origen.get("_requiere_manual", False)

            existente = self.bd.buscar_por_nombre(
                nombre, excluir_id=self.datos_origen.get("id"))
            if existente is not None:
                accion = self._preguntar_duplicado(existente, nombre)
                if accion is None:
                    return                       # el usuario canceló
                if accion != "guardar":
                    self.resultado = {"accion": accion, "ficha": existente}
                    self.destroy()
                    return
                d["nombre_ficha"] = nombre       # variante: nombre explícito
            self.resultado = {"accion": "guardar", "datos": d, "nombre_ficha": nombre}
            self.destroy()

        def _preguntar_duplicado(self, existente, nombre):
            """Tres salidas ante un nombre repetido; ``None`` si cancela."""
            top = ctk.CTkToplevel(self)
            top.title("Ficha repetida")
            top.configure(fg_color=GRIS_BG, padx=16, pady=14)
            top.grab_set()
            estado = existente.get("estado", "activo")
            tarjeta = _tarjeta(top); tarjeta.pack(fill="both", expand=True)
            ctk.CTkLabel(tarjeta, text="Ya existe una ficha con este nombre:",
                        font=_fuente(11, "bold"), text_color=GRIS_TEXTO).pack(
                anchor="w", padx=16, pady=(16, 0))
            ctk.CTkLabel(tarjeta, text=self.bd.nombre_de(existente), text_color=AZUL_ES,
                        wraplength=520, justify="left").pack(anchor="w", padx=16,
                                                             pady=(2, 6))
            ctk.CTkLabel(tarjeta, text=f"Cargada el {existente.get('fecha_carga', '?')}"
                               f"  ·  estado: {estado}", text_color=GRIS_TEXTO_SUAVE).pack(
                anchor="w", padx=16)
            ctk.CTkLabel(tarjeta, text="¿Qué desea hacer?", justify="left",
                        text_color=GRIS_TEXTO).pack(anchor="w", padx=16, pady=(10, 6))
            eleccion = {"v": None}

            def _elegir(valor):
                eleccion["v"] = valor
                top.destroy()

            if self.es_edicion:
                # Editando NO hay archivo nuevo que usar ni ficha que reemplazar:
                # las otras dos salidas no tienen sentido y antes descartaban la
                # edición en silencio.
                opciones = [
                    ("Guardar con este nombre igual", "guardar",
                     "Quedarán dos fichas con el mismo nombre."),
                ]
            else:
                opciones = [
                    ("Usar la ficha que ya existe", "usar_existente",
                     "No se carga nada nuevo."),
                    ("Reemplazar su archivo por este", "reemplazar",
                     "Corrige el archivo y conserva el nombre y las referencias."),
                    ("Guardar como variante", "guardar",
                     "Se agrega otra ficha con el mismo nombre."),
                ]
            for texto, valor, ayuda in opciones:
                f = ctk.CTkFrame(tarjeta, fg_color="transparent")
                f.pack(fill="x", pady=3, padx=16)
                _boton_secundario(f, texto, lambda v=valor: _elegir(v), ancho=220).pack(
                    side="left")
                ctk.CTkLabel(f, text=ayuda, text_color=GRIS_TEXTO_SUAVE).pack(
                    side="left", padx=8)
            _boton_secundario(tarjeta, "Cancelar", top.destroy, ancho=120).pack(
                pady=(10, 16))
            _traer_al_frente(top)
            self.wait_window(top)
            return eleccion["v"]


    class _VentanaSubmittal(ctk.CTkToplevel):
        """Base comun para 'Generar desde BD' y 'Abrir existente'."""

        def __init__(self, master, bd, proyecto, destino, titulo):
            super().__init__(master)
            self.bd = bd; self.proyecto = proyecto; self.destino = destino
            self.title(titulo)
            self.configure(fg_color=GRIS_BG, padx=14, pady=14)
            self.geometry("820x640")
            tarjeta = _tarjeta(self)
            tarjeta.pack(fill="both", expand=True, padx=4, pady=4)
            ctk.CTkLabel(tarjeta, text=titulo, font=_fuente(14, "bold"),
                        text_color=GRIS_TEXTO).pack(anchor="w", padx=18, pady=(16, 0))
            top = ctk.CTkFrame(tarjeta, fg_color="transparent")
            top.pack(fill="x", padx=18, pady=10)
            _boton_secundario(top, "⚙️ Datos del Proyecto", self._datos,
                             ancho=180).pack(side="left")
            ctk.CTkLabel(top, text="  Carpeta destino:", text_color=GRIS_TEXTO).pack(
                side="left")
            self.var_dest = tk.StringVar(value=destino or "")
            ctk.CTkEntry(top, textvariable=self.var_dest, width=340, height=32,
                        corner_radius=8, border_color=BORDE_SUAVE).pack(
                side="left", padx=4)
            _boton_secundario(top, "…", self._elegir_destino, ancho=40).pack(side="left")

            self.tabla = TablaMateriales(tarjeta, bd, proyecto.get("materiales_seleccionados", []))
            self.tabla.pack(fill="both", expand=True, padx=18, pady=8)

            self.txt = ctk.CTkTextbox(tarjeta, height=140, corner_radius=10,
                                      fg_color="#0F172A", text_color="#4ADE80",
                                      font=("Consolas", 10))
            self.txt.pack(fill="x", padx=18, pady=(4, 4))
            _boton(tarjeta, "🚀 Generar / Confirmar cambios", self._generar,
                  color=NARANJA_CTA, ancho=280, alto=42).pack(pady=(4, 18))
            _traer_al_frente(self)

        def _log(self, m):
            self.txt.insert("end", str(m) + "\n"); self.txt.see("end"); self.update_idletasks()

        def _datos(self):
            d = DatosProyectoDialog(self, self.proyecto.get("datos_procedimiento", {}))
            self.wait_window(d)
            if d.resultado:
                self.proyecto["datos_procedimiento"] = d.resultado

        def _elegir_destino(self):
            c = filedialog.askdirectory(title="Carpeta destino del submittal")
            if c:
                self.var_dest.set(c)

        def _generar(self):
            self.proyecto["materiales_seleccionados"] = self.tabla.materiales
            destino = self.var_dest.get().strip()
            if not destino:
                messagebox.showwarning("Destino", "Elija una carpeta destino"); return
            ok, errores = self.bd.validar_proyecto(self.proyecto)
            if not ok:
                messagebox.showerror("No se puede generar", "\n".join(errores)); return
            if not messagebox.askyesno("Confirmar",
                                       "Se regenerarán carátulas, compilados y Excel. ¿Continuar?"):
                return
            tipo = self.proyecto.get("tipo_caratula", "clasica")
            try:
                res = generar_entregables(self.bd, self.proyecto, destino, tipo=tipo, log=self._log)
                self._log(f"\n✅ Listo: {res['materiales']} materiales en {res['destino']}")
                self._subir_metadatos()
                try:
                    os.startfile(destino)  # Windows: abre el explorador
                except Exception:
                    pass
            except Exception as e:
                self._log(f"\n❌ {e}")
                messagebox.showerror("Error al generar", str(e))

        def _subir_metadatos(self):
            """Sube a GitHub el ``submittal_proyecto.json`` del proyecto.

            Solo metadatos: las carátulas, los CMP y los Excel se quedan en la
            carpeta local y se regeneran cuando se necesiten.
            """
            nombre = self.proyecto.get("nombre_proyecto", "proyecto")
            self._log("🔄 Sincronizando con GitHub…")
            r = self.bd.git_push(f"submittal {nombre}")
            if r.get("desactivado"):
                return
            if r.get("subido"):
                extra = (f" · {r['conflictos']} conflicto(s) resuelto(s)"
                         if r.get("conflictos") else "")
                self._log(f"☁️ Metadatos del submittal subidos a GitHub{extra}")
            elif r.get("offline"):
                self._log("📡 Sin conexión: los entregables están listos; los "
                          "metadatos se subirán al reconectar")
            elif r.get("auth"):
                self._log("🔑 Falta el token de GitHub para subir los metadatos")
            elif not r.get("nada_que_subir"):
                self._log(f"⚠️ No se pudo subir: {r.get('error', '')}")


    def _probar_openai_key(api_key):
        """Verifica una API key contra OpenAI. Devuelve ``(ok, mensaje)``.

        Replica la comprobacion de v2.6 (``test_openai``) para no depender de que
        submitals_gui.py este disponible: aqui v3 es autonomo.
        """
        api_key = (api_key or "").strip()
        if not api_key:
            return (False, "Ingrese una API Key.")
        try:
            from openai import OpenAI
        except Exception:
            return (False, "Falta la librería 'openai' (pip install openai).")
        try:
            OpenAI(api_key=api_key, timeout=15).models.list()
            return (True, "Conexión exitosa: la API key funciona.")
        except Exception as e:
            try:
                import openai
                if isinstance(e, openai.AuthenticationError):
                    return (False, "API key inválida o sin créditos.")
            except Exception:
                pass
            return (False, f"No se pudo conectar: {str(e)[:150]}")

    class DialogoConfiguracion(ctk.CTkToplevel):
        """Configuracion unificada del usuario en DOS pestañas:

          * OpenAI: la API key que usa la lectura de fichas (PDF/imagen) con IA.
          * GitHub: repositorio, rama y token (PAT) para sincronizar la BD.

        Antes la API key solo se podia definir desde la app v2.6; en una PC que
        solo tiene el .exe de v3 no habia forma de ingresarla. Esta ventana lo
        resuelve. Ambos secretos se guardan (ofuscados en base64, igual que v2.6)
        en ``%APPDATA%/GeneradorSubmittals/config.json``.
        """

        def __init__(self, master, bd, tab_inicial="openai"):
            super().__init__(master)
            self.bd = bd
            self.cambio_github = False      # solo si cambio algo de GitHub -> resync
            self._probando = False
            self.title("Configuración")
            self.configure(fg_color=GRIS_BG, padx=16, pady=16)
            self.geometry("560x520")
            self.grab_set()

            nb = ctk.CTkTabview(self, fg_color="white", corner_radius=14,
                               border_width=1, border_color=BORDE_SUAVE,
                               segmented_button_selected_color=ROJO_ES,
                               segmented_button_selected_hover_color=_HOVER[ROJO_ES],
                               segmented_button_unselected_color="#E2E8F0",
                               text_color=GRIS_TEXTO, text_color_disabled=GRIS_TEXTO_SUAVE)
            nb.pack(fill="both", expand=True)
            self.tab_openai = nb.add("🔑 OpenAI (lectura de fichas)")
            self.tab_github = nb.add("☁️ GitHub (sincronización)")
            self._build_openai(self.tab_openai)
            self._build_github(self.tab_github)

            barra = ctk.CTkFrame(self, fg_color="transparent")
            barra.pack(fill="x", pady=(12, 0))
            _boton(barra, "💾 Guardar", self._guardar, color=AZUL_ES, ancho=140).pack(
                side="left", padx=6)
            _boton_secundario(barra, "Cerrar", self.destroy, ancho=110).pack(
                side="left", padx=6)

            nb.set("🔑 OpenAI (lectura de fichas)" if tab_inicial == "openai"
                  else "☁️ GitHub (sincronización)")
            _traer_al_frente(self)

        # -------------------------------------------------- pestaña OpenAI
        def _build_openai(self, f):
            ctk.CTkLabel(f, text="API Key de OpenAI", font=_fuente(12, "bold"),
                        text_color=GRIS_TEXTO).grid(row=0, column=0, columnspan=3,
                                                    sticky="w")
            ctk.CTkLabel(f, text="Se usa para leer las fichas técnicas (PDF/imagen) con IA.\n"
                             "Sin ella, la extracción cae a OCR local y revisión manual.",
                        text_color=GRIS_TEXTO_SUAVE, justify="left").grid(
                row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))

            # El entorno TIENE PRIORIDAD sobre la config (ver obtener_api_key):
            # se distingue la fuente para no mostrar "✅ configurada" por una key
            # guardada que en realidad no se usa porque la enmascara el entorno.
            env_key = os.environ.get("OPENAI_API_KEY", "").strip()
            guardada = bd_manager.descifrar_api_key(
                self.bd.cfg.get("api", {}).get("openai_key_encrypted", ""))
            if env_key:
                estado = ("✅ configurada por variable de entorno OPENAI_API_KEY "
                          "(tiene prioridad)")
            elif guardada:
                estado = "✅ ya configurada"
            else:
                estado = "❌ sin configurar"
            ctk.CTkLabel(f, text=f"Estado actual: {estado}   ·   deje el campo vacío para "
                             "conservarla", text_color=GRIS_TEXTO_SUAVE).grid(
                row=2, column=0, columnspan=3, sticky="w", pady=(0, 6))

            ctk.CTkLabel(f, text="API Key:", text_color=GRIS_TEXTO).grid(
                row=3, column=0, sticky="e", pady=4)
            self.v_openai = tk.StringVar(value="")
            self.e_openai = ctk.CTkEntry(f, textvariable=self.v_openai, width=280,
                                        height=32, corner_radius=8,
                                        border_color=BORDE_SUAVE, show="•")
            self.e_openai.grid(row=3, column=1, pady=4)
            self.v_mostrar = tk.BooleanVar(value=False)
            ctk.CTkCheckBox(f, text="Mostrar", variable=self.v_mostrar,
                           command=self._toggle_mostrar, text_color=GRIS_TEXTO,
                           fg_color=AZUL_ES, hover_color=_HOVER[AZUL_ES]).grid(
                row=3, column=2, padx=(6, 0))

            self.btn_probar = _boton_secundario(f, "Probar conexión",
                                                self._probar_openai, ancho=150)
            self.btn_probar.grid(row=4, column=1, sticky="w", pady=(8, 0))
            self.lbl_openai_estado = ctk.CTkLabel(f, text="", text_color=GRIS_TEXTO_SUAVE,
                                                  justify="left", wraplength=420)
            self.lbl_openai_estado.grid(row=5, column=0, columnspan=3, sticky="w",
                                        pady=(6, 0))
            ctk.CTkLabel(f, text="Cree su API key en platform.openai.com/api-keys",
                        text_color=GRIS_TEXTO_SUAVE).grid(
                row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

        def _toggle_mostrar(self):
            self.e_openai.configure(show="" if self.v_mostrar.get() else "•")

        def _probar_openai(self):
            if self._probando:
                return
            key = (self.v_openai.get().strip()
                   or bd_manager.obtener_api_key(cfg=self.bd.cfg,
                                                 config_dir=self.bd.config_dir))
            if not key:
                self.lbl_openai_estado.configure(
                    text="Ingrese una API Key para probar.", text_color=ROJO_ES)
                return
            self._probando = True
            self.btn_probar.configure(state="disabled")
            self.lbl_openai_estado.configure(text="Probando conexión…", text_color=AZUL_ES)

            def trabajo():
                ok, msg = _probar_openai_key(key)
                try:
                    self.after(0, lambda: self._fin_probar(ok, msg))
                except tk.TclError:
                    pass

            threading.Thread(target=trabajo, daemon=True).start()

        def _fin_probar(self, ok, msg):
            # La prueba corre en un hilo (hasta 15 s). Si el usuario cerró la
            # ventana mientras tanto, los widgets ya no existen: winfo_exists()
            # devuelve 0 sin lanzar, y así evitamos un TclError al tocarlos.
            if not self.winfo_exists():
                return
            self._probando = False
            self.btn_probar.configure(state="normal")
            self.lbl_openai_estado.configure(text=("✅ " if ok else "❌ ") + msg,
                                             text_color=(VERDE_OK if ok else ROJO_ES))

        # -------------------------------------------------- pestaña GitHub
        def _build_github(self, f):
            gh = self.bd.cfg.get("github", {}) or {}
            est = self.bd.git_status()
            ctk.CTkLabel(f, text="Sincronización de la Base de Datos",
                        font=_fuente(12, "bold"), text_color=GRIS_TEXTO).grid(
                row=0, column=0, columnspan=2, sticky="w")
            modo = {"git": "git instalado", "rest": "API REST (sin git)"}.get(
                est.get("backend"), est.get("backend", "?"))
            ctk.CTkLabel(f, text=f"Método: {modo}", text_color=GRIS_TEXTO_SUAVE).grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))

            self.v_repo = tk.StringVar(value=gh.get("repo", ""))
            self.v_rama = tk.StringVar(value=gh.get("branch", "main"))
            self.v_token = tk.StringVar(value="")
            filas = [("Repositorio (usuario/repo):", self.v_repo, False),
                     ("Rama:", self.v_rama, False),
                     ("Token (PAT):", self.v_token, True)]
            for i, (etiqueta, var, secreto) in enumerate(filas, 2):
                ctk.CTkLabel(f, text=etiqueta, text_color=GRIS_TEXTO).grid(
                    row=i, column=0, sticky="e", pady=4)
                ctk.CTkEntry(f, textvariable=var, width=240, height=32, corner_radius=8,
                            border_color=BORDE_SUAVE,
                            show="•" if secreto else "").grid(row=i, column=1, pady=4)

            tiene = "✅ ya configurado" if est.get("autenticado") else "❌ sin configurar"
            ctk.CTkLabel(f, text=f"Token actual: {tiene}   ·   deje el campo vacío "
                             "para conservarlo", text_color=GRIS_TEXTO_SUAVE).grid(
                row=5, column=0, columnspan=2, sticky="w")
            ctk.CTkLabel(f, text="Cree el token en github.com/settings/tokens con\n"
                             "permiso Contents: write SOLO sobre este repositorio.",
                        text_color=GRIS_TEXTO_SUAVE, justify="left").grid(
                row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # -------------------------------------------------- guardado
        def _guardar(self):
            cfg = self.bd.cfg

            # --- OpenAI: solo se toca si el usuario escribio algo ---
            key = self.v_openai.get().strip()
            if key:
                cfg.setdefault("api", {})["openai_key_encrypted"] = \
                    bd_manager.cifrar_api_key(key)

            # --- GitHub ---
            cfg.setdefault("github", {})
            old_repo = cfg["github"].get("repo")
            old_rama = cfg["github"].get("branch")
            repo_nuevo = self.v_repo.get().strip() or old_repo or ""
            rama_nueva = self.v_rama.get().strip() or "main"
            token = self.v_token.get().strip()
            repo_o_rama_cambio = (repo_nuevo != old_repo) or (rama_nueva != old_rama)
            if repo_o_rama_cambio or token:
                self.cambio_github = True
            cfg["github"]["repo"] = repo_nuevo
            cfg["github"]["branch"] = rama_nueva
            if token:
                cfg["github"]["token_encrypted"] = bd_manager.cifrar_secreto(token)

            bd_manager.guardar_config(cfg, self.bd.config_dir)

            # Aplicar los cambios al objeto de sincronización EN VIVO (sin reiniciar):
            #  * repo/rama quedan fijados al CONSTRUIR el transporte, así que un
            #    cambio de repo/rama exige reconstruir el sync (set_token no basta);
            #    crear_sync toma repo/rama/token del cfg ya actualizado.
            #  * si solo cambió el token, basta set_token (camino ya probado).
            if self.bd.sync is not None:
                if repo_o_rama_cambio:
                    self.bd.sync = bd_manager.crear_sync(
                        cfg, self.bd.config_dir, self.bd.cache_dir, self.bd.log)
                elif token:
                    self.bd.sync.set_token(token)

            # Aviso: una variable de entorno OPENAI_API_KEY tiene PRIORIDAD sobre la
            # key guardada, así que la lectura de fichas la ignoraría en silencio.
            if key and os.environ.get("OPENAI_API_KEY", "").strip():
                messagebox.showwarning(
                    "Variable de entorno detectada",
                    "Guardé la API key, pero esta computadora tiene una variable de "
                    "entorno OPENAI_API_KEY que TIENE PRIORIDAD sobre ella.\n\n"
                    "La lectura de fichas seguirá usando la variable de entorno hasta "
                    "que la elimine.")
            else:
                messagebox.showinfo("Configuración", "Configuración guardada.")
            self.destroy()


    class App(ctk.CTk):
        """Ventana principal con el menu 2x2 y la sincronizacion con GitHub."""

        def __init__(self):
            super().__init__()
            _configurar_estilo_ttk()
            self.title(f"Generador de Submittals ES v{VERSION}")
            self.configure(fg_color=GRIS_BG, padx=20, pady=20)
            self.geometry("680x600")
            self._sincronizando = False
            self.modo_dev = False
            self._construir()
            # Se revisa/instala Git ANTES de crear el BDManager: la eleccion de
            # transporte (git vs API REST) se decide una sola vez, al construir
            # el GitSync de adentro. Solo tarda si esta PC no tiene git (primera
            # vez); despues git_disponible() es instantaneo.
            self.lbl_sync.configure(text="🔧 Verificando Git…", text_color=AZUL_ES)
            self.update()
            git_bd.instalar_git_si_falta(logger.info)
            self.bd = bd_manager.BDManager(logger=logger)
            self.protocol("WM_DELETE_WINDOW", self._cerrar_seguro)
            self.after(100, lambda: self._sincronizar(inicial=True))

        def _construir(self):
            titulo = ctk.CTkFrame(self, fg_color="transparent")
            titulo.pack(pady=(0, 4))
            ctk.CTkLabel(titulo, text="Generador de Submittals ", text_color=AZUL_ES,
                        font=_fuente(20, "bold")).pack(side="left")
            ctk.CTkLabel(titulo, text="ES", text_color=ROJO_ES,
                        font=_fuente(20, "bold")).pack(side="left")
            self.lbl_estado = ctk.CTkLabel(self, text="", text_color=GRIS_TEXTO_SUAVE)
            self.lbl_estado.pack()
            self.lbl_sync = ctk.CTkLabel(self, text="⏳ Iniciando…", text_color=GRIS_TEXTO_SUAVE)
            self.lbl_sync.pack()
            self.prog = ctk.CTkProgressBar(self, width=360, height=8, corner_radius=4,
                                           mode="indeterminate", progress_color=AZUL_ES)

            grid = ctk.CTkFrame(self, fg_color="transparent"); grid.pack(pady=18)
            botones = [
                ("📤  Generar desde BD", self._generar_desde_bd),
                ("📂  Abrir submittal existente", self._abrir_existente),
                ("➕  Cargar ficha a BD", self._cargar_ficha),
                ("🗂️  Gestionar BD", self._gestionar_bd),
            ]
            for i, (txt, cmd) in enumerate(botones):
                b = ctk.CTkButton(grid, text=txt, command=cmd, width=260, height=84,
                                  fg_color="white", hover_color="#EFF6FF",
                                  text_color=AZUL_ES, border_width=1,
                                  border_color=BORDE_SUAVE, corner_radius=16,
                                  font=_fuente(13, "bold"))
                b.grid(row=i // 2, column=i % 2, padx=10, pady=10)

            sync = ctk.CTkFrame(self, fg_color="transparent"); sync.pack(pady=(0, 10))
            _boton_secundario(sync, "🔄 Sincronizar ahora", self._sincronizar,
                             ancho=170).pack(side="left", padx=4)
            _boton_secundario(sync, "☁️ Subir cambios pendientes", self._subir_pendientes,
                             ancho=210).pack(side="left", padx=4)
            _boton_secundario(sync, "⚙️ Configuración", self._configuracion,
                             ancho=150).pack(side="left", padx=4)

            barra = ctk.CTkFrame(self, fg_color="transparent")
            barra.pack(side="bottom", fill="x")
            _boton_secundario(barra, "🏗️ Generar desde carpetas (v2.6)", self._lanzar_v26,
                             ancho=230).pack(side="left")
            _boton_secundario(barra, "🔄 Buscar actualización", self._buscar_update,
                             ancho=190).pack(side="left", padx=6)
            self.btn_modo_dev = _boton_secundario(barra, "🛠️ Modo desarrollador",
                                                  self._toggle_modo_dev, ancho=190)
            self.btn_modo_dev.pack(side="left", padx=6)
            _boton(barra, "❌ Cerrar", self._cerrar_seguro, color=ROJO_ES,
                  ancho=110).pack(side="right")

        # ------------------------------------------------ sincronizacion
        def _sincronizar(self, inicial=False):
            """Flujo 1: ``git pull`` en segundo plano para no congelar la GUI."""
            if self._sincronizando:
                return
            self._sincronizando = True
            self.lbl_sync.configure(text="🔄 Sincronizando con GitHub…", text_color=AZUL_ES)
            self.prog.pack(pady=(0, 6))
            self.prog.start()

            def trabajo():
                try:
                    _data, resumen = self.bd.sync_indice()
                except Exception as e:      # no debería ocurrir: sync_indice absorbe
                    resumen = {"error": str(e)}
                self.after(0, lambda: self._fin_sincronizar(resumen, inicial))

            threading.Thread(target=trabajo, daemon=True).start()

        def _fin_sincronizar(self, resumen, inicial=False):
            self.prog.stop()
            self.prog.pack_forget()
            self._sincronizando = False
            self._actualizar_estado()

            if resumen.get("conflictos"):
                self.lbl_sync.configure(
                    text=f"✅ Conflicto resuelto y sincronizado "
                         f"({resumen['conflictos']} archivo(s))", text_color=VERDE_OK)
                messagebox.showinfo(
                    "Conflicto resuelto",
                    "Otra computadora había subido cambios a la vez.\n\n"
                    "Se fusionaron automáticamente sin perder datos: se "
                    "conservaron las fichas de ambos lados.")
                return
            if resumen.get("indice_invalido"):
                self.lbl_sync.configure(text="⚠️ Índice con problemas: usando caché local",
                                        text_color=ROJO_ES)
                messagebox.showwarning(
                    "Índice inconsistente",
                    "El índice descargado no pasó la validación; se está usando la "
                    "copia local.\n\nDetalle:\n- " +
                    "\n- ".join(resumen["indice_invalido"][:6]))
                return
            if resumen.get("auth") and inicial:
                self.lbl_sync.configure(text="🔑 Sin token de GitHub (solo lectura)",
                                        text_color=ROJO_ES)
                return
            if resumen.get("offline"):
                self.lbl_sync.configure(text="📡 Sin conexión — trabajando con la copia local",
                                        text_color=ROJO_ES)
                return
            if resumen.get("error"):
                self.lbl_sync.configure(text=f"⚠️ {resumen['error'][:70]}", text_color=ROJO_ES)
                return
            self.lbl_sync.configure(text=self.bd.texto_estado_sync(), text_color=VERDE_OK)

        def _subir_pendientes(self):
            if not self.bd.hay_cambios_sin_subir():
                messagebox.showinfo("Sincronización", "No hay cambios pendientes de subir.")
                return
            self.lbl_sync.configure(text="🔄 Subiendo cambios…", text_color=AZUL_ES)
            self.update_idletasks()
            r = self.bd.git_push("subir cambios pendientes")
            self._reportar_push(r)

        def _reportar_push(self, r):
            if r.get("subido"):
                extra = (f" ({r['conflictos']} conflicto(s) resuelto(s))"
                         if r.get("conflictos") else "")
                self.lbl_sync.configure(text=f"☁️ Cambios subidos a GitHub{extra}",
                                        text_color=VERDE_OK)
            elif r.get("offline"):
                self.lbl_sync.configure(text="📡 Sin conexión — se subirán al reconectar",
                                        text_color=ROJO_ES)
            elif r.get("auth"):
                self.lbl_sync.configure(text="🔑 Falta el token de GitHub", text_color=ROJO_ES)
                if messagebox.askyesno("Token requerido",
                                       "Para subir cambios hace falta un token de "
                                       "GitHub.\n\n¿Configurarlo ahora?"):
                    self._config_github()
            elif r.get("nada_que_subir"):
                self.lbl_sync.configure(text="Sin cambios por subir", text_color=GRIS_TEXTO_SUAVE)
            else:
                self.lbl_sync.configure(text=f"⚠️ {str(r.get('error', ''))[:70]}",
                                        text_color=ROJO_ES)

        def _configuracion(self, tab_inicial="openai"):
            """Abre la configuración unificada (OpenAI + GitHub)."""
            d = DialogoConfiguracion(self, self.bd, tab_inicial=tab_inicial)
            self.wait_window(d)
            if d.cambio_github:
                self._sincronizar()

        def _config_github(self):
            """Atajo que abre la configuración directamente en la pestaña GitHub
            (lo usa el aviso de 'falta el token' al intentar subir)."""
            self._configuracion(tab_inicial="github")

        def _actualizar_estado(self):
            res = self.bd.resumen_por_categoria()
            cache = "  ·  ⚠️ usando caché anterior" if self.bd.usando_cache else ""
            pend = self.bd.pendientes
            sin_subir = f"  ·  ☁️ {len(pend)} cambio(s) sin subir" if pend else ""
            self.lbl_estado.configure(
                text=f"BD: {res['TOTAL']} fichas  (ARQ {res['ARQ']} · ESTR {res['ESTR']} · "
                     f"MEC {res['MEC']} · ELEC {res['ELEC']}){cache}{sin_subir}",
                text_color=GRIS_TEXTO_SUAVE)

        # -------- modo desarrollador
        def _toggle_modo_dev(self):
            if self.modo_dev:
                self.modo_dev = False
                self.btn_modo_dev.configure(text="🛠️ Modo desarrollador", fg_color="white",
                                            text_color=AZUL_ES)
                self.title(f"Generador de Submittals ES v{VERSION}")
                return

            d = _PinDialog(self, "Modo desarrollador", "Ingrese el PIN:")
            self.wait_window(d)
            pin = d.resultado
            if pin is None:
                return
            if pin != PIN_MODO_DEV:
                messagebox.showerror("PIN incorrecto", "El PIN ingresado no es correcto.")
                return

            self.modo_dev = True
            self.btn_modo_dev.configure(text="🛠️ Modo desarrollador: ACTIVO",
                                        fg_color=ROJO_ES, text_color="white")
            self.title(f"Generador de Submittals ES v{VERSION} — MODO DESARROLLADOR")
            messagebox.showinfo(
                "Modo desarrollador activado",
                "Modo desarrollador activado.\n\n"
                "Al generar un submittal desde BD ya no se pedirán los datos del "
                "proyecto: se completan automáticamente con datos de prueba.\n\n"
                "Use este modo solo para pruebas, nunca para submittals reales.")

        # -------- flujos
        def _pedir_datos_proyecto(self):
            if self.modo_dev:
                return {
                    "numero_procedimiento": "PRUEBA-0000",
                    "institucion": "Institución de prueba",
                    "detalle": "Submittal de prueba (modo desarrollador)",
                    "plazo": "N/A",
                    "monto": "0",
                }
            d = DatosProyectoDialog(self)
            self.wait_window(d)
            return d.resultado

        def _generar_desde_bd(self):
            datos = self._pedir_datos_proyecto()
            if not datos:
                return
            destino = filedialog.askdirectory(title="Carpeta destino del submittal")
            if not destino:
                return
            proyecto = {"nombre_proyecto": Path(destino).name,
                        "datos_procedimiento": datos, "tipo_caratula": "clasica",
                        "materiales_seleccionados": []}
            _VentanaSubmittal(self, self.bd, proyecto, destino, "Generar submittal desde BD")

        def _abrir_existente(self):
            carpeta = filedialog.askdirectory(title="Carpeta del submittal (con submittal_proyecto.json)")
            if not carpeta:
                return
            try:
                proyecto = bd_manager.BDManager.cargar_submittal(carpeta)
            except Exception as e:
                messagebox.showerror("No se pudo abrir", str(e)); return
            _VentanaSubmittal(self, self.bd, proyecto, carpeta,
                              f"Editando: {proyecto.get('nombre_proyecto', '')}")

        def _cargar_ficha(self):
            VentanaCargarFicha(self, self.bd, al_terminar=self._actualizar_estado)

        def _gestionar_bd(self):
            VentanaGestionarBD(self, self.bd, al_cambiar=self._actualizar_estado)

        def _lanzar_v26(self):
            import subprocess
            if getattr(sys, "frozen", False):
                # Empaquetado: no hay interprete de Python al que pasarle un
                # .py (sys.executable ES este mismo .exe). Se busca el .exe de
                # v2.6 compilado aparte, en la misma carpeta.
                exe_v26 = Path(sys.executable).resolve().parent / "GeneradorSubmittalsES.exe"
                if exe_v26.exists():
                    subprocess.Popen([str(exe_v26)], cwd=str(exe_v26.parent),
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                else:
                    messagebox.showinfo(
                        "v2.6", "No se encontró GeneradorSubmittalsES.exe (v2.6).\n\n"
                        "Coloque ese archivo en la misma carpeta que este programa "
                        "para poder abrirlo.")
                return
            ruta = BASE_DIR / "submitals_gui.py"
            if ruta.exists():
                subprocess.Popen([sys.executable, str(ruta)], cwd=str(BASE_DIR),
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                messagebox.showinfo("v2.6", "No se encontró submitals_gui.py")

        def _buscar_update(self):
            info = updater_gh.hay_actualizacion(logf=logger.info)
            if info.get("error"):
                messagebox.showinfo("Actualización", info["error"]); return
            if not info.get("disponible"):
                messagebox.showinfo("Actualización", "No hay actualizaciones."); return
            if messagebox.askyesno("Actualización disponible",
                                   f"Nueva versión {info.get('version_remota')}.\n"
                                   f"{info.get('changelog', '')}\n\n"
                                   "Se actualizará el programa y la Base de Datos.\n"
                                   "¿Aplicar ahora?"):
                ok, msg, reinicio, _bd = updater_gh.aplicar_y_sincronizar(
                    info, bd=self.bd, logf=logger.info)
                messagebox.showinfo("Actualización", msg)
                self._actualizar_estado()
                if ok and reinicio:
                    updater_gh.reiniciar()

        def _cerrar_seguro(self):
            """Cierre seguro: ofrece subir lo que quedó pendiente.

            Ya no hay lock que liberar; lo único que puede quedar a medias es un
            cambio local sin subir (por ejemplo si se trabajó sin conexión).
            """
            try:
                pendiente = self.bd.hay_cambios_sin_subir()
            except Exception:
                pendiente = False
            if pendiente:
                r = messagebox.askyesnocancel(
                    "Cambios sin subir",
                    "Hay cambios en la BD que todavía no están en GitHub.\n\n"
                    "¿Subirlos antes de cerrar?")
                if r is None:
                    return
                if r:
                    self.lbl_sync.configure(text="🔄 Subiendo cambios…", text_color=AZUL_ES)
                    self.update_idletasks()
                    res = self.bd.git_push("subir cambios antes de cerrar")
                    if not res.get("subido") and not res.get("nada_que_subir"):
                        if not messagebox.askyesno(
                                "No se pudo subir",
                                f"{res.get('error', 'Error desconocido')}\n\n"
                                "Los cambios están guardados localmente y se "
                                "subirán la próxima vez.\n\n¿Cerrar de todos modos?"):
                            return
            self.destroy()


    class VentanaGestionarBD(ctk.CTkToplevel):
        """Flujo 4: gestionar la BD (buscar, filtrar, editar, desactivar).

        v3.2.0: la columna principal es el NOMBRE DESCRIPTIVO completo, y se
        puede EDITAR una ficha (regenerando su nombre). Poder corregir es lo que
        faltaba; por eso el borrado sigue siendo lógico y reversible.
        """

        def __init__(self, master, bd, al_cambiar=None):
            super().__init__(master)
            self.bd = bd; self.al_cambiar = al_cambiar
            self.title("Gestionar Base de Datos"); self.geometry("1020x640")
            self.configure(fg_color=GRIS_BG, padx=12, pady=12)
            tarjeta = _tarjeta(self)
            tarjeta.pack(fill="both", expand=True, padx=4, pady=4)
            top = ctk.CTkFrame(tarjeta, fg_color="transparent")
            top.pack(fill="x", padx=16, pady=(16, 8))
            ctk.CTkLabel(top, text="Buscar:", text_color=GRIS_TEXTO).pack(side="left")
            self.var_q = tk.StringVar()
            e = ctk.CTkEntry(top, textvariable=self.var_q, width=220, height=32,
                             corner_radius=8, border_color=BORDE_SUAVE)
            e.pack(side="left", padx=4)
            e.bind("<KeyRelease>", lambda _e: self._refrescar())
            ctk.CTkLabel(top, text="Categoría:", text_color=GRIS_TEXTO).pack(
                side="left", padx=(10, 2))
            self.var_cat = tk.StringVar(value="TODAS")
            ctk.CTkComboBox(top, variable=self.var_cat, width=110, height=32,
                            corner_radius=8, border_color=BORDE_SUAVE,
                            button_color=ROJO_ES, button_hover_color=_HOVER[ROJO_ES],
                            state="readonly", dropdown_fg_color="white",
                            values=["TODAS"] + list(bd_manager.CATEGORIAS)).pack(side="left")
            self.var_cat.trace_add("write", lambda *_: self._refrescar())
            self.var_inact = tk.BooleanVar(value=False)
            ctk.CTkCheckBox(top, text="Mostrar desactivadas", variable=self.var_inact,
                           command=self._refrescar, text_color=GRIS_TEXTO,
                           fg_color=AZUL_ES, hover_color=_HOVER[AZUL_ES]).pack(
                side="left", padx=(12, 0))

            self.tree = ttk.Treeview(tarjeta, columns=("n", "c", "e", "f"), show="headings")
            for c, t, w in (("n", "Nombre de la ficha", 600), ("c", "Categoría", 80),
                            ("e", "Estado", 90), ("f", "Cargada", 100)):
                self.tree.heading(c, text=t); self.tree.column(c, width=w)
            self.tree.pack(fill="both", expand=True, padx=16, pady=8)
            self.tree.bind("<Double-Button-1>", lambda _ev: self._editar())

            bar = ctk.CTkFrame(tarjeta, fg_color="transparent")
            bar.pack(fill="x", padx=16, pady=(0, 16))
            _boton(bar, "✏️ Editar ficha", self._editar, color=AZUL_ES, ancho=150).pack(
                side="left")
            _boton_secundario(bar, "📄 Reemplazar PDF", self._reemplazar_pdf,
                             ancho=170).pack(side="left", padx=6)
            _boton(bar, "🗑️ Desactivar", self._eliminar, color=ROJO_ES, ancho=150).pack(
                side="left", padx=6)
            _boton_secundario(bar, "♻️ Reactivar", self._reactivar, ancho=140).pack(
                side="left")
            self.lbl = ctk.CTkLabel(bar, text="", text_color=GRIS_TEXTO_SUAVE)
            self.lbl.pack(side="right")
            self._map = {}
            self._refrescar()
            self._ofrecer_migracion()
            _traer_al_frente(self)

        # ------------------------------------------------------------ listado
        def _refrescar(self):
            q = self.var_q.get().strip()
            cat = self.var_cat.get()
            cat = None if cat == "TODAS" else cat
            inact = self.var_inact.get()
            if q:
                fichas = fuzzy_search.buscar(
                    q, self.bd.listar_fichas(incluir_inactivas=inact),
                    categoria=cat, top_n=200, incluir_inactivas=inact)
            else:
                fichas = [f for f in self.bd.listar_fichas(incluir_inactivas=inact)
                          if not cat or f.get("categoria") == cat]
            for i in self.tree.get_children():
                self.tree.delete(i)
            self._map.clear()
            for f in fichas:
                iid = f.get("id")
                if not iid:
                    continue          # índice inconsistente: no reventar la lista
                self._map[iid] = f
                estado = f.get("estado", "activo")
                self.tree.insert("", "end", iid=iid,
                                 values=(self.bd.nombre_de(f), f.get("categoria", ""),
                                         "desactivada" if estado != "activo" else "activa",
                                         f.get("fecha_carga", "")))
            r = self.bd.resumen_por_categoria()
            self.lbl.configure(text=f"{r['TOTAL']} activas · ARQ {r['ARQ']} · ESTR {r['ESTR']} · "
                                    f"MEC {r['MEC']} · ELEC {r['ELEC']}")

        def _sel(self):
            sel = self.tree.selection()
            if not sel:
                messagebox.showinfo("Seleccione una ficha",
                                    "Elija una ficha de la lista.")
                return None
            return self._map.get(sel[0])

        def _ofrecer_migracion(self):
            """Fichas de versiones anteriores sin nombre descriptivo."""
            pendientes = self.bd.fichas_sin_nombre()
            if not pendientes:
                return
            if not messagebox.askyesno(
                    "Generar nombres",
                    f"Hay {len(pendientes)} ficha(s) sin nombre descriptivo "
                    "(cargadas con una versión anterior).\n\n"
                    "¿Generar sus nombres ahora?"):
                return
            # Sincronizar primero: si otra PC editó esas fichas, se trabaja sobre
            # la versión al día en vez de pisarla.
            self.bd.sincronizar()
            n = self.bd.migrar_nombres_ficha()
            r = self.bd.git_push(f"generar nombre de {n} ficha(s)")
            self._refrescar()
            self._avisar_push(r, f"Nombres generados para {n} ficha(s).")

        # ------------------------------------------------------------ acciones
        def _editar(self):
            f = self._sel()
            if not f:
                return
            datos = dict(f)
            d = DialogoRevisarFicha(self, self.bd, None, datos,
                                    titulo=f"Editar: {self.bd.nombre_de(f)}",
                                    es_edicion=True)
            self.wait_window(d)
            res = d.resultado
            if res.get("accion") != "guardar":
                return
            cambios = {k: v for k, v in res["datos"].items()
                       if not k.startswith("_") and k in
                       ("nombre_material", "marca", "categoria", "dimensiones",
                        "sin_medidas", "tipo_producto", "especificacion",
                        "normativa", "descripcion_corta")}
            manual = res["datos"].get("nombre_ficha", "")
            if manual:
                cambios["nombre_ficha"] = manual
            try:
                # Sin nombre manual se regenera SIEMPRE: es lo que hace efectivo
                # el botón "Regenerar" incluso sobre una ficha que antes tenía el
                # nombre escrito a mano.
                ficha = self.bd.editar_ficha(f["id"], cambios,
                                             regenerar_nombre=not bool(manual))
            except Exception as e:
                messagebox.showerror("No se pudo editar", str(e)); return
            r = self.bd.git_push(f"editar ficha {ficha['nombre_ficha']}")
            self._refrescar()
            self._avisar_push(r, f"Ficha actualizada:\n{ficha['nombre_ficha']}")
            if self.al_cambiar:
                self.al_cambiar()

        def _reemplazar_pdf(self):
            f = self._sel()
            if not f:
                return
            ruta = filedialog.askopenfilename(
                title=f"PDF correcto para {self.bd.nombre_de(f)}",
                filetypes=[("Fichas", "*.pdf *.png *.jpg *.jpeg *.tif *.tiff"),
                           ("Todos", "*.*")])
            if not ruta:
                return
            try:
                self.bd.reemplazar_pdf_ficha(f["id"], ruta)
            except Exception as e:
                messagebox.showerror("No se pudo reemplazar", str(e)); return
            r = self.bd.git_push(f"reemplazar archivo de {self.bd.nombre_de(f)}")
            self._avisar_push(r, "Archivo reemplazado. El nombre y las referencias "
                                 "de los submittals se conservan.")
            self._refrescar()
            if self.al_cambiar:
                self.al_cambiar()

        def _eliminar(self):
            f = self._sel()
            if not f:
                return
            nombre = self.bd.nombre_de(f)
            en_uso = self.bd.proyectos_que_usan(f["id"])
            aviso = ""
            if en_uso:
                detalle = "\n".join(f"  · {p['nombre_proyecto']} ({p['consecutivo']})"
                                    for p in en_uso[:8])
                aviso = ("\n\n⚠️ Esta ficha se usa en "
                         f"{len(en_uso)} submittal(s):\n{detalle}\n"
                         "Esos submittals no podrán regenerarse hasta que se "
                         "cambie el material.")
            if not messagebox.askyesno(
                    "Desactivar ficha",
                    f"¿Desactivar '{nombre}'?\n\n"
                    "Dejará de aparecer en las búsquedas. El PDF NO se borra y la "
                    "ficha se puede reactivar después." + aviso):
                return
            if not self.bd.soft_delete_ficha(f["id"]):
                messagebox.showerror(
                    "No se pudo desactivar",
                    "La ficha ya no está en el índice. Sincronice y vuelva a "
                    "intentar.")
                self._refrescar()
                return
            r = self.bd.git_push(f"desactivar ficha {nombre}")
            self._refrescar()
            self._avisar_push(r, "Ficha desactivada.")
            if self.al_cambiar:
                self.al_cambiar()

        def _reactivar(self):
            f = self._sel()
            if not f:
                return
            if f.get("estado", "activo") == "activo":
                messagebox.showinfo("Reactivar", "La ficha ya está activa.")
                return
            if not self.bd.reactivar_ficha(f["id"]):
                messagebox.showerror(
                    "No se pudo reactivar",
                    "La ficha ya no está en el índice. Sincronice y vuelva a "
                    "intentar.")
                self._refrescar()
                return
            r = self.bd.git_push(f"reactivar ficha {self.bd.nombre_de(f)}")
            self._refrescar()
            self._avisar_push(r, "Ficha reactivada.")
            if self.al_cambiar:
                self.al_cambiar()

        def _avisar_push(self, r, mensaje_ok):
            if r.get("offline"):
                messagebox.showinfo("Sin conexión",
                                    mensaje_ok + "\n\nEl cambio se guardó localmente "
                                    "y se subirá al reconectar.")
            elif r.get("auth"):
                messagebox.showwarning("Falta el token",
                                       mensaje_ok + "\n\nNo se pudo subir a GitHub: "
                                       "configure el token.")
            elif r.get("subido") or r.get("nada_que_subir") or r.get("desactivado"):
                messagebox.showinfo("Listo", mensaje_ok)
            else:
                messagebox.showwarning("No se pudo subir",
                                       mensaje_ok + f"\n\n{r.get('error', '')}")


def main():
    if not _TK_OK:
        print("tkinter no disponible en este entorno; la GUI no puede iniciarse.")
        return
    App().mainloop()


if __name__ == "__main__":
    main()
