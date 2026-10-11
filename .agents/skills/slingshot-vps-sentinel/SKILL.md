---
name: slingshot-vps-sentinel
description: Protocolos, scripts y herramientas para despliegue continuo, auditoría en vivo y auto-healing del VPS de producción Slingshot (80.65.211.99). Cubre sincronización GitOps, verificación de la tríada operativa (Python FastAPI :8000, Node HFT Sidecar, MT5), inspección de logs y healthchecks.
---

# Slingshot VPS Sentinel & Deployment Orchestrator

Esta habilidad equipa a los agentes (especialmente a **KRONOS**) con las directivas, credenciales y scripts para interactuar, desplegar y auditar el VPS institucional de producción (`80.65.211.99`).

---

## 1. Topología del Servidor de Producción

| Parámetro | Valor |
| :--- | :--- |
| **Host IP** | `80.65.211.99` |
| **Protocolo de Gestión** | WinRM sobre HTTPS (`Port 5986`, Auth Basic, SSL) |
| **Directorio Raíz** | `C:\Slingshot` |
| **Backend FastAPI** | `http://127.0.0.1:8000` (Healthcheck: `/api/v1/health`) |
| **HFT WebSockets Sidecar** | Node.js corriendo `sidecar/index.js` |
| **Terminal TradFi** | `terminal64.exe` (MetaTrader 5) |
| **Directorio de Logs** | `C:\Slingshot\logs` (`sentinel.log`, `slingshot.log`, etc.) |

---

## 2. Comandos Canónicos de Auditoría y Despliegue

### A. Auditoría Remota Rápida (Sin Reinicio)
Ejecuta una inspección completa de logs, PIDs activos y estado del sentinel:
```powershell
powershell -File scripts/deploy/sync_and_audit_vps.ps1
```

### B. Despliegue Atómico y Reinicio Verificado (Post-Push Gate)
Descarga la última versión de `origin/main` en el VPS, reinicia el motor con Uvicorn, espera la estabilización y valida el healthcheck HTTP:
```powershell
powershell -File scripts/deploy/deploy_and_verify_vps.ps1
```

---

## 3. Protocolo de Inspección en Tres Capas (KRONOS Invariant)

Toda auditoría de despliegue en producción debe certificar:

1. **Capa 1: Tríada de Procesos Vivos:**
   - `python.exe` (Backend FastAPI, PID activo, WorkingSet > 100MB).
   - `node.exe` (Sidecar WebSocket, WorkingSet > 40MB).
   - `terminal64.exe` (MetaTrader 5, si aplica para TradFi).
2. **Capa 2: Respuesta HTTP 200 en Healthcheck:**
   - `http://127.0.0.1:8000/api/v1/health` debe responder `{"status": "ok"}` o equivalente dentro de un timeout de 10s.
3. **Capa 3: Higiene de Logs (Sentinel Peace):**
   - `sentinel.log` no debe presentar reinicios en bucle infinito en los últimos 5 minutos.
   - Si se detecta un fallo, inspeccionar el log del servicio:
     ```powershell
     powershell -File scripts/deploy/inspect_service_log.ps1
     ```

---

## 4. Procedimiento de Contingencia y Rollback

Si el healthcheck falla tras un despliegue:
1. Revertir inmediatamente al commit anterior en el VPS:
   ```powershell
   git reset --hard HEAD~1
   ```
2. Forzar reinicio del proceso FastAPI.
3. Notificar inmediatamente la falla con el traceback exacto al usuario.
