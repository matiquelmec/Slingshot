# 🏗️ Estructura del Proyecto Slingshot v11.0 Apex Engine

> Guía de referencia oficial para la arquitectura, mantenimiento y evolución del sistema.
> **Última actualización**: Agosto 2026 (v11.0 Apex Engine)

---

## 📁 Árbol de Directorios Actualizado

```text
Slingshot_Trading/
├── app/                             # ═══ DELTA: Terminal Reactiva Frontend (Next.js 15) ═══
│   ├── components/
│   │   ├── radar/                   # ActiveAssetsMonitor & OpportunitiesScanner (CVD / Delta Badges)
│   │   ├── signals/                 # SignalTerminal & SignalCardItem (Calculadora Lote Sugerido)
│   │   └── ui/                      # PlanOperativoPanel & Copiar Plan Completo
│   ├── store/                       # TelemetryStore (Zustand 5 State Management)
│   └── utils/                       # Formatters & Signal LifeCycle Logic
├── engine/                          # ═══ SIGMA: Cerebro Algorítmico (Python 3.12 / FastAPI) ═══
│   ├── main_router.py               # Pipeline principal: Orquesta SMC → Confluence → Gatekeeper
│   ├── api/                         # Capa de comunicación REST / WebSockets
│   │   ├── main.py                  # FastAPI entry point + lifespan
│   │   ├── config.py                # Settings centralizadas (.env)
│   │   ├── ws_manager.py            # WebSocket broadcaster al frontend
│   │   └── advisor.py               # Motor IA (Ollama/Gemma-3) + Fallback Determinístico
│   ├── core/                        # Núcleo del motor
│   │   ├── confluence.py            # ConfluenceManager v11.0 — 10-Factor Confluence (CVD + SMT + Delta)
│   │   ├── store.py                 # MemoryStore — Estado persistente por activo
│   │   ├── session_manager.py       # Gestión de sesiones (Asia/London/NY)
│   │   └── validator.py             # AI Validator Agent — Auditoría narrativa
│   ├── router/                      # Pipeline de señales
│   │   ├── analyzer.py              # MarketAnalyzer — LRU Cache de 200 ítems + SMC Overlays
│   │   └── gatekeeper.py            # SignalGatekeeper — Motor Bayesiano + Sovereign Bypass
│   ├── strategies/                  # Lógica táctica
│   │   └── smc.py                   # SMCInstitutionalStrategy (Tiers A/B con Entrada Límite Óptima)
│   ├── indicators/                  # Análisis técnico e institucional
│   │   ├── volume.py                # Volume Engine — RVOL, Order Flow Delta + CVD Divergence (Factor 9.8)
│   │   ├── structure.py             # Order Blocks, FVGs, S/R + Trap Detection LAF/LBF
│   │   ├── fibonacci.py             # Retrocesos, Golden Pocket (Evaluación Always-On)
│   │   ├── liquidations.py          # Clusters de Liquidación proyectados en vivo
│   │   └── regime.py                # Detector de Régimen de Mercado (EMA + ADX)
│   ├── risk/                        # Gestión de riesgo
│   │   └── risk_manager.py          # RiskManager v11.0 — 1.80% SL Guardarraíl Altcoins + Lot Size Calculator
│   ├── execution/                   # Ejecución de órdenes
│   │   ├── nexus.py                 # Nexus Bridge — Orquestador de ejecuciones
│   │   └── bitunix_executor.py      # Executor Bitunix con Adaptive Iceberg Order Slicer (> $2,000 USDT)
│   ├── ml/                          # Machine Learning
│   │   ├── inference.py             # SlingshotML — Aceleración ONNX Runtime C++ (Sub-2ms) + XGBoost
│   │   └── features.py              # Feature engineering
│   ├── workers/                     # Procesos en background
│   │   └── market_scanner.py        # Scanner de Oportunidades SMC + OTE Watchdog (Radar)
│   └── tests/                       # ═══ Tests de Integridad (13 Tests en Verde 100% OK) ═══
│       ├── test_v11_apex.py         # Suite de verificación v11.0 Apex (CVD, Iceberg, ONNX)
│       ├── test_limit_entry_risk.py # Test de entradas límite y protección SL 1.80%
│       └── test_volume_delta.py     # Test de Order Flow Delta
├── slingshot_hft_sidecar/          # ═══ OMEGA HFT SIDECAR: Ingestor Node.js 20+ (Puerto 8080) ═══
├── launch.bat                       # Lanzador Unificado para Windows
└── README.md                        # Documentación Oficial v11.0 Apex
```

---

## 🔬 Suite de Pruebas Unitarias Verificadas

| Test File | Descripción del Test | Resultado |
| :--- | :--- | :---: |
| `test_v11_apex.py` | Inferencia ONNX, CVD Divergence y Fragmentación Iceberg | **PASS** |
| `test_limit_entry_risk.py` | Entradas Límite SMC y Guardarraíl SL 1.80% Altcoins | **PASS** |
| `test_volume_delta.py` | Order Flow Delta y Tick-Rule HFT | **PASS** |
| `test_confluence_unit.py` | Ponderación del ConfluenceManager (10 Factores) | **PASS** |
| `test_regime.py` | Clasificación de Régimen de Mercado Wyckoff | **PASS** |

---

*Slingshot v11.0 Apex Engine — Documentación Oficial de Estructura de Proyecto.*
