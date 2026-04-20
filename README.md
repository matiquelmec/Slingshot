# 🛡️ SLINGSHOT v6.1.0 Master Gold TITANIUM HARDENED
> **"Institutional-Grade Algorithmic Terminal. Zero Latency. Zero Noise. Full Sovereignty."**

![Status](https://img.shields.io/badge/Status-100%_HARDENED_&_OPERATIONAL-0d2a1a?style=for-the-badge&logo=codeproject&logoColor=fff)
![Version](https://img.shields.io/badge/Version-6.1.0_Titanium_Hardened-1a3a6e?style=for-the-badge)
![Engine](https://img.shields.io/badge/Engine-SMC_Asna--4-ffd700?style=for-the-badge&labelColor=0a0a0a)
![Performance](https://img.shields.io/badge/Latency-Sub--100ms-blue?style=for-the-badge)

## 🏗️ Arquitectura de Baja Latencia (Zero-Delay)
Slingshot opera sobre un orquestador reactivo diseñado para la ejecución algorítmica de grado institucional:

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
        L --> T["ExecutionEngine<br/>(Binance)"]
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
    T --> BB
```

### 📡 El Pipeline Reactivo
El sistema utiliza un orquestador **WebSocket** que inyecta datos directamente desde el radar de alta frecuencia hacia un motor de inferencia híbrido:

1.  **Fast Path (Math):** Procesa cada tick en milisegundos para detectar absorción institucional y barridas de liquidez (FVG/OB/RVOL).
2.  **Slow Path (IA):** El analista senior integrado **(Qwen-3 Local)** genera tácticas estructurales cada cierre de vela, blindado contra alucinaciones.
3.  **Memory Store:** Persistencia atómica en RAM que elimina el cuello de botella de las bases de datos tradicionales.
4.  **Execution Engine:** Motor de firmas asíncronas para Binance Futures con manejo de latencia crítica.

---

## 🛡️ Blindaje & Hardening v6.1 (Zero-Noise)
La versión **v6.1.0 Master Gold Titanium Hardened** consolida el ecosistema para operaciones reales:

- **Unificación de Riesgo:** Consolidación de `MIN_RR` en `config.py` (**Master 2.5**) y el motor `RiskManager` (FTMO Compliant).
- **Saneamiento Analítico:** Resolución del error de resampling HTF (*Shape Mismatch*) mediante el protocolo *Safe Init*.
- **Telemetría Estabilizada:** Eliminación de parpadeos en el Radar mediante keys deterministas y detección de cambios reales.
- **Veto Transparente:** Las señales denegadas ahora explican exactamente por qué (HTF, Valor, Macro, etc.).
- **Ollama Semantic Cache:** Inferencia IA optimizada con MD5 para evitar saturación de CPU innecesaria.

---

## 📂 Estructura Maestro de Operaciones
```text
slingshot_gen1/
├── 📁 engine/          # El Cerebro Algorítmico (FastAPI + SMC Strategy)
│   ├── 📁 execution/   # ✅ Motor de Ejecución Binance Activo (v6.1)
│   ├── 📁 indicators/  # 12 Kernels de Análisis Técnico (SMC/Wyckoff)
│   ├── 📁 tests/       # 🏹 17 tests operativos consolidados (v6.1)
│   ├── 📁 data/        # Persistencia de sesiones (v6.1 JSON-RAM)
├── 📁 app/             # La Terminal UI (Next.js 15 + Zustand 5)
├── 📁 docs/            # Especificación Técnica & Auditoría Profesional
├── 📁 scripts/         # Artefactos de VPS, Docker y Watchdogs
└── 📄 start.ps1        # El Orquestador de Lanzamiento (v6.1 High Priority)
```

## 📖 Documentación Maestra (Blueprints)
Para la referencia técnica completa del sistema con diagramas, bugs, scorecard y roadmap:
👉 **[docs/SLINGSHOT_BIBLE_V6.md](docs/SLINGSHOT_BIBLE_V6.md)** — La Biblia Unificada

Para resúmenes ejecutivos y auditorías:
- [docs/professional_audit_v6.md](docs/professional_audit_v6.md) — Resumen v6
- [docs/knowledge/](docs/knowledge/) — Repositorio de Teoría SMC

---
*v6.1.0 Master Gold Titanium Hardened — El Estándar Maestro de la Terminal Algorítmica Local.*
*Unified & Hardened by Antigravity — April 20, 2026*
