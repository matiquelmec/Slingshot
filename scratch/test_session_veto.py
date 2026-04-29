import sys
import os
import pandas as pd
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.router.gatekeeper import SignalGatekeeper, GatekeeperContext
from engine.risk.risk_manager import RiskManager

rm = RiskManager()
gatekeeper = SignalGatekeeper(rm)

# Dummy inputs
dummy_signals = [{"type": "LONG", "price": 60000.0, "asset": "BTCUSDT", "atr_value": 300.0, "signal_type": "LONG"}]
dummy_df = pd.DataFrame({"timestamp": [pd.Timestamp.now(tz="UTC")], "low": [59000], "high": [61000], "close": [60000], "volume": [100.0]})
dummy_context = GatekeeperContext()

def run_test(mock_time_str, description):
    print(f"\n--- Testing: {description} ({mock_time_str}) ---")
    mock_now = pd.Timestamp(mock_time_str, tz="UTC")
    with patch("engine.router.gatekeeper.pd.Timestamp.now", return_value=mock_now):
        res = gatekeeper.process(
            signals=dummy_signals,
            df=dummy_df,
            smc_map={},
            key_levels=[],
            interval="15m",
            context=dummy_context,
            silent=True
        )
        if res.blocked:
            for b in res.blocked:
                # The reason is often stored in b["diagnostic"]["reason"] or similar.
                # In SignalGatekeeper, self._block sets sig["status"] = reason_code and logs it,
                # but let's check sig directly.
                print(f"BLOCKED! Code: {b.get('status', 'Unknown')}, Message: {b.get('diagnostic', {}).get('block_msg', 'Unknown')}")
        else:
            print("APPROVED! (Or at least passed the Session Veto)")

# Test 1: Normal Time (e.g. 03:30 UTC) - Should pass
run_test("2023-10-10 03:30:00", "Normal Time")

# Test 2: Just before H4 Close (e.g. 03:57 UTC) - Should block
run_test("2023-10-10 03:57:00", "Just before H4 close (04:00)")

# Test 3: Just before D1 Close (e.g. 23:58 UTC) - Should block
run_test("2023-10-10 23:58:00", "Just before D1 close (00:00)")

# Test 4: Just before H1 Close that is NOT H4 (e.g. 02:58 UTC) - Should PASS
run_test("2023-10-10 02:58:00", "Just before H1 close (03:00)")

