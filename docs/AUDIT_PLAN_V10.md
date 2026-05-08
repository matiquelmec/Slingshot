# 🛡️ Plan de Auditoría Exhaustiva — Slingshot v10.0 APEX SOVEREIGN
## v2.0 — Análisis Profundo con Hallazgos Reales
**Auditor:** Antigravity (Claude Opus 4.6 — Advanced AI Coding)
**Fecha:** 5 de Mayo, 2026

---

## 🚨 FASE 0: Hallazgos Críticos Ya Detectados (Prioridad Inmediata)

Antes de cualquier auditoría futura, estos 6 problemas deben resolverse:

### 0.1. Drift de Versiones (Identidad Fracturada)
El proyecto declara versiones distintas en cada archivo. Esto genera confusión operativa:

| Archivo               | Versión Declarada      |
|-----------------------|------------------------|
| `README.md`           | v10.0 Apex Sovereign   |
| `package.json`        | v6.1.0                 |
| `config.py`           | v6.0.0                 |
| `main.py`             | v3.2                   |
| `docker-compose.yml`  | v4.3.5 Titanium        |
| `requirements.txt`    | v6.0.0                 |
| `.env.example`        | v6.0.1                 |

**Acción:** Unificar a `v10.0.0` en todos los archivos. Definir un `VERSION` en un solo lugar (`config.py`) y referenciarlo desde los demás.

### 0.2. Health Check Fantasma (Docker No Arranca)
`docker-compose.yml` (L31) define un healthcheck contra `/api/v1/health`, pero **ese endpoint no existe** en `main.py`. Solo existen `/` y `/api/v1/status`. El contenedor nunca se marca como "healthy", y por tanto el frontend jamás arranca en Docker.

**Acción:** Crear endpoint `/api/v1/health` en `main.py` o corregir la URL del healthcheck.

### 0.3. Suite de Tests Rota
Al ejecutar `npm run test` (pytest), 2 de los 17 tests fallan en **colección** (ni siquiera llegan a correr):
- `test_fetcher.py` → `ModuleNotFoundError: engine.data.fetcher` (módulo eliminado/movido a `engine.indicators.data_utils`)
- `test_debug_ob.py` → `FileNotFoundError` (archivo de datos faltante)

**Acción:** Remapear imports, eliminar tests huérfanos, o mover a `tests/legacy/`.

### 0.4. API Key Hardcodeada en el Frontend
En `telemetryStore.ts:251`, la Security Key está en texto plano:
```typescript
const SECURITY_KEY = 'SLINGSHOT_INTERNAL_V6'; // 🔐 Sigma Security v6.0
```
Esto es visible en el JavaScript del navegador. Cualquier persona con DevTools puede copiar la key y conectarse al WebSocket.

**Acción:** Mover a variable de entorno `NEXT_PUBLIC_SECURITY_KEY` y rotar la key actual.

### 0.5. `on_event("startup")` Deprecado
FastAPI ha deprecado `@app.on_event("startup")` a favor del patrón `lifespan`. Esto generará warnings progresivos y eventual ruptura en versiones futuras.

**Acción:** Migrar a `@asynccontextmanager` lifespan en `main.py`.

### 0.6. Modelo Ollama Inconsistente
`config.py` usa `gemma3:4b` como modelo por defecto, pero `.env.example` recomienda `qwen3:8b` y `docker-compose.yml` pre-descarga `gemma3:4b`. Si el usuario sigue `.env.example` pero Docker hace pull de otro modelo, Ollama falla silenciosamente.

**Acción:** Unificar el modelo por defecto en todos los archivos. Elegir UNO: `qwen3:8b` o `gemma3:4b`.

---

## 📊 FASE 1: Auditoría Arquitectónica (Σ Sigma)

### 1.1. Código Muerto y Módulos Huérfanos
El directorio `engine/execution/` contiene **6 bridges de ejecución**:
- `binance_executor.py` — Binance Futures directo
- `bitunix_bridge.py` — Exchange Bitunix
- `delta_executor.py` — Delta Exchange
- `ftmo_bridge.py` — Prop Trading (FTMO)
- `nexus.py` — Bridge unificado (el activo según docs)
- `omega_listener.py` — Gestión de posiciones vivas

**Pregunta:** ¿Cuántos de estos están realmente activos? Si solo Nexus + Omega están en producción, los demás son deuda técnica que aumenta la superficie de ataque y la complejidad de mantenimiento.

**Acción:** Auditar cada bridge. Mover los inactivos a `engine/execution/archive/` o eliminarlos.

