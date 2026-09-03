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
from engine.risk.cluster_risk_guard import cluster_risk_guard


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

                    # 2. [AUDITORÍA Y TRAILING ESTRUCTURAL SSoT]
                    # Delegamos exclusivamente al TradeManager la gestión institucional de
                    # Fast BE (+1.0R / +1.2R), TP2 Lock (+2.0R) y Ultra Runner 70% Ratchet (+5.0R).
                    try:
                        await trade_manager._update_signal_trailing(sig)
                        sl = float(sig.get("stop_loss", sl))
                    except Exception as tm_err:
                        logger.debug(f"[NEXUS] TradeManager skip para {asset}: {tm_err}")

                    # 3. 🚀 [SOP-16 FREE-ROLL SCALE-IN ENGINE v28.0]
                    # Solo escalar si la posición está confirmada en BREAKEVEN (Cero Riesgo de Capital) y no se ha escalado previamente
                    is_be_active = pos.get("smart_trailing", {}).get("be_active", False) or \
                                   sig.get("trailing_phase") in ("BREAKEVEN", "TRAILING") or \
                                   pos.get("status") in ("BREAKEVEN", "TRAILING")
                    can_scale = is_be_active and not pos.get("averaging_up_done", False)

                    if can_scale:
                        # 🛡️ SOP-16.2: Veto Macro por Noticias de Alto Impacto
                        from engine.indicators.ghost_data import get_ghost_state
                        ghost = get_ghost_state()
                        macro_risk = getattr(ghost, "macro_risk", False) if ghost else False

                        if not macro_risk:
                            session_state = store.get_session_state(asset)
                            vp = (session_state or {}).get("volume_profile", {})
                            poc = vp.get("poc") if vp else None

                            # Zona de Retesteo OTE / POC / FVG
                            target_ref = poc or entry
                            retest_zone = (current_price <= target_ref * 1.002 and current_price >= target_ref * 0.998) if is_long else \
                                          (current_price >= target_ref * 0.998 and current_price <= target_ref * 1.002)

                            if retest_zone:
                                try:
                                    from engine.risk.risk_manager import RiskManager
                                    rm = RiskManager()
                                    size_usd = float(sig.get("position_size_usdt", sig.get("position_size", 100)))
                                    leverage = int(sig.get("leverage", 1))
                                    current_sl_val = float(sig.get("stop_loss", sl))

                                    # Cálculo de Stop Loss Compuesto con Invarianza de PnL Positivo
                                    scale_calc = rm.calculate_scale_in_sizing(
                                        base_position_size_usdt=size_usd,
                                        base_entry_price=entry,
                                        current_sl=current_sl_val,
                                        add_on_entry_price=current_price,
                                        new_structural_sl=current_sl_val,
                                        signal_type=sig.get("type", "LONG"),
                                        scale_ratio=0.50
                                    )

                                    if scale_calc.get("approved"):
                                        add_on_usd = scale_calc.get("add_on_size_usdt", size_usd * 0.5)
                                        side = 'buy' if is_long else 'sell'
                                        logger.warning(f"📈 [SOP-16 SCALE-IN] Retesteo OTE detectado en {asset} (${current_price:.2f}). Ejecutando Scale-In (+${add_on_usd:.2f} USDT, PnL Neto >= ${scale_calc.get('net_pnl_at_sl'):.2f})...")

                                        scale_success = await self.executor.scale_position(
                                            symbol=asset,
                                            side=side,
                                            amount_usd=add_on_usd,
                                            leverage=leverage
                                        )

                                        if scale_success:
                                            pos["averaging_up_done"] = True
                                            pos["signal"]["position_size_usdt"] = size_usd + add_on_usd
                                            logger.info(f"✅ [SOP-16 SCALE-IN] Posición {asset} escalada con éxito. Nuevo tamaño: ${pos['signal']['position_size_usdt']:.2f}")
                                except Exception as scale_err:
                                    logger.error(f"❌ [SOP-16 SCALE-IN] Error al evaluar/escalar posición {asset}: {scale_err}")

                    # 4. Verificar si la posicion se ha cerrado (SL o TP3 final hit)
                    # 🛡️ BREATHING ROOM GUARD: Evitar stopout en los primeros 10s si el precio no es válido o es ruido de spread
                    created_at = float(pos.get("created_timestamp", pos.get("execution", {}).get("timestamp", 0)) or 0)
                    now_ts = time.time()
                    in_grace_period = (now_ts - created_at < 10.0) if created_at > 0 else False

                    # Si el precio actual es 0 o no válido, omitir evaluación de cierre
                    if current_price <= 0:
                        continue

                    # Solo evaluar SL si no estamos en período de gracia de apertura
                    is_sl = False
                    if not in_grace_period:
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
                    self.remove_pending_limit_symbol(asset)
                    # 🧹 [SOP-22 PURGA ATÓMICA] Cancelar inmediatamente el 100% de las órdenes huérfanas de ese activo
                    try:
                        await self.executor.cancel_all_orders_for_symbol(asset)
                    except Exception as purge_err:
                        logger.error(f"❌ [NEXUS SOP-22] Error purgando órdenes huérfanas para {asset}: {purge_err}")

                # 2.1 🛡️ [SOP-22 GHOST ERADICATOR] Purgar cualquier orden CLOSE huérfana de monedas sin posición
                try:
                    await self.executor.purge_orphaned_close_orders(active_symbols=set(real_positions_map.keys()))
                except Exception as ghost_err:
                    logger.debug(f"[NEXUS SOP-22] Skip erradicación de órdenes fantasma: {ghost_err}")

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
                            dist = abs(entry_price - sl_price) if sl_price > 0 else entry_price * 0.015
                            be_price = entry_price + (dist * 1.0) if side == "LONG" else entry_price - (dist * 1.0)
                            tp1 = entry_price + (dist * 1.5) if side == "LONG" else entry_price - (dist * 1.5)
                            tp2 = entry_price + (dist * 3.0) if side == "LONG" else entry_price - (dist * 3.0)
                            tp3 = entry_price + (dist * 5.0) if side == "LONG" else entry_price - (dist * 5.0)
                            logger.info(f"🛡️ [NEXUS SYNC] Posición {symbol} ya cuenta con Stop Loss activo blindado en ${sl_price:.4f}. BE Target: ${be_price:.4f}")
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
                                f3 = int(round(qty * 0.10))
                            else:
                                f1 = round(qty * 0.60, q_dec)
                                f2 = round(qty * 0.20, q_dec)
                                f3 = round(qty * 0.10, q_dec)

                            # 60% TP1, 20% TP2, 10% TP3 límite (el 10% restante queda libre como ULTRA-RUNNER con Trailing Ratchet)
                            tps = [(tp1, f1, "TP1 (60%)"), (tp2, f2, "TP2 (20%)"), (tp3, f3, "TP3 (10% Límite)")]
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
                                # Fallback resiliente: Si Bitunix rechaza por positionId, reintentar orden CLOSE pura
                                if tp_res.get("code") != 0 and "positionId" in tp_payload:
                                    del tp_payload["positionId"]
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
                            "created_timestamp": time.time(),
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
                                    f3 = int(round(pos_qty * 0.10))
                                else:
                                    f1 = round(pos_qty * 0.60, q_dec)
                                    f2 = round(pos_qty * 0.20, q_dec)
                                    f3 = round(pos_qty * 0.10, q_dec)

                                tps = [(tp1_val, f1, "TP1 (60%)"), (tp2_val, f2, "TP2 (20%)"), (tp3_val, f3, "TP3 (10% Límite)")]
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

        # ── REGLA DE CLUSTER DE CORRELACIÓN CRUZADA (v26.0 CLUSTER FORTRESS) ──
        confluence_score = float(signal.get("confluence_score") or (signal.get("confluence") or {}).get("score", 70.0))
        can_open, cluster_reason = cluster_risk_guard.can_open_position(
            new_asset=asset,
            new_direction=sig_type,
            confluence_score=confluence_score,
            active_positions=self._active_positions
        )
        if not can_open:
            logger.warning(f"🛑 [NEXUS CLUSTER] Rechazada orden en {asset}: {cluster_reason}")
            return

        # ── SPREAD CIRCUIT BREAKER (>0.25% VETO) ──
        current_spread_pct = float(signal.get("spread_pct") or 0.0)
        if current_spread_pct > 0.0025:
            logger.warning(f"🛑 [NEXUS SPREAD GUARD] Rechazada orden a mercado en {asset}: Spread excesivo ({current_spread_pct*100:.3f}% > 0.25%).")
            return

        # ── SOP-27: VWAP EXHAUSTION SHIELD (ANTI-SHORT TRAP) ──
        from engine.risk.risk_manager import RiskManager
        vwap_dist = float(signal.get("vwap_dist_pct") or 0.0)
        is_vwap_ok, vwap_msg = RiskManager.check_vwap_exhaustion(sig_type, vwap_dist)
        if not is_vwap_ok:
            logger.warning(f"🛑 [NEXUS SOP-27] Rechazada orden en {asset}: {vwap_msg}")
            return

        # ── PRE-FLIGHT MARGIN GUARD (SOP-10) ──
        if not self.dry_run:
            avail_margin = await self.executor.get_available_margin_usdt()
            req_margin = float(signal.get("position_size_usdt", self.DEFAULT_MARGIN_USDT))
            if avail_margin < req_margin:
                logger.warning(f"🛑 [NEXUS MARGIN GUARD] Saldo insuficiente para {asset}: Disponible ${avail_margin:.2f} USDT < Requerido ${req_margin:.2f} USDT.")
                return

        logger.info(f"⚡ [NEXUS] Recibida señal de alta fidelidad: {asset} {sig_type}")

        # Garantizar tamaño del 5% del capital ($8.50 USDT margen) y calcular apalancamiento dinámico SOP-21
        if not signal.get("position_size") or float(signal.get("position_size", 0)) > 20.0:
            signal["position_size"] = self.DEFAULT_MARGIN_USDT
            signal["position_size_usdt"] = self.DEFAULT_MARGIN_USDT
            
        entry_val = float(signal.get("price") or signal.get("entry_zone_bottom", 0))
        sl_val = float(signal.get("stop_loss", 0))
        
        # ── SOP-21: INVARIANZA DE LIQUIDACIÓN Y APALANCAMIENTO SEGURO ──
        from engine.risk.risk_manager import RiskManager
        if entry_val > 0 and sl_val > 0:
            safe_lev = RiskManager.calculate_safe_leverage(entry_val, sl_val, max_cap=20)
            signal["leverage"] = safe_lev
            is_safe, liq_msg, cl_ratio = RiskManager.verify_liquidation_clearance(entry_val, sl_val, safe_lev)
            logger.info(f"🛡️ [NEXUS SOP-21] {asset} -> {liq_msg}")
            if not is_safe and cl_ratio < 1.10:
                logger.warning(f"🛑 [NEXUS LIQ GUARD] Orden rechazada para {asset}: Riesgo inminente de liquidación antes de SL.")
                return
        else:
            signal["leverage"] = max(1, min(int(signal.get("leverage", 10)), 20))

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
                    "created_timestamp": time.time(),
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

        # ── REGLA DE CLUSTER DE CORRELACIÓN CRUZADA (v26.0 CLUSTER FORTRESS) ──
        confluence_score = float(signal.get("confluence_score") or (signal.get("confluence") or {}).get("score", 70.0))
        can_open, cluster_reason = cluster_risk_guard.can_open_position(
            new_asset=asset,
            new_direction=signal.get("type", signal.get("signal_type", "LONG")),
            confluence_score=confluence_score,
            active_positions=self._active_positions
        )
        if not can_open:
            logger.info(f"🛑 [NEXUS AUTO-LIMIT] Omitida orden límite para {asset}: {cluster_reason}")
            return

        # ── SOP-27: VWAP EXHAUSTION SHIELD (ANTI-SHORT TRAP) ──
        from engine.risk.risk_manager import RiskManager
        sig_dir = signal.get("type", signal.get("signal_type", "LONG"))
        vwap_dist = float(signal.get("vwap_dist_pct") or 0.0)
        is_vwap_ok, vwap_msg = RiskManager.check_vwap_exhaustion(sig_dir, vwap_dist)
        if not is_vwap_ok:
            logger.info(f"🛑 [NEXUS AUTO-LIMIT SOP-27] Omitida orden límite para {asset}: {vwap_msg}")
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

            # Asignar 5% de margen y apalancamiento seguro adaptativo SOP-21
            signal["position_size"] = self.DEFAULT_MARGIN_USDT
            signal["position_size_usdt"] = self.DEFAULT_MARGIN_USDT
            
            entry_p = float(signal.get('price', 0))
            sl_p = float(signal.get('stop_loss', 0))

            from engine.risk.risk_manager import RiskManager
            if entry_p > 0 and sl_p > 0:
                safe_lev = RiskManager.calculate_safe_leverage(entry_p, sl_p, max_cap=20)
                signal["leverage"] = safe_lev
                is_safe, liq_msg, cl_ratio = RiskManager.verify_liquidation_clearance(entry_p, sl_p, safe_lev)
                logger.info(f"🛡️ [NEXUS AUTO-LIMIT SOP-21] {asset} -> {liq_msg}")
                if not is_safe and cl_ratio < 1.10:
                    logger.warning(f"🛑 [NEXUS AUTO-LIMIT LIQ GUARD] Orden límite rechazada para {asset}: Riesgo inminente de liquidación antes de SL.")
                    return
            else:
                signal["leverage"] = 10

            logger.info(f"🎯 [NEXUS AUTO-LIMIT] Enviando orden límite institucional automática a Bitunix para {asset} @ ${entry_p:.2f} (Margen: ${self.DEFAULT_MARGIN_USDT} USDT [5%] @ {signal['leverage']}x)")
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

