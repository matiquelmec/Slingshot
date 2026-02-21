import asyncio
import json
import logging
from engine.data.cc_stream import CryptoCompareStream

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_callback(data: dict):
    logger.info(f"¡Dato recibido de CryptoCompare! -> {json.dumps(data, indent=2)}")

async def main():
    logger.info("Iniciando prueba de conexión WebSocket con CryptoCompare (BTCUSD)...")
    
    # Try with public connection (no API key)
    stream = CryptoCompareStream(symbol="btcusd")
    task = asyncio.create_task(stream.start(callback=test_callback))
    
    logger.info("Escuchando el mercado por 15 segundos...")
    await asyncio.sleep(15)
    
    logger.info("Deteniendo el stream...")
    stream.stop()
    await task
    logger.info("Prueba finalizada.")

if __name__ == "__main__":
    asyncio.run(main())
