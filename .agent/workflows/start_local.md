---
description: Cómo iniciar el proyecto Slingshot v42.2 Apex Titan en local (backend + frontend)
---

# Iniciar Slingshot v42.2 Apex Titan en Local

## ⚡ Forma rápida (recomendada): Un solo comando

// turbo
1. Ejecutar el launcher unificado desde la raíz del proyecto:
```powershell
./start.ps1
```
Esto abre automáticamente dos ventanas de PowerShell separadas:
- Una con el **Backend** (FastAPI) en http://localhost:8000
- Una con el **Frontend** (Next.js) en http://localhost:3000

---

## 🔧 Forma manual (si necesitas control granular)

### Paso 1: Backend (FastAPI)
// turbo
1. Activar el entorno virtual e iniciar el motor Python con Uvicorn:
```powershell
.\.venv\Scripts\python.exe -m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000
```
- Verificar: `[SLINGSHOT ENGINE] Iniciando en http://0.0.0.0:8000`

### Paso 2: Frontend (Next.js)
// turbo
2. Iniciar el servidor de desarrollo:
```powershell
npx next dev
```
- Verificar: `✓ Ready in X.Xs`

---

## ⚠️ IMPORTANTE - Regla de oro en Windows + PowerShell

**NUNCA usar `npm run dev`** para el frontend.

| Comando | Resultado en Windows/PowerShell |
|---------|-------------------------------|
| `npm run dev` | ❌ Pasa por `.cmd` → genera prompt interactivo → muere |
| `npx next dev` | ✅ Llama a Next.js directamente → funciona siempre |

---

## ✅ Verificación
- Backend API: http://localhost:8000/docs (Swagger UI)
- Frontend: http://localhost:3000

## 🌐 Nota sobre VPN
Binance bloquea IPs de VPNs. Para que los datos de mercado carguen correctamente,
**desactiva el VPN** antes de iniciar el proyecto.
