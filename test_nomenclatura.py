#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
 test_nomenclatura.py  --  Pruebas de la nomenclatura de fichas (v3.2.0)
================================================================================
Cubre los casos pedidos en la especificacion y, ademas, una familia por tipo de
material (tubos, acabados, agregados, electricos, mecanicos) y los bordes que se
ven en obra: fracciones de pulgada, dimensiones dentro del propio nombre,
conectores sueltos del OCR y datos insuficientes.

DOS DESVIACIONES DELIBERADAS respecto a los tests del plan original:

  1. ``TUBERIA DE ACERO ASTM A53 - Tuacero``  ->  ``TUBERIA DE ACERO - Tuacero``
     La normativa no entra en el nombre (indicacion del usuario). Ademas el plan
     era contradictorio: en otro ejemplo la ficha tenia ASTM A500M y la norma NO
     aparecia. Esa ficha queda marcada como INSUFICIENTE, que es justo lo que se
     quiere: sin diametro ni cedula no se distingue de otra tuberia de acero.

  2. ``TUBO RECTANGULAR E INDUSTRIAL``  ->  ``TUBO RECTANGULAR INDUSTRIAL``
     La "e" venia del nombre mal extraido; se elimina (asi lo pedia el unit test
     del plan, aunque su lista de ejemplos dijera lo contrario).

Ejecutar:
    python -m unittest test_nomenclatura -v
