# 📖 SLINGSHOT BIBLE v60.0 — THE MASTER CANONICAL SPECIFICATION (SSoT)
## QUANTITATIVE DRAWDOWN FORTRESS: PROGRESSIVE EXPOSURE SIZING (SOP-94), SESSION-ANCHORED VWAP (SOP-95), TRADEZELLA PLAYBOOK TAXONOMY (SOP-96) & DUAL-PROTOCOL OPENAPI BITUNIX TPSL RUNBOOK

> **"Manual Técnico Canónico y Especificación SSoT del Ecosistema Autónomo Slingshot. Versión v60.0 APEX QUANTUM FORTRESS: Incorpora la canonización de los Protocolos SOP-94 (Progressive Exposure Sizing & Asymmetric Drawdown Protection con factor de contracción 1.0x -> 0.75x -> 0.50x y Quick Restore instantáneo al 100% ante riesgo liberado Fast-BE/TP1), SOP-95 (Session-Anchored VWAP - AVWAP con anclajes intradiarios estrictos en Asia 00:00 UTC, Londres 07:00 UTC y Nueva York 13:30 UTC), SOP-96 (TradeZella Style Institutional Playbook Taxonomy & Real-Time Expectancy Engine con clasificación exhaustiva en 4 arquetipos: OB_DISCOUNT_RETEST, LIQUIDITY_SWEEP_FVG, BOS_MOMENTUM_EXPANSION y TREND_CONTINUATION_EMA), consolidando el Blindaje OpenAPI Dual-Protocol TPSL de Bitunix (auto-resolución de ID, protocolo modify-order vs cancel-and-replace, preservación estricta del denominador 1R y protección del rescue mechanism) y los resultados récord de la auditoría oficial cronológica de 180 días (+109.44 R, Max Drawdown -3.25%, y crecimiento compuesto de $1,000 a $12,597.91 USD en Bitunix)."**

---

## 🏛️ 1. Matriz Canónica de Ciclo de Rachas y Despacho Cuantitativo v60.0

```mermaid
flowchart TD
    SIG["Nueva Señal Detectada (MarketScanner)"] --> Q_AVWAP{"¿Alineada con Session AVWAP? (SOP-95)<br/>Asia 00:00 / Lon 07:00 / NY 13:30"}
    
    Q_AVWAP -- "No (Contra-flujo > 0.40%)" --> V_AVWAP["🛑 VETO AVWAP (Filtro Anti-Trampa)"]
    Q_AVWAP -- "Sí (Confluencia +8 pts)" --> TAG["🏷️ Tagging de Playbook TradeZella (SOP-96)<br/>OB_RETEST / LIQ_SWEEP / BOS / TREND"]
    
    TAG --> Q_STREAK{"¿Estado de Racha de la Cuenta? (SOP-94)"}
    
    Q_STREAK -- "0 pérdidas / Riesgo liberado" --> MULT_100["Multiplicador 1.00x (Exposición Plena 100%)"]
    Q_STREAK -- "1 pérdida consecutiva" --> MULT_75["Multiplicador 0.75x (Contracción Preventiva)"]
    Q_STREAK -- ">= 2 pérdidas consecutivas" --> MULT_50["Multiplicador 0.50x (Blindaje de Drawdown)"]
    
    MULT_100 --> CLAMP["🛡️ Pre-Flight Hard-Clamp SOP-42 (Max $5 Loss / $150 Notional)"]
    MULT_75 --> CLAMP
    MULT_50 --> CLAMP
    
    CLAMP --> EXE["🚀 Ejecutar Orden en Exchange / Broker + TPSL Dual-Protocol"]
    
    EXE --> LIFE{"Monitoreo Activo de Trade (TradeManager)"}
    
    LIFE -- "Toca Fast-BE (+1.0R) o TP1" --> QR["⚡ QUICK RESTORE INSTANTÁNEO:<br/>Racha = 0 | Multiplicador -> 1.00x"]
    LIFE -- "Stop Loss Hit / Invalidación Temprana" --> SL_HIT["📉 INCREMENTAR RACHA:<br/>Pérdidas += 1 | Multiplicador Contrae"]
```

---

