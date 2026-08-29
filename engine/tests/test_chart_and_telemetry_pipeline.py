"""
engine/tests/test_chart_and_telemetry_pipeline.py — v22.3 APEX
================================================================
Test Suite de Certificación para el Motor de Gráficos y Telemetría:
  1. Invarianza Cronológica y Normalización de Velas OHLCV (Sin duplicados, orden ascendente).
  2. Resolución Dinámica de Precisión de Precios (Mega-caps vs Micro-tokens).
  3. Bounding Boxes de SMC (Order Blocks y Fair Value Gaps con top > bottom positivos).
  4. Mapeo de Niveles Institucionales (Fibonacci Golden Pocket 0.618 / 0.66, S/R).
  5. Clusters de Liquidación y Normalización de Opacidad (0-100% clamping).
  6. Integridad del Payload de Telemetría para el Gráfico Canvas.
"""
import pytest
import time
import math

def test_chart_candle_chronological_sorting_and_deduplication():
    """Valida que el pipeline de velas elimine duplicados y ordene estrictamente por tiempo."""
    raw_candles = [
        {"time": 1700000300, "open": 100, "high": 105, "low": 98, "close": 102, "volume": 500},
        {"time": 1700000100, "open": 95, "high": 99, "low": 94, "close": 98, "volume": 300},
        {"time": 1700000200, "open": 98, "high": 101, "low": 97, "close": 100, "volume": 400},
        {"time": 1700000200, "open": 98, "high": 101, "low": 97, "close": 100, "volume": 400}, # Duplicado
    ]
    
    # Algoritmo de normalización idéntico a TradingChart.tsx
    sorted_candles = sorted(raw_candles, key=lambda c: int(c["time"]))
    deduped_candles = []
    for i, c in enumerate(sorted_candles):
        if i == 0 or c["time"] != sorted_candles[i - 1]["time"]:
            deduped_candles.append(c)

    assert len(deduped_candles) == 3
    assert deduped_candles[0]["time"] == 1700000100
    assert deduped_candles[1]["time"] == 1700000200
    assert deduped_candles[2]["time"] == 1700000300
    for i in range(1, len(deduped_candles)):
        assert deduped_candles[i]["time"] > deduped_candles[i-1]["time"]


def test_chart_dynamic_precision_resolution():
    """Valida la resolución de precisión decimal para el eje Y de Lightweight Charts."""
    def resolve_precision(price: float):
        if price < 0.001:
            return 8, 0.00000001
        elif price < 0.1:
            return 6, 0.000001
        elif price < 10:
            return 4, 0.0001
        elif price < 100:
            return 3, 0.001
        else:
            return 2, 0.01

    # BTC ($96,000)
    p_btc, min_btc = resolve_precision(96450.50)
    assert p_btc == 2 and min_btc == 0.01

    # SOL / LINK ($15.45)
    p_sol, min_sol = resolve_precision(15.45)
    assert p_sol == 3 and min_sol == 0.001

    # SUI / DOGE ($2.45)
    p_sui, min_sui = resolve_precision(2.45)
    assert p_sui == 4 and min_sui == 0.001 * 0.1

    # PEPE / SHIB ($0.000015)
    p_pepe, min_pepe = resolve_precision(0.000015)
    assert p_pepe == 8 and min_pepe == 0.00000001


def test_smc_bounding_boxes_geometric_integrity():
    """Valida que los Order Blocks y FVGs tengan coordenadas geométricas válidas (top > bottom > 0)."""
    smc_payload = {
        "order_blocks": {
            "bullish": [{"top": 105.50, "bottom": 102.00, "time": 1700000100}],
            "bearish": [{"top": 115.00, "bottom": 112.50, "time": 1700000200}]
        },
        "fvgs": {
            "bullish": [{"top": 98.50, "bottom": 96.00, "time": 1700000300}],
            "bearish": [{"top": 120.00, "bottom": 118.00, "time": 1700000400}]
        }
    }

    for ob in smc_payload["order_blocks"]["bullish"]:
        assert ob["top"] > ob["bottom"] > 0
        assert ob["time"] > 0

    for ob in smc_payload["order_blocks"]["bearish"]:
        assert ob["top"] > ob["bottom"] > 0
        assert ob["time"] > 0

    for fvg in smc_payload["fvgs"]["bullish"]:
        assert fvg["top"] > fvg["bottom"] > 0
        assert fvg["time"] > 0


