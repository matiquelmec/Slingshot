import asyncio
import sys
import os

sys.path.append(os.getcwd())

from engine.execution.nexus import nexus
from engine.api.signal_handler import SignalHandler

class MockBroadcaster:
    def __init__(self):
        self.symbol = "BTCUSDT"
        self.interval = "15m"
    async def _broadcast(self, msg): pass

async def inject_real_test_signal():
    print("=" * 60)
    print("  INJECTING REAL TEST SIGNAL THROUGH SLINGSHOT ENGINE")
    print("=" * 60)
    
    # 1. Define a mock signal that overrides position size/leverage for safety
    # We want a small size (5 USDT) with 5x leverage at a low price ($50,000)
    tactical_mock = {
        "market_regime": "BULLISH_TREND",
        "active_strategy": "SMC_APEX_SNIPER",
        "signals": [
            {
                "type": "LONG",
                "price": 50000.0,
                "stop_loss": 48000.0,
                "take_profit_3r": 55000.0,
                "tp1": 52000.0,
                "tp2": 53500.0,
                "tp3": 55000.0,
                "position_size": 5.0,
                "position_size_usdt": 5.0,
                "leverage": 5,
                "risk_pct": 1.0,
                "atr": 500.0,
                "confluence": {"score": 85},
                "timestamp": "2026-05-02T16:00:00Z"
            }
        ],
        "smc": {
            "order_blocks": {
                "bullish": [{"bottom": 49500.0, "top": 49700.0}],
                "bearish": [{"bottom": 57000.0, "top": 57200.0}]
            }
        }
    }
    
    # 2. Initialize Handler
    handler = SignalHandler("BTCUSDT", "15m", MockBroadcaster())
    
    # 3. Process signal through the engine's pipeline
    print("Injecting tactical signal to Handler...")
    await handler.handle(tactical_mock)
    
    # Wait for the async task to complete
    await asyncio.sleep(5)
    print("\nInjection completed!")

if __name__ == "__main__":
    asyncio.run(inject_real_test_signal())
