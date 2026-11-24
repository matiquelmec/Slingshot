"""
SOP-153 Practical Execution Parity Verification Suite:
1. calculate_mt5_lots() using native trade_tick_value/trade_tick_size & canonical fallback (no 100k bug)
2. MIN_LOT_EXCEEDS_RISK_BUDGET guard (> 1.25x risk budget)
3. Vault mt5_trade_plans persistence & stage updates for Single-Ticket partial closes (50/30/20)
4. MT5Bridge.resolve_broker_symbol()
"""

from types import SimpleNamespace
from engine.risk.ftmo_guardian import FtmoGuardianShield
from engine.core.vault import SlingshotVault
from engine.execution.mt5_bridge import MT5Bridge


def test_calculate_mt5_lots_uses_native_tick_value_and_canonical_contracts(tmp_path):
    g = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1", state_file=str(tmp_path / "g.json"))

    # 1. Native MT5 symbol_info (e.g. XAUUSD: tick_size=0.01, tick_value=1.0 -> $100/lot per $1 move)
    sym_info = SimpleNamespace(volume_min=0.01, volume_max=50.0, volume_step=0.01, trade_tick_value=1.0, trade_tick_size=0.01)
    res_xau = g.calculate_mt5_lots("XAUUSD", entry_price=2650.0, stop_loss=2640.0, mt5_symbol_info=sym_info)
    # $750 risk / ($10 * 100) = 0.75 lots
    assert res_xau["lots"] == 0.75

    # 2. Offline canonical fallback for BTCUSD (must NOT use 100,000!)
    res_btc = g.calculate_mt5_lots("BTCUSD", entry_price=90000.0, stop_loss=89000.0)
    # $750 / ($1000 * 1) = 0.75 lots
    assert res_btc["lots"] == 0.75

    # 3. Guard: if min_lot exceeds 1.25x risk budget ($750 * 1.25 = $937.50), reject cleanly
    huge_min = SimpleNamespace(volume_min=1.0, volume_max=50.0, volume_step=0.1, trade_tick_value=1.0, trade_tick_size=0.01)
    res_reject = g.calculate_mt5_lots("XAUUSD", entry_price=2650.0, stop_loss=2630.0, mt5_symbol_info=huge_min)
    assert res_reject["lots"] == 0.0
    assert res_reject["lot_error"] == "MIN_LOT_EXCEEDS_RISK_BUDGET"


def test_vault_mt5_trade_plans_lifecycle(tmp_path):
    db_path = tmp_path / "vault_test.db"
    v = SlingshotVault(db_path=db_path)
    v.save_mt5_trade_plan(
        order_id="123456",
        symbol="XAUUSD",
        direction="LONG",
        entry_price=2650.0,
        stop_loss=2640.0,
        be_price=2660.0,
        tp1=2663.0,
        tp2=2675.0,
        tp3=2690.0,
        initial_volume=0.80,
    )
    plan = v.get_mt5_trade_plan("123456")
    assert plan is not None
    assert plan["symbol"] == "XAUUSD"
    assert plan["stage"] == "ACTIVE"
    assert plan["tp1"] == 2663.0

    v.update_mt5_trade_plan_stage("123456", "TP1_TAKEN")
    plan2 = v.get_mt5_trade_plan("XAUUSD")
    assert plan2 is not None
    assert plan2["stage"] == "TP1_TAKEN"


def test_mt5_bridge_resolve_broker_symbol_offline():
    b = MT5Bridge(dry_run=True)
    assert b.resolve_broker_symbol("US100") == "US100.cash"
    assert b.resolve_broker_symbol("USOIL") == "USOIL.cash"
    assert b.resolve_broker_symbol("XAUUSD") == "XAUUSD"
