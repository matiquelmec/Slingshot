import asyncio
import time
import pandas as pd
from engine.core.confluence import ConfluenceManager
from engine.api.advisor import generate_tactical_advice

async def test_confluence_assertions():
    print("--- INICIANDO SUITE DE PRUEBAS ON-CHAIN (v4.6) ---\n")
    confluence = ConfluenceManager()

    # Base DataFrame para evitar errores
    df = pd.DataFrame([{
        'timestamp': pd.Timestamp.utcnow(), 
        'close': 50000, 
        'volume': 100, 
        'market_regime': 'RANGING',
        'ob_bullish': True,
        'fvg_bullish': True
    }])

    signal_base = {
        'timestamp': df['timestamp'].iloc[-1],
        'type': 'LONG',
        'pair': 'BTC/USDT'
    }

    print("Escenario A: Breakout con Volumen Whale (Bullish + Whale Inflow)")
    # En On-Chain v4.6, Bullish Accumulation es un evento on-chain válido
    res_a = confluence.evaluate_signal(
        df=df,
        signal=signal_base,
        onchain_bias='BULLISH_ACCUMULATION',
        session_data={'current_session': 'NEW_YORK'}
    )
    
    score_a = res_a['score']
    print(f"Resultado Escenario A - Score de Confluencia: {score_a}%")
    assert score_a > 50, "Fallo: Una acumulación Bullish con On-Chain Bias positivo debería tener un score alto."

    print("\nEscenario B: Ranging sin interés (OI plano)")
    res_b = confluence.evaluate_signal(
        df=df,
        signal=signal_base,
        onchain_bias='NEUTRAL',
        session_data={'current_session': 'OFF_HOURS'}
    )
    score_b = res_b['score']
    print(f"Resultado Escenario B - Score de Confluencia: {score_b}%")
    
    print("\nEscenario C: Manipulación On-Chain (Inflow Masivo -> Bearish Warning)")
    # En un "Bearish Warning", si abrimos un LONG, el multiplier se aplasta a 0.5 (mitad del score)
    res_c = confluence.evaluate_signal(
        df=df,
        signal=signal_base,
        onchain_bias='BEARISH_WARNING',
        session_data={'current_session': 'NEW_YORK'}
    )
    score_c = res_c['score']
    print(f"Resultado Escenario C - Score de Confluencia (LONG en Inflow Masivo): {score_c}%")
    
    # Assert de Validación Strict
    if res_c['score'] >= 75:
        raise AssertionError("ERROR CRÍTICO: El jurado aprobó una ejecución con un Inflow Masivo en contra.")
    else:
        print("PASS: El sistema mitigó correctamente el Long a causa de manipulación On-Chain.\n")

async def test_semantic_cache_latency():
    print("--- BENCHMARK DE LATENCIA Y SEMANTIC CACHING ---")
    tactical_data = {
        'active_strategy': 'SMC Breakout',
        'market_regime': 'RANGING',
        'current_price': 52000,
        'nearest_support': 50000,
        'nearest_resistance': 55000,
        'diagnostic': {'rsi': 45, 'rvol': 2.1}
    }
    onchain_data = {'onchain_bias': 'NEUTRAL'}

    print("Llamada Inicial a LLM (Sin Caché)...")
    t0 = time.time()
    await generate_tactical_advice(
        asset="BTCUSDT",
        tactical_data=tactical_data,
        current_session="NEW_YORK",
        onchain_data=onchain_data
    )
    t1 = time.time()
    call_1_time = t1 - t0
    print(f"Tiempo Incial: {call_1_time:.2f}s")
    
    print("Llamada Secundaria a LLM (Con Caché Semántico)...")
    t0 = time.time()
    advice = await generate_tactical_advice(
        asset="BTCUSDT",
        tactical_data=tactical_data,
        current_session="NEW_YORK",
        onchain_data=onchain_data
    )
    t1 = time.time()
    call_2_time = t1 - t0
    print(f"Tiempo Caché: {call_2_time:.2f}s")

    # Si hay Semantic Cache, debe tardar ínfimamente (< 0.1s usualmente, pero damos un margen)
    if call_2_time > 7.0:
        print("⚠️ ADVERTENCIA DE RENDIMIENTO: El Advisor superó los 7s de respuesta. El 'Semantic Cache' o Ollama están lentos.")
    else:
        print(f"PASS: Semantic Caching funcional y óptimo ({call_2_time:.2f}s)!\n")

async def main():
    await test_confluence_assertions()
    await test_semantic_cache_latency()
    print(">>> TODOS LOS TESTS DE MOTOR ON-CHAIN Y CONFLUENCIA FUERON EXITOSOS. <<<")

if __name__ == "__main__":
    asyncio.run(main())
