# CHANGELOG v3.1.0 — La BD pasa de OneDrive a GitHub

**Fecha:** 2026-07-25
**Alcance:** solo el *backend* de la Base de Datos. La funcionalidad de v3.0.0 es
la misma; v2.6 no se tocó.

---

## Resumen

| | v3.0.0 | v3.1.0 |
|---|---|---|
| Medio | Carpeta de OneDrive sincronizada | Repositorio de GitHub |
| Concurrencia | Archivo `.lock`, máx. 1 PC a la vez, timeout 2 h | Sin lock: git fusiona y reintenta |
| Conflictos | No aplicaba (turnos) | Fusión automática a nivel de registro |
| Sin conexión | Caché de solo lectura | Se trabaja normal y se sube al reconectar |
| Credenciales | API key de OpenAI | + Personal Access Token por usuario |
| Dependencias pip | — | Ninguna nueva |

---

## Módulo nuevo: `git_bd.py`

Capa de transporte con **dos backends** y la misma interfaz
(`inicializar / pull / push / estado`):

- **`GitTransporte`** — ejecutable `git` por `subprocess`. Clona el repositorio en
  `%LOCALAPPDATA%/GeneradorSubmittals/bd_repo` con `--sparse` limitado a
  `BD_Submittals/`.
- **`RestTransporte`** — API REST de GitHub con `urllib` (biblioteca estándar),
  para PCs sin git. Commits por la Data API (blobs → tree → commit → ref) con
  control optimista: si el `ref` se movió, refusiona y reintenta.
- **`GitSync`** — fachada que elige el backend (`auto` → git si está instalado),
  absorbe los errores de red para permitir el modo sin conexión y arma el texto
  de la barra de estado.

### Decisiones que se apartan del plan original

1. **No se usa GitPython ni paramiko.** GitPython invoca el mismo binario de git
   y complica el empaquetado con PyInstaller; paramiko sobra porque la
   autenticación es HTTPS + token, no SSH. Cero dependencias nuevas.
2. **El clon vive en `%LOCALAPPDATA%`, no en la carpeta del proyecto.** Un `git
   pull` automático al abrir el programa habría chocado con los cambios de
   código sin confirmar de la carpeta de trabajo.
3. **Los conflictos NO se resuelven con `-X ours`.** Esa estrategia opera a nivel
   de archivo: habría borrado las fichas cargadas por la otra PC, justo lo
   contrario de "nunca pierde datos". Ver la sección siguiente.
4. **De los proyectos solo se versionan los metadatos.** Subir carátulas, CMP y
   Excel haría crecer el repositorio cientos de MB por proyecto (y GitHub
   rechaza archivos de más de 100 MB). Los entregables se regeneran.
5. **El token nunca se escribe en `.git/config`.** Se inyecta solo en la línea de
   comandos de `fetch`/`push`, y se oculta (`***`) de todo log o mensaje de error.

---

## Resolución de conflictos sin pérdida de datos

`indice.json` se fusiona **por registro**, no por archivo:

| Situación | Resolución |
|---|---|
| Ficha nueva en un solo lado | Se conserva (unión por `id`) |
| Mismo `id` editado en ambos lados | Gana `fecha_modificacion` más reciente |
| Ficha ausente en el remoto | Se conserva: el borrado es lógico, nunca físico |
| Dos PDFs distintos con el mismo nombre | Se conservan los dos: el remoto mantiene el nombre, el local pasa a `<nombre>-2.pdf` y su ficha se reapunta por `hash_archivo` |
| `submittal_proyecto.json` en ambos | Gana `ultima_actualizacion` más reciente |

---

## `bd_manager.py`

**Eliminado:** `detectar_onedrive()`, `detectar_bd_root()`, `LockOcupadoError`,
`adquirir_lock()`, `liberar_lock()`, `lock_vigente()`, `lock_path`,
`NOMBRE_LOCK`, `LOCK_TIMEOUT_SEG`.

**Nuevo:**

- `sincronizar()` / `git_pull()` / `git_push()` / `git_status()` /
  `git_merge_conflict_handler()`.
- `sync_indice()` — pull + validación de integridad + respaldo en caché. Si el
  índice descargado no valida, se usa la copia local y se avisa.
- `validar_indice()` — versión, `id` duplicados, campos obligatorios, `ruta_pdf`.
- `obtener_token_github()` / `guardar_token_github()` / `crear_sync()`.
- Seguimiento de cambios pendientes (`marcar_pendiente`,
  `hay_cambios_sin_subir`), persistido en la caché para sobrevivir un reinicio
  trabajando sin conexión.
