"""
engine/agents/post_mortem_agent.py — SOP-76 NVIDIA NIM Post-Mortem & Anti-Pattern Synthesizer
=============================================================================================
Agente autónomo asincrónico que analiza trades cerrados en pérdida (Stop Loss o salida defensiva)
utilizando NVIDIA NIM (`nvidia/nemotron-3.5-lightning-30b-a3b` o `deepseek-ai/deepseek-v4-flash-0731`)
para descubrir patrones de falla ocultos, registrar lecciones aprendidas y aplicar vetos dinámicos.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
import httpx

from engine.core.logger import logger
from engine.api.config import settings
from engine.core.vault import vault


class PostMortemAgent:
    """
    Agente Asincrónico de Diagnóstico Causal y Síntesis de Anti-Patrones.
    """

    def __init__(self):
        self.nim_url = "https://integrate.api.nvidia.com/v1/chat/completions"
        self.default_model = getattr(settings, "NVIDIA_NIM_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
        self._lock = asyncio.Lock()

    async def analyze_closed_loss_trade(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl_r: float,
        pnl_usd: float,
        exit_reason: str,
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta el análisis causal asíncrono con NVIDIA NIM sin bloquear la ejecución.
        """
        context_data = context_data or {}
        regime = context_data.get("regime", "UNKNOWN")
        session = context_data.get("session", "UNKNOWN")
        rvol = context_data.get("rvol", 1.0)
        active_factors = context_data.get("factors", [])

        # Prompt de grado institucional para NVIDIA NIM
        prompt = f"""[SLINGSHOT QUANTITATIVE POST-MORTEM AUDIT]
Trade ID: {trade_id} | Activo: {symbol} | Dirección: {side}
Precio Entrada: {entry_price} | Precio Salida: {exit_price} | Motivo: {exit_reason}
PnL en R: {pnl_r:.2f}R | PnL USD: ${pnl_usd:.2f}
Régimen: {regime} | Sesión: {session} | RVOL: {rvol:.2f}x
Factores Activos al entrar: {', '.join(str(f) for f in active_factors) if active_factors else 'Ninguno'}

TAREA:
Analiza la causa raíz de la pérdida y determina si existe un patrón de trampa institucional o manipulación recurrente.
Emite tu diagnóstico estrictamente en JSON puro con las siguientes claves:
1. "loss_category": Uno de ["LIQUIDITY_SWEEP", "MACRO_NEWS_SHOCK", "FALSE_BREAKOUT_CHOP", "MOMENTUM_EXHAUSTION", "SPREAD_SLIPPAGE", "EXECUTION_ERROR"].
2. "causal_analysis": Explicación técnica concisa (máximo 2 oraciones).
3. "preventive_rule": Regla preventiva accionable (máximo 1 oración).
4. "apply_veto": true o false (si se debe vetar temporalmente el activo para evitar repetición de trampa).
5. "veto_duration_hours": Horas de veto sugeridas (entre 4 y 24) si apply_veto es true.

RESPONDE SÓLO EL OBJETO JSON:
{{
  "loss_category": "...",
  "causal_analysis": "...",
  "preventive_rule": "...",
  "apply_veto": true,
  "veto_duration_hours": 12
}}"""

        api_key = getattr(settings, "NVIDIA_NIM_API_KEY", None)
        report = None

        if api_key:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Slingshot-PostMortem/1.0"
            }
            payload = {
                "model": self.default_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 512,
                "response_format": {"type": "json_object"}
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(self.nim_url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        raw_text = res_json["choices"][0]["message"]["content"].strip()
                        report = json.loads(raw_text)
                        logger.info(f"🧠 [POST-MORTEM NIM] Diagnóstico causal completado para {symbol} ({report.get('loss_category')})")
            except Exception as e:
                logger.warning(f"[POST-MORTEM NIM] Falla en consulta a NVIDIA NIM ({e}). Activando evaluador determinístico...")

        if not report:
            # Fallback cuantitativo determinístico
            if abs(pnl_r) >= 1.0 and rvol >= 1.8:
                cat = "LIQUIDITY_SWEEP"
                expl = f"Barrido de liquidez violento en {symbol} con volumen institucional alto ({rvol:.1f}x)."
                veto = True
            elif regime in ("CHOPPY", "RANGING"):
                cat = "FALSE_BREAKOUT_CHOP"
                expl = f"Falso rompimiento en régimen de compresión lateral ({regime})."
                veto = False
            else:
                cat = "MOMENTUM_EXHAUSTION"
                expl = f"Agotamiento de impulso en sesión {session} frente a niveles clave."
                veto = False

            report = {
                "loss_category": cat,
                "causal_analysis": expl,
                "preventive_rule": f"Exigir confluencia mayor a 75% para {symbol} en condiciones similares.",
                "apply_veto": veto,
                "veto_duration_hours": 8 if veto else 0
            }

        # Persistir el reporte en la bóveda
        try:
            vault.record_post_mortem_report(
                trade_id=trade_id,
                symbol=symbol,
                side=side,
                pnl_usd=pnl_usd,
                loss_category=report.get("loss_category", "UNKNOWN"),
                causal_analysis=report.get("causal_analysis", ""),
                preventive_rule=report.get("preventive_rule", "")
            )

            # Si se recomendó veto, registrarlo de inmediato
            if report.get("apply_veto", False):
                hrs = int(report.get("veto_duration_hours", 12))
                reason = f"[VETO {report.get('loss_category')}]: {report.get('preventive_rule')}"
                vault.add_post_mortem_veto(
                    symbol=symbol,
                    condition_tag=report.get("loss_category", "POST_MORTEM"),
                    reason=reason,
                    duration_seconds=hrs * 3600
                )
                logger.warning(f"🛑 [POST-MORTEM VETO] Veto temporal activado para {symbol} ({hrs}h): {reason}")
        except Exception as v_err:
            logger.error(f"[POST-MORTEM AGENT] Error guardando veto/reporte en Vault: {v_err}")

        return report

    def trigger_async_analysis(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl_r: float,
        pnl_usd: float,
        exit_reason: str,
        context_data: Optional[Dict[str, Any]] = None
    ):
        """Dispara el análisis en background sin esperar respuesta."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.analyze_closed_loss_trade(
                    trade_id, symbol, side, entry_price, exit_price, pnl_r, pnl_usd, exit_reason, context_data
                ))
            else:
                asyncio.run(self.analyze_closed_loss_trade(
                    trade_id, symbol, side, entry_price, exit_price, pnl_r, pnl_usd, exit_reason, context_data
                ))
        except Exception as err:
            logger.debug(f"[POST-MORTEM AGENT] Error disparando tarea asíncrona: {err}")


# Instancia Singleton
post_mortem_agent = PostMortemAgent()
