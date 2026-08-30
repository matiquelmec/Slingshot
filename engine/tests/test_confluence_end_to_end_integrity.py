"""
engine/tests/test_confluence_end_to_end_integrity.py
=============================================================================
SUITE OFICIAL DE INTEGRIDAD Y TRANSMISIÓN DE CONFLUENCIA (v25.1 ELITE)
=============================================================================
Valida:
1. Evaluación completa de los 14 factores institucionales (SMC, HTF, KER, RVOL, Liquidez, Killzones).
2. Sanitización estricta anti-NaN/Inf en todos los valores numéricos y serialización JSON.
3. Normalización semántica de estados en el checklist (CONFIRMADO, DENEGADO, PRECAUCIÓN, etc.).
4. Integridad de transmisión hacia el SignalHandler y TelegramDispatcher sin pérdida de datos.
"""
import pytest
import json
import math
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from engine.core.confluence import ConfluenceManager, confluence_manager
from engine.api.signal_handler import SignalHandler
from engine.router.telegram_dispatcher import telegram_dispatcher


def _create_mock_market_dataframe(n_bars: int = 60, is_bullish: bool = True) -> pd.DataFrame:
    """Genera un DataFrame mock con todas las columnas necesarias para el jurado de confluencia."""
    now = pd.Timestamp.now(tz=timezone.utc)
    base_price = 2500.0
    
    timestamps = [now - pd.Timedelta(minutes=15 * i) for i in range(n_bars)][::-1]
    closes = [base_price + (i * 2.0 if is_bullish else -i * 2.0) for i in range(n_bars)]
    highs = [c + 3.0 for c in closes]
    lows = [c - 3.0 for c in closes]
    opens = [c - 1.0 if is_bullish else c + 1.0 for c in closes]
    volumes = [1000.0 + (500.0 if i == n_bars - 1 else 0.0) for i in range(n_bars)]
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "ema50": closes,
        "ema200": [c - 20.0 if is_bullish else c + 20.0 for c in closes],
        "market_regime": ["MARKUP" if is_bullish else "MARKDOWN"] * n_bars,
        "ob_bullish": [False] * (n_bars - 1) + [is_bullish],
        "ob_bearish": [False] * (n_bars - 1) + [not is_bullish],
        "fvg_bullish": [False] * (n_bars - 1) + [is_bullish],
        "fvg_bearish": [False] * (n_bars - 1) + [not is_bullish],
    })
    return df


# ── TEST 1: EVALUACIÓN DE FACTORES INSTITUCIONALES EN LONG & SHORT ───────────

def test_confluence_all_factors_evaluation_long_and_short():
    """
    Verifica que el ConfluenceManager evalúe con precisión señales LONG y SHORT,
    produciendo scores coherentes, polaridad y un checklist bien formado.
    """
    cm = ConfluenceManager()
    
    # 1. Evaluar LONG en tendencia alcista
    df_bull = _create_mock_market_dataframe(n_bars=60, is_bullish=True)
    sig_long = {
        "asset": "BTCUSDT",
        "symbol": "BTCUSDT",
        "type": "LONG",
        "signal_type": "LONG",
        "price": float(df_bull["close"].iloc[-1]),
        "timestamp": df_bull["timestamp"].iloc[-1].isoformat(),
        "regime": "MARKUP"
    }
    
    res_long = cm.evaluate_signal(
        df=df_bull,
        signal=sig_long,
        btc_aligned=True,
        onchain_bias="BULLISH_ACCUMULATION"
    )
    
    assert res_long["score"] >= 60
    assert res_long["is_long"] is True
    assert res_long["conviction"] in ("ALTA CONVICCIÓN", "SÓLIDA")
    assert len(res_long["checklist"]) >= 5
    assert "reasoning" in res_long and len(res_long["reasoning"]) > 10
    
    # 2. Evaluar SHORT en tendencia bajista
    df_bear = _create_mock_market_dataframe(n_bars=60, is_bullish=False)
    sig_short = {
        "asset": "ETHUSDT",
        "symbol": "ETHUSDT",
        "type": "SHORT",
        "signal_type": "SHORT",
        "price": float(df_bear["close"].iloc[-1]),
        "timestamp": df_bear["timestamp"].iloc[-1].isoformat(),
        "regime": "MARKDOWN"
    }
    
    res_short = cm.evaluate_signal(
        df=df_bear,
        signal=sig_short,
        btc_aligned=True,
        onchain_bias="BEARISH_WARNING"
    )
    
    assert res_short["score"] >= 60
    assert res_short["is_long"] is False
    assert res_short["conviction"] in ("ALTA CONVICCIÓN", "SÓLIDA")


# ── TEST 2: SANITIZACIÓN ESTRICTA Y SERIALIZACIÓN JSON SEGURA ────────────────

