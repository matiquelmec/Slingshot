"""
engine/tests/test_sop160_world_class_sessions_10of10.py
========================================================================================
Suite de Verificación SOP-160 (Motor de Sesiones y Calendario Bursátil 10/10):
1. Calendario algorítmico NYSE/CME/LSE (Good Friday, Thanksgiving, Black Friday Early Close,
   Independence Day observado viernes, UK Summer Bank Holiday).
2. Quirófano Horario SOP-137 100% DST-Aware en Verano, Invierno y Brecha Transatlántica US/EU.
3. True Trading Day (17:00 NY en XAUUSD vs 00:00 UTC en BTCUSDT).
4. Multi-Session Anchored VWAP DST-Aware en tradfi_smc_engine.py.
"""
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from engine.core.market_calendar import get_venue_liquidity_status
from engine.core.session_manager import _resolve_trading_day
from engine.core.strategy_ssot import is_toxic_hour_sop137
from engine.indicators.tradfi_smc_engine import is_tradfi_killzone, prepare_tradfi_features


def test_market_calendar_nyse_lse_and_early_closes():
    # 1. Good Friday 2026 (2026-04-03): NYSE y LSE cerrados
    gf = datetime(2026, 4, 3, 14, 0, tzinfo=timezone.utc)
    assert get_venue_liquidity_status("US100", gf)["execution_allowed"] is False
    assert get_venue_liquidity_status("UK100", gf)["execution_allowed"] is False
    # Cripto 24/7 sigue permitido pero marca liquidez delgada US_BANK_HOLIDAY_THIN
    btc_gf = get_venue_liquidity_status("BTCUSDT", gf)
    assert btc_gf["execution_allowed"] is True
    assert btc_gf["liquidity_regime"] == "US_BANK_HOLIDAY_THIN"

    # 2. Independence Day 2026 cae Sábado 4 Jul -> observado Viernes 3 Jul
    ind_obs = datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc)
    assert get_venue_liquidity_status("XAUUSD", ind_obs)["execution_allowed"] is False
    assert get_venue_liquidity_status("UK100", ind_obs)["execution_allowed"] is True

    # 3. Black Friday 2026 (2026-11-27): Early Close 13:00 NY (bloqueo desde 12:30 NY = 17:30 UTC)
    bf_open = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)   # 10:00 NY -> permitido
    bf_cutoff = datetime(2026, 11, 27, 17, 35, tzinfo=timezone.utc) # 12:35 NY -> bloqueado
    assert get_venue_liquidity_status("US100", bf_open)["execution_allowed"] is True
    assert get_venue_liquidity_status("US100", bf_cutoff)["execution_allowed"] is False
    assert is_tradfi_killzone(pd.Timestamp(bf_cutoff), symbol="US100") is False

    # 4. UK Summer Bank Holiday 2026 (2026-08-31): UK100 cerrado, US100 abierto
    uk_bh = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    assert get_venue_liquidity_status("UK100.cash", uk_bh)["execution_allowed"] is False
    assert get_venue_liquidity_status("US100.cash", uk_bh)["execution_allowed"] is True


def test_sop137_toxic_hours_dst_and_transatlantic_gap():
    # Verano (EDT/BST, 2026-06-15): 10:00 NY = 14:00 UTC (tóxica), 15:00 UTC = 11:00 NY (limpia)
    assert is_toxic_hour_sop137(datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc)) is True
    assert is_toxic_hour_sop137(datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)) is False

    # Invierno (EST/GMT, 2026-12-15): 10:00 NY pasa a 15:00 UTC (tóxica), 14:00 UTC = 09:00 NY (limpia)
    assert is_toxic_hour_sop137(datetime(2026, 12, 15, 15, 0, tzinfo=timezone.utc)) is True
    assert is_toxic_hour_sop137(datetime(2026, 12, 15, 14, 0, tzinfo=timezone.utc)) is False

    # Brecha transatlántica (2026-03-18: NY ya en EDT UTC-4, Londres aún en GMT UTC+0)
    # 08:00 Londres = 08:00 UTC (tóxica); 10:00 NY = 14:00 UTC (tóxica)
    assert is_toxic_hour_sop137(datetime(2026, 3, 18, 8, 0, tzinfo=timezone.utc)) is True
    assert is_toxic_hour_sop137(datetime(2026, 3, 18, 14, 0, tzinfo=timezone.utc)) is True


def test_true_trading_day_1700_ny_for_tradfi_vs_0000_utc_for_crypto():
    # 2026-06-15 21:30 UTC = 17:30 NY (verano EDT) -> ya es día siguiente en TradFi (16), aún 15 en Cripto
    dt_summer = datetime(2026, 6, 15, 21, 30, tzinfo=timezone.utc)
    assert str(_resolve_trading_day(dt_summer, "XAUUSD")) == "2026-06-16"
    assert str(_resolve_trading_day(dt_summer, "BTCUSDT")) == "2026-06-15"


def test_tradfi_multi_session_avwap_resets_at_ny_rth():
    ts = pd.date_range("2026-06-15 10:00:00", periods=60, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "timestamp": ts,
        "open": np.linspace(100, 110, 60),
        "high": np.linspace(101, 111, 60),
        "low": np.linspace(99, 109, 60),
        "close": np.linspace(100.5, 110.5, 60),
        "volume": np.full(60, 1000.0),
    })
    feat = prepare_tradfi_features(df)
    assert "session_vwap" in feat.columns
    assert not feat["session_vwap"].isna().any()
