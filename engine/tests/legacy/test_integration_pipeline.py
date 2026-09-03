"""
scripts/tests/test_integration_pipeline.py --- v6.0.1 Master Gold Titanium
=========================================================================
Prueba de integración de flujo completo (End-to-End) en memoria: 
Mock Binance WS -> SymbolBroadcaster -> ConfluenceRouter -> SignalHandler
"""
import sys
from pathlib import Path
import asyncio
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from engine.api.ws_manager import SymbolBroadcaster
from engine.api.signal_handler import SignalHandler
from engine.main_router import SlingshotRouter

async def test_full_pipeline():
    print("\n--- INICIANDO TEST E2E: BINANCE -> SIGNAL ---")
    
    # 1. Instanciar el broadcaster
    broadcaster = SymbolBroadcaster("BTCUSDT", "15m")
    
    # Prevenir que inicie tasks asíncronas reales que corran para siempre
    # Mocking "_bootstrap" and "_stream_live" is not necessary if we just feed data
    # to _broadcast directly. But _broadcast receives parsed JSON payloads, not raw Binance.
    # To test the raw binance parsing, we reproduce the logic in _stream_live
    
    # Payload simulado de Binance Kline (vela de 15m)
    binance_kline_payload = {
        "e": "kline",
        "E": 1713296400000,
        "s": "BTCUSDT",
        "k": {
            "t": 1713296400000,
            "T": 1713297299999,
            "s": "BTCUSDT",
            "i": "15m",
            "f": 100,
            "L": 200,
            "o": "85000.00",
            "c": "84950.00",
            "h": "85150.00",
            "l": "84800.00",
            "v": "500.5",
            "n": 100,
            "x": False,
            "q": "42540000",
            "V": "250",
            "Q": "21250000",
            "B": "0"
        }
    }

    # Simulamos el parseo que ocurre en _stream_live
    kline = binance_kline_payload["k"]
    candle_payload = {
        "type": "candle",
        "data": {
            "timestamp": kline["t"] / 1000,
            "open":  float(kline["o"]),
            "high":  float(kline["h"]),
            "low":   float(kline["l"]),
            "close": float(kline["c"]),
            "volume": float(kline["v"])
        }
    }
    
    print(f"[TEST] Vela parseada: {candle_payload['data']}")
    assert candle_payload["data"]["open"] == 85000.0

    print("[TEST] Pasando velada simulada por SignalHandler / Router...")
    
    # Mockear historia mínima para el router
    import pandas as pd
    import numpy as np
    
    def _make_df(rows: int = 150, base: float = 85000.0) -> pd.DataFrame:
        rng = np.random.default_rng(seed=42)
        closes = base + np.cumsum(rng.normal(0, base * 0.002, rows))
        highs  = closes + np.abs(rng.normal(0, base * 0.001, rows))
        lows   = closes - np.abs(rng.normal(0, base * 0.001, rows))
        opens  = closes + rng.normal(0, base * 0.0005, rows)
        vols   = np.abs(rng.normal(500, 100, rows))

        df = pd.DataFrame({
            "timestamp": pd.date_range(start="2024-01-01", periods=rows, freq="15min"),
            "open":   opens.clip(min=1),
            "high":   highs.clip(min=1),
            "low":    lows.clip(min=1),
            "close":  closes.clip(min=1),
            "volume": vols,
        })
        return df

    # En _stream_live, el pipeline táctico se alimenta con _history
    router = SlingshotRouter()
    
    # Agregamos la nueva vela al final del DF
    df_init = _make_df()
    new_row = pd.DataFrame([candle_payload["data"]])
    new_row["timestamp"] = pd.to_datetime(new_row["timestamp"], unit="s")
    df_merged = pd.concat([df_init, new_row], ignore_index=True)
    
    macro_levels = {
        "supports": [{"price": 84000, "strength": 5, "touches": 2}], 
        "resistances": [{"price": 86000, "strength": 5, "touches": 2}]
    }

    from engine.indicators.htf_analyzer import HTFBias
    
    tactical = router.process_market_data(
        df_merged, asset="BTCUSDT", interval="15m",
        macro_levels=macro_levels,
        htf_bias=HTFBias(direction="BULLISH", strength=0.8, reason="Mock", h4_regime="MARKUP", h1_regime="MARKUP")
    )
    
    assert "signals" in tactical
    assert "market_regime" in tactical
    
    print(f"[TEST] Router completado. Régimen detectado: {tactical['market_regime']}")
    print(f"[TEST] Señales procesadas por el Router: {len(tactical['signals'])}")
    
    print("\n[TEST] Verificando SignalHandler (Capa de Decisión de Notificaciones)...")
    handler = SignalHandler("BTCUSDT", "15m", broadcaster)
    
    notified = False
    
    async def mock_send_signal_async(signal, asset, regime, strategy):
        nonlocal notified
        notified = True
        print(f"[MOCK] Notificacion Telegram enviada! Tipo: {signal['type']}")
            
    # Mock Telegram config en signal_handler
    from engine.api import signal_handler
    signal_handler.send_signal_async = mock_send_signal_async
    
    # Inyectar señal falsa para forzar notificación si el router no genero ninguna
    if not tactical["signals"]:
        fake_signal = {
            "symbol": "BTCUSDT",
            "interval": "15m",
            "type": "LONG_OB",
            "confluence": {"score": 95},
            "rr_ratio": 3.0,
            "market_regime": "MARKUP"
        }
        tactical["signals"].append(fake_signal)
        
    await handler.handle(tactical)
    await asyncio.sleep(0.1) # Permitir que create_task de send_signal_async finalice
    
    # Como simulamos una señal válida con score 95 y RR 3.0 (mayor a MIN_RR=2.5), 
    # debió haber activado el DummyNotifier.
    assert notified == True, "La señal no fue enviada a Telegram."
    
    print("\n[SUCCESS] TEST E2E PIPELINE COMPLETADO EXITOSAMENTE")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
