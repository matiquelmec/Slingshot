import asyncio
import pandas as pd
from datetime import datetime, timezone
import random

from engine.api.supabase_client import supabase_service
from engine.main_router import SlingshotRouter

async def test_signal_generation():
    print("Iniciando test de generación de señales...")
    
    # 1. Crear un dataframe simulado de "Ranging" pero falso breakout
    # Vamos a forzar un escenario "perfecto" para que arroje una señal
    data = []
    base_price = 60000
    now = datetime.now(timezone.utc).timestamp()
    
    for i in range(250): # Necesitamos al menos 200 velas para las medias móviles
        # Simular una tendencia bajista constante para forzar oversold
        price = base_price - (i * 10)
        data.append({
            "timestamp": now - ((250 - i) * 900), # 15 min velas
            "open": price + 50,
            "high": price + 100,
            "low": price - 100,
            "close": price,
            "volume": 1000 + random.random() * 500
        })

    # Forzar un "RSI Oversold" + "Bullish MACD" en la última vela
    data[-1]["close"] = price + 500 # Salto alcista
    data[-1]["high"] = price + 600
    data[-1]["volume"] = 5000 # Volumen alto

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    
    # Nos saltaremos a SlingshotRouter para aislarlo, ya que esto depende mucho del Regime actual
    # Simulemos directamente la inserción en la base de datos que haría ws_manager.py
    
    tactical_state = {
        "market_regime": "MARKUP", # Falsificamos el estado para no estar en Standby
        "active_strategy": "TrendFollowingStrategy v2",
    }
    
    sig = {
        "signal_type": "LONG",
        "price": data[-1]["close"],
        "stop_loss": data[-1]["low"] - 50,
        "take_profit_3r": data[-1]["close"] + 300,
        "trigger": "Simulated MACD Cross + Volume Surge",
        "confluence": {"total_score": 85}
    }
    
    print(f"Generando y persistiendo señal simulada: {sig['signal_type']} en ${sig['price']}")
    
    if not supabase_service:
        print("❌ SERVICIO SUPABASE NO ESTA CONFIGURADO")
        return
        
    try:
        db_data = {
            "asset":            "BTCUSDT",
            "interval":         "15m",
            "signal_type":      sig["signal_type"],
            "entry_price":      sig["price"],
            "stop_loss":        sig["stop_loss"],
            "take_profit":      sig["take_profit_3r"],
            "confluence_score": float(sig["confluence"]["total_score"]),
            "regime":           tactical_state["market_regime"],
            "strategy":         tactical_state["active_strategy"],
            "trigger":          sig["trigger"],
            "status":           "ACTIVE",
        }
        
        result = supabase_service.table("signal_events").insert(db_data).execute()
        if result.data:
            print(f"✅ Señal PUSHED a Supabase exitosamente!")
            print(result.data)
        else:
            print(f"⚠️ Supabase no arrojó respuesta (pero tampoco error).")
    except Exception as e:
        print(f"❌ Error al persistir en DB: {e}")

if __name__ == "__main__":
    asyncio.run(test_signal_generation())
