"""
engine/tests/test_streak_circuit_breakers.py
=============================================================================
Pruebas Unitarias para Protocolo SOP-70: Streak Circuit Breakers
- FTMO Daily Loss Cap (2 SLs = Lockout Diario y Purga de Órdenes)
- FTMO Reset Diario a las 00:00:00 CE(S)T
- Crypto Streak Circuit Breaker (3 SLs Consecutivos = Cuarentena Preventiva)
"""

import os
import sys
import unittest
from datetime import datetime, timezone

# Add project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from engine.risk.ftmo_guardian import FtmoGuardianShield
from engine.risk.risk_manager import RiskManager


class TestStreakCircuitBreakers(unittest.TestCase):

    def setUp(self):
        self.tmp_state_file = os.path.join(os.path.dirname(__file__), "tmp_ftmo_test_state.json")
        if os.path.exists(self.tmp_state_file):
            os.remove(self.tmp_state_file)

    def tearDown(self):
        if os.path.exists(self.tmp_state_file):
            os.remove(self.tmp_state_file)

    def test_ftmo_daily_loss_cap_trigger(self):
        """Verifica que tras 2 pérdidas consecutivas en el día se active el lockout preventivo."""
        guardian = FtmoGuardianShield(account_size=100000.0, state_file=self.tmp_state_file)
        guardian.max_daily_losses = 2
        
        self.assertFalse(guardian.is_daily_lockout)
        self.assertEqual(guardian.daily_loss_count, 0)
        
        # Pérdida 1: No debe bloquear
        guardian.register_trade_outcome(is_win=False, symbol="US100.cash")
        self.assertEqual(guardian.daily_loss_count, 1)
        self.assertFalse(guardian.is_daily_lockout)
        
        # Pérdida 2: Debe activar el Daily Loss Cap inmediatamente
        guardian.register_trade_outcome(is_win=False, symbol="US30.cash")
        self.assertEqual(guardian.daily_loss_count, 2)
        self.assertTrue(guardian.is_daily_lockout)
        self.assertIn("DAILY LOSS CAP ACTIVADO", guardian.lockout_reason)

    def test_ftmo_daily_reset_on_broker_rollover(self):
        """Verifica que el rollover a las 00:00:00 CE(S)T resetee el contador de pérdidas y levante el lockout."""
        guardian = FtmoGuardianShield(account_size=100000.0, state_file=self.tmp_state_file)
        guardian.max_daily_losses = 2
        
        # Provocar lockout
        guardian.register_trade_outcome(is_win=False, symbol="US100.cash")
        guardian.register_trade_outcome(is_win=False, symbol="GER40.cash")
        self.assertTrue(guardian.is_daily_lockout)
        
        # Simular cambio de día bancario
        day1 = datetime(2026, 9, 14, 23, 50, tzinfo=timezone.utc)
        guardian.evaluate_broker_day(day1, live_balance=98500.0, live_equity=98500.0)
        
        day2 = datetime(2026, 9, 15, 0, 5, tzinfo=timezone.utc)
        guardian.evaluate_broker_day(day2, live_balance=98500.0, live_equity=98500.0)
        
        self.assertFalse(guardian.is_daily_lockout)
        self.assertEqual(guardian.daily_loss_count, 0)
        self.assertEqual(guardian.consecutive_losses, 0)

    def test_ftmo_win_resets_consecutive_losses(self):
        """Verifica que una victoria resetee las pérdidas consecutivas pero mantenga el conteo del día."""
        guardian = FtmoGuardianShield(account_size=100000.0, state_file=self.tmp_state_file)
        
        guardian.register_trade_outcome(is_win=False, symbol="US100.cash")
        self.assertEqual(guardian.daily_loss_count, 1)
        self.assertEqual(guardian.consecutive_losses, 1)
        
        guardian.register_trade_outcome(is_win=True, symbol="XAUUSD")
        self.assertEqual(guardian.daily_loss_count, 1)
        self.assertEqual(guardian.consecutive_losses, 0)

    def test_crypto_streak_circuit_breaker(self):
        """Verifica que el RiskManager vete la apertura tras 3 pérdidas consecutivas en cripto."""
        # 0, 1, 2 pérdidas consecutivas -> Permitido
        is_ok, msg = RiskManager.check_streak_circuit_breaker(consecutive_losses=0, max_consecutive_losses=3)
        self.assertTrue(is_ok)
        
        is_ok, msg = RiskManager.check_streak_circuit_breaker(consecutive_losses=2, max_consecutive_losses=3)
        self.assertTrue(is_ok)
        
        # 3 pérdidas consecutivas -> Vetado preventivamente
        is_ok, msg = RiskManager.check_streak_circuit_breaker(consecutive_losses=3, max_consecutive_losses=3)
        self.assertFalse(is_ok)
        self.assertIn("SOP-70 STREAK BREAKER", msg)


if __name__ == "__main__":
    unittest.main()
