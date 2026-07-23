# GUÍA — Continuar el desarrollo en Claude Code

Cómo retomar el **Generador de Submittals v2.5.1** desde la línea de comandos con
Claude Code (o cualquier terminal).

## 1. Preparar el entorno
```bash
cd "C:\Users\castr\Downloads\Submitals ES"

python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS/Linux

pip install -r requirements.txt
python -m playwright install chromium
```
(Opcional, OCR de imágenes) instalar Tesseract-OCR:
https://github.com/UB-Mannheim/tesseract/wiki

## 2. Ejecutar / depurar
```bash
python submitals_gui.py          # correr la app
python -m pdb submitals_gui.py   # depurar con pdb
python -m py_compile submitals_gui.py generate_caratulas.py   # chequeo de sintaxis
```

## 3. Verificar sin abrir la GUI (headless)
Como el entorno de línea de comandos puede no tener pantalla, se puede probar la
lógica que NO depende de Tkinter con un stub. Ejemplo:
```python
import sys, types
tk = types.ModuleType("tkinter"); tk.Tk = type("Tk", (object,), {})
for n in ("StringVar","BooleanVar","Frame","Label","Button","Entry",
          "Checkbutton","Text","Toplevel","Radiobutton"):
    setattr(tk, n, type(n, (object,), {}))
for m in ("tkinter.ttk","tkinter.filedialog","tkinter.messagebox"):
    sys.modules[m] = types.ModuleType(m)
sys.modules["tkinter"] = tk
tk.ttk = sys.modules["tkinter.ttk"]; tk.ttk.Combobox = object
tk.ttk.Progressbar = object; tk.ttk.Style = object
tk.filedialog = sys.modules["tkinter.filedialog"]
tk.messagebox = sys.modules["tkinter.messagebox"]

import importlib.util
spec = importlib.util.spec_from_file_location("sg", "submitals_gui.py")
sg = importlib.util.module_from_spec(spec); spec.loader.exec_module(sg)
print(sg.VERSION, sg.CARPETAS_MADRE, sg.VISION_MODEL)
```
Con esto se pueden probar funciones puras: `capitalizar_numero`, `_sicop_vision`
(mockeando `openai`), `construir_materiales`, `resumen_materiales`, etc.

Para probar generación real de un PDF sin GUI, llamar a `sg.hilo_trabajo(...)`
en modo `"existente"` con un `datos_materiales.json` de 1 material (ver ejemplos
en los CHANGELOG de v2.3–v2.5).

## 4. Workflow recomendado para cambios
1. Leer `MEMORIA-Generador-Submittals-v2.5.1-COMPLETA.md` (arquitectura §17).
2. Hacer el cambio **solo en `submitals_gui.py`** salvo que sea imprescindible tocar
   el motor.
3. `python -m py_compile submitals_gui.py` (debe compilar).
4. Probar en headless (stub) la lógica afectada.
5. Probar la GUI real en Windows.
6. Actualizar `submitals_config.json` (version) y el CHANGELOG.
7. Si aplica, recompilar el `.exe` (ver memoria §12).

## 5. Dónde tocar cada cosa
| Necesito… | Archivo / función |
|---|---|
| Cambiar la interfaz | `submitals_gui.py` → `SubmitalsGUI._construir_ui` |
| Cambiar el flujo de generación | `submitals_gui.py` → `hilo_trabajo` |
| Cambiar extracción con IA / prompt | `submitals_gui.py` → `PROMPT_TXT`, `extraer_con_chatgpt` |
| Cambiar SICOP (navegación) | `submitals_gui.py` → `_sicop_screenshot` |
| Cambiar SICOP (lectura Vision) | `submitals_gui.py` → `_sicop_vision`, `VISION_MODEL` |
| Agregar una disciplina | `CARPETAS_MADRE`, `MADRE_A_PREFIJO`, `ORDEN_CAT` |
| Agregar una carátula/template | `CARATULAS` + nuevo `template_*.html` |
| Cambiar cómo se pinta el PDF | `generate_caratulas.py` → `process_material` (con cuidado) |
| Campos del PDF | los `template_*.html` (variables Jinja2) |

## 6. Reglas de oro
- **No relanzar el `.exe`**: nunca usar `subprocess([sys.executable, ...])` cuando
  `getattr(sys, "frozen", False)` sea True (causa el bug de múltiples ventanas).
- Mantener **instancia única** (`instancia_unica()`) y `multiprocessing.freeze_support()`.
- La **API key nunca** se imprime en log ni se copia al portapapeles.
- Cerrar recursos (`Image`, buffers, `PdfWriter`) en `finally`.
- Textos de UI y comentarios en español.

## 7. Comandos útiles de Claude Code
```bash
# buscar dónde se define algo
grep -n "def hilo_trabajo" submitals_gui.py
grep -n "VISION_MODEL\|SICOP_URL\|CARATULAS" submitals_gui.py

# ver diferencias antes de guardar (si usas git)
git diff submitals_gui.py

# recompilar sintaxis rápido
python -m py_compile submitals_gui.py && echo OK
```

## 8. Cuando SICOP falle en vivo
1. Abrir SICOP manualmente y localizar el campo de búsqueda del procedimiento.
2. Ajustar `SICOP_URL` y/o la lista de selectores en `_sicop_screenshot()`.
3. La extracción por Vision (`_sicop_vision`) casi no necesita cambios: lee la
   imagen; si la pantalla capturada muestra los datos, los devolverá.
4. Como respaldo, siempre está el ingreso manual en "Datos del proyecto".
