# 🎯 PROJECT: SENTINEL — BLUEPRINT MAESTRO
## "La precisión es la única respuesta válida ante la fuerza bruta."
> **Versión:** 1.0  |  **Fecha:** 20-02-2026  |  **Estado:** APROBADO ✅

---

## 🔬 ANÁLISIS FORENSE: CRIPTODAMUS (EL PASADO)

### Stack Actual
| Capa | Tecnología | Versión |
|------|-----------|---------|
| Frontend | React + Vite + TypeScript | 18.x / 5.x |
| Estilos | TailwindCSS | 4.x |
| Estado | Zustand | 5.x |
| Backend | Node.js + Express + TypeScript | 18+ |
| ML | TensorFlow.js (Node) | 4.22 |
| DB | Supabase (PostgreSQL) | latest |
| Streams | Binance WS (nativo) | - |
| Deploy | Vercel (FE) + Render (BE) | - |

### 💀 12 Debilidades Críticas Identificadas

1. **Monolito de 99KB** — `signalAuditService.ts` con 99,349 bytes es un monolito que viola SRP. Mezcla auditoría, ML metrics, trades activos y streaming en un solo archivo.

2. **TensorFlow.js en Node.js** — TF.js fue diseñado para el browser. Usarlo en el servidor consume 4-8x más memoria que TensorFlow Python o ONNX Runtime.

3. **0% Test Coverage** — Sistema financiero sin tests unitarios ni de integración. Cualquier cambio puede romper la lógica de señales silenciosamente.

4. **CORS Totalmente Abierto** — `origin: '*'` en producción es una vulnerabilidad de seguridad.

5. **Sin Backtesting Real** — `backtestEngine.ts` existe pero no está integrado en el pipeline de validación. Las estrategias se despliegan a ciegas.

6. **Dependencia Frágil de APIs Públicas** — Sin caching estructurado, si Binance/CoinGecko falla, el sistema queda sin datos.

7. **Arquitectura Plana** — No hay separación entre: `data ingestion`, `signal processing`, `risk management`, y `execution`.

8. **Runtime TSX en Producción** — `tsx watch` en producción añade overhead de transpilación en tiempo real.

9. **Sin Cola de Trabajo (Job Queue)** — El scheduler usa `setInterval` directo. Si el proceso muere, se pierden todos los jobs.

10. **ML Model Drift** — No hay monitoreo de degradación del modelo. Si el mercado cambia, el modelo sigue prediciendo con datos obsoletos.

11. **WebSocket Sin Auth** — El endpoint `/ws` no verifica token. Cualquier cliente puede recibir señales de trading.

12. **Sin Replay/Simulación** — No hay forma de simular escenarios históricos completos para validar nuevas estrategias.

---

## 🎯 SLINGSHOT: EL NUEVO PARADIGMA

### Filosofía de Diseño: "PAUL PERDICES" (SMC Avanzado)
SENTINEL opera bajo un Pipeline de Ejecución de 5 Niveles:

1. **Nivel 0 (Tiempo)**: Operación exclusiva en **KillZones** (Apertura Londres / Nueva York). Fuera de horario = Modo Observador. Reloj del sistema en **UTC Estricto**.
2. **Nivel 1 (Filtro Macro & Ghost Data)**: Detección de régimen de mercado (Tendencia/Rango) e integración de "Datos Fantasma" (Noticias alto impacto, Actividad Solar/Índice Kp, Dominancia BTC).
3. **Nivel 2 (Estructura)**: Mapeo de Liquidez, Order Blocks (OB), Fair Value Gaps (FVG) y Change of Character (ChoCh).
4. **Nivel 3 (Gatillo)**: Confirmación estricta por Volumen y Order Flow.
5. **Nivel 4 (Gestión de Riesgo)**: Ratio **3:1** forzado, Riesgo **1%** por trade, y paso automático a **Breakeven** al tocar 1:1.

```text
El Arma (Stack)       ──► Python + FastAPI + Parquet (Data Lake) + Bun + Next.js 15
La Munición (Señal)   ──► Ghost Data + Pipeline 5 Niveles → Entrada 3:1 (Escáner Multi-Activo Concurrente)
El Objetivo (Mercado) ──► Reversiones en Zonas Institucionales / Cacería de Liquidez
```
---

