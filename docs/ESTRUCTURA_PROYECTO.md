# 🏗️ Estructura del Proyecto Slingshot v22.2 Apex Sovereign

> Guía de referencia oficial para la arquitectura, mantenimiento y evolución del sistema.
> **Última actualización**: Agosto 2026 (v22.2 Apex Sovereign — 1-Click Installer & Onboarding Wizard)

---

## 📁 Árbol de Directorios Oficial v22.2

```text
Slingshot_Trading/
├── app/                             # ═══ DELTA: Terminal Reactiva Frontend (Next.js 15) ═══
│   ├── components/
│   │   ├── radar/                   # OpportunitiesScanner (Notas Educativas + OTE Watchdog)
│   │   ├── setup/                   # OnboardingModal (Asistente Visual de API Keys con Live Test)
│   │   ├── signals/                 # SignalTerminal & SignalCardItem (Calculadora Lote Sugerido)
│   │   ├── execution/               # Panel de Monitoreo de Posiciones y Auditor de Órdenes
│   │   └── ui/                      # PlanOperativoPanel & Copiar Plan Completo
│   ├── store/                       # TelemetryStore (Zustand 5 State Management)
│   └── utils/                       # Formatters & Signal LifeCycle Logic
├── engine/                          # ═══ SIGMA: Cerebro Algorítmico (Python 3.12 / Rust) ═══
│   ├── main_router.py               # Pipeline principal: Orquesta SMC → Confluence → Gatekeeper
│   ├── api/                         # Capa de comunicación REST / WebSockets
│   │   ├── main.py                  # FastAPI entry point con lifespan (Auto-start de Workers)
│   │   ├── setup.py                 # SetupRouter — Endpoints de Onboarding, Live Test y Guardado Atómico
│   │   ├── config.py                # Settings centralizadas (.env) + Watchlist Curada
│   │   ├── ws_manager.py            # WebSocket broadcaster al frontend
│   │   └── advisor.py               # Motor IA (Ollama/Gemma-3) + Fallback Determinístico
│   ├── core/                        # Núcleo del motor y Persistencia
│   │   ├── vault.py                 # SQLite WAL Vault — Persistencia Transaccional ACID (SSoT)
│   │   ├── confluence.py            # ConfluenceManager — Jurado de Confluencia (14 Factores SMC)
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
│   │   ├── risk_manager.py          # RiskManager v22.0 — Matriz Adaptativa R:R y Sizing
│   │   └── ftmo_guardian.py         # FTMO Guardian Shield — Kill-Switch Diario (-3.5%)
│   ├── execution/                   # Ejecución Institucional en Exchanges
│   │   ├── nexus.py                 # Nexus Node — Orquestador de Ejecución con Slot Recycling
│   │   ├── bitunix_executor.py      # Conector Bitunix Futures (Limit Orders Maker 0.02% + TPSL)
│   │   ├── mt5_bridge.py            # Puente MetaTrader 5 (Órdenes Límite TradFi + FTMO Lockout)
│   │   └── delta_executor.py        # Fragmentador de Órdenes Iceberg (Delta 60/20/20)
│   ├── workers/                     # Procesos en segundo plano
│   │   ├── orchestrator.py          # SlingshotOrchestrator — Director de orquesta 24/7
│   │   ├── market_scanner.py        # Escáner de Oportunidades Multitemporal (14 Activos)
│   │   ├── trade_manager.py         # Centinela de Posiciones Activas & Apex Limit Sentinel
│   │   ├── news_worker.py           # Ingestor de Noticias en Tiempo Real
│   │   └── calendar_worker.py       # Calendario Económico de Alto Impacto
│   ├── backtest/                    # Motor de Auditoría y Backtesting
│   │   ├── unified_backtest_engine.py # The Truth Engine — Auditoría con paridad 100%
│   │   ├── backtest_tradfi_6mo.py   # Backtest TradFi de 6 meses
│   │   ├── data/                    # Datasets históricos binarios .parquet (51 archivos)
│   │   └── reports/                 # Reportes oficiales (unified + legacy_runs/)
│   └── tests/                       # ═══ Suite de Certificación QA (56 Tests al 100% OK) ═══
│       ├── test_setup_and_portability.py            # Onboarding, live test de keys, guardado atómico
│       ├── test_post_tp3_and_trailing_invariance.py # Post-TP3 híbrido, 70% ratchet e invarianza SL
│       ├── test_risk_and_resilience_advanced.py     # Micro-buffer BE, 60/20/20 y resiliencia a gaps
│       ├── test_intelligent_limit_order_sentinel.py # Centinela de órdenes límite
│       ├── test_full_engine_autonomy_audit.py       # Autonomía, Slot Recycling y no retroceso SL
│       ├── test_live_trade_management.py            # Gestión en vivo de Stop Loss y Fast BE en Bitunix
│       ├── test_sqlite_vault.py                     # Persistencia WAL, anti-spam y concurrencia
│       ├── test_mt5_bridge.py                       # Ejecución MT5 y bloqueo de Drawdown FTMO
│       ├── test_deterministic_pipeline_isolation.py # Latencia y lot sizing sin red
│       ├── test_session_mastery.py                  # Killzones de sesión (Asia/London/NY)
│       ├── test_market_scanner_hft.py               # Watchdog OTE y order flow fallback
│       ├── test_ftmo_security_guard.py              # Guardian FTMO, Lotes US500/Oro y Config TradFi
│       ├── test_telegram_persistence.py             # Deduplicación y supervivencia a reinicios
│       ├── test_dynamic_sl_professional_audit.py    # Invarianza Monótona, Ratchet 1R-10R y Micro-Buffer ATR
│       └── test_dynamic_universe_screener.py        # Rotación cuantitativa de activos
├── scripts/                         # ═══ Herramientas de Mantenimiento y QA ═══
│   ├── run_qa_suite.py              # Ejecutor oficial de la suite QA (56/56 tests)
│   ├── check_live_bitunix_now.py    # Auditoría en tiempo real de posiciones y SL en Bitunix
│   ├── check_open_orders_now.py     # Inspección de órdenes abiertas y límites en Bitunix
│   ├── compare_optimization_matrix.py # Matriz comparativa de optimización cuantitativa
│   ├── audit_tradfi_universe_deep.py # Auditoría inteligente TradFi multi-activo
│   ├── audit_all_symbols_backtest.py # Auditoría multi-activo en 15m y 1h
│   ├── diagnose_scanner.py          # Diagnóstico rápido de señales del escáner
│   └── test_15m_scan.py             # Benchmark de escaneo en 15m
├── docs/                            # ═══ Documentación Técnica y Biblias ═══
│   ├── ESTRUCTURA_PROYECTO.md       # Guía de arquitectura (este archivo)
│   ├── SLINGSHOT_BIBLE_V22.md       # Biblia técnica oficial v22.2 Apex Sovereign
│   └── knowledge/                   # Base de conocimiento institucional
├── install.bat                      # Instalador automatizado 1-Click para Windows
├── install.ps1                      # Script PowerShell con winget y auto-configuración
└── launch.bat                       # Script de arranque rápido para Windows
```

