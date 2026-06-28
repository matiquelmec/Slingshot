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


class NexusNode:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.executor = BitunixExecutor(dry_run=dry_run)
        self._active_positions = {}
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

                    # 2. Verificar si se ha alcanzado el TP1 para mover a BE
                    be_active = pos.get("smart_trailing", {}).get("be_active", False)

                    if not be_active:
                        target_hit = (current_price >= tp1) if is_long else (current_price <= tp1)
                        if target_hit:
                            logger.info(f"🎯 [OMEGA] {asset} alcanzó TP1. Activando SMART TRAILING (Mover a BE)...")
                            # Mover SL a Entry + Pequeño buffer para comisiones
                            new_sl = entry * 1.0005 if is_long else entry * 0.9995

                            # Cancelar SL antiguo y colocar nuevo en vivo
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

                            if new_sl_id:
                                if protection_orders:
                                    pos["execution"]["protection_orders"][0] = new_sl_id
                                pos["signal"]["stop_loss"] = new_sl
                                pos["smart_trailing"] = {"be_active": True, "trailing_active": True}
                                logger.info(f"🛡️ [OMEGA] SL de {asset} movido a BE de forma real: ${new_sl:.2f}")

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


                    # 3. Verificar si la posición se ha cerrado (SL o TP3 final hit)
                    # Esto es una simplificación; un sistema real monitorearía WebSockets de órdenes
                    # 3. Verificar si la posición se ha cerrado (SL o TP3 final hit)
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
                        from engine.api.registry import registry
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
                        from engine.api.registry import registry
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
                        sl_price = entry_price * 0.98 if side == "LONG" else entry_price * 1.02
                        tp1 = entry_price * 1.02 if side == "LONG" else entry_price * 0.98
                        tp2 = entry_price * 1.04 if side == "LONG" else entry_price * 0.96
                        tp3 = entry_price * 1.06 if side == "LONG" else entry_price * 0.94

                        reconstructed_signal = {
                            "asset": symbol,
                            "interval": "15m",
                            "signal_type": side,
                            "type": side,
                            "entry_price": entry_price,
                            "price": entry_price,
                            "stop_loss": sl_price,
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

                        # 1. Colocar orden de proteccion de posicion (Solo SL) en Bitunix
                        protection_ids = []
                        logger.info(f"🛡️ [NEXUS SYNC] Colocando Stop Loss de posicion en Bitunix (SL: ${sl_price:.2f}) para posicion manual de {symbol}...")
                        tpsl_order_id = await self.executor.place_position_tpsl(
                            symbol=symbol,
                            position_id=position_id,
                            sl_price=sl_price,
                            tp_price=None
                        )
                        if tpsl_order_id:
                            protection_ids.append(tpsl_order_id)

                        # 2. Colocar Take Profits limites fragmentados (60% / 20% / 20%)
                        close_side = "SELL" if side == "LONG" else "BUY"
                        f1 = round(qty * 0.60, 4)
                        f2 = round(qty * 0.20, 4)
                        f3 = round(qty - f1 - f2, 4)
                        tps = [(tp1, f1, "TP1"), (tp2, f2, "TP2"), (tp3, f3, "TP3")]

                        for tp_val, tp_qty, label in tps:
                            if tp_qty <= 0:
                                continue
                            tp_payload = {
                                "symbol": symbol,
                                "qty": str(tp_qty),
                                "price": str(round(tp_val, 2)),
                                "side": close_side,
                                "tradeSide": "CLOSE",
                                "orderType": "LIMIT",
                                "effect": "GTC",
                                "positionId": position_id
                            }
                            tp_res = await self.executor._request("POST", "/api/v1/futures/trade/place_order", json_body=tp_payload)
                            if tp_res.get("code") == 0:
                                tp_order_id = tp_res.get("data", {}).get("orderId")
                                logger.info(f"🎯 [NEXUS SYNC] Orden de {label} limite colocada a ${tp_val:.2f} | ID: {tp_order_id}")
                                protection_ids.append(tp_order_id)
                            else:
                                logger.error(f"❌ [NEXUS SYNC] Error al colocar {label}: {tp_res.get('msg')}")

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

            except Exception as e:
                logger.error(f"❌ [NEXUS SYNC] Error en auto-sincronización: {e}")

            await asyncio.sleep(10)

    async def process_signal(self, signal: Dict[str, Any]):
        """
        Punto de entrada para señales reales.
        """
        asset = signal.get("asset")
        sig_type = signal.get("type", "LONG")

        logger.info(f"⚡ [NEXUS] Recibida señal de alta fidelidad: {asset} {sig_type}")

        # 1. Fragmentación Apex (Delta 60/20/20)
        fragments = DeltaOrchestrator.fragment_order(signal)

        # 2. Ejecución de la Grilla
        try:
            result = await self.executor.execute_signal(signal, fragments=fragments)

            if result.get("status") == "success":
                logger.info(f"✅ [NEXUS] Posición abierta en {asset}. ID: {result.get('main_order_id')}")
                
                # [OMEGA INJECT UPDATE] Actualizar estado de señal a FILLED y transmitir inmediatamente
                signal["status"] = "FILLED"
                await store.save_signal(signal)
                from engine.api.registry import registry
                await registry.broadcast_global({"type": "signal_auditor_update", "data": signal})

                self._active_positions[asset] = {
                    "signal": signal,
                    "execution": result,
                    "status": "OPEN"
                }
            else:
                logger.error(f"❌ [NEXUS] Error al abrir posición en {asset}: {result.get('message')}")

        except Exception as e:
            logger.error(f"💥 [NEXUS] Error crítico procesando señal: {e}")

    def get_active_positions(self):
        return self._active_positions

# Instancia global (Singleton)
# Live trading must be explicitly enabled from .env.
nexus = NexusNode(dry_run=not settings.ENABLE_LIVE_TRADING)

