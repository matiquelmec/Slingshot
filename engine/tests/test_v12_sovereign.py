import os
import pytest
import pandas as pd
import numpy as np
from engine.core.confluence import confluence_manager

def test_v12_btc_macro_alignment_veto():
    # Crear DataFrame mock para Altcoin
    df_alt = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=50, freq="15min"),
        "open": [10.0] * 50,
        "high": [10.5] * 50,
        "low": [9.5] * 50,
        "close": [10.2] * 50,
        "volume": [1000] * 50
    })
    
    signal = {
        "asset": "ADAUSDT",
        "symbol": "ADAUSDT",
        "signal_type": "LONG",
        "price": 10.2,
        "timestamp": str(df_alt["timestamp"].iloc[-1])
    }
    
    # 1. Cuando btc_aligned es False -> Debe aplicar VETO (Multiplier = 0 y Conviction = VETADA)
    res_veto = confluence_manager.evaluate_signal(df_alt, signal, btc_aligned=False)
    assert res_veto["conviction"] == "VETADA"
    assert res_veto["score"] == 0
    assert any(c["factor"] == "Alineación Macro BTC" and c["status"] == "DENEGADO" for c in res_veto["checklist"])
    
    # 2. Cuando btc_aligned es True -> Debe agregar bono de +10pts
    res_confirm = confluence_manager.evaluate_signal(df_alt, signal, btc_aligned=True)
    assert res_confirm["conviction"] != "VETADA"
    assert any(c["factor"] == "Alineación Macro BTC" and c["status"] == "CONFIRMADO" for c in res_confirm["checklist"])

if __name__ == "__main__":
    test_v12_btc_macro_alignment_veto()
    print("[SUCCESS] TEST V12 SOVEREIGN COMPLETADO EXITOSAMENTE")
