# 🎯 PROJECT: SLINGSHOT — BLUEPRINT MAESTRO v2.0
## "El cómputo compartido es la única forma de democratizar el análisis institucional."
> **Versión:** 2.0  |  **Fecha:** 2026-03-04  |  **Estado:** ACTIVO ✅
> *Actualizado desde Blueprint 1.0 (2026-02-20) — Arquitectura refactorizada para escala multi-usuario*

---

## 🔬 ANÁLISIS FORENSE: CRIPTODAMUS (EL PASADO — Punto de Partida)

### Stack original que se reemplazó
| Capa | Tecnología | Motivo de Reemplazo |
|------|-----------|---------------------|
| Frontend | React + Vite + TypeScript | Migrado a Next.js 15 (SSR, App Router) |
| Backend | Node.js + Express | Migrado a Python + FastAPI (ML nativo) |
| ML | TensorFlow.js (Node) | Migrado a XGBoost + ONNX (5-10x más rápido) |
| DB | Supabase PostgreSQL | Mantenido — se expande para multi-tenancy |
| Streams | Binance WS | Mantenido — refactorizado a Workers autónomos |

### 💀 Problemas resueltos en v1 / Nuevos identificados en v2

**Resueltos en Slingshot Gen 1:**
- ✅ TF.js eliminado → ONNX Runtime con XGBoost
- ✅ Monolito Express eliminado → Python FastAPI + módulos independientes
- ✅ Drift Monitor PSI+KS implementado (supera el blueprint original)
- ✅ Risk Manager geográfico con Structural SL/TP (supera el blueprint original)
- ✅ Confluence Scoring ponderado (0-100) con anti-temporal-leak
- ✅ KillZone + SessionManager completo

**Deuda técnica identificada para v2:**
1. **Arquitectura compute-per-connection** — Con N usuarios viendo BTCUSDT, se ejecutan N veces el mismo pipeline. El sistema colapsa antes del usuario 20.
2. **Sin autenticación** — WebSocket abierto a cualquier cliente.
3. **Sin multi-tenancy** — No existe concepto de usuario, watchlist o suscripción.
4. **Señales efímeras** — Viven en LocalStorage del browser. Si el servidor reinicia, se pierden.
5. **Sin contrato de módulos** — Las estrategias usan dicts sin tipado. Errores silenciosos en runtime.
6. **Sin backtesting integrado** — Las estrategias se despliegan sin validación histórica ciega.

---

## 🎯 SLINGSHOT 2.0: EL PARADIGMA MULTI-USUARIO

### Filosofía de Diseño: "Compute Once, Serve Thousands"
La señal de trading para BTCUSDT/15m es **la misma para todos los usuarios**. No tiene sentido calcularla N veces para N usuarios. Se calcula una vez y se distribuye mediante fan-out.

### Pipeline de Análisis (sin cambios desde v1 — funciona bien):
1. **Nivel 0 (Tiempo)**: Operación exclusiva en **KillZones** (Londres/NY). Reloj en **UTC Estricto**.
2. **Nivel 1 (Filtro Macro)**: Régimen Wyckoff + Ghost Data (Fear & Greed, BTCD, Funding Rates).
3. **Nivel 2 (Estructura)**: Order Blocks, FVG, BOS, Fibonacci Golden Pocket.
4. **Nivel 3 (Gatillo)**: Divergencia RSI + Pullback EMA50 (Paul Predice) / SMC (Francotirador).
5. **Nivel 4 (Riesgo)**: Structural SL/TP geográfico + Fractional Kelly + Trade Quality Score.

```text
El Arma (Stack)       ──► Python + FastAPI + Redis Pub/Sub + Next.js 15 + Supabase
La Munición (Señal)   ──► Pipeline 5 Niveles → Compute Once → Fan-out a N usuarios
El Objetivo (Mercado) ──► Zonas Institucionales / Liquidez / Metales Preciosos (Paul Predice)
```

---

## 🏗️ ARQUITECTURA: 5 NIVELES (Pub/Sub Multi-Tenant)

