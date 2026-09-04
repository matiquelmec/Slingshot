# 🏗️ Estructura del Proyecto Slingshot v42.2 APEX TITAN COMPOUND

> Guía de referencia oficial para la arquitectura, mantenimiento y evolución del sistema.
> **Última actualización**: Septiembre 2026 (v42.2 APEX TITAN COMPOUND — Arquitectura Dual Bitunix 2.5% vs FTMO 0.75%, Protocolos SOP-01 a SOP-42, 216/216 QA Tests Passed & SSoT True Backtest Engine).

---

## 📁 Árbol de Directorios Oficial v42.2

```text
Slingshot_Trading/
├── app/                             # ═══ DELTA: Terminal Reactiva Frontend (Next.js 15) ═══
│   ├── (dashboard)/
│   │   ├── layout.tsx               # Navegación Dual: Sidebar Desktop (w-64) + Mobile Topbar, Drawer y Dock Inferior
│   │   ├── page.tsx                 # Overview con Selector Segmentado Móvil (SCANNER / DIAGNÓSTICO / TÁCTICA)
│   │   ├── chart/                   # Terminal de Gráficos con timeframes táctiles y leyendas colapsables
│   │   └── ftmo/                    # Terminal Cuantitativa Prop Firm adaptada a rejilla responsiva
│   ├── components/
│   │   ├── radar/                   # ActiveAssetsMonitor & OpportunitiesScanner
│   │   ├── setup/                   # OnboardingModal (Asistente Visual de API Keys con Live Test)
│   │   ├── signals/                 # SignalTerminal & SignalCardItem
│   │   ├── execution/               # Panel de Monitoreo de Posiciones y Auditor de Órdenes
│   │   └── ui/                      # LatticeScanner (Tarjetas móviles / Grid desktop tabular), PlanOperativoPanel
│   ├── store/                       # TelemetryStore (Zustand 5 State Management)
│   └── utils/                       # Formatters, ftmoSpecs.ts & Signal LifeCycle Logic
├── engine/                          # ═══ SIGMA: Cerebro Algorítmico (Python 3.12 / Rust) ═══
│   ├── main_router.py               # Pipeline principal: Orquesta SMC → Confluence → Gatekeeper
│   ├── api/                         # Capa de comunicación REST / WebSockets
│   │   ├── main.py                  # FastAPI entry point con lifespan (Auto-start de Workers)
│   │   ├── setup.py                 # SetupRouter — Endpoints de Onboarding, Live Test y Guardado Atómico
│   │   ├── config.py                # Settings centralizadas (.env) + Watchlist Curada + RVOL/KER
│   │   ├── ws_manager.py            # WebSocket broadcaster al frontend
│   │   └── registry.py              # SymbolBroadcaster y Pulso Global de Telemetría
│   ├── core/                        # Núcleo del motor y Persistencia
│   │   ├── vault.py                 # SQLite WAL Vault — Persistencia Transaccional ACID (SSoT)
│   │   ├── confluence.py            # ConfluenceManager — Jurado de Confluencia + VWAP Shield + MTF Gate
│   │   ├── store.py                 # MemoryStore — Estado persistente por activo y buffers
│   │   ├── session_manager.py       # Gestión de sesiones institucionales (Asia/London/NY Open)
│   │   └── validator.py             # AI Validator Agent — Auditoría narrativa
│   ├── router/                      # Pipeline de señales y Despacho
│   │   ├── analyzer.py              # MarketAnalyzer — LRU Cache de 200 ítems + SMC Overlays
│   │   ├── gatekeeper.py            # SignalGatekeeper — Motor Bayesiano + Sovereign Bypass
│   │   └── telegram_dispatcher.py   # Telegram Dispatcher — Multi-Destinatario (Privado/Comunidad), SQLite WAL (30m / 3% drift) y 1-Click MT5
│   ├── strategies/                  # Lógica táctica
│   │   └── smc.py                   # SMCInstitutionalStrategy (Tiers A/B con Entrada Límite OTE)
│   ├── indicators/                  # Indicadores Técnicos e Institucionales
│   │   ├── polars_engine.py         # Motor Vectorizado en Rust (Sub-2.5ms con Polars)
│   │   ├── health.py                # Engine KER (Kaufman Efficiency Ratio — Anti-Ruido)
│   │   ├── volume.py                # Volume Engine — RVOL, Order Flow Delta + CVD Divergence + VWAP
│   │   ├── structure.py             # Order Blocks, FVGs, S/R + Trap Detection LAF/LBF
│   │   ├── fibonacci.py             # Retrocesos, Golden Pocket OTE (61.8% - 78.6%)
│   │   ├── liquidations.py          # Clusters de Liquidación proyectados en vivo
│   │   └── regime.py                # Detector de Régimen de Mercado (EMA + ADX)
│   ├── risk/                        # Gestión de riesgo institucional
│   │   ├── risk_manager.py          # RiskManager v42.0 — SOP-25 (-0.65R), SOP-26 (40/40/20) & SOP-32/33
│   │   ├── ftmo_guardian.py         # FTMO Guardian Shield — Lotes Adaptativos y Kill-Switch (-3.5%)
│   │   └── cluster_risk_guard.py    # Cluster Risk Guard — Covarianza en vivo (ρ >= 0.75) y SOP-30
│   ├── execution/                   # Ejecución Institucional en Exchanges
│   │   ├── nexus.py                 # Nexus Node — SOP-39 Dynamic Equity Margin 2.5% & SOP-40 Buffer
│   │   ├── bitunix_executor.py      # Conector Bitunix Futures — Dynamic Precision + Doble SHA-256
│   │   ├── mt5_bridge.py            # Puente MetaTrader 5 — Órdenes TradFi + Trailing de Posiciones MT5
│   │   ├── delta_executor.py        # Fragmentador de Órdenes Iceberg (Delta 40/40/20)
│   │   ├── omega_listener.py        # Centinela de Monitoreo y Sincronización en Vivo
│   │   └── archive/                 # 📦 Conectores inactivos preservados (binance_executor.py)
│   ├── workers/                     # Procesos en segundo plano
│   │   ├── orchestrator.py          # SlingshotOrchestrator — Director de orquesta 24/7
│   │   ├── market_scanner.py        # Escáner Multitemporal Curado (BNB Scalp 15m / PAXG Swing 1H)
│   │   ├── trade_manager.py         # Centinela de Posiciones Activas (Early Invalidation & Trailing)
│   │   └── ci_cd_sentinel.py        # Centinela CI/CD Autónomo (Task Scheduler 5m, Quality Gate 216 tests y auto-pull)
│   ├── backtest/                    # ═══ THE TRUTH ENGINE: Motor de Backtest ═══
│   │   ├── unified_backtest_engine.py # Motor Unificado con Paridad 1:1 SSoT en Producción
│   │   ├── data/                    # Datasets históricos binarios .parquet (107 archivos)
│   │   └── reports/                 # Reportes oficiales inmutables JSON (+72.25R, PF 1.43)
│   └── tests/                       # ═══ Suite Oficial de Certificación QA (216/216 Tests OK) ═══
│       ├── test_setup_and_portability.py            # Onboarding, live test de keys, guardado atómico
│       ├── test_post_tp3_and_trailing_invariance.py # Post-TP3 híbrido, 70% ratchet e invarianza SL
│       ├── test_risk_and_resilience_advanced.py     # Micro-buffer BE, Asymmetric Gating, KER/RVOL
│       ├── test_intelligent_limit_order_sentinel.py # Centinela de órdenes límite
│       ├── test_full_engine_autonomy_audit.py       # Autonomía, Slot Recycling y no retroceso SL
│       ├── test_live_trade_management.py            # Gestión en vivo de Stop Loss, Breathing Room y Fast BE
│       ├── test_sqlite_vault.py                     # Persistencia WAL, anti-spam y concurrencia
│       ├── test_mt5_bridge.py                       # Ejecución MT5 y bloqueo de Drawdown FTMO
│       ├── test_deterministic_pipeline_isolation.py # Latencia y lot sizing sin red
│       ├── test_session_mastery.py                  # Killzones de sesión (Asia/London/NY)
│       ├── test_market_scanner_hft.py               # Watchdog OTE y order flow fallback
│       ├── test_ftmo_security_guard.py              # Guardian FTMO, Lotes GER40/GBPJPY/Oro
│       ├── test_telegram_persistence.py             # Deduplicación y supervivencia a reinicios
│       ├── test_dynamic_sl_professional_audit.py    # Invarianza Monótona, Ratchet 1R-10R y Buffer ATR
│       ├── test_dynamic_universe_screener.py        # Rotación cuantitativa y especialización Oro 1H
│       ├── test_chart_and_telemetry_pipeline.py     # Reactividad de velas, LatticeScanner y Broadcast
│       ├── test_auto_healing_and_telemetry.py       # Auto-Healing, Backoff y Heartbeat Telegram
│       ├── test_confluence_end_to_end_integrity.py  # 14 factores SMC, anti-NaN y Oro 1H Long-Only
│       ├── test_backend_performance_and_security.py # Fast-path orjson Rust, Gzip, métricas y seguridad
│       ├── test_breathing_room_and_nexus_harmony.py # Inmunidad BE prematuro (<1.0R) y armonía SSoT
│       ├── test_institutional_execution_security_audit.py # SOP-07, SOP-08 (20x clamp), SOP-09 y Anti-NaN
│       ├── test_cluster_risk_guard.py               # Covarianza de retornos rodantes, gating ρ>=0.75
│       ├── test_pyramiding_and_free_roll_scale_in.py# Piramidación Free-Roll y escalado seguro
│       ├── test_true_backtest_ssot_parity.py        # Paridad 1:1 Live Engine vs Backtest Engine
│       ├── test_apex_titan_smart_time_gating.py     # SOP-18 Lunes Pre-NY y micro-ventanas de precisión
│       ├── test_apex_zenith_news_and_post_only.py   # SOP-19 Interceptor macro y Post-Only Maker
│       ├── test_multi_market_ftmo_and_crypto_harmony.py # SOP-20 Armonía Dual Cripto / FTMO MT5
│       ├── test_realtime_candlestick_formation_and_stream.py # Formación y stream en vivo de velas
│       ├── test_sop21_liquidation_invariance_and_precision.py # Invarianza de Liquidación (Caso AKE)
│       ├── test_apex_infinity_lifecycle_and_orphan_purge.py # SOP-22 Purga atómica de huérfanas
│       ├── test_sop25_sop26_mae_mfe_harvesting.py   # SOP-25 (-0.65R) y SOP-26 (40/40/20)
│       ├── test_sop27_vwap_exhaustion_shield.py     # SOP-27 Daily VWAP Exhaustion Shield
│       ├── test_sop28_to_sop31_sovereign_suite.py   # Quality Gate, Session Alpha, Beta Limiter & Chop Veto
│       ├── test_sop32_to_sop35_intelligent_leverage.py # Volatility Leverage & Alpha-Tier Kelly Sizing
│       ├── test_sop36_to_sop38_universe_and_fractal_harmony.py # Curated Universe, MTF Gate & Sniper NY
│       ├── test_sop39_sop40_bitunix_dynamic_25pct_risk.py # Bitunix 2.5% Dynamic Margin & Buffer Guardrail
│       ├── test_sop41_sop42_dollar_risk_shield.py   # SOP-41 Pure Dollar-Risk Sizing & SOP-42 Pre-Flight Hard-Clamp
│       ├── test_multi_account_dispatcher.py         # Arquitectura Multi-Cuentas Bitunix (Master Dispatcher)
│       ├── test_ci_cd_security_gates.py             # Quality Gates CI/CD (SOP-08, SOP-41, Zero Balance y CORS)
│       └── legacy/                      # 📦 44 pruebas históricas preservadas (v5 a v17)
├── scripts/                         # ═══ HERRAMIENTAS CLI DE PRODUCCIÓN (SSoT) ═══
│   ├── run_qa_suite.py              # Suite Oficial de Certificación QA (216/216 Tests)
│   ├── historical_fetcher.py        # Descargador oficial de Parquets históricos
│   ├── doctor.py                    # Diagnóstico y salud del sistema
│   ├── watchdog_supervisor.py       # Monitor supervisor 24/7 en segundo plano
│   └── archive/                     # 📦 Bóveda de archivos históricos
│       ├── explorations/            # 30 scripts de investigación y simulación
│       └── tools/                   # Herramientas de diagnóstico tempranas
├── docs/                            # ═══ Documentación Técnica y Biblias ═══
│   ├── ESTRUCTURA_PROYECTO.md       # Guía de arquitectura oficial v42.2 (este archivo)
│   ├── SLINGSHOT_BIBLE_V42.md       # Biblia técnica canónica oficial v42.2 APEX TITAN COMPOUND
│   ├── archive/                     # 📦 16 versiones históricas archivadas (v10 a v33)
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
2. **Protocolo SOP-08 & SOP-32 (Invarianza y Apalancamiento Adaptativo):**
   * Los Stop Loss nunca pueden retroceder o empeorar.
   * El apalancamiento se calcula de forma inversa a la volatilidad del activo ($0.20 / \text{dist}$), garantizando que la liquidación jamás quede cerca del Stop Loss.
3. **Protocolo SOP-25 & SOP-26 (Malla de Salidas Institucional):**
   * Invalidación temprana a $-0.65\text{R}$ (corta pérdidas prematuramente).
   * Cosecha del 40% a +1.2R (SL a Breakeven), 40% a +2.0R (+1.0R en verde) y 20% Runner a +3.5R.
4. **Protocolo SOP-39 & SOP-40 (Gestión de Capital en Bitunix):**
   * Riesgo real dinámico del 2.5% por operación con interés compuesto automático.
   * Mínimo 50% de margen libre garantizado antes de abrir cada posición.
5. **Protocolo SOP-41 & SOP-42 (Pure Dollar-Risk & Hard-Clamp):**
   * Cálculo matemático exacto de cantidad según distancia al Stop Loss.
   * Circuit Breaker atómico con política fail-closed que impide abrir órdenes si no hay balance verificado.
6. **Centinela Autónomo CI/CD & Certificación Continua:**
   * Supervisor perpetuo cada 5 minutos en el VPS (`ci_cd_sentinel.py`).
   * Antes de cualquier despliegue o commit en producción, se ejecuta obligatoriamente:
     ```powershell
     .venv\Scripts\python scripts/run_qa_suite.py
     ```
     Verificando la aprobación del **100% de las 216 pruebas unitarias**.
