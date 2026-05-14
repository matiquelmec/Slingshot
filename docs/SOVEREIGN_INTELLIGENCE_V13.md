# 🧠 SOVEREIGN INTELLIGENCE v13.1 — Yosh Order Flow Edition
> **"From algorithmic terminal to institutional Order Flow intelligence."**

## 1. Introducción
La evolución **v13.1 "Yosh Order Flow Edition"** extiende los tres pilares de v13.0 (Memoria de Errores, Riesgo Adaptativo, Auditoría IA) con inteligencia de **Order Flow institucional** basada en la metodología de Yosh ($2M+ en payouts de prop firms).

---

## 2. El Módulo Black Box (Memoria de Errores)
**Archivo:** `engine/core/memory.py`
**Responsabilidad:** Prevenir la repetición de patrones perdedores.

### Funcionamiento:
1. **Fingerprinting**: Al cerrar un trade en pérdida (SL), el sistema genera una huella digital que incluye:
   - Régimen de mercado (CHOPPY, TRENDING, etc.)
   - Volumen Relativo (RVOL)
   - Sesgo HTF
   - Dirección de la señal.
2. **Persistence**: Se guarda en `data/blackbox.json`.
3. **Similarity Veto**: Antes de aprobar una señal, el `Gatekeeper` consulta a la Black Box. Si el patrón actual coincide en un >85% con una pérdida registrada, la señal es vetada con el motivo `VETO_BY_MEMORY`.

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

---

## 4. AI Validator Agent (Auditoría Narrativa)
**Archivo:** `engine/core/validator.py`
**Responsabilidad:** Segundo analista para la "Zona Gris" (60-80%).

### Pipeline de Inferencia:
1. **Trigger**: Solo se activa para señales con score entre 60% y 80%.
2. **Context Injection**: Envía al modelo local (**gemma3:4b**) el régimen, el checklist de confluencia y la estructura SMC.
3. **Verdict**:
   - **VEST**: Aprobación narrativa confirmada.
   - **VETO**: Rechazo por incongruencia narrativa (Ej: Short en zona de demanda institucional).

---

## 5. Cambios en la Arquitectura
Para soportar la inferencia IA (asíncrona) sin bloquear el flujo de ticks en tiempo real:
- `SignalGatekeeper.process` ahora es **async**.
- `MainRouter.process_market_data` ahora es **async**.
- `BroadcasterPipeline` gestiona las llamadas asíncronas directamente, eliminando el overhead de hilos para estas tareas de decisión.

---

## 6. Verificación de Integridad
- **Tests**: Se recomienda ejecutar `pytest engine/tests` para validar que los cambios asíncronos no rompieron el pipeline táctico.
- **Data**: Asegurarse que el directorio `data/` tenga permisos de escritura para el archivo `blackbox.json`.

---

## 7. Visual Sovereign (UI Integration)
La terminal **DELTA** ha sido actualizada para reflejar la profundidad analítica del motor v13:
- **Intelligence Status Monitor**: En el `MarketContextPanel`, permite monitorear en tiempo real la conectividad con Ollama (gemma3) y el estado de carga de la Black Box.
- **AI Narrative Audit Card**: Las tarjetas de señal ahora incluyen un panel dedicado que muestra el razonamiento de la IA, el nivel de confianza y el veredicto estructural.
- **Dynamic Risk Badge**: Se visualiza el escalado dinámico de riesgo (0.25% - 2.0%) calculado por el `RiskManager`.
- **v13 Status Integration**: El sistema de semáforos del frontend ahora reconoce y renderiza estados `AI_VETO` y `BLOCKED_BY_MEMORY` con iconografía específica.

---

## 8. 🏦 Yosh Order Flow Intelligence (v13.1)

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

### 8.3 Yosh Confluence Scoring
**Archivo:** `engine/core/confluence.py` — Bloque "Yosh Order Flow"

| Condición | Bonus | Descripción |
|-----------|-------|-------------|
| Precio dentro de Value Area | +10 pts | El trade ocurre donde se concentra el valor real |
| Rechazo en VAH/VAL (proximidad <0.3%) | +15 pts | Reacción en los extremos del valor |
| Trampa Institucional confirmada (LAF/LBF) | +25 pts | Barrido de liquidez + fallo = señal de alta convicción |

---

## 9. 📈 Averaging Up — Escalado en Ganancia (v13.1)
**Archivo:** `engine/execution/nexus.py` — `_omega_centinel_loop()`

### Condiciones de Activación:
1. La posición ya tiene el SL en **Breakeven** (riesgo = 0).
2. El precio retestea el **POC** del Volume Profile actual.
3. No se ha escalado previamente (`averaging_up_done = False`).

### Ejecución:
- Se añade un **50% del tamaño original** a la posición.
- Se marca `averaging_up_done = True` para evitar escalados múltiples.
- **Regla de Oro**: Nunca se promedian posiciones perdedoras (anti-averaging-down).

---

## 10. Frontend Yosh (Visualización v13.1)
**Archivos:**
- `app/components/ui/TradingChart.tsx` — Overlays de Value Area y Trap Markers.
- `app/store/indicatorsStore.ts` — Toggles `value_area` y `traps`.

### Elementos Visuales:
| Elemento | Descripción | Control |
|----------|-------------|----------|
| Zona sombreada dorada (VAH→VAL) | Área de Valor del perfil de volumen | Toggle `Yosh Value Area` |
| Línea dorada sólida (POC) | Point of Control — imán de precio | Toggle `Yosh Value Area` |
| Marcador 🪤 sobre vela | Trampa LAF/LBF detectada | Toggle `Market Traps` |

---
*v13.1 Yosh Order Flow Edition — Institutional Order Flow Intelligence.*
*Hardened & Evolved by Antigravity — May 14, 2026*
