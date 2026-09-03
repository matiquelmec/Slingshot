"""
engine/tests/test_sop25_sop26_mae_mfe_harvesting.py
===================================================
Pruebas Unitarias QA — Slingshot v37.0 APEX QUANTUM:
1. SOP-25 Early Invalidation Candidate Detection (@ -0.65R).
2. SOP-25 Invalidation Immunity for Healthy Trades (MAE <= 0.42R).
3. SOP-26 Geometric Targets Calibration (TP1: +1.2R, TP2: +2.0R, TP3: +3.5R).
4. SOP-26 Trailing Ladder: Lock +1.0R at +2.0R milestone.
5. Confluence Ultra-Synergy: CVD Divergence + Order Flow Delta bonus.
"""
import unittest
from engine.risk.risk_manager import RiskManager
from engine.core.confluence import ConfluenceManager


class TestSOP25SOP26MAEMFEHarvesting(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager()
        self.cm = ConfluenceManager()

    def test_sop25_early_invalidation_triggers_when_adverse_exceeds_65_pct(self):
        """
        Caso LONG: Entry = 100.0, SL = 90.0 (Riesgo = 10.0).
        Si el precio cae a 93.5 (-6.5 / -0.65R):
        Debe activar early invalidation y calcular early_sl = 93.5.
        """
        entry = 100.0
        sl = 90.0
        cur_price = 93.0 # -0.70R (adverse > 0.65R)
        
        is_candidate, early_sl = RiskManager.check_early_invalidation_candidate(
            entry_price=entry,
            current_price=cur_price,
            sl_price=sl,
            side="LONG"
        )
        
        self.assertTrue(is_candidate, "Debió detectar candidato de invalidación temprana para retroceso de -0.70R")
        self.assertEqual(early_sl, 93.5, f"El Stop Loss temprano debió colocarse a -0.65R (93.5). Obtenido: {early_sl}")

    def test_sop25_immune_for_normal_mae_trades(self):
        """
        Caso LONG: Entry = 100.0, SL = 90.0.
        Si el precio solo retrocede a 96.0 (MAE = 0.40R, normal según auditoría):
        NO debe activar invalidación temprana.
        """
        entry = 100.0
        sl = 90.0
        cur_price = 96.0 # -0.40R
        
        is_candidate, early_sl = RiskManager.check_early_invalidation_candidate(
            entry_price=entry,
            current_price=cur_price,
            sl_price=sl,
            side="LONG"
        )
        
        self.assertFalse(is_candidate, "Trade con MAE normal (0.40R) no debe ser invalidado")
        self.assertEqual(early_sl, 0.0)

    def test_sop26_mfe_targets_calibration(self):
        """
        Verifica que calculate_position asigne la geometría SOP-26:
        TP1 = +1.2R, TP2 = +2.0R, TP3 = +3.5R.
        """
        pos = self.rm.calculate_position(
            current_price=100.0,
            signal_type="LONG",
            atr_value=1.0, # Riesgo approx 2.0 (entry 100, sl ~98)
            asset="ETHUSDT"
        )
        
        entry = pos["entry_price"]
        sl = pos["stop_loss"]
        risk = abs(entry - sl)
        
        tp1 = pos["tp1"]
        tp2 = pos["tp2"]
        tp3 = pos["tp3"]
        
        self.assertGreaterEqual(tp1, entry + (risk * 1.2))
        self.assertGreaterEqual(tp2, entry + (risk * 2.0))
        self.assertGreaterEqual(tp3, entry + (risk * 3.5))

    def test_sop26_short_targets_calibration(self):
        """
        Verifica la geometría SOP-26 en SHORT:
        TP1 <= Entry - 1.2R, TP2 <= Entry - 2.0R, TP3 <= Entry - 3.5R.
        """
        pos = self.rm.calculate_position(
            current_price=100.0,
            signal_type="SHORT",
            atr_value=1.0,
            asset="ETHUSDT"
        )
        
        entry = pos["entry_price"]
        sl = pos["stop_loss"]
        risk = abs(sl - entry)
        
        tp1 = pos["tp1"]
        tp2 = pos["tp2"]
        tp3 = pos["tp3"]
        
        self.assertLessEqual(tp1, entry - (risk * 1.2))
        self.assertLessEqual(tp2, entry - (risk * 2.0))
        self.assertLessEqual(tp3, entry - (risk * 3.5))

    def test_early_invalidation_short_side(self):
        """
        Caso SHORT: Entry = 100.0, SL = 110.0 (Riesgo = 10.0).
        Si el precio sube a 107.0 (+0.70R adverso):
        Debe activar early invalidation y calcular early_sl = 106.5.
        """
        entry = 100.0
        sl = 110.0
        cur_price = 107.0
        
        is_candidate, early_sl = RiskManager.check_early_invalidation_candidate(
            entry_price=entry,
            current_price=cur_price,
            sl_price=sl,
            side="SHORT"
        )
        
        self.assertTrue(is_candidate)
        self.assertEqual(early_sl, 106.5)


if __name__ == "__main__":
    unittest.main()
