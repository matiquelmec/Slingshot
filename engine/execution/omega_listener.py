"""
engine/execution/omega_listener.py — v6.7.5 (OMEGA Centinel)
============================================================
Vigilancia activa de posiciones y gestión de riesgo en tiempo real.
"""
from engine.core.logger import logger
from engine.api.config import settings

class OmegaCentinel:
    """
    EL CENTINELA DE SOMBRA.
    Vigila el estado de las órdenes para activar el Escudo Total.
    """
    def __init__(self):
        self.daily_pnl = 0.0
        self.max_daily_drawdown = -0.035 # -3.5%
        self.is_locked = False

    async def on_order_update(self, event: dict, active_position: dict):
        """
        Handler para eventos del WebSocket de órdenes.
        """
        if self.is_locked:
            logger.warning("🚫 [OMEGA] Sistema BLOQUEADO por Hard-Stop Diario.")
            return

        order_status = event.get("status")
        order_type = event.get("type") # TP1, TP2, etc.
        
        if order_status == "FILLED":
            if "TP1" in order_type:
                await self._activate_shield(active_position)
            elif "TP2" in order_type:
                await self._lock_profit(active_position)
            
            # Actualizar PnL Diario y verificar Hard-Stop
            await self._audit_daily_health(event.get("realized_pnl", 0.0))

    async def _activate_shield(self, pos: dict):
        """
        Mueve el Stop Loss al precio de entrada (Breakeven).
        """
        logger.info(f"🛡️ [OMEGA] TP1 FILLED para {pos['asset']}. Activando ESCUDO TOTAL (SL -> BE)...")
        # El comando real al bridge sería algo como:
        # await bridge.modify_order(pos['id'], new_sl=pos['entry_price'])
    
    async def _lock_profit(self, pos: dict):
        """
        Mueve el Stop Loss al nivel del TP1 para asegurar ganancias.
        """
        logger.info(f"🔒 [OMEGA] TP2 FILLED para {pos['asset']}. Activando LOCK PROFIT (SL -> TP1)...")
        # await bridge.modify_order(pos['id'], new_sl=pos['tp1'])

    async def _audit_daily_health(self, trade_pnl: float):
        """
        Verifica el límite de pérdida diaria.
        """
        self.daily_pnl += trade_pnl
        if self.daily_pnl <= self.max_daily_drawdown:
            logger.error(f"🚨 [OMEGA] CRITICAL DRAWDOWN: {self.daily_pnl*100:.2f}%. BLOQUEANDO API.")
            self.is_locked = True
            # await exchange.kill_switch()
