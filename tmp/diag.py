"""Diagnostico rapido para identificar el error exacto."""
import sys
import traceback
import os

# Forzar UTF-8 en Windows para evitar UnicodeEncodeError
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, ".")

print("=== DIAGNOSTICO SMOKE TEST v4.1 ===\n")

# Test 1
print("1. Import engine.router.analyzer")
try:
    from engine.router.analyzer import MarketAnalyzer
    print("   OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)

# Test 2
print("2. Generar DataFrame sintetico")
try:
    import pandas as pd
    import numpy as np
    rng = np.random.default_rng(42)
    rows = 300
    closes = 85000.0 + np.cumsum(rng.normal(0, 170, rows))
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=rows, freq="15min"),
        "open":   closes,
        "high":   closes + 85.0,
        "low":    closes - 85.0,
        "close":  closes,
        "volume": [500.0] * rows,
    })
    print(f"   OK - {len(df)} filas")
except Exception:
    traceback.print_exc()
    sys.exit(1)

# Test 3
print("3. MarketAnalyzer.analyze()")
try:
    mm = MarketAnalyzer().analyze(df, asset="BTCUSDT", interval="15m")
    print(f"   OK - Regimen: {mm.market_regime} | Precio: {mm.current_price:.2f}")
    print(f"   key_levels type: {type(mm.key_levels).__name__}")
    print(f"   smc type: {type(mm.smc).__name__}")
    print(f"   smc keys: {list(mm.smc.keys())}")
except Exception:
    traceback.print_exc()
    sys.exit(1)

# Test 4
print("4. build_base_result()")
try:
    from engine.router.dispatcher import build_base_result
    result = build_base_result(mm)
    print(f"   OK - Keys: {list(result.keys())}")
except Exception:
    traceback.print_exc()
    sys.exit(1)

# Test 5
print("5. enrich_signal()")
try:
    from engine.router.dispatcher import enrich_signal
    sig = {"timestamp": "2024-01-01 00:15:00", "price": 85000.0, "type": "LONG_OB"}
    risk = {
        "risk_amount_usdt": 50.0, "risk_pct": 1.0, "leverage": 5,
        "position_size_usdt": 5000.0, "stop_loss": 84000.0,
        "take_profit_3r": 88000.0, "entry_zone_top": 85100.0,
        "entry_zone_bottom": 84900.0, "expiry_candles": 3,
    }
    enriched = enrich_signal(sig, risk, "15m")
    print(f"   OK - SL: {enriched['stop_loss']} | TP: {enriched['take_profit_3r']} | Expira: {enriched['expiry_timestamp']}")
except Exception:
    traceback.print_exc()
    sys.exit(1)

# Test 6
print("6. SlingshotRouter.process_market_data()")
try:
    from engine.main_router import SlingshotRouter
    router = SlingshotRouter()
    out = router.process_market_data(df.copy(), asset="BTCUSDT", interval="15m", silent=True)
    print(f"   OK - Aprobadas: {len(out['signals'])} | Bloqueadas: {len(out['blocked_signals'])}")
    print(f"   Estrategia: {out['active_strategy']}")
    print(f"   Regimen: {out['market_regime']}")
except Exception:
    traceback.print_exc()
    sys.exit(1)

print("\n=== TODOS LOS TESTS PASARON - ARQUITECTURA v4.1 PLATINUM ===")
