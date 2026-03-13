# 🎯 PROJECT: SLINGSHOT — BLUEPRINT MAESTRO v3.3
## "Poder de cómputo local al servicio del trader individual."
> **Versión:** 3.3 (Qwen Local Master Edition)  |  **Fecha:** 2026-03-13  |  **Estado:** ACTIVO ✅
> *Actualizado desde Blueprint 3.0 — Portero Institucional R:R activado. PAXGUSDT (Oro) reintegrado.*

---

## 🔬 EL PIVOTE: DE MULTI-TENANT A HERRAMIENTA PERSONAL (v2 -> v3)

**El paradigma anterior (v2):** Buscaba crear una plataforma SaaS (Software as a Service) multi-usuario, con "fan-out" de señales a miles de usuarios, requiriendo Redis, Supabase, Auth, Vercel y Render.

**La nueva visión (v3):** Slingshot es una **Herramienta de Trading Personal**. Está diseñada para ejecutarse **100% en local**, aprovechando al máximo los recursos de hardware de tu PC personal. 

### 💀 Qué eliminamos (Simplificación radical):
1. **Multi-Tenancy y Autenticación:** Se elimina Supabase Auth y el concepto de cuentas de usuario. Al correr en tu PC, tú eres el único usuario.
2. **Redis Pub/Sub:** Al ser un único cliente (tu frontend local), el backend FastAPI se comunica directamente mediante WebSockets con tu Next.js. No hay necesidad de un bus de mensajes externo.
3. **Persistencia Pesada en DB:** Los análisis se realizan en memoria *mientras el sistema está corriendo*. Ya no es necesario almacenar el historial masivo de señales y eventos en una base de datos en la nube.
4. **Cloud Deployment:** Adiós a Vercel, Render y configuraciones de hosting. Todo corre en `localhost`.

### ⚡ Qué mantenemos y potenciamos:
1. **Python FastAPI + Next.js 15:** El stack central sigue siendo el mismo por su robustez, velocidad y modernidad.
2. **Motor de Análisis (Engine):** Nuestro pipeline de indicadores (KillZones, Wyckoff, SMC, ML, Risk Manager) se mantiene intacto y funcionará más rápido al carecer de límite de recursos en la nube.
3. **WebSocket en Tiempo Real:** La terminal de señales y los gráficos se actualizan instantáneamente sin latencia de red (ping de red = 0ms local).

---

## 🎯 SLINGSHOT 3.0: ARQUITECTURA LOCAL HIPER-OPTIMIZADA

### Filosofía de Diseño: "Zero Latency Local Compute"
Al eliminar el internet (Cloud DB, Redis, APIs externas) como intermediario entre tus propios componentes, la latencia entre el análisis pesado de Python y la pantalla de Next.js se reduce prácticamente a cero.

### Pipeline de Análisis en Vivo:
1. **Binance WebSocket** → Inyecta ticks del mercado en tiempo real a tu PC.
2. **Análisis en Memoria**:
   - Limitación a KillZones.
   - Filtros Macro (Wyckoff).
   - Estructura de Liquidez (OBs, S/R).
   - Gatillos (Divergencias, ML).
3. **FastAPI WebSockets** → Empuja la data estructurada directo a tu Frontend Next.js.

---

## 🏗️ ARQUITECTURA TÉCNICA (Standalone Local)

