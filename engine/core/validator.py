import httpx
import json
import asyncio
from typing import Dict, Any, Optional
from engine.core.logger import logger
from engine.api.config import settings

class ValidatorAgent:
    """
    v13.0 SOVEREIGN INTELLIGENCE — AI Validator Agent.
    Actúa como un 'Segundo Analista' para señales en la zona gris (60-80% confluencia).
    Utiliza un LLM local (configurado en settings.OLLAMA_MODEL) para validar la narrativa estructural.
    """
    
    def __init__(self):
        self.url = f"{settings.OLLAMA_URL}/api/generate"
        self.model = settings.OLLAMA_MODEL
        logger.info(f"🤖 [VALIDATOR] Agente IA inicializado con modelo {self.model}")

    async def validate(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía la señal al LLM para una auditoría narrativa.
        Retorna: {"approved": bool, "ai_reasoning": str, "confidence": float}
        """
        asset = signal.get("asset", "UNKNOWN")
        conf = signal.get("confluence", {})
        score = conf.get("score", 0)
        
        # [PRE-FILTRO] Solo validamos señales en el rango 60-80%
        if score < 60 or score > 80:
            return {
                "approved": True, 
                "ai_reasoning": "Señal fuera de la zona gris. Aprobación técnica automática.",
                "confidence": 1.0
            }

        prompt = self._build_prompt(signal)
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json" # Forzar respuesta en JSON
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"❌ [VALIDATOR] Error de Ollama ({response.status_code})")
                    return self._fallback_response("Error de conexión con el núcleo neural.")

                result = response.json()
                response_text = result.get("response", "{}")
                
                try:
                    data = json.loads(response_text)
                    verdict = str(data.get("verdict", "VETO")).upper()
                    reason = data.get("reason", "Sin justificación proporcionada.")
                    confidence = float(data.get("confidence", 0.5))
                    
                    approved = verdict == "VEST" # VEST = Aprobar en terminología institucional
                    
                    logger.info(f"🤖 [VALIDATOR] {asset} AI Verdict: {verdict} ({confidence*100:.0f}%) | Reason: {reason[:100]}...")
                    
                    return {
                        "approved": approved,
                        "ai_reasoning": reason,
                        "confidence": confidence,
                        "verdict": verdict
                    }
                except Exception as e:
                    logger.error(f"❌ [VALIDATOR] Error parseando respuesta AI: {e} | Text: {response_text}")
                    return self._fallback_response("Error en el razonamiento sintético.")

        except Exception as e:
            logger.error(f"❌ [VALIDATOR] Excepción en ValidatorAgent: {e}")
            return self._fallback_response("Agente IA fuera de línea.")

    def _build_prompt(self, signal: Dict[str, Any]) -> str:
        """Construye el prompt institucional para el LLM."""
        asset = signal.get("asset")
        sig_type = signal.get("type", "LONG")
        conf = signal.get("confluence", {})
        score = conf.get("score")
        regime = signal.get("regime", "UNKNOWN")
        checklist = conf.get("checklist", [])
        
        # Resumen de checklist para el LLM
        checklist_str = "\n".join([f"- {c['factor']}: {c['status']} ({c['detail']})" for c in checklist])

        return f"""
        Actúa como un Senior Institutional Trader de Slingshot Apex. 
        Tu tarea es auditar una señal de trading en la 'Zona Gris' (Confluencia 60-80%).
        
        DATOS DE MERCADO:
        - Activo: {asset}
        - Dirección: {sig_type}
        - Régimen de Mercado: {regime}
        - Score Técnico: {score}%
        - Análisis de Confluencia:
        {checklist_str}
        
        CRITERIOS DE VEST (APROBACIÓN):
        1. La narrativa estructural debe ser coherente (Ej: Long en zona de descuento).
        2. No debe haber divergencias masivas en el volumen (RVOL).
        3. El sesgo institucional (OB/FVG) debe estar alineado.
        
        Responde estrictamente en formato JSON:
        {{
          "verdict": "VEST" o "VETO",
          "reason": "Explicación breve de máximo 2 frases",
          "confidence": 0.0 a 1.0
        }}
        """

    def _fallback_response(self, reason: str) -> Dict[str, Any]:
        """Respuesta de seguridad en caso de fallo de la IA."""
        return {
            "approved": True, # Por seguridad, si la IA falla no bloqueamos trades técnicos sólidos
            "ai_reasoning": f"FALLBACK: {reason}",
            "confidence": 0.0
        }

# Instancia global
validator_agent = ValidatorAgent()
