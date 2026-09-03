import sys
import asyncio
import pandas as pd
sys.path.insert(0, '.')
from engine.indicators.data_utils import fetch_binance_history
from engine.main_router import SlingshotRouter

async def test_router_liq():
    router = SlingshotRouter()
    print("Descargando historial de BTCUSDT para validar liquidaciones...")
    history = await fetch_binance_history('BTCUSDT', '15m', limit=50)
    
    if not history:
        print("Error al descargar historial.")
        return
        
    df = pd.DataFrame([h['data'] for h in history])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    
    # Procesar datos a través del router para forzar el cálculo de confluencia
    result = await router.process_market_data(df, asset='BTCUSDT', interval='15m', silent=True)
    
    # Crear señal mock
    mock_sig = {
        "asset": "BTCUSDT",
        "price": float(df["close"].iloc[-1]),
        "type": "SHORT",
        "signal_type": "SHORT",
        "timestamp": "2026-07-15T00:00:00Z",
        "atr_value": 150.0,
        "confluence": {"score": 75}
    }
    
    # Calcular clusters en vivo
    from engine.indicators.liquidations import estimate_liquidation_clusters
    liq_clusters = estimate_liquidation_clusters(df, mock_sig["price"])
    
    # Llamamos al RiskManager directamente para evaluar
    risk_data = router._risk.calculate_position(
        current_price=mock_sig["price"],
        signal_type="SHORT",
        market_regime="BULLISH_TREND",
        atr_value=150.0,
        asset="BTCUSDT",
        liquidations=liq_clusters,
        confluence_score=75
    )
    
    from engine.main_router import enrich_signal
    enriched_sig = enrich_signal(mock_sig, risk_data, "15m")
    
    confluence_details = enriched_sig.get("confluence", {})
    print("=== DETALLES DE CONFLUENCIA DE LA SEÑAL ===")
    print("Score global       :", confluence_details.get("score"))
    print("¿Posee checklist?   :", "SÍ" if "checklist" in confluence_details else "NO")
    
    # Mostrar items del checklist
    checklist = confluence_details.get("checklist", [])
    for item in checklist:
        print(f"  - {item['name']}: {item['value']} | Status: {item['status']}")
        
    # Comprobar si 'Liq Clusters' está en el checklist y si no es un Bypass
    liq_item = next((i for i in checklist if "Liq Clusters" in i["name"]), None)
    if liq_item:
        print()
        print("¿Liquidaciones disponibles en el checklist? :", "SÍ" if "no disponibles" not in str(liq_item["value"]) else "NO")
    else:
        print("\nError: No se encontró 'Liq Clusters' en el checklist.")

asyncio.run(test_router_liq())
