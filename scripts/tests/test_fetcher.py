import asyncio
import logging
from engine.data.fetcher import DataFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("Iniciando prueba de REST API (DataFetcher)...")
    fetcher = DataFetcher()
    
    try:
        # Intentar traer 200 velas de 1 hora de BTCUSDT
        logger.info("Solicitando datos históricos a Binance (Tier 1)...")
        df = await fetcher.get_ohlcv("BTCUSDT", interval="1h", limit=200)
        
        logger.info(f"¡Éxito! Datos obtenidos satisfactoriamente.")
        logger.info(f"Filas recuperadas: {len(df)}")
        logger.info(f"Muestra de los datos (Últimas 3 velas):\n{df.tail(3)}")
    except Exception as e:
        logger.error(f"Error fatal obteniendo datos: {e}")

if __name__ == "__main__":
    asyncio.run(main())
