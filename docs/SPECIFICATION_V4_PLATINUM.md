# 🛡️ SLINGSHOT v4.3 TITANIUM: ESPECIFICACIÓN TÉCNICA MAESTRA

> **"La precisión institucional al servicio del trader individual. Zero Latency, Zero Cloud, Zero Noise."**
> **Versión:** 4.3 Titanium Edition | **Fecha:** 02 de Abril, 2026 | **Estado:** TOTALMENTE DESPLEGADO ✅

---

## 💎 1. VISIÓN ESTRATÉGICA (EL PIVOTE)
Slingshot v4.0 ha evolucionado de ser un SaaS Retail a una **Terminal de Trading Algorítmica Institucional Local-First**. Hemos eliminado el "ruido retail" (indicadores laggy) para centrarnos en la **Huella del Smart Money**. El sistema opera 100% en local, aprovechando la potencia de tu hardware personal para análisis de baja latencia.

### Core Philosophy:
*   **Local Sovereignty:** No hay bases de datos externas ni autenticación en la nube. Tú eres el dueño de tus datos y tu cómputo.
*   **Institutional Presence:** El motor busca barridas de liquidez, desequilibrios (FVGs) y bloques de órdenes (OBs) en KillZones UTC.
*   **Smart Money Divergence (SMT):** Comparación dinámica entre activos correlacionados (BTC/ETH) habilitada en el Jurado de Confluencia.

---

## 🏗️ 2. ARQUITECTURA TÉCNICA (One-Truth)

### 📡 El Pipeline Reactivo
1.  **Source:** Binance WebSockets (Stream de ticks ininterrumpido).
2.  **Core:** `MemoryStore` centralizado en RAM (Zero-Latency Storage).
3.  **Engine:** `main_router.py` coordina el flujo: Wyckoff → SMC Strategy → Risk Portero.
4.  **UI:** Next.js 15 + React 19 + Zustand 5 (Consumo masivo de datos WS).

### 📁 Estructura del Proyecto (Sincronizada)
```text
slingshot_gen1/
├── 📁 engine/                         # El Cerebro Algorítmico (FastAPI)
│   ├── 📁 core/                       # confluence, store (RAM), session_manager
│   ├── 📁 indicators/                 # Logic: smt, sessions, structure, macro...
│   ├── 📁 ml/                         # Machine Learning: inference, features
│   ├── 📁 api/                        # advisor (IA), ws_manager, config
│   ├── 📁 risk/                       # risk_manager (El Portero Institucional)
│   ├── 📁 strategies/                 # smc.py (Motor Único de Decisión)
│   └── main_router.py                 # El Orquestador Maestro
├── 📁 app/                            # La Terminal de Usuario (Next.js)
│   ├── 📁 (dashboard)/                # Radar, Signals, Chart, Heatmap, History
│   └── 📁 components/                 # SignalCardItem (Audit Evidence), UI Components
├── 📁 docs/                           # Documentación de Arquitectura y Especificación
│   └── 📁 Conocimientos/              # Memorias Teóricas: Algoritmos SMC y Regímenes
├── 📁 scripts/                        # Cajón de Herramientas (Tests & Tools)
├── 📁 tmp/                            # Almacenamiento local temporal y Forensics JSON
├── 📁 .agent/                         # Agentes, Workflows y Skills Consolidados
└── 📄 start.ps1                       # Lanzador One-Click (Launcher Maestro)
```

---

## 🏹 3. LÓGICA DE TRADING SMC (ASNA-4)

### 💠 Capa 1: Contexto Macro & Sesiones
*   **KillZones:** Londres y NY (Calculadas dinámicamente con DST).
*   **Sesgo Diario:** Definido por el barrido de liquidez de la sesión de Asia o el día anterior (PDH/PDL).

### 💠 Capa 2: Selección de Punto de Interés (POI)
*   **Order Blocks (OB):** Identificados por el motor de estructura como zonas de cacería institucional. Se exije el filtro **Wait For Sweep** (solo OBs Extremos que barrieron liquidez previa).
*   **Fair Value Gaps (FVG):** Detectados para filtrar entradas con el sesgo correcto.
*   **Paso 0.50 (Discount/Premium):** Solo Longs en Discount, solo Shorts en Premium.

### 💠 Capa 2.5: La Fusión Predictiva y Protocolo MACRO (V4.3)
*   **Conflict Manager (SMC vs IA):** Si la estructura SMC difiere de la proyección matemática de la Red Neuronal (XGBoost), la señal se suspende (STAND_BY). Operamos solo bajo Armonía Direccional Total.
*   **DEFCON 1 (Ghost Data):** Escáner de calendario económico y noticias. Si el mercado sufre un cisne negro (Ej: Guerra, Hack, Quiebra Bancaria), entra en "DEFCON 1" y anula la señal de inmediato para salvaguardar el fondo.
*   **Forensics JSON:** Post-Trade audit mode. El bot salva el estado completo de RAM y el Output del IA en `tmp/forensics_...` en tiempo real tras tomar una decisión.

### 💠 Capa 3: El Jurado de Confluencia (Audit Evidence)
Cada señal debe superar un score mínimo de **75%** evaluado en:
*   Narrativa de Mercado (Alineación con el régimen).
*   Huella de Volumen (RVOL ≥ 1.5x).
*   Divergencia SMT (Confirmación con activos correlacionados).
*   Proyección Neural (IA Probability).

---

## 🔒 4. EL PORTERO INSTITUCIONAL (GESTIÓN DE RIESGO)
Ninguna señal se emite si no cumple estrictamente:
1.  **Alineación HTF (Confluencia = 0):** Sin el respaldo de la temporalidad superior, el análisis expira antes de evaluarse.
2.  **Mitigación Instantánea (Volatilidad):** Si una vela genera una variación anormal (`> 2.5%`) durante un intento de entrada, se bloquea la orden por 'Flash Volatility' para eludir Slippage.
3.  **Ratio R:R ≥ 1.8** (Calculado por `RiskManager`).
4.  **Chain of Thought Forzado:** El LLM enciende `advisor.py` y analiza por capas obligatorias (Macro -> Estructura -> Sesión) para evitar ceguera estructural.

Las señales que no cumplen son redirigidas al **Modo Auditoría** en el frontend para el estudio de su rechazo.

---

## 🚀 5. GUÍA DE EJECUCIÓN PROFESIONAL
1.  **Lanzamiento:** Ejecutar `powershell ./start.ps1`. Levanta Backend (8000) y Frontend (3000) simultáneamente.
2.  **Mantenimiento:** El sistema rota los estados de sesión (`session_state_*.json`) automáticamente al cambio del día UTC.
3.  **Logs:** El sistema utiliza parches UTF-8 forzados para garantizar visualización de emojis y símbolos institucionales en Windows.

---
---
*Slingshot v4.3 Titanium — El Estándar Maestro de la Terminal Algorítmica.*
*Unificado por Antigravity — 02 de Abril, 2026*
