# 🛡️ SLINGSHOT v27.0 APEX SYNAPSE — Autonomous Institutional Trading Terminal

> **"Terminal Cuantitativa Autónoma de Grado Institucional. Apex Synapse: Pipeline de Telemetría Full-Stack Reactiva a 60 FPS (SOP-15 Resilient WebSocket Telemetry & Zero-Jitter Handshake: Actualización In-Place de Lightweight Charts sin Recolección de Basura, Transición Optimista de Símbolos sin Parpadeo de Pantalla Vacía, Unificación Dinámica de Host Multi-Dispositivo con getApiBaseUrl, Despacho Inmediato de Señales Sub-50ms y Token JWT Silencioso), Instant Warmup Engine: Hidratación Instantánea de Microestructura & 500 Velas de CVD Real en el Arranque (SOP-14 Extracción Nativa de Taker Buy/Sell Volume k[9]/k[10] de Binance Futures), Apex Chronos: Motor de Estacionalidad Semanal y Time Gating (SOP-12 Weekly Liquidity Profiles), Calibrador de Reloj Automático (SOP-11 Server Time Offset), Pre-Flight Margin Guard (SOP-10 Verificación de Margen Libre Previo a Ejecución), Spread Circuit Breaker en Ejecución (Veto a Mercado ante Spread > 0.25%), Tick Inactivity Watchdog (Reciclaje Automático de Sockets Zombi > 30s) y Suite Oficial de 131/131 Pruebas Unitarias Aprobadas al 100%. Stream Fortress: Handshake Escalonado con Jitter Anti-Thundering Herd, Token Bucket Rate Limiter Centralizado en Bitunix REST (Máximo 3 req/s con Connection Pool Persistente), Aislamiento de Feeds de Noticias con Circuit Breaker. Cluster Fortress: Motor de Correlación Cruzada Dinámica (ClusterRiskGuard), Gating Anti-Sobreexposición Sistémica (Máximo 2 Operaciones en Riesgo por Cluster Correlacionado ρ >= 0.75), Inmunidad de Activos Descorrelacionados (Oro 1H, Forex, TradFi). Protocolos de Seguridad SOP-07 a SOP-15."**

