#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas offline de la mejora de imagen de v2.6.8 (no consumen API)."""

import unittest
import queue
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw

import submitals_gui as app


class MejoraImagenTests(unittest.TestCase):
    def test_detecta_imagen_pequena(self):
        img = Image.new("RGB", (560, 470), "#eeeeee")
        ImageDraw.Draw(img).text(
            (20, 20), "FICHA TECNICA ASTM F436", fill="#777777")
        calidad = app.evaluar_calidad_imagen(img)
        self.assertTrue(calidad["necesita_mejora"])
        self.assertEqual((calidad["ancho"], calidad["alto"]), img.size)

    def test_amplia_sin_cambiar_proporcion(self):
        img = Image.new("RGB", (560, 470), "white")
        mejorada = app.mejorar_imagen_para_lectura(img)
        try:
            self.assertEqual(mejorada.mode, "RGB")
            self.assertGreater(mejorada.width, img.width)
            self.assertAlmostEqual(
                mejorada.width / mejorada.height,
                img.width / img.height,
                places=2)
            self.assertLessEqual(max(mejorada.size), 2800)
        finally:
            mejorada.close()

    def test_normaliza_auditoria_visual(self):
        data = app._datos_extraccion_visual({
            "marca": "",
            "descripcion": "Arandela estructural",
            "normativa": "ASTM F436",
            "idioma_original": "español",
            "fue_traducido": False,
            "evidencias": ["ASTM F436", "", "ARANDELA F436"],
        })
        self.assertEqual(data["marca"], app.SIN_ESP)
        self.assertEqual(data["normativa"], "ASTM F436")
        self.assertEqual(len(data["evidencias"]), 2)

    def test_vision_se_usa_aunque_ocr_quede_vacio(self):
        with tempfile.TemporaryDirectory() as temporal:
            base = Path(temporal)
            carpeta = base / "ESTRUCTURALES" / "ESTR01-ARANDELA"
            carpeta.mkdir(parents=True)
            Image.new("RGB", (80, 60), "white").save(carpeta / "ficha.png")
            audit = {"metodo": "prueba", "requiere_revision_manual": False}
            with patch.object(app, "extraer_texto_robusto", return_value=""), \
                    patch.object(
                        app, "extraer_imagenes_con_ia",
                        return_value=(
                            app.SIN_ESP, "Arandela estructural", "ASTM F436",
                            "español", False, audit)) as vision:
                materiales, total = app.construir_materiales(
                    base, "clave-prueba", queue.Queue(), threading.Event())
            self.assertEqual(total, 1)
            self.assertEqual(materiales[0]["normativa"], "ASTM F436")
            self.assertEqual(materiales[0]["auditoria_extraccion"], audit)
            vision.assert_called_once()


if __name__ == "__main__":
    unittest.main()
