#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas offline del campo de marcas múltiples de v2.6.10."""

import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import submitals_gui as app


class MarcasMultiplesTests(unittest.TestCase):
    def test_elimina_duplicados_y_valores_genericos(self):
        marcas = app._marcas_unicas_distintas([
            "Durman", "DURMAN", "SIN ESPECIFICAR", "", "Amanco",
        ])
        self.assertEqual(marcas, ["Durman", "Amanco"])

    def test_conserva_orden_y_formato_visible(self):
        marcas = app._marcas_unicas_distintas([
            "3M", "Sika Costa Rica", "Fosroc",
        ])
        self.assertEqual(marcas, ["3M", "Sika Costa Rica", "Fosroc"])

    def test_construir_materiales_une_marcas_distintas(self):
        with tempfile.TemporaryDirectory() as temporal:
            base = Path(temporal)
            carpeta = base / "ESTRUCTURALES" / "ESTR01-SELLADOR"
            carpeta.mkdir(parents=True)
            (carpeta / "ficha-a.pdf").write_bytes(b"a")
            (carpeta / "ficha-b.pdf").write_bytes(b"b")
            relacion = {
                "relacion": "MISMA_FAMILIA_DISTINTA_MARCA",
                "marcas": ["Sika", "Fosroc", "SIKA"],
                "tipos_producto": ["sellador"],
                "justificacion": "Mismo producto, fabricantes distintos.",
            }
            with patch.object(
                    app, "extraer_texto_robusto",
                    side_effect=["Ficha Sika", "Ficha Fosroc"]), \
                    patch.object(app, "_render_portada_b64", return_value=None), \
                    patch.object(
                        app, "analizar_relacion_fichas",
                        return_value=relacion), \
                    patch.object(
                        app, "extraer_con_chatgpt",
                        return_value=(
                            "Sika", "Sellador para construcción", "ASTM C920",
                            "español", False)):
                materiales, total = app.construir_materiales(
                    base, "clave-prueba", queue.Queue(), threading.Event())

        self.assertEqual(total, 2)
        self.assertEqual(materiales[0]["marca"], "Sika / Fosroc")


if __name__ == "__main__":
    unittest.main()
