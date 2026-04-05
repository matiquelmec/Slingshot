# 🛡️ SLINGSHOT v5.7.15 Master Gold UNIFIED: ESPECIFICACIÓN TÉCNICA MAESTRA

> **"Institucionalidad Pura en 1m. Filtrado de Ruido HFT, Prioridad de CPU y Confluencia Neural."**
**Versión:** 5.7.15 Master Gold | **Fecha:** 05 de Abril, 2026 | **Estado:** PRODUCCIÓN ✅

---

## 💎 1. VISIÓN ESTRATÉGICA (THE HARDENING)
v5.7.15 Master Gold es el resultado de la evolución del motor SMC v4 para el mercado de criptoactivos de alta volatilidad (SOL/BTC). Hemos eliminado el lag de datos y el ruido retail mediante una arquitectura **Local-First** que prioriza la supervivencia del capital sobre la frecuencia de trading.

### Core Philosophy:
*   **Institutional Damping:** Filtrado de picos de volumen mediante Z-Score (Outlier Detection) para ignorar "Flash Pumps" ruidosos.
*   **Value Zone Precision:** El sistema solo opera en zonas de Descuento (Longs) o Premium (Shorts) bajo el algoritmo de Fibonacci Dinámico.
*   **OS Priority Integration:** El motor de trading se auto-eleva a prioridad de CPU "HIGH" para garantizar ejecución en milisegundos.

---

## 🏗️ 2. EL MOTOR DE AUDITORÍA (ENGINE)

### 📡 El Pipeline de Datos (SSOT: Single Source of Truth)
1.  **Ingesta:** Binance Futures WebSocket (Stream continuo de OHLCV y Tickers).
2.  **Saneamiento:** `MarketAnalyzer` convierte OHLCV a numérico (float64) para evitar fallos de cálculo en Pandas.
3.  **Filtrado RVOL (v5.2):**
    *   **Z-Score Filter:** Detecta anomalías > 5.0 desviaciones estándar. Un 1000x de volumen se capea a 5.0x o se ignora por ruido.
    *   **Adaptive Floor:** Suelo dinámico de volumen basado en el 10% de la SMA200 para filtrar sesiones de baja liquidez.

### 🧠 El Jurado de Confluencia (v5.7.15 Master Gold Titanium)
Evalúa cada señal contra 4 capas estructurales:
*   **Capa SMC:** Bloques de Órdenes (OB) y Fair Value Gaps (FVG) de alta probabilidad.
*   **Capa Macro:** Filtra señales según la tendencia del DXY (Dólar) y NASDAQ (Nasdaq100). No se opera contra la liquidez global.
*   **Capa On-Chain:** Sentinel v5.7.15 Master Gold integrado detectando acumulación de ballenas y presión de entrada a exchanges.
*   **Capa Neural (Heatmap):** Inferencia táctica de impacto humano y visualización de Muros de Ordenes GL en tiempo real.

---

## 🎨 3. LA TERMINAL DE USUARIO (REACTIVE FRONTEND)

### 📊 Reactive Store (Zustand 5)
*   **O(1) Mapping:** Las señales se gestionan mediante `Map` de IDs en lugar de `Array`. Renderizado instantáneo de alertas históricas.
*   **Real-time Price:** Sincronización del `latestPrice` en cada vela y actualización táctica para eliminar el estado "CALCULANDO".
*   **Radar Feed & Heatmap:** Visualización global unificada con el Auditor de Señales en tiempo real, con trazado inteligente de zonas de liquidez profunda.

---

## ⚡ 4. LANZAMIENTO Y MANTENIMIENTO

### 🚀 Unified Launcher (`start.ps1`)
*   Secuencia de arranque de 3 fases: Backend → Frontend → OS Optimization.
*   Auto-priorización de procesos Python y Ollama para minimizar micro-lag de trading.

### 🧹 Vault Cleanup (`scripts/vault_cleanup.ps1`)
*   Purger preventivo de bytecode de Python (`__pycache__`), caches de Next.js y archivos residuales de `/tmp`.

---

## 📂 5. ESTRUCTURA DE LA BÓVEDA (ORQUESTACIÓN)
```text
slingshot_trading/
├── 📁 engine/           # El Cerebro Algorítmico (FastAPI + SMC Strategy)
├── 📁 app/              # La Terminal de Usuario (React + Zustand 5)
├── 📁 docs/             # El Repositorio de Inteligencia
│   ├── MASTER_SPEC_V5   # (Este documento) La Referencia Maestra
│   ├── 📁 architecture/ # Diagramas de flujo y Pipeline
│   ├── 📁 knowledge/    # Teoría de Trading: Wyckoff y SMC Pro
│   └── 📁 archive/      # Resúmenes de versiones anteriores
├── 📁 scripts/          # Herramientas y Escudos de Auditoría
│   ├── 📁 tests/        # Bóveda Centralizada de Pruebas y Benchmarks
│   ├── start.ps1        # Launcher Unificado (Single Click)
│   └── vault_cleanup    # Higiene del sistema
└── 📄 start.ps1         # Enlace directo al Lanzador Maestro
```

**"En v5.7.15 Master Gold, el código no solo es trading; es la armadura de tus $200k."**
