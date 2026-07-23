#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test rapido y GRATIS (no llama a OpenAI) del fix v2.6.5:
  - es_tabla_tecnica_densa()
  - extraer_resumen_tabla_pdfplumber()
  - _desc_parece_valida()

Recorre las fichas tecnicas reales de este proyecto (ARQUITECTONICOS,
ESTRUCTURALES, MECANICOS, ELECTRICOS) y reporta en cuales detecto una tabla
tecnica densa y si pdfplumber pudo releerla. No modifica ningun archivo.

Uso:
    python test_tablas_tecnicas.py
"""
from pathlib import Path
import submitals_gui as app

BASE = Path(__file__).resolve().parent


def main():
    print(f"Generador de Submittals — test offline v2.6.5 (VERSION app: {app.VERSION})\n")

    fichas = []
    for madre in app.CARPETAS_MADRE:
        d = BASE / madre
        if not d.is_dir():
            continue
        for sub in sorted(d.iterdir()):
            if not sub.is_dir():
                continue
            fichas += app.buscar_archivos_carpeta(sub)

    pdfs = [f for f in fichas if f.suffix.lower() == ".pdf"]
    print(f"Fichas PDF encontradas: {len(pdfs)}\n")

    detectadas, releidas = 0, 0
    for f in pdfs:
        try:
            t = app.extraer_texto_robusto(f)
        except Exception as e:
            print(f"[ERROR leyendo] {f.relative_to(BASE)}: {e}")
            continue
        seg = t[:1500]
        if app.es_tabla_tecnica_densa(seg):
            detectadas += 1
            resumen = app.extraer_resumen_tabla_pdfplumber(f)
            ok = bool(resumen)
            releidas += ok
            print(f"[TABLA DENSA{' + pdfplumber OK' if ok else ' - sin tabla via pdfplumber'}] "
                  f"{f.relative_to(BASE)}")

    print(f"\nResumen: {detectadas} ficha(s) detectada(s) como tabla tecnica densa "
          f"de {len(pdfs)} PDF(s); {releidas} releidas con exito via pdfplumber.")

    print("\n--- _desc_parece_valida() ---")
    casos = [
        ("Conexion sanitaria DWV SCH40 de diversos diametros, norma ASTM D2466", True),
        ("42.54 0.10 42.04 0.13 60.71 0.15 89.41 0.20", False),
        ("", False),
    ]
    for desc, esperado in casos:
        resultado = app._desc_parece_valida(desc)
        estado = "OK" if resultado == esperado else "FALLO"
        print(f"[{estado}] '{desc[:50]}' -> {resultado} (esperado {esperado})")


if __name__ == "__main__":
    main()
