import asyncio
import json
import logging
from engine.data.mock_stream import MockStream

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_callback(data: dict):
    logger.info(f"¡Tick MOCK procesado! Precio Actual: {data['data']['c']:.2f} | Cerrada: {data['data']['closed']}")

async def main():
    logger.info("Iniciando prueba de conexión con el MOCK STREAM LOCAL (BTCUSDT)...")
    
    stream = MockStream(symbol="btcusdt")
    task = asyncio.create_task(stream.start(callback=test_callback))
    
    logger.info("Escuchando el mercado simulado por 10 segundos...")
    await asyncio.sleep(10)
    
    logger.info("Deteniendo el stream simulado...")
    stream.stop()
    await task
    logger.info("Prueba MOCK finalizada con éxito. Motor interno listo.")

if __name__ == "__main__":
    asyncio.run(main())
