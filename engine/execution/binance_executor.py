import os
import asyncio
import logging
import ccxt  # [FIX v6.6.17] Sync version for Windows stability
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, List, Optional
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

    async def execute_signal(self, signal: Dict[str, Any], fragments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
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
            
            # 4. Órdenes de Protección (Soporte Multi-TP Delta 60/20/20)
            sl_price = signal.get('stop_loss')
            protection_orders = []
            
            # 4.1. Stop Loss (Único para toda la posición)
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

            # 4.2. Take Profits Fragmentados (v10.2.0 Apex)
            if not fragments:
                from engine.execution.delta_executor import DeltaOrchestrator
                fragments = DeltaOrchestrator.fragment_order(signal)
            
            tp_side = 'sell' if side == 'buy' else 'buy'
            for frag in fragments:
                tp_price = frag.get("tp_price")
                if not tp_price: continue
                
                # Calcular cantidad del tramo
                raw_frag_amount = (frag["volume_usdt"] * leverage) / current_price
                frag_amount = float((Decimal(str(raw_frag_amount)) / Decimal(str(min_amount))).quantize(Decimal('1'), rounding=ROUND_DOWN) * Decimal(str(min_amount)))
                
                if frag_amount <= 0: continue

                try:
                    tp_order = await asyncio.to_thread(
                        self.client.create_order,
                        symbol=symbol,
                        type='TAKE_PROFIT_MARKET',
                        side=tp_side,
                        amount=frag_amount,
                        params={
                            'stopPrice': self.client.price_to_precision(symbol, tp_price),
                            'reduceOnly': True
                        }
                    )
                    protection_orders.append(tp_order['id'])
                    logger.info(f"🎯 TP Fragmentado ({frag['id']}) colocado en {tp_price} | Vol: {frag_amount}")
                except Exception as tp_err:
                    logger.error(f"⚠️ Error colocando TP {frag['id']}: {tp_err}")

            return {
                "status": "success",
                "exchange": "binance_futures",
                "main_order_id": main_order['id'],
                "protection_orders": protection_orders,
                "amount": amount,
                "entry_price": current_price,
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

    async def update_stop_loss(self, symbol: str, old_order_id: str, new_stop_price: float, amount: float, side: str) -> Optional[str]:
        """
        Actualiza un Stop Loss cancelando el anterior y colocando uno nuevo.
        """
        if self.dry_run:
            logger.info(f"🧪 [DRY RUN] Actualizando SL para {symbol}: Cancelar {old_order_id} -> Nuevo SL en {new_stop_price}")
            return "dry_run_sl_id"

        await self._load_markets()
        if 'USDT' not in symbol: symbol += 'USDT'
        
        try:
            # 1. Cancelar orden antigua si existe
            if old_order_id:
                try:
                    await asyncio.to_thread(self.client.cancel_order, id=old_order_id, symbol=symbol)
                    logger.info(f"🛡️ SL antiguo {old_order_id} cancelado para {symbol}")
                except Exception as cancel_err:
                    logger.warning(f"⚠️ No se pudo cancelar SL {old_order_id} (puede estar cerrado/inexistente): {cancel_err}")
            
            # 2. Crear nueva orden de Stop Loss
            sl_order = await asyncio.to_thread(
                self.client.create_order,
                symbol=symbol,
                type='STOP_MARKET',
                side=side,
                amount=amount,
                params={
                    'stopPrice': self.client.price_to_precision(symbol, new_stop_price),
                    'reduceOnly': True
                }
            )
            logger.info(f"🛡️ Nuevo SL colocado en {new_stop_price} para {symbol}. Nuevo Order ID: {sl_order['id']}")
            return sl_order['id']
        except Exception as e:
            logger.error(f"❌ Error actualizando Stop Loss para {symbol}: {e}")
            return None

    async def scale_position(self, symbol: str, side: str, amount_usd: float, leverage: int) -> bool:
        """
        Ejecuta una orden de mercado para añadir contratos (Averaging Up / Escalado).
        """
        if self.dry_run:
            logger.info(f"🧪 [DRY RUN] Escalando posición {symbol} ({side.upper()}) con ${amount_usd} de volumen nominal.")
            return True

        await self._load_markets()
        if 'USDT' not in symbol: symbol += 'USDT'
        
        try:
            # 1. Obtener precio actual para calcular contratos
            ticker = await asyncio.to_thread(self.client.fetch_ticker, symbol)
            current_price = ticker['last']
            
            raw_amount = (amount_usd * leverage) / current_price
            market = self.client.market(symbol)
            min_amount = market['limits']['amount']['min']
            amount = float((Decimal(str(raw_amount)) / Decimal(str(min_amount))).quantize(Decimal('1'), rounding=ROUND_DOWN) * Decimal(str(min_amount)))
            
            if amount <= 0:
                logger.warning(f"⚠️ Cantidad de escalado muy pequeña para {symbol}: {raw_amount}")
                return False

            logger.info(f"🚀 Enviando orden de escalado de mercado {side.upper()} para {symbol}: {amount} unidades")
            
            scale_order = await asyncio.to_thread(
                self.client.create_order,
                symbol=symbol,
                type='market',
                side=side,
                amount=amount
            )
            logger.info(f"✅ Escalado exitoso en {symbol}. Order ID: {scale_order['id']}")
            return True
        except Exception as e:
            logger.error(f"❌ Error ejecutando escalado para {symbol}: {e}")
            return False

if __name__ == "__main__":
    executor = BinanceExecutor(dry_run=True)
    print("Módulo BinanceExecutor inicializado (Modo Sync/Hilos).")
