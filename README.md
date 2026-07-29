<div align="center">

# 🏗️ Generador de Submittals ES

[![Version](https://img.shields.io/badge/version-3.1.0-blue?style=for-the-badge&logo=github)](https://github.com/adrianix360/generador-submittals/releases)
[![Python](https://img.shields.io/badge/Python-3.8+-green?style=for-the-badge&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen?style=for-the-badge)]()

**Generador automático de submittales para proyectos de construcción**  


[Características](#-características) • [Instalación](#-instalación) • [Uso](#-uso) • [Versiones](#-versiones)

</div>

---

## 📋 Descripción

**Generador de Submittals ES** es una aplicación desktop que automatiza la creación de documentos de aprobación de materiales (submittales) para proyectos constructivos. 

Con v3.3.5, implementamos una **base de datos centralizada en GitHub** que permite:
- ✅ Reutilizar fichas técnicas sin regenerarlas
- ✅ Crear submittales desde una biblioteca compartida
- ✅ Editar proyectos y regenerar entregables dinámicamente
- ✅ Sincronización automática entre múltiples computadoras
- ✅ Control de versiones integrado

---

## 🎯 Características Principales

### 📊 Base de Datos Centralizada
- **GitHub** como fuente única de verdad
- 800+ fichas técnicas (ARQ, ESTR, MEC, ELEC)
- Fichas de hasta 15MB cada una
- Sincronización automática `git pull/push`

### 🔍 Búsqueda Inteligente
- Búsqueda fuzzy con tolerancia del 50%
- Autocompletado en tiempo real
- Filtros por categoría y marca
- Sugerencias dinámicas

### 📄 Generación de Entregables
- **Carátulas**: Clásica + Ministerio de Salud
- **Compilados**: PDF por material + por disciplina
- **Excel**: Guía Submittal + Guía interna
- Renumeración automática de consecutivos

### 🔄 Edición de Proyectos
- Abrir proyectos existentes
- Modificar materiales (agregar, eliminar, cambiar marca)
- Regenerar entregables con un clic
- Historial de cambios automático (Git)

### 🛡️ Multi-PC
- Máx 4 usuarios (acceso secuencial)
- Sincronización automática
- Resolución de conflictos inteligente
- Caché local (máx 2GB)

### 🤖 Extracción Automática
- **OpenAI Vision** para leer fichas digitales
- **OCR avanzado** para escaneos
- Formulario manual como fallback
- Detección automática de categoría

---

## 🚀 Inicio Rápido

### Requisitos
- **Python** 3.8+
- **Git** instalado
- **Windows** (versión de escritorio)
- Cuenta GitHub con acceso al repo privado
- Conexión a internet (para sincronización)

### Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/adrianix360/generador-submittals.git
cd generador-submittals

# 2. Crear entorno virtual (opcional pero recomendado)
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar token GitHub
# Generar en: https://github.com/settings/tokens
# Guardar en: %APPDATA%/GeneradorSubmittals/config.json
```

### Configuración (config.json)
```json
{
  "github_token": "ghp_xxxxxxxxxxxxx",
  "github_repo": "adrianix360/generador-submittals",
  "github_branch": "main",
  "openai_api_key": "sk-xxxxxxxxxxxxxxxx"
}
```

### Ejecutar
```bash
python submitals_gui_v3.py
```

---

## 📖 Guía de Uso

### 1️⃣ Generar nuevo submittal desde BD

```
Menú Principal
    ↓
[📊 Generar desde BD]
    ↓
Llenar "Datos del Proyecto" (obligatorio)
    ↓
Seleccionar carpeta destino
    ↓
Buscar materiales (ej: "tubo 150")
    ↓
Agregar a lista + seleccionar marca(s)
    ↓
[Generar entregables]
    ↓
✅ Carpeta con CMPs + Excel generada
```

### 2️⃣ Editar submittal existente

```
[📂 Abrir submittal existente]
    ↓
Seleccionar carpeta proyecto
    ↓
Ver lista de materiales
    ↓
Editar / Eliminar / Agregar
    ↓
[Confirmar cambios]
    ↓
✅ Regenera automáticamente
```

### 3️⃣ Cargar fichas nuevas a BD

```
[⚙️ Gestionar BD] → [Cargar ficha(s)]
    ↓
Seleccionar archivo(s) PDF
    ↓
App extrae con OpenAI/OCR
    ↓
Preview (editable)
    ↓
[Guardar a BD]
    ↓
✅ Sube a GitHub automáticamente
```

---

## 📁 Estructura de Carpetas

```
generador-submittals/
├── 📄 submitals_gui_v3.py          # Interfaz principal v3.0.0
├── 📄 bd_manager.py                # Gestión GitHub
├── 📄 fuzzy_search.py              # Búsqueda inteligente
├── 📄 ocr_extractor.py             # OCR + OpenAI
├── 📄 updater_gh.py                # Actualización remota
├── 📄 generate_caratulas.py        # Motor v2.6
├── 📄 submitals_gui.py             # GUI v2.6
│
├── 📁 BD_Submittals/               # Base de datos
│   ├── indice.json                 # Índice de fichas
│   ├── 📁 ARQ/                     # Fichas Arquitectónicas
│   ├── 📁 ESTR/                    # Fichas Estructurales
│   ├── 📁 MEC/                     # Fichas Mecánicas
│   ├── 📁 ELEC/                    # Fichas Eléctricas
│   └── 📁 Proyectos/               # Proyectos guardados
│
├── 📋 requirements.txt
├── 🔐 .gitignore
└── 📖 README.md
```

---

## 🔄 Sincronización Git

### Flujo automático

```
App abre
    ↓
git pull() ← Descarga cambios recientes
    ↓
Carga índice en memoria
    ↓
Usuario trabaja
    ↓
Usuario cierra/guarda
    ↓
git push() → Sube cambios a GitHub
    ↓
✅ Sincronizado
```

### Si hay conflicto

```
git push() falla (otro usuario subió cambios)
    ↓
git_merge_conflict_handler() automático
    ↓
Resuelve inteligentemente (más reciente gana)
    ↓
git push() reintenta
    ↓
✅ Sincronizado
```

---

## 📊 Versiones

| Versión | Fecha | Cambio Principal |
|---------|-------|-----------------|
| **3.0.0** | Jul 2026 | BD centralizada en GitHub + sincronización automática |
| 2.6.16 | Jul 2026 | Columna "Proveedor" en Excel |
| 2.6.15 | Jul 2026 | Fix tamaño carátula definitivo |
| 2.6 | Jul 2026 | Duplicados + Excel + OCR robusto |
| 2.0 | Jul 2026 | Auto-generación JSON con ChatGPT |
| 1.0 | Jul 2026 | Interfaz base Tkinter |

[Ver CHANGELOG completo](CHANGELOG-COMPLETO.md)

---

## 🧪 Testing

### Unit Tests
```bash
pytest tests/ -v
```

### Testing manual
```bash
# 1. Sincronización normal
# PC1 carga ficha → PC2 la ve

# 2. Conflictos
# Dos PCs modifican índice → resuelve automático

# 3. Sin conexión
# App funciona con caché local

# 4. Generación entregables
# Crear submittal → validar PDF + Excel
```

---

## 🛠️ Dependencias Principales

```python
# requirements.txt
GitPython==3.1.40          # Operaciones Git
openpyxl==3.11.0          # Excel
PyMuPDF==1.23.0           # PDF lectura
pytesseract==0.3.10       # OCR
Pillow==10.0.0            # Imágenes
requests==2.31.0          # HTTP
openai==1.3.0             # OpenAI API
python-dotenv==1.0.0      # Variables entorno
```

---

## ⚙️ Configuración Avanzada

### Variables de entorno (.env)
```bash
OPENAI_API_KEY=sk-xxxxx
GITHUB_TOKEN=ghp_xxxxx
DEBUG_MODE=False
CACHE_MAX_GB=2
```

### Logging
- **Archivo**: `%APPDATA%/GeneradorSubmittals/app.log`
- **Nivel**: INFO (operaciones) + ERROR (excepciones)
- **Rotación**: máx 10MB

---

## 📞 Soporte

### Errores comunes

**"BD en uso"**
→ Otra PC está sincronizando. Espera 30s e intenta de nuevo.

**"Sin conexión a GitHub"**
→ Verifica internet. App funciona con caché local.

**"Ficha corrupta"**
→ Carga nuevamente. Sistema detecta y reemplaza automáticamente.

**"OCR/OpenAI falla"**
→ Llena datos manualmente en el formulario que aparece.

### Reportar bugs
```
GitHub Issues: https://github.com/adrianix360/generador-submittals/issues
```

---

## 👨‍💻 Desarrollado por

**Adrián Castro**  

---

## 📜 Licencia

Este proyecto está bajo licencia **MIT**. Ver [LICENSE](LICENSE) para más detalles.

---

## 🎯 Roadmap Futuro

- [ ] Dashboard de estadísticas
- [ ] Exportación a otros formatos
- [ ] Búsqueda avanzada + filtros
- [ ] Historial de versiones por ficha
- [ ] Integración con sistemas externos
- [ ] App móvil (consultadoras)

---

<div align="center">

### ⭐ Si te fue útil, ¡dame una estrella!

[⬆ Subir](#-generador-de-submittals-es)

</div>

