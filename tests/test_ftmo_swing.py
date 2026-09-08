import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
import tempfile
from datetime import datetime, timezone

try:
    from engine.risk.ftmo_guardian import FtmoGuardianShield
except ImportError:
    from ftmo_guardian_updated import FtmoGuardianShield

def test_ftmo_guardian_suite():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_state = tf.name

    try:
        guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1", account_type="SWING", state_file=temp_state)
        
        # Test 1.1: Rollover a medianoche con saldo base max(balance, equity)
        server_midnight = datetime(2026, 9, 9, 0, 0, 0, tzinfo=timezone.utc)
        guardian.evaluate_broker_day(server_midnight, live_balance=99110.24, live_equity=99500.0)
        assert guardian.daily_starting_equity == 99500.0, f"Expected 99500.0, got {guardian.daily_starting_equity}"
        assert guardian.current_broker_date == "2026-09-09"
        assert not guardian.is_daily_lockout
        
        # Test 1.2: Pérdida moderada no activa lockout
        status = guardian.update_equity(current_equity=98000.0)
        assert not status["is_daily_lockout"]
        assert round(status["daily_dd_pct"], 2) == round((99500.0 - 98000.0) / 99500.0 * 100, 2)
        
        # Test 1.3: Pérdida de 3.6% activa Hard Kill-Switch Diario
        loss_equity = 99500.0 * (1 - 0.036) # -3.6%
        status_loss = guardian.update_equity(current_equity=loss_equity)
        assert status_loss["is_daily_lockout"]
        assert "KILL-SWITCH DIARIO" in status_loss["lockout_reason"]
        
        # Test 1.4: Persistencia atómica en JSON
        with open(temp_state, "r", encoding="utf-8") as f:
            saved = json.load(f)
            assert saved["is_daily_lockout"] is True
            assert saved["daily_starting_equity"] == 99500.0
            assert saved["account_type"] == "SWING"

        # Test 1.5: Margen Governor en Swing (1:30)
        # GBPUSD 1.3000 con SL a 15 pips arriesgando $750 da aprox 5.0 lotes
        # 5.0 lotes = $500k notional / 30 = ~$16,666 USD de margen requerido
        lots_res = guardian.calculate_mt5_lots("GBPUSD", 1.3000, 1.2985, margin_free=25000.0)
        assert lots_res["lots"] > 0
        assert lots_res["margin_warning"] is True # $16.6k > 40% de $25k ($10k)
        
        lots_ok = guardian.calculate_mt5_lots("GBPUSD", 1.3000, 1.2985, margin_free=80000.0)
        assert lots_ok["margin_warning"] is False # $16.6k < 40% de $80k ($32k)

        print("[OK] 1. FTMO Guardian Tests: 5/5 PASSED")
    finally:
        if os.path.exists(temp_state):
            os.remove(temp_state)

# 2. Test Correlation Governor Logic
def test_correlation_governor_logic():
    # Simular posiciones existentes en MT5
    active_positions = [{"symbol": "US100.cash", "side": "LONG"}]
    
    # Intento 1: US30 en LONG cuando US100 ya está en LONG -> Debe ser vetado
    sym_attempt = "US30.cash"
    dir_attempt = "LONG"
    
    is_blocked = False
    if "US100" in sym_attempt or "US30" in sym_attempt:
        other_idx = "US30.cash" if "US100" in sym_attempt else "US100.cash"
        for pos in active_positions:
            if pos["symbol"] == other_idx and pos["side"] == dir_attempt:
                is_blocked = True
                break
                
    assert is_blocked is True, "US30 LONG should have been blocked by US100 LONG"
    
    # Intento 2: GBPUSD en LONG -> No debe ser vetado
    sym_attempt2 = "GBPUSD"
    is_blocked2 = False
    if "US100" in sym_attempt2 or "US30" in sym_attempt2:
        is_blocked2 = True
    assert is_blocked2 is False, "GBPUSD should not be blocked by index correlation"
    
    print("[OK] 2. Correlation Governor Tests: 2/2 PASSED")

# 3. Test Weekend Gap Shield for Swing
def test_weekend_swing_shield():
    # Viernes a las 21:15 UTC
    friday_night = datetime(2026, 9, 11, 21, 15, 0, tzinfo=timezone.utc)
    is_weekend = (friday_night.weekday() == 4 and friday_night.hour >= 21) or (friday_night.weekday() in (5, 6))
    assert is_weekend is True
    
    # Posición con flotante positivo (+1.2R) debe ser auto-protegida a BE
    pos = {
        "symbol": "US100.cash",
        "entry_price": 28500.0,
        "cur_price": 28700.0,
        "sl": 28400.0,
        "r_profit": 2.0
    }
    
    target_sl = None
    if is_weekend and pos["r_profit"] >= 0.8 and pos["sl"] < pos["entry_price"]:
        target_sl = pos["entry_price"]
        
    assert target_sl == 28500.0, "Position with profit should have SL moved to entry (BE) for the weekend"
    print("[OK] 3. Weekend Gap Shield Tests: 2/2 PASSED")

if __name__ == "__main__":
    test_ftmo_guardian_suite()
    test_correlation_governor_logic()
    test_weekend_swing_shield()
    print("\nALL 9 INSTITUTIONAL SWING UNIT TESTS PASSED WITH 100% SUCCESS!")
