#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 test_v3.py  --  Pruebas de la version 3.1.0 (Generador de Submittals ES)
================================================================================
Cubre:
  UNIT
    - fuzzy_search: umbral 50 %, top 5, filtros, generacion de search_keywords.
    - bd_manager: soft delete, validaciones, cache FIFO 2 GB, API key
      (env/base64), token de GitHub, seguimiento de cambios pendientes.
  CASOS REALES (usa las fichas del propio proyecto)
    - Alta de fichas reales + busqueda fuzzy sobre keywords reales.
    - Submittal completo -> materializacion + CMP por material + Excel (sin
      carATulas, que requieren Playwright/Chromium).
    - Simulacion de BD ilegible -> uso de cache.
    - Extraccion de ficha real por OCR (fallback sin API key).

NOTA v3.1.0: las pruebas del ``.lock`` de OneDrive desaparecieron porque el
lock ya no existe: git resuelve la concurrencia. La sincronizacion (pull, push,
conflictos entre dos PCs, modo offline) se prueba en ``test_git_bd.py``, que
monta un repositorio local y no necesita internet.

NOTA v3.2.0: la nomenclatura de fichas (``nombre_ficha``), la edicion de fichas
y el reemplazo de PDF se prueban en ``test_nomenclatura.py``.

Ejecutar:
    python -m unittest test_v3 test_git_bd test_nomenclatura -v
