import os
import asyncio
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
    # Caché compartida de offset de reloj del servidor Bitunix para todas las cuentas
    _shared_server_time_offset_ms: int = 0
    _shared_last_time_sync: float = 0.0
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        account_id: str = "primary",
        account_label: str = "Cuenta Principal",
        dry_run: bool = False
    ):
        self.account_id = account_id
        self.account_label = account_label
        self.api_key = api_key or settings.BITUNIX_API_KEY
        self.secret_key = secret_key or settings.BITUNIX_SECRET_KEY
        self.dry_run = dry_run
        self.base_url = "https://fapi.bitunix.com"
        self._server_time_offset_ms = BitunixExecutor._shared_server_time_offset_ms
        self._last_time_sync = BitunixExecutor._shared_last_time_sync
        self._last_verified_balance = 0.0
        self._last_balance_ts = 0.0
        
        if not self.dry_run and (not self.api_key or not self.secret_key):
            logger.error(f"❌ [{self.account_label}] BITUNIX_API_KEY o SECRET_KEY no encontrados. Cambiando a DRY_RUN.")
            self.dry_run = True
            
        logger.info(f"🛡️ [BITUNIX] Executor '{self.account_label}' inicializado (Dry Run: {self.dry_run})")

    async def sync_server_time(self) -> int:
        """
        [SOP-11 CLOCK DRIFT CALIBRATOR]
        Sincroniza la hora local con la hora oficial del servidor de Bitunix Futures.
        Evita rechazos por Timestamp Expired (100007) si el reloj de Windows está desfasado.
        Reutiliza la calibración compartida si se ejecutó hace menos de 60 segundos.
        """
        now = time.time()
        if (now - BitunixExecutor._shared_last_time_sync) < 60.0 and BitunixExecutor._shared_last_time_sync > 0:
            self._server_time_offset_ms = BitunixExecutor._shared_server_time_offset_ms
            return self._server_time_offset_ms

        try:
            url = f"{self.base_url}/api/v1/futures/market/time"
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    server_time = 0
                    if isinstance(data.get("data"), (int, float)):
                        server_time = int(data["data"])
                    elif isinstance(data.get("data"), dict) and "time" in data["data"]:
                        server_time = int(data["data"]["time"])
                    
                    if server_time > 0:
                        local_time = int(time.time() * 1000)
                        offset = server_time - local_time
                        BitunixExecutor._shared_server_time_offset_ms = offset
                        BitunixExecutor._shared_last_time_sync = now
                        self._server_time_offset_ms = offset
                        self._last_time_sync = now
                        logger.info(f"⏱️ [BITUNIX TIME SYNC] Reloj calibrado con exchange. Offset: {offset:+d}ms")
                        return offset
        except Exception as e:
            logger.debug(f"[BITUNIX TIME SYNC] Error sincronizando hora de Bitunix: {e}")
        return self._server_time_offset_ms

    def get_calibrated_timestamp_ms(self) -> int:
        """Retorna el timestamp actual compensado con el offset del servidor del exchange."""
        offset = BitunixExecutor._shared_server_time_offset_ms or self._server_time_offset_ms
        return int(time.time() * 1000) + offset

    async def get_available_margin_usdt(self) -> float:
        """
        [SOP-10 PRE-FLIGHT MARGIN CHECK & SOP-41 ZERO FAKE FALLBACK]
        Consulta el saldo disponible real en USDT en la cuenta de futuros de Bitunix.
        """
        if self.dry_run:
            return 1000.0
        try:
            res = await self._request("GET", "/api/v1/futures/account", params={"marginCoin": "USDT"})
            if res.get("code") == 0 and isinstance(res.get("data"), dict):
                acc = res["data"]
                avail = float(acc.get("available") or acc.get("availableMargin") or acc.get("availableBalance") or acc.get("marginBalance") or 0.0)
                if avail > 0:
                    self._last_verified_balance = avail
                    self._last_balance_ts = time.time()
                    return avail
        except Exception as e:
            logger.debug(f"[BITUNIX MARGIN] Error consultando balance de margen: {e}")
            
        if self._last_verified_balance > 0 and (time.time() - self._last_balance_ts) < 120.0:
            logger.info(f"🛡️ [BITUNIX MARGIN] Usando último saldo verificado en caché: ${self._last_verified_balance:.2f} USDT")
            return self._last_verified_balance
            
        return 0.0

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
        
        # Auto-calibrar reloj si han pasado más de 15 minutos desde la última sincronización
        if not self.dry_run and self._last_time_sync > 0 and (time.time() - self._last_time_sync > 900.0):
            asyncio.create_task(self.sync_server_time())

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
            
        max_retries = 3
        last_err = None

        for attempt in range(1, max_retries + 1):
            try:
                # Regenerar timestamp compensado y nonce por intento
                curr_ts = str(self.get_calibrated_timestamp_ms())
                curr_nonce = uuid.uuid4().hex
                curr_sign = self._generate_signature(curr_nonce, curr_ts, query_str, body_str)
                curr_headers = {
                    "api-key": self.api_key,
                    "nonce": curr_nonce,
                    "timestamp": curr_ts,
                    "sign": curr_sign,
                    "Content-Type": "application/json"
                }

                async with httpx.AsyncClient(timeout=10.0) as client:
                    if method.upper() == "POST":
                        response = await client.post(url, params=params, content=body_str, headers=curr_headers)
                    else:
                        response = await client.get(url, params=params, headers=curr_headers)

                    if response.status_code == 429 or response.status_code >= 500:
                        raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)

                    response.raise_for_status()
                    res_json = response.json()

                    if res_json.get("code") != 0:
                        # Errores específicos de exchange (ej. 100007, 10002) no requieren retry infinito
                        logger.error(f"❌ Bitunix API error en {path}: {res_json}")
                    return res_json

            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    import random
                    sleep_time = (0.5 * (2 ** (attempt - 1))) + random.uniform(0.1, 0.3)
                    logger.debug(f"[BITUNIX RETRY] Reintento {attempt}/{max_retries} para {path} en {sleep_time:.2f}s debido a: {e}")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.error(f"💥 Fallo definitivo en conexión HTTP con Bitunix tras {max_retries} intentos: {e}")

        return {"code": -1, "msg": str(last_err), "data": {}}

    async def get_symbol_precision(self, symbol: str) -> tuple[int, int]:
        """
        Devuelve (qty_precision, price_precision) consultando la API de Bitunix o desde la caché en memoria.
        """
        sym = symbol.replace('/', '').upper()
        if not hasattr(self, "_symbol_precisions"):
            self._symbol_precisions = {}
            
        if sym in self._symbol_precisions:
            return self._symbol_precisions[sym]
            
        try:
            r = await self._request("GET", "/api/v1/futures/market/trading_pairs")
            if r.get("code") == 0 and isinstance(r.get("data"), list):
                for item in r["data"]:
                    s = item.get("symbol")
                    bp = int(item.get("basePrecision", 2))
                    qp = int(item.get("quotePrecision", 2))
                    self._symbol_precisions[s] = (bp, qp)
                    
            if sym in self._symbol_precisions:
                return self._symbol_precisions[sym]
        except Exception as e:
            logger.debug(f"[BITUNIX] Error cargando precisiones de mercado: {e}")
            
        # Fallback inteligente con soporte nativo de micro-tokens
        fallback_map = {
            "BTCUSDT": (4, 1), "ETHUSDT": (3, 2), "SOLUSDT": (2, 2), "PAXGUSDT": (3, 2),
            "AVAXUSDT": (2, 2), "LINKUSDT": (2, 2), "NEARUSDT": (1, 3), "RENDERUSDT": (1, 3),
            "SUIUSDT": (1, 4), "INJUSDT": (2, 3), "FETUSDT": (0, 4), "ATOMUSDT": (2, 3),
            "TIAUSDT": (1, 3), "XRPUSDT": (0, 4), "TRUMPUSDT": (2, 3), "AKEUSDT": (0, 6)
        }
        if sym in fallback_map:
            return fallback_map[sym]
            
        # Para tokens micro desconocidos (< $0.10), usar 6 decimales de precio
        return (0, 6) if any(m in sym for m in ["AKE", "PEPE", "SHIB", "FLOKI", "BONK"]) else (2, 2)

    async def get_ticker_price(self, symbol: str) -> float:
        """Obtiene el último precio de mercado para un símbolo en Bitunix (con fallback institucional)."""
        sym = symbol.replace('/', '').upper()
        try:
            ticker_res = await self._request("GET", "/api/v1/futures/market/tickers", params={"symbols": sym})
            if ticker_res.get("code") == 0 and ticker_res.get("data"):
                data = ticker_res.get("data")
                if isinstance(data, list) and len(data) > 0:
                    p = float(data[0].get("lastPrice", 0.0))
                    if p > 0: return p
            # Fallback 1: ticker individual Bitunix
            ticker_single = await self._request("GET", "/api/v1/futures/market/ticker", params={"symbol": sym})
            if ticker_single.get("code") == 0 and ticker_single.get("data"):
                p = float(ticker_single["data"].get("lastPrice", 0.0))
                if p > 0: return p
        except Exception as e:
            logger.debug(f"⚠️ Error consultando precio Bitunix para {sym}: {e}")
        
        # Fallback 2: Binance market data para cero latencia
        try:
            from engine.indicators.data_utils import fetch_binance_history
            candles = await fetch_binance_history(sym, "1m", limit=2)
            if candles:
                return float(candles[-1]["data"]["close"])
        except Exception:
            pass
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

            # 2. Calcular cantidad nominal ajustada y precisión dinámica exacta
            qty_decimals, price_decimals = await self.get_symbol_precision(symbol)
            
            # Prioridad 1: Si la señal ya trae exact_qty calculada bajo SOP-41, respetarla
            if signal.get("exact_qty") and float(signal.get("exact_qty")) > 0:
                raw_qty = float(signal.get("exact_qty"))
            else:
                nominal_usd = amount_usd * leverage
                raw_qty = nominal_usd / entry_price

            # ── PROTOCOLO SOP-42: PRE-FLIGHT RISK HARD-CLAMP (CIRCUIT BREAKER) ──
            stop_loss = signal.get("stop_loss")
            if stop_loss and float(stop_loss) > 0 and entry_price and float(entry_price) > 0:
                sl_dist = abs(float(entry_price) - float(stop_loss))
                projected_loss = raw_qty * sl_dist
                
                verified_bal = self._last_verified_balance if self._last_verified_balance > 0 else await self.get_available_margin_usdt()
                if verified_bal > 0:
                    max_loss_allowed = verified_bal * 0.026 # Tolerancia máxima 2.6% ($2.13 USD en $82 USD)
                    if projected_loss > max_loss_allowed:
                        safe_qty = (verified_bal * 0.025) / sl_dist
                        logger.warning(f"🛑 [SOP-42 HARD-CLAMP] Orden sobredimensionada en {symbol}! Pérdida proyectada: ${projected_loss:.2f} USDT > Límite: ${max_loss_allowed:.2f} USDT. Clampando Qty de {raw_qty:.4f} -> {safe_qty:.4f}")
                        raw_qty = safe_qty

            qty = str(int(raw_qty)) if qty_decimals == 0 else f"{raw_qty:.{qty_decimals}f}"
            if float(qty) <= 0:
                logger.warning(f"🛑 [SOP-42] Cantidad calculada ({qty}) es 0 o menor al mínimo permitido para {symbol}. Cancelando orden.")
                return {"status": "rejected", "reason": "SOP-42: Qty below minimum exchange limit"}
            
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
            if stop_loss and float(stop_loss) > 0:
                order_payload["slPrice"] = f"{float(stop_loss):.{price_decimals}f}"
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
                    # [SOP-21] Respetar la precisión dinámica exacta del símbolo (ej. 6 decimales en micro-tokens)
                    qty_decimals, price_decimals = await self.get_symbol_precision(symbol)

                    if qty_decimals == 0:
                        f1 = int(round(qty_float * 0.60))
                        f2 = int(round(qty_float * 0.20))
                        f3 = int(round(qty_float - f1 - f2))
                    else:
                        f1 = round(qty_float * 0.60, qty_decimals)
                        f2 = round(qty_float * 0.20, qty_decimals)
                        f3 = round(qty_float - f1 - f2, qty_decimals)

                    tps = [(tp1, f1, "TP1"), (tp2, f2, "TP2"), (tp3, f3, "TP3")]
                    for tp_price, tp_qty, label in tps:
                        if tp_qty <= 0:
                            continue
                        formatted_tp_qty = str(int(tp_qty) if qty_decimals == 0 else f"{tp_qty:.{qty_decimals}f}")
                        formatted_tp_price = f"{float(tp_price):.{price_decimals}f}"
                        tp_payload = {
                            "symbol": symbol,
                            "qty": formatted_tp_qty,
                            "price": formatted_tp_price,
                            "side": close_side,
                            "tradeSide": "CLOSE",
                            "orderType": "LIMIT",
                            "effect": "GTC"
                        }
                        # Intentar primero orden límite de cierre directa
                        tp_res = await self._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_payload)
                        
                        # Fallback resiliente: si Bitunix exige positionId o falla, reintentar con positionId
                        if tp_res.get("code") != 0 and order_id:
                            tp_payload["positionId"] = str(order_id)
                            tp_res = await self._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_payload)

                        if tp_res.get("code") == 0:
                            tp_order_id = tp_res.get("data", {}).get("orderId")
                            logger.info(f"🎯 [BITUNIX] Orden de {label} límite colocada a ${formatted_tp_price} ({formatted_tp_qty} u) | ID: {tp_order_id}")
                            protection_ids.append(tp_order_id)
                        else:
                            logger.error(f"❌ [BITUNIX] Error al colocar {label} a ${formatted_tp_price}: {tp_res.get('msg')}")
                
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
        raw_side = str(signal.get('signal_type', signal.get('direction', signal.get('type', 'LONG')))).upper()
        side = 'BUY' if 'LONG' in raw_side or 'BUY' in raw_side else 'SELL'
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

            # 2. Calcular cantidad nominal ajustada y precisión dinámica exacta de Bitunix
            qty_decimals, price_decimals = await self.get_symbol_precision(symbol)
            
            # Prioridad 1: Si la señal ya trae exact_qty calculada bajo SOP-41, respetarla
            if signal.get("exact_qty") and float(signal.get("exact_qty")) > 0:
                raw_qty = float(signal.get("exact_qty"))
            else:
                nominal_usd = amount_usd * leverage
                raw_qty = nominal_usd / entry_price

            # ── PROTOCOLO SOP-42: PRE-FLIGHT RISK HARD-CLAMP (CIRCUIT BREAKER) ──
            if stop_loss > 0 and entry_price > 0:
                sl_dist = abs(entry_price - stop_loss)
                projected_loss = raw_qty * sl_dist
                
                verified_bal = self._last_verified_balance if self._last_verified_balance > 0 else await self.get_available_margin_usdt()
                if verified_bal > 0:
                    max_loss_allowed = verified_bal * 0.026 # Tolerancia máxima 2.6% ($2.13 USD en $82 USD)
                    if projected_loss > max_loss_allowed:
                        safe_qty = (verified_bal * 0.025) / sl_dist
                        logger.warning(f"🛑 [SOP-42 LIMIT HARD-CLAMP] Orden límite sobredimensionada en {symbol}! Pérdida proyectada: ${projected_loss:.2f} USDT > Límite: ${max_loss_allowed:.2f} USDT. Clampando Qty de {raw_qty:.4f} -> {safe_qty:.4f}")
                        raw_qty = safe_qty

            qty = str(int(raw_qty)) if qty_decimals == 0 else f"{raw_qty:.{qty_decimals}f}"
            if float(qty) <= 0:
                logger.warning(f"🛑 [SOP-42 LIMIT] Cantidad calculada ({qty}) es 0 o menor al mínimo permitido para {symbol}. Cancelando orden.")
                return {"status": "rejected", "reason": "SOP-42: Qty below minimum exchange limit"}
            
            price_str = f"{entry_price:.{price_decimals}f}"

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
                order_payload["slPrice"] = f"{stop_loss:.{price_decimals}f}"
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

    async def modify_position_tpsl(self, symbol: str, position_id: Optional[str] = None, sl_price: Optional[float] = None, tp_price: Optional[float] = None) -> bool:
        """
        Modifica el Stop Loss y/o Take Profit de una posicion abierta en Bitunix.
        Si position_id no es un ID numérico real, lo resuelve automáticamente consultando get_pending_positions.
        """
        sym = symbol.replace('/', '').upper()
        if self.dry_run or (position_id and str(position_id).startswith("dry_")):
            logger.info(f"🧪 [BITUNIX DRY RUN] Modificando TP/SL de posicion para {sym} (PosId: {position_id}) -> TP: {tp_price}, SL: {sl_price}")
            return True

        # Resolver position_id real desde las posiciones abiertas si no es válido
        if not position_id or not str(position_id).isdigit():
            try:
                real_positions = await self.get_pending_positions()
                for p in real_positions:
                    if p.get("symbol") == sym:
                        position_id = str(p.get("positionId") or p.get("id"))
                        break
            except Exception as e:
                logger.debug(f"[BITUNIX] Error resolviendo positionId para {sym}: {e}")

        if not position_id or not str(position_id).isdigit():
            logger.debug(f"[BITUNIX] No se encontró posición abierta real en Bitunix para {sym}")
            return False

        order_id = await self.place_position_tpsl(symbol=sym, position_id=position_id, sl_price=sl_price, tp_price=tp_price)
        return order_id is not None

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
        Verifica primero si ya existe una orden TPSL activa para evitar el error de duplicado ('Network Error').
        """
        sym = symbol.replace('/', '').upper()
        if self.dry_run or (position_id and str(position_id).startswith("dry_")):
            logger.info(f"🧪 [BITUNIX DRY RUN] Colocando TP/SL de posicion para {sym} (PosId: {position_id}) -> TP: {tp_price}, SL: {sl_price}")
            return f"dry_tpsl_{uuid.uuid4().hex[:8]}"

        _, decimals = await self.get_symbol_precision(sym)
        formatted_sl = f"{float(sl_price):.{decimals}f}" if sl_price is not None else None
        formatted_tp = f"{float(tp_price):.{decimals}f}" if tp_price is not None else None

        # 1. Comprobar si ya existe un TPSL para esta posición en Bitunix y aplicar INVARIANZA ABSOLUTA
        try:
            res_orders = await self._request("GET", "/api/v1/futures/tpsl/get_pending_orders", params={"symbol": sym})
            existing_orders = res_orders.get("data", []) or []
            if isinstance(existing_orders, list):
                for eo in existing_orders:
                    raw_sl_str = eo.get("slPrice") or eo.get("triggerPrice") or ""
                    eo_id = str(eo.get("id") or eo.get("orderId") or "")
                    
                    if raw_sl_str and formatted_sl:
                        try:
                            existing_sl_val = float(raw_sl_str)
                            new_sl_val = float(formatted_sl)
                            
                            # Si ya tiene exactamente el mismo SL configurado, no reenviar
                            if abs(existing_sl_val - new_sl_val) < 0.0001:
                                logger.info(f"🛡️ [BITUNIX] {sym} ya cuenta con Stop Loss activo blindado en ${existing_sl_val:.4f} (ID: {eo_id}).")
                                return eo_id
                                
                            # 🔒 REGLA DE INVARIANZA: Determinar la dirección de la posición
                            # Si no se especifica, consultar la dirección en posiciones abiertas
                            pos_side = "LONG"
                            positions = await self.get_pending_positions()
                            for p in positions:
                                if p.get("symbol") == sym:
                                    pos_side = "LONG" if p.get("side") in ("BUY", "LONG", "1") else "SHORT"
                                    break
                                    
                            # Si es LONG y el nuevo SL es MENOR al existente -> BLOQUEAR INTENTO DE DEGRADACIÓN
                            if pos_side == "LONG" and new_sl_val < existing_sl_val:
                                logger.warning(f"🛑 [INVARIANZA SL] Intento de retroceder SL en LONG para {sym} de ${existing_sl_val:.4f} a ${new_sl_val:.4f} RECHAZADO.")
                                return eo_id
                                
                            # Si es SHORT y el nuevo SL es MAYOR al existente -> BLOQUEAR INTENTO DE DEGRADACIÓN
                            if pos_side == "SHORT" and new_sl_val > existing_sl_val:
                                logger.warning(f"🛑 [INVARIANZA SL] Intento de retroceder SL en SHORT para {sym} de ${existing_sl_val:.4f} a ${new_sl_val:.4f} RECHAZADO.")
                                return eo_id
                        except (ValueError, TypeError):
                            pass
                            
                    # Si el nuevo SL es estrictamente mejor, cancelamos el TPSL previo para colocar el nuevo
                    if eo_id:
                        logger.info(f"🔄 [BITUNIX] Actualizando SL de {sym} (Cancelando TPSL previo {eo_id})...")
                        await self._request("POST", "/api/v1/futures/tpsl/cancel_order", json_body={"orderId": eo_id, "symbol": sym})
        except Exception as e:
            logger.debug(f"[BITUNIX] Error verificando TPSL previos: {e}")

        # 2. Emitir la nueva orden de Stop Loss / Take Profit
        payload = {
            "symbol": sym,
            "positionId": str(position_id)
        }
        if formatted_sl:
            payload["slPrice"] = formatted_sl
            payload["slStopType"] = "LAST_PRICE"
        if formatted_tp:
            payload["tpPrice"] = formatted_tp
            payload["tpStopType"] = "LAST_PRICE"

        res = await self._request("POST", "/api/v1/futures/tpsl/position/place_order", json_body=payload)
        if res.get("code") == 0:
            order_id = res.get("data", {}).get("orderId")
            logger.info(f"✅ [BITUNIX] TP/SL de posicion colocado con exito para {sym}. Order ID: {order_id}")
            return order_id
        else:
            logger.error(f"❌ [BITUNIX] Error al colocar TP/SL de posicion {sym}: {res.get('msg')}")
            return None

    async def get_pending_positions(self) -> Optional[List[Dict[str, Any]]]:
        """Obtiene las posiciones abiertas actuales desde Bitunix."""
        try:
            res = await self._request("GET", "/api/v1/futures/position/get_pending_positions")
            if res.get("code") == 0 and isinstance(res.get("data"), list):
                return res["data"]
            else:
                logger.error(f"❌ Error al obtener posiciones de Bitunix: {res.get('msg')}")
                return None
        except Exception as e:
            logger.error(f"❌ Error al conectar con endpoint de posiciones: {e}")
            return None

    async def get_pending_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene las órdenes límite pendientes activas en Bitunix."""
        if self.dry_run:
            return []
        try:
            params = {}
            if symbol:
                params["symbol"] = symbol.replace('/', '').upper()
            res = await self._request("GET", "/api/v1/futures/trade/get_pending_orders", params=params)
            if res.get("code") == 0 and res.get("data"):
                data = res["data"]
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "orderList" in data:
                    return data["orderList"] or []
        except Exception as e:
            logger.debug(f"[BITUNIX] No se pudieron obtener órdenes pendientes: {e}")
        return []

    async def cancel_limit_order(self, symbol: str, order_id: str) -> bool:
        """Cancela una orden límite específica en Bitunix."""
        if self.dry_run:
            logger.info(f"🧪 [BITUNIX DRY RUN] Cancelando orden límite {order_id} en {symbol}")
            return True
        try:
            sym = symbol.replace('/', '').upper()
            res = await self._request("POST", "/api/v1/futures/trade/cancel_orders", json_body={
                "symbol": sym,
                "orderList": [{"orderId": str(order_id)}]
            })
            if res.get("code") == 0:
                logger.info(f"🗑️ [BITUNIX] Orden límite {order_id} cancelada exitosamente en {sym}.")
                return True
            else:
                logger.warning(f"⚠️ [BITUNIX] No se pudo cancelar orden {order_id} en {sym}: {res.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"❌ [BITUNIX] Error cancelando orden {order_id} en {sym}: {e}")
    async def cancel_all_orders_for_symbol(self, symbol: str) -> int:
        """
        [SOP-22 ATOMIC ORPHAN PURGE]
        Cancela de forma atómica el 100% de las órdenes pendientes (tanto OPEN como CLOSE)
        para un activo específico en Bitunix.
        """
        sym = symbol.replace('/', '').upper()
        if self.dry_run:
            logger.info(f"🧪 [BITUNIX DRY RUN] Cancelando todas las órdenes pendientes para {sym}")
            return 0

        try:
            pending = await self.get_pending_orders(sym)
            if not pending:
                return 0
                
            order_ids = [str(o.get("orderId")) for o in pending if o.get("orderId")]
            if not order_ids:
                return 0
                
            logger.info(f"🧹 [SOP-22 PURGE] Purgando {len(order_ids)} órdenes huérfanas/pendientes para {sym}...")
            
            # Enviar cancelación masiva en lotes de 10
            cancelled_count = 0
            for i in range(0, len(order_ids), 10):
                batch = order_ids[i:i+10]
                res = await self._request("POST", "/api/v1/futures/trade/cancel_orders", json_body={
                    "symbol": sym,
                    "orderList": [{"orderId": oid} for oid in batch]
                })
                if res.get("code") == 0:
                    cancelled_count += len(batch)
                else:
                    logger.warning(f"⚠️ [SOP-22 PURGE] Error en lote de cancelación para {sym}: {res.get('msg')}")
                    
            logger.info(f"✅ [SOP-22 PURGE] {cancelled_count} órdenes huérfanas eliminadas exitosamente para {sym}.")
            return cancelled_count
        except Exception as e:
            logger.error(f"❌ [SOP-22 PURGE] Excepción purgando órdenes para {sym}: {e}")
            return 0

    async def purge_orphaned_close_orders(self, active_symbols: set) -> int:
        """
        [SOP-22 GHOST ORDER ERADICATOR]
        Audita todas las órdenes en Bitunix y cancela aquellas órdenes límite de cierre ('CLOSE')
        que pertenezcan a monedas que YA NO tienen una posición abierta.
        """
        if self.dry_run:
            return 0
            
        try:
            all_pending = await self.get_pending_orders()
            if not all_pending:
                return 0
                
            active_clean = {s.replace('/', '').upper() for s in active_symbols}
            ghost_orders_by_sym = {}
            
            for o in all_pending:
                sym = str(o.get("symbol", "")).upper()
                is_close = o.get("tradeSide") == "CLOSE" or bool(o.get("reduceOnly"))
                # Si es una orden de cierre pero no hay posición viva para ese símbolo -> ES HUÉRFANA FANTASMA
                if is_close and sym not in active_clean:
                    oid = str(o.get("orderId"))
                    if sym not in ghost_orders_by_sym:
                        ghost_orders_by_sym[sym] = []
                    ghost_orders_by_sym[sym].append(oid)
                    
            total_ghosts_purged = 0
            for sym, oids in ghost_orders_by_sym.items():
                logger.warning(f"👻 [SOP-22 GHOST ALERT] Encontradas {len(oids)} órdenes huérfanas de cierre en {sym} sin posición abierta. Erradicando...")
                res = await self._request("POST", "/api/v1/futures/trade/cancel_orders", json_body={
                    "symbol": sym,
                    "orderList": [{"orderId": oid} for oid in oids]
                })
                if res.get("code") == 0:
                    total_ghosts_purged += len(oids)
                    
            if total_ghosts_purged > 0:
                logger.info(f"🛡️ [SOP-22 GHOST ERADICATOR] Total de órdenes fantasma erradicadas: {total_ghosts_purged}")
            return total_ghosts_purged
        except Exception as e:
            logger.error(f"❌ [SOP-22 GHOST ERADICATOR] Error en auditoría de órdenes fantasma: {e}")
            return 0

    async def get_balance(self) -> float:
        """Obtiene el balance disponible real en USDT de la cuenta."""
        if self.dry_run:
            return 1000.0
        try:
            res = await self._request("GET", "/api/v1/futures/account", params={"marginCoin": "USDT"})
            if res.get("code") == 0 and res.get("data"):
                data = res.get("data")
                avail = 0.0
                if isinstance(data, list) and len(data) > 0:
                    avail = float(data[0].get("available", 0.0))
                elif isinstance(data, dict):
                    avail = float(data.get("available", 0.0))
                if avail > 0:
                    self._last_verified_balance = avail
                    self._last_balance_ts = time.time()
                    return avail
        except Exception as e:
            logger.error(f"❌ Error al obtener balance de Bitunix: {e}")
            
        if self._last_verified_balance > 0 and (time.time() - self._last_balance_ts) < 120.0:
            return self._last_verified_balance
        return 0.0