```
┌──────────────────────────────────────────────────────────────────────┐
│  NIVEL 0: DATA WORKERS (1 por símbolo, no por usuario)              │
│                                                                      │
│  Binance WS ──► BTC Worker ──┐                                      │
│  Binance WS ──► ETH Worker ──┤──► Redis Pub/Sub                     │
│  Binance WS ──► PAXG Worker ─┘    "market:BTCUSDT:15m"             │
│                                   "market:PAXGUSDT:15m"             │
└───────────────────────────────────────────────┬──────────────────────┘
                                                │ Pre-computed JSON
┌───────────────────────────────────────────────▼──────────────────────┐
│  NIVEL 1: ENGINE (Cómputo Compartido — SlingshotRouter)              │
│                                                                      │
│  SymbolWorker("BTCUSDT") → Wyckoff → SMC → ML → Confluencia → Redis │
│  1 instancia de motor por activo, sin importar cuántos usuarios lo   │
│  estén viendo. El resultado se publica en Redis UNA VEZ.             │
└───────────────────────────────────────────────┬──────────────────────┘
                                                │ Redis Subscribe
┌───────────────────────────────────────────────▼──────────────────────┐
│  NIVEL 2: API GATEWAY (FastAPI — solo orquestación, sin lógica)     │
│                                                                      │
│  /api/v1/stream/{symbol} ← User WS → subscribe Redis → fan-out      │
│  /api/v1/auth            ← Supabase JWT verification                │
│  /api/v1/user/watchlist  ← CRUD watchlist personal                  │
│  /api/v1/signals         ← Historial desde Supabase                 │
│                                                                      │
│  main.py < 200 líneas. Sin lógica de negocio aquí.                  │
└───────────────────────────────────────────────┬──────────────────────┘
                                                │ PostgreSQL + Auth
┌───────────────────────────────────────────────▼──────────────────────┐
│  NIVEL 3: SUPABASE (Auth + DB + RLS Multi-Tenant)                   │
│                                                                      │
│  auth.users → subscription_tiers → user_watchlists → signal_events  │
│  Row Level Security: cada usuario solo ve sus propios datos          │
└───────────────────────────────────────────────┬──────────────────────┘
                                                │ HTTPS / WS
┌───────────────────────────────────────────────▼──────────────────────┐
│  NIVEL 4: NEXT.JS 15 (Frontend Multi-Tenant)                        │
│                                                                      │
│  /login  /register  /dashboard  /signals  /backtest  /portfolio     │
│  Autenticación con Supabase Auth (JWT). Watchlist personal por user. │
│  Tiers de suscripción controlan acceso a funcionalidades.            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ STACK TECNOLÓGICO v2.0

### Backend: Motor Python + Gateway

| Componente | Tecnología | Motivo |
|-----------|-----------|--------|
| **Lenguaje** | Python 3.12 | Ecosistema ML/Data nativo |
| **API Framework** | FastAPI 0.115+ | Async nativo, OpenAPI auto-generado |
| **ASGI Server** | Uvicorn | Producción-ready |
| **ML Inference** | ONNX Runtime | <50ms latencia, modelos portables |
| **ML Training** | XGBoost + scikit-learn | Estado del arte para series tabulares |
| **Indicadores TA** | pandas-ta | RSI, MACD, BBWP, Bollinger |
| **Message Bus** | Redis Pub/Sub (Upstash) | Fan-out de señales a N usuarios simultáneos |
| **Auth Verification** | Supabase JWT | Tokens verificados en cada WS connection |
| **WS** | FastAPI WebSockets + aioredis | Nativo async, sin extra libs |

> ⚠️ **ELIMINADO del stack:** Celery, Job Queue, Microservicios por ruta.
> Motivo: Over-engineering para esta escala. `asyncio` nativo + Redis Pub/Sub es suficiente para 10K usuarios.

### Frontend: Multi-Tenant

| Componente | Tecnología | Motivo |
|-----------|-----------|--------|
| **Framework** | Next.js 15 (App Router) | SSR/SSG, middleware de auth, streaming |
| **Auth** | Supabase Auth + `@supabase/ssr` | JWT integrado, server-side session |
| **Lenguaje** | TypeScript 5.5+ | Tipado estricto, Pydantic-compatibilidad |
| **Estilos** | TailwindCSS v4 | Config zero, máximo rendimiento |
| **Estado Global** | Zustand 5 (cliente) | Estado de señales en tiempo real |
| **Charts** | Lightweight Charts v4 (TradingView) | Mejor para OHLCV profesional |
| **Animaciones** | Framer Motion | Micro-animaciones institucionales |
| **Modelos de contrato** | Tipos Pydantic → TypeScript generados | Sin desincronización frontend/backend |

### Infraestructura

| Componente | Tecnología | Motivo |
|-----------|-----------|--------|
| **Deploy Engine + Workers** | Render (Background Workers) | Workers 24/7, auto-restart, escalado por servicio |
| **Deploy Frontend** | Vercel | Edge Network, deploy automático desde GitHub |
| **DB + Auth** | Supabase | PostgreSQL gestionado, RLS, Auth incluida |
| **Cache + Pub/Sub** | Upstash Redis | Serverless Redis, free tier generoso, latencia <1ms |
| **Monitoring** | Sentry (Python + TS) | Errores en producción tiempo real |
| **ML Training** | Google Colab (GPU) | Zero coste local para entrenar modelos |
| **Reloj del sistema** | UTC Estricto | Prevención de bugs temporales cross-timezone |

---

## 🗄️ ESQUEMA DE BASE DE DATOS (Supabase)

```sql
-- SEÑALES: Globales, no pertenecen a ningún usuario específico
CREATE TABLE public.signal_events (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    asset           TEXT NOT NULL,
    interval        TEXT NOT NULL DEFAULT '15m',
    signal_type     TEXT NOT NULL CHECK (signal_type IN ('LONG', 'SHORT')),
    entry_price     FLOAT NOT NULL,
    stop_loss       FLOAT NOT NULL,
    take_profit     FLOAT NOT NULL,
    confluence_score FLOAT,
    regime          TEXT,
    strategy        TEXT,
    trigger         TEXT,
    status          TEXT DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','HIT_TP','HIT_SL','EXPIRED')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    closed_price    FLOAT,
    pnl_pct         FLOAT
);

