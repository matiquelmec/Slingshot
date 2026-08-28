# 🏗️ Estructura del Proyecto Slingshot v22.3 Apex Sovereign

> Guía de referencia oficial para la arquitectura, mantenimiento y evolución del sistema.
> **Última actualización**: Agosto 2026 (v22.3 Apex Sovereign — Self-Healing, Dynamic Precision & 24/7 Watchdog)

---

## 📁 Árbol de Directorios Oficial v22.3

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
│   └── utils/                       # Formatters, ftmoSpecs.ts & Signal LifeCycle Logic
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
│   │   └── telegram_dispatcher.py   # Telegram Dispatcher — Heartbeat Vital cada 4h + Alertas 1-Click
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
│   │   └── tradfi_provider.py       # Proveedor TradFi: XAUUSD, US100, US30, US500, GER40, GBPJPY
│   ├── risk/                        # Gestión de riesgo institucional
│   │   ├── risk_manager.py          # RiskManager v22.3 — Matriz Adaptativa R:R y Sizing Estructural
│   │   └── ftmo_guardian.py         # FTMO Guardian Shield — Lotes Adaptativos y Kill-Switch (-3.5%)
│   ├── execution/                   # Ejecución Institucional en Exchanges
│   │   ├── nexus.py                 # Nexus Node — Auto-Healing Reconciliator, Slot Recycling y Precision
│   │   ├── bitunix_executor.py      # Conector Bitunix Futures — Dynamic Precision + Backoff Exponencial
│   │   ├── mt5_bridge.py            # Puente MetaTrader 5 — Órdenes TradFi + Trailing de Posiciones MT5
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
│   └── tests/                       # ═══ Suite Oficial de Certificación QA (63/63 Tests OK) ═══
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
│       ├── test_ftmo_security_guard.py              # Guardian FTMO, Lotes GER40/GBPJPY/Oro
│       ├── test_telegram_persistence.py             # Deduplicación y supervivencia a reinicios
│       ├── test_dynamic_sl_professional_audit.py    # Invarianza Monótona, Ratchet 1R-10R y Buffer ATR
│       ├── test_dynamic_universe_screener.py        # Rotación cuantitativa de activos
│       └── test_auto_healing_and_telemetry.py       # Auto-Healing, Backoff y Heartbeat Telegram
├── scripts/                         # ═══ Herramientas de Mantenimiento y QA ═══
│   ├── run_qa_suite.py              # Ejecutor oficial de la suite QA (63/63 tests PASS)
│   ├── watchdog_supervisor.py       # Supervisor Watchdog 24/7 para auto-reinicio en VPS
│   ├── check_live_bitunix_now.py    # Auditoría en tiempo real de posiciones y SL en Bitunix
│   ├── check_open_orders_now.py     # Inspección de órdenes abiertas y límites en Bitunix
│   ├── compare_optimization_matrix.py # Matriz comparativa de optimización cuantitativa
│   ├── audit_tradfi_universe_deep.py # Auditoría inteligente TradFi multi-activo
│   ├── audit_all_symbols_backtest.py # Auditoría multi-activo en 15m y 1h
│   ├── diagnose_scanner.py          # Diagnóstico rápido de señales del escáner
│   └── test_15m_scan.py             # Benchmark de escaneo en 15m
├── docs/                            # ═══ Documentación Técnica y Biblias ═══
│   ├── ESTRUCTURA_PROYECTO.md       # Guía de arquitectura oficial v22.3 (este archivo)
│   ├── SLINGSHOT_BIBLE_V22.md       # Biblia técnica oficial v22.3 Apex Sovereign
│   └── knowledge/                   # Base de conocimiento institucional
├── install.bat                      # Instalador automatizado 1-Click para Windows
├── install.ps1                      # Script PowerShell con winget y auto-configuración
└── launch.bat                       # Script de arranque rápido para Windows
```

---

## 🔒 Protocolos de Seguridad y Mantenimiento

1. **Protocolo SOP-07 (Manejo Seguro de Credenciales):**
   * Las API keys jamás se imprimen en logs, consola ni respuestas HTTP públicas.
   * La escritura de `.env` se realiza de forma atómica a través de buffers temporales.
2. **Protocolo SOP-08 (Invarianza Absoluta de Riesgo):**
   * Los Stop Loss nunca pueden retroceder o empeorar.
   * El cálculo de lotes de MT5 y Bitunix previene cualquier sobreapalancamiento que exceda el riesgo máximo por operación ($0.50\%$ en FTMO / $5\%$ de margen en Bitunix).
3. **Protocolo SOP-09 (Auto-Healing Reconciliator):**
   * Toda posición abierta es auditada cada 15-30s. Si carece de Stop Loss o Take Profits, el sistema los coloca automáticamente.
4. **Certificación Continua (QA Suite):**
   * Antes de cualquier despliegue o commit en producción, se ejecuta obligatoriamente:
     ```powershell
     python scripts/run_qa_suite.py
     ```
