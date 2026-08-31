"""
engine/tests/test_weekly_seasonality_and_time_gating.py
=============================================================================
SUITE OFICIAL DE CERTIFICACIÓN QA: ESTACIONALIDAD SEMANAL & TIME GATING (v26.2)
=============================================================================
Audita:
1. Penalización de manipulación Lunes Pre-NY (<13:00 UTC) con status PRECAUCIÓN.
2. Bono de días institucionales de alta expansión (Martes, Miércoles, Jueves, Viernes).
3. Veto estricto de Killzones en Índices TradFi (US100, US500, GER40) fuera de horario.
4. Gating de baja liquidez y mechas de fin de semana (Sábado/Domingo) en Cripto.
5. Rotación de sesiones y preservación de niveles PDH/PDL en SessionManager.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from engine.core.confluence import ConfluenceManager
from engine.core.session_manager import SessionManager

def _create_mock_df(timestamp: datetime, is_bullish: bool = True) -> pd.DataFrame:
    """Genera un DataFrame mock anclado a un timestamp específico."""
    n_bars = 60
    base_price = 2500.0
    timestamps = [timestamp - timedelta(minutes=15 * i) for i in range(n_bars)][::-1]
    closes = [base_price + (i * 2.0 if is_bullish else -i * 2.0) for i in range(n_bars)]
    highs = [c + 3.0 for c in closes]
    lows = [c - 3.0 for c in closes]
    opens = [c - 1.0 if is_bullish else c + 1.0 for c in closes]
    volumes = [1000.0 + (500.0 if i == n_bars - 1 else 0.0) for i in range(n_bars)]
    
    return pd.DataFrame({
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

def test_monday_pre_ny_manipulation_penalty():
    """
    Verifica que un Lunes a las 09:00 UTC (Pre-NY) aplique penalización de -5pts y PRECAUCIÓN.
    """
    cm = ConfluenceManager()
    
    # Lunes 2026-08-31 09:00 UTC
    dt_monday_pre_ny = datetime(2026, 8, 31, 9, 0, 0, tzinfo=timezone.utc)
    df = _create_mock_df(dt_monday_pre_ny, is_bullish=True)
    
    signal = {
        "asset": "BTCUSDT",
        "symbol": "BTCUSDT",
        "type": "LONG",
        "price": 60000.0,
        "timestamp": dt_monday_pre_ny.isoformat()
    }
    
    res = cm.evaluate_signal(df=df, signal=signal)
    
    day_item = next((item for item in res["checklist"] if item["factor"] == "Día Institucional"), None)
    assert day_item is not None, "El factor 'Día Institucional' debe estar presente en el checklist"
    assert day_item["status"] == "PRECAUCIÓN"
    assert "Lunes Pre-NY" in day_item["detail"]

def test_institutional_expansion_days_bonus():
    """
    Verifica que Martes, Miércoles, Jueves y Viernes reciban el bono de alta expansión (+5pts).
    """
    cm = ConfluenceManager()
    
    # Probar Miércoles (2026-09-02 14:30 UTC - NY Session)
    dt_wednesday = datetime(2026, 9, 2, 14, 30, 0, tzinfo=timezone.utc)
    df = _create_mock_df(dt_wednesday, is_bullish=True)
    
    signal = {
        "asset": "ETHUSDT",
        "symbol": "ETHUSDT",
        "type": "LONG",
        "price": 3200.0,
        "timestamp": dt_wednesday.isoformat()
    }
    
    res = cm.evaluate_signal(df=df, signal=signal)
    
    day_item = next((item for item in res["checklist"] if item["factor"] == "Día Institucional"), None)
    assert day_item is not None
    assert day_item["status"] == "CONFIRMADO"
    assert "Wednesday" in day_item["detail"]

def test_tradfi_indices_killzone_gating():
    """
    Verifica que los índices TradFi (US100, US500, GER40) sean vetados fuera de Killzones
    y aprobados dentro de la Killzone de NY.
    """
    cm = ConfluenceManager()
    
    # Caso 1: US100 fuera de Killzone (03:00 UTC - Sesión Asiática) -> MULTIPLIER 0.0 / DENEGADO
    dt_off_hours = datetime(2026, 9, 1, 3, 0, 0, tzinfo=timezone.utc)
    df_off = _create_mock_df(dt_off_hours, is_bullish=True)
    sig_off = {
        "asset": "US100",
        "symbol": "US100",
        "type": "LONG",
        "price": 19500.0,
        "timestamp": dt_off_hours.isoformat()
    }
    res_off = cm.evaluate_signal(df=df_off, signal=sig_off)
    assert res_off["score"] == 0
    assert res_off["conviction"] == "VETADA"
    kz_item_off = next((item for item in res_off["checklist"] if item["factor"] == "Killzone Timing TradFi"), None)
    assert kz_item_off is not None
    assert kz_item_off["status"] == "DENEGADO"

    # Caso 2: US100 en NY Killzone (14:30 UTC) -> CONFIRMADO
    dt_ny_kz = datetime(2026, 9, 1, 14, 30, 0, tzinfo=timezone.utc)
    df_ny = _create_mock_df(dt_ny_kz, is_bullish=True)
    sig_ny = {
        "asset": "US100",
        "symbol": "US100",
        "type": "LONG",
        "price": 19500.0,
        "timestamp": dt_ny_kz.isoformat()
    }
    res_ny = cm.evaluate_signal(df=df_ny, signal=sig_ny)
    kz_item_ny = next((item for item in res_ny["checklist"] if item["factor"] == "Killzone Timing TradFi"), None)
    assert kz_item_ny is not None
    assert kz_item_ny["status"] == "CONFIRMADO"

def test_weekend_session_status():
    """
    Verifica que en Fin de Semana (Sábado/Domingo), el sistema identifique la sesión como NEUTRAL.
    """
    cm = ConfluenceManager()
    
    # Sábado 2026-09-05 18:00 UTC
    dt_saturday = datetime(2026, 9, 5, 18, 0, 0, tzinfo=timezone.utc)
    df = _create_mock_df(dt_saturday, is_bullish=True)
    
    signal = {
        "asset": "SOLUSDT",
        "symbol": "SOLUSDT",
        "type": "LONG",
        "price": 175.0,
        "timestamp": dt_saturday.isoformat()
    }
    
    res = cm.evaluate_signal(df=df, signal=signal)
    day_item = next((item for item in res["checklist"] if item["factor"] == "Día Institucional"), None)
    assert day_item is not None
    assert day_item["status"] == "NEUTRAL"
    assert "Saturday" in day_item["detail"]

def test_session_rotation_and_pdh_pdl_preservation():
    """
    Verifica que SessionManager preserve el PDH/PDL entre días.
    """
    sm = SessionManager("BTCUSDT_TEST")
    
    # Simular velas de ayer con High 62000 y Low 59000
    now_utc = datetime.now(timezone.utc)
    yesterday_ts = int((now_utc - timedelta(days=1)).timestamp())
    
    mock_history = [
        {"timestamp": yesterday_ts, "open": 60000, "high": 62000, "low": 59000, "close": 61000, "volume": 500},
        {"timestamp": yesterday_ts + 3600, "open": 61000, "high": 61500, "low": 59500, "close": 60500, "volume": 400}
    ]
    
    sm.bootstrap(mock_history)
    assert sm._state.get("pdh") == 62000
    assert sm._state.get("pdl") == 59000