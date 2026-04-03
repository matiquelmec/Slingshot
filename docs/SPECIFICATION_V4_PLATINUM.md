# 🛡️ SLINGSHOT v4.3.5 TITANIUM: ESPECIFICACIÓN TÉCNICA MAESTRA

> **"La precisión institucional al servicio del trader individual. Zero Latency, Zero Cloud, Zero Noise."**
**Versión:** 4.3.5 Titanium Edition | **Fecha:** 03 de Abril, 2026 | **Estado:** TOTALMENTE DESPLEGADO ✅

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

### 📁 Estructura del Proyecto (Sincronizada a la Realidad Operativa v4.3.4)
```text
slingshot_gen1/
├── 📁 engine/                         # El Cerebro Algorítmico (FastAPI)
│   ├── 📁 core/                       # confluence, store (RAM), session_manager, logger (SRE)
│   ├── 📁 indicators/                 # Logic: smt, sessions, structure, macro...
│   ├── 📁 execution/                  # El Puente Mecánico: ftmo_bridge, bitunix_bridge
│   ├── 📁 ml/                         # Machine Learning: inference, features
│   ├── 📁 api/                        # advisor (IA), ws_manager, config, json_utils, main
│   ├── 📁 risk/                       # risk_manager (El Portero Institucional)
│   ├── 📁 strategies/                 # smc.py (Motor Único de Decisión)
│   ├── 📁 router/                     # Módulos Especializados: analyzer, dispatcher, gatekeeper
│   └── main_router.py                 # El Orquestador Maestro (Facade)
├── 📁 app/                            # La Terminal de Usuario (Next.js)
│   ├── 📁 (dashboard)/                # Radar, Signals, Chart, Heatmap, History
│   └── 📁 components/                 # SignalCardItem (Audit Evidence), UI Components
├── 📁 docs/                           # Documentación de Arquitectura y Especificación
│   └── 📁 Conocimientos/              # Memorias Teóricas: Algoritmos SMC y Regímenes
├── 📁 scripts/                        # Cajón de Herramientas (Tests, refactors, downlads)
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

### 💠 Capa 2.5: Arquitectura Inteligente Zero-Latency (v4.3 Titanium)
Hemos asegurado tiempos de reacción algorítmicos sub-50ms bajo la carga extrema del WebSocket a través de tácticas maestras:
1.  **HFT Payload Pruning:** Serialización JSON exenta del histórico inútil mediante `payload.pop('candles')`, aliviando el Event Loop.
2.  **Ultra-Buffer Circular:** Uso de matrices C-Compiled (`collections.deque(maxlen=300)`) descartando recolección de basura OOM.
3.  **Vectorización Fast-Path:** Solo el Tick Reciente viaja por `pd.to_datetime(...)`, anexándose algebraicamente en Pandas a los dates oxidados pre-cacheados.
4.  **SMC Slice & Persistencia O(1):** `structure.py` procesa un micro-slice (`df.tail(50)`), fusionándolo dinámicamente con inyecciones de Long-Term Memory SMC tolerantes al envejecimiento temporal.

---

### 💠 Capa 2.6: Protocolos de Supervivencia VPS (Hardening v4.3.5)
Para despliegues en entornos hostiles (VPS Londres/NY), se han implementado 4 blindajes contra fallos:
1.  **Stale Guard (Frontend):** Monitorización de gaps en WebSocket (>60s). Al detectar una pestaña "zombie" (tras suspensión), el sistema purga mensajes obsoletos y realiza un resync forzado al `HEAD` de los datos.
2.  **Advisor Aislado (Timeout 45s):** El motor LLM (Ollama) está configurado con un semáforo de concurrencia e inyección de precio en vivo ($900 sync). Si la IA no responde en 45s, el sistema libera recursos para priorizar la ejecución técnica (Fast Path).
3.  **Resurrección Automática (systemd):** Configuración `Restart=always` con 5s de delay. En caso de crash de proceso o OOM del VPS, el bot revive en <20s reconstruyendo todo el estado estructural desde el histórico.
4.  **Blindaje Anti-Alucinación (Sensorized Priority):** Los datos del Radar (RVOL, Killzone status) se inyectan como "Verdad Absoluta" en el prompt. El Advisor tiene prohibido contradecir estos flags (Ej: No puede reportar RVOL bajo si el radar marca 20x).

---

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
