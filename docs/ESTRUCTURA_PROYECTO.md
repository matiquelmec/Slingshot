# 🏗️ Estructura del Proyecto Slingshot v21.0 Apex Autonomous

> Guía de referencia oficial para la arquitectura, mantenimiento y evolución del sistema.
> **Última actualización**: Agosto 2026 (v21.0 Apex Autonomous)

---

## 📁 Árbol de Directorios Oficial v21.0

```text
Slingshot_Trading/
├── app/                             # ═══ DELTA: Terminal Reactiva Frontend (Next.js 15) ═══
│   ├── components/
│   │   ├── radar/                   # OpportunitiesScanner (Notas Educativas + OTE Watchdog)
│   │   ├── signals/                 # SignalTerminal & SignalCardItem (Calculadora Lote Sugerido)
│   │   ├── execution/               # Panel de Monitoreo de Posiciones y Auditor de Órdenes
│   │   └── ui/                      # PlanOperativoPanel & Copiar Plan Completo
│   ├── store/                       # TelemetryStore (Zustand 5 State Management)
│   └── utils/                       # Formatters & Signal LifeCycle Logic
├── engine/                          # ═══ SIGMA: Cerebro Algorítmico (Python 3.12 / Rust) ═══
│   ├── main_router.py               # Pipeline principal: Orquesta SMC → Confluence → Gatekeeper
│   ├── api/                         # Capa de comunicación REST / WebSockets
│   │   ├── main.py                  # FastAPI entry point con lifespan (Auto-start de Workers)
│   │   ├── config.py                # Settings centralizadas (.env) + Watchlist Curada
│   │   ├── ws_manager.py            # WebSocket broadcaster al frontend
│   │   └── advisor.py               # Motor IA (Ollama/Gemma-3) + Fallback Determinístico
│   ├── core/                        # Núcleo del motor y Persistencia
│   │   ├── vault.py                 # SQLite WAL Vault — Persistencia Transaccional ACID (SSoT)
│   │   ├── confluence.py            # ConfluenceManager — Jurado de Confluencia (12 Factores SMC)
│   │   ├── store.py                 # MemoryStore — Estado persistente por activo y buffers
│   │   ├── session_manager.py       # Gestión de sesiones institucionales (Asia/London/NY)
│   │   └── validator.py             # AI Validator Agent — Auditoría narrativa
│   ├── router/                      # Pipeline de señales y Despacho
│   │   ├── analyzer.py              # MarketAnalyzer — LRU Cache de 200 ítems + SMC Overlays
│   │   ├── gatekeeper.py            # SignalGatekeeper — Motor Bayesiano + Sovereign Bypass
│   │   └── telegram_dispatcher.py   # Telegram Institutional Dispatcher (1-Click MT5 Alerts)
│   ├── strategies/                  # Lógica táctica
│   │   └── smc.py                   # SMCInstitutionalStrategy (Tiers A/B con Entrada Límite OTE)
│   ├── indicators/                  # Indicadores Técnicos e Institucionales
│   │   ├── polars_engine.py         # Motor Vectorizado en Rust (Sub-2.5ms con Polars)
│   │   ├── health.py                # Engine KER (Kaufman Efficiency Ratio — Anti-Ruido)
│   │   ├── volume.py                # Volume Engine — RVOL, Order Flow Delta + CVD Divergence
│   │   ├── structure.py             # Order Blocks, FVGs, S/R + Trap Detection LAF/LBF
│   │   ├── fibonacci.py             # Retrocesos, Golden Pocket OTE (61.8% - 78.6%)
│   │   ├── liquidations.py          # Clusters de Liquidación proyectados en vivo
│   │   ├── regime.py                # Detector de Régimen de Mercado (EMA + ADX)
│   │   └── tradfi_provider.py       # Configuración de Activos TradFi (Oro, Nasdaq, Dow Jones)
│   ├── risk/                        # Gestión de riesgo institucional
│   │   ├── risk_manager.py          # RiskManager v21.0 — Matriz Adaptativa R:R y Sizing
│   │   └── ftmo_guardian.py         # FTMO Guardian Shield — Kill-Switch Diario (-3.5%)
│   ├── execution/                   # Ejecución Institucional en Exchanges
│   │   ├── nexus.py                 # Nexus Node — Orquestador de Ejecución con Slot Recycling
│   │   ├── bitunix_executor.py      # Conector Bitunix Futures (Limit Orders Maker 0.02% + TPSL)
│   │   ├── mt5_bridge.py            # Puente MetaTrader 5 (Órdenes Límite TradFi + FTMO Lockout)
│   │   └── delta_executor.py        # Fragmentador de Órdenes Iceberg (Delta 60/20/20)
│   ├── workers/                     # Procesos en segundo plano
│   │   ├── orchestrator.py          # SlingshotOrchestrator — Director de orquesta 24/7
│   │   ├── market_scanner.py        # Escáner de Oportunidades Multitemporal (14 Activos)
│   │   ├── trade_manager.py         # Centinela de Posiciones Activas & Fast Breakeven (+1.0R)
│   │   ├── news_worker.py           # Ingestor de Noticias en Tiempo Real
│   │   └── calendar_worker.py       # Calendario Económico de Alto Impacto
│   ├── backtest/                    # Motor de Auditoría y Backtesting
│   │   ├── unified_backtest_engine.py # The Truth Engine — Auditoría barra a barra
│   │   ├── backtest_tradfi_6mo.py   # Backtest TradFi de 6 meses
│   │   └── data/                    # Datasets históricos 180d en formato binario .parquet
│   └── tests/                       # ═══ Suite de Certificación QA (26 Tests al 100% OK) ═══
│       ├── test_full_engine_autonomy_audit.py # Autonomía, Slot Recycling y no retroceso SL
│       ├── test_live_trade_management.py      # Gestión en vivo de Stop Loss y Fast BE en Bitunix
│       ├── test_sqlite_vault.py               # Persistencia WAL, anti-spam y concurrencia
│       ├── test_mt5_bridge.py                 # Ejecución MT5 y bloqueo de Drawdown FTMO
│       ├── test_deterministic_pipeline_isolation.py # Latencia < 15ms sin dependencias LLM
│       ├── test_session_mastery.py            # Killzones Londres/NY y barridos de sesión
│       ├── test_market_scanner_hft.py         # OTE Watchdog y fallback orden flow HFT
│       ├── test_ftmo_security_guard.py        # Lot sizing de Oro y protección diaria FTMO
│       ├── test_telegram_persistence.py       # Tolerancia a reinicios y purga de alertas
│       └── test_dynamic_universe_screener.py  # Inmutabilidad de Core y rotación dinámica RVOL/KER
├── scripts/                         # ═══ Utilidades de Mantenimiento y Auditoría ═══
│   ├── manage_open_positions.py     # Script de inspección y protección en vivo en Bitunix
│   └── run_qa_suite.py              # Ejecutor de la suite de pruebas unitarias
├── slingshot_hft_sidecar/          # ═══ OMEGA HFT SIDECAR: Ingestor Node.js 20+ (Puerto 8080) ═══
├── docs/                            # ═══ Documentación Técnica Oficial ═══
│   ├── SLINGSHOT_BIBLE_V21.md       # Biblia Técnica de v21.0 Apex Autonomous
│   └── ESTRUCTURA_PROYECTO.md       # Referencia de arquitectura del sistema
├── launch.bat                       # Lanzador Unificado para Windows
└── README.md                        # Documentación Oficial v21.0 Apex Autonomous
```

