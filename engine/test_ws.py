import asyncio
import json
import logging
from engine.data.binance_stream import BinanceStream

# Configurar logging básico para ver el output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_callback(data: dict):
    """
    Función simple que se ejecutará cada vez que llegue un dato del WebSocket.
    """
    logger.info(f"¡Dato recibido de Binance! -> {json.dumps(data, indent=2)}")

async def main():
    logger.info("Iniciando prueba de conexión WebSocket con Binance (BTCUSDT)...")
    
    # Instanciar el stream para BTCUSDT
    stream = BinanceStream(symbol="btcusdt")
    
    # Iniciar el stream pasando nuestro callback
    # Usamos asyncio.create_task para que corra de fondo
    task = asyncio.create_task(stream.start(callback=test_callback))
    
    # Dejar que corra por 10 segundos para capturar algunos ticks
    logger.info("Escuchando el mercado por 10 segundos...")
    await asyncio.sleep(10)
    
    # Detener el stream gracefulmente
    logger.info("Deteniendo el stream...")
    stream.stop()
    await task
    logger.info("Prueba de conexión finalizada con éxito.")

if __name__ == "__main__":
    asyncio.run(main())