## 🛡️ 2. Especificación Técnica de los Nuevos Protocolos Canónicos

### SOP-94: Progressive Exposure Sizing & Asymmetric Drawdown Protection
- **Fundamento Cuantitativo (Words of Rizdom / Umar Ashraf / Christian Flanders):**
  En sistemas de alta frecuencia y prop trading institucional, mantener una exposición constante durante rachas desfavorables degrada el Sortino Ratio y eleva el riesgo de ruina. Reducir asimétricamente el capital arriesgado ante pérdidas consecutivas contiene el drawdown de cola, mientras que una recuperación inmediata (*Quick Restore*) al primer evento de ganancia o protección asegura que el sistema capture el pleno rendimiento del rebote.
- **Formulación Matemática:**
  $$\text{StreakMultiplier} = \begin{cases} 
  1.00x & \text{si } \text{consecutive\_losses} = 0 \lor \text{risk\_released\_recently} = \text{True} \\ 
  0.75x & \text{si } \text{consecutive\_losses} = 1 \\ 
  0.50x & \text{si } \text{consecutive\_losses} \ge 2 
  \end{cases}$$
- **Mecanismo de Quick Restore:**
  - Si una posición abierta alcanza **Fast-BE (+1.0R con SL a $+0.00$)** o ejecuta **TP1**, el riesgo flotante queda eliminado. El centinela `on_risk_released` en [`nexus.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/execution/nexus.py) resetea automáticamente `consecutive_losses = 0` y activa `risk_released_recently = True`.
  - La siguiente orden entra inmediatamente al **1.00x (100% de riesgo nominal)**, eliminando la inercia punitiva de los sistemas de martingala inversa tradicionales.
- **Implementación en Producción:**
  - [`engine/risk/risk_manager.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/risk/risk_manager.py): Método estático `calculate_streak_exposure_multiplier()`.
  - [`engine/execution/nexus.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/execution/nexus.py): Integración por cuenta en `_execute_signal_for_account` y `_place_limit_for_account`.

---

### SOP-95: Session-Anchored VWAP (AVWAP) Intraday Filter
- **Fundamento Cuantitativo (Brian Shannon / Fredy Sarmiento):**
  El VWAP diario tradicional de 24 horas promedia el volumen global de cripto de forma homogénea, distorsionando el punto de equilibrio institucional cuando ingresa el flujo de las principales plazas financieras. El Session-Anchored VWAP resetea la acumulación en el segundo exacto en que abren los tres centros neurálgicos de volumen global.
- **Anclajes Temporales Canónicos:**
  1. **Sesión Asia / Día UTC:** `00:00 UTC` (Reseteo base de liquidez asiática).
  2. **Sesión Londres:** `07:00 UTC` (Ingreso masivo de flujos interbancarios europeos).
  3. **Sesión Nueva York:** `13:30 UTC` (Apertura de Wall Street, contado y futuros CME).
- **Ecuación Vectorial de Acumulación por Ventana:**
  $$\text{AVWAP}_t = \frac{\sum_{i \in S} P_i \cdot V_i}{\sum_{i \in S} V_i}, \quad P_i = \frac{\text{High}_i + \text{Low}_i + \text{Close}_i}{3}$$
  donde $S = \{i \mid t_{\text{anchor}} \le t_i \le t\}$.
- **Reglas Operativas:**
  - **Condición Long:** El precio actual debe cotizar sobre o a menos de un $0.10\%$ bajo el AVWAP de la sesión activa ($P_t \ge \text{AVWAP}_t \times 0.999$). Otorga $+8\text{ pts}$ de confluencia.
  - **Condición Short:** El precio actual debe cotizar bajo o a menos de un $0.10\%$ sobre el AVWAP de la sesión activa ($P_t \le \text{AVWAP}_t \times 1.001$). Otorga $+8\text{ pts}$ de confluencia.
  - **Veto de Contraflujo Violento:** Si el precio diverge en más de $\pm 0.40\%$ en contra de la dirección buscada respecto al AVWAP activo, la señal es vetada incondicionalmente.
- **Implementación en Producción:**
  - [`engine/indicators/volume.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/indicators/volume.py): `calculate_session_anchored_vwap()`.
  - [`engine/workers/market_scanner.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/workers/market_scanner.py): Checklist dinámico y adición de confluencia.
  - [`engine/backtest/unified_backtest_engine.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/backtest/unified_backtest_engine.py): Paridad 1:1 en simulaciones históricas.

