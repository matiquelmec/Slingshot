"""
engine/aiq/config.py — Configuración de Modelos y Endpoints NVIDIA AI-Q
=======================================================================
Centraliza las credenciales, URLs y catálogos de modelos NIM aprobados
en el Blueprint de Inteligencia Agéntica de Slingshot.
"""

import os
from pydantic_settings import BaseSettings
from pydantic import Field


class AIQSettings(BaseSettings):
    # API Key global de NVIDIA NIM
    NVIDIA_NIM_API_KEY: str = Field(
        default_factory=lambda: os.getenv("NVIDIA_NIM_API_KEY", "")
    )
    
    # URL base del clúster de inferencia de NVIDIA NIM
    NVIDIA_NIM_BASE_URL: str = Field(
        default="https://integrate.api.nvidia.com/v1"
    )

    # Catálogo Canónico de Modelos NIM (NVIDIA AI-Q Blueprint)
    # 1. Micro-Razonamiento Causal Sub-segundo (Post-Mortem Táctico & Vetos)
    MODEL_POST_MORTEM_FAST: str = Field(
        default="nvidia/nemotron-3.5-lightning-30b-a3b"
    )
    MODEL_POST_MORTEM_FALLBACK: str = Field(
        default="deepseek-ai/deepseek-v4-flash-0731"
    )

    # 2. Embeddings & Memoria Semántica Blackbox (RAG Multidimensional)
    MODEL_EMBEDDINGS: str = Field(
        default="nvidia/nemotron-3-embed-1b"
    )

    # 3. Meta-Planificador y Síntesis Macro Semanal (1M de Contexto)
    MODEL_MACRO_SYNTHESIZER: str = Field(
        default="nvidia/nemotron-3-ultra-550b-a55b"
    )

    # 4. Modelo Fundacional Relacional Multi-Tabla
    MODEL_RELATIONAL_PREDICTOR: str = Field(
        default="kumo/kumo-relational"
    )

    # Parámetros Operativos
    TIMEOUT_SECONDS_FAST: float = 12.0
    TIMEOUT_SECONDS_MACRO: float = 45.0
    MAX_RETRIES: int = 2

    class Config:
        env_file = ".env"
        extra = "ignore"


aiq_settings = AIQSettings()
