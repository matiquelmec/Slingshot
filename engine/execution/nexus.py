"""
engine/execution/nexus.py — v11.1 APEX SOVEREIGN (Audited)
=============================================
EL NODO DE EJECUCIÓN SOBERANO.

Responsabilidad:
  1. Escuchar señales aprobadas del SignalHandler.
  2. Fragmentar órdenes usando DeltaOrchestrator (60/20/20).
  3. Ejecutar vía BinanceExecutor (Modo Sync/Hilos) o Bitunix.
  4. Monitorear estados de órdenes y activar el Smart Trailing en vivo.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, List
from engine.core.logger import logger
from engine.execution.delta_executor import DeltaOrchestrator
from engine.execution.bitunix_executor import BitunixExecutor
from engine.api.config import settings
from engine.core.memory import blackbox
from engine.core.store import store
from engine.workers.trade_manager import trade_manager
from engine.api.registry import registry


class NexusNode:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.executor = BitunixExecutor(dry_run=dry_run)
        self._active_positions = {}
        self._pending_limit_symbols = set()
        logger.info(f"🛡️ [NEXUS] Nodo de Ejecución inicializado (Dry Run: {dry_run})")

    def start_centinels(self):
        """Inicia los procesos de monitoreo y gestión de riesgo."""
        loop = asyncio.get_event_loop()
        loop.create_task(self._dashboard_loop())
        loop.create_task(self._omega_centinel_loop())
        loop.create_task(self._sync_exchange_positions_loop())

    async def _omega_centinel_loop(self):
        """
        [OMEGA CENTINEL v10.2.0]
        Monitorea el precio en vivo y gestiona el Smart Trailing.
        """
        logger.info("👁️ [OMEGA] Centinela de Riesgo activado.")
        while True:
            await asyncio.sleep(5) # Ciclo de auditoría cada 5 segundos

            assets_to_remove = []
            for asset, pos in list(self._active_positions.items()):
                try:
                    # 1. Obtener precio actual (simplificado vía ticker)
                    current_price = await self.executor.get_ticker_price(asset)

                    sig = pos['signal']
                    entry = sig['price']
                    tp1 = sig['tp1']
                    sl = sig['stop_loss']
                    is_long = sig['type'] == "LONG"

                    # 2. 🛡️ [SMART TRAILING 2-FASES] (Fase 1: Fast BE +1.0R / $0.00 Riesgo | Fase 2: Lock en TP2)
                    be_active = pos.get("smart_trailing", {}).get("be_active", False)
                    tp2 = sig.get('tp2')
                    tp2_locked = pos.get("smart_trailing", {}).get("tp2_locked", False)

                    # Fase 1: Fast BE (+1.0R) alcanzado -> Mover SL a Breakeven + Buffer de Comisiones
                    be_target = float(sig.get('be_price', 0)) or (entry + abs(entry - sl) if is_long else entry - abs(entry - sl))
                    if not be_active:
                        target_hit = (current_price >= be_target) if is_long else (current_price <= be_target)
                        if target_hit:
                            logger.info(f"🎯 [OMEGA FASE 1] {asset} alcanzó Fast BE (+1.0R / ${be_target:.2f}). Moviendo SL a BREAKEVEN en Bitunix...")
                            new_sl = entry * 1.0005 if is_long else entry * 0.9995

                            old_sl_id = None
                            protection_orders = pos.get("execution", {}).get("protection_orders", [])
                            if protection_orders:
                                old_sl_id = protection_orders[0]

                            sl_side = 'sell' if is_long else 'buy'
                            amount = pos.get("execution", {}).get("amount", 0.0)

                            new_sl_id = await self.executor.update_stop_loss(
                                symbol=asset,
                                old_order_id=old_sl_id,
                                new_stop_price=new_sl,
                                amount=amount,
                                side=sl_side,
                                position_id=pos.get("execution", {}).get("main_order_id"),
                                tp_price=None
                            )

                            if new_sl_id or self.dry_run:
                                if protection_orders:
                                    pos["execution"]["protection_orders"][0] = new_sl_id
                                pos["signal"]["stop_loss"] = new_sl
                                pos["signal"]["trailing_phase"] = "BREAKEVEN"
                                pos["signal"]["profit_locked"] = True
                                pos["smart_trailing"] = {"be_active": True, "trailing_active": True, "phase": "BREAKEVEN"}
                                
                                # Broadcast actualización a la UI
                                await registry.broadcast_global({
                                    "type": "signal_auditor_update",
                                    "data": {**pos["signal"], "trailing_phase": "BREAKEVEN", "profit_locked": True, "status": "ACTIVE_PROTECTED"}
                                })
                                logger.info(f"🛡️ [OMEGA FASE 1] SL de {asset} movido a BE de forma real en Bitunix: ${new_sl:.2f} (Trade 100% Risk-Free)")

                    # Fase 2: TP2 alcanzado -> Mover SL a TP1 (Bloquear ganancia +1.5R)
                    elif be_active and tp2 and not tp2_locked:
                        tp2_hit = (current_price >= tp2) if is_long else (current_price <= tp2)
                        if tp2_hit:
                            logger.info(f"🎯 [OMEGA FASE 2] {asset} alcanzó TP2. Moviendo SL a TP1 (${tp1:.2f}) para bloquear +1.5R...")
                            new_sl = tp1

                            old_sl_id = None
                            protection_orders = pos.get("execution", {}).get("protection_orders", [])
                            if protection_orders:
                                old_sl_id = protection_orders[0]

                            sl_side = 'sell' if is_long else 'buy'
                            amount = pos.get("execution", {}).get("amount", 0.0)

                            new_sl_id = await self.executor.update_stop_loss(
                                symbol=asset,
                                old_order_id=old_sl_id,
                                new_stop_price=new_sl,
                                amount=amount,
                                side=sl_side,
                                position_id=pos.get("execution", {}).get("main_order_id"),
                                tp_price=None
                            )

                            if new_sl_id or self.dry_run:
                                if protection_orders:
                                    pos["execution"]["protection_orders"][0] = new_sl_id
                                pos["signal"]["stop_loss"] = new_sl
                                pos["signal"]["trailing_phase"] = "TRAILING_TP1"
                                pos["smart_trailing"]["tp2_locked"] = True
                                pos["smart_trailing"]["phase"] = "TRAILING_TP1"

                                await registry.broadcast_global({
                                    "type": "signal_auditor_update",
                                    "data": {**pos["signal"], "trailing_phase": "TRAILING_TP1", "stop_loss": new_sl}
                                })
                                logger.info(f"💎 [OMEGA FASE 2] Ganancia asegurada en {asset}: SL en ${new_sl:.2f} (+1.5R garantizado)")

                    # 4. 🚀 [YOSH v13.1] AVERAGING UP (Escalado en Ganancia)
                    # Si ya estamos en BE y el precio retrocede a una zona de VALOR, añadir contratos.
                    can_scale = be_active and not pos.get("averaging_up_done", False)
                    if can_scale:
                        session_state = store.get_session_state(asset)
                        vp = (session_state or {}).get("volume_profile", {})

                        if vp and vp.get("poc"):
                            poc = vp["poc"]

                            # Criterio: El precio retrocede al POC (dependiendo de la dirección)
                            target_ref = poc # Usamos el POC como imán de valor principal
                            retest_zone = (current_price <= target_ref * 1.001 and current_price >= target_ref) if is_long else \
                                          (current_price >= target_ref * 0.999 and current_price <= target_ref)

                            if retest_zone:
                                logger.warning(f"📈 [YOSH] Retest de VALOR detectado en {asset} (${current_price:.2f}). Ejecutando AVERAGING UP...")
                                try:
                                    side = 'buy' if is_long else 'sell'
                                    size_usd = float(sig.get("position_size_usdt", sig.get("position_size", 100)))
                                    leverage = int(sig.get("leverage", 1))

                                    # Añadir 50% de contratos
                                    scale_success = await self.executor.scale_position(
                                        symbol=asset,
                                        side=side,
                                        amount_usd=size_usd * 0.5,
                                        leverage=leverage
                                    )

                                    if scale_success:
                                        pos["averaging_up_done"] = True
                                        pos["signal"]["position_size_usdt"] *= 1.5
                                        logger.info(f"✅ [YOSH] Posición {asset} escalada de forma real. Nuevo tamaño en memoria: ${pos['signal']['position_size_usdt']:.2f}")
                                except Exception as scale_err:
                                    logger.error(f"❌ [YOSH] Error al escalar posición: {scale_err}")


                    # 3. [TRAILING ESTRUCTURAL] Actualizar SL con confirmaciones reales
                    # Delegamos al TradeManager para aplicar la triple confirmacion
                    # (cierre de vela + RVOL + BOS) antes de mover el SL.
                    # Esto reemplaza el SL fijo por el SL dinamico estructural.
                    try:
                        await trade_manager._update_signal_trailing(sig)
                        # Releer el SL del signal: puede haber sido actualizado por el TradeManager
                        sl = float(sig.get("stop_loss", sl))
                    except Exception as tm_err:
                        logger.debug(f"[NEXUS] TradeManager skip para {asset}: {tm_err}")

                    # 4. Verificar si la posicion se ha cerrado (SL o TP3 final hit)
                    is_sl = (current_price <= sl) if is_long else (current_price >= sl)
                    is_tp = False
                    if not is_sl:
                        tp3 = sig.get('tp3', tp1 * 1.1)
                        is_tp = (current_price >= tp3) if is_long else (current_price <= tp3)

                    if is_sl or is_tp:
                        result_str = "STOP_LOSS" if is_sl else "TAKE_PROFIT"
                        logger.info(f"🏁 [OMEGA] {asset} cerrado por {result_str}. Grabando en Black Box y transmitiendo.")

                        # Grabar en la caja negra para aprendizaje institucional
                        blackbox.record_trade(sig, result_str)

                        # Actualizar estado e informar al frontend y base de datos
                        sig["status"] = result_str
                        await store.save_signal(sig)
                        await registry.broadcast_global({"type": "signal_auditor_update", "data": sig})

                        assets_to_remove.append(asset)

                except Exception as e:
                    logger.error(f"⚠️ [OMEGA] Error auditando {asset}: {e}")

            for asset in assets_to_remove:
                del self._active_positions[asset]

    async def _dashboard_loop(self):
        """Monitor simple para ver posiciones en tiempo real."""
        logger.info("📊 [NEXUS] Dashboard de Ejecución activado.")
        while True:
            await asyncio.sleep(10) # Refrescar cada 10 segundos
            if not self._active_positions:
                continue

            logger.info("="*50)
            logger.info("📈 DASHBOARD DE EJECUCIÓN APEX (LIVE)")
            logger.info("="*50)
            for asset, pos in self._active_positions.items():
                sig = pos.get('signal', {})
                status = pos.get('status', 'UNKNOWN')
                entry = sig.get('price', 0)
                tp1 = sig.get('tp1', 0)
                tp3 = sig.get('take_profit_3r', sig.get('tp3', 0))
                sl = sig.get('stop_loss', 0)
                size = sig.get('position_size_usdt', sig.get('position_size', 0))

                # Proyección de PnL (asumiendo TP3 como target final)
                if entry > 0:
                    rr = round(abs(tp3 - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0
                    profit_pct = round(abs(tp3 - entry) / entry * 100, 2)
                else:
                    rr = 0
                    profit_pct = 0

                logger.info(f"🔹 {asset} [{sig.get('type', 'LONG')}] | Status: {status}")
                logger.info(f"   Entry: ${entry:.2f} | Size: ${size:.2f}")
                logger.info(f"   SL: ${sl:.2f} | TP1: ${tp1:.2f} | TP3: ${tp3:.2f}")
                logger.info(f"   Proyección: R:R {rr}:1 | +{profit_pct}% (Max)")
            logger.info("="*50)

    async def _sync_exchange_positions_loop(self):
        """
        [NEXUS AUTO-SYNC]
        Sincroniza periódicamente las posiciones abiertas reales de la API de Bitunix
        con el estado interno y las transmite al frontend.
        """
        if self.dry_run:
            logger.info("ℹ️ [NEXUS SYNC] Modo Dry Run activo. Desactivando auto-sincronización.")
            return

        logger.info("🔄 [NEXUS SYNC] Centinela de Auto-Sincronización activado.")
        while True:
            try:
                # 1. Obtener posiciones reales del exchange
                real_positions = await self.executor.get_pending_positions()
                if real_positions is None:
                    await asyncio.sleep(15)
                    continue

                real_positions_map = {p.get("symbol"): p for p in real_positions if p.get("symbol")}

                # 2. Eliminar de memoria posiciones que ya no existen en Bitunix (cerradas)
                closed_assets = []
                for asset, pos_data in list(self._active_positions.items()):
                    if asset not in real_positions_map:
                        logger.info(f"📉 [NEXUS SYNC] Posición en {asset} ya no existe en Bitunix. Removiendo.")
                        closed_assets.append(asset)
                        sig = pos_data.get("signal", {})
                        sig["status"] = "CLOSED"
                        await store.save_signal(sig)
                        await registry.broadcast_global({"type": "signal_auditor_update", "data": sig})

                for asset in closed_assets:
                    del self._active_positions[asset]

                # 3. Añadir a memoria posiciones abiertas en Bitunix que no tenemos registradas
                for symbol, p in real_positions_map.items():
                    if symbol not in self._active_positions:
                        qty = float(p.get("qty", 0))
                        entry_price = float(p.get("avgOpenPrice", 0)) or 1.0
                        raw_side = p.get("side", "BUY").upper()
                        side = "LONG" if raw_side in ("BUY", "LONG") else "SHORT"
                        leverage = int(p.get("leverage", 1))
                        margin = float(p.get("margin", 0))
                        position_id = p.get("positionId", f"manual_{int(time.time())}")

                        logger.info(f"📈 [NEXUS SYNC] Sincronizando posicion externa Bitunix: {symbol} ({side})")

                        # 1. Comprobar si la posición YA tiene un Stop Loss activo en Bitunix
                        existing_sl_in_exchange = None
                        # Revisar si viene directamente en la posición
                        pos_direct_sl = p.get("slPrice") or p.get("stopLoss")
                        if pos_direct_sl:
                            try:
                                existing_sl_in_exchange = float(pos_direct_sl)
                            except (ValueError, TypeError):
                                pass

                        if not existing_sl_in_exchange:
                            try:
                                tpsl_chk = await self.executor._request("GET", "/api/v1/futures/tpsl/get_pending_orders", params={"symbol": symbol})
                                if tpsl_chk.get("code") == 0 and isinstance(tpsl_chk.get("data"), list):
                                    for t_item in tpsl_chk["data"]:
                                        raw_sl = t_item.get("slPrice") or t_item.get("triggerPrice")
                                        if raw_sl:
                                            try:
                                                existing_sl_in_exchange = float(raw_sl)
                                                break
                                            except (ValueError, TypeError):
                                                pass
                            except Exception as e:
                                logger.debug(f"[NEXUS SYNC] Error consultando TPSL existente: {e}")

                        # Buscar si existe un setup SMC institucional activo para este activo en el escáner
                        all_opps = store.get_scanner_opportunities("scalp") + store.get_scanner_opportunities("swing")
                        matching_setup = next((o for o in all_opps if o.get("asset") == symbol and side in str(o.get("direction", "")).upper()), None)

                        if existing_sl_in_exchange:
                            sl_price = existing_sl_in_exchange
                            be_price = entry_price
                            dist = abs(entry_price - sl_price) if sl_price > 0 else entry_price * 0.02
                            tp1 = entry_price + (dist * 1.3) if side == "LONG" else entry_price - (dist * 1.3)
                            tp2 = entry_price + (dist * 2.2) if side == "LONG" else entry_price - (dist * 2.2)
                            tp3 = entry_price + (dist * 3.5) if side == "LONG" else entry_price - (dist * 3.5)
                            logger.info(f"🛡️ [NEXUS SYNC] Posición {symbol} ya cuenta con Stop Loss activo blindado en ${sl_price:.4f}.")
                        elif matching_setup:
                            sl_price = float(matching_setup.get("stop_loss", 0))
                            be_price = float(matching_setup.get("be_price", 0))
                            tp1 = float(matching_setup.get("tp1", 0))
                            tp2 = float(matching_setup.get("tp2", 0))
                            tp3 = float(matching_setup.get("tp3", 0))
                            logger.info(f"💎 [NEXUS SYNC] Setup institucional SMC emparejado para {symbol}: SL: ${sl_price} | BE: ${be_price} | TP1: ${tp1}")
                        else:
                            dist = entry_price * 0.02
                            sl_price = entry_price * 0.98 if side == "LONG" else entry_price * 1.02
                            be_price = entry_price + (dist * 1.0) if side == "LONG" else entry_price - (dist * 1.0)
                            tp1 = entry_price + (dist * 1.3) if side == "LONG" else entry_price - (dist * 1.3)
                            tp2 = entry_price + (dist * 2.2) if side == "LONG" else entry_price - (dist * 2.2)
                            tp3 = entry_price + (dist * 3.5) if side == "LONG" else entry_price - (dist * 3.5)

                        reconstructed_signal = {
                            "asset": symbol,
                            "interval": "15m",
                            "signal_type": side,
                            "type": side,
                            "entry_price": entry_price,
                            "price": entry_price,
                            "stop_loss": sl_price,
                            "be_price": be_price,
                            "tp1": tp1,
                            "tp2": tp2,
                            "tp3": tp3,
                            "take_profit_3r": tp3,
                            "status": "FILLED",
                            "position_size": margin,
                            "position_size_usdt": margin,
                            "leverage": leverage,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "id": position_id
                        }

                        # Si NO tenía Stop Loss en el exchange, colocar el SL inicial
                        protection_ids = []
                        if not existing_sl_in_exchange and sl_price > 0:
                            logger.info(f"🛡️ [NEXUS SYNC] Configurando Stop Loss inicial en Bitunix (SL: ${sl_price:.2f}) para {symbol}...")
                            tpsl_order_id = await self.executor.place_position_tpsl(
                                symbol=symbol,
                                position_id=position_id,
                                sl_price=sl_price,
                                tp_price=None
                            )
                            if tpsl_order_id:
                                protection_ids.append(tpsl_order_id)

                        # 2. Colocar Take Profits límites fragmentados (60% / 20% / 20%) si no existen previamente
                        try:
                            existing_orders_res = await self.executor._request("GET", "/api/v1/futures/trade/get_pending_orders", params={"symbol": symbol})
                            existing_orders = existing_orders_res.get("data", {}).get("orderList", []) if existing_orders_res.get("code") == 0 else []
                            existing_close_orders = [o for o in existing_orders if o.get("reduceOnly") or o.get("tradeSide") == "CLOSE"]
                        except Exception:
                            existing_close_orders = []

                        if not existing_close_orders:
                            # Formatear decimales según especificación exacta y dinámica de Bitunix
                            q_dec, p_dec = await self.executor.get_symbol_precision(symbol)
                            
                            if q_dec == 0:
                                f1 = int(round(qty * 0.60))
                                f2 = int(round(qty * 0.20))
                                f3 = int(qty - f1 - f2)
                            else:
                                f1 = round(qty * 0.60, q_dec)
                                f2 = round(qty * 0.20, q_dec)
                                f3 = round(qty - f1 - f2, q_dec)

                            tps = [(tp1, f1, "TP1 (60%)"), (tp2, f2, "TP2 (20%)"), (tp3, f3, "TP3 (20%)")]
                            close_side = "SELL" if side == "LONG" else "BUY"

                            for tp_val, tp_qty, label in tps:
                                if tp_qty <= 0 or tp_val <= 0:
                                    continue
                                tp_payload = {
                                    "symbol": symbol,
                                    "qty": str(int(tp_qty) if q_dec == 0 else f"{tp_qty:.{q_dec}f}"),
                                    "price": f"{float(tp_val):.{p_dec}f}",
                                    "side": close_side,
                                    "tradeSide": "CLOSE",
                                    "orderType": "LIMIT",
                                    "effect": "GTC"
                                }
                                if position_id and str(position_id).isdigit():
                                    tp_payload["positionId"] = str(position_id)

                                tp_res = await self.executor._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_payload)
                                if tp_res.get("code") == 0:
                                    tp_order_id = tp_res.get("data", {}).get("orderId")
                                    logger.info(f"🎯 [NEXUS SYNC] Orden de {label} límite colocada a ${tp_val:.{p_dec}f} ({tp_qty} unidades) | ID: {tp_order_id}")
                                    protection_ids.append(tp_order_id)
                                else:
                                    logger.error(f"❌ [NEXUS SYNC] Error al colocar {label}: {tp_res.get('msg')}")
                        else:
                            logger.info(f"🛡️ [NEXUS SYNC] {symbol} ya cuenta con {len(existing_close_orders)} órdenes límite de Take Profit activas en Bitunix.")
                            for eo in existing_close_orders:
                                protection_ids.append(eo.get("orderId"))

                        await store.save_signal(reconstructed_signal)
                        self._active_positions[symbol] = {
                            "signal": reconstructed_signal,
                            "execution": {
                                "main_order_id": position_id,
                                "amount": qty,
                                "entry_price": entry_price,
                                "asset": symbol,
                                "protection_orders": protection_ids
                            },
                            "status": "FILLED"
                        }
                        from engine.api.registry import registry
                        await registry.broadcast_global({"type": "signal_auditor_update", "data": reconstructed_signal})

                # 4. 🛡️ [AUTO-HEALING RECONCILIATOR]
                # Auditar posiciones activas existentes para auto-reparar cualquier SL o TP faltante
                for symbol, pos_data in list(self._active_positions.items()):
                    try:
                        sig = pos_data.get("signal", {})
                        entry_p = float(sig.get("entry_price") or sig.get("price", 0))
                        pos_id = str(pos_data.get("execution", {}).get("main_order_id", ""))
                        pos_qty = float(pos_data.get("execution", {}).get("amount", 0))
                        sl_p = float(sig.get("stop_loss", 0))
                        side = sig.get("signal_type", sig.get("type", "LONG"))

                        # 4.1 Comprobar y auto-reparar Stop Loss si falta
                        if sl_p > 0 and pos_id:
                            chk_tpsl = await self.executor._request("GET", "/api/v1/futures/tpsl/get_pending_orders", params={"symbol": symbol})
                            t_orders = chk_tpsl.get("data", []) or []
                            has_active_sl = any(t.get("slPrice") or t.get("triggerPrice") for t in t_orders) if isinstance(t_orders, list) else False
                            if not has_active_sl:
                                logger.warning(f"🩹 [AUTO-HEALING] Posición {symbol} carece de Stop Loss activo en Bitunix. Auto-reparando SL @ ${sl_p}...")
                                await self.executor.place_position_tpsl(symbol=symbol, position_id=pos_id, sl_price=sl_p)

                        # 4.2 Comprobar y auto-reparar Take Profits límites si faltan
                        tp1_val = float(sig.get("tp1", 0))
                        tp2_val = float(sig.get("tp2", 0))
                        tp3_val = float(sig.get("tp3") or sig.get("take_profit_3r", 0))

                        if tp1_val > 0 and pos_qty > 0 and pos_id:
                            chk_orders_res = await self.executor._request("GET", "/api/v1/futures/trade/get_pending_orders", params={"symbol": symbol})
                            chk_data = chk_orders_res.get("data", {})
                            cur_orders = chk_data.get("orderList", []) if isinstance(chk_data, dict) else (chk_data if isinstance(chk_data, list) else [])
                            close_count = sum(1 for o in cur_orders if o.get("tradeSide") == "CLOSE" or o.get("reduceOnly"))
                            
                            # Si no hay órdenes de cierre y aún no hemos alcanzado TP1, re-colocar la grilla 60/20/20
                            if close_count == 0 and not pos_data.get("smart_trailing", {}).get("be_active"):
                                logger.warning(f"🩹 [AUTO-HEALING] Posición {symbol} no tiene órdenes límite TP en Bitunix. Auto-reparando salidas escalonadas...")
                                q_dec, p_dec = await self.executor.get_symbol_precision(symbol)
                                if q_dec == 0:
                                    f1 = int(round(pos_qty * 0.60))
                                    f2 = int(round(pos_qty * 0.20))
                                    f3 = int(pos_qty - f1 - f2)
                                else:
                                    f1 = round(pos_qty * 0.60, q_dec)
                                    f2 = round(pos_qty * 0.20, q_dec)
                                    f3 = round(pos_qty - f1 - f2, q_dec)

                                tps = [(tp1_val, f1, "TP1"), (tp2_val, f2, "TP2"), (tp3_val, f3, "TP3")]
                                close_side = "SELL" if "LONG" in side.upper() else "BUY"
                                for p_val, q_val, lbl in tps:
                                    if q_val <= 0 or p_val <= 0: continue
                                    tp_pld = {
                                        "symbol": symbol,
                                        "qty": str(int(q_val) if q_dec == 0 else f"{q_val:.{q_dec}f}"),
                                        "price": f"{float(p_val):.{p_dec}f}",
                                        "side": close_side,
                                        "tradeSide": "CLOSE",
                                        "orderType": "LIMIT",
                                        "effect": "GTC",
                                        "positionId": str(pos_id)
                                    }
                                    res_heal = await self.executor._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_pld)
                                    if res_heal.get("code") == 0:
                                        logger.info(f"✅ [AUTO-HEALING] {symbol} {lbl} colocado a ${p_val:.{p_dec}f} ({q_val} u)")
                    except Exception as heal_err:
                        logger.debug(f"[AUTO-HEALING] Skip reconciliación para {symbol}: {heal_err}")

            except Exception as e:
                logger.error(f"❌ [NEXUS SYNC] Error en auto-sincronización: {e}")

            await asyncio.sleep(15)

    MAX_CONCURRENT_POSITIONS = 4
    DEFAULT_MARGIN_USDT = 8.50 # ~5% del capital ($170 USDT) a 20x apalancamiento aislado

    def get_unprotected_risk_count(self) -> int:
        """
        Calcula cuántas posiciones abiertas tienen riesgo real flotante.
        Las posiciones en Breakeven (Fast BE / $0.00 riesgo) LIBERAN su slot de riesgo.
        """
        unprotected = 0
        for asset, pos in self._active_positions.items():
            sig = pos.get("signal", {})
            be_active = pos.get("smart_trailing", {}).get("be_active", False)
            is_long = "LONG" in str(sig.get("type", sig.get("signal_type", "LONG"))).upper()
            entry = float(sig.get("price", 0))
            sl = float(sig.get("stop_loss", 0))
            
            # Si el SL ya está en la entrada (o mejor), no hay riesgo de capital
            sl_at_be = (is_long and entry > 0 and sl >= entry * 0.999) or (not is_long and entry > 0 and sl > 0 and sl <= entry * 1.001)
            if not (be_active or sl_at_be):
                unprotected += 1
        return unprotected

    async def process_signal(self, signal: Dict[str, Any]):
        """
        Punto de entrada para señales de ejecución directa a mercado.
        """
        asset = signal.get("asset")
        sig_type = signal.get("type", "LONG")

        # ── REGLA INSTITUCIONAL DE RIESGO: MÁXIMO 4 OPERACIONES EN RIESGO (SLOT RECYCLING) ──
        unprotected_count = self.get_unprotected_risk_count()
        if unprotected_count >= self.MAX_CONCURRENT_POSITIONS:
            logger.warning(f"🛑 [NEXUS RIESGO] Límite de {self.MAX_CONCURRENT_POSITIONS} operaciones en riesgo alcanzado ({unprotected_count} activas con riesgo). Rechazando entrada en {asset}.")
            return

        logger.info(f"⚡ [NEXUS] Recibida señal de alta fidelidad: {asset} {sig_type}")

        # Garantizar tamaño del 5% del capital ($8.50 USDT margen a 20x)
        if not signal.get("position_size") or float(signal.get("position_size", 0)) > 20.0:
            signal["position_size"] = self.DEFAULT_MARGIN_USDT
            signal["position_size_usdt"] = self.DEFAULT_MARGIN_USDT
        signal["leverage"] = signal.get("leverage", 20)

        # 1. Fragmentación Apex (Delta 60/20/20)
        fragments = DeltaOrchestrator.fragment_order(signal)

        # 2. Ejecución de la Grilla
        try:
            result = await self.executor.execute_signal(signal, fragments=fragments)

            if result.get("status") == "success":
                logger.info(f"✅ [NEXUS] Posición abierta en {asset}. ID: {result.get('main_order_id')}")

                self._active_positions[asset] = {
                    "signal": signal,
                    "execution": result,
                    "status": "OPEN"
                }
            else:
                logger.error(f"❌ [NEXUS] Error al abrir posición en {asset}: {result.get('message')}")

        except Exception as e:
            logger.error(f"💥 [NEXUS] Error crítico procesando señal: {e}")

    async def process_limit_setup(self, signal: Dict[str, Any]):
        """
        [NEXUS AUTO-LIMIT]
        Coloca automáticamente una orden LÍMITE en Bitunix para oportunidades institucionales del escáner.
        Evita duplicar órdenes si ya existe una posición o una orden límite activa para ese activo.
        """
        asset = signal.get("asset", signal.get("symbol", "")).upper()
        if not asset or self.dry_run:
            return

        # ── REGLA INSTITUCIONAL DE RIESGO: MÁXIMO 4 OPERACIONES EN RIESGO (SLOT RECYCLING) ──
        unprotected_count = self.get_unprotected_risk_count()
        if unprotected_count >= self.MAX_CONCURRENT_POSITIONS:
            logger.info(f"🛑 [NEXUS RIESGO] Máximo de {self.MAX_CONCURRENT_POSITIONS} operaciones con riesgo alcanzado ({unprotected_count} en riesgo / {len(self._active_positions)} totales). Pausando nuevas órdenes.")
            return

        # Si ya tenemos una posición abierta o una orden pendiente registrada en este activo, no duplicar
        if asset in self._active_positions or asset in self._pending_limit_symbols:
            return

        try:
            # Verificar órdenes pendientes en Bitunix para no saturar el libro
            pending_orders = await self.executor.get_pending_orders(asset)
            if pending_orders:
                logger.debug(f"[NEXUS AUTO-LIMIT] Ya existe orden límite pendiente en Bitunix para {asset}.")
                self._pending_limit_symbols.add(asset)
                return

            # Asignar 5% de margen y 20x de apalancamiento
            signal["position_size"] = self.DEFAULT_MARGIN_USDT
            signal["position_size_usdt"] = self.DEFAULT_MARGIN_USDT
            signal["leverage"] = 20

            entry_p = float(signal.get('price', 0))
            logger.info(f"🎯 [NEXUS AUTO-LIMIT] Enviando orden límite institucional automática a Bitunix para {asset} @ ${entry_p:.2f} (Margen: ${self.DEFAULT_MARGIN_USDT} USDT [5%] @ 20x)")
            res = await self.executor.place_limit_signal(signal)
            if res.get("status") == "success":
                self._pending_limit_symbols.add(asset)
                logger.info(f"✅ [NEXUS AUTO-LIMIT] Orden límite para {asset} colocada exitosamente en Bitunix! ID: {res.get('order_id')}")
            else:
                logger.warning(f"⚠️ [NEXUS AUTO-LIMIT] No se pudo colocar orden límite en {asset}: {res.get('message')}")
        except Exception as e:
            logger.error(f"❌ [NEXUS AUTO-LIMIT] Error colocando orden en {asset}: {e}")

    def remove_pending_limit_symbol(self, symbol: str):
        """Libera el activo del conjunto de órdenes pendientes en memoria."""
        sym_clean = symbol.replace('/', '').upper()
        self._pending_limit_symbols.discard(sym_clean)

    async def purge_all_pending_limit_orders(self, reason: str = "SLOT_OVERLOAD"):
        """
        [SAFETY PURGE] Cancela todas las órdenes límite pendientes en Bitunix
        cuando se alcanza el límite de riesgo o por invalidación global.
        """
        logger.warning(f"🛡️ [NEXUS PURGE] Iniciando purga de órdenes límite pendientes. Razón: {reason}")
        try:
            pending_orders = await self.executor.get_pending_orders()
            # Filtrar solo órdenes que abren posiciones (tradeSide == 'OPEN' o reduceOnly == False)
            open_limits = [
                o for o in pending_orders 
                if (o.get("tradeSide") == "OPEN" or not o.get("reduceOnly")) and o.get("orderType") == "LIMIT"
            ]
            
            for o in open_limits:
                sym = o.get("symbol")
                oid = o.get("orderId")
                if sym and oid:
                    await self.executor.cancel_limit_order(sym, oid)
                    self.remove_pending_limit_symbol(sym)
                    logger.info(f"🧹 [NEXUS PURGE] Orden límite sobrante {oid} ({sym}) cancelada por seguridad ({reason}).")
        except Exception as e:
            logger.error(f"❌ [NEXUS PURGE] Error en purga de órdenes límite: {e}")

    def get_active_positions(self):
        return self._active_positions

# Instancia global (Singleton)
# Live trading must be explicitly enabled from .env.
nexus = NexusNode(dry_run=not settings.ENABLE_LIVE_TRADING)