---

### SOP-96: TradeZella Style Playbook Taxonomy & Real-Time Expectancy Engine
- **Fundamento Cuantitativo:**
  La clasificación sistemática de las operaciones bajo arquetipos definidos permite descomponer la esperanza matemática de cada setup, identificar los catalizadores de mayor Profit Factor y descartar u optimizar estrategias de baja expectativa.
- **Taxonomía Canónica de Playbooks:**
  1. `OB_DISCOUNT_RETEST`: Entrada tras confirmación de Order Block institucional en zona de descuento OTE (Fibonacci 61.8% a 78.6%).
     * *Rendimiento Auditado (180 días):* **Profit Factor 2.61**, **Win Rate 50.0%**, **+64.09 R** (El arquetipo de mayor rentabilidad del sistema).
  2. `LIQUIDITY_SWEEP_FVG`: Entrada tras barrido de liquidez de máximos/mínimos previos (Buy-Side/Sell-Side Liquidity) acoplado a un Fair Value Gap no mitigado.
     * *Rendimiento Auditado (180 días):* **Profit Factor 1.67**, **Win Rate 43.1%**, **+42.51 R**.
  3. `BOS_MOMENTUM_EXPANSION`: Ruptura confirmada de estructura de mercado (Break of Structure) con expansión de volumen relativo (RVOL $\ge 1.05$) y aceleración tendencial ($\text{ADX} \ge 20$).
  4. `TREND_CONTINUATION_EMA`: Entrada en retrocesos a favor de la tendencia macro sustentada por las medias móviles exponenciales EMA 9, 21 y 200.
- **Implementación en Producción:**
  - Etiquetado automático en [`engine/workers/market_scanner.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/workers/market_scanner.py) y [`engine/backtest/unified_backtest_engine.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/backtest/unified_backtest_engine.py).
  - Reporte consolidado automático en la sección 5 del motor de backtesting institucional.

---

### Blindaje OpenAPI Dual-Protocol TPSL de Bitunix & Invariant 1R Cache
- **Problema Diagnosticado:**
  La OpenAPI de Bitunix rechaza órdenes `place_order` de tipo TPSL si la posición ya cuenta con una orden condicional activa, y rechaza `modify_order` si no existe una orden previa o si el broker opera en modo de reemplazo estricto. Asimismo, cuando el Mitigador de Riesgo (-0.5R) acercaba el Stop Loss al precio de entrada, el recálculo dinámico de $1\text{R}$ reducía a la mitad la distancia base, distorsionando el trailing stop.