### 1.2. El Monolito de 40KB: `telemetryStore.ts`
Este archivo tiene **815 líneas** y maneja:
- Conexión WebSocket
- Parsing de 15+ tipos de mensaje
- Gestión de estado de velas, señales, noticias, liquidaciones, on-chain...
- Persistencia en localStorage
- Reconexión con backoff
- Watchdog de conexión
- Stale Guard

Es el archivo más frágil del proyecto. Un bug aquí rompe **todo** el frontend.

**Acción:** Extraer en módulos:
- `wsConnection.ts` → Lógica de conexión, auth, reconexión
- `messageHandlers.ts` → Dispatcher de tipos de mensaje
- `signalPersistence.ts` → localStorage + merge logic
- `telemetryStore.ts` → Solo la interfaz del store Zustand

### 1.3. `ws_manager.py` — El Otro Monolito (964 líneas)
Mismo problema en el backend. El `SymbolBroadcaster` es una clase-dios con bootstrap, streaming, fast path, slow path, depth processing, ML, on-chain, advisor, sessions... todo mezclado.

**Acción:** Ya se hizo una extracción parcial (SignalHandler, AdvisorBridge). Completar extrayendo:
- `bootstrap.py` → Lógica de inicialización y carga de historia
- `kline_processor.py` → Fast path + Slow path

### 1.4. Excepciones Silenciosas
Bloques `except:` o `except Exception:` sin logging detectados:
- `main_router.py:121` — `except Exception: pass` en el sorting de señales
- `ws_manager.py` múltiples `except: pass` en bootstrap

Estos ocultan bugs que podrían afectar la calidad de las señales de trading.

**Acción:** Reemplazar cada `except: pass` por `except Exception as e: logger.debug(f"...")` como mínimo.

---

## 🏹 FASE 2: Auditoría de Lógica de Trading (Δ Delta)

### 2.1. Validación del Veto Fractal (Gatekeeper v10)
- Ejecutar backtest comparativo: señales **con** y **sin** Gatekeeper sobre los 90 días de datos en `btcusdt_15m_1YEAR.parquet`.
- Verificar que el Gatekeeper realmente bloquea LONGs en régimen bajista L1 y viceversa.
- Auditar el `GatekeeperContext` para confirmar que los datos HTF se inyectan correctamente.

### 2.2. Precisión de Order Blocks
- Auditar `engine/indicators/structure.py` (25KB, el archivo más grande de indicadores).
- Verificar que la "Mitigación RTO" calcula correctamente el 50% del OB (Mean Threshold).
- Cross-validar con datos reales de BTC: comparar los OBs detectados vs. zonas de reacción real del precio.

### 2.3. Risk Manager (Risk:Reward)
- Confirmar que el `MAX_RISK_PCT` de `.env` (0.01 = 1%) sea respetado por `risk_manager.py` bajo todos los regímenes.
- Verificar que el SL no pueda colocarse a 0.0 o negativo bajo ninguna combinación de inputs.
- Probar edge case: ¿qué pasa si el ATR es 0? ¿El motor divide por cero?

### 2.4. Backtesting Engine
- `engine/backtest/replay_engine.py` (17KB) necesita validación independiente.
- ¿El backtest simula slippage y comisiones?
- ¿Los resultados del README (+28.4R, 68.5% WR) son reproducibles hoy con el código actual?

---

## 🔒 FASE 3: Auditoría de Seguridad

### 3.1. Secretos y Credenciales
- **API Key en Frontend:** Ya mencionada en Fase 0.4.
- **JWT Secret derivado de API Key:** En `auth.py:58-60`, si `JWT_SECRET` no está definido, el secret se deriva de `SECURITY_API_KEY + "_JWT_v6.0.1"`. Como la API Key está en el frontend, un atacante puede reconstruir el JWT secret.
- **Telegram tokens:** Verificar que nunca se logueen en caso de error de envío.

### 3.2. Sanitización de Datos
- El `sanitize_for_json()` en `json_utils.py` — ¿maneja correctamente NaN, Infinity y valores extremos de pandas?
- ¿Hay protección contra inyección en los parámetros de la URL del WebSocket? (e.g., `symbol` y `interval`)

### 3.3. Rate Limiting
- No existe rate limiting en los endpoints REST (`/api/v1/analyze/{symbol}`, etc.).
- Un actor malicioso podría hacer flood de análisis y saturar el backend.

---

## ⚡ FASE 4: Auditoría de Rendimiento (Ω Omega)

### 4.1. Latencia End-to-End
- Medir el pipeline completo: `Binance WS → ws_manager → router → broadcast → frontend render`.
- Objetivo: sub-30ms para el fast path (inter-vela).
- Utilizar `scripts/latency_benchmark.py` y `scripts/latency_breakdown.py`.

