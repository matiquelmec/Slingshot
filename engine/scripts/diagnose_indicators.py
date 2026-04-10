
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Añadir el root del proyecto al path
sys.path.append(os.getcwd())

from engine.api.binance_client import binance_client
from engine.indicators.structure import identify_order_blocks, detect_fvg
from engine.indicators.regime import RegimeDetector

def test_indicators():
    print("--- DIAGNÓSTICO DE INDICADORES (Slingshot v6.1) ---")
    pair = "BTCUSDT"
    interval = "15m"
    
    print(f"Descargando datos para {pair} {interval}...")
    df = binance_client.get_ohlcv(pair, interval, limit=500)
    
    if df is None or df.empty:
        print("Error: No se pudieron descargar datos.")
        return

    print(f"Datos recibidos: {len(df)} velas.")
    
    # 1. Detectar Régimen
    detector = RegimeDetector()
    df = detector.detect_regime(df)
    print(f"Régimen predominante: {df['market_regime'].tail(20).mode()[0]}")
    
    # 2. Detectar Order Blocks
    print("Calculando Order Blocks...")
    df = identify_order_blocks(df)
    
    bullish_obs = df[df['ob_bullish'] == True]
    bearish_obs = df[df['ob_bearish'] == True]
    
    print(f"Bullish OBs detectados: {len(bullish_obs)}")
    print(f"Bearish OBs detectados: {len(bearish_obs)}")
    
    # 3. Detectar FVG
    print("Calculando FVGs...")
    df = detect_fvg(df)
    bullish_fvgs = df[df['fvg_bullish'] == True]
    bearish_fvgs = df[df['fvg_bearish'] == True]
    
    print(f"Bullish FVGs detectados: {len(bullish_fvgs)}")
    print(f"Bearish FVGs detectados: {len(bearish_fvgs)}")
    
    if len(bullish_obs) == 0 and len(bearish_obs) == 0:
        print("\n⚠️ ALERTA: No se detectan OBs. Revisando lógica interna...")
        # Revisemos los últimos 5 cambios de precio para ver por qué no califican
        last_changes = df['change_pct'].tail(10)
        print(f"Últimos 10 cambios %: {last_changes.tolist()}")
        print(f"Threshold de expansión (1.5%): {df['change_pct'].std() * 1.5}")

if __name__ == "__main__":
    test_indicators()