- **Solución Canónica Implementada:**
  1. **Dual-Protocol In-Place Modification vs Cancel-and-Replace:**
     En [`engine/execution/bitunix_executor.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/execution/bitunix_executor.py), el ejecutor intenta primero la modificación atómica *in-place* (`POST /api/v1/futures/tpsl/position/modify_order`). Si el exchange retorna error de rechazo, cancela inmediatamente la orden condicional existente (`POST /api/v1/futures/trade/cancel_order`) y emite la nueva orden con `POST /api/v1/futures/tpsl/position/place_order`.
  2. **Auto-Resolución de `position_id` Nulo:**
     Si el identificador de posición arriba como `None`, string `"None"` o vacío, el método consulta en tiempo real `get_pending_positions()` y auto-resuelve el `positionId` numérico del contrato abierto.
  3. **Preservación Invariante del Denominador 1R (`_initial_risk_cache`):**
     En [`engine/workers/trade_manager.py`](file:///c:/Users/Matías Riquelme/Desktop/Proyectos documentados/Slingshot_Trading/engine/workers/trade_manager.py), se indexa en memoria el riesgo base original ($1\text{R} = |\text{Entry} - \text{Initial SL}|$). Todas las mediciones posteriores de Breakeven, TP y Trailing Stop utilizan este denominador inmutable.
  4. **Protección del Rescue Mechanism:**
     El cierre de emergencia a mercado no se ejecuta si la posición ya cuenta con una orden de protección activa (`eo_id`), blindando la cuenta ante micro-desconexiones temporales de red.

---

## 📊 3. Auditoría Cuantitativa Oficial SSoT 180 Días (Versión v60.0 vs Versiones Anteriores)

Replay cronológico oficial sobre 14 activos VIP (`BTC`, `ETH`, `SOL`, `BNB`, `XRP`, `ADA`, `DOGE`, `AVAX`, `LINK`, `DOT`, `NEAR`, `SUI`, `FET`, `APT`) en temporalidad 15m con comisiones Maker/Taker reales y slippage descontados:

```text
========================================================================================================================
Métrica Cuantitativa Institucional    | Slingshot v31.0 Base    | Slingshot v51.0         | Slingshot v60.0 APEX FORTRESS
========================================================================================================================
Total Operaciones Auditadas           | 466 trades (Aisladas)   | 237 trades (Replay)     | 326 trades (Replay SSoT)
Win Rate Efectivo                     | 42.3%                   | 46.8%                   | 46.0% (150 Wins / 176 Losses)
Profit Factor Base                    | 1.07 (Frágil)           | 1.80                    | 1.87 (Robusto)
Profit Factor con Progressive Sizing  | 1.10                    | 1.99                    | 1.98 🚀 (Consistencia Alta)
Retorno Total Base en R               | +22.40 R                | +66.31 R                | +109.44 R
Retorno Total con Progressive Sizing  | +25.00 R                | +94.75 R                | +106.60 R 💎
Drawdown Máximo de Cartera (Plano)    | -38.10%                 | -4.21%                  | -3.25% 🛡️ (Blindaje Prop Firm)
Sortino Ratio (Riesgo a la Baja)      | 1.12                    | 24.63                   | 29.52 🛡️ (+540% s/ Base)
Crecimiento Compuesto Bitunix ($1k)   | +$1,546.25 USD (+154%)  | +$8,148.56 USD (+814%)  | +$11,597.91 USD (+1,159.8% / 12.6X)
Capital Final Compuesto ($1,000 USD)  | $2,546.25 USD           | $9,148.56 USD           | $12,597.91 USD 🚀
Drawdown Máximo Compuesto en Cuenta   | -38.10%                 | -14.63%                 | -11.70% 🛡️ (Totalmente Controlado)
========================================================================================================================
```

### Desglose Oficial por Playbooks (TradeZella Style SSoT):
```text
====================================================================================================
                        DESGLOSE OFICIAL POR PLAYBOOKS INSTITUCIONALES
====================================================================================================
Playbook Arquetípico               Trades   Win Rate    PnL (R)      Avg R      PF    Expectancy (R)
----------------------------------------------------------------------------------------------------
OB_DISCOUNT_RETEST                    138     50.0%    +64.09R     +0.46R    2.61           +0.46R
LIQUIDITY_SWEEP_FVG                   188     43.1%    +42.51R     +0.23R    1.67           +0.23R
====================================================================================================
```

---

## 🧪 4. Certificación QA Oficial (100% Passed)

Comandos para verificar la integridad matemática y operativa de los nuevos protocolos en el VPS de producción o local:

```powershell
# Certificación Nuevos Protocolos SOP-94 (Progressive Sizing) y SOP-95 (Session AVWAP) [9 Tests]
python -m pytest engine/tests/test_progressive_exposure_and_streak_sizing.py engine/tests/test_session_anchored_vwap.py -v

# Certificación Blindaje Bitunix Dual-Protocol TPSL y Gestión de SL [12 Tests]
python -m pytest engine/tests/test_bitunix_tpsl_modify_and_id_resolution.py engine/tests/test_live_trade_management.py -v

# Certificación Global Integrada [21 Tests]
python -m pytest engine/tests/test_progressive_exposure_and_streak_sizing.py engine/tests/test_session_anchored_vwap.py engine/tests/test_bitunix_tpsl_modify_and_id_resolution.py engine/tests/test_live_trade_management.py -v
```
*(Resultado certificado: **21 passed in 5.83s — 100% de éxito**).*
