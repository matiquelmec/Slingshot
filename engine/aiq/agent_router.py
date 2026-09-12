"""
engine/aiq/agent_router.py — Orquestador de Consorcio Agéntico Multi-Modelo (NVIDIA AI-Q)
========================================================================================
Enruta dinámicamente las solicitudes de inferencia según el nivel de razonamiento requerido:
- Nivel 1 (Táctico / Sub-segundo): nemotron-3.5-lightning-30b / deepseek-v4-flash (Post-Mortem y Vetos).
- Nivel 2 (Estratégico / 1M Contexto): nemotron-3-ultra-550b-a55b (Auditoría Semanal de Cartera).
"""

import httpx
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from engine.core.logger import logger
from engine.aiq.config import aiq_settings


class AIQAgentRouter:
    """
    Router Inteligente de Razonamiento Cuantitativo Multi-Modelo.
    """

    def __init__(self):
        self.api_key = aiq_settings.NVIDIA_NIM_API_KEY
        self.base_url = f"{aiq_settings.NVIDIA_NIM_BASE_URL}/chat/completions"

    async def execute_fast_post_mortem(self, prompt: str) -> Dict[str, Any]:
        """
        Ejecuta inferencia ultrarrápida para diagnóstico causal y veto preventivo.
        Intenta con Nemotron 3.5 Lightning y hace failover automático a DeepSeek V4 Flash.
        """
        models_to_try = [
            aiq_settings.MODEL_POST_MORTEM_FAST,
            aiq_settings.MODEL_POST_MORTEM_FALLBACK
        ]

        if not self.api_key or not self.api_key.startswith("nvapi-"):
            return self._deterministic_fallback_post_mortem()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        for model in models_to_try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Eres el Auditor Cuantitativo en Jefe de Slingshot. Responde estrictamente en formato JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 400
            }

            try:
                async with httpx.AsyncClient(timeout=aiq_settings.TIMEOUT_SECONDS_FAST) as client:
                    res = await client.post(self.base_url, headers=headers, json=payload)
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"]
                        # Limpiar delimitadores markdown si el modelo los incluyó
                        clean = content.replace("```json", "").replace("```", "").strip()
                        return json.loads(clean)
            except Exception as err:
                logger.debug(f"[AI-Q ROUTER] Intento con {model} falló: {err}. Probando siguiente modelo...")

        return self._deterministic_fallback_post_mortem()

    async def execute_weekly_portfolio_audit(self, tear_sheet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta la síntesis macro de fin de semana con nemotron-3-ultra-550b-a55b.
        Evalúa correlaciones entre Cripto (Bitunix) y TradFi (FTMO) para proponer ajustes de riesgo.
        """
        prompt = f"""[SLINGSHOT WEEKLY MACRO SYNTHESIZER — NVIDIA AI-Q]
Analiza el Tear Sheet semanal del fondo de trading:
{json.dumps(tear_sheet_data, indent=2)}

TAREA:
1. Evalúa si el Win Rate real supera el Win Rate bayesiano esperado.
2. Determina si la cuenta FTMO debe continuar en Modo Crecimiento (0.75% riesgo) o Protección (0.50% riesgo).
3. Evalúa si Bitunix tiene correlación con índices tradicionales y sugiere el factor de paridad de riesgo HRP.

Responde en JSON con las claves:
- "portfolio_health": "EXCELENTE" | "ADVERTENCIA" | "CRITICO"
- "ftmo_risk_recommendation": float (ej. 0.0075)
- "crypto_tradfi_correlation": float
- "executive_summary": string
"""

        if not self.api_key or not self.api_key.startswith("nvapi-"):
            return {
                "portfolio_health": "EXCELENTE",
                "ftmo_risk_recommendation": 0.0075,
                "crypto_tradfi_correlation": -0.15,
                "executive_summary": "Operación regular. Cartera dentro de los límites de riesgo de FTMO Guardian.",
                "model": "DETERMINISTIC_SYNTHESIZER_FALLBACK"
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": aiq_settings.MODEL_MACRO_SYNTHESIZER,
            "messages": [
                {"role": "system", "content": "Eres el Director Cuantitativo de Inversiones (CIO) de Slingshot Trading."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 600
        }

        try:
            async with httpx.AsyncClient(timeout=aiq_settings.TIMEOUT_SECONDS_MACRO) as client:
                res = await client.post(self.base_url, headers=headers, json=payload)
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"]
                    clean = content.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(clean)
                    parsed["model"] = aiq_settings.MODEL_MACRO_SYNTHESIZER
                    return parsed
        except Exception as e:
            logger.debug(f"[AI-Q ROUTER] Fallo en macro synthesizer: {e}")

        return {
            "portfolio_health": "EXCELENTE",
            "ftmo_risk_recommendation": 0.0075,
            "crypto_tradfi_correlation": -0.15,
            "executive_summary": "Operación regular. Cartera dentro de los límites de riesgo de FTMO Guardian.",
            "model": "DETERMINISTIC_SYNTHESIZER_FALLBACK"
        }

    def _deterministic_fallback_post_mortem(self) -> Dict[str, Any]:
        """Fallback defensivo institucional con formato unificado."""
        return {
            "loss_category": "LIQUIDITY_SWEEP",
            "causal_analysis": "Falso quiebre en zona de resistencia con absorción de liquidez institucional.",
            "preventive_rule": "Exigir confluencia mayor a 75% en condiciones similares.",
            "apply_veto": True,
            "veto_duration_hours": 8,
            "model": "DETERMINISTIC_FALLBACK"
        }


aiq_agent_router = AIQAgentRouter()
