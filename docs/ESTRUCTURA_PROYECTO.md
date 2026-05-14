# 🏗️ Estructura del Proyecto Slingshot v12.1 Apex Sovereign

> Guía de referencia oficial para la arquitectura, mantenimiento y evolución del sistema.
> **Última actualización**: Mayo 14, 2026

---

## 📁 Árbol de Directorios

```text
Slingshot_Trading/
├── engine/                          # ═══ SIGMA: Cerebro Algorítmico (Python/FastAPI) ═══
│   ├── main_router.py               # Pipeline principal: Orquesta SMC → Confluence → Gatekeeper
│   ├── api/                         # Capa de comunicación
│   │   ├── main.py                  # FastAPI entry point + lifespan
│   │   ├── config.py                # Settings centralizadas (.env)
│   │   ├── ws_manager.py            # WebSocket broadcaster al frontend
│   │   ├── advisor.py               # Motor IA (Ollama/Qwen-3)
│   │   ├── advisor_bridge.py        # Puente HTTP para inferencia IA
│   │   ├── auth.py                  # Autenticación JWT
│   │   ├── signal_handler.py        # Handler de señales HTTP/WS
│   │   ├── registry.py              # Registro de activos monitoreados
│   │   ├── json_utils.py            # Sanitización JSON (numpy → python)
│   │   └── broadcaster/             # Pipeline de broadcast asíncrono
│   ├── core/                        # Núcleo del motor
│   │   ├── confluence.py            # ConfluenceManager v12.0 — Jurado Neural (13 factores)
│   │   ├── store.py                 # MemoryStore — Estado persistente por activo
│   │   ├── session_manager.py       # Gestión de sesiones (Asia/London/NY)
│   │   └── logger.py                # Logger institucional
│   ├── router/                      # Pipeline de señales
│   │   ├── analyzer.py              # MarketAnalyzer — Procesamiento de indicadores
│   │   ├── gatekeeper.py            # SignalGatekeeper v12.0 — 8 filtros + Sovereign Bypass
│   │   ├── dispatcher.py            # Despacho de señales aprobadas
│   │   └── processors.py            # Procesadores auxiliares de datos
│   ├── strategies/                  # Lógica táctica
│   │   └── smc.py                   # SMCInstitutionalStrategy v12.0 (OB+Sweep/Retest+FVG)
│   ├── indicators/                  # Análisis técnico e institucional
│   │   ├── structure.py             # Order Blocks, FVGs, Soporte/Resistencia (v12.1)
│   │   ├── fibonacci.py             # Retrocesos, Golden Pocket, OTE
│   │   ├── volume.py                # RVOL, Absorción, Huella Institucional
│   │   ├── liquidity.py             # Muros de Liquidez (Orderbook)
│   │   ├── liquidations.py          # Clusters de Liquidación proyectados
│   │   ├── regime.py                # Detector de Régimen de Mercado
│   │   ├── htf_analyzer.py          # Análisis HTF (1M/1W/1D)
│   │   ├── macro.py                 # Indicadores Macro (DXY, VIX)
│   │   ├── onchain_provider.py      # Métricas On-Chain (OI, Funding)
│   │   ├── ghost_data.py            # Ghost Sentinel (Macro Bias Global)
│   │   ├── market_analyzer.py       # Análisis de mercado auxiliar
│   │   └── data_utils.py            # Utilidades de datos
│   ├── risk/                        # Gestión de riesgo
│   │   └── risk_manager.py          # RiskManager v11.1 — SIGMA Tuning + SL/TP Estructural
│   ├── execution/                   # Ejecución de órdenes
│   │   ├── nexus.py                 # Nexus Bridge — Puente a exchanges
│   │   ├── binance_executor.py      # Executor Binance Futures
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
│   │   ├── news_worker.py           # Scraper de noticias
│   │   └── calendar_worker.py       # Calendario económico
│   ├── notifications/               # Sistema de alertas
│   │   ├── filter.py                # Filtro anti-spam de notificaciones
│   │   └── telegram.py              # Bot de Telegram
│   ├── backtest/                    # Motor de backtesting
│   │   └── replay_engine.py         # ReplayEngine v11.1.2 (Event-Driven)
│   ├── tests/                       # Tests de integridad (17 tests)
│   │   ├── test_engine.py           # Test del motor principal
│   │   ├── test_pipeline.py         # Test del pipeline completo
│   │   ├── test_integration_pipeline.py
│   │   ├── test_confluence_unit.py  # Test unitario de confluencia
│   │   ├── test_router_smoke.py     # Smoke test del router
│   │   ├── test_signal.py           # Test de señales
│   │   ├── test_gatekeeping_live.py # Test live del gatekeeper
│   │   ├── test_obs.py              # Test de Order Blocks
│   │   ├── test_debug_ob.py         # Debug de OBs
│   │   ├── test_htf_analyzer.py     # Test HTF
│   │   ├── test_regime.py           # Test de régimen
│   │   ├── test_liquidations_v2.py  # Test liquidaciones v2
│   │   ├── test_fetcher.py          # Test de fetcher
│   │   ├── test_calendar.py         # Test calendario
│   │   ├── test_llm.py              # Test del LLM
│   │   ├── test_macro_tickers.py    # Test tickers macro
│   │   ├── test_nexus_apex.py       # Test Nexus
│   │   ├── data/                    # Datasets para tests (.parquet)
│   │   └── legacy/                  # Tests de versiones antiguas
│   ├── tools/                       # Herramientas de auditoría
│   │   ├── fast_profit_audit.py     # Auditoría rápida de rentabilidad
│   │   ├── find_gold.py             # Buscador de setups en XAUUSD
│   │   ├── integrity_audit.py       # Auditoría de integridad de datos
│   │   ├── audit_numbers_v10.py     # Auditoría numérica v10
│   │   └── multi_asset_backtest.py  # Backtest multi-activo
│   └── data/                        # Estado de sesión (runtime)
│       ├── session_state_*.json     # Estado por activo (gitignored)
│       ├── macro_state.json         # Estado macro global
│       ├── economic_calendar.json   # Calendario económico cache
│       └── ai_cache.json            # Cache del advisor IA
│
├── app/                             # ═══ DELTA: Terminal UI (Next.js 15) ═══
│   ├── layout.tsx                   # Layout principal
│   ├── globals.css                  # Estilos globales
│   ├── (dashboard)/                 # Páginas del dashboard
│   ├── components/                  # Componentes React (Charts, Radar)
│   ├── store/                       # TelemetryStore (Zustand 5)
│   ├── types/                       # TypeScript interfaces
│   └── utils/                       # Utilidades del frontend
│
├── data/                            # Dataset maestro
│   └── btcusdt_15m_1YEAR.parquet    # 1 año de data BTC 15m
│
├── docs/                            # Documentación técnica
│   ├── ESTRUCTURA_PROYECTO.md       # ← Este archivo
│   ├── SLINGSHOT_BIBLE_V10.md       # Especificación técnica (Fuente de Verdad)
│   ├── AUDIT_PLAN_V11.md            # Plan de auditoría vigente
│   ├── TELEMETRY_RESILIENCE_V11.md  # Documentación de resiliencia
│   ├── knowledge/                   # Base de conocimientos SMC/Wyckoff
│   └── archive/                     # Documentos de versiones anteriores
│
├── scripts/                         # DevOps y herramientas de sistema
│   ├── deploy/                      # Dockerfile + systemd service
│   │   ├── Dockerfile
│   │   └── slingshot.service
│   ├── debug_connection.py          # Diagnóstico de red (REST+WS+Bitunix)
│   ├── doctor.py                    # Diagnóstico del sistema
│   ├── historical_fetcher.py        # Descarga de datos históricos
│   ├── latency_benchmark.py         # Benchmark de latencia
│   ├── latency_breakdown.py         # Desglose de latencia por componente
│   ├── optimize_os.ps1              # Optimizaciones de Windows
│   └── vault_cleanup.ps1            # Limpieza de caché
│
├── scratch/                         # Diagnósticos puntuales (gitignored)
│   ├── scratch_xag_audit.py         # Auditoría profunda XAGUSDT
│   ├── audit_xag_funding.py         # Verificación de funding XAG
│   ├── test_bitunix_depth.py        # Test de orderbook Bitunix
│   └── test_bitunix_ticker.py       # Test de ticker Bitunix
│
└── tmp/                             # Logs y caché temporal (gitignored)
    ├── data/                        # Datos de sesión temporales
    └── logs/                        # Logs del sistema
```

