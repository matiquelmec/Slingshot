import asyncio
import json
import time
import pandas as pd
from datetime import datetime, timezone
from engine.api.advisor import generate_tactical_advice, _strategic_memo, start_ai_worker
from engine.core.logger import logger

async def test_gatekeeping():
    # 1. Iniciar worker para la cola
    start_ai_worker()
    print("\n[WORKER] Motor de inferencia local activo.")
    
    print("\n--- 🛡️ VERIFICACIÓN DE FUEGO REAL: GATEKEEPING COGNITIVO ---")
    
    # Mock de datos tácticos
    symbol = "SOLUSDT"
    
    # CASO 1: Score Bajo (65) - Debería ser bloqueado por el Gatekeeping
    print("\n[ESCENARIO 1] 📉 Baja Confluencia (Score: 65)")
    tactical_low = {
        "confluence_score": 65,
        "signal": "NEUTRAL",
        "price": 180.0,
        "regime": "RANGING"
    }
    
    start_t = time.time()
    # Lógica de gatekeeping (la misma que ws_manager)
    if tactical_low.get("signal") == "NEUTRAL" and tactical_low.get("confluence_score") < 70:
        advice = json.dumps({"verdict": "SIDEWAYS", "logic": "Confluencia Baja (Standby)", "threat": "LOW"})
    else:
        advice = await generate_tactical_advice(symbol, tactical_data=tactical_low)
    
    end_t = time.time()
    print(f"Resultado: {advice}")
    print(f"Latencia: {(end_t - start_t)*1000:.2f}ms (Esperado: < 5ms)")

    # CASO 2: Umbral de Diferencial (0.15%)
    print("\n[ESCENARIO 2] 🧊 Umbral de Diferencial (Variación: 0.05%)")
    _strategic_memo[symbol] = {"price": 180.0, "advice": '{"verdict": "GO", "logic": "Test Cache"}'}
    
    tactical_diff = {
        "confluence_score": 75,
        "signal": "NEUTRAL",
        "price": 180.05, # Variación de solo 0.05%
        "regime": "BULLISH"
    }
    
    start_t = time.time()
    advice_cached = await generate_tactical_advice(symbol, tactical_data=tactical_diff)
    end_t = time.time()
    
    print(f"Resultado: {advice_cached}")
    print(f"Latencia: {(end_t - start_t)*1000:.2f}ms (Esperado: < 1ms de Cache Hit)")

    # CASO 3: Fuego Real (Ollama + JSON)
    print("\n[ESCENARIO 3] 🔥 Alta Confluencia (Score: 85) -> Trigger Ollama")
    tactical_high = {
        "confluence_score": 85,
        "signal": "LONG",
        "price": 185.0,
        "regime": "BULLISH"
    }
    
    print("Invocando a Ollama (Veredicto Institucional v6.0)...")
    start_t = time.time()
    advice_ollama = await generate_tactical_advice(symbol, tactical_high)
    end_t = time.time()
    
    print(f"\nResultado Final JSON:\n{advice_ollama}")
    print(f"Latencia Final: {(end_t - start_t):.2f}s")
    
    print("\n✅ VERIFICACIÓN DE OPERACIÓN RELÁMPAGO COMPLETADA.")

if __name__ == "__main__":
    asyncio.run(test_gatekeeping())
