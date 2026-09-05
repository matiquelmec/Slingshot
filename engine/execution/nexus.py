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
from typing import Dict, Any, List, Optional
from engine.core.logger import logger
from engine.execution.delta_executor import DeltaOrchestrator
from engine.execution.bitunix_executor import BitunixExecutor
from engine.api.config import settings
from engine.core.memory import blackbox
from engine.core.store import store
from engine.workers.trade_manager import trade_manager
from engine.api.registry import registry
from engine.risk.cluster_risk_guard import cluster_risk_guard
from engine.risk.risk_manager import RiskManager


class NexusNode:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        from engine.execution.account_manager import AccountManager
        self.account_manager = AccountManager(dry_run=dry_run)
        self.executor = self.account_manager.get_executor("primary") or BitunixExecutor(dry_run=dry_run)
        self._active_positions = {}
        self._pending_limit_symbols = set()
        logger.info(f"🛡️ [NEXUS] Nodo de Ejecución Multi-Cuenta inicializado (Dry Run: {dry_run})")

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
                        logger.info(f"🏁 [OMEGA] {asset} alcanzó umbral de {result_str}. Grabando evento y transmitiendo. (Remoción delegada a Bitunix SSoT)")

                        # Grabar en la caja negra para aprendizaje institucional
                        blackbox.record_trade(sig, result_str)

                        # Actualizar estado e informar al frontend y base de datos
                        sig["status"] = result_str
                        await store.save_signal(sig)
                        await registry.broadcast_global({"type": "signal_auditor_update", "data": sig})
                        # 🛡️ SSoT RULE: NO eliminar de self._active_positions aquí.
                        # La única fuente de verdad para eliminar una posición abierta es Bitunix confirmando
                        # el cierre real en _sync_exchange_positions_loop.

                except Exception as e:
                    logger.error(f"⚠️ [OMEGA] Error auditando {asset}: {e}")

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
                # 1. Obtener posiciones reales del exchange para todas las cuentas activas (SOP-45)
                executors = self.account_manager.get_all_executors(enabled_only=True)
                if not executors:
                    executors = {"primary": self.executor}

                all_account_positions = {}
                for acc_id, ex in executors.items():
                    try:
                        acc_pos = await ex.get_pending_positions()
                        if acc_pos is not None:
                            all_account_positions[acc_id] = {p.get("symbol"): p for p in acc_pos if p.get("symbol")}
                    except Exception as err:
                        logger.debug(f"[NEXUS SYNC] Error obteniendo posiciones para {acc_id}: {err}")

                primary_positions_map = all_account_positions.get("primary", {})
                real_positions_map = primary_positions_map

                # 2. Eliminar de memoria posiciones que ya no existen en Bitunix (cerradas)
                closed_assets = []
                for asset, pos_data in list(self._active_positions.items()):
                    pos_acc = pos_data.get("account_id", "primary")
                    acc_active_map = all_account_positions.get(pos_acc, real_positions_map)
                    base_asset = pos_data.get("signal", {}).get("asset", asset).split("_")[-1]
                    if base_asset not in acc_active_map and asset not in real_positions_map:
                        logger.info(f"📉 [NEXUS SYNC] Posición en {asset} ({pos_acc}) ya no existe en Bitunix. Removiendo.")
                        closed_assets.append(asset)
                        sig = pos_data.get("signal", {})
                        sig["status"] = "CLOSED"
                        await store.save_signal(sig)
                        await registry.broadcast_global({"type": "signal_auditor_update", "data": sig})

                for asset in closed_assets:
                    del self._active_positions[asset]
                    self.remove_pending_limit_symbol(asset)
                    # 🧹 [SOP-22 PURGA ATÓMICA] Cancelar órdenes huérfanas de ese activo en todos los ejecutores
                    for ex in executors.values():
                        try:
                            await ex.cancel_all_orders_for_symbol(asset)
                        except Exception as purge_err:
                            logger.error(f"❌ [NEXUS SOP-22] Error purgando órdenes huérfanas para {asset}: {purge_err}")

                # 2.1 🛡️ [SOP-22 GHOST ERADICATOR] Purgar cualquier orden CLOSE huérfana de monedas sin posición
                for acc_id, ex in executors.items():
                    try:
                        acc_syms = set(all_account_positions.get(acc_id, {}).keys())
                        await ex.purge_orphaned_close_orders(active_symbols=acc_syms)
                    except Exception as ghost_err:
                        logger.debug(f"[NEXUS SOP-22] Skip erradicación de órdenes fantasma ({acc_id}): {ghost_err}")

                # 3. Añadir a memoria posiciones abiertas en Bitunix que no tenemos registradas (para TODAS las cuentas activas)
                for acc_id, acc_pos_map in all_account_positions.items():
                    target_ex = executors.get(acc_id) or self.executor
                    is_primary_acc = (acc_id == "primary")
                    for symbol, p in acc_pos_map.items():
                        mem_key = symbol if is_primary_acc else f"{acc_id}_{symbol}"
                        alt_key = f"{acc_id}_{symbol}" if is_primary_acc else symbol
                        
                        # Si ya está registrada en memoria bajo cualquiera de las claves, continuar
                        if mem_key in self._active_positions or (is_primary_acc and alt_key in self._active_positions):
                            continue

                        qty = float(p.get("qty", 0))
                        entry_price = float(p.get("avgOpenPrice", 0)) or 1.0
                        raw_side = p.get("side", "BUY").upper()
                        side = "LONG" if raw_side in ("BUY", "LONG") else "SHORT"
                        leverage = int(p.get("leverage", 1))
                        margin = float(p.get("margin", 0))
                        position_id = p.get("positionId", f"manual_{int(time.time())}")

                        logger.info(f"📈 [NEXUS SYNC] [{target_ex.account_label}] Sincronizando posición externa Bitunix: {symbol} ({side})")

                        # 1. Comprobar si la posición YA tiene un Stop Loss activo en Bitunix
                        existing_sl_in_exchange = None
                        pos_direct_sl = p.get("slPrice") or p.get("stopLoss")
                        if pos_direct_sl:
                            try:
                                existing_sl_in_exchange = float(pos_direct_sl)
                            except (ValueError, TypeError):
                                pass

                        if not existing_sl_in_exchange:
                            try:
                                tpsl_chk = await target_ex._request("GET", "/api/v1/futures/tpsl/get_pending_orders", params={"symbol": symbol})
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
                                logger.debug(f"[NEXUS SYNC] [{target_ex.account_label}] Error consultando TPSL existente: {e}")

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
                            logger.info(f"🛡️ [NEXUS SYNC] [{target_ex.account_label}] Posición {symbol} ya cuenta con Stop Loss activo blindado en ${sl_price:.4f}. BE Target: ${be_price:.4f}")
                        elif matching_setup:
                            sl_price = float(matching_setup.get("stop_loss", 0))
                            be_price = float(matching_setup.get("be_price", 0))
                            tp1 = float(matching_setup.get("tp1", 0))
                            tp2 = float(matching_setup.get("tp2", 0))
                            tp3 = float(matching_setup.get("tp3", 0))
                            logger.info(f"💎 [NEXUS SYNC] [{target_ex.account_label}] Setup institucional SMC emparejado para {symbol}: SL: ${sl_price} | BE: ${be_price} | TP1: ${tp1}")
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
                            "id": position_id,
                            "account_id": acc_id
                        }

                        # Si NO tenía Stop Loss en el exchange, colocar el SL inicial
                        protection_ids = []
                        if not existing_sl_in_exchange and sl_price > 0:
                            logger.info(f"🛡️ [NEXUS SYNC] [{target_ex.account_label}] Configurando Stop Loss inicial en Bitunix (SL: ${sl_price:.2f}) para {symbol}...")
                            tpsl_order_id = await target_ex.place_position_tpsl(
                                symbol=symbol,
                                position_id=position_id,
                                sl_price=sl_price,
                                tp_price=None
                            )
                            if tpsl_order_id:
                                protection_ids.append(tpsl_order_id)

                        # 2. Colocar Take Profits límites fragmentados (60% / 20% / 10%) si no existen previamente
                        try:
                            existing_orders_res = await target_ex._request("GET", "/api/v1/futures/trade/get_pending_orders", params={"symbol": symbol})
                            existing_orders = existing_orders_res.get("data", {}).get("orderList", []) if existing_orders_res.get("code") == 0 else []
                            existing_close_orders = [o for o in existing_orders if o.get("reduceOnly") or o.get("tradeSide") == "CLOSE"]
                        except Exception:
                            existing_close_orders = []

                        if not existing_close_orders:
                            q_dec, p_dec = await target_ex.get_symbol_precision(symbol)
                            
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

                                tp_res = await target_ex._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_payload)
                                if tp_res.get("code") != 0 and "positionId" in tp_payload:
                                    del tp_payload["positionId"]
                                    tp_res = await target_ex._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_payload)

                                if tp_res.get("code") == 0:
                                    tp_order_id = tp_res.get("data", {}).get("orderId")
                                    logger.info(f"🎯 [NEXUS SYNC] [{target_ex.account_label}] Orden de {label} límite colocada a ${tp_val:.{p_dec}f} ({tp_qty} unidades) | ID: {tp_order_id}")
                                    protection_ids.append(tp_order_id)
                                else:
                                    logger.error(f"❌ [NEXUS SYNC] [{target_ex.account_label}] Error al colocar {label}: {tp_res.get('msg')}")
                        else:
                            logger.info(f"🛡️ [NEXUS SYNC] [{target_ex.account_label}] {symbol} ya cuenta con {len(existing_close_orders)} órdenes límite de Take Profit activas en Bitunix.")
                            for eo in existing_close_orders:
                                protection_ids.append(eo.get("orderId"))

                        await store.save_signal(reconstructed_signal)
                        pos_entry = {
                            "signal": reconstructed_signal,
                            "execution": {
                                "main_order_id": position_id,
                                "amount": qty,
                                "entry_price": entry_price,
                                "asset": symbol,
                                "protection_orders": protection_ids
                            },
                            "created_timestamp": time.time(),
                            "status": "FILLED",
                            "account_id": acc_id
                        }
                        self._active_positions[mem_key] = pos_entry
                        if is_primary_acc:
                            self._active_positions[f"primary_{symbol}"] = pos_entry
                        from engine.api.registry import registry
                        await registry.broadcast_global({"type": "signal_auditor_update", "data": reconstructed_signal})

                # 4. 🛡️ [AUTO-HEALING RECONCILIATOR]
                # Auditar posiciones activas existentes para auto-reparar cualquier SL o TP faltante en la cuenta correspondiente
                for key, pos_data in list(self._active_positions.items()):
                    try:
                        pos_acc = pos_data.get("account_id", "primary")
                        target_ex = executors.get(pos_acc) or self.executor
                        sig = pos_data.get("signal", {})
                        symbol = sig.get("asset", sig.get("symbol", key.split("_")[-1])).upper()
                        entry_p = float(sig.get("entry_price") or sig.get("price", 0))
                        pos_id = str(pos_data.get("execution", {}).get("main_order_id", ""))
                        pos_qty = float(pos_data.get("execution", {}).get("amount", 0))
                        sl_p = float(sig.get("stop_loss", 0))
                        side = sig.get("signal_type", sig.get("type", "LONG"))

                        # 4.1 Comprobar y auto-reparar Stop Loss si falta
                        if sl_p > 0 and pos_id:
                            chk_tpsl = await target_ex._request("GET", "/api/v1/futures/tpsl/get_pending_orders", params={"symbol": symbol})
                            t_orders = chk_tpsl.get("data", []) or []
                            has_active_sl = any(t.get("slPrice") or t.get("triggerPrice") for t in t_orders) if isinstance(t_orders, list) else False
                            if not has_active_sl:
                                logger.warning(f"🩹 [AUTO-HEALING] [{target_ex.account_label}] Posición {symbol} carece de Stop Loss activo en Bitunix. Auto-reparando SL @ ${sl_p}...")
                                await target_ex.place_position_tpsl(symbol=symbol, position_id=pos_id, sl_price=sl_p)

                        # 4.2 Comprobar y auto-reparar Take Profits límites si faltan
                        tp1_val = float(sig.get("tp1", 0))
                        tp2_val = float(sig.get("tp2", 0))
                        tp3_val = float(sig.get("tp3") or sig.get("take_profit_3r", 0))

                        if tp1_val > 0 and pos_qty > 0 and pos_id:
                            chk_orders_res = await target_ex._request("GET", "/api/v1/futures/trade/get_pending_orders", params={"symbol": symbol})
                            chk_data = chk_orders_res.get("data", {})
                            cur_orders = chk_data.get("orderList", []) if isinstance(chk_data, dict) else (chk_data if isinstance(chk_data, list) else [])
                            close_count = sum(1 for o in cur_orders if o.get("tradeSide") == "CLOSE" or o.get("reduceOnly"))
                            
                            # Si no hay órdenes de cierre y aún no hemos alcanzado TP1, re-colocar la grilla 60/20/20
                            if close_count == 0 and not pos_data.get("smart_trailing", {}).get("be_active"):
                                logger.warning(f"🩹 [AUTO-HEALING] [{target_ex.account_label}] Posición {symbol} no tiene órdenes límite TP en Bitunix. Auto-reparando salidas escalonadas...")
                                q_dec, p_dec = await target_ex.get_symbol_precision(symbol)
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
                                    res_heal = await target_ex._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_pld)
                                    if res_heal.get("code") != 0 and "positionId" in tp_pld:
                                        del tp_pld["positionId"]
                                        res_heal = await target_ex._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_pld)
                                    if res_heal.get("code") == 0:
                                        logger.info(f"✅ [AUTO-HEALING] [{target_ex.account_label}] {symbol} {lbl} colocado a ${p_val:.{p_dec}f} ({q_val} u)")
                                    else:
                                        logger.warning(f"⚠️ [AUTO-HEALING] [{target_ex.account_label}] No se pudo colocar {lbl} para {symbol}: {res_heal.get('msg')}")
                    except Exception as heal_err:
                        logger.error(f"❌ [AUTO-HEALING] Error reconciliando {key}: {heal_err}")

            except Exception as e:
                logger.error(f"❌ [NEXUS SYNC] Error en auto-sincronización: {e}")

            await asyncio.sleep(15)

    MAX_CONCURRENT_POSITIONS = 4
    DEFAULT_MARGIN_USDT = 17.00 # SOP-39: 2.5% de riesgo real para cuenta de $200 USD (~8.5% de margen a ~12X con SL medio)

    def get_unprotected_risk_count(self, account_id: Optional[str] = None) -> int:
        """
        Calcula cuántas posiciones abiertas tienen riesgo real flotante.
        Las posiciones en Breakeven (Fast BE / $0.00 riesgo) LIBERAN su slot de riesgo.
        SOP-45: Soporta aislamiento estricto por account_id.
        """
        unprotected = 0
        counted_symbols = set()

        for key, pos in self._active_positions.items():
            pos_acc = pos.get("account_id", "primary")
            if account_id is not None and pos_acc != account_id:
                continue

            sig = pos.get("signal", {})
            sym = sig.get("asset", sig.get("symbol", key.split("_")[-1])).upper()

            # Evitar contar doble si la posición está registrada como 'XRPUSDT' y 'primary_XRPUSDT'
            acc_sym_key = f"{pos_acc}_{sym}"
            if acc_sym_key in counted_symbols:
                continue
            counted_symbols.add(acc_sym_key)

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

        # ── SOP-31: REGIME QUARANTINE GUARD (ANTI-CHOP) ──
        adx_val = float(signal.get("adx") or 25.0)
        ker_val = float(signal.get("ker") or 0.40)
        is_regime_ok, regime_msg = RiskManager.check_regime_quarantine(adx_val, ker_val)
        if not is_regime_ok:
            logger.warning(f"🛑 [NEXUS SOP-31] Rechazada orden en {asset}: {regime_msg}")
            return

        # ── SOP-33 & SOP-38: ALPHA-TIER KELLY SIZING & SNIPER NY OPEN ──
        from engine.risk.risk_manager import RiskManager
        confluence_val = float(signal.get("confluence_score", 70.0))
        hour_now = datetime.now(timezone.utc).hour
        sizing_mult = RiskManager.calculate_alpha_tier_sizing(asset, confluence_val, hour_utc=hour_now)
        if sizing_mult <= 0.0:
            logger.warning(f"🛑 [NEXUS SOP-33] Omitido activo descalificado: {asset}")
            return

        # ── PROTOCOLO DE SEGURIDAD SOP-08: CLAMP PREVENTIVO DE RIESGO ──
        if float(signal.get("position_size", 0)) > self.DEFAULT_MARGIN_USDT:
            signal["position_size"] = self.DEFAULT_MARGIN_USDT
            signal["position_size_usdt"] = self.DEFAULT_MARGIN_USDT
        if int(signal.get("leverage", 1)) > 20:
            signal["leverage"] = 20

        entry_val = float(signal.get("price") or signal.get("entry_zone_bottom", 0))
        sl_val = float(signal.get("stop_loss", 0))
        
        # ── SOP-21 & SOP-32: INVARIANZA DE LIQUIDACIÓN Y APALANCAMIENTO SEGURO ──
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
            safe_lev = signal["leverage"]

        # 1. Fragmentación Apex (Delta 60/20/20)
        fragments = DeltaOrchestrator.fragment_order(signal)

        # 2. Despacho Multi-Cuenta en Paralelo
        enabled_accounts = self.account_manager.get_all_accounts(enabled_only=True)
        if not enabled_accounts:
            # Fallback a cuenta primaria (.env) si no hay registradas
            from engine.execution.account_manager import BitunixAccountConfig
            fallback_acc = BitunixAccountConfig(
                account_id="primary",
                label="Cuenta Principal",
                api_key="",
                secret_key="",
                dry_run=self.dry_run,
                is_primary=True
            )
            await self._execute_signal_for_account(self.executor, fallback_acc, signal, safe_lev, entry_val, sl_val, fragments)
        else:
            tasks = []
            for acc in enabled_accounts:
                ex = self.account_manager.get_executor(acc.account_id) or self.executor
                tasks.append(self._execute_signal_for_account(ex, acc, signal, safe_lev, entry_val, sl_val, fragments))
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_signal_for_account(
        self,
        executor: BitunixExecutor,
        account: Any,
        signal: Dict[str, Any],
        safe_lev: int,
        entry_val: float,
        sl_val: float,
        fragments: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Ejecuta una señal de mercado en una cuenta específica con su propio cálculo de riesgo SOP-41."""
        acc_signal = dict(signal)
        asset = acc_signal.get("asset")
        acc_id = getattr(account, "account_id", "primary")

        # 1. Regla de Riesgo Aislada por Cuenta: Máximo 4 operaciones con riesgo flotante
        unprotected_count = self.get_unprotected_risk_count(account_id=acc_id)
        if unprotected_count >= self.MAX_CONCURRENT_POSITIONS:
            logger.warning(f"🛑 [NEXUS RIESGO] [{account.label}] Límite de {self.MAX_CONCURRENT_POSITIONS} operaciones en riesgo alcanzado ({unprotected_count} activas). Rechazando entrada en {asset}.")
            return None

        # 1.1 🛡️ DEDUP GUARD EN MEMORIA: Evitar abrir si ya existe posición registrada para esta cuenta
        acc_pos_key = f"{acc_id}_{asset}"
        if acc_pos_key in self._active_positions or (acc_id == "primary" and asset in self._active_positions):
            logger.warning(f"🛑 [NEXUS DEDUP GUARD MEM] [{account.label}] Rechazando orden a mercado en {asset}: Posición ya registrada en memoria interna.")
            return None

        # 1.2 🛡️ DEDUP GUARD EN VIVO BITUNIX (Defensa en profundidad): Consultar el exchange directamente
        if not executor.dry_run:
            try:
                open_pos = await executor.get_pending_positions()
                if open_pos and any(p.get("symbol") == asset for p in open_pos):
                    logger.warning(f"🛑 [NEXUS DEDUP GUARD EXCHANGE] [{account.label}] Rechazando orden a mercado en {asset}: Ya existe una posición abierta en Bitunix.")
                    return None
            except Exception as chk_err:
                logger.debug(f"[NEXUS DEDUP GUARD] [{account.label}] Error al verificar posiciones pendientes en Bitunix: {chk_err}")

        try:
            avail_margin = await executor.get_available_margin_usdt()
        except Exception:
            avail_margin = 0.0
        if avail_margin <= 0 and executor.dry_run:
            avail_margin = 82.23

        if avail_margin <= 0:
            logger.warning(f"🛑 [NEXUS MULTI-ACCOUNT] [{account.label}] Saldo insuficiente o no verificado para {asset}: ${avail_margin:.2f} USDT.")
            return None

        if sl_val > 0 and entry_val > 0:
            qty_decimals, _ = await executor.get_symbol_precision(asset)
            
            # SOP-43: Quarter-Kelly Asymmetric Risk Scaling (unless explicitly overridden in signal/account)
            base_acc_risk = getattr(account, "risk_pct", 0.025)
            if "risk_pct" in signal and signal.get("risk_pct") is not None:
                dyn_risk_pct = float(signal["risk_pct"])
            else:
                confluence_score = float(signal.get("confluence_score", 70.0))
                hour_now = datetime.now(timezone.utc).hour
                dyn_risk_pct = RiskManager.calculate_quarter_kelly_risk(
                    base_risk_pct=base_acc_risk,
                    symbol=asset,
                    confluence_score=confluence_score,
                    hour_utc=hour_now
                )
            
            risk_calc = RiskManager.calculate_dollar_risk_position(
                account_balance=avail_margin,
                risk_pct=dyn_risk_pct,
                entry_price=entry_val,
                sl_price=sl_val,
                leverage=safe_lev,
                max_notional_mult=getattr(account, "max_notional_mult", 5.0),
                qty_decimals=qty_decimals
            )
            if not risk_calc["approved"]:
                logger.warning(f"🛑 [NEXUS SOP-41] [{account.label}] Orden rechazada para {asset}: {risk_calc['reason']}")
                return None

            # SOP-44: Portfolio Heat Check (Directional Heat Cap @ 7.5% isolated per account)
            pos_risk_usd = risk_calc["projected_loss"]
            sig_side = str(signal.get("type", signal.get("signal_type", "LONG"))).upper()
            acc_id = getattr(account, "account_id", "primary")
            is_heat_ok, heat_msg, _ = RiskManager.check_portfolio_heat(
                active_positions=self._active_positions,
                new_direction=sig_side,
                new_trade_risk_usd=pos_risk_usd,
                account_balance=avail_margin,
                max_heat_pct=0.075,
                account_id=acc_id
            )
            if not is_heat_ok:
                logger.warning(f"🛑 [NEXUS SOP-44] [{account.label}] {heat_msg}")
                return None

            req_margin = risk_calc["required_margin"]
            acc_signal["position_size"] = req_margin
            acc_signal["position_size_usdt"] = req_margin
            acc_signal["exact_qty"] = risk_calc["qty"]
            acc_signal["leverage"] = safe_lev
            logger.info(f"💎 [NEXUS SOP-41/43/44] [{account.label}] {asset} -> Qty: {risk_calc['qty']} | Margen: ${req_margin:.2f} USDT | Riesgo Dinámico: {dyn_risk_pct*100:.2f}% (${risk_calc['projected_loss']:.2f} USDT)")
        else:
            req_margin = self.DEFAULT_MARGIN_USDT
            acc_signal["position_size"] = req_margin
            acc_signal["position_size_usdt"] = req_margin
            acc_signal["leverage"] = safe_lev

        if getattr(account, "is_primary", False) or getattr(account, "account_id", "") in ("primary", ""):
            signal["position_size"] = req_margin
            signal["position_size_usdt"] = req_margin
            if "exact_qty" in acc_signal:
                signal["exact_qty"] = acc_signal["exact_qty"]
            signal["leverage"] = safe_lev

        # SOP-40 Buffer guardrail
        if not executor.dry_run:
            min_buffer = min(50.0, avail_margin * 0.50)
            if (avail_margin - req_margin) < min_buffer:
                logger.warning(f"🛑 [NEXUS BUFFER GUARD] [{account.label}] Buffer insuficiente para {asset}: Remanente ${avail_margin - req_margin:.2f} < Min ${min_buffer:.2f} USDT.")
                return None

        try:
            result = await executor.execute_signal(acc_signal, fragments=fragments)
            if result.get("status") == "success":
                logger.info(f"✅ [NEXUS] [{account.label}] Posición abierta en {asset}. ID: {result.get('main_order_id')}")
                pos_entry = {
                    "signal": acc_signal,
                    "execution": result,
                    "created_timestamp": time.time(),
                    "status": "OPEN",
                    "account_id": getattr(account, "account_id", "primary")
                }
                if getattr(account, "is_primary", False) or getattr(account, "account_id", "") in ("primary", ""):
                    self._active_positions[asset] = pos_entry
                self._active_positions[f"{getattr(account, 'account_id', 'primary')}_{asset}"] = pos_entry
                return result
            else:
                logger.error(f"❌ [NEXUS] [{account.label}] Error al abrir posición en {asset}: {result.get('message')}")
                return result
        except Exception as e:
            logger.error(f"💥 [NEXUS] [{account.label}] Error crítico procesando señal en {asset}: {e}")
            return None

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

        # ── SOP-31: REGIME QUARANTINE GUARD (ANTI-CHOP) ──
        adx_val = float(signal.get("adx") or 25.0)
        ker_val = float(signal.get("ker") or 0.40)
        is_regime_ok, regime_msg = RiskManager.check_regime_quarantine(adx_val, ker_val)
        if not is_regime_ok:
            logger.info(f"🛑 [NEXUS AUTO-LIMIT SOP-31] Omitida orden límite para {asset}: {regime_msg}")
            return

        try:
            # ── SOP-33 & SOP-38: ALPHA-TIER KELLY SIZING & SNIPER NY OPEN ──
            from engine.risk.risk_manager import RiskManager
            confluence_val = float(signal.get("confluence_score", 70.0))
            hour_now = datetime.now(timezone.utc).hour
            sizing_mult = RiskManager.calculate_alpha_tier_sizing(asset, confluence_val, hour_utc=hour_now)
            if sizing_mult <= 0.0:
                logger.debug(f"[NEXUS AUTO-LIMIT SOP-33] Omitido activo descalificado: {asset}")
                return
                
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
                safe_lev = 10

            # ── DESPACHO MULTI-CUENTA EN PARALELO (AUTO-LIMIT) ──
            enabled_accounts = self.account_manager.get_all_accounts(enabled_only=True)
            if not enabled_accounts:
                from engine.execution.account_manager import BitunixAccountConfig
                fallback_acc = BitunixAccountConfig(
                    account_id="primary",
                    label="Cuenta Principal",
                    api_key="",
                    secret_key="",
                    dry_run=self.dry_run,
                    is_primary=True
                )
                await self._place_limit_for_account(self.executor, fallback_acc, signal, safe_lev, entry_p, sl_p)
            else:
                tasks = []
                for acc in enabled_accounts:
                    ex = self.account_manager.get_executor(acc.account_id) or self.executor
                    tasks.append(self._place_limit_for_account(ex, acc, signal, safe_lev, entry_p, sl_p))
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"❌ [NEXUS AUTO-LIMIT] Error colocando orden en {asset}: {e}")

    async def _place_limit_for_account(
        self,
        executor: BitunixExecutor,
        account: Any,
        signal: Dict[str, Any],
        safe_lev: int,
        entry_p: float,
        sl_p: float
    ) -> Optional[Dict[str, Any]]:
        """Coloca una orden límite en una cuenta específica con su propio cálculo de riesgo SOP-41."""
        acc_signal = dict(signal)
        asset = acc_signal.get("asset", acc_signal.get("symbol", "")).upper()
        acc_id = getattr(account, "account_id", "primary")

        # 1. Regla de Riesgo por cuenta: Máximo 4 operaciones con riesgo flotante para esta cuenta
        unprotected_count = self.get_unprotected_risk_count(account_id=acc_id)
        if unprotected_count >= self.MAX_CONCURRENT_POSITIONS:
            logger.info(f"🛑 [NEXUS AUTO-LIMIT RIESGO] [{account.label}] Máximo de {self.MAX_CONCURRENT_POSITIONS} operaciones con riesgo alcanzado ({unprotected_count} activas). Pausando nuevas órdenes.")
            return None

        # 2. Verificar si esta cuenta específica ya tiene una posición activa en este activo
        acc_pos_key = f"{acc_id}_{asset}"
        if acc_pos_key in self._active_positions or (acc_id == "primary" and asset in self._active_positions):
            logger.debug(f"[NEXUS AUTO-LIMIT] [{account.label}] Omitiendo orden límite: Posición ya activa para {asset}.")
            return None

        # 2.1 🛡️ DEDUP GUARD EN VIVO BITUNIX: Si ya hay una posición abierta en el exchange, no colocar orden límite
        if not executor.dry_run:
            try:
                open_pos = await executor.get_pending_positions()
                if open_pos and any(p.get("symbol") == asset for p in open_pos):
                    logger.debug(f"[NEXUS AUTO-LIMIT] [{account.label}] Omitiendo orden límite: Ya existe una posición abierta en Bitunix para {asset}.")
                    return None
            except Exception as chk_err:
                logger.debug(f"[NEXUS AUTO-LIMIT] [{account.label}] Error al verificar posiciones en Bitunix: {chk_err}")

        # Verificar órdenes pendientes en Bitunix para esta cuenta específica para no duplicar en el libro
        try:
            acc_pending = await executor.get_pending_orders(asset)
            if acc_pending:
                logger.debug(f"[NEXUS AUTO-LIMIT] [{account.label}] Ya existe orden límite pendiente en Bitunix para {asset}.")
                self._pending_limit_symbols.add(asset)
                return None
        except Exception as pe_err:
            logger.debug(f"[NEXUS AUTO-LIMIT] [{account.label}] Error verificando órdenes pendientes: {pe_err}")

        try:
            avail_margin = await executor.get_available_margin_usdt()
        except Exception:
            avail_margin = 0.0
        if avail_margin <= 0 and executor.dry_run:
            avail_margin = 82.23

        if avail_margin <= 0:
            logger.debug(f"[NEXUS AUTO-LIMIT] [{account.label}] Saldo insuficiente o no verificado para {asset}: ${avail_margin:.2f} USDT.")
            return None

        qty_decimals, _ = await executor.get_symbol_precision(asset)
        risk_calc = RiskManager.calculate_dollar_risk_position(
            account_balance=avail_margin,
            risk_pct=getattr(account, "risk_pct", 0.025),
            entry_price=entry_p,
            sl_price=sl_p,
            leverage=safe_lev,
            max_notional_mult=getattr(account, "max_notional_mult", 5.0),
            qty_decimals=qty_decimals
        )
        if not risk_calc["approved"]:
            logger.debug(f"[NEXUS AUTO-LIMIT] [{account.label}] Orden rechazada para {asset}: {risk_calc['reason']}")
            return None

        req_margin = risk_calc["required_margin"]
        acc_signal["position_size"] = req_margin
        acc_signal["position_size_usdt"] = req_margin
        acc_signal["exact_qty"] = risk_calc["qty"]
        acc_signal["leverage"] = safe_lev

        if getattr(account, "is_primary", False) or getattr(account, "account_id", "") in ("primary", ""):
            signal["position_size"] = req_margin
            signal["position_size_usdt"] = req_margin
            signal["exact_qty"] = risk_calc["qty"]
            signal["leverage"] = safe_lev

        # SOP-40 Buffer guardrail
        if not executor.dry_run:
            min_buffer = min(50.0, avail_margin * 0.50)
            if (avail_margin - req_margin) < min_buffer:
                logger.info(f"🛑 [NEXUS AUTO-LIMIT BUFFER GUARD] [{account.label}] Buffer insuficiente para {asset}: Remanente ${avail_margin - req_margin:.2f} < Min ${min_buffer:.2f} USDT.")
                return None

        logger.info(f"🎯 [NEXUS AUTO-LIMIT] [{account.label}] Enviando orden límite a Bitunix para {asset} @ ${entry_p:.2f} (Qty: {risk_calc['qty']} | Margen: ${req_margin} USDT @ {safe_lev}x | Riesgo Max: ${risk_calc['projected_loss']:.2f} USDT)")
        res = await executor.place_limit_signal(acc_signal)
        if res.get("status") == "success":
            self._pending_limit_symbols.add(asset)
            logger.info(f"✅ [NEXUS AUTO-LIMIT] [{account.label}] Orden límite para {asset} colocada exitosamente en Bitunix! ID: {res.get('order_id')}")
        else:
            logger.warning(f"⚠️ [NEXUS AUTO-LIMIT] [{account.label}] No se pudo colocar orden límite en {asset}: {res.get('message')}")
        return res

    def remove_pending_limit_symbol(self, symbol: str):
        """Libera el activo del conjunto de órdenes pendientes en memoria."""
        sym_clean = symbol.replace('/', '').upper()
        self._pending_limit_symbols.discard(sym_clean)

    async def purge_all_pending_limit_orders(self, reason: str = "SLOT_OVERLOAD"):
        """
        [SAFETY PURGE] Cancela todas las órdenes límite pendientes en Bitunix
        cuando se alcanza el límite de riesgo o por invalidación global en todas las cuentas (SOP-45).
        """
        logger.warning(f"🛡️ [NEXUS PURGE] Iniciando purga de órdenes límite pendientes. Razón: {reason}")
        try:
            executors = self.account_manager.get_all_executors(enabled_only=True)
            if not executors:
                executors = {"primary": self.executor}

            for acc_id, ex in executors.items():
                try:
                    pending_orders = await ex.get_pending_orders()
                    if not pending_orders:
                        continue
                    open_limits = [
                        o for o in pending_orders 
                        if (o.get("tradeSide") == "OPEN" or not o.get("reduceOnly")) and o.get("orderType") == "LIMIT"
                    ]
                    for o in open_limits:
                        sym = o.get("symbol")
                        oid = o.get("orderId")
                        if sym and oid:
                            await ex.cancel_limit_order(sym, oid)
                            self.remove_pending_limit_symbol(sym)
                            logger.info(f"🧹 [NEXUS PURGE] [{ex.account_label}] Orden límite sobrante {oid} ({sym}) cancelada por seguridad ({reason}).")
                except Exception as ex_err:
                    logger.warning(f"❌ [NEXUS PURGE] Error purgando límites para {acc_id}: {ex_err}")
        except Exception as e:
            logger.error(f"❌ [NEXUS PURGE] Error en purga de órdenes límite: {e}")

    def get_active_positions(self):
        return self._active_positions

# Instancia global (Singleton)
# Live trading must be explicitly enabled from .env.
nexus = NexusNode(dry_run=not settings.ENABLE_LIVE_TRADING)