## 🏗️ ARQUITECTURA: 6 CAPAS (Router Híbrido)
```
[📡 Capa 1: Datos]   Binance WS + Fetcher + Fallbacks (Parquet Data Lake)
        │
        ▼
[🧠 Capa 2: Router]  Detector de Régimen (Wyckoff: Acumulación, Markup, Distribución, Markdown)
        │            (Enruta a la estrategia correcta según la fase del mercado)
        ▼
[⚙️ Capa 3: Motor]   Ejecutor de Estrategias (SMC Paul Perdices, Trend Following, Mean Reversion)
        │
        ▼
[🔌 Capa 4: API]     FastAPI + WebSocket Manager + Redis
        │
        ▼
[🖥️ Capa 5: UI]      Next.js 15 + Zustand + TanStack Query + Lightweight Charts
        │
        ▼
[☁️ Capa 6: Infra]   Supabase PostgreSQL / Caching
```

---

## 🛠️ STACK TECNOLÓGICO DEFINITIVO

### Backend: El Motor Python (Core Engine)
| Componente | Tecnología | Motivo |
|-----------|-----------|--------|
| **Lenguaje** | Python 3.12 | Ecosistema ML/Data nativo, 10x mejor que TF.js-Node |
| **API Framework** | FastAPI 0.115+ | Async nativo, OpenAPI auto-generado, 40K req/s |
| **ASGI Server** | Uvicorn + Gunicorn | Producción-ready, workers múltiples |
| **ML Inference** | ONNX Runtime 1.18 | 5-10x más rápido que TF.js en CPU, modelos portables |
| **ML Training** | scikit-learn + XGBoost | Mejor que TF.js para series temporales tabulares |
| **Datos TA** | TA-Lib + pandas-ta | Librería estándar de la industria para indicadores |
| **Cache** | Redis 7.x (Upstash) | Cache de datos de mercado en tiempo real |
| **Job Queue** | Celery + Redis | Cola robusta con reintentos y monitoreo |
| **WS** | FastAPI WebSockets | Nativo, sin librería extra |

### Frontend: La Interfaz
| Componente | Tecnología | Motivo |
|-----------|-----------|--------|
| **Framework** | Next.js 15 (App Router) | SSR/SSG, Streaming, mejor DX que Vite |
| **Lenguaje** | TypeScript 5.5+ | Tipado estricto |
| **Estilos** | TailwindCSS v4 | Config zero, máximo rendimiento |
| **Estado** | Zustand 5 + TanStack Query | Server state separado del cliente |
| **Charts** | Lightweight Charts v4 (TradingView) | El mejor para OHLCV profesional |
| **Animaciones** | Framer Motion | Micro-animaciones profesionales |

### Runtime & Infra
| Componente | Tecnología | Motivo |
|-----------|-----------|--------|
| **JS Runtime** | Bun 1.x | 4x más rápido que Node |
| **Python Pkg** | uv (Astral) | 100x más rápido que pip |
| **Almacenamiento** | Formato `.parquet` (Data Lake Local) | Optimizado para Big Data y Pandas |
| **Entrenamiento ML** | Google Colab (GPU/TPU) | Zero coste local para IA pesada |
| **Deploy BE** | Render / Railway.app | Contenedores para motor Python 24/7 |
| **Deploy FE** | Vercel | Hosting nativo optimizado para Next.js 15 |
| **Reloj del Sistema**| **UTC Estricto** | Prevención de errores de sincronización temporales |

---

## 📁 ESTRUCTURA DE DIRECTORIOS

