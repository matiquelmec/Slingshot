
import asyncio
import httpx
from engine.api.advisor import generate_tactical_advice

async def test_llm():
    print("Testing LLM Advisor...")
    try:
        # Mock data
        tactical_data = {
            "market_regime": "MARKUP",
            "active_strategy": "TrendFollowing",
            "current_price": 73500.0,
            "rsi": 65.0,
            "macd": "BULLISH_CROSS",
            "bbwp": 45.0,
            "squeeze": False,
            "bull_div": False,
            "bear_div": False,
            "support": 72000.0,
            "resistance": 75000.0,
            "fibo_lvl": "0.618",
            "obs_bullish": 2,
            "fvgs_bullish": 1,
            "obs_bearish": 1,
            "fvgs_bearish": 0,
            "htf_bias": {
                "direction": "BULLISH",
                "reason": "4H Structure is strongly bullish."
            }
        }
        
        advice = await generate_tactical_advice(
            "BTCUSDT",
            tactical_data=tactical_data,
            current_session="NEW_YORK",
            ml_projection={"direction": "ALCISTA", "probability": 85},
            news=[{"title": "Bitcoin reaches new ATH", "sentiment": "BULLISH"}],
            liquidations=[]
        )
        print("\n--- LLM RESPONSE ---")
        print(advice)
        print("--------------------")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm())
