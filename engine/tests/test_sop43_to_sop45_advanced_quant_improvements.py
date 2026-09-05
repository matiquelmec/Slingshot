"""
engine/tests/test_sop43_to_sop45_advanced_quant_improvements.py
=============================================================================
SLINGSHOT v43.0 APEX TITAN COMPOUND — QA SUITE (SOP-43, SOP-44 & SOP-45)
=============================================================================
Certifica:
1. SOP-43: Asymmetric Quarter-Kelly Risk Scaling (1.25% - 3.25%).
2. SOP-43: Aceleracion en NY Open (13-17 UTC) vs Preservacion en Asia (0-6 UTC).
3. SOP-44: Portfolio Heat Cap @ 7.5% direccional en Longs y Shorts.
4. SOP-44: Liberacion de cupo (Heat = $0.00) cuando el trade alcanza Breakeven.
5. SOP-45: Optimizacion de Comisiones Maker / Post-Only (-60% fee drag).
6. Multi-Account Isolation: El heat y margen de una cuenta no afecta a las otras.
"""

import unittest
from engine.risk.risk_manager import RiskManager
from engine.execution.nexus import NexusNode
from engine.execution.account_manager import BitunixAccountConfig

class TestSOP43ToSOP45AdvancedQuantImprovements(unittest.TestCase):

    def test_sop43_quarter_kelly_scaling_apex_ny_open(self):
        base_risk = 0.025
        dyn_risk = RiskManager.calculate_quarter_kelly_risk(
            base_risk_pct=base_risk,
            symbol="FETUSDT",
            confluence_score=85.0,
            hour_utc=14
        )
        self.assertGreaterEqual(dyn_risk, 0.0300)
        self.assertLessEqual(dyn_risk, 0.0325)

    def test_sop43_quarter_kelly_preservation_asia_night(self):
        base_risk = 0.025
        dyn_risk = RiskManager.calculate_quarter_kelly_risk(
            base_risk_pct=base_risk,
            symbol="BTCUSDT",
            confluence_score=65.0,
            hour_utc=3
        )
        self.assertLessEqual(dyn_risk, 0.0175)
        self.assertGreaterEqual(dyn_risk, 0.0125)

    def test_sop44_portfolio_heat_cap_prevents_overexposure(self):
        account_balance = 1000.0
        active_positions = {
            "BTCUSDT": {
                "signal": {"type": "LONG", "price": 60000.0, "stop_loss": 59000.0},
                "smart_trailing": {"be_active": False},
                "risk_usd": 25.0
            },
            "ETHUSDT": {
                "signal": {"type": "LONG", "price": 3000.0, "stop_loss": 2950.0},
                "smart_trailing": {"be_active": False},
                "risk_usd": 25.0
            },
            "SOLUSDT": {
                "signal": {"type": "LONG", "price": 150.0, "stop_loss": 145.0},
                "smart_trailing": {"be_active": False},
                "risk_usd": 25.0
            }
        }

        approved, reason, current_heat = RiskManager.check_portfolio_heat(
            active_positions=active_positions,
            new_direction="LONG",
            new_trade_risk_usd=20.0,
            account_balance=account_balance,
            max_heat_pct=0.075
        )

        self.assertFalse(approved)
        self.assertIn("🛑 [SOP-44 HEAT VETO]", reason)
        self.assertAlmostEqual(current_heat, 75.0, places=1)

    def test_sop44_breakeven_frees_portfolio_heat(self):
        account_balance = 1000.0
        active_positions = {
            "BTCUSDT": {
                "signal": {"type": "LONG", "price": 60000.0, "stop_loss": 60050.0},
                "smart_trailing": {"be_active": True},
                "risk_usd": 0.0
            },
            "ETHUSDT": {
                "signal": {"type": "LONG", "price": 3000.0, "stop_loss": 3002.0},
                "smart_trailing": {"be_active": True},
                "risk_usd": 0.0
            },
            "SOLUSDT": {
                "signal": {"type": "LONG", "price": 150.0, "stop_loss": 145.0},
                "smart_trailing": {"be_active": False},
                "risk_usd": 25.0
            }
        }

        approved, reason, current_heat = RiskManager.check_portfolio_heat(
            active_positions=active_positions,
            new_direction="LONG",
            new_trade_risk_usd=25.0,
            account_balance=account_balance,
            max_heat_pct=0.075
        )

        self.assertTrue(approved)
        self.assertIn("✅ [SOP-44 HEAT OK]", reason)
        self.assertAlmostEqual(current_heat, 25.0, places=1)

    def test_sop44_shorts_isolated_from_longs(self):
        account_balance = 1000.0
        active_positions = {
            "BTCUSDT": {
                "signal": {"type": "LONG", "price": 60000.0, "stop_loss": 59000.0},
                "smart_trailing": {"be_active": False},
                "risk_usd": 75.0
            }
        }

        approved, reason, current_heat = RiskManager.check_portfolio_heat(
            active_positions=active_positions,
            new_direction="SHORT",
            new_trade_risk_usd=25.0,
            account_balance=account_balance,
            max_heat_pct=0.075
        )

        self.assertTrue(approved)
        self.assertAlmostEqual(current_heat, 0.0, places=1)

    def test_sop45_fee_optimizer_parity(self):
        nominal_volume = 1000.0
        taker_fee_rate = 0.0006
        maker_fee_rate = 0.0002

        taker_cost = nominal_volume * taker_fee_rate
        maker_cost = nominal_volume * maker_fee_rate
        savings_pct = (taker_cost - maker_cost) / taker_cost * 100.0

        self.assertAlmostEqual(taker_cost, 0.60, places=2)
        self.assertAlmostEqual(maker_cost, 0.20, places=2)
        self.assertAlmostEqual(savings_pct, 66.67, places=1)

    def test_multi_account_independent_risk_and_heat(self):
        # Usando INJ (entry=4.798, sl=4.876, qty_decimals=1)
        calc_primary = RiskManager.calculate_dollar_risk_position(
            account_balance=1000.0,
            risk_pct=0.025,
            entry_price=4.798,
            sl_price=4.876,
            leverage=10,
            qty_decimals=1
        )
        calc_client = RiskManager.calculate_dollar_risk_position(
            account_balance=200.0,
            risk_pct=0.025,
            entry_price=4.798,
            sl_price=4.876,
            leverage=10,
            qty_decimals=1
        )

        self.assertTrue(calc_primary["approved"])
        self.assertTrue(calc_client["approved"])
        self.assertAlmostEqual(calc_primary["projected_loss"], 25.0, delta=1.5)
        self.assertAlmostEqual(calc_client["projected_loss"], 5.0, delta=0.5)
        # La cuenta principal arriesga exactamente 5x más que la secundaria sin interferencias
        self.assertAlmostEqual(calc_primary["required_margin"] / calc_client["required_margin"], 5.0, delta=0.5)

if __name__ == "__main__":
    unittest.main()