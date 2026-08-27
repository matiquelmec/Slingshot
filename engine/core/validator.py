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
        
        import os
        # [PRE-FILTRO] Fast path / Backtest mode
        if os.environ.get("DISABLE_AI_VALIDATOR") == "true" or score < 60 or score > 80:
            return {
                "approved": True, 
                "ai_reasoning": "Aprobación técnica automática (Bypass / Backtest Mode).",
                "confidence": 1.0
            }

        prompt = self._build_prompt(signal)
        
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                if settings.OPENROUTER_API_KEY:
                    url = "https://openrouter.ai/api/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": settings.OPENROUTER_MODEL or "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"}
                    }
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        result = response.json()
                        response_text = result["choices"][0]["message"]["content"].strip()
                    else:
                        return self._fallback_response("Aprobación técnica determinística (OpenRouter fallback).")
                elif settings.GROQ_API_KEY:
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    groq_payload = {
                        "model": "qwen/qwen3.6-27b",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"}
                    }
                    response = await client.post(url, json=groq_payload, headers=headers)
                    if response.status_code == 200:
                        result = response.json()
                        response_text = result["choices"][0]["message"]["content"].strip()
                    else:
                        return self._fallback_response("Aprobación técnica determinística (Groq fallback).")
                elif settings.GEMINI_API_KEY:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
                    gemini_payload = {
                        "contents": [{
                            "parts": [{"text": prompt}]
                        }],
                        "generationConfig": {
                            "responseMimeType": "application/json"
                        }
                    }
                    response = await client.post(url, json=gemini_payload)
                    
                    if response.status_code != 200:
                        logger.error(f"❌ [VALIDATOR] Error de Gemini API ({response.status_code}) - {response.text}")
                        return self._fallback_response("Error de conexión con el núcleo neural en la nube de Google.")
                        
                    result = response.json()
                    try:
                        response_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    except (KeyError, IndexError):
                        response_text = "{}"
                else:
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
                        return self._fallback_response("Error de conexión con el núcleo neural local.")

                    result = response.json()
                    response_text = result.get("response", "{}")
                
                try:
                    data = json.loads(response_text)
                    verdict = str(data.get("verdict", "VETO")).upper().strip()
                    reason = data.get("reason", "Sin justificación proporcionada.")
                    confidence = float(data.get("confidence", 0.5))
                    
                    # Robustez v13.1.2: Acepta variaciones de aprobación de modelos en la nube (Groq/Gemini)
                    approved = verdict in ("VEST", "APPROVE", "APPROVED", "GO", "YES", "TRUE")
                    
                    logger.info(f"🤖 [VALIDATOR] {asset} AI Verdict: {verdict} ({confidence*100:.0f}%) | Approved: {approved} | Reason: {reason[:100]}...")
                    
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