---

## 📜 Reglas de Arquitectura

### 1. Ubicación de Archivos
| Tipo de archivo | Ubicación correcta | Regla |
|---|---|---|
| Script de diagnóstico temporal | `scratch/` | Gitignored. No commitear. |
| Herramienta de auditoría reutilizable | `engine/tools/` | Commiteado. Debe funcionar sin errores. |
| Script de infraestructura/DevOps | `scripts/` | Commiteado. Herramientas de sistema. |
| Test de integridad del motor | `engine/tests/` | Commiteado. Se ejecutan con pytest. |
| Documentación técnica vigente | `docs/` | Commiteado. Siempre actualizada. |
| Documentación obsoleta | `docs/archive/` | Referencia histórica solamente. |

### 2. Reglas de SMC (v12.1)
- Los **Order Blocks** se invalidan SOLO cuando el precio **cierra** fuera del rango (no por mechas ni por regla del 50%)
- Los setups válidos requieren: **OB + (Sweep O Retest) + FVG**
- El **Sovereign Bypass** permite ignorar el Veto Fractal si `confluence_score >= 95%`
- El **Apex Override** bonifica señales con `absorption_score >= 90%` (+20 puntos)

### 3. Logging
Formato institucional obligatorio: `[MODULO] Mensaje`
```
[GATEKEEPER] [FRACTAL_VETO] BTCUSDT SHORT bloqueado
[CONFLUENCE] Asset: XAGUSDT | Score: 82% (Multiplier: 1.0)
[NEXUS] Orden ejecutada: LONG BTCUSDT @ 107,250
```
