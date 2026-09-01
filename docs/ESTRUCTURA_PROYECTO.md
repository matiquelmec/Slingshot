# 🏗️ Estructura del Proyecto Slingshot v33.0 Apex Olympus

> Guía de referencia oficial para la arquitectura, mantenimiento y evolución del sistema.
> **Última actualización**: Septiembre 2026 (v33.0 Apex Olympus — Multi-Market Crypto & FTMO Supreme Harmony, Selector Visual de Mercados, Protocolos SOP-07 a SOP-20, 156/156 QA Tests Passed & SSoT True Backtest Engine)

---

## 📁 Árbol de Directorios Oficial v24.0

```text
Slingshot_Trading/
├── app/                             # ═══ DELTA: Terminal Reactiva Frontend (Next.js 15) ═══
│   ├── components/
│   │   ├── radar/                   # ActiveAssetsMonitor & OpportunitiesScanner
│   │   ├── setup/                   # OnboardingModal (Asistente Visual de API Keys con Live Test)
│   │   ├── signals/                 # SignalTerminal & SignalCardItem
│   │   ├── execution/               # Panel de Monitoreo de Posiciones y Auditor de Órdenes
│   │   └── ui/                      # LatticeScanner (Stream Reactivo), PlanOperativoPanel
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
│   │   ├── confluence.py            # ConfluenceManager — Jurado de Confluencia + Asymmetric Altcoin Gating
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
│   │   └── regime.py                # Detector de Régimen de Mercado (EMA + ADX)
│   ├── risk/                        # Gestión de riesgo institucional
│   │   ├── risk_manager.py          # RiskManager v24.0 — Staged Exits 50/30/20 & Fee Absorber (+0.08%)
│   │   └── ftmo_guardian.py         # FTMO Guardian Shield — Lotes Adaptativos y Kill-Switch (-3.5%)
│   ├── execution/                   # Ejecución Institucional en Exchanges
│   │   ├── nexus.py                 # Nexus Node — Breathing Room Shield (10s), Auto-Healing y Precision
│   │   ├── bitunix_executor.py      # Conector Bitunix Futures — Dynamic Precision + Doble SHA-256
│   │   ├── mt5_bridge.py            # Puente MetaTrader 5 — Órdenes TradFi + Trailing de Posiciones MT5
│   │   └── delta_executor.py        # Fragmentador de Órdenes Iceberg (Delta 50/30/20)
│   ├── workers/                     # Procesos en segundo plano
│   │   ├── orchestrator.py          # SlingshotOrchestrator — Director de orquesta 24/7
│   │   ├── market_scanner.py        # Escáner de Oportunidades Multitemporal (14 Activos)
│   │   └── trade_manager.py         # Centinela de Posiciones Activas en Bitunix (Fast BE & Trailing)
│   └── backtest/                    # ═══ THE TRUTH ENGINE: Motor de Backtest ═══
│       ├── unified_backtest_engine.py # Motor Unificado de Backtesting con Paridad 1:1 en Producción
│       ├── data/                    # Datasets históricos binarios .parquet (51 archivos)
│       └── reports/                 # Reportes oficiales inmutables JSON
│   └── tests/                       # ═══ Suite Oficial de Certificación QA (106/106 Tests OK) ═══
│       ├── test_setup_and_portability.py            # Onboarding, live test de keys, guardado atómico
│       ├── test_post_tp3_and_trailing_invariance.py # Post-TP3 híbrido, 70% ratchet e invarianza SL
│       ├── test_risk_and_resilience_advanced.py     # Micro-buffer BE, 50/30/20, Asymmetric Gating, KER/RVOL
│       ├── test_intelligent_limit_order_sentinel.py # Centinela de órdenes límite
│       ├── test_full_engine_autonomy_audit.py       # Autonomía, Slot Recycling y no retroceso SL
│       ├── test_live_trade_management.py            # Gestión en vivo de Stop Loss, Breathing Room y Fast BE
│       ├── test_sqlite_vault.py                     # Persistencia WAL, anti-spam y concurrencia
│       ├── test_mt5_bridge.py                       # Ejecución MT5 y bloqueo de Drawdown FTMO
│       ├── test_deterministic_pipeline_isolation.py # Latencia y lot sizing sin red
│       ├── test_session_mastery.py                  # Killzones de sesión (Asia/London/NY)
│       ├── test_market_scanner_hft.py               # Watchdog OTE y order flow fallback
│       ├── test_ftmo_security_guard.py              # Guardian FTMO, Lotes GER40/GBPJPY/Oro y Dynamic Phase Sizing
│       ├── test_telegram_persistence.py             # Deduplicación y supervivencia a reinicios
│       ├── test_dynamic_sl_professional_audit.py    # Invarianza Monótona, Ratchet 1R-10R y Buffer ATR
│       ├── test_dynamic_universe_screener.py        # Rotación cuantitativa y especialización Oro 1H
│       ├── test_chart_and_telemetry_pipeline.py     # Reactividad de velas, LatticeScanner y Broadcast
│       ├── test_auto_healing_and_telemetry.py       # Auto-Healing, Backoff y Heartbeat Telegram
│       ├── test_confluence_end_to_end_integrity.py  # 14 factores SMC, anti-NaN y Oro 1H Long-Only
│       ├── test_backend_performance_and_security.py # Fast-path orjson Rust, Gzip, métricas y seguridad
│       ├── test_breathing_room_and_nexus_harmony.py # Inmunidad BE prematuro (<1.0R) y armonía SSoT
│       ├── test_institutional_execution_security_audit.py # SOP-07, SOP-08 (20x clamp), SOP-09 y Anti-NaN
│       └── test_cluster_risk_guard.py               # Covarianza de retornos rodantes, gating ρ>=0.75
├── scripts/                         # ═══ HERRAMIENTAS CLI DE PRODUCCIÓN (SSoT) ═══
│   ├── run_institutional_backtest.py# CLI Oficial de Backtesting por Símbolo / Timeframe / Cartera
│   ├── run_qa_suite.py              # Suite Oficial de Certificación QA (106/106 Tests)
│   ├── historical_fetcher.py        # Descargador oficial de Parquets históricos
│   ├── doctor.py                    # Diagnóstico y salud del sistema
│   ├── watchdog_supervisor.py       # Monitor supervisor 24/7 en segundo plano
│   └── archive/                     # 📦 28 scripts antiguos archivados
├── docs/                            # ═══ Documentación Técnica y Biblias ═══
│   ├── ESTRUCTURA_PROYECTO.md       # Guía de arquitectura oficial v26.0 (este archivo)
│   ├── SLINGSHOT_BIBLE_V25.md       # Biblia técnica oficial v26.0 Cluster Fortress
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
