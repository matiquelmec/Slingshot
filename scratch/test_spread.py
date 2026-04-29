import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.risk.risk_manager import RiskManager

rm = RiskManager()

# Simulate a low liquidity, high spread asset (PAXGUSDT)
signal_paxg = {
    "price": 2400.0,
    "atr_value": 5.0,
    "signal_type": "LONG",
    "asset": "PAXGUSDT"
}

# The risk distance is atr * 2.0 = 10.0
# Friction is 2400 * 0.0015 = 3.6
# 3.6 > (10 * 0.2) = 2.0 -> Should trigger Spread Kill Switch

res_paxg = rm.validate_signal(signal_paxg)
print("PAXGUSDT Validation:", res_paxg)


# Simulate a high liquidity, low spread asset (BTCUSDT)
signal_btc = {
    "price": 60000.0,
    "atr_value": 300.0,
    "signal_type": "LONG",
    "asset": "BTCUSDT"
}

# Risk distance = 600.0
# Friction = 60000 * 0.0002 = 12.0
# 12.0 < (600 * 0.2) = 120.0 -> Should NOT trigger Spread Kill Switch, should evaluate R:R

res_btc = rm.validate_signal(signal_btc)
print("BTCUSDT Validation:", res_btc)
