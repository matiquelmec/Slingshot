# 🏗️ Estructura del Proyecto Slingshot v52.0 APEX ADAPTIVE TITANIUM

> Guía de referencia técnica oficial de la arquitectura, jerarquía de directorios, módulos y componentes del sistema autónomo Slingshot.
> **Última actualización**: Septiembre 2026 (v52.0 APEX ADAPTIVE TITANIUM — Sistema de Calibración Continua en Tres Bucles: Anillo 1 Bayesiano SMC <10µs, Anillo 2 HMM/GMM y Walk-Forward ML, Anillo 3 Post-Mortem NVIDIA NIM con Veto en Gatekeeper, Arquitectura Dual Cripto Bitunix 2.5% vs FTMO MetaTrader 5 TradFi 0.75%, Persistencia SQLite WAL y Suite QA Certificada al 100% en VPS).

---

## 📊 Árbol de Directorios Oficial v52.0

```text
Slingshot/
├── app/                             # ═══ DELTA: Terminal Reactiva Frontend (Next.js 15 / React 19) ═══
│   ├── (dashboard)/
│   │   ├── layout.tsx               # Navegación Dual: Sidebar Desktop (w-64) + Mobile Topbar, Drawer y Dock Inferior
│   │   ├── page.tsx                 # Overview Principal con Selector (SCANNER / DIAGNÓSTICO / TÁCTICA)
│   │   ├── chart/                   # Terminal de Gráficos con timeframes táctiles y leyendas colapsables SMC
│   │   └── ftmo/                    # Terminal Cuantitativa Prop Firm adaptada a rejilla responsiva MT5
│   ├── components/
│   │   ├── radar/                   # ActiveAssetsMonitor & OpportunitiesScanner (Cripto + TradFi)
│   │   ├── setup/                   # OnboardingModal (Asistente Visual de API Keys con Live Test Cifrado)
│   │   ├── signals/                 # SignalTerminal & SignalCardItem con Score de Confluencia
│   │   ├── execution/               # Panel de Monitoreo de Posiciones y Auditor de Órdenes en Tiempo Real
│   │   └── ui/                      # LatticeScanner (Tarjetas móviles / Grid desktop tabular), PlanOperativoPanel
│   ├── store/                       # TelemetryStore (Zustand 5 State Management)
│   └── utils/                       # Formatters, ftmoSpecs.ts & Signal LifeCycle Logic
│
├── engine/                          # ═══ SIGMA & OMEGA: Cerebro Algorítmico & Ejecución (Python 3.12 / Rust) ═══
│   ├── main_router.py               # Pipeline principal: Orquesta SMC → Confluence → Gatekeeper → Dispatcher
│   ├── api/                         # Capa de comunicación REST / WebSockets
│   │   ├── main.py                  # FastAPI entry point con lifespan (Auto-start de Workers y Daemons)
│   │   ├── setup.py                 # SetupRouter — Endpoints de Onboarding, Live Test y Guardado Atómico Cifrado
│   │   ├── config.py                # Settings centralizadas (.env) + Watchlist Curada + Umbrales de Riesgo
│   │   ├── ws_manager.py            # WebSocket broadcaster al frontend (Streaming a 60 FPS SOP-15)
│   │   └── registry.py              # SymbolBroadcaster y Pulso Global de Telemetría
│   ├── core/                        # Núcleo del motor, Calibración Bayesiana y Persistencia
│   │   ├── vault.py                 # SQLite WAL Vault — Persistencia Transaccional ACID (SSoT), Anti-Spam y Vetos
│   │   ├── confluence.py            # ConfluenceManager — Jurado de 14 Factores SMC + Meta-Labeling ML (+10pts)
│   │   ├── bayesian_confluence.py   # BayesianConfluenceCalibrator — Anillo 1 Calibración en Tiempo Real (<10µs SOP-72)
│   │   ├── store.py                 # MemoryStore — Estado persistente por activo y buffers en memoria
│   │   ├── session_manager.py       # Gestión de sesiones bancarias institucionales (Asia/London/NY Open SOP-29)
│   │   ├── tear_sheet.py            # Quantitative Tear Sheet Generator — Sharpe, Sortino, PF, Drawdown (SOP-60)
│   │   └── validator.py             # AI Validator Agent — Auditoría narrativa cuantitativa de señales
│   ├── agents/                      # Agentes Cuantitativos y de Razonamiento Profundo
│   │   ├── regime_agent.py          # SlingshotRegimeAgent — Detección Macro y Modulación de Riesgo (0.65x - 1.30x SOP-63)
│   │   ├── regime_hmm.py            # MarketRegimeHMM — Anillo 2 Clasificador GMM/HMM de 4 Estados (SOP-73)
│   │   └── post_mortem_agent.py     # PostMortemAgent — Anillo 3 Razonamiento NVIDIA NIM y Veto Preventivo (SOP-74)
│   ├── ml/                          # Pipeline de Machine Learning y Reentrenamiento
│   │   ├── inference.py             # SlingshotML — Inferencia Meta-Labeling con Hot-Reload Atómico (reload_model)
│   │   ├── train_rolling.py         # Rolling Walk-Forward Retraining con Guardián OOS ≥ 52% (SOP-73)
│   │   ├── train.py                 # Entrenamiento base LightGBM / XGBoost
│   │   └── drift_monitor.py         # Monitor de Drift de Modelo con métricas Kolmogorov-Smirnov
│   ├── router/                      # Pipeline de señales y Despacho
│   │   ├── analyzer.py              # MarketAnalyzer — LRU Cache de 200 ítems + SMC Overlays
│   │   ├── gatekeeper.py            # SignalGatekeeper — Filtro Bayesiano, Veto Post-Mortem y Sovereign Bypass
│   │   └── telegram_dispatcher.py   # Telegram Dispatcher — Multi-Destinatario Concurrente (SOP-54 / SOP-62)
│   │   └── telegram_dispatcher.py   # Telegram Dispatcher — Multi-Destinatario Concurrente (SOP-54 / SOP-62)
│   ├── strategies/                  # Lógica táctica cuantitativa
│   │   └── smc.py                   # SMCInstitutionalStrategy (Zonas OTE 61.8%-78.6%, Order Blocks y FVGs)
│   ├── indicators/                  # Indicadores Técnicos, de Volumen y Conectores de Datos
│   │   ├── polars_engine.py         # Motor Vectorizado en Rust (Sub-2.5ms con Polars DataFrames)
│   │   ├── health.py                # Engine KER (Kaufman Efficiency Ratio — Anti-Ruido y Filtro Chop)
│   │   ├── volume.py                # Volume Engine — RVOL, Order Flow Delta + CVD Divergence + Daily VWAP
│   │   ├── structure.py             # Order Blocks, FVGs, S/R + Trap Detection LAF/LBF
│   │   ├── fibonacci.py             # Retrocesos y Golden Pocket OTE (61.8% - 78.6%)
│   │   ├── liquidations.py          # Clusters de Liquidación proyectados en vivo
│   │   ├── regime.py                # Detector de Régimen de Mercado (EMA Trend + ADX Momentum)
│   │   └── tradfi_provider.py       # Proveedor TradFi MT5 — Descarga de Barras, Spreads y Configuración Tier A
│   ├── risk/                        # Gestión y Guardianes de Riesgo Institucional
│   │   ├── risk_manager.py          # RiskManager — SOP-25 (-0.65R), SOP-26 (40/40/20) & SOP-32/33 Kelly
│   │   ├── ftmo_guardian.py         # FTMO Guardian Shield — Lotes Adaptativos, Midnight Rollover y Kill-Switch (-3.5%)
│   │   └── cluster_risk_guard.py    # Cluster Risk Guard — Covarianza rodante en vivo (ρ >= 0.75) y SOP-30 Beta
│   ├── execution/                   # Ejecución Institucional en Exchanges y MetaTrader
│   │   ├── nexus.py                 # Nexus Node — Router Multi-Mercado, SOP-39 Dynamic Equity & SOP-40 Buffer
│   │   ├── account_manager.py       # AccountManager — Bóveda Multi-Tenant Cifrada AES-256 Fernet (SOP-57)
│   │   ├── bitunix_executor.py      # Conector Bitunix Futures — Dynamic Decimals, HMAC-SHA256 y Post-Only
│   │   ├── mt5_bridge.py            # Puente MetaTrader 5 — SOP-65 Dynamic FOK/IOC y SOP-66 Cierres Parciales Nativos
│   │   ├── delta_executor.py        # Fragmentador de Órdenes Iceberg
│   │   ├── omega_listener.py        # Centinela de Monitoreo y Sincronización en Vivo
│   │   └── archive/                 # Conectores históricos preservados
│   ├── workers/                     # Procesos y Demonios en Segundo Plano
│   │   ├── orchestrator.py          # SlingshotOrchestrator — Director de orquesta 24/7
│   │   ├── market_scanner.py        # Escáner Multitemporal Cripto (BNB Scalp 15m / BTC / Alts 24/7)
│   │   ├── tradfi_scanner.py        # Escáner Autónomo TradFi (Ciclo 45s, Tier A SOP-67, Gold Shield SOP-68)
│   │   ├── trade_manager.py         # Centinela de Posiciones Vivas (Early Invalidation, 50/30/20 y Purgas Huérfanas)
│   │   └── ci_cd_sentinel.py        # Centinela CI/CD Autónomo (Auditoría periódica de salud del sistema)
│   ├── backtest/                    # ═══ THE TRUTH ENGINE: Motor de Backtest SSoT ═══
│   │   ├── unified_backtest_engine.py # Motor Unificado con Paridad 1:1 SSoT en Producción
│   │   ├── data/                    # Datasets históricos binarios en formato .parquet
│   │   └── reports/                 # Reportes oficiales inmutables JSON (+94.75R Cripto y +76.98% TradFi)
│   └── tests/                       # ═══ Suite Oficial de Certificación QA (100% Passed) ═══
│       ├── test_ftmo_titanium_strategy.py           # 6 Pruebas Tier A, Poda, Cosecha 50/30/20, Cierres Parciales MT5
│       ├── test_tradfi_scanner_and_risk.py          # 15 Pruebas Scanner TradFi, Provider MT5 y Guardian FTMO
│       ├── test_multi_account_advanced_security.py  # 38 Pruebas Cifrado AES, Aislamiento, Deduplicación y Kill-Switch
│       ├── test_setup_and_portability.py            # Onboarding, live test de keys, guardado atómico
│       ├── test_post_tp3_and_trailing_invariance.py # Post-TP3 híbrido, 70% ratchet e invarianza SL
│       ├── test_risk_and_resilience_advanced.py     # Micro-buffer BE, Asymmetric Gating, KER/RVOL
│       ├── test_intelligent_limit_order_sentinel.py # Centinela de órdenes límite y purga huérfanas
│       ├── test_full_engine_autonomy_audit.py       # Autonomía, Slot Recycling y no retroceso SL
│       ├── test_live_trade_management.py            # Gestión en vivo de Stop Loss, Breathing Room y Fast BE
│       ├── test_sqlite_vault.py                     # Persistencia WAL, anti-spam y concurrencia
│       ├── test_mt5_bridge.py                       # Conexión MT5 y bloqueo de Drawdown FTMO
│       ├── test_deterministic_pipeline_isolation.py # Latencia y lot sizing sin red
│       ├── test_session_mastery.py                  # Killzones de sesión (Asia/London/NY)
│       ├── test_market_scanner_hft.py               # Watchdog OTE y order flow fallback
│       ├── test_institutional_end_to_end_pipeline_and_contracts.py # Golden Path E2E, Contratos UI y Blindaje SOP-68
│       ├── legacy/test_ftmo_security_guard_v18.py   # Suite histórica v18 preservada
│       ├── test_telegram_persistence.py             # Deduplicación y supervivencia a reinicios
│       ├── test_dynamic_sl_professional_audit.py    # Invarianza Monótona, Ratchet 1R-10R y Buffer ATR
│       ├── test_dynamic_universe_screener.py        # Rotación cuantitativa y especialización
│       ├── test_chart_and_telemetry_pipeline.py     # Reactividad de velas y Broadcast WebSocket
│       ├── test_auto_healing_and_telemetry.py       # Auto-Healing, Backoff y Heartbeat Telegram
│       ├── test_confluence_end_to_end_integrity.py  # 14 factores SMC, anti-NaN y Oro Long-Only
│       ├── test_backend_performance_and_security.py # Fast-path orjson Rust, Gzip, métricas y seguridad
│       ├── test_breathing_room_and_nexus_harmony.py # Inmunidad BE prematuro (<1.0R) y armonía SSoT
│       ├── test_institutional_execution_security.py # SOP-07, SOP-08 (20x clamp), SOP-09 y Anti-NaN
│       ├── test_cluster_risk_guard.py               # Covarianza de retornos rodantes, gating ρ>=0.75
│       ├── test_pyramiding_and_free_roll_scale_in.py# Piramidación Free-Roll y escalado seguro
│       ├── test_true_backtest_ssot_parity.py        # Paridad 1:1 Live Engine vs Backtest Engine
│       ├── test_apex_titan_smart_time_gating.py     # SOP-18 Lunes Pre-NY y micro-ventanas de precisión
│       ├── test_apex_zenith_news_and_post_only.py   # SOP-19 Interceptor macro y Post-Only Maker
│       ├── test_multi_market_ftmo_and_crypto.py     # SOP-20 Armonía Dual Cripto / FTMO MT5
│       ├── test_realtime_candlestick_formation.py   # Formación y stream en vivo de velas
│       ├── test_sop21_liquidation_invariance.py     # Invarianza de Liquidación (Caso AKE)
│       ├── test_apex_infinity_lifecycle.py          # SOP-22 Purga atómica de huérfanas
│       ├── test_sop25_sop26_mae_mfe_harvesting.py   # SOP-25 (-0.65R) y SOP-26 Cosecha Escalonada
│       ├── test_sop27_vwap_exhaustion_shield.py     # SOP-27 Daily VWAP Exhaustion Shield
│       ├── test_sop28_to_sop31_sovereign_suite.py   # Quality Gate, Session Alpha, Beta Limiter & Chop
│       ├── test_sop32_to_sop35_intelligent_lev.py   # Volatility Leverage & Alpha-Tier Kelly Sizing
│       ├── test_sop36_to_sop38_universe_harmony.py  # Curated Universe, MTF Gate & Sniper NY
│       ├── test_sop39_sop40_bitunix_dynamic_risk.py # Bitunix 2.5% Dynamic Margin & Buffer Guardrail
│       ├── test_sop41_sop42_dollar_risk_shield.py   # SOP-41 Dollar-Risk Sizing & SOP-42 Hard-Clamp
│       ├── test_ci_cd_security_gates.py             # Quality Gates CI/CD y CORS
│       ├── test_bayesian_confluence_calibration.py  # 5 Pruebas Calibración Bayesiana SMC, Prior Beta(10,10) y Microsegundos (SOP-72)
│       ├── test_hmm_regime_and_rolling_train.py     # 4 Pruebas HMM 4 Estados, Markov Transition y Hot-Reload Atómico (SOP-73)
│       ├── test_post_mortem_and_veto_suite.py       # 3 Pruebas Agente Post-Mortem NVIDIA NIM y Veto Gatekeeper (SOP-74)
│       └── legacy/                                  # Pruebas históricas preservadas
│
├── scripts/                         # ═══ HERRAMIENTAS CLI & DE DESPLIEGUE (SSoT) ═══
│   ├── verificar_sistema.bat        # Script de verificación integral en Windows/VPS (56 tests)
│   ├── run_qa_suite.py              # Ejecutor automático de suites de pruebas
│   ├── historical_fetcher.py        # Descargador oficial de Parquets históricos
│   ├── doctor.py                    # Diagnóstico de puertos, sockets y servicios
│   ├── watchdog_supervisor.py       # Monitor supervisor de procesos en segundo plano
│   └── diagnostic/                  # Scripts de telemetría y diagnósticos de conectividad
│
└── docs/                            # ═══ DOCUMENTACIÓN TÉCNICA CANÓNICA (SSoT) ═══
    ├── README.md                    # Manual general del ecosistema y especificaciones ejecutivas
    ├── SLINGSHOT_BIBLE_V51.md       # Biblia canónica maestra v51.0 (Especificación completa del sistema)
    ├── SLINGSHOT_BIBLE_V52.md       # Biblia canónica maestra v52.0 (Tri-Loop Adaptive Calibration, SOP-72 a SOP-74)
    ├── ESTRUCTURA_PROYECTO.md       # Guía de estructura, archivos y módulos (este archivo)
    └── MULTI_ACCOUNT_INSTITUTIONAL_SPEC.md # Especificación técnica de la arquitectura multi-cuenta
```

