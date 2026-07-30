# 🚀 INSTRUCCIONES PARA LANZAR v3.0.0

## ✅ ESTADO ACTUAL

- ✓ VERSION.json actualizado a v3.0.0
- ✓ Todos los archivos v3 listos
- ✓ Hashes SHA-256 recalculados
- ✓ Auto-updater configurado
- ✓ Sistema GitHub funcional

---

## 📋 PASOS PARA LANZAR

### 1. Verificar que todo esté listo

```bash
cd /ruta/al/repo/generador-submittals
git status
```

Deberías ver como archivos modificados:
- `VERSION.json`
- Posiblemente: `submitals_gui_v3.py`, `bd_manager.py`, etc.

### 2. Agregar todos los archivos a git

```bash
git add VERSION.json
git add submitals_gui_v3.py
git add bd_manager.py
git add fuzzy_search.py
git add nomenclatura.py
git add ocr_extractor.py
git add updater_gh.py
git add auto_updater.py
git add requirements.txt
```

O simplemente:
```bash
git add -A
```

### 3. Hacer commit

```bash
git commit -m "Release v3.0.0: BD centralizada en GitHub + nomenclatura + hard delete"
```

### 4. Push a GitHub

```bash
git push origin main
```

---

## 🎯 RESULTADOS ESPERADOS

### Después del push:

1. **VERSION.json estará en GitHub** → auto-updater lo descargará
2. **Usuarios con v2.6.x verán notificación** de actualización disponible
3. **Descargará automáticamente:**
   - submitals_gui_v3.py
   - bd_manager.py
   - fuzzy_search.py
   - nomenclatura.py
   - ocr_extractor.py
   - updater_gh.py
   - requirements.txt + nuevas dependencias

---

## 👥 CÓMO USAN LOS USUARIOS LA v3.0.0

### Para usuarios nuevos:

```bash
# 1. Clonar repo
git clone https://github.com/adrianix360/generador-submittals.git
cd generador-submittals

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar (NUEVO EN v3)
python submitals_gui_v3.py
```

### Para usuarios con v2.6.x:

```bash
# Auto-updater detectará actualización disponible
# Opción 1: Descarga automática (recomendado)
# Opción 2: Manual
python submitals_gui.py  # O submitals_gui_v3.py si ya actualizado
```

---

## 📝 NOTAS IMPORTANTES

- **No es necesario .exe** → Solo Python, funciona en cualquier PC
- **BD sincronizada automáticamente** → Git pull/push funciona transparente
- **Actualizaciones futuras serán rápidas** → Solo descarga archivos que cambiaron
- **Coexiste con v2.6** → Usuarios pueden elegir qué versión usar

---

## ✅ CHECKLIST FINAL

Antes de hacer push:

- [ ] VERSION.json está en v3.0.0
- [ ] Todos los archivos v3 existen y tienen permisos
- [ ] requirements.txt está actualizado (GitPython, etc.)
- [ ] REPO_SLUG en auto_updater.py es correcto: `adrianix360/generador-submittals`
- [ ] BRANCH es `main`
- [ ] No hay archivos sensibles (_duplicados, logs, etc.)

---

## 🎉 ¡LISTO!

Después del push, v3.0.0 estará disponible para todos los usuarios.

**Comparte el README y este será el lanzamiento oficial.**
