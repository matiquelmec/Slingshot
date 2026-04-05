
import asyncio
import logging
import json
import os
import sys

# Inyectar el root del proyecto en el path para evitar ModuleNotFoundError
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from engine.api.advisor import generate_tactical_advice

# Configurar logging mínimo
logging.basicConfig(level=logging.INFO)

async def test_advisor_v5_output():
    print("\n" + "="*60)
    print(" 🧪 SIMULACIÓN DE INFORME IA v5.4.3 UNIFIED PLATINUM")
    print("="*60)
    
    # Datos Sintéticos de Alta Fidelidad (v5)
    tactical_data = {
        "current_price": 98450.25,
        "symbol": "BTCUSDT",
        "regime": "ACCUMULATION",
        "strategy": "SMC_5.4_PRO",
        "diagnostic": {
            "rsi": 32,
            "macd_bullish_cross": True,
            "bbwp": 92.5,
            "squeeze_active": True,
            "bullish_divergence": True,
            "rvol": 4.5,
            "z_score": 6.22  # ANOMALÍA INSTITUCIONAL CRÍTICA
        },
        "key_levels": {
            "supports": [{"price": 97800.0, "strength": 0.9}],
            "resistances": [{"price": 99500.0, "strength": 0.85}]
        },
        "ml_projection": {
            "direction": "long",
            "probability": 78.4
        },
        "fibonacci": {
            "swing_high": 102000.0,
            "swing_low": 95000.0,
            "levels": {"0.618": 97660.0, "0.66": 97400.0},
            "is_whale_leg": True
        },
        "htf_bias": {
            "direction": "bullish",
            "reason": "DXY en caída libre y Nasdaq rompiendo máximos."
        }
    }
    
    # Mocking external session data (Killzone ON via Monkey Patch)
    from engine.core.session_manager import session_manager
    session_manager.is_killzone_active = lambda: True
    
    print("\n🚀 Generando análisis con Ollama (Prioridad HIGH)...")
    
    # Llamar al advisor real con la firma v5.4.3
    advice = await generate_tactical_advice(
        asset="BTCUSDT",
        tactical_data=tactical_data,
        current_session="LONDRES (OPEN)",
        ml_projection=tactical_data["ml_projection"]
    )
    
    print("\n" + "─"*60)
    print(f"📄 RESULTADO DEL ADVISOR (MOTOR v5.4.3 PLATINUM):")
    if not advice or len(advice.strip()) < 10:
        print("⚠️  ADVERTENCIA: La IA devolvió un informe vacío o demasiado corto.")
    else:
        print(f"\n{advice}\n")
    print("─"*60 + "\n")
    print("✅ SIMULACIÓN FINALIZADA CON ÉXITO.")

if __name__ == "__main__":
    asyncio.run(test_advisor_v5_output())