================================================================================
"""

import re
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import nomenclatura as nm
import bd_manager as bd

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


# ==========================================================================
# CASOS DE LA ESPECIFICACION
# ==========================================================================
class TestCasosDelPlan(unittest.TestCase):

    def test_con_dimensiones_en_dict(self):
        metadata = {
            "nombre_material": "Tubo Estructural",
            "marca": "MultiGroup",
            "descripcion_corta": "8x8x3/16, cuadrado",
            "normativa": "ASTM A500M",
            "dimensiones_detectadas": {"ancho": 8, "largo": 8, "espesor": 0.1875},
        }
        self.assertEqual(nm.generar_nombre_ficha_unico(metadata),
                         'TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup')
        # La normativa NO entra en el nombre, pero la ficha si es distinguible.
        self.assertTrue(nm.analizar(metadata)["suficiente"])

    def test_sin_dimensiones_quita_el_conector(self):
        metadata = {
            "nombre_material": "Tubo Rectangular e Industrial",
            "marca": "Macopa",
            "descripcion_corta": "industrial",
            "normativa": None,
            "dimensiones_detectadas": None,
        }
        a = nm.analizar(metadata)
        self.assertEqual(a["nombre"], "TUBO RECTANGULAR INDUSTRIAL - Macopa")
        # Sin dimensiones ni calibre no se distingue: hay que pedir el dato.
        self.assertFalse(a["suficiente"])
        self.assertIn("dimensiones", a["faltantes"][0])

    def test_normativa_fuera_del_nombre(self):
        metadata = {"nombre_material": "Tubería de acero", "marca": "Tuacero",
                    "descripcion_corta": "", "normativa": "ASTM A53",
                    "dimensiones_detectadas": None}
        a = nm.analizar(metadata)
        self.assertEqual(a["nombre"], "TUBERÍA DE ACERO - Tuacero")
        self.assertNotIn("ASTM", a["nombre"])
        self.assertFalse(a["suficiente"])
        # Con el diámetro ya alcanza.
        metadata["dimensiones"] = '4"'
        b = nm.analizar(metadata)
        self.assertEqual(b["nombre"], 'TUBERÍA DE ACERO 4" - Tuacero')
        self.assertTrue(b["suficiente"])

    def test_acabado_conserva_su_unidad(self):
        metadata = {"nombre_material": "Cerámica Porcelanato", "marca": "Porcelanato Plus",
                    "categoria": "ARQ", "dimensiones": "60x60 cm"}
        self.assertEqual(nm.generar_nombre_ficha_unico(metadata),
                         "CERÁMICA PORCELANATO 60 x 60 cm - Porcelanato Plus")

    def test_calibre_en_el_nombre(self):
        metadata = {"nombre_material": "Tubo Estructural Rectangular",
                    "marca": "MultiGroup", "categoria": "ESTR",
                    "dimensiones": '6"x2"', "especificacion": "CH13"}
        self.assertEqual(nm.generar_nombre_ficha_unico(metadata),
                         'TUBO ESTRUCTURAL RECTANGULAR 6" x 2" CH 13 - MultiGroup')


# ==========================================================================
# UNA FAMILIA POR TIPO DE MATERIAL
# ==========================================================================
class TestFamilias(unittest.TestCase):

    def _nombre(self, **kw):
        return nm.generar_nombre_ficha_unico(kw)

    def test_agregado_por_presentacion(self):
        self.assertEqual(
            self._nombre(nombre_material="Cemento Hidráulico", marca="Holcim",
                         categoria="ESTR", descripcion_corta="saco de 50 kg"),
            "CEMENTO HIDRÁULICO SACO 50 kg - Holcim")

    def test_pintura_por_envase(self):
        self.assertEqual(
            self._nombre(nombre_material="Pintura Acrílica Satinada Blanco", marca="Sur",
                         categoria="ARQ", descripcion_corta="cubeta de 5 galones"),
            "PINTURA ACRÍLICA SATINADA BLANCO CUBETA 5 gal - Sur")

    def test_electrico_por_tipo_y_modelo(self):
        self.assertEqual(
            self._nombre(nombre_material="Breaker Termomagnético", marca="Schneider",
                         categoria="ELEC",
                         especificacion="2 polos 60 A modelo QO260"),
            "BREAKER TERMOMAGNÉTICO 2P 60 A QO260 - Schneider")

    def test_cable_por_calibre_awg(self):
        self.assertEqual(
            self._nombre(nombre_material="Cable THHN", marca="Viakón",
                         categoria="ELEC", especificacion="#12 AWG"),
            "CABLE THHN #12 AWG - Viakón")

    def test_mecanico_por_diametro_y_serie(self):
        self.assertEqual(
            self._nombre(nombre_material="Tubería PVC", marca="Amanco",
                         categoria="MEC", dimensiones='4"', especificacion="SDR 26"),
            'TUBERÍA PVC 4" SDR 26 - Amanco')

    def test_familia_detectada(self):
        casos = [
            ({"nombre_material": "Tubo Estructural", "categoria": "ESTR"}, nm.FAMILIA_TUBO),
            ({"nombre_material": "Cerámica", "categoria": "ARQ"}, nm.FAMILIA_AREA),
            ({"nombre_material": "Cemento", "categoria": "ESTR"}, nm.FAMILIA_AGREGADO),
            ({"nombre_material": "Cable THHN", "categoria": "ELEC"}, nm.FAMILIA_ELEC),
            ({"nombre_material": "Válvula de compuerta", "categoria": "MEC"}, nm.FAMILIA_MEC),
        ]
        for metadata, esperada in casos:
            self.assertEqual(nm.detectar_familia(metadata), esperada, metadata)

    def test_mensaje_de_falta_es_especifico(self):
        """Cada familia pide el dato que le corresponde."""
        pide = {
            nm.FAMILIA_TUBO: "calibre",
            nm.FAMILIA_AREA: "unidad",
            nm.FAMILIA_AGREGADO: "presentacion",
            nm.FAMILIA_ELEC: "modelo",
            nm.FAMILIA_MEC: "diametro",
        }
        for familia, palabra in pide.items():
            self.assertIn(palabra, nm._que_falta(familia).lower(), familia)


# ==========================================================================
# DIMENSIONES
# ==========================================================================
class TestDimensiones(unittest.TestCase):

    def test_decimal_a_fraccion(self):
        self.assertEqual(nm.decimal_a_fraccion(0.1875), "3/16")
        self.assertEqual(nm.decimal_a_fraccion(0.5), "1/2")
        self.assertEqual(nm.decimal_a_fraccion(1.25), "1 1/4")
        self.assertEqual(nm.decimal_a_fraccion(8), "8")
        self.assertIsNone(nm.decimal_a_fraccion(0.137))   # no es fracción típica
        self.assertIsNone(nm.decimal_a_fraccion("x"))

    def test_pulgadas_se_repiten_y_metricas_van_al_final(self):
        self.assertEqual(nm.formatear_dimensiones('8"x8"x3/16"'), '8" x 8" x 3/16"')
        self.assertEqual(nm.formatear_dimensiones("150x100x1.5 mm"), "150 x 100 x 1.5 mm")
        self.assertEqual(nm.formatear_dimensiones("60x60 cm"), "60 x 60 cm")

    def test_sin_unidad_no_se_inventa(self):
        self.assertEqual(nm.formatear_dimensiones("45x45"), "45 x 45")

    def test_fraccion_sin_unidad_implica_pulgadas(self):
        self.assertEqual(nm.formatear_dimensiones("6x2x1/8"), '6" x 2" x 1/8"')

    def test_medida_unica(self):
        self.assertEqual(nm.formatear_dimensiones('4"'), '4"')
        self.assertEqual(nm.formatear_dimensiones("Ø 2 1/2"), '2 1/2"')
        self.assertEqual(nm.formatear_dimensiones("12 mm"), "12 mm")

    def test_numero_solo_no_es_dimension(self):
        """Un numero sin unidad dentro de texto libre no debe entrar al nombre."""
        self.assertEqual(nm.formatear_dimensiones("resistente hasta 50 años"), "")
        self.assertEqual(nm.formatear_dimensiones("8"), "")

    def test_dict_con_unidad_explicita(self):
        self.assertEqual(
            nm.formatear_dimensiones({"ancho": 150, "largo": 100, "espesor": 1.5,
                                      "unidad": "mm"}),
            "150 x 100 x 1.5 mm")

    def test_dict_ordena_diametro_primero(self):
        self.assertEqual(nm.formatear_dimensiones({"espesor": 0.5, "diametro": 4}),
                         '4" x 1/2"')

    def test_vacios(self):
        for valor in (None, "", {}, "sin medidas"):
            self.assertEqual(nm.formatear_dimensiones(valor), "")

    def test_multiple_se_acepta_como_medida(self):
        """Algunas marcas usan una sola ficha para todo un lineal de productos
        (tubos Amanco, bloques Bloquera PC): MULTIPLE/MULTIPLES es una medida
        valida, no una medida faltante."""
        self.assertEqual(nm.formatear_dimensiones("MULTIPLE"), "MULTIPLE")
        self.assertEqual(nm.formatear_dimensiones("multiples"), "MULTIPLE")
        self.assertEqual(nm.formatear_dimensiones("Múltiples"), "MULTIPLE")
        self.assertEqual(nm.formatear_dimensiones("  Multiple  "), "MULTIPLE")

    def test_multiple_cuenta_como_distintivo_en_analizar(self):
        ficha = {"nombre_material": "Tuberia PVC", "marca": "Amanco",
                 "categoria": "MEC", "dimensiones": "MULTIPLE"}
        r = nm.analizar(ficha)
        self.assertTrue(r["suficiente"])
        self.assertEqual(r["faltantes"], [])
        self.assertIn("MULTIPLE", r["nombre"])


# ==========================================================================
# BORDES
# ==========================================================================
class TestBordes(unittest.TestCase):

    def test_dimensiones_dentro_del_nombre_no_se_duplican(self):
        a = nm.analizar({"nombre_material": "Tubo Estructural 150x100x1.5",
                         "marca": "MultiGroup", "categoria": "ESTR",
                         "dimensiones": "150x100x1.5 mm"})
        self.assertEqual(a["nombre"], "TUBO ESTRUCTURAL 150 x 100 x 1.5 mm - MultiGroup")
        self.assertEqual(a["nombre"].count("150"), 1)

    def test_forma_ya_presente_no_se_repite(self):
        a = nm.analizar({"nombre_material": "Tubo Cuadrado", "marca": "X",
                         "categoria": "ESTR", "descripcion_corta": "cuadrado",
                         "dimensiones": '2"x2"'})
        self.assertEqual(a["nombre"].count("CUADRADO"), 1)

    def test_normativas_se_quitan_del_nombre_del_material(self):
        a = nm.analizar({"nombre_material": "Varilla ASTM A615 grado 60",
                         "marca": "Arcelor", "categoria": "ESTR",
                         "dimensiones": '1/2"'})
        self.assertNotIn("A615", a["nombre"])
        self.assertNotIn("ASTM", a["nombre"])
        self.assertIn("GRADO 60", a["nombre"])

    def test_ficha_vacia_no_reventar(self):
        a = nm.analizar({})
        self.assertEqual(a["nombre"], "")
        self.assertFalse(a["suficiente"])
        self.assertTrue(any("nombre del material" in x for x in a["faltantes"]))
        self.assertEqual(nm.generar_nombre_ficha_unico(None), "")

    def test_sin_marca_se_avisa(self):
        a = nm.analizar({"nombre_material": "Cemento", "descripcion_corta": "saco 50 kg"})
        self.assertEqual(a["nombre"], "CEMENTO SACO 50 kg")
        self.assertFalse(a["suficiente"])
        self.assertTrue(any("marca" in x.lower() for x in a["faltantes"]))

    def test_amperios_no_se_confunden_con_texto(self):
        """'resistente a 60 grados' no debe leerse como 60 amperios."""
        a = nm.analizar({"nombre_material": "Luminaria", "marca": "X",
                         "categoria": "ELEC",
                         "descripcion_corta": "resistente a 60 grados"})
        self.assertNotIn("60 A", a["nombre"])

    def test_clave_unicidad_ignora_formato(self):
        self.assertEqual(nm.clave_unicidad('TUBO 8" x 8" - MultiGroup'),
                         nm.clave_unicidad("tubo 8x8 - multigroup"))
        self.assertNotEqual(nm.clave_unicidad("TUBO 8x8 - A"),
                            nm.clave_unicidad("TUBO 8x9 - A"))

    def test_slug_de_archivo_es_seguro(self):
        s = nm.slug_archivo('TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup')
        self.assertEqual(s, "TUBO-ESTRUCTURAL-CUADRADO-8-x-8-x-3-16-MultiGroup")
        for prohibido in '"/\\:*?<>|':
            self.assertNotIn(prohibido, s)
        self.assertTrue(nm.slug_archivo(""))          # nunca vacío
        self.assertLessEqual(len(nm.slug_archivo("A" * 400)), 110)

    def test_nombre_sin_marca(self):
        self.assertEqual(
            nm.nombre_sin_marca('TUBO ESTRUCTURAL 8" x 8" - MultiGroup', "MultiGroup"),
            'TUBO ESTRUCTURAL 8" x 8"')
        # Sin marca declarada también funciona.
        self.assertEqual(nm.nombre_sin_marca("CEMENTO SACO 50 kg - Holcim"),
                         "CEMENTO SACO 50 kg")
        # Un guion dentro del nombre no confunde.
        self.assertEqual(nm.nombre_sin_marca("CEMENTO SACO 50 kg", "Holcim"),
                         "CEMENTO SACO 50 kg")


# ==========================================================================
# REGRESION: BUGS ENCONTRADOS EN LA REVISION (con fichas reales del proyecto)
# ==========================================================================
class TestRegresionRevision(unittest.TestCase):
    """Cada prueba de aqui corresponde a un bug real que se corrigio.

    Se encontraron probando el generador contra las 71 fichas de
    ``datos_materiales.json`` del propio proyecto.
    """

    def test_pistas_de_familia_no_capturan_subcadenas(self):
        """'cal' no debe capturar 'calibre', 'calidad' ni 'caliente'.

        Sin el \\b de cierre, un tubo galvanizado 'en caliente' se clasificaba
        como agregado y se le pedia una presentacion en sacos.
        """
        tubo = {"nombre_material": "Tubo Estructural Cuadrado", "categoria": "ESTR",
                "marca": "MultiGroup", "especificacion": "CH 13, galvanizado en caliente"}
        self.assertEqual(nm.detectar_familia(tubo), nm.FAMILIA_TUBO)
        a = nm.analizar(tubo)
        self.assertEqual(a["nombre"], "TUBO ESTRUCTURAL CUADRADO CH 13 - MultiGroup")
        self.assertEqual(a["presentacion"], "")
        # 'cal' como palabra propia sigue siendo un agregado.
        self.assertEqual(nm.detectar_familia({"nombre_material": "Cal hidratada"}),
                         nm.FAMILIA_AGREGADO)

    def test_el_modelo_no_se_pierde_por_mala_familia(self):
        breaker = {"nombre_material": "Breaker Termomagnetico", "categoria": "ELEC",
                   "marca": "Schneider",
                   "especificacion": "2 polos 60 A modelo QO260, calibre de cable 12 AWG"}
        self.assertEqual(nm.detectar_familia(breaker), nm.FAMILIA_ELEC)
        self.assertIn("QO260", nm.analizar(breaker)["nombre"])

    def test_equis_mayuscula_separa_dimensiones(self):
        """Los nombres de las fichas vienen en mayusculas: '100X100X2'."""
        self.assertEqual(nm.formatear_dimensiones("100X100X2 mm"), "100 x 100 x 2 mm")
        self.assertEqual(nm.formatear_dimensiones("60 X 60 cm"), "60 x 60 cm")
        a = nm.analizar({"nombre_material": "CERAMICA", "categoria": "ARQ",
                         "marca": "Lanzi", "dimensiones": "60 X 60 cm"})
        self.assertEqual(a["nombre"], "CERAMICA 60 x 60 cm - Lanzi")
        # Y por lo tanto la ficha SI se puede guardar.
        self.assertTrue(a["suficiente"])

    def test_la_preposicion_en_no_se_confunde_con_la_norma_EN(self):
        """'disponible en 12 AWG' perdia el calibre porque 'EN' era normativa."""
        self.assertEqual(nm.quitar_normativas("Aplicar en 2 capas"), "Aplicar en 2 capas")
        d = nm.detectar_designaciones({"especificacion": "Disponible en 12 AWG, 600 V"})
        self.assertIn("#12 AWG", d)
        d2 = nm.detectar_designaciones({"especificacion": "2 polos, disponible en 60 A"})
        self.assertIn("60 A", d2)
        self.assertIn("2P", d2)
        # Las normas de verdad se siguen quitando.
        self.assertNotIn("A500", nm.quitar_normativas("Tubo ASTM A500M grado B"))

    def test_awg_admite_calibres_gruesos(self):
        """1/0, 2/0 y 4/0 colapsaban todos a '#0 AWG': dos cables distintos
        terminaban con el mismo nombre."""
        vistos = set()
        for calibre in ("1/0", "2/0", "4/0", "12"):
            d = nm.detectar_designaciones({"especificacion": f"{calibre} AWG"})
            self.assertEqual(d, [f"#{calibre} AWG"], calibre)
            vistos.add(d[0])
        self.assertEqual(len(vistos), 4)

    def test_grado_y_clase_exigen_numero(self):
        """'grado de humedad' generaba la designacion 'GRADO DE'."""
        for texto in ("grado de humedad controlada", "clase de exposicion",
                      "grado uso pesado"):
            self.assertEqual(nm.detectar_designaciones({"descripcion_corta": texto}),
                             [], texto)
        self.assertEqual(nm.detectar_designaciones({"descripcion_corta": "grado 60"}),
                         ["GRADO 60"])

    def test_la_a_de_un_rango_no_es_amperios(self):
        """'de 20 A 30 mm' es un rango, no 20 amperios."""
        a = nm.analizar({"nombre_material": "LAMINA", "categoria": "ARQ", "marca": "X",
                         "descripcion_corta": "Espesor de 20 A 30 mm"})
        self.assertNotIn("20 A", a["nombre"])
        self.assertNotIn("30 mm", a["nombre"])   # tampoco el extremo del rango
        self.assertFalse(a["suficiente"])
        # Un amperaje de verdad sigue detectandose.
        self.assertEqual(nm.detectar_designaciones({"especificacion": "60 A"}), ["60 A"])

    def test_unidad_compuesta_no_es_presentacion(self):
        """Ficha real: 'Concreto 210 kg/cm2 a 28 dias' no es un saco de 210 kg."""
        a = nm.analizar({"nombre_material": "CONCRETO PREMEZCLADO", "categoria": "ESTR",
                         "marca": "Holcim",
                         "descripcion_corta": "Concreto 210 kg/cm2 a 28 dias"})
        self.assertEqual(a["presentacion"], "")
        self.assertNotIn("210", a["nombre"])
        self.assertFalse(a["suficiente"])        # hay que pedir la presentacion

    def test_rango_en_medida_unica(self):
        """Ficha real: 'tejas de 400 a 500 mm de ancho' no mide 500 mm."""
        self.assertEqual(nm.formatear_dimensiones("tejas de 400 a 500 mm de ancho"), "")
        a = nm.analizar({"nombre_material": "POLICARBONATO SKYLUX", "categoria": "ARQ",
                         "marca": "Skylux",
                         "descripcion_corta": "tejas de 400 a 500 mm de ancho"})
        self.assertNotIn("500", a["nombre"])

    def test_calibre_a_la_tica(self):
        """Fichas reales: 'CAL.24' y '#26' no se reconocian como calibre."""
        self.assertEqual(nm.detectar_designaciones({"descripcion_corta": "CAL.24"}),
                         ["CH 24"])
        self.assertEqual(nm.detectar_designaciones({"descripcion_corta": "#26"}),
                         ["CH 26"])
        a = nm.analizar({"nombre_material": "LAMINA CANAL RECTANGULAR ESMALTADA",
                         "categoria": "ARQ", "marca": "Metalica",
                         "descripcion_corta": "#26"})
        self.assertTrue(a["suficiente"])
        # El calibre pegado al nombre no se duplica: se normaliza a "CH 26".
        b = nm.analizar({"nombre_material": "LAMINA CANAL RECTANGULAR ESMALTADA #26",
                         "categoria": "ARQ", "marca": "Terracota Plus"})
        self.assertEqual(b["nombre"],
                         "LAMINA CANAL RECTANGULAR ESMALTADA CH 26 - Terracota Plus")
        c = nm.analizar({"nombre_material": "CUBIERTA BANDEJA BLP-250 CAL.24",
                         "categoria": "ARQ", "marca": "Metalica"})
        self.assertEqual(c["nombre"], "CUBIERTA BANDEJA BLP-250 CH 24 - Metalica")
        # '#12 AWG' sigue siendo AWG, no calibre de lamina.
        self.assertEqual(nm.detectar_designaciones({"especificacion": "#12 AWG"}),
                         ["#12 AWG"])

    def test_dict_ignora_metadatos_que_no_son_medidas(self):
        """Una clave 'confianza' del OCR entraba como dimension."""
        self.assertEqual(
            nm.formatear_dimensiones({"ancho": 8, "largo": 8, "espesor": 0.1875,
                                      "confianza": 0.97, "paginas": 3}),
            '8" x 8" x 3/16"')

    def test_valores_no_finitos_no_lanzan(self):
        """json.loads acepta Infinity/NaN: no deben llegar como traceback."""
        self.assertIsNone(nm.decimal_a_fraccion(float("inf")))
        self.assertIsNone(nm.decimal_a_fraccion(float("nan")))
        self.assertEqual(nm.formatear_dimensiones({"ancho": float("nan"),
                                                   "largo": float("inf")}), "")
        # Y el nombre se genera igual, sin dimensiones.
        a = nm.analizar({"nombre_material": "Tubo", "marca": "X",
                         "dimensiones_detectadas": {"ancho": float("nan")}})
        self.assertEqual(a["nombre"], "TUBO - X")

    def test_presentacion_sin_cantidad_no_alcanza(self):
        """'SACO' a secas no distingue un saco de 25 kg de uno de 50 kg."""
        a = nm.analizar({"nombre_material": "MORTERO", "categoria": "ESTR", "marca": "Y",
                         "descripcion_corta": "se vende en saco"})
        self.assertEqual(a["presentacion"], "SACO")
        self.assertIn("SACO", a["nombre"])
        self.assertFalse(a["suficiente"])
        # Con la cantidad si alcanza.
        b = nm.analizar({"nombre_material": "MORTERO", "categoria": "ESTR", "marca": "Y",
                         "descripcion_corta": "saco de 40 kg"})
        self.assertTrue(b["suficiente"])

    def test_fichas_reales_del_proyecto(self):
        """Pasa el generador por todas las fichas de datos_materiales.json.

        No se comprueba el nombre exacto (son datos de obra que cambian), sino
        que nada revienta y que ningun nombre queda con basura evidente.
        """
        p = Path(__file__).resolve().parent / "datos_materiales.json"
        if not p.exists():
            self.skipTest("no hay datos_materiales.json en el proyecto")
        datos = json.loads(p.read_text(encoding="utf-8"))
        materiales = datos.get("materiales", [])
        self.assertTrue(materiales)
        for m in materiales:
            metadata = {"nombre_material": m.get("nombre", ""),
                        "marca": (m.get("marca") or "").split(" / ")[0],
                        "categoria": m.get("categoria", ""),
                        "normativa": m.get("normativa", ""),
                        "descripcion_corta": m.get("descripcion", "")}
            a = nm.analizar(metadata)
            self.assertIsInstance(a["nombre"], str)
            for basura in ("GRADO DE", "CLASE DE", "None", "  "):
                self.assertNotIn(basura, a["nombre"], f"{m.get('nombre')} -> {a['nombre']}")
            # Palabra completa: "expANSIvo" contiene "ANSI" y no es una norma.
            for norma in ("ASTM", "INTE", "ANSI", "NFPA", "ISO"):
                self.assertIsNone(
                    re.search(rf"\b{norma}\b", a["nombre"].upper()),
                    f"{m.get('nombre')} -> {a['nombre']}")


# ==========================================================================
# INTEGRACION CON LA BD
# ==========================================================================
class TestIntegracionBD(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.m = bd.BDManager(bd_root=self.tmp / "BD", cache_dir=self.tmp / "cache",
                              config_dir=self.tmp / "cfg")
        self.m.inicializar_bd()
        self.pdf = self.tmp / "ficha.pdf"
        self.pdf.write_bytes(PDF)
        self.pdf2 = self.tmp / "otra.pdf"
        self.pdf2.write_bytes(PDF + b"DISTINTO")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _alta(self, **kw):
        datos = {"nombre_material": "Tubo Estructural", "marca": "MultiGroup",
                 "categoria": "ESTR", "dimensiones": '8"x8"x3/16"',
                 "descripcion_corta": "cuadrado"}
        datos.update(kw)
        return self.m.agregar_ficha(str(kw.pop("_pdf", self.pdf)), datos)

    def test_alta_genera_nombre_y_nombra_el_pdf(self):
        f = self._alta()
        self.assertEqual(f["nombre_ficha"],
                         'TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup')
        self.assertFalse(f["nombre_ficha_manual"])
        # El PDF se guarda con el nombre descriptivo: la carpeta se lee sin abrir
        # el indice.
        self.assertEqual(f["ruta_pdf"],
                         "ESTR/TUBO-ESTRUCTURAL-CUADRADO-8-x-8-x-3-16-MultiGroup.pdf")
        self.assertTrue((self.m.bd_root / f["ruta_pdf"]).exists())

    def test_nombre_manual_se_respeta(self):
        f = self._alta(nombre_ficha="MI NOMBRE A MANO 8x8")
        self.assertEqual(f["nombre_ficha"], "MI NOMBRE A MANO 8x8")
        self.assertTrue(f["nombre_ficha_manual"])
        # Y no se regenera al editar otros campos.
        act = self.m.editar_ficha(f["id"], {"marca": "Metalco"})
        self.assertEqual(act["nombre_ficha"], "MI NOMBRE A MANO 8x8")

    def test_editar_regenera_el_nombre(self):
        f = self._alta()
        act = self.m.editar_ficha(f["id"], {"dimensiones": '6"x2"',
                                            "especificacion": "CH 13"})
        self.assertEqual(act["nombre_ficha"],
                         'TUBO ESTRUCTURAL CUADRADO 6" x 2" CH 13 - MultiGroup')

    def test_regenerar_nombre_forzado_sobre_uno_manual(self):
        f = self._alta(nombre_ficha="NOMBRE VIEJO")
        act = self.m.editar_ficha(f["id"], {}, regenerar_nombre=True)
        self.assertEqual(act["nombre_ficha"],
                         'TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16" - MultiGroup')
        self.assertFalse(act["nombre_ficha_manual"])

    def test_el_nombre_es_buscable(self):
        f = self._alta()
        self.assertIn("multigroup", f["search_keywords"])
        for consulta in ("tubo 8", "cuadrado 8", "tubo estructural cuadrado"):
            ids = [x["id"] for x in self.m.buscar(consulta)]
            self.assertIn(f["id"], ids, consulta)

    def test_deteccion_de_duplicados(self):
        f = self._alta()
        self.assertIsNotNone(self.m.buscar_por_nombre(f["nombre_ficha"]))
        # Tolerante al formato del nombre.
        self.assertIsNotNone(
            self.m.buscar_por_nombre("tubo estructural cuadrado 8x8x3/16 - multigroup"))
        # No se confunde con otra medida.
        self.assertIsNone(
            self.m.buscar_por_nombre('TUBO ESTRUCTURAL CUADRADO 9" x 8" x 3/16" - MultiGroup'))
        # Y se puede excluir la propia ficha (al editarla).
        self.assertIsNone(self.m.buscar_por_nombre(f["nombre_ficha"], excluir_id=f["id"]))

    def test_dos_fichas_del_mismo_material_se_distinguen(self):
        a = self._alta()
        b = self._alta(dimensiones='6"x2"', descripcion_corta="rectangular")
        self.assertNotEqual(a["nombre_ficha"], b["nombre_ficha"])
        self.assertNotEqual(a["ruta_pdf"], b["ruta_pdf"])

    def test_reemplazar_pdf_conserva_id_y_nombre(self):
        f = self._alta()
        ruta = f["ruta_pdf"]
        hash_viejo = f["hash_archivo"]
        act = self.m.reemplazar_pdf_ficha(f["id"], str(self.pdf2))
        self.assertEqual(act["id"], f["id"])
        self.assertEqual(act["ruta_pdf"], ruta)
        self.assertEqual(act["nombre_ficha"], f["nombre_ficha"])
        self.assertNotEqual(act["hash_archivo"], hash_viejo)
        self.assertEqual((self.m.bd_root / ruta).read_bytes(), PDF + b"DISTINTO")
        # El cache se refresca (no devuelve el PDF viejo).
        self.assertEqual(Path(self.m.ruta_local_ficha(act)).read_bytes(),
                         PDF + b"DISTINTO")

    def test_soft_delete_sigue_siendo_reversible(self):
        """Se conserva el borrado logico: es lo que permite fusionar dos BDs."""
        f = self._alta()
        self.m.soft_delete_ficha(f["id"])
        self.assertEqual(len(self.m.listar_fichas()), 0)
        self.assertTrue((self.m.bd_root / f["ruta_pdf"]).exists())
        self.assertTrue(self.m.reactivar_ficha(f["id"]))
        self.assertEqual(len(self.m.listar_fichas()), 1)

    def test_migracion_de_fichas_sin_nombre(self):
        """Fichas cargadas con v3.1.0 (sin nombre_ficha)."""
        f = self._alta()
        data = self.m.cargar_indice()
        for x in data["fichas"]:
            x.pop("nombre_ficha", None)
            x.pop("nombre_ficha_manual", None)
        self.m._guardar_indice(data)

        self.assertEqual(len(self.m.fichas_sin_nombre()), 1)
        # nombre_de() lo calcula al vuelo, sin escribir.
        vieja = self.m.obtener_ficha(f["id"])
        self.assertTrue(self.m.nombre_de(vieja))
        self.assertEqual(len(self.m.fichas_sin_nombre()), 1)
        # migrar lo persiste, y es idempotente.
        self.assertEqual(self.m.migrar_nombres_ficha(), 1)
        self.assertEqual(self.m.fichas_sin_nombre(), [])
        self.assertEqual(self.m.migrar_nombres_ficha(), 0)

    def test_aviso_de_ficha_en_uso(self):
        f = self._alta()
        proyecto = {"nombre_proyecto": "Obra Muni",
                    "datos_procedimiento": {"numero_procedimiento": "1",
                                            "institucion": "M", "detalle": "d",
                                            "plazo": "p", "monto": "1"},
                    "materiales_seleccionados": [
                        {"consecutivo": "ESTR01", "id_ficha_bd": f["id"],
                         "categoria": "ESTR", "nombre_material": "Tubo",
                         "marca": "MultiGroup"}]}
        self.m.guardar_submittal(proyecto)
        uso = self.m.proyectos_que_usan(f["id"])
        self.assertEqual(len(uso), 1)
        self.assertEqual(uso[0]["nombre_proyecto"], "Obra Muni")
        self.assertEqual(uso[0]["consecutivo"], "ESTR01")
        self.assertEqual(self.m.proyectos_que_usan("otro-id"), [])

    def test_imagen_conserva_su_extension(self):
        """Guardar un .jpg como '.pdf' rompia el compilado en silencio."""
        jpg = self.tmp / "ficha.jpg"
        jpg.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)   # cabecera JPEG
        f = self.m.agregar_ficha(str(jpg), {
            "nombre_material": "Lámina", "marca": "Metalica", "categoria": "ARQ",
            "descripcion_corta": "#26"})
        self.assertTrue(f["ruta_pdf"].endswith(".jpg"), f["ruta_pdf"])
        self.assertTrue((self.m.bd_root / f["ruta_pdf"]).exists())

    def test_reemplazar_valida_y_ajusta_la_extension(self):
        f = self._alta()
        # Un archivo vacio o que no es PDF se rechaza.
        malo = self.tmp / "vacio.pdf"
        malo.write_bytes(b"")
        with self.assertRaises(bd.BDError):
            self.m.reemplazar_pdf_ficha(f["id"], str(malo))
        no_pdf = self.tmp / "falso.pdf"
        no_pdf.write_bytes(b"esto no es un pdf")
        with self.assertRaises(bd.BDError):
            self.m.reemplazar_pdf_ficha(f["id"], str(no_pdf))
        # Cambiar a imagen ajusta la ruta y borra el archivo anterior.
        jpg = self.tmp / "nueva.jpg"
        jpg.write_bytes(b"\xff\xd8\xff\xe0" + b"1" * 64)
        vieja = f["ruta_pdf"]
        act = self.m.reemplazar_pdf_ficha(f["id"], str(jpg))
        self.assertTrue(act["ruta_pdf"].endswith(".jpg"))
        self.assertFalse((self.m.bd_root / vieja).exists())
        self.assertTrue((self.m.bd_root / act["ruta_pdf"]).exists())

    def test_cache_se_invalida_por_hash_no_por_tamano(self):
        """Si el reemplazo pesa lo mismo, el cache devolvia el archivo viejo."""
        f = self._alta()
        primera = Path(self.m.ruta_local_ficha(f))
        self.assertEqual(primera.read_bytes(), PDF)
        mismo_tamano = self.tmp / "mismo.pdf"
        mismo_tamano.write_bytes(PDF[:-1] + b"Z")
        self.assertEqual(len(mismo_tamano.read_bytes()), len(PDF))
        act = self.m.reemplazar_pdf_ficha(f["id"], str(mismo_tamano))
        self.assertEqual(Path(self.m.ruta_local_ficha(act)).read_bytes(),
                         PDF[:-1] + b"Z")

    def test_migrar_no_pisa_ediciones_remotas(self):
        """La migracion de nombres es cosmetica: no debe tocar
        fecha_modificacion, que es lo que decide los conflictos entre PCs."""
        f = self._alta()
        data = self.m.cargar_indice()
        for x in data["fichas"]:
            x.pop("nombre_ficha", None)
            x["fecha_modificacion"] = "2020-01-01T00:00:00"
        self.m._guardar_indice(data)
        self.m.migrar_nombres_ficha()
        self.assertEqual(self.m.obtener_ficha(f["id"])["fecha_modificacion"],
                         "2020-01-01T00:00:00")

    def test_materializar_empareja_por_consecutivo(self):
        """Con la lista de materiales desordenada, el PDF iba a la carpeta de
        otro material."""
        a = self._alta()
        b = self._alta(nombre_material="Cemento", marca="Holcim",
                       dimensiones="", descripcion_corta="saco de 50 kg",
                       _pdf=self.pdf2)
        proyecto = {
            "nombre_proyecto": "Desordenado",
            "datos_procedimiento": {"numero_procedimiento": "1", "institucion": "M",
                                    "detalle": "d", "plazo": "p", "monto": "1"},
            # A proposito en orden inverso al consecutivo.
            "materiales_seleccionados": [
                {"consecutivo": "ESTR02", "id_ficha_bd": b["id"], "categoria": "ESTR",
                 "nombre_material": "Cemento", "marca": "Holcim"},
                {"consecutivo": "ESTR01", "id_ficha_bd": a["id"], "categoria": "ESTR",
                 "nombre_material": "Tubo", "marca": "MultiGroup"},
            ]}
        destino = self.tmp / "salida"
        self.m.materializar_proyecto(proyecto, destino)
        datos = json.loads((destino / "datos_materiales.json").read_text(encoding="utf-8"))
        for mat in datos["materiales"]:
            esperada = a if mat["consecutivo"] == "ESTR01" else b
            archivo = Path(mat["ruta_carpeta"]) / Path(esperada["ruta_pdf"]).name
            self.assertTrue(archivo.exists(),
                            f"{mat['consecutivo']} no recibió su propia ficha")

    def test_nombre_de_material_en_entregables_sin_marca(self):
        """En carátulas y Excel el nombre va sin la marca (tiene su columna)."""
        f = self._alta()
        limpio = nm.nombre_sin_marca(f["nombre_ficha"], f["marca"])
        self.assertEqual(limpio, 'TUBO ESTRUCTURAL CUADRADO 8" x 8" x 3/16"')
        proyecto = {"materiales_seleccionados": [
            {"consecutivo": "ESTR01", "id_ficha_bd": f["id"], "categoria": "ESTR",
             "nombre_material": limpio, "marca": f["marca"]}]}
        datos = self.m.construir_datos_materiales(proyecto, self.tmp / "out")
        self.assertEqual(datos["materiales"][0]["nombre"], limpio)
        self.assertEqual(datos["materiales"][0]["marca"], "MultiGroup")


if __name__ == "__main__":
    unittest.main(verbosity=2)
