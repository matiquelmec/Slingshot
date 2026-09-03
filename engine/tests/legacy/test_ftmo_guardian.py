import pytest
from engine.risk.ftmo_guardian import FtmoGuardianShield

def test_ftmo_guardian_daily_drawdown_killswitch():
    """Valida que el Guardián FTMO active el Kill-Switch preventivo al llegar a -3.5% diario."""
    guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1")
    guardian.reset_daily_metrics(new_starting_equity=100000.0)
    
    # 1. Pérdida normal (-1.5%)
    status = guardian.update_equity(98500.0)
    assert not status["is_daily_lockout"]
    assert status["daily_dd_pct"] == 1.5
    
    # 2. Pérdida crítica (-3.6% -> supera el 3.5%)
    status_crit = guardian.update_equity(96400.0)
    assert status_crit["is_daily_lockout"]
    assert "KILL-SWITCH DIARIO ACTIVADO" in status_crit["lockout_reason"]

def test_ftmo_guardian_mt5_lot_sizing_calculations():
    """Valida que el cálculo de lotes MT5 respete las especificaciones de contrato de Oro y Nasdaq."""
    guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1")
    
    # Oro (XAUUSD): Entry 2500, SL 2490 (dist = $10 USD), Riesgo $750 USD
    # Contrato: 100 oz. Lotes = 750 / (10 * 100) = 0.75 Lots
    gold_lots = guardian.calculate_mt5_lots("XAUUSD", entry_price=2500.0, stop_loss=2490.0)
    assert gold_lots["lots"] == 0.75
    assert gold_lots["risk_usd"] == 750.0
    
    # Nasdaq (US100): Entry 20000, SL 19950 (dist = 50 pts), Riesgo $750 USD
    # Contrato: 1. Lotes = 750 / (50 * 1) = 15.0 Lots
    nasdaq_lots = guardian.calculate_mt5_lots("US100", entry_price=20000.0, stop_loss=19950.0)
    assert nasdaq_lots["lots"] == 15.0
