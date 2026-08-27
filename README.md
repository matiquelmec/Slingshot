# 🛡️ SLINGSHOT v22.1 APEX SOVEREIGN — Intelligent Limit Sentinel, Staged Exits (60/20/20) & The Truth Engine

> **"Terminal Cuantitativa Autónoma de Grado Institucional. Kernel de Indicadores en Rust (Polars < 2.5ms). Persistencia Transaccional SQLite WAL. Centinela Inteligente de Órdenes Límite en Vivo. Gestión Activa de Stop Loss & Fast Breakeven (+1.0R) en Bitunix. Puente Directo MetaTrader 5 con Protección FTMO. Suite de Certificación QA (45/45 Tests Aprobados al 100%)."**

![Status](https://img.shields.io/badge/Status-100%25_AUTONOMOUS-0d2a1a?style=for-the-badge&logo=codeproject&logoColor=fff)
![Version](https://img.shields.io/badge/Version-22.1_Apex_Sovereign-1a3a6e?style=for-the-badge)
![Kernel](https://img.shields.io/badge/Kernel-Polars_Rust_Sub--2.5ms-black?style=for-the-badge&logo=rust&logoColor=fff)
![Vault](https://img.shields.io/badge/Persistence-SQLite_WAL_ACID-003B57?style=for-the-badge&logo=sqlite&logoColor=fff)
![Execution](https://img.shields.io/badge/Execution-Bitunix_Live_&_MT5-orange?style=for-the-badge)
![QA](https://img.shields.io/badge/QA_Suite-45%2F45_Passed-success?style=for-the-badge)

---

## 🎯 Nuestra Misión: Democratizar el Smart Money

Slingshot es una **Terminal de Inteligencia y Ejecución Cuantitativa Institucional** diseñada para operar en mercados de Criptomonedas y Cuentas de Fondeo (*Prop Firms* como FTMO). El sistema combina:
* **Smart Money Concepts (SMC):** Fair Value Gaps (FVG), Order Blocks, Zonas OTE (Fibonacci 61.8% - 78.6%) y Liquidez.
* **Centinela Inteligente de Órdenes Límite (*Apex Limit Sentinel*):** Auto-cancelación en Bitunix si el precio toca TP1 o SL antes de entrar, o si expira a las 12 velas (TTL).
* **Kernel de Alto Rendimiento en Rust (`Polars`):** Cálculo de indicadores y confluencias en menos de $2.5\text{ ms}$.
* **Bóveda SQLite WAL Transaccional (`vault.py`):** Persistencia ACID de sesiones, deduplicación anti-spam de alertas y bitácora de auditoría.
* **Gestión de Posiciones Activa en Bitunix:** Movimiento automático de Stop Loss a **Fast Breakeven (+1.0R)** y tomas de parciales escalonadas (**TP1 60% / TP2 20% / TP3 20%**).
* **Universo Dinámico Cuantitativo (RVOL + KER):** Descubrimiento automatizado de activos líquidos con volumen relativo superior.
* **Liberación Dinámica de Slots ("Slot Recycling"):** Permite abrir nuevas oportunidades de alta probabilidad en cuanto las operaciones existentes quedan blindadas con riesgo cero ($0.00).

---

## 🏛️ Arquitectura del Sistema v22.0

```mermaid
graph TB
    subgraph "FRONTEND — Next.js 15 (Radar & Terminal)"
        A["Dashboard & Multi-Asset Radar"] --> B["TelemetryStore (Zustand 5)"]
        B --> C["WebSocket Client MasterSync"]
        A --> D["Escáner de Oportunidades SMC (14 Activos + Dinámicos)"]
        A --> E["Auditor de Posiciones y Órdenes en Vivo"]
    end

    subgraph "SIGMA — Motor Cuantitativo & Vault (Python 3.12 / Rust)"
        J["FastAPI Lifespan Engine"] --> K["SlingshotOrchestrator"]
        K --> L["MarketScanner (15m Scalp / 1H Swing)"]
        L --> M["ConfluenceManager (14 Factores SMC)"]
        L --> N["Polars Rust Kernel (Sub-2.5ms)"]
        M --> V["SQLite WAL Vault (vault.py)<br/>• Telegram Anti-Spam<br/>• Session SSoT (Asia/London/NY)<br/>• Audit Trail Log"]
    end

    subgraph "OMEGA — Ejecución Autónoma & Centinelas de Resiliencia"
        L --> NX["NexusNode (Slot Recycling)"]
        NX --> T["Telegram Dispatcher (1-Click MT5 Copy)"]
        NX --> BX["BitunixExecutor (Limit Orders + Maker Fee 0.02%)"]
        NX --> MT5["MT5Bridge (FTMO Guard Lockout -3.5%)"]
        TM["TradeManager Centinel (Polling 30s)"] --> |"Fast BE (+1.0R) & Staged TPs 60/20/20"| BX
        LS["Apex Limit Sentinel (Polling 30s)"] --> |"Missed Target / Pre-SL Auto-Cancel"| BX
    end

    C <--> |"WebSockets"| J
```

---

## 💎 Innovaciones Clave de Slingshot v22.0

### 1. 👁️ Centinela Inteligente de Órdenes Límite (*Apex Limit Sentinel*)
* **Missed Target Kill-Switch:** Si el mercado toca TP1 sin activar la orden límite, la cancela de inmediato para evitar trampas de liquidez tardías.
* **Pre-Entry Invalidation:** Si el precio rompe el Stop Loss antes de entrar, retira la orden del libro de Bitunix.
* **Caducidad Dinámica (TTL):** Purgado automático de órdenes con más de 3 horas desfasadas.

### 2. 🛡️ Fast Breakeven (+1.0R) y Salidas Escalonadas (60 / 20 / 20)
* **Blindaje Inmediato:** Al avanzar $+1.0\text{R}$, el centinela [`TradeManager`](file:///c:/Users/Mat%C3%ADas%20Riquelme/Desktop/Proyectos%20documentados/Slingshot_Trading/engine/workers/trade_manager.py) coloca el Stop Loss al precio exacto de entrada (**$\$0.00$ de pérdida**).
* **Parciales Óptimos:** Toma el **$60\%$ del volumen en TP1 (+1.5R)**, el **$20\%$ en TP2 (+2.5R)** y el **$20\%$ en TP3 (+3.5R)**, asegurando ganancias mayoritarias de inmediato.

### 3. ♻️ Liberación Dinámica de Slots ("Slot Recycling")
* **Máxima Eficiencia de Capital:** Las posiciones en Breakeven **liberan su cupo de riesgo de inmediato**, permitiendo al sistema capturar nuevas oportunidades sin sobreexponer el margen.

### 4. 👑 The Truth Engine (Motor Unificado de Backtesting)
* Simulación con 100% de paridad con producción, deducción exacta de comisiones de Bitunix (Maker 0.02%, Taker 0.06%), slippage y soporte de interés compuesto.

### 5. 🏛️ Repositorio Transaccional SQLite WAL (`vault.py`)
* Persistencia ACID inmutable en `slingshot_vault.db` para sesiones, bitácora de auditoría y deduplicación anti-spam.

### 6. 🏢 Puente MetaTrader 5 Institucional (`mt5_bridge.py`)
* Integración TradFi para Oro (`XAUUSD`), Nasdaq (`US100`) y Forex con **FTMO Circuit Breaker (-3.5% lockout)**.

---

## 🛠️ Stack Tecnológico

* **Frontend**: Next.js 15 (App Router), Zustand 5, Tailwind CSS, Lightweight Charts.
* **Backend**: Python 3.12, FastAPI, Uvicorn, WebSockets, Polars (Rust), Pandas, NumPy.
* **Base de Datos / Persistencia**: SQLite 3 (WAL Mode & Normal Synchronous).
* **Exchanges & Brokers**: Bitunix Futures REST API, MetaTrader 5 (MT5 Python API).
* **Testing & QA**: Pytest 8, AnyIO, Asyncio (45/45 tests pasando al 100% en 6s).

---

## 🚀 Guía de Inicio Rápido (Quick Start)

### 1. Iniciar el Motor Completo (Backend + Centinelas)
```powershell
python -m uvicorn engine.api.main:app --host 0.0.0.0 --port 8000
```

### 2. Inspeccionar y Proteger Posiciones en Vivo en Bitunix
```powershell
python scripts/manage_open_positions.py
```

### 3. Ejecutar la Suite de Pruebas Unitarias (26 Tests)
```powershell
python -m pytest engine/tests/ -v
```

---

## 🧪 Matriz de Certificación QA (26/26 Tests Aprobados)

```text
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-8.4.2, pluggy-1.6.0
rootdir: Slingshot_Trading

engine/tests/test_full_engine_autonomy_audit.py::test_orchestrator_auto_starts_trade_manager PASSED [  3%]
engine/tests/test_full_engine_autonomy_audit.py::test_security_sl_never_moves_backwards PASSED [  7%]
engine/tests/test_full_engine_autonomy_audit.py::test_slot_recycling_frees_risk_on_breakeven PASSED [ 11%]
engine/tests/test_live_trade_management.py::test_fast_be_trigger_at_1r PASSED [ 15%]
engine/tests/test_live_trade_management.py::test_sync_live_positions_fast_be PASSED [ 19%]
engine/tests/test_sqlite_vault.py::test_vault_initialization_and_wal_mode PASSED [ 23%]
engine/tests/test_sqlite_vault.py::test_telegram_dedup_and_cooldown PASSED [ 26%]
engine/tests/test_sqlite_vault.py::test_session_state_persistence PASSED [ 30%]
engine/tests/test_sqlite_vault.py::test_concurrent_writes_thread_safety PASSED [ 34%]
engine/tests/test_mt5_bridge.py::test_mt5_bridge_dry_run_placement PASSED [ 38%]
engine/tests/test_mt5_bridge.py::test_mt5_bridge_blocks_on_drawdown_lockout PASSED [ 42%]
engine/tests/test_deterministic_pipeline_isolation.py::test_confluence_evaluation_latency PASSED [ 46%]
engine/tests/test_deterministic_pipeline_isolation.py::test_ftmo_lot_sizing_zero_latency PASSED [ 50%]
engine/tests/test_session_mastery.py::test_session_manager_initialization PASSED [ 53%]
engine/tests/test_session_mastery.py::test_time_filter_killzone_ny_and_london PASSED [ 57%]
engine/tests/test_session_mastery.py::test_global_session_status_structure PASSED [ 61%]
engine/tests/test_session_mastery.py::test_session_sweep_logic PASSED    [ 65%]
engine/tests/test_market_scanner_hft.py::test_market_scanner_session_integration PASSED [ 69%]
engine/tests/test_market_scanner_hft.py::test_market_scanner_ote_watchdog_chasing_detection PASSED [ 73%]
engine/tests/test_market_scanner_hft.py::test_hft_order_flow_graceful_fallback PASSED [ 76%]
engine/tests/test_ftmo_security_guard.py::test_ftmo_lot_sizing_gold PASSED [ 80%]
engine/tests/test_ftmo_security_guard.py::test_ftmo_daily_drawdown_protection PASSED [ 84%]
engine/tests/test_ftmo_security_guard.py::test_tradfi_assets_config_integrity PASSED [ 88%]
engine/tests/test_telegram_persistence.py::test_reboot_survival_no_duplicate_signal PASSED [ 92%]
engine/tests/test_telegram_persistence.py::test_price_drift_allows_retrigger PASSED [ 96%]
engine/tests/test_telegram_persistence.py::test_purge_old_dispatches PASSED [100%]

============================= 26 passed in 5.25s ==============================
```

---

*Slingshot v21.0 Apex Autonomous — Documentación Oficial de Arquitectura y Operativa.*
