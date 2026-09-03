import sys
import os
sys.path.append(os.getcwd())
import pandas as pd
import numpy as np

from engine.strategies.larry_williams import LarryWilliamsOopsStrategy

def test_oops_strategy_long():
    strategy = LarryWilliamsOopsStrategy()
    
    # Crear un dataframe simulado de 15m con 100 velas
    # Queremos simular que ayer el mínimo (PDL) fue 100.0
    # Y en la vela actual (velas de hoy), el precio cae a 98.0 pero cierra en 101.0
    timestamps = pd.date_range(start="2026-06-01 00:00:00", periods=100, freq="15min")
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": [105.0] * 100,
        "high": [110.0] * 100,
        "low": [102.0] * 100,
        "close": [106.0] * 100,
        "volume": [1000.0] * 100
    })
    
    # Definir velas para el día anterior (primeras 50 velas)
    df.loc[0:49, 'low'] = 100.0  # El mínimo de ayer es 100.0
    
    # Simular la última vela (vela actual de hoy):
    # Cae por debajo del PDL (100.0) y cierra por encima de él
    df.loc[99, 'low'] = 98.0
    df.loc[99, 'open'] = 99.0
    df.loc[99, 'close'] = 101.0
    df.loc[99, 'volume'] = 2000.0 # Alto volumen para superar el filtro
    
    df_analyzed = strategy.analyze(df)
    
    # Verificar que pdh y pdl se hayan calculado
    assert 'pdh' in df_analyzed.columns
    assert 'pdl' in df_analyzed.columns
    assert df_analyzed['pdl'].iloc[99] == 100.0
    
    opportunities = strategy.find_opportunities(df_analyzed, asset="BTCUSDT")
    
    # Debería haber una oportunidad LONG detectada
    assert len(opportunities) == 1
    assert opportunities[0]['signal_type'] == 'LONG'
    assert opportunities[0]['price'] == 100.0 # entrada al PDL
    assert opportunities[0]['type'] == 'Oops! Reversal'
    
    print("Test Oops Strategy Long: PASSED")

if __name__ == "__main__":
    test_oops_strategy_long()
