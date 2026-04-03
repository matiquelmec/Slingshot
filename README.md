# 🛡️ SLINGSHOT v4.3.5 TITANIUM EDITION
> **"Institutional-Grade Algorithmic Terminal. Zero Latency. Zero Noise. Full Sovereignty."**

![Status](https://img.shields.io/badge/Status-TOTALMENTE_DESPLEGADO-0d2a1a?style=for-the-badge&logo=codeproject&logoColor=fff)
![Version](https://img.shields.io/badge/Version-4.3.5_Titanium-1a3a6e?style=for-the-badge)
![Engine](https://img.shields.io/badge/Engine-SMC_Asna--4-ffd700?style=for-the-badge&labelColor=0a0a0a)

## 💎 La Visión (The Pivot)
**Slingshot** no es un indicador retail. Es una **Terminal Algorítmica Local-First** diseñada para capturar la huella del **Smart Money** (Instituciones) a través de una arquitectura reactiva de baja latencia. 

Eliminamos el ruido de los indicadores tradicionales para centrarnos en lo único que mueve el precio: **Liquidez, Tiempo y Volumen.**

---

## 🏗️ Arquitectura de Baja Latencia (Zero-Delay)

### 📡 El Pipeline Reactivo
El sistema utiliza un orquestador **WebSocket** que inyecta datos directamente desde el radar de alta frecuencia hacia un motor de inferencia híbrido:

1.  **Fast Path (Math):** Procesa cada tick en milisegundos para detectar absorción institucional y barridas de liquidez (FVG/OB).
2.  **Slow Path (IA):** El analista senior integrado **(Gemma-3 Local)** genera tácticas estructurales cada cierre de vela, blindado con un sistema de inyección de precio en vivo (Anti-Hallucination).
3.  **Memory Store:** Persistencia atómica en RAM que elimina el cuello de botella de las bases de datos tradicionales en el flujo de ejecución.

---

## 🛡️ Blindaje de Supervivencia (VPS Londres/NY Ready)
La versión **v4.3.5 Titanium** introduce 4 protocolos de endurecimiento para entornos hostiles:

- **Stale Guard (Frontend):** Detección de "Pestañas Zombie" tras suspensión de PC; purga de mensajes obsoletos y resync automático al HEAD.
- **Advisor Isolation:** Protección del Event Loop con timeouts de 45s y semáforos de CPU concurrente.
- **Auto-Resurrection (systemd):** Watchdog institucional que garantiza el 99.9% de uptime reviviendo el sistema en <20s tras cualquier fallo de proceso.
- **Docker Core:** Contenedores aislados con límites de RAM (`mem_limit: 2g`) para evitar saturación del host.

---

## 🏹 Smart Money Concept (SMC) Engine
- **KillZones Dinámicas:** NY & Londres ajustadas por horario UTC y DST.
- **Order Blocks & FVGs:** Detección de zonas экстреmas (Wait For Sweep) con algoritmo de mitigación en tiempo real.
- **SMT Divergence:** Comparación dinámica multiactivo para confirmar sesgos institucionales.
- **RVOL 20x Detection:** Escáner de volumen en tiempo real para alertar sobre Absorción Profesional (Fuego Institucional).

---

## 🚀 Despliegue en Un Click (Launcher)

### Requisitos Previos
- **Backend:** Python 3.12+ (con dependencias en `requirements.txt`).
- **Frontend:** Node.js 20+ (Next.js 15).
- **IA Local:** Ollama (modelo `gemma3:4b`).

### Inicio Local
```powershell
./start.ps1
```

### Despliegue VPS (Docker)
```bash
docker-compose up -d --build
```

---

## 📂 Estructura Maestro de Operaciones
```text
slingshot_gen1/
├── 📁 engine/          # El Cerebro Algorítmico (FastAPI + SMC Strategy)
├── 📁 app/             # La Terminal UI (Next.js + Zustand 5)
├── 📁 docs/            # Especificación Técnica Maestra (v4.3.5 Titanium)
├── 📁 deploy/          # Artefactos de VPS: Dockerfiles, systemd, Watchdogs
└── 📄 start.ps1        # El Orquestador de Lanzamiento
```

## 📖 Documentación Profunda
Para auditorías forenses o especificaciones de bajo nivel, consulta:
👉 **[docs/SPECIFICATION_V4_PLATINUM.md](file:///c:/Users/Mat%C3%ADas%20Riquelme/Desktop/Proyectos%20documentados/Slingshot_Trading/docs/SPECIFICATION_V4_PLATINUM.md)**

---
*Slingshot v4.3.5 Titanium — El Estándar Maestro de la Terminal Algorítmica Local.*
*Unified by Antigravity — April 03, 2026*
