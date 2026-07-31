; ==================================================================================
; Generador de Submittals ES - Script de instalacion Inno Setup 6
; ==================================================================================
; Este script genera un instalador por-usuario (sin UAC / sin permisos de
; administrador) para la aplicacion "Generador de Submittals ES" v3.2.0.
;
; Rutas relativas: este .iss vive en la RAIZ DEL PROYECTO
; (C:\Users\castr\Downloads\Submitals_ES), por lo que las rutas Source
; se escriben como "dist\...", "assets\...", etc.
;
; Compilar con:  ISCC.exe "GeneradorSubmittalsES.iss"
; ==================================================================================

; ----------------------------------------------------------------------------------
; [Setup] - Configuracion general del instalador
; ----------------------------------------------------------------------------------
[Setup]
; AppId: GUID estable que identifica la app entre versiones. Generar UNA sola vez
; y no cambiarlo nunca, para que las actualizaciones y el desinstalador apunten
; siempre a la misma instalacion. Las llaves dobles {{ }} escapan la llave literal.
AppId={{B4A1C2D3-9E7F-4A2B-8C5D-3F6E1A9D0B72}}

; Nombre visible de la app (sin numero de version) en el asistente y en
; "Agregar o quitar programas".
AppName=Generador de Submittals ES

; Version mostrada en "Agregar o quitar programas". Mantener sincronizada con
; VERSION_v3.json.
AppVersion=3.3.8

; Editor / fabricante. Solo cosmetico: aparece en el asistente y en la lista de
; programas como senal de confianza.
AppPublisher=E.S. Consultoria y Construccion S.A.

; --- CLAVE: instalacion por-usuario SIN UAC ---
; PrivilegesRequired=lowest ejecuta el instalador en modo NO administrativo:
; nunca aparece el cuadro de elevacion de Windows (UAC). Es lo mas simple para
; usuarios no tecnicos. La app NO necesita escribir en su carpeta de instalacion
; (config/cache/logs/BD van a %APPDATA% / %LOCALAPPDATA%), asi que por-usuario basta.
PrivilegesRequired=lowest

; Carpeta de instalacion. Bajo "lowest", {autopf} resuelve a %LOCALAPPDATA%\Programs,
; escribible sin permisos de administrador.
DefaultDirName={autopf}\Generador de Submittals ES

; Nombre de la carpeta del menu Inicio. Como se desactiva la pagina de seleccion
; de grupo (abajo), este nombre se usa automaticamente.
DefaultGroupName=Generador de Submittals ES

; Menos pantallas para el usuario: se ocultan las paginas de "carpeta del menu
; Inicio" y de "carpeta de destino". El instalador usa los valores por defecto.
DisableProgramGroupPage=yes
DisableDirPage=yes

; Nombre del instalador .exe generado (sin extension).
OutputBaseFilename=GeneradorSubmittalsES_Setup_v3.3.8

; Carpeta donde se escribe el instalador compilado, relativa a este .iss.
OutputDir=Instalador

; Icono del ejecutable del instalador y del asistente. Debe ser un .ico real
; multi-resolucion (no un .png renombrado).
SetupIconFile=assets\icono_app.ico

; Icono mostrado para la entrada en "Agregar o quitar programas". Apunta al exe
; instalado (que ya incrusta el icono de la app).
UninstallDisplayIcon={app}\GeneradorSubmittalsES_v3.exe

; --- Compresion ---
; El payload es un exe one-file de PyInstaller YA comprimido, por lo que
; recomprimir al maximo (lzma2/max, el default de Inno) tarda minutos sin ganar
; tamano. lzma2/fast mantiene la compilacion rapida. SolidCompression=no porque
; con un unico exe grande no hay diccionario que compartir.
Compression=lzma2/fast
SolidCompression=no

; Estilo visual moderno (blanco, contemporaneo).
WizardStyle=modern

; Build de 64 bits: rechaza instalar en arquitecturas incompatibles con un mensaje
; claro en vez de dejar una app rota.
ArchitecturesAllowed=x64compatible

