import unittest
import pandas as pd
import numpy as np
from engine.risk.risk_manager import RiskManager

class TestLimitEntryRisk(unittest.TestCase):
    def setUp(self):
        self.risk_manager = RiskManager()

    def test_altcoin_stop_loss_protection(self):
        # Para un activo de altcoin (ej. DOTUSDT) a un precio de 5.0, verificar que el SL no sea menor al 1.80%
        pos = self.risk_manager.calculate_position(
            current_price=5.0,
            signal_type="LONG",
            asset="DOTUSDT",
            atr_value=0.05
        )
        sl = pos["stop_loss"]
        sl_dist_pct = (5.0 - sl) / 5.0
        self.assertGreaterEqual(sl_dist_pct, 0.0180)

    def test_structural_stop_loss_air_room(self):
        # Verificar que el Stop Loss tenga margen de 0.8x-1.2x ATR detrás de un Order Block
        smc_data = {
            "order_blocks": {
                "bullish": [{"top": 4.90, "bottom": 4.85}]
            }
        }
        pos = self.risk_manager.calculate_position(
            current_price=4.90,
            signal_type="LONG",
            asset="NEARUSDT",
            smc_data=smc_data,
            atr_value=0.05
        )
        sl = pos["stop_loss"]
        # El SL debe estar razonablemente por debajo del bottom del OB (4.85)
        self.assertLess(sl, 4.85)

if __name__ == "__main__":
    unittest.main()
