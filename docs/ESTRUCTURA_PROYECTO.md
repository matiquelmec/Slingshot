# 🏗️ Estructura del Proyecto Slingshot v12.0 Sovereign Core

> Guía de referencia oficial para la arquitectura, mantenimiento y evolución del sistema.
> **Última actualización**: Agosto 2026 (v12.0 Sovereign Core)

---

## 📁 Árbol de Directorios Actualizado

```text
Slingshot_Trading/
├── app/                             # ═══ DELTA: Terminal Reactiva Frontend (Next.js 15) ═══
│   ├── components/
│   │   ├── radar/                   # OpportunitiesScanner (Notas Educativas + KER Anti-Ruido Filter)
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
│   │   ├── confluence.py            # ConfluenceManager v12.0 — Veto Macro BTC + 10 Factores
│   │   ├── store.py                 # MemoryStore — Estado persistente por activo
│   │   ├── session_manager.py       # Gestión de sesiones (Asia/London/NY)
│   │   └── validator.py             # AI Validator Agent — Auditoría narrativa
│   ├── router/                      # Pipeline de señales
│   │   ├── analyzer.py              # MarketAnalyzer — LRU Cache de 200 ítems + SMC Overlays
│   │   └── gatekeeper.py            # SignalGatekeeper — Motor Bayesiano + Sovereign Bypass
│   ├── strategies/                  # Lógica táctica
│   │   └── smc.py                   # SMCInstitutionalStrategy (Tiers A/B con Entrada Límite Óptima)
│   ├── indicators/                  # Análisis técnico e institucional
│   │   ├── health.py                # Engine KER (Kaufman Efficiency Ratio — Anti-Ruido/Cuarentena)
│   │   ├── volume.py                # Volume Engine — RVOL, Order Flow Delta + CVD Divergence
│   │   ├── structure.py             # Order Blocks, FVGs, S/R + Trap Detection LAF/LBF
│   │   ├── fibonacci.py             # Retrocesos, Golden Pocket (Evaluación Always-On)
│   │   ├── liquidations.py          # Clusters de Liquidación proyectados en vivo
│   │   └── regime.py                # Detector de Régimen de Mercado (EMA + ADX)
│   ├── risk/                        # Gestión de riesgo
│   │   └── risk_manager.py          # RiskManager v12.0 — 1.80% SL Guardarraíl Altcoins + Lot Size Calculator
│   ├── execution/                   # Ejecución de órdenes
│   │   ├── nexus.py                 # Nexus Bridge — Orquestador de ejecuciones
│   │   └── bitunix_executor.py      # Executor Bitunix con Adaptive Iceberg Order Slicer (> $2,000 USDT)
│   ├── ml/                          # Machine Learning
│   │   ├── inference.py             # SlingshotML — Aceleración ONNX Runtime C++ (Sub-2ms) + XGBoost
│   │   └── features.py              # Feature engineering
│   ├── workers/                     # Procesos en background
│   │   └── market_scanner.py        # Scanner de Oportunidades SMC + Veto Macro BTC (Radar)
│   └── tests/                       # ═══ Tests de Integridad (14 Tests en Verde 100% OK) ═══
│       ├── test_v12_sovereign.py    # Suite de verificación v12.0 Sovereign (Veto BTC Macro)
│       ├── test_v11_ker_adaptive.py # Test del motor adaptativo KER Anti-Ruido
│       ├── test_v11_apex.py         # Suite de verificación v11.0 Apex (CVD, Iceberg, ONNX)
│       └── test_limit_entry_risk.py # Test de entradas límite y protección SL 1.80%
├── slingshot_hft_sidecar/          # ═══ OMEGA HFT SIDECAR: Ingestor Node.js 20+ (Puerto 8080) ═══
├── docs/                            # ═══ Documentación Técnica Oficial ═══
│   ├── SLINGSHOT_BIBLE_V12.md       # Biblia Técnica de v12.0 Sovereign Core
│   └── ESTRUCTURA_PROYECTO.md       # Referencia de arquitectura del sistema
├── launch.bat                       # Lanzador Unificado para Windows
└── README.md                        # Documentación Oficial v12.0 Sovereign Core
```

---

## 🔬 Suite de Pruebas Unitarias Verificadas

| Test File | Descripción del Test | Resultado |
| :--- | :--- | :---: |
| `test_v12_sovereign.py` | Veto Absoluto por BTC Macro Divergence (H2) | **PASS** |
| `test_v11_ker_adaptive.py` | Motor Adaptativo KER y Detección de Cuarentena | **PASS** |
| `test_v11_apex.py` | Inferencia ONNX, CVD Divergence y Fragmentación Iceberg | **PASS** |
| `test_limit_entry_risk.py` | Entradas Límite SMC y Guardarraíl SL 1.80% Altcoins | **PASS** |
| `test_volume_delta.py` | Order Flow Delta y Tick-Rule HFT | **PASS** |
| `test_confluence_unit.py` | Ponderación del ConfluenceManager (10 Factores) | **PASS** |

---

*Slingshot v12.0 Sovereign Core — Documentación Oficial de Estructura de Proyecto.*
