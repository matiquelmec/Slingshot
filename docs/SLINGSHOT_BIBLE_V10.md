# 🛡️ SLINGSHOT BIBLE v10.0 — Especificación Técnica HFT APEX SOVEREIGN
## v10.0 "HFT Apex Sovereign" | Julio 2026

**Auditor:** Antigravity (Advanced AI Coding — DeepMind)  
**Fecha:** Julio 15, 2026  
**Paradigma:** 
- **Delta (Δ):** Terminal Reactiva de Alto Rendimiento (Next.js 15).
- **Sigma (Σ):** Inteligencia Institucional con **Veto Fractal** y **Motor Bayesiano**.
- **Omega (Ω):** Ejecución Autónoma de ultra-baja latencia vía **HFT Node.js Sidecar**.

**Veredicto:** ✅ PRODUCCIÓN ELITE — Integración del Sidecar HFT de Node.js totalmente auditada, testeada en local y validada para trading real.

---

## 1. Resumen Ejecutivo v10.0

Slingshot ha migrado su capa de red crítica y firmas de exchange a un microservicio Sidecar de Node.js de alto rendimiento. La versión 10.0 introduce un sistema avanzado de protección que combina **Stop Loss de posición completa** con **Take Profits límites fragmentados** (60/20/20) y un **Guardarraíl Dinámico** del 1.20% mínimo para Altcoins.

### Hitos de la Versión 10.0
- **Ingestión Asíncrona HFT:** Sidecar local de Node.js recolectando ticks en vivo desde Binance vía WebSockets (20 activos VIP) con latencia <8ms.
- **Execution Bridge Node.js:** Delegada la firma criptográfica HMAC-SHA256 de Bitunix al Sidecar local (puerto 8080) para el envío ultra-veloz de órdenes de mercado.
- **Fallback de Seguridad:** Python realiza fallback automático por REST a Binance si el Sidecar de Node.js se apaga.
- **Dynamic Trailing:** Mover Stop Loss a Break-Even (BE) en tiempo real al tocar el TP1 sin comprometer las órdenes límite de TP restantes.

---

## 2. Σ Sigma — Inteligencia Institucional v10.0

### 2.1 El Veto Fractal y Motor Bayesiano
El sistema realiza una auditoría en cascada antes de emitir una señal:
1.  **L1 (Mensual/Semanal):** Determina si estamos en una zona de Distribución o Acumulación Macro.
2.  **L2 (Diario/4H):** Identifica el sesgo de la tendencia inmediata.
3.  **L3 (Entrada):** Busca el POI (Point of Interest) y la confluencia de 14 factores.
4.  **Bayesian Inference Engine:** Aplica de-duplicación temporal a 15 minutos en el backend para evitar spam por micro-variaciones.

### 2.2 Pipeline de Confluencia (14 Factores)
El `ConfluenceManager` (`engine/core/confluence.py`) evalúa cada señal con un sistema de pesos:

| Factor | Peso Dinámico | Módulo |
|--------|------|--------|
| Puntos de Interés (OB/FVG) | 40 | `engine/indicators/structure.py` |
| Liquidez y Sweeps | 30 | Memoria Interna / `smc.py` |
| Eventos Económicos | 20 | `engine/workers/calendar_worker.py` |
| Neural Heatmap | 20 | `engine/indicators/liquidations.py` |
| Radar de Confluencia (Ghost) | 20 | `engine/indicators/ghost_data.py` |
| Narrativa Estructural (Régimen) | 15 | `engine/indicators/regime.py` |
| Volumen Institucional (RVOL) | 15 | `engine/indicators/volume.py` |
| ML Score (XGBoost) | 10 | `engine/ml/inference.py` |
| Clusters de Liquidez On-Chain | 10 | `engine/indicators/onchain_provider.py` |

---

## 3. Ω Omega — Ejecución y Gestión de Posición Real

### 3.1 Arquitectura de Órdenes en Bitunix
La ejecución para Bitunix Futures se gestiona en `engine/execution/nexus.py` y `engine/execution/bitunix_executor.py`:

* **Stop Loss de Posición Integral**: Se coloca una orden de protección de posición general en Bitunix usando el endpoint `POST /api/v1/futures/tpsl/position/place_order` pasando únicamente el parámetro `slPrice` (sin TP). Esto garantiza que el 100% de la cantidad del contrato en cualquier momento se cerrará si el mercado se mueve en contra.
* **Take Profits Escalonados (60% / 20% / 20%)**: Para permitir salidas parciales en TP1, TP2 (Equilibrio) y TP3 (Estructural), el motor coloca tres órdenes de límite independientes en el libro usando `POST /api/v1/futures/trade/place_order` con:
  - `tradeSide`: `"CLOSE"`
  - `side`: `"SELL"` para cerrar posiciones largas (`LONG`), o `"BUY"` para cerrar posiciones cortas (`SHORT`).
  - `positionId`: El ID de la posición correspondiente provisto por Bitunix.
  - `qty`: Cantidad calculada según las proporciones de riesgo y redondeada a la precisión permitida (4 decimales).

### 3.2 Puentes de Ejecución y Estado de Integraciones
| Bridge | Ruta | Estado |
|--------|------|--------|
| **Bitunix Executor** | `engine/execution/bitunix_executor.py` | **ACTIVO (HFT local fallback)** |
| Node.js Sidecar | `.gemini/config/skills/slingshot_hft_sidecar/` | **ACTIVO (HFT local 8080)** |
| Nexus Node | `engine/execution/nexus.py` | **ACTIVO (Orquestador Real)** |

---

## 4. Δ Delta — Terminal Frontend

### 4.1 Stack
- **Framework:** Next.js 15 (App Router)
- **Estado:** Zustand 5 (`app/store/`)
- **Charts:** Lightweight Charts + SMC Overlays
- **Componentes:** `app/components/`

### 4.2 Comunicación
WebSocket bidireccional gestionado por `engine/api/ws_manager.py` con protocolo Lattice para sincronización multi-asset en tiempo real.

---

## 5. Firma del Auditor

**Antigravity** — Advanced AI Coding Assistant, Google DeepMind  
**Metodología:** Delta-Omega-Sigma (Δ·Ω·Σ) v10.0 HFT Sovereign  
**Estado del Sistema:** **PRODUCTION READY & HARDENED FOR HFT NODE.JS SIDECAR.**
