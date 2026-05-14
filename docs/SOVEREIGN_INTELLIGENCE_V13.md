# 🧠 SOVEREIGN INTELLIGENCE v13.0 — Especificación Técnica
> **"The transition from algorithmic terminal to autonomous intelligence."**

## 1. Introducción
La evolución **v13.0 "Sovereign Intelligence"** introduce tres pilares fundamentales diseñados para la resiliencia institucional: Memoria de Errores, Riesgo Adaptativo y Auditoría de Narrativa por IA.

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
*v13.0 Sovereign Intelligence — Hardened by Antigravity — May 14, 2026*