---

## 🔬 Suite de Pruebas Unitarias Verificadas (29/29 Tests en Verde)

```powershell
python scripts/run_qa_suite.py
```

| Módulo de Prueba | Componente Auditado | Resultado |
| :--- | :--- | :---: |
| `test_full_engine_autonomy_audit.py` | Autonomía, Slot Recycling y Seguridad de SL | **PASS (3/3)** |
| `test_live_trade_management.py` | Fast BE (+1.0R) y Sincronización con Bitunix | **PASS (2/2)** |
| `test_sqlite_vault.py` | Repositorio SQLite WAL y Concurrencia | **PASS (4/4)** |
| `test_mt5_bridge.py` | Puente MetaTrader 5 y Drawdown Lockout | **PASS (2/2)** |
| `test_deterministic_pipeline_isolation.py` | Cero latencia ($< 15\text{ ms}$) y Sizing | **PASS (2/2)** |
| `test_session_mastery.py` | Sesiones Institucionales y Killzones | **PASS (4/4)** |
| `test_market_scanner_hft.py` | Escáner OTE Watchdog y Fallback HFT | **PASS (3/3)** |
| `test_ftmo_security_guard.py` | Guardián FTMO TradFi y Lotes | **PASS (3/3)** |
| `test_telegram_persistence.py` | Anti-Spam Telegram y Persistencia | **PASS (3/3)** |
| `test_dynamic_universe_screener.py` | Inmutabilidad Core y Rotación RVOL/KER | **PASS (3/3)** |

---

*Slingshot v21.0 Apex Autonomous — Documentación Oficial de Estructura de Proyecto.*