```
slingshot/
├── 📁 engine/                    # Motor Python (Core)
│   ├── 📁 data/
│   │   ├── binance_stream.py     # WS Binance nativo (v2)
│   │   ├── fetcher.py            # REST 4-tier fallback con retry
│   │   └── cache.py              # Redis cache layer
│   ├── 📁 indicators/            # TA puro y limpio
│   │   ├── trend.py              # EMA, SMA, Ichimoku
│   │   ├── momentum.py           # RSI, MACD, Stoch
│   │   ├── volume.py             # CVD, OBV, RVOL
│   │   ├── structure.py          # Order Blocks, FVG, BOS
│   │   └── fibonacci.py          # Fib automático con fractales
│   ├── 📁 strategies/            # Estrategias puras (sin side effects)
│   │   ├── smc.py               # Smart Money Concepts
│   │   ├── quant.py             # Quantitative (mean reversion)
│   │   ├── momentum.py          # Trend following
│   │   └── base.py              # Interface/Protocol abstracta
│   ├── 📁 ml/
│   │   ├── features.py           # Feature engineering (50+ features)
│   │   ├── train.py              # XGBoost/LightGBM trainer
│   │   ├── inference.py          # ONNX Runtime inference
│   │   └── drift_monitor.py      # ⭐ NUEVO: Detección de drift (PSI+KS)
│   ├── 📁 risk/
│   │   ├── position_sizer.py     # Kelly Criterion + ATR sizing
│   │   ├── portfolio.py          # Gestión de portfolio virtual
│   │   └── drawdown.py          # Max drawdown protection
│   ├── 📁 backtest/
│   │   ├── engine.py             # Motor vectorizado (vectorbt)
│   │   ├── reporter.py           # Métricas: Sharpe, Calmar, etc.
│   │   └── walk_forward.py      # Walk-forward optimization
│   ├── 📁 api/
│   │   ├── main.py               # FastAPI app entry point
│   │   ├── routes/
│   │   │   ├── signals.py
│   │   │   ├── market.py
│   │   │   ├── ml.py
│   │   │   └── admin.py
│   │   └── ws_manager.py        # WebSocket manager (desacoplado)
│   ├── 📁 notifications/
│   │   ├── telegram.py
│   │   └── filter.py             # Deduplicación y spam filter
│   └── 📁 tests/                 # ⭐ Tests desde el día 1
│       ├── test_indicators.py
│       ├── test_strategies.py
│       ├── test_ml.py
│       └── test_risk.py
│
├── 📁 app/                       # Next.js 15 Frontend
│   ├── 📁 (dashboard)/
│   │   ├── page.tsx              # Dashboard principal
│   │   ├── signals/page.tsx
│   │   ├── backtest/page.tsx     # ⭐ NUEVO
│   │   ├── portfolio/page.tsx    # ⭐ NUEVO
│   │   └── lab/page.tsx         # ⭐ NUEVO: Laboratorio de señales
│   ├── 📁 components/
│   │   ├── signals/
│   │   ├── charts/
│   │   └── ui/                   # shadcn/ui components
│   ├── 📁 hooks/
│   │   ├── useWebSocket.ts
│   │   └── useSignals.ts
│   └── 📁 stores/
│       └── useSlingshotStore.ts
│
├── 📁 supabase/
│   └── migrations/               # SQL con control de versión
│
├── 📁 docs/                      # ← ESTÁS AQUÍ
│   └── BLUEPRINT_MAESTRO.md
│
├── 📄 docker-compose.yml         # ⭐ Redis + PG local
├── 📄 pyproject.toml             # Python dependencies (uv)
├── 📄 package.json               # JS dependencies (Bun)
├── 📄 .env.example
└── 📄 README.md
```

---

## 🚀 ROADMAP DE IMPLEMENTACIÓN: 4 FASES

### FASE 1 — Cimientos (Semana 1-2): "La Honda"
> Objetivo: Infraestructura base y pipeline de datos funcionando

- [ ] Crear monorepo `slingshot/` con estructura definitiva
- [ ] Configurar Python con `uv` + FastAPI + Docker Compose (Redis)
- [ ] Implementar `binance_stream.py` (WS nativo, sin dependencias)
- [ ] Implementar `fetcher.py` con 4-tier fallback
- [ ] Implementar `cache.py` con Redis (TTL por timeframe)
- [ ] Setup Next.js 15 + TailwindCSS v4
- [ ] Conectar Supabase con migrations versionadas

### FASE 2 — El Motor (Semana 3-4): "La Piedra"
> Objetivo: Análisis técnico profesional + estrategias limpias

