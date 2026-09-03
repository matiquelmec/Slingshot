# engine/tests/test_ai_advisor.py
import pytest
import asyncio
import json
from engine.api.advisor import ai_worker, _ai_queue, generate_tactical_advice, extract_json_from_llm
from engine.api.config import settings

@pytest.mark.asyncio
async def test_nvidia_openrouter_inference_and_latency():
    """Valida la inferencia en tiempo real con OpenRouter / NVIDIA Nemotron y mide la latencia."""
    assert settings.OPENROUTER_API_KEY, "OPENROUTER_API_KEY debe estar configurada en el entorno"
    
    worker_task = asyncio.create_task(ai_worker())
    
    tactical_data = {
        'price': 2520.0,
        'interval': '1h',
        'signal': 'LONG',
        'regime': 'TRENDING_BULL',
        'diagnostic': {'rvol': 2.1},
        'smc': {'order_blocks': [{'type': 'bullish'}], 'fvgs': [{'type': 'bullish'}]},
        'key_levels': {'support': '2480.0', 'resistance': '2580.0'}
    }
    
    start_time = asyncio.get_event_loop().time()
    raw_advice = await generate_tactical_advice('PAXGUSDT', tactical_data, current_session='LONDON')
    elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000.0
    
    worker_task.cancel()
    
    print(f"\n[AI BENCHMARK] Latencia de Inferencia: {elapsed_ms:.1f} ms")
    
    # 1. Validación de JSON estricto
    clean_json = extract_json_from_llm(raw_advice)
    parsed = json.loads(clean_json)
    
    assert "verdict" in parsed, "El JSON debe contener 'verdict'"
    assert "threat" in parsed, "El JSON debe contener 'threat'"
    assert "logic" in parsed, "El JSON debe contener 'logic'"
    assert parsed["verdict"] in ["GO", "AVOID", "SIDEWAYS"], f"Veredicto no estándar: {parsed['verdict']}"
    assert parsed["threat"] in ["LOW", "MEDIUM", "HIGH"], f"Nivel de amenaza no estándar: {parsed['threat']}"

def test_json_extractor_resilience():
    """Valida que el extractor de JSON tolere markdown, etiquetas backtick y texto conversacional."""
    dirty_output_1 = '```json\n{"verdict": "GO", "threat": "LOW", "logic": "OB Limpio"}\n```'
    dirty_output_2 = 'Aquí está el resultado institucional:\n{"verdict": "AVOID", "threat": "HIGH", "logic": "Divergencia SMT"}\nSaludos cordiales.'
    
    res_1 = json.loads(extract_json_from_llm(dirty_output_1))
    res_2 = json.loads(extract_json_from_llm(dirty_output_2))
    
    assert res_1["verdict"] == "GO"
    assert res_2["verdict"] == "AVOID"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
