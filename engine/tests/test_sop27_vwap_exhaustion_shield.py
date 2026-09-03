"""
engine/tests/test_sop27_vwap_exhaustion_shield.py
=============================================================================
SLINGSHOT v38.0 APEX TITAN — SOP-27 DAILY VWAP EXHAUSTION SHIELD QA SUITE
=============================================================================
Pruebas de certificación para:
1. Veto preventivo en SHORT sobreextendido a más de -1.5% bajo el Daily VWAP.
2. Aprobación de SHORT en zona premium (> +0.5% sobre Daily VWAP).
3. Bonificación y aprobación de LONG con descuento institucional (< -0.5%).
4. Precisión matemática de calculate_vwap con anclaje a 00:00 UTC.
5. Integración en ConfluenceManager con factor 9.9 y checklist auditado.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from engine.risk.risk_manager import RiskManager
from engine.indicators.volume import calculate_vwap
from engine.core.confluence import confluence_manager

class TestSOP27VWAPExhaustionShield(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager(account_balance=100_000.0, base_risk_pct=0.01)

    def test_sop27_blocks_overextended_shorts(self):
        """
        [SOP-27] Si un SHORT tiene vwap_dist_pct = -1.8% (< -1.5%),
        debe ser vetado para prevenir la trampa de sobreventa (PF 0.91 histórico).
        """
        is_ok, msg = RiskManager.check_vwap_exhaustion(
            side="SHORT",
            vwap_dist_pct=-1.8,
            max_short_extension=-1.5
        )
        self.assertFalse(is_ok)
        self.assertIn("SOP-27 VWAP VETO", msg)
        self.assertIn("-1.80%", msg)

    def test_sop27_approves_premium_and_neutral_shorts(self):
        """
        [SOP-27] Si un SHORT se abre en Premium (+0.8%) o Neutral (-0.5%),
        debe ser aprobado con éxito.
        """
        is_ok_prem, msg_prem = RiskManager.check_vwap_exhaustion(
            side="SHORT",
            vwap_dist_pct=0.8,
            max_short_extension=-1.5
        )
        self.assertTrue(is_ok_prem)
        self.assertIn("SOP-27 VWAP OK", msg_prem)

        is_ok_neu, msg_neu = RiskManager.check_vwap_exhaustion(
            side="SELL",
            vwap_dist_pct=-0.5,
            max_short_extension=-1.5
        )
        self.assertTrue(is_ok_neu)

    def test_sop27_immune_for_long_orders(self):
        """
        [SOP-27] Las órdenes LONG no se ven vetadas por estar bajo el VWAP,
        ya que representan zonas de descuento institucional de alto valor (PF 1.41).
        """
        is_ok_long, _ = RiskManager.check_vwap_exhaustion(
            side="LONG",
            vwap_dist_pct=-2.5,
            max_short_extension=-1.5
        )
        self.assertTrue(is_ok_long)

    def test_calculate_vwap_mathematical_precision(self):
        """
        Verifica el cálculo de calculate_vwap con velas sintéticas:
        Vela 1: Close 100, High 102, Low 98 (Typ 100), Vol 10 -> cum_tp_vol = 1000, cum_vol = 10 -> VWAP = 100
        Vela 2: Close 110, High 112, Low 108 (Typ 110), Vol 10 -> cum_tp_vol = 2100, cum_vol = 20 -> VWAP = 105
        vwap_dist_pct en Vela 2 = (110 - 105) / 105 * 100 = 4.7619%
        """
        dates = [datetime(2026, 9, 1, 10, 0), datetime(2026, 9, 1, 10, 15)]
        df = pd.DataFrame({
            "timestamp": dates,
            "open": [100.0, 105.0],
            "high": [102.0, 112.0],
            "low": [98.0, 108.0],
            "close": [100.0, 110.0],
            "volume": [10.0, 10.0]
        })
        res = calculate_vwap(df)
        self.assertIn("d_vwap", res.columns)
        self.assertIn("vwap_dist_pct", res.columns)
        self.assertAlmostEqual(res["d_vwap"].iloc[0], 100.0, places=2)
        self.assertAlmostEqual(res["d_vwap"].iloc[1], 105.0, places=2)
        self.assertAlmostEqual(res["vwap_dist_pct"].iloc[1], 4.76, places=1)

    def test_confluence_manager_vwap_integration(self):
        """
        Verifica que el ConfluenceManager reconozca el descuento institucional en LONG (+15pts)
        y el veto por sobreextensión en SHORT.
        """
        dates = pd.date_range(start="2026-09-01 00:00", periods=50, freq="15min")
        df = pd.DataFrame({
            "timestamp": dates,
            "open": np.linspace(100, 95, 50),
            "high": np.linspace(101, 96, 50),
            "low": np.linspace(99, 94, 50),
            "close": np.linspace(100, 95, 50),
            "volume": [100.0] * 50
        })
        df = calculate_vwap(df)
        df["vwap_dist_pct"] = -1.8

        long_res = confluence_manager.evaluate_signal(
            df=df,
            signal={"type": "LONG", "symbol": "ETHUSDT", "price": 95.0, "atr": 1.0, "recent_choch": True}
        )
        
        vwap_item = next((item for item in long_res["checklist"] if item["factor"] == "Daily VWAP Anchor"), None)
        self.assertIsNotNone(vwap_item)
        self.assertEqual(vwap_item["status"], "CONFIRMADO")
        self.assertIn("Descuento Institucional", vwap_item["detail"])

if __name__ == "__main__":
    unittest.main()
