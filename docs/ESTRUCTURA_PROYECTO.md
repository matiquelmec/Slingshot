# Estructura del Proyecto Slingshot v10.0.0

> Mapa oficial de directorios y módulos activos del ecosistema **Slingshot (`v10.0.0` — FSD Multi-Tenant Dual-Engine, SOP-142)**.  
> **Última actualización:** Noviembre 2026 | **Gobernanza:** [`AGENTS.md`](../AGENTS.md) | **Blueprint:** [`BLUEPRINT_2026.md`](architecture/BLUEPRINT_2026.md)

---

## Árbol de Directorios Real

```text
Slingshot_Trading/
├── src/                                  # Frontend Next.js 15 + React 19 (Feature-Sliced Design)
│   ├── app/                              # App Router, layouts, estilos globales y componentes de terminal
│   │   ├── (dashboard)/                  # Rutas: bitunix, chart, ftmo, heatmap, history, radar, signals
│   │   ├── components/                   # execution, macro, radar, setup, signals, ui
│   │   ├── store/                        # telemetryStore (Zustand 5), connection, handlers, constants
│   │   ├── types/                        # Tipos locales de UI
│   │   └── utils/                        # Utilidades de interfaz y signalLogic
│   ├── entities/                         # Modelos de dominio y esquemas Zod (signal, tenant, trade, user)
│   ├── features/                         # Slices interactivos y Server Actions protegidos (Anti-IDOR)
│   │   ├── backtest-metrics/             # Auditoría de paridad teórica vs. ejecución real (SOP-119)
│   │   ├── multi-account/                # Gestión multi-cuenta Bitunix con cifrado AES-256 Fernet
│   │   ├── order-execution/              # Despacho de órdenes con validación Zod
│   │   ├── positions-tracker/            # Seguimiento de posiciones y salud Turso DB
│   │   ├── signals-feed/                 # Feed reactivo de señales
│   │   └── system-diagnostics/           # Panel de diagnóstico L2, Funding, Monte Carlo y SOPs
│   └── shared/                           # Primitivas transversales (auth, db/Drizzle+Turso, lib, types, ui)
│
├── engine/                               # Motor Cuantitativo & Ejecución (Python 3.12 + FastAPI + Polars)
│   ├── main_router.py                    # Pipeline principal SMC -> Confluence -> Gatekeeper -> Dispatcher
│   ├── agents/                           # regime_agent.py, regime_hmm.py, post_mortem_agent.py
│   ├── aiq/                              # Orquestación NVIDIA AI-Q (agent_router, relational, semantic_memory)
│   ├── analytics/                        # Centinelas cuantitativos (L2 SOP-108, Funding SOP-109, Monte Carlo SOP-107, OB Liquidity SOP-112, Escenarios SOP-106)
│   ├── api/                              # FastAPI (main.py, config.py, auth.py, ws_manager.py, routes/, broadcaster/)
│   ├── backtest/                         # Motor de backtesting unificado y simulaciones cronológicas
│   ├── core/                             # confluence.py, memory.py (BlackBox), bayesian_confluence.py, session_manager.py, store.py, vault.py, tear_sheet.py, validator.py, maintenance.py
│   ├── data/                             # Ingesta y caché de datos históricos/mercado
│   ├── execution/                        # nexus.py, bitunix_executor.py, mt5_bridge.py, account_manager.py, omni_broker_hub.py, turso_sync.py, omega_listener.py
│   ├── indicators/                       # Indicadores SMC, CVD, liquidaciones, macro, noticias
│   ├── inference/                        # Inferencia auxiliar y utilidades
│   ├── ml/                               # inference.py (SlingshotML), train_rolling.py, train.py, drift_monitor.py, features.py
│   ├── notifications/                    # Despachadores y formateadores de alertas
│   ├── resilience/                       # Coordinadores de alta disponibilidad y failover
│   ├── risk/                             # Gestión de riesgo Dollar-Risk, Kelly, HRP
│   ├── router/                           # analyzer.py, gatekeeper.py, telegram_dispatcher.py
│   ├── strategies/                       # Estrategias SMC y Playbooks
│   ├── workers/                          # orchestrator.py, market_scanner.py, tradfi_scanner.py, trade_manager.py, asset_incubator.py, ci_cd_sentinel.py, calendar_worker.py, news_worker.py
│   └── tests/                            # Suite Pytest (529 tests recolectados, SOP-01 a SOP-142)
│
├── sidecar/                              # Ingestor HFT WebSocket en Node.js (:8080)
│   └── index.js                          # Streaming de ticks y ordenamiento L2 para activos canónicos
│
├── scripts/
│   ├── deploy/                           # Despliegue y auditoría remota WinRM en VPS (deploy_and_verify_vps.ps1, sync_and_audit_vps.ps1, inspect_service_log.ps1)
│   ├── diagnostic/                       # check_hygiene.py, inspect_real_state.py
│   └── archive/                          # Scripts históricos de exploración y herramientas
│
├── tests/unit/                           # Suite Vitest Frontend & FSD (66 tests)
├── docs/
│   ├── architecture/BLUEPRINT_2026.md    # Especificación técnica maestra y bitácora de fases
│   ├── ESTRUCTURA_PROYECTO.md            # Este mapa de estructura
│   └── knowledge/                        # Documentación de referencia de regímenes
│
├── AGENTS.md                             # Protocolo de gobernanza y reglas innegociables (Reglas 1-28)
├── README.md                             # Portada ejecutiva y guía operativa del repositorio
└── package.json                          # Scripts npm, versión 10.0.0 y dependencias Frontend
```
