# Instrucciones de publicación (deployment) — Generador de Submittals

Repo: **https://github.com/adrianix360/generador-submittals**

## Cómo publicar una versión nueva (para el desarrollador)
1. Editar el código localmente (`submitals_gui.py`, etc.).
2. Ejecutar:
   ```
   python deployment.py 2.6.8 "Descripción de los cambios"
   ```
   Esto: sube el número de versión, calcula hashes SHA-256, genera `VERSION.json`,
   hace `git add/commit/push`.
3. Solo si hubo cambios grandes que requieren recompilar el `.exe`:
   ```
   python deployment.py 2.6.8 "cambios" --build --release
   ```
   (`--build` compila con PyInstaller; `--release` crea el Release con `gh`.)

Flags útiles: `--no-tests`, `--no-git`, `--build`, `--release`.

## Qué recibe el usuario (sin hacer nada técnico)
Al abrir la app, esta consulta `VERSION.json` en GitHub. Si hay versión nueva:
- Cambios solo de código (`.py`/`.html`) → descarga los archivos que cambiaron
  (segundos), y reinicia sola.
- Si cambió `requirements.txt` → además hace `pip install -r requirements.txt`.
- Si cambió el `.exe` (modo empaquetado) → descarga el nuevo y lo instala al cerrar.

## Primer setup del repositorio (una vez)
```
cd "C:\Users\castr\Downloads\Submitals_ES"
git init
git remote add origin https://github.com/adrianix360/generador-submittals.git
git add -A
git commit -m "v2.6.7: base + auto-updater"
git branch -M main
git push -u origin main
```
Requisitos para `--release`: instalar **GitHub CLI** (`gh`) y `gh auth login`.
Para compilar: `pip install pyinstaller`.

## Seguridad
`submitals_config.json` (con la API key) y `datos_materiales.json` están en
`.gitignore`: NO se suben a GitHub. No los quites del `.gitignore`.

## Requisitos del entorno de la app
`pip install -r requirements.txt` + `python -m playwright install chromium`.
Nuevas dependencias de esta versión: `requests` (ya estaba) y `packaging`.
`PyGithub` solo se usaría desde `deployment.py` si prefieres crear releases por
API en vez de `gh` (opcional).