- `listar_proyectos()` — proyectos guardados en la BD.
- Campos nuevos en cada ficha: `fecha_modificacion` (decide los conflictos) y
  `cargada_por`.
- `ruta_local_ficha()` descarga el PDF bajo demanda con el backend REST.

**Compatibilidad:** `BDManager(bd_root=carpeta)` sigue funcionando como gestor de
una carpeta local sin red — los métodos de git responden `{"desactivado": True}`.
Eso mantiene las pruebas simples y permite usar el módulo aislado.

---

## `submitals_gui_v3.py`

**Eliminado:** el diálogo *"BD en uso — ¿forzar acceso?"* y todo el manejo del
lock (`_lock_ok`, `_dialogo_lock`).

**Nuevo:**

- Sincronización al abrir, en un hilo aparte con barra indeterminada, para no
  congelar la ventana.
- Barra de estado con: *"🔄 Sincronizando con GitHub…"*, *"☁️ Última subida: hace
  5 min"*, *"📡 Sin conexión — trabajando con la copia local"*, *"✅ Conflicto
  resuelto y sincronizado"*, *"🔑 Sin token de GitHub"* y el contador de cambios
  sin subir.
- Botones **Sincronizar ahora**, **Subir cambios pendientes** y **Configurar
  GitHub** (diálogo de repositorio, rama y token, con el token enmascarado).
- Push automático al cargar fichas, al generar un submittal y al desactivar una
  ficha.
- Cierre seguro: si quedan cambios sin subir, ofrece subirlos antes de cerrar.

---

## `updater_gh.py`

`aplicar_y_sincronizar()` — actualiza el programa y la BD en una sola operación,
validando la integridad del índice después del pull. El botón *Buscar
actualización* ya lo usa.

---

## `.gitignore`

Las reglas de v2.6 ignoran `*.pdf` y `*.xlsx` para no subir documentos de obra.
Se re-incluyen **solo** los PDFs de las cuatro carpetas de categoría de la BD:

```gitignore
!BD_Submittals/ARQ/**/*.pdf
!BD_Submittals/ESTR/**/*.pdf
!BD_Submittals/MEC/**/*.pdf
!BD_Submittals/ELEC/**/*.pdf
BD_Submittals/Proyectos/**/CARATULA*.pdf
BD_Submittals/Proyectos/**/*-CMP.pdf
BD_Submittals/Proyectos/**/CMP SUBMITTAL *.pdf
```

Las entradas del plan original con variables de entorno
(`%LOCALAPPDATA%/...`) no se incluyeron: `.gitignore` no expande variables, y esas
rutas están fuera del repositorio.

---

## Pruebas: 54 en total, sin internet

`test_git_bd.py` (28, nuevo) monta un repositorio *bare* local que hace de GitHub
y dos clones que hacen de PC1 y PC2 — git de verdad, sin red — más un GitHub en
memoria para el backend REST:

- Sincronización normal: PC1 carga una ficha → PC2 la ve (índice + PDF).
- **Conflicto de índice:** las dos PCs cargan a la vez → se resuelve solo y las
  dos fichas sobreviven en ambas PCs, con el índice válido.
- **Colisión de nombre de PDF:** los dos archivos se conservan y cada `hash` sigue
  correspondiendo a su archivo.
- Edición simultánea de la misma ficha → gana la más reciente, sin duplicar.
- Metadatos de proyecto viajando entre PCs.
- Sin conexión: el trabajo no se pierde, queda pendiente y se sube al reconectar.
- Push rechazado (otra PC se adelanta entre el commit y el `ref`) → reintenta y
  fusiona.
- Repositorio inaccesible → se avisa sin corromper nada.
- El token nunca aparece en los mensajes de error.

`test_v3.py` (26) mantiene toda la cobertura de v3.0.0; se reemplazaron las
pruebas del lock por: que no quede ningún resto de la implementación anterior,
modo local sin red, cambios pendientes, `fecha_modificacion` y token de GitHub.
El caso real de submittal completo (materialización + CMP + Excel con fichas
reales del proyecto) sigue pasando: **sin regresión**.

---

## Migración

La BD estaba vacía, así que no hay datos que migrar. En cada PC:

1. Instalar Git for Windows (opcional pero recomendado).
2. Abrir el programa → **⚙️ Configurar GitHub** → pegar el token.
3. **🔄 Sincronizar ahora**.

El `bd_root` de OneDrive que hubiera en un `config.json` de v3.0.0 se descarta
solo al cargar la configuración.
