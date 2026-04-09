# 🛡️ SLINGSHOT v6.0.0 Master Gold TITANIUM EDITION
> **"Institutional-Grade Algorithmic Terminal. Zero Latency. Zero Noise. Full Sovereignty."**

![Status](https://img.shields.io/badge/Status-100%_HARDENED_&_REORGANIZED-0d2a1a?style=for-the-badge&logo=codeproject&logoColor=fff)
![Version](https://img.shields.io/badge/Version-6.0.0_Titanium-1a3a6e?style=for-the-badge)
![Engine](https://img.shields.io/badge/Engine-SMC_Asna--4-ffd700?style=for-the-badge&labelColor=0a0a0a)

## 🏗️ Arquitectura de Baja Latencia (Zero-Delay)

```mermaid
graph TB
    subgraph "Frontend — Next.js 15"
        A["Dashboard<br/>(page.tsx)"] --> B["TelemetryStore<br/>(Zustand 5)"]
        B --> C["WebSocket Client"]
        A --> D["TradingChart<br/>LW Charts"]
    end

    subgraph "Backend — Python FastAPI"
        J["main.py<br/>FastAPI"] --> K["ws_manager.py<br/>BroadcasterRegistry"]
        K --> L["SymbolBroadcaster<br/>(por activo:intervalo)"]
        L --> M["SlingshotRouter<br/>(main_router.py)"]
        M --> P["ConfluenceManager"]
        M --> Q["RiskManager"]
        L --> R["SessionManager"]
        L --> S["Advisor LLM<br/>(Ollama)"]
    end

    subgraph "Data Layer"
        Z["MemoryStore<br/>(RAM)"]
        AA["JSON Files<br/>(session_state)"]
        BB["Binance WS<br/>(Streaming)"]
    end

    C <--- "WebSocket (LocalMasterSync v2)" ---> J
    L --> Z
    R --> AA
    BB --> L
```

### 📡 El Pipeline Reactivo
El sistema utiliza un orquestador **WebSocket** que inyecta datos directamente desde el radar de alta frecuencia hacia un motor de inferencia híbrido:

1.  **Fast Path (Math):** Procesa cada tick en milisegundos para detectar absorción institucional y barridas de liquidez (FVG/OB).
2.  **Slow Path (IA):** El analista senior integrado **(Gemma-3 Local)** genera tácticas estructurales cada cierre de vela, blindado con un sistema de inyección de precio en vivo (Anti-Hallucination).
3.  **Memory Store:** Persistencia atómica en RAM que elimina el cuello de botella de las bases de datos tradicionales en el flujo de ejecución.

---

## 🛡️ Blindaje & Hardening v6.0 (Zero-Noise)
La versión **v6.0.0 Master Gold Titanium** introduce el protocolo de silencio operativo y armonización de riesgo:

- **Unificación de Riesgo:** Consolidación de `MIN_RR` en `config.py` (Master 3.0) y el motor `RiskManager`.
- **Refactorización de Tests:** Tests movidos desde `scripts/` hacia `engine/tests/` para cumplimiento de estándares PEP.
- **Veto Transparente:** Las señales denegadas ahora explican exactamente por qué (HTF, Valor, Macro, etc.).
- **Ollama Semantic Cache:** Inferencia IA optimizada con MD5 para evitar saturación de CPU innecesaria.

---

## 📂 Estructura Maestro de Operaciones
```text
slingshot_gen1/
├── 📁 engine/          # El Cerebro Algorítmico (FastAPI + SMC Strategy)
│   ├── 📁 tests/       # 🏹 15 tests operativos consolidados (v6.0)
│   ├── 📁 data/        # Persistencia de sesiones (v6.0 JSON-RAM)
├── 📁 app/             # La Terminal UI (Next.js + Zustand 5)
├── 📁 docs/            # Especificación Técnica & Auditoría Profesional
├── 📁 deploy/          # Artefactos de VPS: Dockerfiles, systemd, Watchdogs
└── 📄 start.ps1        # El Orquestador de Lanzamiento (v6.0 High Priority)
```

## 📖 Auditoría Forense
Para la referencia técnica completa del sistema con diagramas, bugs, scorecard y roadmap:
👉 **[docs/SLINGSHOT_BIBLE_V6.md](docs/SLINGSHOT_BIBLE_V6.md)** — La Biblia Unificada

Para auditorías legacy o resúmenes ejecutivos:
- [docs/professional_audit_v6.md](docs/professional_audit_v6.md) — Resumen v6
- [docs/professional_audit_v5.md](docs/professional_audit_v5.md) — Auditoría v5 original

---
*v6.0.0 Master Gold Titanium — El Estándar Maestro de la Terminal Algorítmica Local.*
*Unified & Hardened by Antigravity — April 06, 2026*
