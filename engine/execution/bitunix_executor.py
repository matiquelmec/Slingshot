import os
import hashlib
import time
import uuid
import httpx
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_DOWN
from engine.api.config import settings

logger = logging.getLogger("BitunixExecutor")

class BitunixExecutor:
    """
    Motor de Ejecución para Bitunix Futures.
    Realiza firmas de doble SHA-256 e interactúa mediante REST API directa.
    """
    
    def __init__(self, dry_run: bool = False):
        self.api_key = settings.BITUNIX_API_KEY
        self.secret_key = settings.BITUNIX_SECRET_KEY
        self.dry_run = dry_run
        self.base_url = "https://fapi.bitunix.com"
        
        if not self.dry_run and (not self.api_key or not self.secret_key):
            logger.error("❌ BITUNIX_API_KEY o SECRET_KEY no encontrados. Cambiando a DRY_RUN.")
            self.dry_run = True
            
        logger.info(f"🛡️ [BITUNIX] Executor inicializado (Dry Run: {self.dry_run})")

    def _generate_signature(self, nonce: str, timestamp: str, query_params: str, body: str) -> str:
        """Genera la firma utilizando el algoritmo de doble SHA-256 de Bitunix."""
        digest_input = f"{nonce}{timestamp}{self.api_key}{query_params}{body}"
        digest = hashlib.sha256(digest_input.encode('utf-8')).hexdigest()
        signature = hashlib.sha256((digest + self.secret_key).encode('utf-8')).hexdigest()
        return signature

    async def _request(self, method: str, path: str, params: dict = None, json_body: dict = None) -> dict:
        """Realiza una petición HTTP firmada con doble SHA-256 a la API oficial de Bitunix Futures."""
        if self.dry_run:
            return {"code": 0, "msg": "Success (DRY RUN)", "data": {}}

        url = f"{self.base_url}{path}"
        nonce = uuid.uuid4().hex
        timestamp = str(int(time.time() * 1000))
        
        # Serializar parámetros de consulta ordenados por clave
        query_str = ""
        if params:
            sorted_keys = sorted(params.keys())
            query_str = "".join(f"{k}{params[k]}" for k in sorted_keys)
            
        # Serializar cuerpo de petición sin espacios
        body_str = ""
        if json_body:
            import json
            body_str = json.dumps(json_body, separators=(',', ':'))
            
        sign = self._generate_signature(nonce, timestamp, query_str, body_str)
        
        headers = {
            "api-key": self.api_key,
            "nonce": nonce,
            "timestamp": timestamp,
            "sign": sign,
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if method.upper() == "POST":
                    response = await client.post(url, params=params, content=body_str, headers=headers)
                else:
                    response = await client.get(url, params=params, headers=headers)
                
                response.raise_for_status()
                res_json = response.json()
                
                if res_json.get("code") != 0:
                    logger.error(f"❌ Bitunix API error en {path}: {res_json}")
                return res_json
        except Exception as e:
            logger.error(f"💥 Fallo en conexión HTTP con Bitunix: {e}")
            return {"code": -1, "msg": str(e), "data": {}}

    async def get_ticker_price(self, symbol: str) -> float:
        """Obtiene el último precio de mercado para un símbolo en Bitunix."""
        sym = symbol.replace('/', '').upper()
        try:
            ticker_res = await self._request("GET", "/api/v1/futures/market/tickers", params={"symbols": sym})
            if ticker_res.get("code") == 0 and ticker_res.get("data"):
                data = ticker_res.get("data")
                if isinstance(data, list) and len(data) > 0:
                    return float(data[0].get("lastPrice", 0.0))
        except Exception as e:
            logger.error(f"❌ Error al obtener precio del ticker para {sym}: {e}")
        return 0.0

    async def execute_iceberg_signal(self, signal: Dict[str, Any], num_slices: int = 3, slice_delay_ms: float = 150) -> Dict[str, Any]:
        """
        Adaptive Iceberg Slicing Engine v11.0 Apex.
        Divide órdenes grandes (>2000 USDT) en sub-lotes dinámicos para eliminar el impacto en el libro y el slippage.
        """
        amount_usd = signal.get('position_size', 100)
        symbol = signal.get('asset', 'BTCUSDT').replace('/', '').upper()
        
        if amount_usd <= 2000 or num_slices <= 1:
            return await self.execute_signal(signal)
            
        logger.info(f"🧊 [ICEBERG] Fragmentando posición de ${amount_usd} USDT en {num_slices} sub-lotes para {symbol}...")
        sliced_amount = amount_usd / num_slices
        slice_results = []
        
        for i in range(num_slices):
            slice_signal = signal.copy()
            slice_signal['position_size'] = sliced_amount
            res = await self.execute_signal(slice_signal)
            slice_results.append(res)
            if i < num_slices - 1:
                import asyncio
                await asyncio.sleep(slice_delay_ms / 1000.0)
                
        return {
            "status": "success",
            "execution_type": "ICEBERG",
            "num_slices": num_slices,
            "total_amount_usdt": amount_usd,
            "slices": slice_results
        }

    async def execute_signal(self, signal: Dict[str, Any], fragments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ejecuta una señal colocando la orden principal en Bitunix.
        """
        symbol = signal.get('asset', 'BTCUSDT').replace('/', '').upper()
        side = 'BUY' if 'LONG' in signal.get('type', '') else 'SELL'
        entry_price = signal.get('price') or signal.get('entry_zone_bottom')
        amount_usd = signal.get('position_size', 100)
        leverage = signal.get('leverage', 1)

        if self.dry_run or signal.get("is_test", False):
            logger.info(f"🧪 [BITUNIX DRY RUN] Orden {side} para {symbol} (Vía BitunixExecutor) [Test Signal: {signal.get('is_test', False)}]")
            return {
                "status": "success",
                "exchange": "bitunix_futures",
                "main_order_id": f"dry_bitunix_order_{uuid.uuid4().hex[:8]}",
                "protection_orders": [f"dry_bitunix_sl_{uuid.uuid4().hex[:8]}"],
                "amount": amount_usd / entry_price,
                "entry_price": entry_price,
                "asset": symbol
            }

        try:
            # 1. Configurar apalancamiento en Bitunix
            await self._request("POST", "/api/v1/futures/account/change_leverage", json_body={
                "symbol": symbol,
                "leverage": int(leverage),
                "marginCoin": "USDT"
            })

            # 2. Calcular cantidad nominal ajustada (Margen * Apalancamiento)
            nominal_usd = amount_usd * leverage
            qty = str(round(nominal_usd / entry_price, 4))
            
            logger.info(f"🚀 [BITUNIX] Enviando orden {side} para {symbol} de {qty} unidades (Margen: ${amount_usd} USDT @ {leverage}x).")
            
            # 3. Colocar orden de mercado principal con SL integrado para máxima seguridad
            order_payload = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "tradeSide": "OPEN",
                "orderType": "MARKET"
            }
            
            stop_loss = signal.get("stop_loss")
            if stop_loss:
                order_payload["slPrice"] = str(round(float(stop_loss), 2))
                order_payload["slStopType"] = "LAST_PRICE"
                order_payload["slOrderType"] = "MARKET"
            
            main_order = await self._request("POST", "/api/v1/futures/trade/place_order", json_body=order_payload)
            
            if main_order.get("code") == 0:
                order_id = main_order.get("data", {}).get("orderId", f"bitunix_order_{uuid.uuid4().hex[:8]}")
                logger.info(f"✅ [BITUNIX] Orden principal colocada con éxito. ID: {order_id}")
                
                # 4. Colocar órdenes de límite Take Profit fragmentadas (60% / 20% / 20%)
                protection_ids = []
                close_side = "SELL" if side == "BUY" else "BUY"
                qty_float = float(qty)
                
                tp1 = signal.get("tp1")
                tp2 = signal.get("tp2")
                tp3 = signal.get("tp3") or signal.get("take_profit_3r")
                
                if tp1 and tp2 and tp3:
                    # Determinar precisión de cantidad y precio dinámicamente
                    qty_decimals = 0 if qty_float >= 100 or "." not in str(qty) else 2
                    price_decimals = 4 if float(entry_price) < 10.0 else 2

                    f1 = round(qty_float * 0.60, qty_decimals)
                    f2 = round(qty_float * 0.20, qty_decimals)
                    f3 = round(qty_float - f1 - f2, qty_decimals)
                    if qty_decimals == 0:
                        f1, f2, f3 = int(f1), int(f2), int(f3)

                    tps = [(tp1, f1, "TP1"), (tp2, f2, "TP2"), (tp3, f3, "TP3")]
                    for tp_price, tp_qty, label in tps:
                        if tp_qty <= 0:
                            continue
                        tp_payload = {
                            "symbol": symbol,
                            "qty": str(tp_qty),
                            "price": f"{float(tp_price):.{price_decimals}f}",
                            "side": close_side,
                            "tradeSide": "CLOSE",
                            "orderType": "LIMIT",
                            "effect": "GTC",
                            "positionId": str(order_id)
                        }
                        tp_res = await self._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_payload)
                        if tp_res.get("code") == 0:
                            tp_order_id = tp_res.get("data", {}).get("orderId")
                            logger.info(f"🎯 [BITUNIX] Orden de {label} límite colocada a ${tp_price} | ID: {tp_order_id}")
                            protection_ids.append(tp_order_id)
                        else:
                            logger.error(f"❌ [BITUNIX] Error al colocar {label}: {tp_res.get('msg')}")
                
                return {
                    "status": "success",
                    "exchange": "bitunix_futures",
                    "main_order_id": order_id,
                    "protection_orders": protection_ids,
                    "amount": qty_float,
                    "entry_price": entry_price,
                    "asset": symbol
                }
            else:
                return {"status": "error", "message": main_order.get("msg", "Unknown error")}

        except Exception as e:
            logger.error(f"❌ [BITUNIX] Error crítico en execute_signal: {e}")
            return {"status": "error", "message": str(e)}

    async def place_limit_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Coloca una orden LÍMITE (Limit Order) pendiente en Bitunix con SL integrado.
        Usado por el Escáner SMC para programar entradas pasivas OTE (61.8% / Golden Pocket).
        """
        symbol = signal.get('asset', signal.get('symbol', 'BTCUSDT')).replace('/', '').upper()
        side = 'BUY' if 'LONG' in str(signal.get('type', signal.get('direction', 'LONG'))).upper() else 'SELL'
        entry_price = float(signal.get('price', 0.0))
        stop_loss = float(signal.get('stop_loss', 0.0))
        amount_usd = float(signal.get('position_size', signal.get('position_size_usdt', 10.0)))
        leverage = int(signal.get('leverage', 20))

        if self.dry_run or signal.get("is_test", False):
            logger.info(f"🧪 [BITUNIX DRY RUN] Orden LÍMITE {side} para {symbol} @ ${entry_price:.2f}")
            return {"status": "success", "order_id": f"dry_limit_{uuid.uuid4().hex[:8]}"}

        if entry_price <= 0:
            return {"status": "error", "message": "Invalid entry price"}

        try:
            # 1. Configurar apalancamiento
            await self._request("POST", "/api/v1/futures/account/change_leverage", json_body={
                "symbol": symbol,
                "leverage": leverage,
                "marginCoin": "USDT"
            })

            # 2. Calcular cantidad nominal ajustada
            nominal_usd = amount_usd * leverage
            decimals = 4 if entry_price < 10.0 else 2
            qty = str(round(nominal_usd / entry_price, 4))
            price_str = f"{entry_price:.{decimals}f}"

            # 3. Payload orden límite en Bitunix
            order_payload = {
                "symbol": symbol,
                "qty": qty,
                "price": price_str,
                "side": side,
                "tradeSide": "OPEN",
                "orderType": "LIMIT",
                "effect": "GTC"
            }
            if stop_loss > 0:
                order_payload["slPrice"] = f"{stop_loss:.{decimals}f}"
                order_payload["slStopType"] = "LAST_PRICE"
                order_payload["slOrderType"] = "MARKET"

            res = await self._request("POST", "/api/v1/futures/trade/place_order", json_body=order_payload)
            if res.get("code") == 0 and res.get("data"):
                order_id = res["data"].get("orderId")
                logger.info(f"🎯 [BITUNIX AUTO-LIMIT] Orden Límite {side} colocada para {symbol} ({qty} units @ ${price_str}) | ID: {order_id}")
                return {"status": "success", "order_id": order_id, "symbol": symbol, "price": entry_price}
            else:
                logger.error(f"❌ [BITUNIX AUTO-LIMIT] Error al colocar orden límite en {symbol}: {res.get('msg')}")
                return {"status": "error", "message": res.get("msg")}
        except Exception as e:
            logger.error(f"💥 [BITUNIX AUTO-LIMIT] Excepción: {e}")
            return {"status": "error", "message": str(e)}

    async def modify_position_tpsl(self, symbol: str, position_id: str, sl_price: Optional[float] = None, tp_price: Optional[float] = None) -> bool:
        """
        Modifica el Stop Loss y/o Take Profit de una posicion abierta en Bitunix.
        Consulta las órdenes TPSL existentes para pasar el orderId correspondiente de forma atómica.
        """
        sym = symbol.replace('/', '').upper()
        if self.dry_run or (position_id and str(position_id).startswith("dry_")):
            logger.info(f"🧪 [BITUNIX DRY RUN] Modificando TP/SL de posicion para {sym} (PosId: {position_id}) -> TP: {tp_price}, SL: {sl_price}")
            return True

        # 1. Obtener y purgar órdenes TPSL desfasadas para evitar desajustes de cantidad
        try:
            res_orders = await self._request("GET", "/api/v1/futures/tpsl/get_pending_orders", params={"symbol": sym})
            existing_orders = res_orders.get("data", []) or []
            if existing_orders and isinstance(existing_orders, list):
                for ord_item in existing_orders:
                    o_id = str(ord_item.get("id"))
                    await self._request("POST", "/api/v1/futures/tpsl/cancel_order", json_body={"orderId": o_id, "symbol": sym})
        except Exception as e:
            logger.debug(f"[BITUNIX] Error purgando TPSL desfasados: {e}")

        decimals = 4 if sl_price and float(sl_price) < 10.0 else 2

        # 2. Colocar orden de posición 100% limpia y sincronizada con el tamaño actual
        payload_new = {
            "positionId": str(position_id),
            "symbol": sym,
        }
        if sl_price is not None:
            payload_new["slPrice"] = f"{float(sl_price):.{decimals}f}"
            payload_new["slStopType"] = "LAST_PRICE"
        if tp_price is not None:
            payload_new["tpPrice"] = f"{float(tp_price):.{decimals}f}"
            payload_new["tpStopType"] = "LAST_PRICE"

        res_plc = await self._request("POST", "/api/v1/futures/tpsl/position/place_order", json_body=payload_new)
        if res_plc.get("code") == 0:
            logger.info(f"✅ [BITUNIX] Stop Loss de posición {sym} fijado y blindado en ${sl_price}")
            return True
        else:
            logger.warning(f"⚠️ [BITUNIX] Error al colocar TPSL de posición {sym}: {res_plc.get('msg')}")
            return False

    async def update_stop_loss(self, symbol: str, old_order_id: str, new_stop_price: float, amount: float, side: str, position_id: Optional[str] = None, tp_price: Optional[float] = None) -> Optional[str]:
        """
        Actualiza el Stop Loss para una posicion abierta en Bitunix (Breakeven / Trailing).
        Si se provee position_id, modifica el TP/SL de la posicion entera de forma nativa en Bitunix.
        """
        sym = symbol.replace('/', '').upper()
        if self.dry_run or (position_id and str(position_id).startswith("dry_")):
            logger.info(f"🧪 [BITUNIX DRY RUN] Actualizando SL para {sym} (PosId: {position_id}) -> Nuevo SL en {new_stop_price}")
            return f"dry_bitunix_sl_{uuid.uuid4().hex[:8]}"

        try:
            if position_id:
                logger.info(f"🛡️ [BITUNIX] Actualizando TP/SL de posicion de forma dinámica (PosId: {position_id}) -> Nuevo SL: {new_stop_price}, TP: {tp_price}")
                success = await self.modify_position_tpsl(symbol=sym, position_id=position_id, sl_price=new_stop_price, tp_price=tp_price)
                return "position_tpsl_updated" if success else None

            # 1. Cancelar orden antigua si se provee
            if old_order_id:
                await self._request("POST", "/api/v1/futures/trade/cancel_orders", json_body={
                    "symbol": sym,
                    "orderList": [{"orderId": old_order_id}]
                })
                logger.info(f"🛡️ [BITUNIX] SL antiguo cancelado: {old_order_id}")

            # 2. Colocar nueva orden de Stop Loss
            sl_payload = {
                "symbol": sym,
                "qty": str(round(amount, 4)),
                "side": side.upper(),
                "tradeSide": "CLOSE",
                "orderType": "MARKET",
                "triggerPrice": str(new_stop_price)
            }
            
            new_order = await self._request("POST", "/api/v1/futures/trade/place_order", json_body=sl_payload)
            if new_order.get("code") == 0:
                new_id = new_order.get("data", {}).get("orderId")
                logger.info(f"🛡️ [BITUNIX] Nuevo SL colocado en {new_stop_price} | ID: {new_id}")
                return new_id
            return None
        except Exception as e:
            logger.error(f"❌ [BITUNIX] Error al actualizar Stop Loss: {e}")
            return None

    async def scale_position(self, symbol: str, side: str, amount_usd: float, leverage: int) -> bool:
        """
        Ejecuta una orden de mercado para escalar o añadir contratos (Averaging Up).
        """
        sym = symbol.replace('/', '').upper()
        if self.dry_run:
            logger.info(f"🧪 [BITUNIX DRY RUN] Escalando posición {sym} ({side.upper()}) con ${amount_usd} nominal.")
            return True

        try:
            # 1. Necesitamos el precio de mercado aproximado para calcular la cantidad
            # Podemos consultar el endpoint público de tickers
            ticker_res = await self._request("GET", "/api/v1/futures/market/ticker", params={"symbol": sym})
            if ticker_res.get("code") != 0 or not ticker_res.get("data"):
                logger.error("❌ No se pudo obtener el precio en vivo de Bitunix para escalar.")
                return False
                
            price = float(ticker_res["data"].get("lastPrice", 0))
            if price <= 0:
                return False
                
            qty = str(round(amount_usd / price, 4))
            
            logger.info(f"🚀 [BITUNIX] Escalando posición en {sym}: +{qty} unidades.")
            
            order_payload = {
                "symbol": sym,
                "qty": qty,
                "side": side.upper(),
                "tradeSide": "OPEN",
                "orderType": "MARKET"
            }
            
            res = await self._request("POST", "/api/v1/futures/trade/place_order", json_body=order_payload)
            return res.get("code") == 0
        except Exception as e:
            logger.error(f"❌ [BITUNIX] Error escalando posición: {e}")
            return False

    async def place_position_tpsl(self, symbol: str, position_id: str, sl_price: Optional[float] = None, tp_price: Optional[float] = None) -> Optional[str]:
        """
        Establece Stop Loss y/o Take Profit para una posicion abierta en Bitunix.
        Usa el endpoint POST /api/v1/futures/tpsl/position/place_order.
        """
        sym = symbol.replace('/', '').upper()
        if self.dry_run or (position_id and str(position_id).startswith("dry_")):
            logger.info(f"🧪 [BITUNIX DRY RUN] Colocando TP/SL de posicion para {sym} (PosId: {position_id}) -> TP: {tp_price}, SL: {sl_price}")
            return f"dry_tpsl_{uuid.uuid4().hex[:8]}"

        payload = {
            "symbol": sym,
            "positionId": str(position_id)
        }
        if sl_price:
            payload["slPrice"] = str(round(float(sl_price), 2))
            payload["slStopType"] = "LAST_PRICE"
        if tp_price:
            payload["tpPrice"] = str(round(float(tp_price), 2))
            payload["tpStopType"] = "LAST_PRICE"

        res = await self._request("POST", "/api/v1/futures/tpsl/position/place_order", json_body=payload)
        if res.get("code") == 0:
            order_id = res.get("data", {}).get("orderId")
            logger.info(f"✅ [BITUNIX] TP/SL de posicion colocado con exito. Order ID: {order_id}")
            return order_id
        else:
            logger.error(f"❌ [BITUNIX] Error al colocar TP/SL de posicion: {res.get('msg')}")
            return None

    async def get_pending_positions(self) -> List[Dict[str, Any]]:
        """Obtiene las posiciones abiertas actuales desde Bitunix."""
        try:
            res = await self._request("GET", "/api/v1/futures/position/get_pending_positions")
            if res.get("code") == 0 and isinstance(res.get("data"), list):
                return res["data"]
            else:
                logger.error(f"❌ Error al obtener posiciones de Bitunix: {res.get('msg')}")
        except Exception as e:
            logger.error(f"❌ Error al conectar con endpoint de posiciones: {e}")
        return []

    async def get_pending_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene las órdenes límite pendientes activas en Bitunix."""
        if self.dry_run:
            return []
        try:
            params = {}
            if symbol:
                params["symbol"] = symbol.replace('/', '').upper()
            res = await self._request("GET", "/api/v1/futures/trade/get_pending_orders", params=params)
            if res.get("code") == 0 and isinstance(res.get("data"), list):
                return res["data"]
        except Exception as e:
            logger.debug(f"[BITUNIX] No se pudieron obtener órdenes pendientes: {e}")
        return []

    async def get_balance(self) -> float:
        """Obtiene el balance disponible real en USDT de la cuenta."""
        if self.dry_run:
            return 1000.0
        try:
            res = await self._request("GET", "/api/v1/futures/account", params={"marginCoin": "USDT"})
            if res.get("code") == 0 and res.get("data"):
                data = res.get("data")
                if isinstance(data, list) and len(data) > 0:
                    return float(data[0].get("available", 1000.0))
                elif isinstance(data, dict):
                    return float(data.get("available", 1000.0))
        except Exception as e:
            logger.error(f"❌ Error al obtener balance de Bitunix: {e}")
        return 1000.0