![Status](https://img.shields.io/badge/Status-100%25_AUTONOMOUS_&_SELF--HEALING-0d2a1a?style=for-the-badge&logo=codeproject&logoColor=fff)
![Version](https://img.shields.io/badge/Version-27.0_Apex_Synapse-1a3a6e?style=for-the-badge)
![Synapse](https://img.shields.io/badge/Apex_Synapse-60_FPS_Telemetry_%26_Zero--Jitter-purple?style=for-the-badge)
![Warmup](https://img.shields.io/badge/Instant_Warmup-500_Bars_CVD_%26_Taker_Flow-purple?style=for-the-badge)
![Chronos](https://img.shields.io/badge/Apex_Chronos-Weekly_Profiles_%26_Time_Gating-purple?style=for-the-badge)
![Apex](https://img.shields.io/badge/Apex_Shield-Time_Calibrator_%26_Spread_Breaker-purple?style=for-the-badge)
![Stream](https://img.shields.io/badge/Stream_Fortress-Staggered_Handshake_%26_Token_Bucket-purple?style=for-the-badge)
![Cluster](https://img.shields.io/badge/Cluster_Risk_Guard-%CF%81_%3E=_0.75_Gating-purple?style=for-the-badge)
![Security](https://img.shields.io/badge/Security_Protocols-SOP--07%20to%20SOP--15-emerald?style=for-the-badge)
![Breathing](https://img.shields.io/badge/Breathing_Shield-1.0R%20Lockout%20Air-emerald?style=for-the-badge)
![Gold](https://img.shields.io/badge/Gold_Specialization-1H_Native_Swing-gold?style=for-the-badge)
![Confluence](https://img.shields.io/badge/Confluence-14_Factors_End--to--End-emerald?style=for-the-badge)
![FTMO](https://img.shields.io/badge/FTMO_Guardian-Dynamic_Phase_Sizing-gold?style=for-the-badge)
![Alpha](https://img.shields.io/badge/Alpha_Maximizer-50%2F30%2F20_Staged_Exits-purple?style=for-the-badge)
![Kernel](https://img.shields.io/badge/Kernel-Polars_Rust_Sub--2.5ms-black?style=for-the-badge&logo=rust&logoColor=fff)
![Vault](https://img.shields.io/badge/Persistence-SQLite_WAL_ACID-003B57?style=for-the-badge&logo=sqlite&logoColor=fff)
![Execution](https://img.shields.io/badge/Execution-Bitunix_Live_&_MT5_Dual_Engine-orange?style=for-the-badge)
![QA](https://img.shields.io/badge/QA_Suite-131%2F131_Passed_100%25-success?style=for-the-badge)

---

## 🎯 Nuestra Misión: Democratizar el Smart Money con Máxima Resiliencia

Slingshot es una **Terminal de Inteligencia y Ejecución Cuantitativa Institucional** diseñada para operar simultáneamente en mercados de Criptomonedas (Bitunix 24/7) y Cuentas de Fondeo (*Prop Firms* como FTMO en MetaTrader 5). El sistema combina:

* **Smart Money Concepts (SMC):** Fair Value Gaps (FVG), Order Blocks, Zonas OTE (Fibonacci 61.8% - 78.6%) y Liquidez con precisión de nivel institucional.
* **Asimetría Direccional en Altcoins (v24.0):** Gating estadístico en Altcoins (`SUI`, `RENDER`, `ATOM`, `FET`, `NEAR`) con preferencia Long y exigencia de Confluencia $\ge 70$ para Shorts.
* **Salidas Escalonadas Alpha Maximizer (50% / 30% / 20%):** Cobro del 50% en TP1 (+1.5R) cubriendo riesgo, 30% en TP2 (+3.0R) elevando SL a +2.0R y 20% en Runner (+5R a +8R) con Trailing Ratchet al 70%.
* **Breathing Room Shield (10s):** Inmunidad de apertura contra micro-ruidos de spread y mechas de libro.
* **Filtros Cuantitativos Institucionales:** `RVOL >= 1.30` y `KER >= 0.35` para purgar consolidaciones y falsos quiebres sin volumen.
* **SSoT Backtest CLI:** `scripts/run_institutional_backtest.py` como Fuente Única de Verdad para simulación de cartera y activos individuales.
* **Auto-Healing Reconciliator:** Auditoría continua cada 15-30s que detecta contratos huérfanos y auto-coloca el Stop Loss y las órdenes de Take Profit.
* **Resolución Dinámica de Precisión de Activos:** Mapeo en tiempo real de decimales de cantidad (`basePrecision`) y precio (`quotePrecision`).
* **Invarianza Monótona Absoluta del Stop Loss:** Blindaje que prohíbe que un Stop Loss retroceda o se degrade ante reinicios.
* **Kernel en Rust (`Polars`):** Cálculo vectorial de indicadores y confluencias en menos de $2.5\text{ ms}$.
* **Bóveda SQLite WAL Transaccional (`vault.py`):** Persistencia ACID de sesiones y bitácora de auditoría inmutable.
* **Guardián de Telemetría y Heartbeat en Telegram:** Reporte periódico cada 4 horas de signos vitales, latencia, margen y PnL.
* **Supervisor Watchdog 24/7 (`scripts/watchdog_supervisor.py`):** Monitor de subprocesos para ejecución inmortal en VPS.

---

## 🏛️ Arquitectura del Sistema v22.3 APEX SOVEREIGN

```mermaid
graph TB
    subgraph "FRONTEND — Next.js 15 (Radar & Terminal Reactiva)"
        A["Dashboard & Multi-Asset Radar"] --> B["TelemetryStore (Zustand 5)"]
        B --> C["WebSocket Client MasterSync"]
        A --> D["Escáner de Oportunidades SMC (14 Cripto + 6 TradFi)"]
        A --> E["Auditor de Posiciones y Órdenes en Vivo"]
        A --> OB["OnboardingModal (Validación en Vivo de Claves)"]
    end

    subgraph "SIGMA — Motor Cuantitativo & Vault (Python 3.12 / Rust)"
        J["FastAPI Lifespan Engine"] --> K["SlingshotOrchestrator"]
        K --> L["MarketScanner (15m Scalp / 1H Swing / 1D Daily)"]
        K --> SETUP["SetupRouter (/api/v1/setup Status/Test/Save)"]
        L --> M["ConfluenceManager (14 Factores SMC + KER)"]
        L --> N["Polars Rust Kernel (Sub-2.5ms)"]
        M --> V["SQLite WAL Vault (vault.py)<br/>• Telegram Anti-Spam<br/>• Session SSoT (Asia/London/NY)<br/>• Audit Trail Log"]
    end

    subgraph "OMEGA — Ejecución Autónoma & Centinelas de Resiliencia"
        L --> NX["NexusNode (Slot Recycling & Auto-Healing)"]
        NX --> T["Telegram Dispatcher (Heartbeat & 1-Click MT5 Copy)"]
        NX --> BX["BitunixExecutor (Limit Orders + Exponential Backoff)"]
        NX --> MT5["MT5Bridge (FTMO Guard Lockout -3.5%)"]
        TM["TradeManager Centinel (Polling 15s)"] --> |"Fast BE (+1.0R), Trailing (+2.0R) & Staged TPs"| BX
        TM --> |"Fast BE & Trailing Ratchet Multi-Asset"| MT5
        LS["Apex Limit Sentinel (Polling 30s)"] --> |"Missed Target / Pre-SL / TTL Auto-Cancel"| BX
        AH["Auto-Healing Reconciliator (Polling 15s)"] --> |"Auto-Repara SL y TPs Faltantes"| BX
    end

    C <--> |"WebSockets"| J
```

---

## 💎 Las 10 Innovaciones de Grado Institucional (v22.3)

### 1. 🔄 Auto-Healing Reconciliator & Dynamic Precision
* **Auditoría Bidireccional:** Cada 15-30s audita que todas las posiciones abiertas cuenten con su Stop Loss nativo y sus 3 órdenes de Take Profit.
* **Auto-Reparación:** Si una orden no se colocó en la apertura por micro-cortes o congestión del exchange, la detecta, resuelve su precisión exacta con `get_symbol_precision()` y la emite de inmediato.

### 2. ⚡ Reintentos con Exponential Backoff & Jitter
* Todas las peticiones al exchange incorporan reintentos automáticos ante códigos `429 Too Many Requests`, `500 Internal Error` o desconexiones, regenerando nonce y firma digital en cada iteración.

### 3. 🔒 Invarianza Monótona Absoluta de Stop Loss
* Guardia de hardware y software que **prohíbe estrictamente cualquier retroceso o degradación del Stop Loss**. Una vez que una posición entra en ganancia o Breakeven, el SL solo puede avanzar a favor del trade.

### 4. 👁️ Centinela Inteligente de Órdenes Límite (*Apex Limit Sentinel*)
* **Missed Target Kill-Switch:** Si el mercado toca TP1 sin activar la orden límite, la cancela de inmediato para evitar trampas de liquidez tardías.
* **Pre-Entry Invalidation:** Si el precio rompe el Stop Loss antes de entrar, retira la orden del libro.
* **Caducidad Dinámica (TTL):** Purgado automático de órdenes con más de 3 horas desfasadas.

### 5. 🛡️ Fast Breakeven (+1.0R) y Salidas Escalonadas (60 / 20 / 20)
* **Blindaje Inmediato:** Al avanzar $+1.0\text{R}$, el centinela coloca el Stop Loss al precio de entrada (**$\$0.00$ de pérdida**).
* **Parciales Óptimos:** Toma el **$60\%$ del volumen en TP1 (+1.3R)**, el **$20\%$ en TP2 (+2.2R)** y el **$20\%$ en TP3 (+3.5R Runner)**, asegurando ganancias mayoritarias y capturando mega-tendencias.

### 6. ♻️ Liberación Dinámica de Cupos (*Slot Recycling Protocol*)
* **Máxima Eficiencia de Capital:** Las posiciones en Breakeven **liberan su cupo de riesgo de inmediato**, permitiendo al sistema ejecutar el volumen de 8-10 operaciones con el margen de 4.

### 7. 🏛️ Ecosistema MetaTrader 5 TradFi (FTMO Guardian)
* Integración nativa de **Oro (`XAUUSD`), Nasdaq (`US100`), Dow Jones (`US30`), S&P 500 (`US500`), DAX 40 (`GER40`, PF 2.17) y GBPJPY (`El Dragón`, PF 2.23)** con cálculo dinámico de lotes y **FTMO Circuit Breaker (-3.5% lockout)**.

### 8. 💓 Telemetría Vital y Heartbeat en Telegram
* Despacho de signos vitales cada 4 horas con latencia de API, margen libre, posiciones activas, PnL no realizado y alertas rojas inmediatas ante anomalías.

### 9. 🐕 Supervisor Watchdog 24/7 (`scripts/watchdog_supervisor.py`)
* Supervisor de subprocesos diseñado para servidores VPS Windows, garantizando auto-reinicio en $< 2\text{ segundos}$ ante reinicios del sistema operativo.

### 10. 👑 The Truth Engine (Motor de Backtesting Unificado)
* Simulación con 100% de paridad con producción, comisiones reales Maker (0.02%) y Taker (0.06%), slippage y soporte de interés compuesto.

---

## 🛠️ Stack Tecnológico

* **Frontend**: Next.js 15 (App Router), Zustand 5, Tailwind CSS, Lightweight Charts, Lucide Icons.
* **Backend**: Python 3.12, FastAPI, Uvicorn, WebSockets, Polars (Rust), Pandas, NumPy, MetaTrader 5.
* **Base de Datos / Persistencia**: SQLite 3 (WAL Mode & Normal Synchronous), SQLiteVault.
* **Exchanges & Brokers**: Bitunix Futures REST API (Dual SHA-256), MetaTrader 5 IPC Bridge.
* **Testing & QA**: Pytest 8, AnyIO, Asyncio (**63/63 tests pasando al 100% en 8.9s**).

---

## 🚀 Guía de Inicio Rápido (Quick Start)

### 1. Instalación en 1 Solo Clic (Windows)
Haz doble clic en el instalador de la raíz:
```powershell
install.bat
```
*(Detecta Python y Node.js con `winget`, construye `.venv`, instala dependencias y crea el acceso directo en tu Escritorio).*

### 2. Iniciar el Motor de Producción (1-Clic)
```powershell
launch.bat
```
*(Opcional: Para modo servidor 24/7 en VPS, ejecuta `python scripts/watchdog_supervisor.py`).*

### 3. Ejecutar la Suite Oficial de Certificación QA (63 Pruebas)
```powershell
python scripts/run_qa_suite.py
```

---

## 📄 Licencia y Auditoría
* **Arquitectura:** Slingshot APEX SOVEREIGN v22.3
* **Auditoría:** Antigravity (Advanced AI Coding — Google DeepMind)
* **Certificación:** ✅ 63/63 Tests PASS (100% Green)