-- WATCHLISTS: Cada usuario decide qué activos monitorea
CREATE TABLE public.user_watchlists (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    asset           TEXT NOT NULL,
    interval        TEXT DEFAULT '15m',
    alerts_enabled  BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, asset, interval)
);

-- TIERS: Controlan acceso a funcionalidades (free / pro / enterprise)
CREATE TABLE public.subscription_tiers (
    user_id         UUID REFERENCES auth.users(id) PRIMARY KEY,
    tier            TEXT DEFAULT 'free'
                    CHECK (tier IN ('free', 'pro', 'enterprise')),
    max_watchlist   INT DEFAULT 3,    -- free: 3 | pro: 20 | enterprise: ∞
    telegram_alerts BOOLEAN DEFAULT false,
    api_access      BOOLEAN DEFAULT false,
    valid_until     TIMESTAMPTZ
);

-- TRADES: Registro personal de trades tomados por el usuario
CREATE TABLE public.user_trades (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    signal_id       UUID REFERENCES public.signal_events(id),
    entry_price     FLOAT,
    exit_price      FLOAT,
    position_size   FLOAT,
    result          TEXT CHECK (result IN ('WIN','LOSS','BREAKEVEN','OPEN')),
    pnl_usdt        FLOAT,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 📁 ESTRUCTURA DE DIRECTORIOS v2.0

```
slingshot/
├── 📁 engine/                        # Motor Python (Core — no cambiar)
│   ├── 📁 workers/                   # ⭐ NUEVO: Workers autónomos por símbolo
│   │   ├── symbol_worker.py          # Worker: Binance WS → Pipeline → Redis publish
│   │   ├── orchestrator.py           # Gestiona qué símbolos tienen workers activos
│   │   └── base_worker.py            # Clase base abstracta para workers
│   ├── 📁 data/
│   │   ├── fetcher.py                # ⭐ PENDIENTE: REST 4-tier fallback con retry
│   │   └── cache.py                  # ⭐ PENDIENTE: Redis cache layer por timeframe
│   ├── 📁 indicators/                # ✅ COMPLETO — no tocar
│   │   ├── fibonacci.py              # AutoFib con Golden Pocket (0.5-0.66)
│   │   ├── ghost_data.py             # Fear & Greed, BTCD, Funding Rates
│   │   ├── liquidity.py              # Detección de clusters de liquidez
│   │   ├── momentum.py               # RSI Divergencias, MACD, BBWP
│   │   ├── regime.py                 # Detector Wyckoff (Acum/Markup/Dist/Markdown)
│   │   ├── sessions.py               # KillZones horarias
│   │   ├── structure.py              # Order Blocks, FVG, BOS, S/R
│   │   └── volume.py                 # CVD, RVOL
│   ├── 📁 strategies/                # ✅ FUNCIONAL — añadir base.py
│   │   ├── base.py                   # ⭐ PENDIENTE: Protocol/ABC abstracto
│   │   ├── smc.py                    # SMC Paul Perdices (Francotirador)
│   │   ├── trend.py                  # Paul Predice (Tendencia + Divergencia)
│   │   └── reversion.py              # Mean Reversion (Acumulación/Distribución)
│   ├── 📁 ml/                        # ✅ COMPLETO
│   │   ├── features.py               # Feature engineering (50+ features)
│   │   ├── train.py                  # XGBoost trainer
│   │   ├── inference.py              # ONNX Runtime (<50ms)
│   │   └── drift_monitor.py          # ✅ PSI + KS test (supera el blueprint v1)
│   ├── 📁 risk/                      # ✅ COMPLETO
│   │   └── risk_manager.py           # Structural SL/TP + Fractional Kelly
│   ├── 📁 core/                      # ✅ COMPLETO
│   │   ├── confluence.py             # Jurado Neural 0-100 ponderado
│   │   └── session_manager.py        # KillZone state por símbolo
│   ├── 📁 backtest/                  # ⭐ PENDIENTE: Motor offline de backtesting
│   │   ├── engine.py                 # Backtesting batch sobre histórico
│   │   └── reporter.py               # Sharpe, Calmar, Win Rate, Max DD
│   ├── 📁 api/                       # 🔄 REFACTORIZAR
│   │   ├── main.py                   # Solo gateway: auth + fan-out Redis → user WS
│   │   ├── config.py                 # Settings con Pydantic BaseSettings
│   │   ├── advisor.py                # LLM Advisor (bonus no previsto en v1)
│   │   └── ws_manager.py             # WebSocket connection manager
│   └── 📁 notifications/             # ✅ COMPLETO — extender para multi-usuario
│       ├── telegram.py               # Alertas por usuario (conectar a user_id)
│       └── filter.py                 # Deduplicación y spam filter
│
├── 📁 app/                           # Next.js 15 Frontend (Multi-Tenant)
│   ├── 📁 (auth)/                    # ⭐ NUEVO: Rutas de autenticación
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── 📁 (dashboard)/               # ✅ FUNCIONAL — extender con auth guard
│   │   ├── page.tsx                  # Dashboard principal (watchlist personal)
│   │   ├── signals/page.tsx          # Historial de señales
│   │   ├── backtest/page.tsx         # ⭐ PENDIENTE
│   │   └── portfolio/page.tsx        # ⭐ PENDIENTE: P&L personal
│   ├── 📁 components/                # ✅ FUNCIONAL
│   │   ├── signals/
│   │   │   ├── SignalTerminal.tsx    # ✅ UI profesional de señales
│   │   │   └── MarketContextPanel.tsx # ✅ Contexto maestro en vivo
│   │   └── ui/
│   │       ├── TradingChart.tsx       # ✅ TradingView Charts
│   │       ├── MacroRadar.tsx         # ✅ Ghost Data visual
│   │       ├── QuantDiagnosticPanel.tsx
│   │       ├── LiquidityHeatmap.tsx
│   │       └── SessionClock.tsx
│   ├── 📁 store/                     # ✅ FUNCIONAL
│   │   ├── telemetryStore.ts
│   │   └── indicatorsStore.ts
│   └── 📁 hooks/                     # ⭐ PENDIENTE
│       ├── useWebSocket.ts
│       └── useSupabase.ts
│
├── 📁 supabase/
│   └── migrations/                   # ⭐ PENDIENTE: SQL versionado
│
├── 📁 docs/
│   └── BLUEPRINT_MAESTRO.md          # ← ESTÁS AQUÍ
│
├── 📄 render.yaml                    # ⭐ PENDIENTE: Multi-service deploy config (Render)
├── 📄 requirements.txt               # Python dependencies
├── 📄 package.json
├── 📄 .env.example
└── 📄 README.md
```

---

## 🚀 ROADMAP v2.0: 4 FASES DE ESCALA

### FASE 1 — Multi-Tenancy Foundation (Semana 1-2): "La Identidad"
> Objetivo: Añadir usuarios reales sin romper nada. Additive-only.

- [x] Crear tablas Supabase (signal_events, user_watchlists, subscription_tiers, user_trades)
- [x] Añadir Supabase Auth al frontend (`/login`, `/register`)
- [x] Middleware Next.js para proteger rutas del dashboard (redirect si sin JWT)
- [x] Persistir señales en `signal_events` al generarlas (el engine no cambia)
- [x] Context global de usuario con Zustand + Supabase session
- [x] Watchlist personal: usuario elige qué activos monitorear

**✅ Entregable:** Sistema funcionando con login real. Señales guardadas permanentemente.

---

### FASE 2 — Arquitectura Pub/Sub (Semana 3-4): "El Escalador"
> Objetivo: Separar cómputo del gateway. Transformación arquitectónica crítica.

- [ ] Crear `engine/workers/symbol_worker.py` — Worker autónomo por símbolo
- [ ] Integrar Upstash Redis (Pub/Sub channel por símbolo)
- [ ] Refactorizar `websocket_stream_endpoint` → solo subscribe Redis + fan-out al usuario
- [x] Crear `engine/workers/orchestrator.py` — inicia/detiene workers según demanda
- [ ] Verificación JWT en cada nueva conexión WebSocket
- [x] `main.py` queda en ≤200 líneas (solo orquestación)
- [ ] Tests de integración: Worker → Redis → Gateway → Cliente

**✅ Entregable:** 1000+ usuarios simultáneos en el mismo activo sin degradación de CPU.

---

### FASE 3 — Features de Producto (Semana 5-6): "El Producto"
> Objetivo: Las funcionalidades que hacen que un usuario quiera pagar.

- [ ] `engine/strategies/base.py` — Protocol/ABC abstracto (contrato obligatorio)
- [ ] `engine/backtest/engine.py` — Motor de backtesting batch
- [ ] Página `/backtest` en UI — selección de activo + rango + estrategia
- [ ] Página `/portfolio` — P&L histórico personal (wins/losses/drawdown)
- [ ] Telegram Alerts por usuario — conectar `telegram.py` a `user_watchlists`
- [ ] Modelo Guardian 4H — filtro macro direccional (segunda capa ML)
- [ ] Pydantic V2 como contrato de módulos (reemplazar dicts sin tipado)

**✅ Entregable:** Producto completo justificable para suscripción de pago.

---

### FASE 4 — Producción y Monetización (Semana 7): "El Disparo"
> Objetivo: Sistema deployado 24/7, monitoreado y facturando.

- [ ] `render.yaml` con definición de servicios (engine workers + api gateway como Background Workers)
- [ ] GitHub Actions CI/CD — tests automáticos en cada push a main
- [ ] Sentry integration (Python + TypeScript)
- [ ] Stripe webhooks para gestión de suscripciones
- [ ] Rate limiting en API (por tier)
- [ ] Documentación técnica (auto-generada desde FastAPI OpenAPI)
- [ ] `README.md` público con onboarding para usuarios

**✅ Entregable:** Sistema en producción Render + Vercel + Supabase, con usuarios reales pagando.

---

## ⚡ COMPARATIVA: GEN 1 vs GEN 2

| Dimensión | Slingshot Gen 1 | Slingshot Gen 2 |
|-----------|-----------------|-----------------|
| **Usuarios simultáneos** | ~5-10 (colapsa) | 10,000+ |
| **Cómputo por usuario** | 1 pipeline completo | 0 (fan-out pre-calculado) |
| **Conexiones Binance** | 1 por usuario | 1 por símbolo activo |
| **Persistencia señales** | LocalStorage (volátil) | Supabase (permanente + historial) |
| **Autenticación** | Sin auth (WS abierto) | JWT + Supabase Auth |
| **Multi-tenancy** | No existe | Sí (watchlist, tiers, portfolio) |
| **Monetización** | No | Stripe + Subscription tiers |
| **Deploy** | Solo local | Render + Vercel (24/7) |
| **Monitoring** | `print()` / console.log | Sentry + Render Metrics |
| **Contrato de módulos** | Dicts sin tipado | Pydantic V2 BaseModels |
| **Backtesting** | Sin integrar | Motor batch + UI |
| **Alertas Telegram** | Global o manual | Por usuario + watchlist |

---

## 📊 LO QUE SUPERA AL BLUEPRINT v1 (Logros de Gen 1)

Estas piezas están por encima de lo planificado originalmente y **no deben tocarse**:

| Módulo | Por qué supera el blueprint |
|--------|----------------------------|
| `drift_monitor.py` | PSI por percentiles + accuracy rolling + cache TTL. Nivel Data Science real. |
| `risk_manager.py` | Structural SL/TP geográfico (busca OB más cercano). Prop trading real. |
| `confluence.py` | Jurado ponderado con anti-temporal-leak. 6 dimensiones de evaluación. |
| `session_manager.py` | KillZone state por símbolo. 19KB de lógica detallada. |
| `advisor.py` | LLM Advisor contextual. No estaba planificado en v1. |
| MarketContextPanel | Semántica de checklist institucional. UX superior. |

---

## ✅ PRINCIPIOS DE TRABAJO v2.0

1. **Compute Once, Fan-Out** — La señal se calcula una sola vez y se distribuye a N usuarios.
2. **Additive Migrations** — Cada fase añade funcionalidad sin romper la anterior.
3. **Pydantic V2 como contrato** — Todos los módulos del engine usan modelos tipados.
4. **Supabase como fuente de verdad** — Señales, usuarios y trades viven en la DB, no en memoria.
5. **Tests antes de merge** — No se integra código sin al menos test de smoke.
6. **Commits semánticos** — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`
7. **UTC Estricto** — Ningún timestamp sin timezone. Siempre UTC en backend.
8. **Secretos en .env** — Nunca hardcoded. Validados con Pydantic BaseSettings.

---

*SLINGSHOT v2.0 — "David no le falló a Goliat por accidente. Fue el resultado de datos, práctica y la arquitectura correcta para el momento correcto."*

---

## 📌 DECISIONES DE INFRAESTRUCTURA JUSTIFICADAS

### ¿Por qué Render y no Railway?

| Criterio | Render | Railway |
|---|---|---|
| **Background Workers** | ✅ Tipo nativo en la UI | ✅ También soportado |
| **Free Tier** | ✅ 750h/mes de compute | ✅ $5 crédito inicial |
| **Auto-deploy desde GitHub** | ✅ Nativo | ✅ Nativo |
| **Escalado Worker Independiente** | ✅ Cada servicio escala por separado | ✅ Similar |
| **Estabilidad histórica** | ✅ Más maduro (2019) | ⚠️ Más joven (2020) |
| **Comunidad Python** | ✅ FastAPI docs lo recomiendan | ✅ También soporte bueno |
| **render.yaml** | ✅ Infrastructure-as-Code nativo | ✅ railway.toml equivalente |

**Veredicto:** Render es la elección correcta. Más maduro, free tier más claro, y es el recomendado oficial en la documentación de FastAPI para deploy de production workers Python.

### Stack de infra definitivo:
```
Render     → Engine Workers (Python) + API Gateway (FastAPI)
Vercel     → Frontend (Next.js 15)
Supabase   → Auth + PostgreSQL + Storage
Upstash    → Redis Pub/Sub (serverless, sin gestionar infra)
Sentry     → Error monitoring (Python + TypeScript)
```
