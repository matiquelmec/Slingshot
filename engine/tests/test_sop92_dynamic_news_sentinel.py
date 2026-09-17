"""
engine/tests/test_sop92_dynamic_news_sentinel.py
================================================
Test suite for SOP-92 Dynamic High-Impact News Sentinel and Post-News Sniper.
"""
import pytest
from datetime import datetime, timezone, timedelta
from engine.indicators.news_interceptor import DynamicNewsInterceptor
from engine.indicators.post_news_sniper import PostNewsInstitutionalSniper
import pandas as pd
import numpy as np

def test_dynamic_news_interceptor_blocks_within_window():
    interceptor = DynamicNewsInterceptor(default_before_mins=30, default_after_mins=15)
    
    # Evento FOMC a las 18:00 UTC
    fomc_time = datetime(2026, 9, 16, 18, 0, 0, tzinfo=timezone.utc)
    mock_events = [
        {
            "title": "Federal Funds Rate",
            "country": "USD",
            "impact": "High",
            "date": fomc_time.isoformat()
        }
    ]

    # Caso 1: 17:35 UTC (25 min antes de la noticia) -> DEBE BLOQUEAR US30
    dt_before = datetime(2026, 9, 16, 17, 35, 0, tzinfo=timezone.utc)
    assert interceptor.is_macro_news_blackout(dt_before, asset="US30", store_events=mock_events) is True

    # Caso 2: 18:10 UTC (10 min después de la noticia) -> DEBE BLOQUEAR US30
    dt_after = datetime(2026, 9, 16, 18, 10, 0, tzinfo=timezone.utc)
    assert interceptor.is_macro_news_blackout(dt_after, asset="US30", store_events=mock_events) is True

    # Caso 3: 17:15 UTC (45 min antes) -> NO DEBE BLOQUEAR (fuera de ventana de 30m)
    dt_safe_before = datetime(2026, 9, 16, 17, 15, 0, tzinfo=timezone.utc)
    assert interceptor.is_macro_news_blackout(dt_safe_before, asset="US30", store_events=mock_events) is False

    # Caso 4: 18:20 UTC (20 min después) -> NO DEBE BLOQUEAR (fuera de ventana de 15m)
    dt_safe_after = datetime(2026, 9, 16, 18, 20, 0, tzinfo=timezone.utc)
    assert interceptor.is_macro_news_blackout(dt_safe_after, asset="US30", store_events=mock_events) is False

def test_currency_isolation():
    interceptor = DynamicNewsInterceptor()
    gbp_event = datetime(2026, 9, 16, 6, 0, 0, tzinfo=timezone.utc)
    mock_events = [
        {
            "title": "CPI y/y",
            "country": "GBP",
            "impact": "High",
            "date": gbp_event.isoformat()
        }
    ]
    
    test_dt = datetime(2026, 9, 16, 5, 50, 0, tzinfo=timezone.utc) # 10 min antes de la noticia de GBP
    
    # Debe bloquear GBPUSD
    assert interceptor.is_macro_news_blackout(test_dt, asset="GBPUSD", store_events=mock_events) is True
    
    # NO debe bloquear US30 ni BTCUSDT (solo dependen de USD)
    assert interceptor.is_macro_news_blackout(test_dt, asset="US30", store_events=mock_events) is False
    assert interceptor.is_macro_news_blackout(test_dt, asset="BTCUSDT", store_events=mock_events) is False

def test_post_news_window_and_setup_evaluation():
    sniper = PostNewsInstitutionalSniper(activation_window_mins=60, min_cooldown_mins=15)
    event_time = datetime(2026, 9, 16, 14, 0, 0, tzinfo=timezone.utc)
    mock_events = [
        {"title": "CPI", "country": "USD", "impact": "High", "date": event_time.isoformat()}
    ]

    # A las 14:30 UTC (30 min después): Ventana activa
    now_test = datetime(2026, 9, 16, 14, 30, 0, tzinfo=timezone.utc)
    info = sniper.is_post_news_window_active("US30", now=now_test, store_events=mock_events)
    assert info is not None
    assert info["elapsed_minutes"] == 30

    # DataFrame mock de velas de 15m con desplazamiento y retroceso
    dates = pd.date_range("2026-09-16 10:00", periods=35, freq="15min")
    prices = np.linspace(40000, 40500, 35)
    df_mock = pd.DataFrame({
        "open": prices - 10,
        "high": prices + 20,
        "low": prices - 20,
        "close": prices
    }, index=dates)

    setup = sniper.evaluate_post_news_setup(df_mock, "US30", info)
    assert setup is not None
    assert setup["strategy"] == "POST_NEWS_INSTITUTIONAL_SNIPER"
    assert setup["confluence_score"] >= 80
    assert setup["rr_ratio"] >= 3.5
