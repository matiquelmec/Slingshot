# 🏗️ Estructura del Proyecto Slingshot v10.0 HFT Apex Edition

> Guía de referencia oficial para la arquitectura, mantenimiento y evolución del sistema.
> **Última actualización**: Julio 15, 2026

---

## 📁 Árbol de Directorios Actualizado

```text
Slingshot_Trading/
├── engine/                          # ═══ SIGMA: Cerebro Algorítmico (Python/FastAPI) ═══
│   ├── main_router.py               # Pipeline principal: Orquesta SMC → Confluence → Gatekeeper
│   ├── api/                         # Capa de comunicación
│   │   ├── main.py                  # FastAPI entry point + lifespan
│   │   ├── config.py                # Settings centralizadas (.env)
│   │   ├── ws_manager.py            # WebSocket broadcaster al frontend
│   │   ├── advisor.py               # Motor IA (Ollama/Gemma-3) + Fallback Determinístico v10.0
│   │   ├── advisor_bridge.py        # Puente HTTP para inferencia IA
│   │   ├── auth.py                  # Autenticación JWT
│   │   ├── signal_handler.py        # Handler de señales HTTP/WS
│   │   ├── registry.py              # Registro de activos monitoreados
│   │   ├── json_utils.py            # Sanitización JSON (numpy → python)
│   │   └── broadcaster/             # Pipeline de broadcast asíncrono
│   ├── core/                        # Núcleo del motor
│   │   ├── confluence.py            # ConfluenceManager v10.0 — Parámetros unificados + GP + Liquidaciones
│   │   ├── store.py                 # MemoryStore — Estado persistente por activo
│   │   ├── session_manager.py       # Gestión de sesiones (Asia/London/NY)
│   │   ├── memory.py                # BlackBox Memory — Registro e historial de trades
│   │   ├── validator.py             # AI Validator Agent — Auditoría narrativa
│   │   └── logger.py                # Logger institucional
│   ├── router/                      # Pipeline de señales
│   │   ├── analyzer.py              # MarketAnalyzer — Procesamiento de indicadores
│   │   ├── gatekeeper.py            # SignalGatekeeper v10.0 — Motor Bayesiano + Sovereign Bypass
│   │   ├── dispatcher.py            # Despacho de señales aprobadas
│   │   └── processors.py            # Procesadores + Slow Path (Volume Profile, Trap Detection)
│   ├── strategies/                  # Lógica táctica
│   │   ├── smc.py                   # SMCInstitutionalStrategy v10.0 (Tiers A/B con Convicción Diferenciada)
│   │   └── larry_williams.py        # Estrategia auxiliar de Larry Williams
│   ├── indicators/                  # Análisis técnico e institucional
│   │   ├── structure.py             # Order Blocks, FVGs, S/R + Trap Detection LAF/LBF
│   │   ├── fibonacci.py             # Retrocesos, Golden Pocket (Evaluación Always-On)
│   │   ├── volume.py                # RVOL, Absorción + Volume Profile POC/VAH/VAL
│   │   ├── liquidity.py             # Muros de Liquidez (Orderbook)
│   │   ├── liquidations.py          # Clusters de Liquidación proyectados en vivo
│   │   ├── regime.py                # Detector de Régimen de Mercado (EMA + ADX)
│   │   ├── htf_analyzer.py          # Análisis HTF (1M/1W/1D)
│   │   ├── macro.py                 # Indicadores Macro (DXY, VIX)
│   │   ├── onchain_provider.py      # Métricas On-Chain (OI, Funding)
│   │   ├── ghost_data.py            # Ghost Sentinel (Macro Bias Global)
│   │   ├── market_analyzer.py       # Análisis de mercado auxiliar
│   │   └── data_utils.py            # Conector de datos de Binance + Inserción HFT Node.js
│   ├── risk/                        # Gestión de riesgo
│   │   └── risk_manager.py          # RiskManager v10.0 — Stop Hunt Shield + Guardarraíles Dinámicos (1.20% / 0.45%)
│   ├── execution/                   # Ejecución de órdenes
│   │   ├── nexus.py                 # Nexus Bridge — Exchanges + Averaging Up Yosh
│   │   ├── binance_executor.py      # Executor Binance Futures
│   │   ├── bitunix_executor.py      # Executor Bitunix con firmas HFT y Node.js Integration
│   │   ├── delta_executor.py        # Executor genérico
│   │   └── omega_listener.py        # Listener de posiciones abiertas
│   ├── ml/                          # Machine Learning
│   │   ├── inference.py             # XGBoost predictor
│   │   ├── features.py              # Feature engineering
│   │   ├── train.py                 # Entrenamiento del modelo
│   │   ├── drift_monitor.py         # Monitor de drift del modelo
│   │   └── models/                  # Modelos serializados (.json)
│   ├── inference/                   # Inferencia de patrones
│   │   ├── volume_pattern.py        # VolumePatternScheduler
│   │   └── bridge_loader.py         # Cargador de modelos
│   ├── workers/                     # Procesos en background
│   │   ├── orchestrator.py          # Orquestador principal de sensores
│   │   ├── market_scanner.py        # Scanner de oportunidades + OTE Watchdog (Radar)
│   │   ├── trade_manager.py         # Administrador de posiciones reales en Bitunix
│   │   ├── news_worker.py           # Scraper de noticias
│   │   └── calendar_worker.py       # Calendario económico
│   ├── notifications/               # Sistema de alertas
│   │   ├── filter.py                # Filtro anti-spam de notificaciones
│   │   └── telegram.py              # Bot de Telegram
│   ├── backtest/                    # ═══ Ecosistema de Backtesting v10.0 (Fidelity Engine) ═══
│   │   ├── data/                    # Datasets parquet históricos de 90 días unificados
│   │   ├── reports/                 # Reportes JSON autogenerados con timestamp
│   │   ├── replay_engine.py         # ReplayEngine v10.0 (Event-Driven Async)
│   │   ├── fast_audit.py            # Auditoría rápida de profit con ATR real (True Range EWM 14)
│   │   ├── multi_asset.py           # Simulación de portafolio multi-activo
│   │   ├── multi_asset_15m.py       # Simulación de 15m multi-activo
│   │   └── stress_audit.py          # Evaluación de precisión del Gatekeeper (asíncrono)
│   ├── tests/                       # ═══ Tests de Integridad (23 tests verificados) ═══
│   │   ├── test_engine.py           # Test del motor principal
│   │   ├── test_pipeline.py         # Test del pipeline completo
│   │   ├── test_integration_pipeline.py
│   │   ├── test_confluence_unit.py  # Test unitario del ConfluenceManager
│   │   ├── test_router_smoke.py     # Smoke test del enrutador
│   │   ├── test_signal.py           # Test de señales
│   │   ├── test_gatekeeper_bayes.py # Test del motor bayesiano
│   │   ├── test_gatekeeping_live.py # Test live del gatekeeper
│   │   ├── test_obs.py              # Test de Order Blocks
│   │   ├── test_debug_ob.py         # Debug de OBs
│   │   ├── test_htf_analyzer.py     # Test de análisis temporal superior
│   │   ├── test_regime.py           # Test de régimen de mercado
│   │   ├── test_regime_stabilization.py # Test de estabilidad de régimen
│   │   ├── test_risk_calculations.py # Test del RiskManager y SL/Apalancamiento
│   │   ├── test_router_liquidations.py # Test de liquidaciones en el router
│   │   ├── test_liquidations_v2.py  # Test liquidaciones v2
│   │   ├── test_fetcher.py          # Test de descarga de datos
│   │   ├── test_calendar.py         # Test de calendario
│   │   ├── test_llm.py              # Test de Ollama local
│   │   ├── test_macro_tickers.py    # Test de tickers macro
│   │   ├── test_nexus_apex.py       # Test del Nexus Node
│   │   ├── test_larry_williams.py   # Test de la estrategia Larry Williams
│   │   ├── test_bitunix_executor_safety.py # Test del conector de Bitunix
│   │   ├── test_advisor_gatekeeping.py # Test de veto por LLM
|   │   ├── test_ws.py               # Test de WebSocket en Python
|   │   ├── test_ws.js               # Test de WebSocket en JavaScript
│   │   └── data/                    # Datasets para tests (.parquet)
│   └── tools/                       # Herramientas de diagnóstico auxiliar
│       ├── integrity_audit.py       # Auditoría de integridad de datos y sistemas
│       └── audit_data_ingestion.py  # Auditoría de ingesta de datos
├── app/                             # ═══ DELTA: Terminal UI (Next.js 15) ═══
│   ├── layout.tsx                   # Layout principal
│   ├── globals.css                  # Estilos globales
│   ├── (dashboard)/                 # Páginas del dashboard
│   ├── components/                  # Componentes React (TradingChart, Radar, Value Area Overlay)
│   ├── store/                       # TelemetryStore + IndicatorsStore (Zustand 5)
│   ├── types/                       # TypeScript interfaces
│   └── utils/                       # Utilidades del frontend
├── scripts/                         # DevOps y herramientas de sistema
│   ├── deploy/                      # Dockerfile + systemd service
│   ├── debug_connection.py          # Diagnóstico de red (REST+WS+Bitunix)
│   ├── doctor.py                    # Diagnóstico del sistema
│   ├── historical_fetcher.py        # Descarga de datos históricos
│   ├── latency_benchmark.py         # Benchmark de latencia
│   ├── latency_breakdown.py         # Desglose de latencia por componente
│   ├── optimize_os.ps1              # Optimizaciones de Windows
│   ├── vault_cleanup.ps1            # Limpieza de caché
│   └── diagnostico_motor.py         # Herramienta de diagnóstico de motor
└── scratch/                         # Carpeta temporal (gitignored - 100% LIMPIA)
```

---

## 🔌 slingshot-hft-sidecar (Antigravity Custom Skill)

El módulo de alto rendimiento corre de forma aislada en la carpeta de personalización global:
`C:\Users\Matías Riquelme\.gemini\config\skills\slingshot_hft_sidecar/`

### Componentes:
*   `SKILL.md`: Documento de definición y control de la Skill.
*   `scripts/package.json`: Dependencias aisladas del Sidecar.
*   `scripts/index.js`: Cliente WebSocket de 20 activos + Execution Bridge (Bitunix HMAC-SHA256).
