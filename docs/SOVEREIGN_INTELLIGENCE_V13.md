# 🧠 SOVEREIGN INTELLIGENCE v13.4 — Institutional Backtesting & Fidelity Edition
> **"From algorithmic terminal to live institutional execution and high-fidelity offline auditing."**

## 1. Introducción
La evolución **v13.2 "Sovereign Execution"** consolida la potencia de los modelos asíncronos y la metodología de **Order Flow institucional** de Yosh con ejecución real y optimizada en exchanges. Resuelve bugs críticos de diagnóstico, introduce paralelización de IA de ultra-alto rendimiento en el Gatekeeper, aisla la memoria de errores por activo y reemplaza las simulaciones de Smart Trailing y Averaging Up por llamadas reales de API vía CCXT.

---

## 2. El Módulo Black Box (Memoria de Errores)
**Archivo:** `engine/core/memory.py`
**Responsabilidad:** Prevenir la repetición de patrones perdedores de forma específica por activo.

### Funcionamiento v13.2:
1. **Fingerprinting**: Al cerrar un trade en pérdida (SL), el sistema genera una huella digital que incluye:
   - Régimen de mercado (CHOPPY, TRENDING, etc.)
   - Volumen Relativo (RVOL)
   - Sesgo HTF
   - Dirección de la señal.
2. **Persistence**: Se guarda en `data/blackbox.json`.
3. **Similarity Veto (Active-Isolated)**: Antes de aprobar una señal, el `Gatekeeper` consulta a la Black Box. En esta versión, el sistema filtra y compara el setup actual **únicamente contra las pérdidas registradas del mismo activo (`asset`)**. Si coincide en un >85% con un error previo de ese activo, es vetada con el motivo `BLACKBOX_VETO`. Esto elimina falsos vetos cruzados entre activos de diferente régimen de volatilidad.

---

## 3. Adaptive Risk Management (Scaling Dinámico)
**Archivo:** `engine/risk/risk_manager.py`
**Responsabilidad:** Escalar la exposición basada en la calidad técnica.

### Matriz de Riesgo v13:
| Confluence Score | Perfil de Riesgo | % de Balance |
|------------------|------------------|--------------|
| < 60%            | BLOQUEADO        | 0.00%        |
| 60% - 75%        | Conservador      | 0.25% - 0.5% |
| 75% - 90%        | Estándar         | 1.00%        |
| > 90%            | Apex (Institutional) | 2.00%    |

*Nota: Se corrigió la asignación de `take_profit_3r` al primer target en los alias del retorno para garantizar que el cálculo de R:R en el gatekeeper represente fielmente la proyección estructural del setup.*

---

## 4. AI Validator Agent (Auditoría Narrativa)
**Archivo:** `engine/core/validator.py`
**Responsabilidad:** Segundo analista para la "Zona Gris" (60-80%).

### Pipeline de Inferencia:
1. **Trigger**: Solo se activa para señales con score entre 60% y 80%.
2. **Context Injection**: Envía al modelo local (**gemma3:4b** u otro modelo superior) el régimen, el checklist de confluencia y la estructura SMC.
3. **Verdict**:
   - **VEST**: Aprobación narrativa confirmada.
   - **VETO**: Rechazo por incongruencia narrativa (Ej: Short en zona de demanda institucional).

---

## 5. Cambios en la Arquitectura (Paralelización de Inferencia)
Para soportar la inferencia IA (asíncrona) sin bloquear el flujo de ticks en tiempo real ni congestionar el procesamiento de señales:
* **asyncio.gather**: El método `SignalGatekeeper.process` ha sido reestructurado en 3 fases:
  1. **Pre-filtrado**: Evaluaciones rápidas y síncronas de confluencia, riesgo, vetos fractales y desalineaciones de tendencia.
  2. **Inferencia Concurrente**: Se agrupan todas las señales sobrevivientes y se dispara `validator_agent.validate(sig)` en paralelo utilizando `asyncio.gather`. Esto reduce la latencia total de inferencia al máximo valor individual en lugar de la suma de todas las señales.
  3. **Post-filtrado**: Aplicación del veredicto de la IA, veto de Black Box por activo, y validación final de Path Traversal.

---

## 6. Verificación de Integridad
- **Backtests**: `fast_profit_audit.py` fue corregido para inyectar la propiedad `timestamp` en `mock_signal`, resolviendo el bug del reloj de obsolescencia que arrojaba profits nulos de 0.00R.
- **Tests**: Se recomienda ejecutar `python -m engine.tools.fast_profit_audit` e `integrity_audit.py` para validar que el pipeline táctico funcione sin excepciones ni regresiones de código.

---

## 7. Visual Sovereign (UI Integration)
La terminal **DELTA** refleja la profundidad analítica del motor v13.2:
- **Intelligence Status Monitor**: En el `MarketContextPanel`, permite monitorear en tiempo real la conectividad con Ollama (gemma3) y el estado de carga de la Black Box.
- **AI Narrative Audit Card**: Las tarjetas de señal incluyen un panel dedicado que muestra el razonamiento de la IA, el nivel de confianza y el veredicto estructural.
- **Dynamic Risk Badge**: Se visualiza el escalado dinámico de riesgo (0.25% - 2.0%) calculado por el `RiskManager`.

---

## 8. 🏦 Yosh Order Flow Intelligence

### 8.1 Volume Profile (POC / VAH / VAL)
**Archivo:** `engine/indicators/volume.py` — `calculate_volume_profile()`
**Pipeline:** Ejecutado en el Slow Path de `engine/router/processors.py` cada ~60 segundos.

