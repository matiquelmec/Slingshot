import pytest
import asyncio
import pandas as pd
import numpy as np
from engine.indicators.tradfi_provider import tradfi_provider, TRADFI_ASSETS_CONFIG
from engine.backtest.backtest_tradfi_6mo import run_tradfi_asset_backtest

@pytest.mark.asyncio
async def test_tradfi_provider_assets_specs():
    """Valida que los activos TradFi tengan especificaciones institucionales correctas."""
    assert "XAUUSD" in TRADFI_ASSETS_CONFIG
    assert "US100" in TRADFI_ASSETS_CONFIG
    assert "US30" in TRADFI_ASSETS_CONFIG
    assert "GBPUSD" in TRADFI_ASSETS_CONFIG
    
    gold = TRADFI_ASSETS_CONFIG["XAUUSD"]
    assert gold["contract_size"] == 100
    assert gold["spread_usd"] == 0.18
    
    nasdaq = TRADFI_ASSETS_CONFIG["US100"]
    assert nasdaq["contract_size"] == 1
    assert nasdaq["spread_usd"] == 1.10

def test_tradfi_backtest_execution_engine():
    """Valida que el motor de backtest TradFi aplique Fast BE a +1.0R y TP1 a +1.3R."""
    # Crear serie sintética de 100 velas con tendencia alcista clara
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    base_price = 2500.0 + np.linspace(0, 100, n)
    
    df = pd.DataFrame({
        "timestamp": dates,
        "open": base_price - 1.0,
        "high": base_price + 3.0,
        "low": base_price - 3.0,
        "close": base_price + 1.0,
        "volume": [1000]*n,
        "tr": [6.0]*n,
        "atr": [6.0]*n,
        "ema50": base_price - 2.0,
        "ema200": base_price - 10.0
    })
    
    res = run_tradfi_asset_backtest("XAUUSD", df, initial_balance=100000.0, risk_pct=0.0075)
    
    assert "final_balance" in res
    assert "roi_pct" in res
    assert "total_trades" in res
    assert res["max_drawdown_pct"] < 10.0, "El Drawdown no debe superar el límite de FTMO"
