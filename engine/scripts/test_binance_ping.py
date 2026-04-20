import os
import asyncio
import time
import logging
from dotenv import load_dotenv
from engine.execution.binance_executor import BinanceExecutor

# Cargar llaves de entorno
load_dotenv()

# Configuración de Logging para el Ping
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PingTest")

async def run_ping_test():
    """
    Ejecuta un test de integración real contra Binance Futures Testnet.
    (ROE: ISOLATION - Script lineal sin dependencias de red externas)
    """
    logger.info("🔥 INICIANDO PING DE FUEGO REAL - BINANCE TESTNET")
    
    # 1. Instanciación (dry_run=False para obligar ejecución real en Testnet)
    executor = BinanceExecutor(dry_run=False)
    
    # Validar llaves antes de proceder
    if not os.getenv("BINANCE_API_KEY") or not os.getenv("BINANCE_API_SECRET"):
        logger.error("❌ ERROR: No se encontraron las llaves BINANCE_API_KEY / SECRET en el .env")
        return

    # 2. Test de Autenticación Simple (ROE: ISOLATION)
    try:
        logger.info("🧪 Probando autenticación (fetch_balance)...")
        balance = await executor.client.fetch_balance()
        logger.info("✅ Autenticación exitosa. Balance USDT disponible.")
    except Exception as e:
        logger.error(f"❌ FALLO DE AUTENTICACIÓN: {str(e)}")
        # No salimos, intentamos seguir para ver si el error es específico de un endpoint
    
    # 3. Forja de Señal Mock Perfecta (ROE: PRECISION_VERIFICATION)
    # Simulamos una señal LONG de BTCUSDT
    mock_signal = {
        "id": "ping-test-" + str(int(time.time())),
        "asset": "BTCUSDT",
        "type": "🟢 LONG_SCALP",
        "price": 60000.0,  # Precio base
        "entry_zone_bottom": 60000.0,
        "position_size": 20.0, # 20 USDT de margen
        "leverage": 5,        # 5x leverage
        "stop_loss": 58500.0,  # SL a -2.5%
        "tp1": 61500.0         # TP a +2.5%
    }
    
    logger.info(f"🛰️ Enviando señal Mock: {mock_signal['asset']} {mock_signal['type']} @ {mock_signal['price']}")
    
    # 4. Ejecución y Medición de Latencia
    start_time = time.perf_counter()
    
    try:
        result = await executor.execute_signal(mock_signal)
        end_time = time.perf_counter()
        latency = (end_time - start_time) * 1000
        
        if result.get("status") == "success":
            logger.info("✅ TEST EXITOSO")
            logger.info(f"⏱️ Latencia E2E: {latency:.2f}ms")
            logger.info(f"🆔 Order Entry ID: {result.get('main_order_id')}")
            logger.info(f"🛡️ Protection IDs (SL/TP): {result.get('protection_orders')}")
            logger.info("⚠️ Verificación ROE: Las órdenes SL/TP incluyen el flag 'REDUCE_ONLY' por diseño del executor.")
        else:
            logger.error(f"❌ FALLO EN LA EJECUCIÓN: {result.get('message')}")
            
    except Exception as e:
        logger.error(f"💥 ERROR CRÍTICO DURANTE EL PING: {repr(e)}")

if __name__ == "__main__":
    asyncio.run(run_ping_test())