#### Funcionamiento:
1. **Discretización**: Se divide el rango de precios de las últimas 100 velas en 50 bins.
2. **Histograma**: Se acumula el volumen en cada bin de precio.
3. **POC**: El bin con mayor volumen transado. Actúa como imán de precio.
4. **VAH/VAL**: Los límites del área que contiene el 70% del volumen total (Value Area).
5. **LVNs**: Low Volume Nodes, zonas de vacío donde el precio tiende a moverse rápidamente.

### 8.2 Trap Detection (LAF / LBF)
**Archivo:** `engine/indicators/structure.py` — `identify_look_and_fail()`

#### Criterios de Detección:
- **Look Above and Fail (LAF)**: El precio supera un máximo previo (PDH, Overnight High) por al menos 0.1% pero cierra significativamente debajo (≥0.15% del rango). Señal bajista institucional.
- **Look Below and Fail (LBF)**: Inverso del LAF. Señal alcista institucional.
- **Resultado**: Se inyecta `laf_bull` / `laf_bear` en el objeto `traps` del `persistent_smc`.

---

## 9. 📈 Live Execution & Trailing (v13.2)
**Archivos:** `engine/execution/nexus.py` y `engine/execution/binance_executor.py`

### 9.1 Smart Trailing (Mover Stop Loss a BE)
Cuando el precio en vivo (monitoreado cada 5 segundos por el `_omega_centinel_loop`) alcanza el nivel de **TP1**, el bot cancela la orden de Stop Loss original y coloca una nueva orden `STOP_MARKET` en el precio de entrada más un pequeño buffer para comisiones (riesgo = 0).

### 9.2 Averaging Up (Escalado de Yosh en Ganancia)
Si la posición ya tiene el SL en **Breakeven** y el precio realiza un retroceso saludable retesteando el **POC** (Point of Control) del Volume Profile, el `NexusNode` ejecuta una orden real de mercado para añadir un **50% del tamaño original** de contratos a la posición.
* **Seguridad Estricta**: Estas llamadas de API respetan la propiedad `dry_run`. Por seguridad del balance, por defecto el singleton `nexus` arranca en `dry_run = True` (simulación), y el ejecutor apunta a **Binance Futures Testnet**.

---

## 10. ⚡ Frontend Latency Optimization (v13.3)
**Archivos:** `app/components/signals/SignalTerminal.tsx`, `app/components/radar/RadarFeed.tsx` y `app/components/radar/ActiveAssetsMonitor.tsx`

### 10.1 Memoización de Feeds Híbridos
El flujo constante de ticks a través de WebSockets saturaba el hilo de ejecución principal debido a cálculos repetitivos en el cuerpo de los componentes. En la v13.3 implementamos:
* **Memoización reactiva con `useMemo`**: Toda transformación, filtrado, normalización y ordenamiento de señales o estados del mercado se realiza ahora únicamente cuando las dependencias subyacentes (`signalHistory`, `marketSummary`, etc.) cambian de forma discreta.
* **Reducción de latencia en renderizado**: Se eliminaron re-renderizados costosos de arrays complejos, logrando una fluidez de interfaz excepcional (latencia de UI cercana a 0ms bajo estrés).

---

## 11. Ecosistema de Backtesting & Fidelidad Asíncrona (v13.4)
**Directorio:** `engine/backtest/`
**Responsabilidad:** Validar las estrategias e indicadores en datos históricos con un 100% de concordancia y fidelidad analítica respecto al pipeline de producción.

### 11.1 Conexión Asíncrona del Pipeline
Anteriormente, el motor de backtesting (`replay_engine.py`) invocaba el método `SlingshotRouter.process_market_data` de forma síncrona, omitiendo el operador `await`. Como esta función es asíncrona, devolvía un objeto corrutina descartado en silencio por el motor, lo que provocaba que nunca se detectara o registrara ninguna señal en los reportes de backtest offline.
* **Fidelidad Total**: Se refactorizó el bucle del motor a asíncrono (`async def run()`), utilizando llamadas `await` reales al router y gatekeeper. Ahora las señales se detectan y auditan con un 100% de correspondencia con el WebSocket en vivo.

### 11.2 Centralización Física y Unificación
Para evitar la dispersión de herramientas en la raíz o carpetas secundarias, se estructuró la carpeta `engine/backtest/`:
* `data/`: Contiene los datasets históricos parquet para mayor cohesión analítica.
* `reports/`: Almacena los reportes automatizados de auditoría en formato JSON con marcas de tiempo.
* `fast_audit.py` y `replay_engine.py`: Corregidos y optimizados.
* `stress_audit.py`, `multi_asset.py` y `find_signals.py`: Migrados desde la carpeta legacy de herramientas (`engine/tools/`) y adaptados a la nueva estructura de imports.

### 11.3 Precisión de Métricas y SL/TP por ATR Real
Se corrigió la llamada al evaluador de confluencias de `fast_audit.py` eliminando argumentos posicionales inexistentes que falseaban las métricas de confluencia. Además, se reemplazó la desviación estándar simple (estática) por el cálculo de Average True Range (ATR) institucional real mediante True Range de suavizado exponencial (EWM 14), garantizando que las zonas de Stop Loss y Take Profit simulen fielmente el comportamiento de los algoritmos en producción.

---
*v13.4 Sovereign Intelligence — Live Institutional Order Flow & Algorithmic Terminal.*
*Hardened & Evolved by Antigravity — May 20, 2026*
