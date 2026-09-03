import pytest
import logging
import pandas as pd
from engine.indicators.data_utils import fetch_binance_history

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_binance_history_fetch():
    """Prueba la descarga de datos históricos desde Binance (v10.0 logic)."""
    logger.info("Iniciando prueba de descarga de datos (fetch_binance_history)...")
    
    symbol = "BTCUSDT"
    interval = "1h"
    limit = 50
    
    raw = await fetch_binance_history(symbol, interval=interval, limit=limit)
    
    assert raw is not None, "La respuesta de Binance no debería ser None"
    assert len(raw) > 0, f"Deberían haberse descargado velas para {symbol}"
    
    # Validar formato
    first_candle = raw[0]
    assert "data" in first_candle, "Cada vela debe tener una clave 'data'"
    assert "close" in first_candle["data"], "La vela debe contener el precio de cierre"
    
    # Convertir a DataFrame para validar compatibilidad con el router
    df = pd.DataFrame([i["data"] for i in raw])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    
    logger.info(f"¡Éxito! {len(df)} velas obtenidas y procesadas en DataFrame.")
    logger.info(f"Último precio de cierre: {df['close'].iloc[-1]}")
    
    assert len(df) == len(raw)