### 4.2. Memory Leaks
- `_live_buffer` es un deque(maxlen=300) — correcto.
- Pero `_history` es una lista sin límite. ¿Crece indefinidamente durante sesiones largas?
- `_subscribers` — ¿se limpian correctamente los clientes zombies?

### 4.3. Frontend Performance
- `TradingChart.tsx` (34KB) y `QuantDiagnosticPanel.tsx` (28KB) son componentes masivos.
- ¿Usan `React.memo` o `useMemo` para evitar re-renders innecesarios?
- ¿El spread `...d` en el tactical update (`telemetryStore.ts:469`) causa renders excesivos por crear objetos nuevos en cada tick?

---

## 📖 FASE 5: Auditoría de Documentación

### 5.1. Documentación vs. Realidad (Sincronizado v10.2.0)

| Claim en Docs                     | Estado Real                            |
|-----------------------------------|----------------------------------------|
| "25+ Tests operativos"            | ✅ 17+ tests (Hardening completado)    |
| "Qwen-3:8B (vía Ollama)"         | ✅ Sincronizado en config y advisor.py |
| "Sub-30ms Latency"               | ⏳ En verificación (Fase 4 pendiente)  |
| "+28.4R / 68.5% WR"              | ⚠️ Validando en Backtest v10           |
| "Nexus Execution Bridge activo"   | ✅ Único puente (Bridges muertos eliminados) |

### 5.2. Documentación Faltante
- **No existe un CHANGELOG.md** — No hay historial de cambios entre versiones.
- **No existe CONTRIBUTING.md** — No hay guía para colaboradores.
- **No existe documentación de la API REST** — El Swagger de FastAPI existe pero no está customizado.
- **No hay diagrama de flujo de datos** actualizado (el del README es simplificado).

---

## 🚀 FASE 6: DevOps y Automatización (Nueva)

### 6.1. CI/CD Inexistente
- No hay GitHub Actions, ni tests automatizados en push/PR.
- No hay linting automatizado (eslint existe pero no corre en CI).
- No hay build verification para el frontend.

**Acción:** Crear `.github/workflows/ci.yml` con:
1. Python tests (pytest)
2. TypeScript build check (`next build`)
3. Linting (eslint + pylint/ruff)

### 6.2. Dependencias
- Ejecutar `npm audit` y `pip audit` para vulnerabilidades conocidas.
- `requirements.txt` no tiene versiones pinneadas exactas (usa `>=`), lo que puede causar builds irreproducibles.

### 6.3. Archivos Residuales
- `scratch/` y `tmp/` en la raíz del proyecto — ¿deberían estar en `.gitignore`?
- `engine/tests/legacy/` — 2 tests abandonados con `__pycache__`.

---

## 📋 Matriz de Prioridades (Actualizada)

| # | Hallazgo | Severidad | Esfuerzo | Fase | Estado |
|---|----------|-----------|----------|------|--------|
| 1 | API Key hardcodeada en frontend | 🔴 CRÍTICO | 30 min | 0 | ✅ FIX |
| 2 | JWT Secret derivable desde frontend | 🔴 CRÍTICO | 1 hora | 0 | ✅ FIX |
| 3 | Health check fantasma en Docker | 🟠 ALTO | 15 min | 0 | ✅ FIX |
| 4 | Tests rotos (imports huérfanos) | 🟠 ALTO | 30 min | 0 | ✅ FIX |
| 5 | Drift de versiones en 7 archivos | 🟡 MEDIO | 20 min | 0 | ✅ FIX |
| 6 | Modelo Ollama inconsistente | 🟡 MEDIO | 10 min | 0 | ✅ FIX |
| 7 | Monolito telemetryStore.ts (815 LOC) | 🟡 MEDIO | 4 horas | 1 | ✅ FIX |
| 8 | Monolito ws_manager.py (964 LOC) | 🟡 MEDIO | 4 horas | 1 | ✅ FIX |
| 9 | 5 execution bridges muertos | 🟡 MEDIO | 2 horas | 1 | ✅ FIX |
| 10 | Excepciones silenciosas (except: pass) | 🟡 MEDIO | 1 hora | 1 | ✅ FIX |

---

## 📈 Estado de la Auditoría (v10.2.0)

| Versión | Milestone | Estado |
|---------|-----------|--------|
| **v10.0.0** | **Estabilización (Fase 0)** | ✅ **COMPLETADO**. |
| **v10.1.0** | **Modularización (Fase 1)** | ✅ **COMPLETADO**. Arquitectura desacoplada y Hardening de excepciones. |
| **v10.2.0** | **Lógica Delta (Fase 2)** | 🟢 **EN PROCESO**. Unificación de fragmentación 60/20/20. |