; ----------------------------------------------------------------------------------
; [Languages] - Idioma del asistente (Espanol)
; ----------------------------------------------------------------------------------
[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

; ----------------------------------------------------------------------------------
; [Tasks] - Tareas opcionales elegibles por el usuario
; ----------------------------------------------------------------------------------
; Casilla para crear el acceso directo en el Escritorio. Con "checkedonce" la
; casilla aparece MARCADA por defecto en una instalacion nueva (el usuario obtiene
; el icono sin hacer nada) y solo se desmarca en actualizaciones posteriores, para
; no recrear un icono que el usuario pudo haber borrado.
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

; ----------------------------------------------------------------------------------
; [Files] - Archivos a instalar
; ----------------------------------------------------------------------------------
; NOTA sobre flags:
;  - ignoreversion: sobrescribe siempre el archivo en reinstalaciones/actualizaciones
;    (los exe one-file de PyInstaller no suelen traer version util para comparar).
;  - NO se usa el flag "readonly" en ningun archivo (no aporta proteccion a un
;    one-file exe y rompe actualizaciones/desinstalaciones limpias).
;  - nocompression en los exe: ya vienen comprimidos; se evita recomprimir.
[Files]
; --- Ejecutable principal v3 (payload, ~144 MB) ---
Source: "dist\GeneradorSubmittalsES_v3.exe"; DestDir: "{app}"; Flags: ignoreversion nocompression

; --- Ejecutable hermano v2.6 (NO requerido pero solicitado) ---
; La auditoria indica needs_v26_exe = true. v3 lanza el build heredado v2.6 como
; ARCHIVO HERMANO en la misma carpeta (submitals_gui_v3.py:1506-1508) para el boton
; "Generar desde carpetas (v2.6)". Como la instalacion es por-usuario en
; %LOCALAPPDATA%\Programs (carpeta ESCRIBIBLE), las escrituras propias de v2.6
; (submitals_config.json, tessdata_es\, ms-playwright\) funcionan sin admin.
; skipifsourcedoesntexist permite compilar aunque este exe no este en dist\ al construir.
Source: "dist\GeneradorSubmittalsES.exe"; DestDir: "{app}"; Flags: ignoreversion nocompression skipifsourcedoesntexist

; --- OPCIONAL, NO incluido ---
; tessdata_es\  (eng/osd/spa .traineddata, ~32MB): la auditoria lo marca como
; OPCIONAL. Solo pre-siembra los datos OCR del hermano v2.6 (que se auto-puebla en
; tiempo de ejecucion). El nucleo v3 no lo usa. Se omite a proposito para no inflar
; el instalador; si se quisiera pre-sembrar, se agregaria una linea:
;   Source: "tessdata_es\*"; DestDir: "{app}\tessdata_es"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
;
; Todo lo demas (generate_caratulas.py, plantillas HTML, assets, paquetes
; playwright/jinja2/pypdf/etc.) ya va EMBEBIDO dentro del exe one-file por PyInstaller,
; por lo que no se copia por separado.

; ----------------------------------------------------------------------------------
; [Icons] - Accesos directos
; ----------------------------------------------------------------------------------
; Menu Inicio: se crea SIEMPRE (sin parametro Tasks).
; Escritorio: se crea solo si la casilla "desktopicon" quedo marcada.
; Se usan constantes {auto*} para que todo quede en el perfil del usuario actual
; (coherente con PrivilegesRequired=lowest, sin necesidad de administrador).
[Icons]
Name: "{autoprograms}\Generador de Submittals ES"; Filename: "{app}\GeneradorSubmittalsES_v3.exe"; WorkingDir: "{app}"; IconFilename: "{app}\GeneradorSubmittalsES_v3.exe"
Name: "{autodesktop}\Generador de Submittals ES"; Filename: "{app}\GeneradorSubmittalsES_v3.exe"; WorkingDir: "{app}"; IconFilename: "{app}\GeneradorSubmittalsES_v3.exe"; Tasks: desktopicon

; ----------------------------------------------------------------------------------
; [Run] - Accion posterior a la instalacion
; ----------------------------------------------------------------------------------
; Casilla en la pagina final "Instalacion completada" para iniciar la app.
;  - postinstall: muestra la casilla al final.
;  - nowait: cierra el asistente sin bloquear (el one-file tarda unos segundos en
;    auto-extraerse en el primer arranque).
;  - skipifsilent: no lanza la app en instalaciones silenciosas (/SILENT).
[Run]
Filename: "{app}\GeneradorSubmittalsES_v3.exe"; Description: "Iniciar Generador de Submittals ES ahora"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent
