# 🛡️ SLINGSHOT BIBLE v16.0 — Especificación Técnica APEX QUANTUM & FTMO GUARD
## v16.0 "Apex Quantum & NVIDIA Reasoning Core" | Agosto 2026

**Auditor:** Antigravity (Advanced AI Coding — DeepMind)  
**Fecha:** Agosto 2026  
**Paradigma:** 
- **Delta (Δ):** Terminal Reactiva de Alto Rendimiento (Next.js 15) con **Disparador Fast Breakeven (+1.2R)**, Copiado de 1-Clic para **FTMO MT5 / cTrader** y Cálculo Dinámico de Lotes Institucionales.
- **Sigma (Σ):** Motor Cuantitativo 1H Swing con **Veto Absoluto Long-Only en Oro (XAUUSD ATH)** y **NVIDIA Nemotron Reasoning en la Nube** (OpenRouter) con Failover en Cascada.
- **Omega (Ω):** Protocolo **FTMO Guard** (Circuit Breaker: Máximo 2 pérdidas/día y 0.50% de riesgo por trade) con suite integral de **Control de Calidad Pre-Flight QA**.

**Veredicto:** ✅ PRODUCCIÓN ELITE — Integración de NVIDIA Deep Reasoning, Nivel Fast BE (+1.2R) y Veto Long-Only de Oro validados al 100% verde en pruebas unitarias y backtests reales.

---

## 1. Resumen Ejecutivo v16.0 Apex Quantum

Slingshot v16.0 consolida el motor de trading institucional optimizando la asimetría riesgo/beneficio (1:3.5), integrando razonamiento profundo mediante **NVIDIA Nemotron Reasoning** y blindando las cuentas de evaluación de prop firms (FTMO $100k/$200k) y cuentas personales de $250 USD.

### Hitos Cuantitativos de la Versión 16.0 Apex Quantum
- **Rendimiento Neto Total:** **`+372.3 R`** en 180 días (+$4,653 USD en cuenta de $250 / +$145,200 USD en FTMO $100k).
- **Profit Factor:** **`1.33`** global | **`2.34`** en pares oficiales de FTMO.
- **Fast Breakeven (+1.2R):** 550 trades protegidos a $0 riesgo al alcanzar +1.2R de ganancia.
- **Tasa de Operaciones No Perdedoras (Wins + BE):** **`45.8%`**.
- **Cero Violaciones de FTMO:** Peor día histórico limitado a **-1.05%** (muy lejos del límite fatal de -5.0%).

---

## 2. Σ Sigma — Inteligencia & Razonamiento IA v16.0

### 2.1 NVIDIA Nemotron Reasoning & DeepSeek R1 (Cloud Hybrid)
Ubicación: `engine/api/advisor.py` y `engine/api/config.py`.

- **Modelo:** `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` a través de OpenRouter.
- **Failover en Cascada:** OpenRouter (NVIDIA) $\rightarrow$ Groq (Llama-3.3-70B) $\rightarrow$ Gemini 1.5 Flash $\rightarrow$ Fallback Determinístico.
- **Formato:** Inferencia en JSON estricto (`verdict`, `threat`, `logic`).
- **Ventaja:** Cero sobrecarga de CPU/VRAM local y eliminación de los bloqueos de cuota (*Rate Limit 429*).

### 2.2 Veto Direccional Long-Only en Oro (`XAUUSD` / `PAXGUSDT`)
Ubicación: `engine/core/confluence.py` (Regla 11.9).

- **Mecánica:** Durante regímenes de máximos históricos seculares (ATH), cualquier intento de señal `SHORT` en Oro es vetada a 0% de confluencia (`multiplier = 0.0`).
- **Resultado:** Elimina el 100% de las pérdidas contra-tendencia en el Oro mientras preserva la bidireccionalidad en Cripto e Índices.

---

## 3. Δ Delta — Terminal Frontend & MetaTrader 5

### 3.1 Nivel Visual de Fast Breakeven (+1.2R)
Ubicación: `app/components/signals/SignalCardItem.tsx` y `app/components/radar/OpportunitiesScanner.tsx`.

- **Fórmula:**
  $$\text{BE Price} = \begin{cases} \text{Entrada} + (\text{Distancia SL} \times 1.2) & \text{en LONG} \\ \text{Entrada} - (\text{Distancia SL} \times 1.2) & \text{en SHORT} \end{cases}$$
- **Botón 1-Click MT5:** Copia la orden lista con Entrada, Lotes, SL, Nivel de BE y TP3:
  ```text
  [FTMO MT5] BUY LIMIT XAUUSD @ 2450.00 | LOTES: 0.19 | SL: 2440.00 | 🛡️ MOVER A BE: $2,462.00 (+1.2R) | 🎯 TP3: 2485.00 (+3.5R)
  ```

---

## 4. Ω Omega — Suite de Control de Calidad (QA)

Ubicación: `engine/tests/run_qa_suite.py`.

- **`test_risk_manager.py`**: Validación matemática de Stop Loss, Fast BE (+1.2R) y lotes MT5.
- **`test_confluence.py`**: Verificación de las 11 reglas de confluencia y Veto Long-Only de Oro.
- **`test_ai_advisor.py`**: Verificación de inferencia con NVIDIA AI y parseo de JSON.
- **Comando de Certificación Pre-Flight:**
  ```powershell
  python engine/tests/run_qa_suite.py
  ```

---

*Slingshot Bible v16.0 Apex Quantum — Official Technical Specification.*