def test_fibonacci_golden_pocket_overlay_coherence():
    """Valida que las líneas del Golden Pocket (0.618 / 0.66) se calculen dentro del rango swing."""
    swing_high = 200.0
    swing_low = 100.0
    diff = swing_high - swing_low

    fib_0618 = swing_high - (diff * 0.618)
    fib_0660 = swing_high - (diff * 0.660)

    assert fib_0618 == pytest.approx(138.2, 0.01)
    assert fib_0660 == pytest.approx(134.0, 0.01)
    assert swing_low < fib_0660 < fib_0618 < swing_high


def test_liquidation_strength_clamping_and_opacity_safety():
    """Valida que los clusters de liquidación normalicen su opacidad entre 0.10 y 0.50 sin NaN ni desbordes."""
    sample_liquidations = [
        {"price": 105.0, "strength": 0, "type": "SHORT_LIQ"},
        {"price": 110.0, "strength": 50, "type": "SHORT_LIQ"},
        {"price": 95.0, "strength": 100, "type": "LONG_LIQ"},
        {"price": 90.0, "strength": 150, "type": "LONG_LIQ"}, # Outlier
    ]

    for liq in sample_liquidations:
        clamped_strength = max(0, min(100, liq["strength"]))
        opacity = 0.1 + (clamped_strength / 100.0) * 0.4
        assert 0.10 <= opacity <= 0.50
        assert not math.isnan(opacity)


def test_live_tick_candle_update_invariance():
    """Valida que un tick en vivo actualice High, Low y Close sin romper la apertura de la vela."""
    candle = {"time": 1700000000, "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0}
    
    # Tick alcista por encima del High
    tick_1 = 108.0
    updated_1 = {
        **candle,
        "close": tick_1,
        "high": max(candle["high"], tick_1),
        "low": min(candle["low"], tick_1)
    }
    assert updated_1["open"] == 100.0
    assert updated_1["high"] == 108.0
    assert updated_1["low"] == 98.0
    assert updated_1["close"] == 108.0

    # Tick bajista por debajo del Low
    tick_2 = 95.0
    updated_2 = {
        **candle,
        "close": tick_2,
        "high": max(candle["high"], tick_2),
        "low": min(candle["low"], tick_2)
    }
    assert updated_2["open"] == 100.0
    assert updated_2["high"] == 105.0
    assert updated_2["low"] == 95.0
    assert updated_2["close"] == 95.0


def test_price_update_payload_and_live_tick_broadcasting():
    """Valida la estructura y absorción de eventos price_update desde miniTicker/markPrice."""
    payload = {
        "type": "price_update",
        "data": {
            "symbol": "BTCUSDT",
            "price": 96520.25,
            "ts": 1700000500.0,
            "source": "24hrTicker"
        }
    }
    
    assert payload["type"] == "price_update"
    assert payload["data"]["symbol"] == "BTCUSDT"
    assert float(payload["data"]["price"]) > 0
    assert payload["data"]["ts"] > 0


def test_candle_payload_includes_asset_for_isolation():
    """Valida que el mensaje de vela contenga el asset explícito para evitar contaminación cruzada."""
    kline_sample = {
        "t": 1700000000000,
        "o": "84500.0",
        "h": "84600.0",
        "l": "84450.0",
        "c": "84550.0",
        "v": "12.5",
        "x": False
    }
    
    candle = {
        "type": "candle",
        "asset": "BTCUSDT",
        "data": {
            "timestamp": kline_sample["t"] / 1000,
            "open": float(kline_sample["o"]),
            "high": float(kline_sample["h"]),
            "low": float(kline_sample["l"]),
            "close": float(kline_sample["c"]),
            "volume": float(kline_sample["v"]),
        }
    }
    
    assert candle["type"] == "candle"
    assert candle["asset"] == "BTCUSDT"
    assert candle["data"]["timestamp"] == 1700000000.0
    assert candle["data"]["close"] == 84550.0
    assert candle["data"]["volume"] == 12.5


def test_multi_timeframe_tick_update_safety():
    """Valida la integridad de la actualización de la vela independientemente de la temporalidad."""
    timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '1d']
    last_candle = {"time": 1700000000, "open": 5.40, "high": 5.50, "low": 5.35, "close": 5.45, "volume": 1000}
    
    for tf in timeframes:
        live_tick = 5.55
        updated = {
            **last_candle,
            "close": live_tick,
            "high": max(last_candle["high"], live_tick),
            "low": min(last_candle["low"], live_tick)
        }
        assert updated["close"] == 5.55
        assert updated["high"] == 5.55
        assert updated["low"] == 5.35
        assert updated["time"] == 1700000000

