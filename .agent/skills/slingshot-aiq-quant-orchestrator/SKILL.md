---
name: slingshot-aiq-quant-orchestrator
description: Orquestador agéntico institucional para Slingshot basado en el NVIDIA AI-Q Blueprint. Conecta bases de datos relacionales SQLite WAL (Kumo Relational), vectoriza memoria semántica de mercado (nemotron-3-embed-1b) y despacha inferencia multi-nivel (nemotron-3.5-lightning, deepseek-v4-flash, nemotron-3-ultra-550b).
---

# Slingshot AI-Q Quantitative Orchestrator

Esta habilidad equipa a los agentes con los protocolos, modelos y flujos del **NVIDIA AI-Q Blueprint for Intelligent Agents** adaptado al motor de trading algorítmico Slingshot Apex Sovereign.

## 1. Patrón Arquitectónico NVIDIA AI-Q

```
[CONNECT]  SQLite WAL (closed_trades, factor_attribution, regime_history, audit_log)
    ↓
[RETRIEVE] Inferencia Relacional (Kumo Relational) + Memoria Semántica (nemotron-3-embed-1b)
    ↓
[REASON]   Consorcio Agéntico Multi-Modelo:
           • Sub-segundo: nemotron-3.5-lightning-30b / deepseek-v4-flash (Post-Mortem y Vetos)
           • Macro Semanal: nemotron-3-ultra-550b (1M Contexto - Paridad de Riesgo HRP)
    ↓
[ACT]      Inyección de Vetos en Gatekeeper y Asignación de Capital Multi-Broker (FTMO + Bitunix)
```

## 2. Modelos Aprobados de NVIDIA NIM

| Modelo | Propósito | Tiempo de Respuesta | Uso en Slingshot |
| :--- | :--- | :--- | :--- |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | Razonamiento Causal Táctico | $< 800\text{ ms}$ | Análisis asíncrono de Stop Loss y vetos preventivos |
| `deepseek-ai/deepseek-v4-flash-0731` | MoE de Alta Velocidad (284B) | $< 900\text{ ms}$ | Respaldo automático de ultra-baja latencia |
| `nvidia/nemotron-3-embed-1b` | Embeddings Semánticos | $< 50\text{ ms}$ | Indexación vectorial de anomalías en el Blackbox |
| `nvidia/nemotron-3-ultra-550b-a55b` | Mamba-Transformer (1M Contexto) | $5 - 15\text{ s}$ | Auditoría macro de fin de semana (Tear Sheet) |
| `kumo/kumo-relational` | Foundation Model Relacional | Por lote | Estimación de Win Rate sobre esquemas multi-tabla |

## 3. Protocolo de Operación en Dos Rieles

1. **Riel 1 (VPS de Producción):**
   * El bot en el servidor (`C:\Slingshot`) opera bajo el **Protocolo de Manos Libres** por 6 semanas.
   * Acumula $N \ge 100$ ejecuciones para permitir la convergencia bayesiana de pesos SMC.
   * FTMO Guardian protege la cuenta de \$100,000 USD contra drawdowns superiores a 4.5% diario.
2. **Riel 2 (Desarrollo Agéntico Local):**
   * Desarrollo de conectores relacionales y pruebas de integración en `engine/aiq/`.
   * Simulación de escalado multi-broker (`FTMO` + `FundedNext` + `Bitunix`).
