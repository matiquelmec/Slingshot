import pytest
import pandas as pd
import numpy as np
from engine.core.confluence import ConfluenceManager

def test_ker_adaptive_quarantine():
    cm = ConfluenceManager()
    
    # 1. Crear DF con tendencia limpia (KER alto)
    clean_prices = np.linspace(100, 150, 30) # Tendencia lineal sin mechas
    df_clean = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=30, freq="15min"),
        "open": clean_prices - 0.1,
        "high": clean_prices + 0.2,
        "low": clean_prices - 0.2,
        "close": clean_prices,
        "volume": [1000] * 30,
        "atr": [0.5] * 30
    })
    
    sig_clean = {
        "asset": "BTCUSDT",
        "symbol": "BTCUSDT",
        "signal_type": "LONG",
        "price": 150.0,
        "timestamp": str(df_clean["timestamp"].iloc[-1])
    }
    
    res_clean = cm.evaluate_signal(df_clean, sig_clean)
    assert "asset_health" in res_clean
    assert res_clean["asset_health"]["ker"] >= 0.40
    assert res_clean["asset_health"]["status"] == "OPTIMAL"
    assert not res_clean["asset_health"]["is_quarantined"]
    
    # 2. Crear DF con mechas altamente ruidosas (KER bajo)
    noisy_prices = [100.0 if i % 2 == 0 else 100.5 for i in range(30)] # Subidas y bajadas constantes
    df_noisy = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=30, freq="15min"),
        "open": noisy_prices,
        "high": [p + 5.0 for p in noisy_prices],
        "low": [p - 5.0 for p in noisy_prices],
        "close": noisy_prices,
        "volume": [1000] * 30,
        "atr": [0.5] * 30
    })
    
    sig_noisy = {
        "asset": "XRPUSDT",
        "symbol": "XRPUSDT",
        "signal_type": "LONG",
        "price": 100.0,
        "timestamp": str(df_noisy["timestamp"].iloc[-1])
    }
    
    res_noisy = cm.evaluate_signal(df_noisy, sig_noisy)
    assert "asset_health" in res_noisy
    assert res_noisy["asset_health"]["ker"] < 0.22
    assert res_noisy["asset_health"]["status"] == "QUARANTINED"
    assert res_noisy["asset_health"]["is_quarantined"]
