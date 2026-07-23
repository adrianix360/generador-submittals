================================================================================
TAREA: Generador de Submittals - ES Constructora  →  VERSIÓN v2.3
Solo trabajar los cambios listados. Construye sobre v2.2 (funcional).
================================================================================

IMPORTANTE PARA QUIEN EJECUTA ESTE PROMPT (Opus):
- Esta es la v2.3. La v2.2 YA FUNCIONA. Agrega SOLO lo nuevo de este documento y
  NO rompas nada de lo existente.
- Verifica siempre que el código COMPILE (py_compile) y que la lógica que no
  dependa de pantalla la puedas probar en modo headless. tkinter, os.startfile,
  portapapeles y las llamadas reales a OpenAI solo corren en la PC Windows de la
  usuaria; esos se validan por lógica.
- Entrega archivos completos y funcionales + documentación (INSTRUCCIONES y
  CHANGELOG) + checklist marcado.

================================================================================
PARTE 1 — CONTEXTO Y ESTADO ACTUAL (v2.2)
================================================================================
Proyecto: "Generador de Submittals - ES Constructora". Responsable: Adrián Castro.
Ubicación base: C:\Users\castr\Downloads\Submitals ES
Propósito: para cada carpeta de material (ARQ##, ESTR##, MEC##) leer sus fichas
técnicas, extraer datos con ChatGPT y generar una CARÁTULA PDF (portada) y un
COMPILADO PDF (carátula + fichas).

ARCHIVOS ACTUALES (NO renombrar sin necesidad):
  submitals_gui.py            → app tkinter principal (v2.2)  [MODIFICAR a v2.3]
  submitals_config.json       → configuración persistente     [ACTUALIZAR]
  generate_caratulas.py       → MOTOR que renderiza el HTML a PDF (Jinja2 +
                                 Playwright/WeasyPrint/pdfkit). Modificar SOLO si
                                 es imprescindible para el selector de plantilla
                                 y los campos nuevos; de preferencia parametrizar.
  template_caratula.html      → carátula CLÁSICA (roja #E11D2D, genérica ES)
  template_ministerio_salud.html → carátula MINISTERIO DE SALUD (azul #001F60)
  Tabla visual refresh/assets/logo_es_crop.png            (logo ES)
  Tabla visual refresh/assets/ministerio_salud_banner.png (logo Ministerio)
  datos_materiales.json       → salida con la lista de materiales
  MEMORIA / CHANGELOG / INSTRUCCIONES *.md/.txt

CÓMO FUNCIONA HOY (resumen v2.2):
1. La usuaria abre la app, ingresa su API Key de OpenAI (se guarda ofuscada
   base64 en submitals_config.json), elige la carpeta base y pulsa GENERAR.
2. Modo automático: escanea subcarpetas, lee TODAS las fichas de cada una
   (PDF texto, PDF escaneado por OCR con PyMuPDF+Tesseract, JPG/PNG/BMP/TIFF por
   OCR, DOCX), envía todo a ChatGPT (gpt-4o-mini) que FUSIONA y devuelve
   {marca, descripcion, normativa}. Construye datos_materiales.json.
3. Genera la carátula por material (motor) y luego el compilado
   "<CONS>-<NOMBRE>-CMP.pdf" (carátula pág.1 + fichas pág.2+).
4. Threading con 5 fases, barra de progreso, botón Cancelar, panel de
   Mantenimiento (cambiar/limpiar/probar API key, resetear config).
5. Motor: intenta Playwright (Chromium) → WeasyPrint → pdfkit. Playwright es el
   recomendado en Windows.
6. Estructura JSON por material: consecutivo, nombre, categoria, marca,
   descripcion, normativa, documentos_encontrados, compilado_generado, estado,
   carpeta_vacia, ruta_carpeta.

La carátula del Ministerio (template_ministerio_salud.html) ya usa variables
Jinja2: logo_ministerio, consecutivo, nombre_comercial, fabricante,
descripcion_tecnica, normativa, documentacion_tecnica, observaciones_material,
registro, version, fecha_emision, proyecto, cliente, plazo, contrato, monto,
nombre_cargo, fecha, estado, fecha_revision, observaciones_respuesta, revisa.
La carátula clásica (template_caratula.html) usa: logo_path, consecutivo,
nombre_comercial, fabricante, descripcion_tecnica, normativa.

================================================================================
PARTE 2 — CAMBIOS SOLICITADOS PARA v2.3 (5)
================================================================================

--------------------------------------------------------------------------------
CAMBIO 1 — AUTO-VERIFICACIÓN E INSTALACIÓN DE DEPENDENCIAS ("bootstrap")
--------------------------------------------------------------------------------
Objetivo: que la app funcione en CUALQUIER computadora que solo tenga Python
instalado. Al arrancar, debe consultar al sistema si tiene TODAS las
dependencias necesarias y, si faltan, instalarlas de inmediato.

Requisitos:
1. Al iniciar (antes de abrir la ventana principal), ejecutar un "bootstrap" que:
   a) Verifique la versión de Python (mínimo 3.9). Si es menor, mostrar mensaje
      claro y detener.
   b) Detecte qué paquetes pip faltan de esta lista y los instale:
        jinja2, openai, pypdf, pymupdf, pytesseract, Pillow, python-docx,
        playwright
      (usar importlib.util.find_spec para detectar; instalar los faltantes con
       subprocess: [sys.executable, "-m", "pip", "install", ...]).
   c) Verifique el navegador de Playwright (Chromium). Si falta, ejecutar
        [sys.executable, "-m", "playwright", "install", "chromium"].
   d) Verifique Tesseract-OCR (binario del sistema, NO es pip). Como no se puede
      instalar en silencio de forma fiable en todas las PCs:
        - Detectar con shutil.which("tesseract") o la ruta típica
          C:\Program Files\Tesseract-OCR\tesseract.exe.
        - Si NO está: avisar que el OCR de imágenes/PDF escaneado no funcionará,
          ofrecer abrir el enlace de descarga
          (https://github.com/UB-Mannheim/tesseract/wiki) y CONTINUAR igual
          (degradación elegante: PDFs de texto y DOCX siguen funcionando).
        - OPCIONAL (deseable): permitir que, si junto al .exe/al script existe una
          carpeta "tesseract\" embebida, se use esa ruta.
2. La instalación debe mostrarse a la usuaria con una ventana/consola de progreso
   ("Verificando dependencias… Instalando pymupdf…") y NO congelar todo sin
   feedback. Puede ser una ventana previa (splash) con log en vivo.
3. Manejo de errores robusto y en español:
   - Sin internet al instalar → mensaje claro: "No se pudieron instalar las
     dependencias. Verifique su conexión a internet e intente de nuevo."
   - pip falla por permisos → sugerir ejecutar como administrador o usar
     "pip install --user".
   - Registrar todo en el log.
4. IMPORTANTE sobre empaquetado: si la app se distribuye como .exe con PyInstaller,
   las librerías pip ya van EMBEBIDAS (no hace falta pip). En ese caso el bootstrap
   debe: (a) detectar si corre "congelado" (sys.frozen) y saltar la instalación de
   paquetes pip, pero (b) seguir verificando Chromium de Playwright y Tesseract
   (que pueden faltar en la PC destino). Cuando corre desde el .py (no congelado),
   sí instala los paquetes pip faltantes.
5. Reintentar la verificación tras instalar, y solo abrir la app cuando todo lo
   crítico esté disponible (al menos: jinja2 + un motor de PDF).

--------------------------------------------------------------------------------
CAMBIO 2 — SELECTOR DE CARÁTULA (plantillas precargadas en el .exe)
--------------------------------------------------------------------------------
Objetivo: antes de generar, la usuaria debe ELEGIR cuál carátula usar. Todas las
carátulas deben venir PRECARGADAS dentro del propio .exe.

Requisitos:
1. Menú/paso de selección de carátula (puede ser una sección nueva en la GUI o un
   diálogo antes de generar) con las opciones disponibles. De momento hay 2:
      - "Clásica (ES Constructora)"  → template_caratula.html
      - "Ministerio de Salud"        → template_ministerio_salud.html
   Mostrar cada opción con su nombre y, si es posible, una miniatura o descripción.
2. Debe incluir una ADVERTENCIA visible dentro del mismo menú, por ejemplo:
   "⚠ Si la carátula que necesita no está disponible en esta lista, solicite al
    administrador una actualización del software."
3. Las plantillas HTML y sus logos/recursos deben ir EMBEBIDOS en el .exe
   (PyInstaller --add-data). En tiempo de ejecución, resolver la ruta con un
   helper resource_path() que use sys._MEIPASS cuando está congelado y la carpeta
   local cuando corre desde el .py. Copiar/extraer la plantilla y su asset a una
   ubicación temporal accesible por el motor si hace falta (el motor y el
   compilado necesitan rutas file:/// válidas para el logo).
4. La selección debe recordarse en submitals_config.json ("caratula_seleccionada").
5. El motor debe renderizar la plantilla ELEGIDA (no siempre template_caratula.html).
   Parametrizar la selección de plantilla y su logo correspondiente
   (logo_path para la clásica, logo_ministerio para la del Ministerio).

--------------------------------------------------------------------------------
CAMBIO 3 — CONFIGURACIÓN INICIAL DE DATOS DEL PROYECTO (para la carátula Ministerio)
--------------------------------------------------------------------------------
Contexto: la carátula del Ministerio tiene campos que hasta ahora no se llenaban:
fecha, responsable (nombre y cargo), número de licitación/contrato, plazo,
cliente y monto. Estos son datos del PROYECTO (iguales para todos los materiales),
no salen de las fichas.

Requisitos:
1. Cuando la usuaria elija la carátula "Ministerio de Salud" (o siempre, pero
   aplicando solo a esa plantilla), mostrar un MENÚ DE CONFIGURACIÓN INICIAL que
   solicite y guarde estos campos del proyecto:
      - proyecto            (nombre del proyecto)
      - cliente             (cliente / institución)
      - contrato            (número de contrato / licitación)
      - monto
      - plazo
      - nombre_cargo        (responsable: nombre y cargo)
      - fecha               (fecha, formato dd/mm/aaaa)
      - fecha_emision       (opcional)
      - fecha_revision, revisa, observaciones_respuesta → normalmente vacíos
        (se llenan a mano después); dejarlos como campos opcionales o en blanco.
2. Estos valores se guardan en submitals_config.json bajo una clave nueva, p.ej.
   "datos_proyecto": { proyecto, cliente, contrato, monto, plazo, nombre_cargo,
   fecha, fecha_emision } y se REUTILIZAN en todas las carátulas del lote.
3. REGLAS FIJAS al generar la carátula del Ministerio:
      - "version"  = SIEMPRE "v1".
      - "registro" = SIEMPRE el consecutivo del material (ej. ARQ07, MEC03).
   (Estas dos NO se piden a la usuaria; se asignan automáticamente por material.)
4. El resto de campos del material (nombre_comercial, fabricante,
   descripcion_tecnica, normativa, documentacion_tecnica, observaciones_material)
   siguen saliendo de las fichas/ChatGPT como hoy.
5. Para la carátula CLÁSICA no se piden estos datos de proyecto (no los usa).
6. El menú de configuración inicial debe poder reabrirse/editarse (por ejemplo,
   un botón "Datos del proyecto" o dentro de Mantenimiento) y recordar lo último.

--------------------------------------------------------------------------------
CAMBIO 4 — CAMPOS VACÍOS CUANDO NO HAY SUFICIENTE INFORMACIÓN
--------------------------------------------------------------------------------
Requisito: si al leer los PDFs/fichas no hay información suficiente para completar
toda la carátula, dejar EN BLANCO únicamente los campos que falten (NO inventar
datos, NO rellenar con texto de relleno, NO abortar el material).
- Si falta marca → dejar el campo de fabricante vacío (o "POR DEFINIR" solo si así
  se decide, pero preferiblemente vacío para la carátula del Ministerio).
- Si falta normativa → dejar vacío (hoy se usa "SIN ESPECIFICAR"; para la carátula
  se debe mostrar VACÍO, no el literal "SIN ESPECIFICAR").
- Si falta descripción → vacío.
- Los campos del proyecto que la usuaria no llenó → vacíos.
- La carátula debe generarse igual, con los espacios en blanco listos para
  completarse a mano.
Nota: mantener la lógica actual de estados (FICHA_DISPONIBLE / FICHA_INCOMPLETA /
CARPETA_VACÍA), pero al RENDERIZAR, convertir los valores tipo "SIN ESPECIFICAR"
o "POR DEFINIR" en cadena vacía en la carátula.

--------------------------------------------------------------------------------
CAMBIO 5 — "FORZAR GENERADO" DEBE SOBREESCRIBIR LA CARÁTULA EXISTENTE
--------------------------------------------------------------------------------
Requisito: cuando la usuaria marca la casilla "Forzar regeneración", la app debe
SOBREESCRIBIR la carátula (y el compilado) existentes con la nueva versión.
- Comportamiento esperado: si ya existe "CARATULA <...>.pdf" (y/o "<...>-CMP.pdf"),
  se reemplazan por los nuevos (borrar/regenerar o escribir encima).
- Debe funcionar aunque el archivo exista; manejar el caso de archivo bloqueado
  (abierto en un visor) con mensaje claro: "Cierre el PDF <nombre> y reintente."
- Con "Solo faltantes" (opción opuesta) se mantiene el comportamiento incremental
  actual (saltar los que ya existen).
- Verificar que "forzar" tenga prioridad y realmente reemplace el contenido.

================================================================================
PARTE 3 — PERSISTENCIA (submitals_config.json v2.3)
================================================================================
Agregar/mantener:
{
  "version": "2.3",
  "caratula_seleccionada": "clasica" | "ministerio_salud",
  "datos_proyecto": {
    "proyecto": "", "cliente": "", "contrato": "", "monto": "",
    "plazo": "", "nombre_cargo": "", "fecha": "", "fecha_emision": ""
  },
  "opciones": { solo_faltantes, forzar_regeneracion, mostrar_log,
                generar_json_automatico, usar_json_existente },
  "api": { openai_key_encrypted, ultima_validacion },
  "mantenimiento": { ultima_limpieza_cache, veces_reseted },
  "carpetas_recientes": [...], "ultimo_json": ""
}
- Migración automática desde v2.1/v2.2 (no borrar la API key ni las carpetas).

================================================================================
PARTE 4 — EMPAQUETADO (.exe) Y RECURSOS
================================================================================
- El .exe debe incluir EMBEBIDOS: las plantillas HTML (clásica y ministerio) y
  sus logos (logo_es_crop.png, ministerio_salud_banner.png). Documentar el
  comando PyInstaller con --add-data para cada recurso y --collect-all para
  playwright/jinja2/pypdf/pymupdf.
- Helper resource_path(rel) que devuelva la ruta correcta en modo congelado
  (sys._MEIPASS) y en modo desarrollo (carpeta del script).
- El motor y el compilado necesitan que el logo se pase como file:/// válido;
  si la plantilla está embebida, extraer plantilla+logo a una carpeta temporal
  o a la carpeta base para que las rutas file:/// funcionen en el render.

================================================================================
PARTE 5 — ENTREGABLES v2.3
================================================================================
1. submitals_gui.py (v2.3) — con bootstrap de dependencias, selector de carátula,
   menú de datos de proyecto, campos vacíos y forzar-sobreescritura. Debe COMPILAR.
2. Ajustes mínimos y justificados en generate_caratulas.py SOLO si son necesarios
   para (a) elegir plantilla y (b) inyectar los campos de proyecto + version="v1"
   + registro=consecutivo + vaciar "SIN ESPECIFICAR"/"POR DEFINIR" al renderizar.
   Si es posible, hacerlo SIN romper el uso actual del motor.
3. submitals_config.json (v2.3) actualizado (preservando datos existentes).
4. INSTRUCCIONES_v2.3.txt — instalación en PC nueva (solo Python), cómo funciona
   el auto-instalador, cómo elegir carátula, cómo llenar los datos del proyecto,
   qué pasa con Tesseract si no está, troubleshooting.
5. CHANGELOG_v2.3.md — resumen de los 5 cambios.
6. (Opcional) INSTRUCCIONES de empaquetado con PyInstaller y --add-data.

================================================================================
PARTE 6 — CHECKLIST DE VALIDACIÓN v2.3
================================================================================
□ Al arrancar, detecta dependencias faltantes y las instala (modo .py).
□ En modo .exe (congelado) salta pip, pero verifica Chromium y Tesseract.
□ Verifica Python >= 3.9; mensajes claros si algo falla o no hay internet.
□ Muestra progreso de la verificación/instalación (no se congela sin feedback).
□ Selector de carátula con las 2 opciones (Clásica / Ministerio de Salud).
□ Advertencia visible: "si no está la que necesita, pida al administrador…".
□ Plantillas + logos EMBEBIDOS en el .exe (resource_path funciona congelado y no).
□ El motor renderiza la plantilla ELEGIDA con su logo correcto.
□ Menú de datos del proyecto (Ministerio): proyecto, cliente, contrato, monto,
  plazo, responsable, fecha… se piden, se guardan y se reutilizan.
□ version = "v1" SIEMPRE; registro = consecutivo del material, automáticos.
□ Campos sin información → quedan EN BLANCO (no se inventa; "SIN ESPECIFICAR"/
  "POR DEFINIR" se muestran vacíos en la carátula).
□ "Forzar regeneración" SOBREESCRIBE carátula y compilado existentes.
□ "Solo faltantes" mantiene el comportamiento incremental.
□ Manejo de archivo bloqueado (PDF abierto) con mensaje claro.
□ submitals_config.json v2.3 con caratula_seleccionada y datos_proyecto;
  migración sin perder API key ni carpetas.
□ Compatibilidad con datos_materiales.json de versiones previas.
□ El código COMPILA y las funciones no-GUI pasan pruebas headless.
□ Documentos INSTRUCCIONES_v2.3.txt y CHANGELOG_v2.3.md entregados.

================================================================================
PARTE 7 — CUIDADOS / PRIORIDADES
================================================================================
PRIORIDADES:
1. Que funcione en una PC nueva con solo Python (bootstrap sólido).
2. Selector de carátula + plantillas embebidas.
3. Datos de proyecto para la carátula del Ministerio (con version=v1 y
   registro=consecutivo automáticos).
CUIDADOS:
- No romper la generación actual (carátula + compilado + multi-documento + OCR).
- No borrar la API key ni las carpetas recientes al migrar la config.
- Tesseract no se puede instalar en silencio de forma universal: degradar con
  aviso, nunca romper el flujo.
- En .exe congelado NO intentar pip install de lo ya embebido.
- Rutas con espacios/acentos y file:/// deben seguir funcionando (Windows).
- No agregar elementos a las carátulas que no existan en sus PDFs originales.
================================================================================