```text
┌──────────────────────────────────────────────────────────────────────┐
│  DATA SOURCE (Internet)                                             │
│  Binance WS (Kline / AggrTrade / Depth)                             │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │ WebSockets
┌───────────────────────────────────▼──────────────────────────────────┐
│  BACKEND LOCAL (Tu PC: Python + FastAPI)                            │
│                                                                      │
│  - Symbol Workers corren en procesos locales (CPU multicore).       │
│  - ML Inference (ONNX) corre nativo en tu máquina.                  │
│  - Estado efímero de las señales mantenido en Memoria RAM.          │
└───────────────────────────────────┬──────────────────────────────────┘
                                    │ WebSockets (Localhost)
┌───────────────────────────────────▼──────────────────────────────────┐
│  FRONTEND LOCAL (Tu PC: Next.js 15)                                 │
│                                                                      │
│  - UI Institucional de Señales (Signal Terminal) en vivo.           │
│  - Acceso directo al Dashboard sin Login.                           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ ADAPTACIÓN DE LA BASE DE DATOS

Dado que las señales son efímeras y el análisis vive *mientras la app esté desplegada en tu terminal*, la base de datos PostgreSQL en Supabase se **reduce a lo mínimo indispensable** o se reemplaza por opciones locales (como SQLite o simples archivos JSON de configuración).

**¿Qué necesitamos guardar realmente? (Settings Locales):**
1. **Configuración de Watchlist:** Qué monedas (`BTCUSDT`, `ETHUSDT`) e intervalos quieres monitorear al encender la herramienta.
2. **Configuraciones de Estrategia/UI:** Preferencias del Risk Manager, umbrales de score, selección de tema oscuro/claro.

*Todo evento transaccional masivo (ticks, señales descartadas) vive y muere en la sesión actual de RAM.*

---

## 🛠️ STACK TECNOLÓGICO v3.3

### Backend (Local Engine)
| Componente | Tecnología | Uso |
|-----------|-----------|-----|
| **Lenguaje** | Python 3.12 | Cálculos de hardware y procesamiento TA/ML. |
| **API / WS** | FastAPI + Uvicorn | Gateway ultrarrápido por WebSockets en localhost. |
| **State Manager** | `engine/core/store.py` (MemoryStore) | Estado efímero con buffers circulares y asyncio.Lock. |
| **Risk Manager** | `engine/risk/risk_manager.py` | Portero Institucional: calcular SL/TP, validar R:R ≥ 1.8. |
| **Notificaciones** | `engine/notifications/` | Telegram + Signal Filter anti-spam. |
| **Orquestador** | `engine/workers/orchestrator.py` | Mantiene Broadcasters VIP vivos (BTC, ETH, SOL, PAXG). |
| **ML Probabilístico**| `engine/ml/inference.py` (XGBoost)| Probabilidad matemática Alcista/Bajista en <50ms. |
| **LLM Táctico**    | `engine/api/advisor.py` (Ollama/Qwen3) | Cerebro Institucional que asimila data y emite directrices 100% locales. |
| **Persistencia** | JSON Local (`engine/data/`) | Solo estados de sesión VIP entre reinicios. |

### Frontend (Local UI)
| Componente | Tecnología | Uso |
|-----------|-----------|-----|
| **Framework** | Next.js 15 (React 19) | Interfaz pesada, corriendo en modo dev local. |
| **Estilos** | TailwindCSS v4 + Glassmorphism | Visual institucional premium. |
| **Estado** | Zustand 5 (`telemetryStore`) | Stream vivo de datos WS en el cliente. |
| **Gráficos** | Lightweight Charts v4 | Visualización de Velas y Señales. |

### Activos VIP (Monitoreados 24/7)
| Activo | Estrategia | Intervalo |
|--------|-----------|----------|
| `BTCUSDT` | Dual: SMC + Trend + Reversion | 15m |
| `ETHUSDT` | Dual: SMC + Trend + Reversion | 15m |
| `SOLUSDT` | Dual: SMC + Trend + Reversion | 15m |
| `PAXGUSDT` | **Paul Predices Exclusivo** (KillZone+OB+Sweep+RVOL) | 15m |

---

## 📁 ESTRUCTURA DE DIRECTORIOS (Visión Simplificada)

```
slingshot_gen1/
├── 📁 engine/                         # Python FastAPI Engine
│   ├── 📁 api/                        # FastAPI: main.py, ws_manager.py, config.py
│   ├── 📁 core/                       # store.py (MemoryStore), confluence.py, session_manager.py
│   ├── 📁 indicators/                 # Lógica matemática: regime, structure, ghost_data, fibonacci...
│   ├── 📁 ml/                         # XGBoost local: inference.py, features.py, drift_monitor.py
│   ├── 📁 risk/                       # risk_manager.py — Portero Institucional R:R
│   ├── 📁 strategies/                 # smc.py, trend.py, reversion.py
│   ├── 📁 workers/                    # orchestrator.py — mantiene broadcasters VIP vivos
│   ├── 📁 notifications/              # telegram.py, filter.py — alertas opcionales
│   ├── 📁 filters/                    # time_filter.py — KillZone UTC
│   ├── 📁 data/                       # session_state_*.json — estados VIP entre sesiones
│   └── main_router.py                 # Router Maestro: Wyckoff → Strategy → Risk → Signal
│
├── 📁 app/                            # Next.js UI Local
│   ├── 📁 (dashboard)/
│   │   ├── page.tsx                   # Dashboard principal (Radar + Context Panel)
│   │   ├── layout.tsx                 # Sidebar + Header (Sin auth)
│   │   ├── 📁 radar/                  # Radar Center — malla de activos VIP
│   │   ├── 📁 signals/                # Signal Terminal — señales vivas con SL/TP
│   │   ├── 📁 chart/                  # Trading Chart — Lightweight Charts
│   │   ├── 📁 heatmap/                # Liquidity Heatmap
│   │   └── 📁 history/                # Session Log — historial efímero de la sesión
│   ├── 📁 components/                 # SignalTerminal, DiagnosticGrid, MarketContextPanel...
│   └── 📁 store/                      # telemetryStore.ts — Zustand estado WS
│
├── 📁 scripts/                        # Utilidades: download_history.py, tests/
├── 📁 docs/                           # BLUEPRINT_MAESTRO.md
├── 📄 run_engine.py                   # Entry point del backend
├── 📄 start.ps1                       # Script para levantar backend + frontend juntos
└── 📄 README.md                       # Instrucciones de arranque
```

---

---

## 🚀 ROADMAP v3.0: EL PIVOTE LOCAL Y PLAN DE IMPLEMENTACIÓN (Fusión v3.2)

Este plan detalla la transición profesional desde una arquitectura dependiente de la nube (Redis, Auth) hacia un sistema de **Estado Efímero Centralizado** 100% local.

### FASE 1: Limpieza del Proyecto Anterior ✅ COMPLETADA
- [x] Eliminar toda lógica de Supabase Auth en el Frontend (Login, Registro, Guards).
- [x] Desacoplar Base de Datos: La UI solo lee variables directo del WebSocket en vivo.
- [x] **Eliminar Redis**: `MemoryStore` interno con `asyncio.Lock` / `asyncio.Queue`.
- [x] **Desacoplar el Monolito del Frontend**: Grupo de rutas `app/(dashboard)/` creado.

### FASE 2: Motor Reactivo, Estado In-Memory y Centralización de Cómputo ✅ COMPLETADA
- [x] Almacén central de datos (`engine/core/store.py`) con buffers circulares.
- [x] `SymbolBroadcaster` y `Orchestrator` como únicos motores de análisis por activo.
- [x] **Centralización de Gestión de Riesgos**:
  - [x] `engine/risk/risk_manager.py` refactorizado con Portero Institucional.
  - [x] `main_router.py` como único despachador de señales validadas.
  - [x] Filtro R:R ≥ 1.8 activo — señales subóptimas rechazadas automáticamente.

### FASE 3: Interfaz de Poder Local y Blindaje Frontend ✅ COMPLETADA
- [x] `SignalTerminal` y `RadarCenter` consumen endpoints locales (`/api/v1/market-states`, WS).
- [x] `Session Log` (ex Audit History) con auto-refresh cada 5 segundos.
- [x] Sidebar limpio: Overview, Radar Center, Signal Terminal, Trading Chart, Heatmap, Session Log.

### FASE 4: Limpieza Profunda y Estandarización ✅ COMPLETADA
- [x] Eliminados 14 logs de raíz (879KB+), 36 scripts tmp/ Supabase-era.
- [x] Eliminados directorios fantasma `supabase/` y `lib/`.
- [x] Eliminados session states de activos no-VIP (BNBUSDT, PEPEUSDT, PAXUSDT).
- [x] Bugs de versión corregidos en `main.py`, `ws_manager.py`, `layout.tsx`.
- [x] `PAXGUSDT` (Oro) reintegrado con estrategia Paul Predices exclusiva.

---

## 🏛️ ANEXO: RESUMEN DE AUDITORÍA ARQUITECTÓNICA v1.0->v3.0

Para mantener contexto sobre por qué se estructura el código de esta forma, resumimos las brechas identificadas de la versión original:

1. **Frontend (Next.js)**: Originalmente una SPA masiva en `app/page.tsx`. -> *Solución (Fase 1)*: Migración a estructura multi-ruta para Code Splitting automático.
2. **Capa de Riesgo/Backtest**: Acoplamiento de reglas de riesgo dentro de los módulos de estrategia rompiendo el Principio de Responsabilidad Única. -> *Solución (Fase 2)*: Reinvención de `risk_manager.py` global e inyección de dependencias.
3. **Capa Core/Estrategias**: La estructura en backend base (`indicators/`, `strategies/`) estaba fuerte. -> *Solución*: Se mantiene. A futuro, asegurar herencia de una clase abstracta común.
4. **Capa de Inteligencia (ML)**: El pipeline base era correcto pero el Hub visual en frontend desconectado. -> *Solución*: Exposición mediante microservicios FastAPI limpios (`/api/ml/predict`) asíncronos para consumo ligero.

---

## ✅ PRINCIPIOS DE TRABAJO v3.0

1. **Local-First Extremo:** Tu PC es el servidor y el cliente. Optimizamos para tus especificaciones.
2. **Data Volátil (Hot State):** Solo nos importa lo que pasa mientras estás sentado con la app abierta operando. Al reiniciar, el sistema "siembra" los activos base automáticamente.
3. **Máximo Rendimiento Centralizado:** Al no depender de la nube (Redis latencia, DB inserts) y operar como un monolito optimizado en `MemoryStore`, nos concentramos en velocidad y consistencia matemática absoluta.

---

*SLINGSHOT v3.2 — "Tu propia terminal algorítmica institucional. Silenciosa, rápida, matemáticamente impecable y enteramente tuya."*
