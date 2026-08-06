import unittest
import pandas as pd
import numpy as np
import asyncio
from engine.indicators.volume import calculate_cvd_divergence
from engine.execution.bitunix_executor import BitunixExecutor
from engine.core.confluence import ConfluenceManager

class TestV11ApexEngine(unittest.TestCase):
    def setUp(self):
        # Crear DataFrame sintético de prueba con 50 velas
        np.random.seed(42)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=50, freq='15min')
        prices = 100.0 + np.cumsum(np.random.randn(50) * 0.5)
        volumes = np.random.randint(100, 1000, size=50)
        
        self.df = pd.DataFrame({
            'timestamp': dates.astype(int) // 10**6,
            'open': prices - 0.2,
            'high': prices + 0.5,
            'low': prices - 0.5,
            'close': prices,
            'volume': volumes,
            'delta_ratio': np.random.uniform(-0.8, 0.8, size=50)
        })

    def test_cvd_divergence_indicator(self):
        res = calculate_cvd_divergence(self.df)
        self.assertIn("status", res)
        self.assertIn(res["status"], ["BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "IN_SYNC", "NEUTRAL"])

    def test_confluence_cvd_factor(self):
        cm = ConfluenceManager()
        sig = {'asset': 'BTCUSDT', 'signal_type': 'LONG', 'price': 100.0, 'timestamp': 'now'}
        res = cm.evaluate_signal(self.df, sig)
        factors = [c['factor'] for c in res.get('checklist', [])]
        self.assertIn("CVD Divergence", factors)

    def test_iceberg_executor_slicing(self):
        executor = BitunixExecutor(dry_run=True)
        sig = {'asset': 'BTCUSDT', 'type': 'LONG', 'price': 50000.0, 'position_size': 3000.0}
        
        async def run_iceberg():
            return await executor.execute_iceberg_signal(sig, num_slices=3, slice_delay_ms=10)
            
        res = asyncio.run(run_iceberg())
        self.assertEqual(res.get("execution_type"), "ICEBERG")
        self.assertEqual(res.get("num_slices"), 3)

if __name__ == "__main__":
    unittest.main()
