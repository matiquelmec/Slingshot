"""
scripts/tests/test_router_smoke.py --- v5.7.155 Master Gold
=========================================================================
Smoke Test modular: verifica cada capa de la arquitectura v5.x
con datos sintéticos (sin conexión a Binance).
Compatible con Windows (sin emojis en stdout).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np


def _make_df(rows: int = 300, base: float = 85000.0) -> pd.DataFrame:
    """DataFrame OHLCV sintetico con variacion realista."""
    rng = np.random.default_rng(seed=42)
    closes = base + np.cumsum(rng.normal(0, base * 0.002, rows))
    highs  = closes + np.abs(rng.normal(0, base * 0.001, rows))
    lows   = closes - np.abs(rng.normal(0, base * 0.001, rows))
    opens  = closes + rng.normal(0, base * 0.0005, rows)
    vols   = np.abs(rng.normal(500, 100, rows))

    df = pd.DataFrame({
        "timestamp": pd.date_range(start="2024-01-01", periods=rows, freq="15min"),
        "open":   opens.clip(min=1),
        "high":   highs.clip(min=1),
        "low":    lows.clip(min=1),
        "close":  closes.clip(min=1),
        "volume": vols,
    })
    return df


# ---------------------------------------------------------------------------
# Tests Unitarios por Modulo
# ---------------------------------------------------------------------------

def test_market_analyzer():
    """MarketAnalyzer produce un MarketMap valido."""
    from engine.router.analyzer import MarketAnalyzer
    mm = MarketAnalyzer().analyze(_make_df(), asset="BTCUSDT", interval="15m")

    assert mm.current_price > 0,              f"Precio invalido: {mm.current_price}"
    assert mm.market_regime is not None,      "Regimen no detectado"
    assert isinstance(mm.smc, dict),          "SMC data invalida"
    assert isinstance(mm.key_levels, dict),   "Key levels invalidos"
    assert mm.df_analyzed is not None,        "DataFrame analizado faltante"

    obs_b = len(mm.smc.get("order_blocks", {}).get("bullish", []))
    obs_r = len(mm.smc.get("order_blocks", {}).get("bearish", []))
    print(f"  [PASS] MarketAnalyzer | Regimen: {mm.market_regime} | OBs: {obs_b}B/{obs_r}R | Precio: ${mm.current_price:,.2f}")


def test_build_base_result():
    """build_base_result produce la estructura de resultado esperada."""
    from engine.router.analyzer import MarketAnalyzer
    from engine.router.dispatcher import build_base_result

    mm = MarketAnalyzer().analyze(_make_df(), asset="BTCUSDT", interval="15m")
    result = build_base_result(mm)

    required = [
        "asset", "interval", "timestamp", "current_price", "market_regime",
        "active_strategy", "key_levels", "smc", "signals", "blocked_signals",
        "fibonacci", "htf_bias", "diagnostic",
    ]
    missing = [k for k in required if k not in result]
    assert not missing, f"Claves faltantes: {missing}"
    assert isinstance(result["key_levels"], dict), "key_levels debe ser dict"
    assert result["signals"] == [],               "signals debe iniciar vacio"
    assert result["blocked_signals"] == [],        "blocked_signals debe iniciar vacio"
    print(f"  [PASS] build_base_result | {len(result)} claves | Estrategia: {result['active_strategy']}")


def test_enrich_signal():
    """enrich_signal inyecta correctamente los datos de riesgo."""
    from engine.router.dispatcher import enrich_signal
    import pandas as pd

    sig = {"timestamp": "2024-01-01 00:15:00", "price": 85000.0, "type": "LONG_OB"}
    risk = {
        "risk_amount_usdt": 50.0, "risk_pct": 1.0, "leverage": 5,
        "position_size_usdt": 5000.0, "stop_loss": 84000.0,
        "take_profit_3r": 88000.0, "entry_zone_top": 85100.0,
        "entry_zone_bottom": 84900.0, "expiry_candles": 3,
    }
    enriched = enrich_signal(sig, risk, "15m")

    assert enriched["stop_loss"] == 84000.0,      "SL no inyectado"
    assert enriched["take_profit_3r"] == 88000.0, "TP no inyectado"
    assert enriched["leverage"] == 5,             "Leverage no inyectado"
    assert "expiry_timestamp" in enriched,        "Timestamp expiracion faltante"
    assert enriched["interval_minutes"] == 15,    "Intervalo incorrecto"

    expiry = pd.Timestamp(enriched["expiry_timestamp"])
    origin = pd.Timestamp("2024-01-01 00:15:00")
    assert expiry > origin, "Expiracion debe ser posterior al inicio"
    print(f"  [PASS] enrich_signal | SL: {enriched['stop_loss']} | TP: {enriched['take_profit_3r']} | Expira: {enriched['expiry_timestamp']}")


def test_slingshot_router_smoke():
    """Pipeline completo SlingshotRouter con datos sinteticos."""
    from engine.main_router import SlingshotRouter

    router = SlingshotRouter()
    result = router.process_market_data(_make_df(), asset="BTCUSDT", interval="15m", silent=True)

    assert isinstance(result, dict),               "Resultado debe ser dict"
    assert "signals" in result,                    "Clave 'signals' faltante"
    assert "blocked_signals" in result,            "Clave 'blocked_signals' faltante"
    assert "market_regime" in result,              "Clave 'market_regime' faltante"
    assert "smc" in result,                        "Clave 'smc' faltante"
    assert "fibonacci" in result,                  "Clave 'fibonacci' faltante"
    assert result["active_strategy"] is not None,  "Estrategia activa no declarada"

    total = len(result["signals"]) + len(result["blocked_signals"])
    print(f"  [PASS] SlingshotRouter | Aprobadas: {len(result['signals'])} | Bloqueadas: {len(result['blocked_signals'])} | Total procesadas: {total}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  SMOKE TEST --- SLINGSHOT v5.7.155 Master Gold UNIFIED")
    print("=" * 60)

    suite = [
        ("MarketAnalyzer",    test_market_analyzer),
        ("build_base_result", test_build_base_result),
        ("enrich_signal",     test_enrich_signal),
        ("SlingshotRouter",   test_slingshot_router_smoke),
    ]

    passed = failed = 0
    for name, fn in suite:
        print(f"\n[TEST] {name}")
        try:
            fn()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  [FAIL] {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 60}")
    status = "TODOS PASARON" if failed == 0 else f"{failed} FALLARON"
    print(f"  Resultado: {passed}/{passed+failed} --- {status}")
    print("=" * 60)
    sys.exit(failed)