---

## 🔬 Suite de Pruebas Unitarias Verificadas (57/57 Tests en Verde)

```powershell
python scripts/run_qa_suite.py
```

| Módulo de Prueba | Componente Auditado | Resultado |
| :--- | :--- | :---: |
| `test_setup_and_portability.py` | Asistente de Onboarding, Live Key Testing, Guardado Atómico | **PASS (5/5)** |
| `test_post_tp3_and_trailing_invariance.py` | Híbrido 50/50, 70% Ratchet, Invarianza Reboot y Rechazo de Degradación | **PASS (6/6)** |
| `test_risk_and_resilience_advanced.py` | Micro-Buffer BE, Salidas 60/20/20, Gaps y Lockout FTMO | **PASS (5/5)** |
| `test_intelligent_limit_order_sentinel.py` | Missed Target, Pre-SL, TTL y Auto-Purga | **PASS (6/6)** |
| `test_full_engine_autonomy_audit.py` | Autonomía, Slot Recycling y Seguridad de SL | **PASS (3/3)** |
| `test_live_trade_management.py` | Fast BE (+1.0R) y Sincronización con Bitunix | **PASS (2/2)** |
| `test_sqlite_vault.py` | Repositorio SQLite WAL y Concurrencia | **PASS (4/4)** |
| `test_mt5_bridge.py` | Puente MetaTrader 5 y Drawdown Lockout | **PASS (2/2)** |
| `test_deterministic_pipeline_isolation.py` | Cero latencia ($< 15\text{ ms}$) y Sizing | **PASS (2/2)** |
| `test_session_mastery.py` | Sesiones Institucionales y Killzones | **PASS (4/4)** |
| `test_market_scanner_hft.py` | Escáner OTE Watchdog y Fallback HFT | **PASS (3/3)** |
| `test_ftmo_security_guard.py` | FTMO Guardian Shield, Lotes US500/Oro y Config TradFi | **PASS (4/4)** |
| `test_telegram_persistence.py` | Deduplicación de Alertas y Drift de Precio | **PASS (3/3)** |
| `test_dynamic_sl_professional_audit.py` | Invarianza Monótona, Ratchet 1R-10R y Micro-Buffer ATR | **PASS (5/5)** |
| `test_dynamic_universe_screener.py` | Inmutabilidad Core y Rotación RVOL/KER | **PASS (3/3)** |
| **TOTAL** | **57 Pruebas Unitarias Ejecutadas en 7.83s** | **100% PASS ✅** |

*Slingshot v21.0 Apex Autonomous — Documentación Oficial de Estructura de Proyecto.*
