import asyncio
from engine.core.logger import logger
from engine.core.store import store
from engine.api.json_utils import sanitize_for_json
from engine.indicators.ghost_data import refresh_ghost_data

class BroadcasterDispatcher:
    """
    Gestiona la distribución de mensajes a los suscriptores y la sincronización del estado con el Store.
    """
    def __init__(self, state, subscribers, lock, broadcaster):
        self.state = state
        self.subscribers = subscribers
        self.lock = lock
        self.bc = broadcaster

    async def broadcast(self, message: dict):
        """Envía un mensaje a TODOS los suscriptores activos y cachea el estado clave."""
        clean = sanitize_for_json(message)
        msg_type = clean.get("type", "")
        
        # Seguridad: Evitar fugas de datos (Leaks)
        if msg_type == "tactical_update":
            payload = clean.get("data", {})
            asset = payload.get("asset") if isinstance(payload, dict) else "?"
            if asset and asset != self.state.symbol and asset != "?":
                logger.error(f"🚨 [LEAK] {self.state.symbol} intentó emitir payload de {asset}! Bloqueando.")
                return

        # Sincronización de Estado y Almacén
        await self._sync_state(msg_type, clean)
        
        # Envío a suscriptores
        dead = []
        async with self.lock:
            clients = dict(self.subscribers)
            
        for cid, q in clients.items():
            try:
                q.put_nowait(clean)
            except asyncio.QueueFull:
                dead.append(cid)
                
        if dead:
            async with self.lock:
                for cid in dead:
                    self.subscribers.pop(cid, None)
                    logger.info(f"[DISPATCHER] {self.state.symbol} → cliente {cid[:6]} eliminado (queue llena)")

    async def _sync_state(self, msg_type: str, clean: dict):
        """Actualiza el caché local y el store global según el tipo de mensaje."""
        data = clean.get("data", {})
        
        if msg_type == "ghost_update":     
            self.state.last_ghost = clean
            await store.update_market_state(self.state.symbol, {
                "macro_bias": data.get("macro_bias"),
                "dxy_trend":  data.get("dxy_trend"),
                "risk_appetite": data.get("risk_appetite")
            })
        elif msg_type == "smc_data":       
            self.state.last_smc = clean
            obs = data.get("order_blocks", {})
            fvgs = data.get("fvgs", {})
            await store.update_market_state(self.state.symbol, {
                "ob_bullish_count": len(obs.get("bullish", [])),
                "ob_bearish_count": len(obs.get("bearish", [])),
                "fvg_bullish_active": len(fvgs.get("bullish", [])) > 0,
                "fvg_bearish_active": len(fvgs.get("bearish", [])) > 0
            })
        elif msg_type == "tactical_update":
            self.state.last_tactical = clean
            conf = data.get("confluence", {})
            await store.update_market_state(self.state.symbol, {
                "regime":        data.get("market_regime"),
                "strategy":      data.get("active_strategy"),
                "price":         float(data.get("current_price", 0)),
                "in_killzone":   any(f.get("factor") == "Liquidez/KZ" and f.get("status") == "CONFIRMADO" for f in conf.get("checklist", [])),
                "macro_risk":    any(f.get("factor") == "Macro Calendar" and f.get("status") == "PRECAUCIÓN" for f in conf.get("checklist", [])),
                "liq_magnet":    any(f.get("factor") == "Liq Clusters" and f.get("status") == "CONFIRMADO" for f in conf.get("checklist", []))
            })
        elif msg_type == "session_update": 
            self.state.last_session = clean
            await store.update_market_state(self.state.symbol, {"session": data.get("current_session")})
        elif msg_type == "advisor_update":
            self.state.last_advisor = clean
        elif msg_type == "neural_pulse":
            ml = data.get("ml_projection", {})
            if ml:
                await store.update_market_state(self.state.symbol, {
                    "ml_dir": ml.get("direction"),
                    "ml_prob": ml.get("probability")
                })
                # Auto-briefing inicial
                if not self.state.first_advisor_done and self.state.last_tactical:
                    self.state.first_advisor_done = True
                    from engine.core.session_manager import SessionManager
                    asyncio.create_task(self.bc._emit_advisor(self.state.last_tactical, self.state.last_session or {}))
        elif msg_type == "liquidation_update":
            self.state.last_liquidations = clean
            await store.update_liquidation_clusters(self.state.symbol, data)
        elif msg_type == "candle":
            await store.save_candle(self.state.symbol, self.state.interval, clean)
            await store.update_market_state(self.state.symbol, {"price": float(data.get("close", 0))})
        elif msg_type == "onchain_update":
            self.state.last_onchain = clean
            # 🟢 Sincronización con el store global para el Radar Center
            await store.update_market_state(self.state.symbol, {
                "funding_rate": data.get("funding_rate", 0),
                "oi_delta_pct": data.get("oi_delta_pct", 0),
                "onchain_bias": data.get("onchain_bias", "NEUTRAL")
            })
