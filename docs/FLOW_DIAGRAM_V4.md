# 🏹 SLINGSHOT v4.3 — DIAMANTE INSTITUCIONAL (MASTERPLAN)

> **"La precisión no es una opción, es nuestra arquitectura."**
> **Versión:** 4.3 Platinum Masterplan | **Actualizado:** 02 de Abril, 2026

---

## 💎 Visión General del Sistema (Capa Platinum)

Este diagrama representa el flujo de datos de baja latencia (Zero-Latency) desde la captura del tick hasta la ejecución de la señal filtrada por el Portero Institucional.

![Visual Masterplan Slingshot v4.3](file:///C:/Users/Mat%C3%ADas%20Riquelme/.gemini/antigravity/brain/b834964e-5d22-4b31-82ed-ea992899c39d/arch_masterplan_v4_1775104346480.png)

---

## 🔄 Flujo de Datos Institucional (Táctico)

```mermaid
flowchart TD
    %% --- CAPA DE INGESTA (TELEMETRÍA) ---
    subgraph DATA_LAYER ["🌐 CAPA DE DATOS (REAL-TIME)"]
        BN["🛰️ Binance WS\nTicks & Liquidez"]
        GH["👻 Ghost Data\nMacro & Noticias"]
        REG["📋 Registry\nFan-out n-Clients"]
    end

    %% --- MOTOR DE INTELIGENCIA (EL CEREBRO) ---
    subgraph ENGINE_LAYER ["🧠 MOTOR DE INTELIGENCIA PLATINUM"]
        ML["🤖 ML Engine\nXGBoost v2"]
        DRIFT["🚨 DRIFT MONITOR\nPSI & Accuracy"]
        SMC["🏛️ SMC Core\nOB/FVG/Structure"]
        HTF[" telescope: HTF Bias\nInstitucional H1/H4"]
    end

    %% --- PORTEROS DE RIESGO (LOS FILTROS) ---
    subgraph RISK_LAYER ["⚖️ EL PORTERO INSTITUCIONAL"]
        direction TB
        G1{"🔒 HTF GATE\n¿Sesgo correcto?"}
        G2{"🔒 R:R GATE\n¿Ratio ≥ 1.8?"}
        G3{"🔒 JURY GATE\n¿Score ≥ 75%?"}
    end

    %% --- CAPA DE PERSISTENCIA Y SALIDA ---
    subgraph OUTPUT_LAYER ["🛡️ AUDITORÍA & ACCIÓN"]
        RAM["💾 RAM Store\nZero-Latency"]
        ADV["🧠 AI Advisor\nBriefing Llamat-3"]
        TG["📱 Telegram\nInstitutional Alert"]
        UI["🖥️ Terminal UI\nNext.js Dashboard"]
    end

    %% --- CONEXIONES ---
    BN & GH --> REG
    REG --> ML & SMC & HTF
    ML <-.->|Supervisión| DRIFT
    
    ML & SMC & HTF --> G1
    G1 -- "Aprobado" --> G2
    G2 -- "Aprobado" --> G3
    G1 & G2 & G3 -- "RECHAZO" --> RAM
    
    G3 -- "SEÑAL ELITE" --> RAM
    RAM --> ADV & TG & UI

    %% --- ESTILOS PLATINUM ---
    style BN fill:#0b1e3b,color:#fff,stroke:#1a3a6e
    style GH fill:#0b1e3b,color:#fff,stroke:#1a3a6e
    style REG fill:#1a3a6e,color:#fff
    
    style ENGINE_LAYER fill:#0a0a0a,color:#ffd700,stroke:#ffd700,stroke-width:2px
    style ML fill:#1c1c1c,color:#fff,stroke:#4a4a4a
    style DRIFT fill:#7a1f1f,color:#fff,stroke:#ff4d4d
    style SMC fill:#1c1c1c,color:#fff,stroke:#4a4a4a
    style HTF fill:#1c1c1c,color:#fff,stroke:#4a4a4a

    style G1 fill:#4a2d0d,color:#fff,stroke:#ffd700
    style G2 fill:#4a2d0d,color:#fff,stroke:#ffd700
    style G3 fill:#4a2d0d,color:#fff,stroke:#ffd700

    style RAM fill:#0d2a1a,color:#fff,stroke:#1a5236
    style TG fill:#0088cc,color:#fff,stroke:#fff
    style UI fill:#1a3a6e,color:#fff
    style ADV fill:#4a2d0d,color:#fff
```

---

## 🏆 Hitos Logrados (V4.3 Diamond Phase)

| Estado | Módulo | Descripción |
|:---:|---|---|
| ✅ | **Drift Monitor** | PSI (Population Stability Index) & Rolling Accuracy activo. |
| ✅ | **Modular Router** | Separación en `analyzer.py`, `gatekeeper.py` y `dispatcher.py`. |
| ✅ | **Telegram Core** | Pipeline de alertas institucionales con MarkdownV2. |
| ✅ | **Memory Store** | Hidratación Zero-Latency para el AI Advisor. |
| ✅ | **SMC Engine** | Identificación de Liquidez, OBs y FVGs en tiempo real. |

---

## 🔭 Roadmap Siguiente Nivel

1.  **Capa SMT Dinámica**: Comparación multiactivo parametrizable (no solo BTC/ETH).
2.  **Backtest en Caliente**: Simulación de la estrategia actual en el histórico local al detectar drift.
3.  **Radar de Clusters**: Agrupación masiva de órdenes en el heatmap para prever barridas mayores.

---
*Actualizado por Antigravity — Slingshot v4.3 Platinum — 02 Abril 2026*