- [x] Módulos de Macro-Data (Fear & Greed, Funding Rates, BTCD)
- [x] Módulos de Liquidez (Liquidation Maps, Sweep detection)
- [x] Implementar todos los indicadores con TA-Lib (RSI Divs, MACD, BBWP)
- [x] Implementar Order Blocks y Fair Value Gaps (SMC puro)
- [x] Indicador Autofib Bidireccional con Golden Pocket institucional
- [x] Sistema de scoring modular hiper-confluente (0-100)
- [x] Gestión de riesgo estricta (Kelly Criterion + ATR + Breakeven OS)
- [x] Pipeline completo: Datos → Indicadores → Score → Señal
- [/] Tests unitarios para cada módulo (pytest)

### FASE 3 — La Inteligencia (Semana 5-6): "El Cerebro"
> Objetivo: ML real con Arquitectura Multi-Temporal Especializada

- [x] Feature engineering profesional (Inyectar métricas de SMC Order Blocks)
- [x] Construir script de descarga masiva (35,000+ velas) desde Binance API
- [x] Entrenar **Cerebro Core (15m)** - Modelo táctico intradía (`slingshot_xgb_15m_v2`)
- [ ] Entrenar **Cerebro Macro (4H)** - Filtro direccional guardián (`slingshot_xgb_4h_v2`)
- [x] Exportar a ONNX para inferencia en producción con latencia <50ms
- [ ] Drift monitor (PSI + KS test) para alertar si el modelo queda obsoleto
- [x] Backtesting vectorizado con vectorbt
- [/] Dashboard de métricas ML en tiempo real

### FASE 4 — La Precisión (Semana 7-8): "El Disparo"
> Objetivo: Sistema end-to-end, producción-ready

- [ ] Telegram Bot v2 (comandos: /señales, /portfolio, /backtest)
- [ ] Portfolio tracker con P&L real
- [ ] Laboratorio de señales (backtesting desde UI)
- [ ] Monitoring con Sentry
- [ ] Deploy: Railway (Python) + Vercel (Next.js)
- [ ] Documentación técnica completa (auto-generada con OpenAPI)

---

## ⚡ COMPARATIVA: ANTES VS DESPUÉS

| Dimensión | CriptoDamus (Antes) | SLINGSHOT (Después) |
|-----------|---------------------|---------------------|
| **ML Runtime** | TF.js Node (lento, 200MB) | ONNX Runtime (5-10x más rápido) |
| **ML Training** | TF.js (básico) | XGBoost + LightGBM (estado del arte) |
| **TA Engine** | Custom TypeScript | TA-Lib (C-native, estándar industria) |
| **Arquitectura** | Monolito Express | Microservicios FastAPI |
| **Tests** | 0% | >80% coverage objetivo |
| **Backtesting** | Script suelto | Motor integrado + UI |
| **Caching** | node-cache (in-memory) | Redis distribuido (persistente) |
| **Job Queue** | setInterval | Celery + monitoreo (Flower) |
| **Seguridad** | CORS `*`, 0 auth WS | JWT, Rate Limit, WS auth |
| **Deploy** | TSX en producción | Uvicorn compilado |
| **Monitoreo** | console.log | Sentry + métricas estructuradas |
| **Docs** | 40% manual | 100% auto-generado (OpenAPI) |

---

## ✅ PRINCIPIOS DE TRABAJO PROFESIONAL

1. **Monorepo único** — Un solo Git repo para engine (Python) y app (Next.js)
2. **Docker Compose local** — Redis + PostgreSQL local, sin depender de la nube en dev
3. **Rama por fase** — `feat/fase-1-cimientos`, `feat/fase-2-motor`, etc.
4. **Tests desde el día 1** — No se mergea código sin tests
5. **Commits semánticos** — `feat:`, `fix:`, `test:`, `docs:`
6. **CI/CD desde el inicio** — GitHub Actions: tests automáticos en cada PR
7. **Variables de entorno** — Nunca un secreto hardcodeado en el código
8. **Code Review** — Cada cambio pasa por checklist antes de merge

---

*SLINGSHOT v1.0 — "David no le falló a Goliat por accidente. Fue el resultado de datos, práctica y la precisión de saber exactamente dónde golpear."*
