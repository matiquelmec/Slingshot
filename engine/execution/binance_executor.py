import os
import asyncio
import logging
import ccxt  # [FIX v6.6.17] Sync version for Windows stability
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Configuración de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BinanceExecutor")

class BinanceExecutor:
    """
    Motor de Ejecución para Binance (Modo Futures Testnet).
    Refactorizado a modo Síncrono via Hilos para máxima estabilidad en Windows.
    """
    
    def __init__(self, dry_run: bool = False):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.dry_run = dry_run
        self.testnet = True # 🚨 ROE: STRICT_TESTNET_LOCK
        
        if not self.dry_run and (not self.api_key or not self.api_secret):
            logger.error("❌ BINANCE_API_KEY o SECRET no encontrados. Cambiando a DRY_RUN.")
            self.dry_run = True
            
        # Instancia Síncrona
        self.client = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
            }
        })
        
        # Bypass manual de sandbox (CCXT Block Evade)
        if self.testnet:
            testnet_url = 'https://testnet.binancefuture.com/fapi/v1'
            self.client.urls['api']['fapiPublic'] = testnet_url
            self.client.urls['api']['fapiPrivate'] = testnet_url
            self.client.urls['api']['public'] = testnet_url
            self.client.urls['api']['private'] = testnet_url
            logger.info("🛠️ [SYNC_BYPASS] Binance Futures Testnet configurada correctamente.")
        
        self.markets_loaded = False

    async def _load_markets(self):
        """Carga markets en un hilo separado."""
        if not self.markets_loaded:
            try:
                await asyncio.to_thread(self.client.load_markets)
                self.markets_loaded = True
                logger.info("✅ Mercados de Binance cargados correctamente (Sync Mode).")
            except Exception as e:
                logger.error(f"❌ Error cargando mercados: {e}")
                raise

    async def execute_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta una señal aprobada usando asyncio.to_thread para cada llamada a la API.
        """
        if self.dry_run:
            logger.info(f"🧪 [DRY RUN] Ejecutando señal: {signal.get('asset')} {signal.get('type')}")
            return {"status": "success", "mode": "DRY_RUN", "signal_id": signal.get('id')}

        await self._load_markets()
        
        symbol = signal.get('asset', 'BTCUSDT')
        if 'USDT' not in symbol: symbol += 'USDT'
        
        side = 'buy' if 'LONG' in signal.get('type', '') else 'sell'
        entry_price = signal.get('price') or signal.get('entry_zone_bottom')
        amount_usd = signal.get('position_size', 100)
        leverage = signal.get('leverage', 1)
        
        try:
            # 1. Configurar Apalancamiento
            await asyncio.to_thread(self.client.fapiPrivatePostLeverage, {
                "symbol": symbol.replace('/', ''),
                "leverage": int(leverage)
            })
            
            # 2. Calcular cantidad ajustada
            current_price = entry_price 
            raw_amount = (amount_usd * leverage) / current_price
            
            market = self.client.market(symbol)
            
            # Ajustar cantidad al step size mínimo
            min_amount = market['limits']['amount']['min']
            amount = float((Decimal(str(raw_amount)) / Decimal(str(min_amount))).quantize(Decimal('1'), rounding=ROUND_DOWN) * Decimal(str(min_amount)))
            
            logger.info(f"🚀 Enviando orden {side.upper()} para {symbol}: {amount} unidades a {entry_price}")

            # 3. Orden de Entrada
            main_order = await asyncio.to_thread(
                self.client.create_order,
                symbol=symbol,
                type='market',
                side=side,
                amount=amount
            )
            
            # 4. Órdenes de Protección
            sl_price = signal.get('stop_loss')
            tp1_price = signal.get('tp1')
            
            protection_orders = []
            
            if sl_price:
                sl_side = 'sell' if side == 'buy' else 'buy'
                sl_order = await asyncio.to_thread(
                    self.client.create_order,
                    symbol=symbol,
                    type='STOP_MARKET',
                    side=sl_side,
                    amount=amount,
                    params={
                        'stopPrice': self.client.price_to_precision(symbol, sl_price),
                        'reduceOnly': True
                    }
                )
                protection_orders.append(sl_order['id'])
                logger.info(f"🛡️ Stop Loss colocado en {sl_price}")

            if tp1_price:
                tp_side = 'sell' if side == 'buy' else 'buy'
                tp_order = await asyncio.to_thread(
                    self.client.create_order,
                    symbol=symbol,
                    type='TAKE_PROFIT_MARKET',
                    side=tp_side,
                    amount=amount,
                    params={
                        'stopPrice': self.client.price_to_precision(symbol, tp1_price),
                        'reduceOnly': True
                    }
                )
                protection_orders.append(tp_order['id'])
                logger.info(f"🎯 Take Profit colocado en {tp1_price}")

            return {
                "status": "success",
                "exchange": "binance_testnet",
                "main_order_id": main_order['id'],
                "protection_orders": protection_orders,
                "asset": symbol
            }

        except Exception as e:
            import traceback
            logger.error(f"💥 Error crítico en ejecución: {str(e)}")
            logger.error(traceback.format_exc())
            return {"status": "error", "message": str(e)}
        finally:
            # En sync no hay await client.close()
            pass

if __name__ == "__main__":
    executor = BinanceExecutor(dry_run=True)
    print("Módulo BinanceExecutor inicializado (Modo Sync/Hilos).")
