# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
for paquete in ('playwright', 'jinja2', 'pypdf', 'pytesseract', 'PIL', 'docx',
                'fitz', 'openpyxl', 'pdfplumber', 'openai', 'pydantic',
                'requests', 'bs4', 'packaging'):
    tmp_ret = collect_all(paquete)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

datas += [
    # generate_caratulas.py se carga en tiempo de ejecucion (importlib), no
    # como un import normal: sin esto PyInstaller no lo empaqueta solo.
    ('generate_caratulas.py', '.'),
    ('template_caratula.html', '.'),
    ('template_ministerio_salud.html', '.'),
    ('Tabla visual refresh/assets/logo_es_crop.png', 'Tabla visual refresh/assets'),
    ('Tabla visual refresh/assets/ministerio_salud_banner.png', 'Tabla visual refresh/assets'),
    ('assets/icono_app.ico', 'assets'),
    ('assets/icono_app.png', 'assets'),
    ('assets/icono_header.png', 'assets'),
]


a = Analysis(
    ['submitals_gui_v3.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GeneradorSubmittalsES_v3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icono_app.ico',
)
