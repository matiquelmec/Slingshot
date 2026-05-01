"""
engine/execution/omega_listener.py — v8.2.0 (OMEGA Centinel Live Sync)
========================================================================
Vigilancia activa de posiciones y gestión de riesgo en tiempo real.
Conectado con el Store para simular o procesar ejecuciones Reales/Paper.
"""
from engine.core.logger import logger
from engine.api.config import settings
from engine.core.store import store

class OmegaCentinel:
    """
    EL CENTINELA DE SOMBRA.
    Vigila el precio en vivo y actualiza el estado de las órdenes en el Store,
    luego dispara Webhooks de UI para OMEGA Dashboard.
    """
    def __init__(self):
        self.daily_pnl = 0.0
        self.max_daily_drawdown = -0.035 # -3.5%
        self.is_locked = False
        self.last_update_ts = 0

    async def check_live_price(self, symbol: str, current_price: float, broadcaster) -> None:
        """
        Llamado en cada tick desde el websocket.
        Examina las señales pendientes y cambia sus estados si el precio las toca.
        """
        if self.is_locked:
            return

        active_signals = await store.get_signals(asset=symbol)
        if not active_signals:
            return

        updated_any = False
        
        for sig in active_signals:
            status = sig.get("status", "ACTIVE")
            
            # Las señales nuevas empiezan en "ACTIVE" (que para nosotros es PENDING ENTRY)
            # En v8, vamos a considerar que una señal en Radar = PENDING, y FILLED = OMEGA ACTIVA.
            signal_type = sig.get("signal_type", "LONG").upper()
            ez_bottom = float(sig.get("entry_zone_bottom", sig.get("price", 0)))
            ez_top = float(sig.get("entry_zone_top", sig.get("price", 0)))
            entry_price = float(sig.get("price", 0))
            sl = float(sig.get("stop_loss", 0))
            tp1 = float(sig.get("tp1", 0))
            tp2 = float(sig.get("tp2", 0))
            tp3 = float(sig.get("tp3", 0))

            changed = False

            # FASE 1: TRIGGER PENDING -> FILLED
            if status == "ACTIVE":
                margin = (ez_top - ez_bottom) * 0.1 # Pequeño margen
                if signal_type == "LONG" and (current_price <= ez_top + margin):
                    sig["status"] = "FILLED"
                    sig["shield_active"] = False
                    sig["profit_locked"] = False
                    logger.info(f"⚡ [OMEGA] {symbol} {signal_type} PENDING -> FILLED @ {current_price}")
                    changed = True
                elif signal_type == "SHORT" and (current_price >= ez_bottom - margin):
                    sig["status"] = "FILLED"
                    sig["shield_active"] = False
                    sig["profit_locked"] = False
                    logger.info(f"⚡ [OMEGA] {symbol} {signal_type} PENDING -> FILLED @ {current_price}")
                    changed = True

            # FASE 2: GESTIÓN DE POSICIÓN ABIERTA (FILLED)
            elif status == "FILLED":
                # Check Stop Loss Invalidation
                if signal_type == "LONG" and current_price <= sl:
                     sig["status"] = "STOPPED_OUT"
                     logger.warning(f"🛑 [OMEGA] {symbol} LONG STOPPED OUT @ {current_price}")
                     changed = True
                     # Restar al max daily drawdown
                elif signal_type == "SHORT" and current_price >= sl:
                     sig["status"] = "STOPPED_OUT"
                     logger.warning(f"🛑 [OMEGA] {symbol} SHORT STOPPED OUT @ {current_price}")
                     changed = True

                # Check TP1 -> SHIELD ACTIVATION
                if not sig.get("shield_active"):
                    if signal_type == "LONG" and current_price >= tp1:
                        sig["shield_active"] = True
                        sig["sl_dynamic"] = entry_price # Break-even
                        logger.info(f"🛡️ [OMEGA] {symbol} LONG hit TP1 @ {current_price}. SHIELD ACTIVATED (SL -> BE)!")
                        changed = True
                    elif signal_type == "SHORT" and current_price <= tp1:
                        sig["shield_active"] = True
                        sig["sl_dynamic"] = entry_price
                        logger.info(f"🛡️ [OMEGA] {symbol} SHORT hit TP1 @ {current_price}. SHIELD ACTIVATED (SL -> BE)!")
                        changed = True

                # Check TP2 -> PROFIT LOCK
                if sig.get("shield_active") and not sig.get("profit_locked"):
                     if signal_type == "LONG" and current_price >= tp2:
                         sig["profit_locked"] = True
                         sig["sl_dynamic"] = tp1
                         logger.info(f"🔒 [OMEGA] {symbol} LONG hit TP2 @ {current_price}. PROFITS LOCKED (SL -> TP1)!")
                         changed = True
                     elif signal_type == "SHORT" and current_price <= tp2:
                         sig["profit_locked"] = True
                         sig["sl_dynamic"] = tp1
                         logger.info(f"🔒 [OMEGA] {symbol} SHORT hit TP2 @ {current_price}. PROFITS LOCKED (SL -> TP1)!")
                         changed = True

                # Check TP3 -> CLOSED
                if signal_type == "LONG" and current_price >= tp3:
                     sig["status"] = "CLOSED_TP_MAX"
                     changed = True
                     logger.info(f"✅ [OMEGA] {symbol} LONG FULL TAKE PROFIT MARGIN @ {current_price}!")
                elif signal_type == "SHORT" and current_price <= tp3:
                     sig["status"] = "CLOSED_TP_MAX"
                     changed = True
                     logger.info(f"✅ [OMEGA] {symbol} SHORT FULL TAKE PROFIT MARGIN @ {current_price}!")

            # Si algo cambió, re-guardamos en el store y emitimos
            if changed:
                sig["current_price"] = current_price
                await store.save_signal(sig)
                from engine.api.registry import registry
                await registry.broadcast_global({"type": "execution_update", "data": sig})
                # También notificamos al Radar Feed como un update de auditoría
                await registry.broadcast_global({"type": "signal_auditor_update", "data": sig})
                updated_any = True

# Instancia global centinela
omega_centinel = OmegaCentinel()