================================================================================
"""

import os
import json
import time
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta

import fuzzy_search
import bd_manager as bd
import ocr_extractor
import submitals_gui_v3 as g3

BASE_DIR = Path(__file__).resolve().parent


def _pdf_minimo(path):
    path.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")


def _fichas_reales(maximo=3):
    """Devuelve rutas de fichas reales del proyecto (excluye carATulas/CMP)."""
    encontrados = []
    for madre, cat in (("ESTRUCTURALES", "ESTR"), ("ARQUITECTONICOS", "ARQ"),
                       ("MECANICOS", "MEC")):
        d = BASE_DIR / madre
        if not d.is_dir():
            continue
        for sub in sorted(d.iterdir()):
            if not sub.is_dir():
                continue
            for p in sub.glob("*.pdf"):
                up = p.name.upper()
                if up.startswith("CARATULA") or up.endswith("-CMP.PDF"):
                    continue
                encontrados.append((p, sub.name, cat))
                break
            if len(encontrados) >= maximo:
                return encontrados
    return encontrados


# ==========================================================================
# UNIT: fuzzy_search
# ==========================================================================
class TestFuzzySearch(unittest.TestCase):

    def setUp(self):
        self.fichas = [
            {"id": "1", "nombre_material": "Tubo Estructural 150x100x1.5",
             "marca": "MultiGroup", "categoria": "ESTR",
             "search_keywords": "tubo estructural 150x100x1.5 multigroup astm a500m",
             "estado": "activo"},
            {"id": "2", "nombre_material": "Tubo Estructural 152x100x1.5",
             "marca": "Metalco", "categoria": "ESTR",
             "search_keywords": "tubo estructural 152x100x1.5 metalco", "estado": "activo"},
            {"id": "3", "nombre_material": "Cemento", "marca": "Holcim",
             "categoria": "ESTR", "search_keywords": "cemento holcim hidraulico",
             "estado": "activo"},
            {"id": "4", "nombre_material": "Pintura", "marca": "Sur",
             "categoria": "ARQ", "search_keywords": "pintura satinada sur", "estado": "activo"},
        ]

    def test_match_relevante(self):
        res = fuzzy_search.buscar("tubo 150", self.fichas)
        self.assertTrue(res)
        self.assertEqual(res[0]["id"], "1")  # el mas parecido primero

    def test_umbral_50_descarta_irrelevantes(self):
        # "cemento" no debe traer tubos ni pintura
        res = fuzzy_search.buscar("cemento", self.fichas)
        self.assertEqual([r["id"] for r in res], ["3"])

    def test_puntaje_nunca_bajo_umbral(self):
        for r in fuzzy_search.buscar("tubo", self.fichas):
            self.assertGreaterEqual(r["_similitud"], fuzzy_search.UMBRAL_MINIMO)

    def test_top_n(self):
        muchos = [{"id": str(i), "search_keywords": "tubo estructural acero galvanizado",
                   "estado": "activo", "categoria": "ESTR", "marca": "X"} for i in range(20)]
        self.assertLessEqual(len(fuzzy_search.buscar("tubo estructural", muchos)),
                             fuzzy_search.TOP_N)

    def test_filtro_categoria(self):
        res = fuzzy_search.buscar("pintura", self.fichas, categoria="ESTR")
        self.assertEqual(res, [])  # la pintura es ARQ

    def test_filtro_marca(self):
        res = fuzzy_search.buscar("tubo", self.fichas, marca="metalco")
        self.assertTrue(all(r["marca"].lower() == "metalco" for r in res))

    def test_ignora_inactivas(self):
        self.fichas[2]["estado"] = "inactivo"
        self.assertEqual(fuzzy_search.buscar("cemento", self.fichas), [])

    def test_generar_search_keywords(self):
        kw = fuzzy_search.generar_search_keywords({
            "nombre_material": "Tubo Estructural", "marca": "MultiGroup",
            "categoria": "ESTR", "dimensiones": "150x100x1.5",
            "normativa": "ASTM A500M", "descripcion_corta": "Tubo de acero"})
        self.assertIn("tubo", kw)
        self.assertIn("multigroup", kw)
        # Sin duplicados: 'tubo' aparece una sola vez
        self.assertEqual(kw.split().count("tubo"), 1)


# ==========================================================================
# UNIT: bd_manager
# ==========================================================================
class TestBDManager(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.m = bd.BDManager(bd_root=self.tmp / "BD", cache_dir=self.tmp / "cache",
                              config_dir=self.tmp / "cfg")
        self.m.inicializar_bd()
        self.pdf = self.tmp / "ficha.pdf"
        _pdf_minimo(self.pdf)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _agregar(self, nombre="Tubo 150", marca="MultiGroup", cat="ESTR"):
        return self.m.agregar_ficha(str(self.pdf), {
            "nombre_material": nombre, "marca": marca, "categoria": cat,
            "dimensiones": "150x100x1.5", "normativa": "ASTM A500M",
            "descripcion_corta": "Tubo de acero"})

    def test_agregar_y_listar(self):
        f = self._agregar()
        self.assertEqual(len(self.m.listar_fichas()), 1)
        self.assertTrue(f["search_keywords"])
        self.assertTrue((self.m.bd_root / f["ruta_pdf"]).exists())

    def test_validacion_campos_obligatorios(self):
        with self.assertRaises(bd.BDError):
            self.m.agregar_ficha(str(self.pdf),
                                 {"nombre_material": "", "marca": "", "categoria": ""})

    def test_validacion_pdf_invalido(self):
        vacio = self.tmp / "vacio.pdf"; vacio.write_bytes(b"")
        with self.assertRaises(bd.BDError):
            self.m.agregar_ficha(str(vacio),
                                 {"nombre_material": "X", "marca": "Y", "categoria": "ESTR"})

    def test_soft_delete_no_borra_pdf(self):
        f = self._agregar()
        ruta_pdf = self.m.bd_root / f["ruta_pdf"]
        self.assertTrue(self.m.soft_delete_ficha(f["id"]))
        self.assertEqual(len(self.m.listar_fichas()), 0)              # no activa
        self.assertEqual(len(self.m.listar_fichas(incluir_inactivas=True)), 1)
        self.assertTrue(ruta_pdf.exists())                            # PDF intacto
        self.assertEqual(self.m.obtener_ficha(f["id"])["estado"], "inactivo")

    def test_aspectos_adicionales_se_guarda_y_edita(self):
        """Nota manual para la caratula (ej: 'ficha de un sistema completo').

        Cubre el caso de marcas que usan una sola ficha tecnica para todo un
        lineal (Amanco, Bloquera PC): la nota se guarda al cargar la ficha y
        se puede corregir despues desde 'Editar ficha'."""
        f = self.m.agregar_ficha(str(self.pdf), {
            "nombre_material": "Sistema de rociadores", "marca": "Amanco",
            "categoria": "MEC", "dimensiones": "MULTIPLE",
            "aspectos_adicionales": "Ficha de sistema completo."})
        self.assertEqual(f["aspectos_adicionales"], "Ficha de sistema completo.")

        editada = self.m.editar_ficha(f["id"], {"aspectos_adicionales": "Nota corregida."})
        self.assertEqual(editada["aspectos_adicionales"], "Nota corregida.")

    def test_aspectos_adicionales_llega_a_datos_materiales(self):
        """La nota de la ficha alimenta 'aspectos_adicionales' de la caratula
        cuando no hay justificacion de stock (que tiene prioridad, ver
        ``_texto_aspectos``)."""
        f = self.m.agregar_ficha(str(self.pdf), {
            "nombre_material": "Bloque de concreto", "marca": "Bloquera PC",
            "categoria": "ARQ", "dimensiones": "MULTIPLE",
            "aspectos_adicionales": "Cubre todo el lineal de bloques."})
        proyecto = {"materiales_seleccionados": [
            {"consecutivo": "ARQ01", "id_ficha_bd": f["id"],
             "nombre_material": f["nombre_material"], "marca": f["marca"],
             "categoria": "ARQ"}]}
        datos = self.m.construir_datos_materiales(proyecto, self.tmp / "destino")
        self.assertEqual(datos["materiales"][0]["aspectos_adicionales"],
                         "Cubre todo el lineal de bloques.")

    def test_actualizar_recalcula_keywords(self):
        f = self._agregar()
        act = self.m.actualizar_ficha(f["id"], {"marca": "Metalco"})
        self.assertIn("metalco", act["search_keywords"])

    # ---- SIN LOCK (v3.1.0) ----
    def test_ya_no_existe_el_lock(self):
        """El control de acceso por archivo desaparecio: git maneja la
        concurrencia. Que no quede ningun resto de la implementacion anterior."""
        for atributo in ("lock_path", "adquirir_lock", "liberar_lock", "lock_vigente"):
            self.assertFalse(hasattr(self.m, atributo),
                             f"BDManager todavia expone '{atributo}'")
        self.assertFalse(hasattr(bd, "LockOcupadoError"))
        self.assertFalse(hasattr(bd, "detectar_onedrive"))
        self.assertFalse((self.m.bd_root / ".lock").exists())

    def test_modo_local_sin_sincronizacion(self):
        """Con ``bd_root`` explicito el gestor no toca la red: los metodos de
        git responden 'desactivado' en vez de fallar."""
        self.assertIsNone(self.m.sync)
        for r in (self.m.git_pull(), self.m.git_push("x"),
                  self.m.git_merge_conflict_handler()):
            self.assertTrue(r.get("desactivado"))
        self.assertEqual(self.m.git_status()["backend"], "local")

    # ---- CAMBIOS PENDIENTES DE SUBIR ----
    def test_cambios_pendientes_se_registran(self):
        f = self._agregar()
        self.assertIn("indice.json", self.m.pendientes)
        self.assertIn(f["ruta_pdf"], self.m.pendientes)
        # Sobreviven a un reinicio de la app (se guardan en el cache).
        otro = bd.BDManager(bd_root=self.m.bd_root, cache_dir=self.m.cache_dir,
                            config_dir=self.tmp / "cfg")
        self.assertTrue(otro.pendientes)

    def test_fecha_modificacion_permite_ganar_conflictos(self):
        f = self._agregar()
        self.assertTrue(f.get("fecha_modificacion"))
        antes = f["fecha_modificacion"]
        time.sleep(1.05)
        act = self.m.actualizar_ficha(f["id"], {"marca": "Metalco"})
        self.assertGreater(act["fecha_modificacion"], antes)
        borrada = self.m.obtener_ficha(f["id"])
        self.m.soft_delete_ficha(f["id"])
        self.assertGreaterEqual(self.m.obtener_ficha(f["id"])["fecha_modificacion"],
                                borrada["fecha_modificacion"])

    # ---- TOKEN DE GITHUB ----
    def test_token_github_env_y_config(self):
        cfg_dir = self.tmp / "cfg"
        os.environ["GITHUB_TOKEN"] = "ghp-desde-env"
        try:
            self.assertEqual(bd.obtener_token_github(config_dir=cfg_dir), "ghp-desde-env")
        finally:
            del os.environ["GITHUB_TOKEN"]
        os.environ.pop("GH_TOKEN", None)
        bd.guardar_token_github("ghp-guardado", config_dir=cfg_dir)
        self.assertEqual(bd.obtener_token_github(config_dir=cfg_dir), "ghp-guardado")
        # No se guarda en texto plano legible directamente.
        crudo = (cfg_dir / "config.json").read_text(encoding="utf-8")
        self.assertNotIn("ghp-guardado", crudo)

    # ---- CACHE ----
    def test_cache_fifo_2gb(self):
        # Crear archivos falsos en cache y forzar limite bajo
        for i in range(5):
            p = self.m.cache_dir / f"f{i}.bin"
            p.write_bytes(b"0" * 1000)
            os.utime(p, (time.time() + i, time.time() + i))  # f0 el mas antiguo
        borrados = self.m.limpiar_cache_si_excede(max_bytes=2500)  # deja ~2 archivos
        self.assertGreater(borrados, 0)
        self.assertFalse((self.m.cache_dir / "f0.bin").exists())   # el mas antiguo se borro

    # ---- API KEY ----
    def test_api_key_env_tiene_prioridad(self):
        os.environ["OPENAI_API_KEY"] = "sk-desde-env"
        try:
            self.assertEqual(bd.obtener_api_key(config_dir=self.tmp / "cfg"), "sk-desde-env")
        finally:
            del os.environ["OPENAI_API_KEY"]

    def test_api_key_base64_config(self):
        os.environ.pop("OPENAI_API_KEY", None)
        cfg = bd.cargar_config(self.tmp / "cfg")
        cfg["api"]["openai_key_encrypted"] = bd.cifrar_api_key("sk-secreto-123")
        bd.guardar_config(cfg, self.tmp / "cfg")
        self.assertEqual(bd.obtener_api_key(config_dir=self.tmp / "cfg"), "sk-secreto-123")

    def test_validar_proyecto(self):
        f = self._agregar()
        proyecto = {"nombre_proyecto": "P",
                    "datos_procedimiento": {"numero_procedimiento": "1", "institucion": "M",
                                            "detalle": "d", "plazo": "p", "monto": "1"},
                    "materiales_seleccionados": [
                        {"consecutivo": "ESTR01", "id_ficha_bd": f["id"], "categoria": "ESTR",
                         "nombre_material": "Tubo 150", "marca": "MultiGroup"}]}
        ok, errs = self.m.validar_proyecto(proyecto)
        self.assertTrue(ok, errs)
        # Sin materiales -> falla
        proyecto["materiales_seleccionados"] = []
        self.assertFalse(self.m.validar_proyecto(proyecto)[0])


# ==========================================================================
# CASOS REALES
# ==========================================================================
class TestCasosReales(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.reales = _fichas_reales(3)

    def setUp(self):
        if not self.reales:
            self.skipTest("No hay fichas reales en el proyecto")
        self.tmp = Path(tempfile.mkdtemp())
        self.m = bd.BDManager(bd_root=self.tmp / "BD", cache_dir=self.tmp / "cache",
                              config_dir=self.tmp / "cfg")
        self.m.inicializar_bd()
        self.ids = []
        for pdf, nombre, cat in self.reales:
            f = self.m.agregar_ficha(str(pdf), {
                "nombre_material": nombre, "marca": "MarcaReal", "categoria": cat,
                "normativa": "ASTM", "descripcion_corta": f"Ficha real {nombre}"})
            self.ids.append((f, nombre, cat))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_busqueda_sobre_fichas_reales(self):
        primera = self.ids[0][1]
        token = primera.split()[0]
        res = self.m.buscar(token)
        self.assertTrue(res, f"No encontro '{token}' en fichas reales")

    def test_submittal_completo_sin_caratulas(self):
        materiales = []
        contad = {}
        for f, nombre, cat in self.ids:
            contad[cat] = contad.get(cat, 0) + 1
            materiales.append({"consecutivo": f"{cat}{contad[cat]:02d}",
                               "id_ficha_bd": f["id"], "categoria": cat,
                               "nombre_material": nombre, "marca": "MarcaReal"})
        proyecto = {"nombre_proyecto": "Prueba Real",
                    "datos_procedimiento": {"numero_procedimiento": "PROC-1", "institucion": "Muni",
                                            "detalle": "obra", "plazo": "6m", "monto": "1000"},
                    "tipo_caratula": "clasica", "materiales_seleccionados": materiales}
        destino = self.tmp / "salida"
        res = g3.generar_entregables(self.m, proyecto, destino, tipo="clasica",
                                     log=lambda *_a: None, con_caratulas=False)
        self.assertEqual(res["materiales"], len(materiales))
        # CMP por material generados y validos
        cmps = list(destino.rglob("*-CMP.pdf"))
        self.assertEqual(len(cmps), len(materiales))
        from pypdf import PdfReader
        for p in cmps:
            self.assertGreater(len(PdfReader(str(p)).pages), 0)
        # Excel generados y legibles
        self.assertTrue((destino / "Guía Submittal.xlsx").exists())
        self.assertTrue((destino / "Guía interna materiales.xlsx").exists())
        from openpyxl import load_workbook
        load_workbook(destino / "Guía Submittal.xlsx")
        # submittal_proyecto.json persistido
        sj = json.loads((destino / "submittal_proyecto.json").read_text(encoding="utf-8"))
        self.assertTrue(sj["entregables_generados"])

    def test_bd_ilegible_usa_cache(self):
        # Poblar cache leyendo el indice una vez
        self.m.cargar_indice()
        self.assertTrue(self.m.cache_indice.exists())
        # "Romper" la BD renombrando el indice y bajar reintentos/espera
        shutil.move(str(self.m.indice_path), str(self.m.indice_path) + ".bak")
        # Con el indice ausente cargar_indice devuelve vacio (no error); para
        # simular corrupcion escribimos basura:
        self.m.indice_path.write_text("{ esto no es json valido", encoding="utf-8")
        original_espera = bd.ESPERA_REINTENTO_SEG
        bd.ESPERA_REINTENTO_SEG = 0
        try:
            data = self.m.cargar_indice()
        finally:
            bd.ESPERA_REINTENTO_SEG = original_espera
        self.assertTrue(self.m.usando_cache)
        self.assertEqual(len(data.get("fichas", [])), len(self.ids))

    def test_extraccion_ocr_ficha_real(self):
        os.environ.pop("OPENAI_API_KEY", None)
        pdf = str(self.reales[0][0])
        datos = ocr_extractor.extraer([pdf], api_key="")  # forzar sin IA -> OCR/manual
        # Siempre devuelve las claves de salida y marca revision manual
        for k in ocr_extractor.CAMPOS_SALIDA:
            self.assertIn(k, datos)
        self.assertTrue(datos.get("_requiere_manual"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