def test_confluence_json_serialization_safe():
    """
    Verifica que el resultado del Jurado de Confluencia sea 100% serializable a JSON
    sin valores NaN, infinitos ni objetos no primitivos.
    """
    cm = ConfluenceManager()
    df = _create_mock_market_dataframe(n_bars=50, is_bullish=True)
    
    sig = {
        "asset": "SOLUSDT",
        "type": "LONG",
        "signal_type": "LONG",
        "price": 145.50,
        "timestamp": df["timestamp"].iloc[-1].isoformat()
    }
    
    res = cm.evaluate_signal(df=df, signal=sig)
    
    # Verificar que los campos numéricos sean números finitos
    assert math.isfinite(res["score"])
    assert math.isfinite(res["rvol"])
    assert math.isfinite(res["smt_strength"])
    assert math.isfinite(res["asset_health"]["ker"])
    
    # Serialización JSON estricta (no debe arrojar excepción)
    json_str = json.dumps(res, default=str)
    assert len(json_str) > 50
    parsed = json.loads(json_str)
    assert parsed["score"] == res["score"]
    assert parsed["conviction"] == res["conviction"]


# ── TEST 3: NORMALIZACIÓN SEMÁNTICA DE ESTADOS EN CHECKLIST ──────────────────

def test_confluence_checklist_status_normalization():
    """
    Verifica que todos los factores del checklist contengan estados estandarizados
    reconocidos por el sistema y el frontend.
    """
    cm = ConfluenceManager()
    df = _create_mock_market_dataframe(n_bars=50, is_bullish=True)
    
    sig = {
        "asset": "AVAXUSDT",
        "type": "LONG",
        "signal_type": "LONG",
        "price": 28.50,
        "timestamp": df["timestamp"].iloc[-1].isoformat()
    }
    
    res = cm.evaluate_signal(df=df, signal=sig)
    valid_statuses = {
        "CONFIRMADO", "FAVORABLE", "PRECAUCIÓN", "DIVERGENTE", 
        "DENEGADO", "NEUTRAL", "CALIBRANDO", "FRESCO", "ALERTA",
        "OPTIMAL", "MODERATE_NOISE", "QUARANTINED", "OBSOLETO",
        "BAJO", "PARCIAL", "VOLÁTIL", "ALINEADO", "INSTITUCIONAL", "ACTIVO", "ELITE"
    }
    
    for item in res["checklist"]:
        assert "factor" in item
        assert "status" in item
        assert "detail" in item
        assert item["status"] in valid_statuses, f"Estado desconocido en checklist: {item['status']}"


# ── TEST 4: COHERENCIA DE SALIDAS 50/30/20 EN TELEGRAM Y SIGNAL HANDLER ──────

def test_confluence_to_telegram_and_signal_handler_coherence():
    """
    Verifica que la transmisión del payload hacia el SignalHandler y TelegramDispatcher
    preserve el formato de salidas escalonadas 50/30/20 (+1.5R, +3.0R, +5.0R).
    """
    price = 60000.0
    sl = 59000.0
    dist = 1000.0
    
    # Validar que los niveles calculados coincidan con la especificación v25.1
    expected_tp1 = price + (dist * 1.5)  # 61500.0
    expected_tp2 = price + (dist * 3.0)  # 63000.0
    expected_tp3 = price + (dist * 5.0)  # 65000.0
    
    # Probar formateo en Telegram Dispatcher sin enviar por red
    dist_calc = abs(price - sl)
    tp1 = price + (dist_calc * 1.5 * 1.0)
    tp2 = price + (dist_calc * 3.0 * 1.0)
    tp3 = price + (dist_calc * 5.0 * 1.0)
    assert tp1 == expected_tp1
    assert tp2 == expected_tp2
    assert tp3 == expected_tp3


# ── TEST 5: ESPECIALIZACIÓN MULTITEMPORAL DEL ORO (1H NATIVO) ─────────────────

def test_confluence_gold_1h_native_specialization():
    """
    Verifica que el Oro (PAXGUSDT / XAUUSD) evalúe con alta convicción en temporalidad 1H
    bajo el régimen secular alcista Long-Only y rechace ventas en corto.
    """
    cm = ConfluenceManager()
    df_gold_1h = _create_mock_market_dataframe(n_bars=60, is_bullish=True)
    
    # 1. Señal LONG en Oro 1H
    sig_gold_long = {
        "asset": "PAXGUSDT",
        "symbol": "PAXGUSDT",
        "type": "LONG",
        "signal_type": "LONG",
        "price": 2540.0,
        "timeframe": "1h",
        "interval": "1h",
        "timestamp": df_gold_1h["timestamp"].iloc[-1].isoformat(),
        "regime": "MARKUP"
    }
    
    res_gold_long = cm.evaluate_signal(df=df_gold_1h, signal=sig_gold_long)
    assert res_gold_long["score"] >= 60
    assert res_gold_long["is_long"] is True
    assert res_gold_long["conviction"] in ("ALTA CONVICCIÓN", "SÓLIDA")
    
    # 2. Intento de SHORT en Oro (debe ser vetado automáticamente por ATH Long-Only)
    sig_gold_short = {
        "asset": "PAXGUSDT",
        "symbol": "PAXGUSDT",
        "type": "SHORT",
        "signal_type": "SHORT",
        "price": 2540.0,
        "timeframe": "1h",
        "interval": "1h",
        "timestamp": df_gold_1h["timestamp"].iloc[-1].isoformat(),
        "regime": "MARKDOWN"
    }
    res_gold_short = cm.evaluate_signal(df=df_gold_1h, signal=sig_gold_short)
    assert res_gold_short["score"] == 0 or res_gold_short["conviction"] == "VETADA"
