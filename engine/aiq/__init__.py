"""
engine/aiq — NVIDIA AI-Q Blueprint Architecture for Slingshot Quantitative Trading
===================================================================================
Patrón empresarial de inteligencia agéntica:
1. CONNECT: Conectores de datos vivos a SQLite WAL (trades, confluencias, régimen, auditoría).
2. RETRIEVE: Inferencia relacional (Kumo Relational) y memoria semántica vectorial (nemotron-3-embed-1b).
3. REASON: Consorcio agéntico multi-modelo (nemotron-3.5-lightning, deepseek-v4-flash, nemotron-3-ultra-550b).
4. ACT: Aplicación de vetos preventivos en el Gatekeeper y balanceo institucional de riesgo (HRP).
"""

from engine.aiq.config import aiq_settings
from engine.aiq.relational_connector import AIQRelationalConnector, aiq_relational_connector
from engine.aiq.semantic_memory import AIQSemanticMemory, aiq_semantic_memory
from engine.aiq.agent_router import AIQAgentRouter, aiq_agent_router

__all__ = [
    "aiq_settings",
    "AIQRelationalConnector",
    "aiq_relational_connector",
    "AIQSemanticMemory",
    "aiq_semantic_memory",
    "AIQAgentRouter",
    "aiq_agent_router",
]
