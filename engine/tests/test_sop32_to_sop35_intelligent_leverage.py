"""
engine/tests/test_sop32_to_sop35_intelligent_leverage.py
=============================================================================
SLINGSHOT v40.0 APEX TITAN LEVERAGE — QA CERTIFICATION SUITE (SOP-32 to SOP-35)
=============================================================================
Pruebas de certificación para:
1. SOP-32: Volatility-Targeted Leverage (Apalancamiento nominal inverso al SL%).
2. SOP-33: Alpha-Tier Kelly Sizing (Multiplicadores asimétricos por ventaja estadística).
3. SOP-33: Exclusión de activos con bajo rendimiento histórico (0.0x a laggards).
4. SOP-34: Confluence Multiplier (Escalado de margen por calidad del setup 65-88 pts).
5. SOP-35: Free-Roll Leverage Integrity (Control de margen y apalancamiento).
"""

import unittest
from engine.risk.risk_manager import RiskManager

class TestSOP32ToSOP35IntelligentLeverage(unittest.TestCase):
    def test_sop32_volatility_targeted_leverage_btc_vs_alt(self):
        """
        [SOP-32] Activos con SL estrecho (ej. BTC con 0.8% SL) pueden usar apalancamiento
        seguro alto (12x a 18x). Activos con SL amplio (ej. FET con 3.0% SL) deben
        limitarse a <= 8x para prevenir liquidación prematura.
        """
        btc_lev = RiskManager.calculate_volatility_targeted_leverage("BTCUSDT", sl_distance_pct=0.008)
        self.assertGreaterEqual(btc_lev, 12)
        self.assertLessEqual(btc_lev, 18)

        alt_lev = RiskManager.calculate_volatility_targeted_leverage("FETUSDT", sl_distance_pct=0.030)
        self.assertLessEqual(alt_lev, 8)
        self.assertGreaterEqual(alt_lev, 3)

    def test_sop33_alpha_tier_sizing_champions(self):
        """
        [SOP-33] Activos Tier S (FET) y Tier A (INJ, NEAR, BNB) reciben multiplicadores
        de asignación asimétrica superiores (1.25x a 1.40x).
        """
        fet_mult = RiskManager.calculate_alpha_tier_sizing("FETUSDT", confluence_score=75.0)
        inj_mult = RiskManager.calculate_alpha_tier_sizing("INJUSDT", confluence_score=75.0)
        near_mult = RiskManager.calculate_alpha_tier_sizing("NEARUSDT", confluence_score=75.0)
        bnb_mult = RiskManager.calculate_alpha_tier_sizing("BNBUSDT", confluence_score=75.0)

        self.assertEqual(fet_mult, 1.40)
        self.assertEqual(inj_mult, 1.25)
        self.assertEqual(near_mult, 1.25)
        self.assertEqual(bnb_mult, 1.25)

    def test_sop33_alpha_tier_sizing_low_conviction_defensive(self):
        """
        [SOP-33] Activos de baja convicción (RENDER, AVAX) reciben multiplicador
        defensivo reducido (0.60x) para mitigar drawdown.
        """
        render_mult = RiskManager.calculate_alpha_tier_sizing("RENDERUSDT", confluence_score=75.0)
        avax_mult = RiskManager.calculate_alpha_tier_sizing("AVAXUSDT", confluence_score=75.0)

        self.assertEqual(render_mult, 0.60)
        self.assertEqual(avax_mult, 0.60)

    def test_sop34_confluence_multiplier_scaling(self):
        """
        [SOP-34] Un setup con confluencia élite (>= 82 pts) recibe un bono del +15% de margen.
        Un setup limítrofe (< 68 pts) recibe una reducción defensiva del -20%.
        """
        # Sol estándar a 75 pts = 1.00x
        sol_std = RiskManager.calculate_alpha_tier_sizing("SOLUSDT", confluence_score=75.0)
        self.assertEqual(sol_std, 1.00)

        # Sol élite a 85 pts = 1.15x
        sol_elite = RiskManager.calculate_alpha_tier_sizing("SOLUSDT", confluence_score=85.0)
        self.assertAlmostEqual(sol_elite, 1.15, places=2)

        # Sol limítrofe a 65 pts = 0.80x
        sol_def = RiskManager.calculate_alpha_tier_sizing("SOLUSDT", confluence_score=65.0)
        self.assertAlmostEqual(sol_def, 0.80, places=2)

    def test_sop35_freeroll_leverage_macro_tier_conservatism(self):
        """
        [SOP-35] Activos Macro (BTC, ETH, LINK, XRP) aplican multiplicador conservador
        (0.75x base) para preservar capital y actuar como anclas de baja volatilidad.
        """
        btc_mult = RiskManager.calculate_alpha_tier_sizing("BTCUSDT", confluence_score=75.0)
        eth_mult = RiskManager.calculate_alpha_tier_sizing("ETHUSDT", confluence_score=75.0)

        self.assertEqual(btc_mult, 0.75)
        self.assertEqual(eth_mult, 0.75)

if __name__ == "__main__":
    unittest.main()
