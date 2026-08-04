import unittest
import pandas as pd
import numpy as np
from engine.indicators.volume import calculate_order_flow_delta, calculate_absorption_index
from engine.core.confluence import ConfluenceManager

class TestVolumeDelta(unittest.TestCase):
    def setUp(self):
        self.confluence_manager = ConfluenceManager()
        # Mock DataFrame con datos de OHLCV
        dates = pd.date_range(start="2026-08-01", periods=30, freq="15min")
        self.mock_df = pd.DataFrame({
            "timestamp": dates,
            "open": [50000 + i * 10 for i in range(30)],
            "high": [50020 + i * 10 for i in range(30)],
            "low": [49990 + i * 10 for i in range(30)],
            "close": [50015 + i * 10 for i in range(30)],
            "volume": [100.0 + (i % 5) * 50 for i in range(30)],
            "market_regime": ["MARKUP"] * 30
        })

    def test_calculate_order_flow_delta_basic(self):
        delta = calculate_order_flow_delta(self.mock_df)
        self.assertEqual(len(delta), 30)
        self.assertTrue((delta >= -1.0).all() and (delta <= 1.0).all())

    def test_calculate_order_flow_delta_with_sidecar_ratio(self):
        df_sidecar = self.mock_df.copy()
        df_sidecar["delta_ratio"] = 0.85
        delta = calculate_order_flow_delta(df_sidecar)
        self.assertGreater(delta.iloc[-1], 0.5)

    def test_absorption_index_includes_order_flow_delta(self):
        df_result = calculate_absorption_index(self.mock_df)
        self.assertIn("order_flow_delta", df_result.columns)
        self.assertIn("absorption_score", df_result.columns)

    def test_confluence_manager_evaluates_order_flow_delta(self):
        df_with_delta = calculate_absorption_index(self.mock_df)
        signal = {
            "asset": "BTCUSDT",
            "signal_type": "LONG",
            "price": 50300.0,
            "timestamp": df_with_delta["timestamp"].iloc[-1]
        }
        res = self.confluence_manager.evaluate_signal(df_with_delta, signal)
        self.assertIn("score", res)
        factors = [item["factor"] for item in res.get("checklist", [])]
        self.assertIn("Order Flow Delta", factors)

if __name__ == "__main__":
    unittest.main()
