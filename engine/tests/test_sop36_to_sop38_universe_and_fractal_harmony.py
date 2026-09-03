"""
engine/tests/test_sop36_to_sop38_universe_and_fractal_harmony.py
=============================================================================
SLINGSHOT v41.0 APEX ZENITH SOVEREIGN — QA CERTIFICATION SUITE (SOP-36 to SOP-38)
=============================================================================
Pruebas de certificación para:
1. SOP-36: Universo Curado (Inclusión de BNB y exclusión de PAXG en 15m scalp).
2. SOP-36: Especialización de PAXG exclusivamente en 1H Swing / TradFi.
3. SOP-37: Strict MTF Alignment (Veto / penalización severa a contratendencia HTF).
4. SOP-38: Sniper NY Open (Asignación bonificada +10% en ventana 13:00-17:00 UTC).
5. SOP-38: Asia Defense (Reducción al 0.70x en sesión 00:00-07:00 UTC).
"""

import unittest
import pandas as pd
from engine.workers.market_scanner import MarketScanner
from engine.risk.risk_manager import RiskManager
from engine.core.confluence import confluence_manager

class TestSOP36ToSOP38UniverseAndFractalHarmony(unittest.TestCase):
    def setUp(self):
        self.scanner = MarketScanner()

    def test_sop36_curated_scalp_universe_assets(self):
        """
        [SOP-36] El universo de scalping 15m debe incluir activos campeones como
        BNB (+125R), INJ (+138R), SOL (+120R), y excluir PAXG (oro con spread destructivo en 15m).
        """
        self.assertIn("BNBUSDT", self.scanner.scalp_assets)
        self.assertIn("INJUSDT", self.scanner.scalp_assets)
        self.assertIn("SOLUSDT", self.scanner.scalp_assets)
        self.assertNotIn("PAXGUSDT", self.scanner.scalp_assets)

    def test_sop36_paxg_reserved_for_swing_1h(self):
        """
        [SOP-36] PAXGUSDT (Oro) debe estar reservado estrictamente para 1H Swing
        donde el rango diario absorbe holgadamente el coste del spread.
        """
        self.assertIn("PAXGUSDT", self.scanner.core_swing_1h_assets)

    def test_sop37_strict_mtf_fractal_alignment(self):
        """
        [SOP-37] Una señal LONG en 15m que opere por debajo de la EMA800 (HTF 4H)
        debe recibir estado DIVERGENTE en su checklist.
        """
        df_contra = pd.DataFrame({
            "timestamp": [pd.Timestamp.now(tz="UTC")],
            "open": [100.0], "high": [101.0], "low": [99.0], "close": [100.0], "volume": [1000.0],
            "ema800": [115.0] # Precio (100) muy por debajo de EMA HTF (115) para un LONG
        })
        sig = {"type": "LONG", "symbol": "SOLUSDT", "price": 100.0}
        eval_res = confluence_manager.evaluate_signal(df=df_contra, signal=sig)
        
        item_htf = next((i for i in eval_res["checklist"] if "HTF" in i["factor"]), None)
        self.assertIsNotNone(item_htf)
        self.assertEqual(item_htf["status"], "DIVERGENTE")

    def test_sop38_sniper_ny_open_allocation_boost(self):
        """
        [SOP-38] Operar en la ventana dorada de NY Open (14:00 UTC) debe otorgar
        un bono del +10% en el multiplicador de asignación de margen.
        """
        mult_std = RiskManager.calculate_alpha_tier_sizing("BNBUSDT", confluence_score=75.0, hour_utc=10) # Londres
        mult_ny = RiskManager.calculate_alpha_tier_sizing("BNBUSDT", confluence_score=75.0, hour_utc=14)  # NY Open
        
        self.assertGreater(mult_ny, mult_std)
        self.assertAlmostEqual(mult_ny, 1.38, places=2) # 1.25 * 1.10 = 1.375 -> 1.38

    def test_sop38_asia_capital_defense_reduction(self):
        """
        [SOP-38] Operar en la sesión asiática (03:00 UTC) debe reducir el tamaño
        al 0.70x para proteger la cuenta del ruido y falso volumen.
        """
        mult_asia = RiskManager.calculate_alpha_tier_sizing("SOLUSDT", confluence_score=75.0, hour_utc=3)
        self.assertLess(mult_asia, 1.00)
        self.assertAlmostEqual(mult_asia, 0.70, places=2)

if __name__ == "__main__":
    unittest.main()
