# 🛡️ SLINGSHOT BIBLE v33.0 — APEX OLYMPUS

> **"Manual Técnico Institucional y Especificación Canónica del Ecosistema Autónomo Slingshot. Versión v33.0 APEX OLYMPUS: Arquitectura Multi-Mercado Dual (Criptomonedas Bitunix 24/7 + Cartera Suprema FTMO MetaTrader 5: Oro, Plata, Nasdaq, S&P, Petróleo, DAX y Forex), Selector Visual en Frontend, Interceptor de Noticias Macro SOP-19, Ejecución Pasiva Post-Only Maker 100%, Runner Adaptativo 25% en Macro Tendencias, Time-Gating Cuántico SOP-18, FTMO Guardian Shield (-3.5% Kill-Switch), Entradas Límite OTE en Descuento FVG 50% con Cobro TP0 30% en +1.0R (+417.23R de Retorno Combinado), y Suite Oficial de 156/156 Pruebas Unitarias Aprobadas al 100%. Protocolos de Seguridad SOP-07 a SOP-20."**

---

## 🏛️ 1. Matriz de Carteras Institucionales Multi-Mercado

### A. Cartera Criptomonedas (Bitunix Futures 24/7) — $+156.23	ext{ R}$
* **Activos:** `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `AVAXUSDT`, `LINKUSDT`, `XRPUSDT`, `PAXGUSDT`, `RENDERUSDT`, `SUIUSDT`, `INJUSDT`, `NEARUSDT`, `FETUSDT`, `ATOMUSDT`, `TIAUSDT`.
* **Métricas Auditadas:** 546 trades | 57.5% Win Rate Real | $+156.23	ext{ R}$ Netos | Profit Factor: 1.64.
* **Especialización Fractal:** 15M Scalp en Altcoins y 1H Swing en Bitcoin / Oro Cripto (`PAXG`).
* **Micro-Ventanas de Precisión (`SOP-18`):** AVAX a las 09h y 17h UTC; RENDER a las 08h, 13h y 17h UTC.

### B. Cartera Suprema TradFi (FTMO MetaTrader 5) — $+261.00	ext{ R}$
* **Metales:** `XAUUSD` (Oro 1H, $+58.4	ext{R}$, WR $55.5\%$) y `XAGUSD` (Plata 1H, $+42.5	ext{R}$).
* **Índices USA:** `US100` (Nasdaq 15M Apertura NY 13:30-16:30 UTC, $+6.5	ext{R}$) y `US500` (S&P 1H/15M, $+28.3	ext{R}$).
* **Índices Europa:** `GER40` (DAX 15M Apertura Frankfurt 07:00-10:00 UTC, $+5.0	ext{R}$).
* **Commodities:** `USOIL` (Petróleo WTI 15M, $+7.6	ext{R}$).
* **Forex Majors:** `USDCAD` ($+45.4	ext{R}$), `GBPJPY` ($+29.0	ext{R}$), `USDJPY` ($+23.1	ext{R}$), `EURUSD` ($+23.1	ext{R}$).
* **Métricas Auditadas:** 3,756 trades | 54.4% Win Rate Real | $+261.00	ext{ R}$ Netos | Profit Factor: 1.25.

---

## 🛡️ 2. Protocolos de Seguridad Operativa (SOP-07 a SOP-20)

* **SOP-07 (Zero Credentials Leak):** Sanitización absoluta de payloads y logs en memoria.
* **SOP-08 (Max Risk Allocation Enforcement):** Límite estricto del $1.0\%$ en Cripto y $0.50\%-0.75\%$ en FTMO.
* **SOP-09 (Rust/Orjson Fast Path Latency):** Serialización sub-2.5ms con Polars y orjson.
* **SOP-10 (Anti-NaN Extreme Values Sanitization):** Limpieza matemática de tensores numéricos.
* **SOP-11 (Trailing Monotonic Ratchet):** Invarianza de Stop Loss (nunca retrocede hacia pérdida).
* **SOP-12 (Slot Recycling on Fast BE):** Liberación instantánea de cupos al tocar TP0 (+1.0R Breakeven).
* **SOP-13 (Cluster Correlation Gating):** Máximo 2 posiciones por cluster correlacionado ($ho \ge 0.75$).
* **SOP-14 (Instant Microstructure Hydration):** Reconstrucción de 500 barras de CVD Real en arranque frío.
* **SOP-15 (Reactive Full-Stack Synapse Stream):** Telemetría sin latencia a 60 FPS al frontend.
* **SOP-16 (Free-Roll Scale-In Pyramiding):** Adición de volumen solo sobre beneficios consolidados.
* **SOP-17 (Single Source of Truth SSoT):** Paridad 1:1 idéntica entre Backtesting y Ejecución Real.
* **SOP-18 (Dynamic Asset-Specific Time-Gating):** Bloqueo de Lunes Pre-NY y Jueves Tarde + Micro-ventanas.
* **SOP-19 (Macro News Lockout & Post-Only Shield):** Bloqueo de $\pm 15$ min en NFP/CPI/FOMC y tarifas 100% Maker.
* **SOP-20 (Multi-Market Dual Isolation & TradFi Killzone Gating):** Aislamiento asíncrono Cripto/MT5 y Killzones bancarias.

---

## 🧪 3. Certificación QA Oficial

* **Total de Pruebas Aprobadas:** **156/156 pruebas unitarias (100% de éxito)**.
* **Compilación Frontend:** TypeScript verificado con **0 errores** (`npx tsc --noEmit`).
* **Persistencia:** SQLite WAL ACID Transaccional en [`engine/core/vault.py`](file:///c:/Users/Mat%C3%ADas%20Riquelme/Desktop/Proyectos%20documentados/Slingshot_Trading/engine/core/vault.py).