---

## 🔍 Resumen Funcional de los Módulos Clave

### 1. Motor de Confluencia & Machine Learning (`engine/core/confluence.py` & `engine/core/regime_agent.py`)
* Integra 14 factores cuantitativos basados en Smart Money Concepts (SMC), zonas OTE de Fibonacci (61.8% - 78.6%), divergencias de CVD, volumen relativo (RVOL) y el escudo de agotamiento VWAP.
* **Meta-Labeling con XGBoost / ONNX:** Inferencia neural en tiempo real que inyecta $+10$ puntos de confianza a la señal o penaliza $-5$ puntos ante contradicción estadística.
* **Agente de Régimen (SOP-63):** Modula la asignación de riesgo (0.65x a 1.30x) protegiendo el capital ante turbulencias macro o falta de tendencia.

### 2. Capa de Ejecución Dual (`engine/execution/`)
* **`nexus.py`:** Enrutador maestro multi-mercado que recibe señales validadas y distribuye órdenes a los ejecutores correspondientes según el tipo de activo (Cripto en Bitunix o TradFi en MT5).
* **`bitunix_executor.py`:** Ejecutor nativo para futuros perpetuos USDT con firma HMAC-SHA256, cálculo dinámico de precisión decimal por contrato y soporte Post-Only.
* **`mt5_bridge.py`:** Puente IPC de latencia sub-milisegundo con MetaTrader 5 de 64 bits. Implementa resolución dinámica de broker (SOP-65 para `ORDER_FILLING_FOK` / `ORDER_FILLING_IOC`), normalización de lotes al `volume_step`, y cierres parciales de volumen mediante `close_partial_position()` con `TRADE_ACTION_DEAL` (SOP-66).
* **`account_manager.py`:** Administrador multi-tenant que almacena y gestiona credenciales de API secundarias cifradas con AES-256 Fernet (SOP-57), asegurando aislamiento estricto de margen y tolerancia a fallos desacoplada.

### 3. Escáneres y Centinelas en Segundo Plano (`engine/workers/`)
* **`market_scanner.py`:** Escáner 24/7 sobre el universo de Criptomonedas (BTC, ETH, SOL, BNB, etc.) en temporalidad 15m.
* **`tradfi_scanner.py`:** Escáner TradFi ejecutado cada 45 segundos sobre activos Tier A (`XAUUSD`, `US100`, `GBPUSD`, `US30`) durante sesiones de Londres y Nueva York, con filtro anti-stacking y Slot Fortress.
* **`trade_manager.py`:** Centinela activo de posiciones vivas y órdenes pendientes. Controla el protocolo SOP-25 (invalidación a $-0.65\text{R}$ y cancelación post-TP1), la cosecha escalonada (40/40/20 en Cripto y 50/30/20 en FTMO), el Fast Breakeven y la purga atómica de órdenes huérfanas tras intervenciones manuales (SOP-59).
