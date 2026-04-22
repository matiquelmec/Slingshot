import asyncio
import uuid
from typing import Dict, Optional
from engine.core.logger import logger
from engine.core.store import store

class BroadcasterRegistry:
    """
    Registro global de SymbolBroadcasters.
    Crea un broadcaster cuando el primer cliente se conecta a un símbolo.
    Lo destruye automáticamente (Grace Period) cuando el último cliente desconecta.
    """

    def __init__(self):
        self._broadcasters: Dict[str, any] = {} # Evitar import circular
        self._lock = asyncio.Lock()
        self._pulse_task: Optional[asyncio.Task] = None
        self._simulation_task: Optional[asyncio.Task] = None
        self._last_radar_summary: Optional[list] = None
        
        # 📊 Métricas de Simulación Sigma (v6.0)
        self._metrics = {
            "auth_ok": 0,
            "auth_fail": 0,
            "latency_sum": 0.0,
            "latency_count": 0,
            "vetoes": [] # (symbol, reason)
        }

    def set_broadcasters(self, b_dict):
        """Inyección para resolver dependencias circulares temporalmente."""
        self._broadcasters = b_dict

    async def start_global_pulse(self):
        """Inicia el latido global que sincroniza el estado de todos los radares."""
        if self._pulse_task: return
        self._pulse_task = asyncio.create_task(self._pulse_loop())
        logger.info("[REGISTRY] 💓 Global Radar Pulse iniciado (3s interval)")

    async def _pulse_loop(self):
        """Loop que emite el estado resumido de todo el mercado cada 3 segundos."""
        while True:
            try:
                await asyncio.sleep(3) 
                states = await store.get_market_states()
                if not states: continue

                summary = []
                for s in states:
                    summary.append({
                        "asset":       s.get("asset"),
                        "price":       s.get("price") or s.get("current_price"),
                        "regime":      s.get("regime") or s.get("market_regime", "UNKNOWN"),
                        "strategy":    s.get("strategy") or "SMC INSTITUTIONAL",
                        "bias":        s.get("macro_bias") or (s.get("htf_bias", {}).get("direction", "NEUTRAL") if isinstance(s.get("htf_bias"), dict) else "NEUTRAL"),
                        "ob_count":    (s.get("ob_bullish_count", 0) + s.get("ob_bearish_count", 0)),
                        "fvg_active":  (s.get("fvg_bullish_active", False) or s.get("fvg_bearish_active", False)),
                        "is_killzone": s.get("in_killzone", False),
                        "macro_risk":  s.get("macro_risk", False),
                        "liq_magnet":  s.get("liq_magnet", False),
                        "ml_dir":      s.get("ml_dir", "NEUTRAL"),
                        "ml_prob":     s.get("ml_prob", 50),
                        "sentiment":   s.get("risk_appetite", "NEUTRAL")
                    })

                self._last_radar_summary = summary

                async with self._lock:
                    for b in self._broadcasters.values():
                        # Usamos _broadcast que debe estar implementado en el SymbolBroadcaster
                        await b._broadcast({"type": "radar_update", "data": summary})
            except Exception as e:
                logger.error(f"[REGISTRY] Pulse error: {e}")
                await asyncio.sleep(5)

    async def get_or_create(self, symbol: str, interval: str, persistent: bool = False) -> tuple:
        """
        Retorna el broadcaster para symbol:interval, creándolo si no existe.
        Importa SymbolBroadcaster localmente para evitar ciclos.
        """
        from engine.api.ws_manager import SymbolBroadcaster # Local import
        
        if not self._pulse_task:
            await self.start_global_pulse()

        key = f"{symbol.upper()}:{interval}"
        client_id = str(uuid.uuid4())

        async with self._lock:
            if key not in self._broadcasters:
                await store.flush_symbol(symbol.upper()) # Flush & Sync
                
                # [OPTIMIZACIÓN v8.5] Auto-persistir activos de la Watchlist
                from engine.api.config import settings
                if symbol.upper() in settings.MASTER_WATCHLIST:
                    persistent = True
                    logger.info(f"[REGISTRY] 💎 {key} detectado en Watchlist. Iniciando como PERSISTENTE.")

                broadcaster = SymbolBroadcaster(symbol, interval, persistent=persistent)
                self._broadcasters[key] = broadcaster
                await broadcaster.start()
                logger.info(f"[REGISTRY] ✅ Nuevo broadcaster: {key}")
            else:
                if persistent and not self._broadcasters[key].persistent:
                    self._broadcasters[key].persistent = True
                    logger.info(f"[REGISTRY] 💎 Broadcaster {key} elevado a PERSISTENTE")
                    
                logger.info(f"[REGISTRY] ♻️  Reutilizando broadcaster: {key}")

        return self._broadcasters[key], client_id

    async def release(self, symbol: str, interval: str, client_id: str):
        """Desregistra un cliente con Grace Period."""
        key = f"{symbol.upper()}:{interval}"
        async with self._lock:
            broadcaster = self._broadcasters.get(key)
            if broadcaster is None: return

            await broadcaster.unsubscribe(client_id)

            if broadcaster.subscriber_count() == 0 and not broadcaster.persistent:
                # [OPTIMIZACIÓN v8.5] Comprobar si es un activo Keep-Alive (Master Watchlist)
                from engine.api.config import settings
                if symbol.upper() in settings.MASTER_WATCHLIST:
                    logger.debug(f"[REGISTRY] 💎 Broadcaster {key} es un activo Keep-Alive. No se eliminará.")
                    return

                async def _delayed_cleanup():
                    await asyncio.sleep(600.0) # Periodo de Gracia aumentado a 10 min
                    async with self._lock:
                        if key in self._broadcasters and self._broadcasters[key].subscriber_count() == 0:
                            await self._broadcasters[key].stop()
                            del self._broadcasters[key]
                            logger.info(f"[REGISTRY] 🗑️ Broadcaster eliminado tras Grace Period (10 min): {key}")
                
                asyncio.create_task(_delayed_cleanup())

    def status(self) -> dict:
        return {
            key: {"subscribers": b.subscriber_count()}
            for key, b in self._broadcasters.items()
        }

    async def broadcast_global(self, message: dict):
        """Envía un mensaje a todos los clientes conectados en todos los broadcasters."""
        tasks = []
        async with self._lock:
            for b in self._broadcasters.values():
                tasks.append(b._broadcast(message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ── Métricas de Simulación (Sigma Audit) ──────────────────────────────────
    def record_auth(self, success: bool):
        if success: self._metrics["auth_ok"] += 1
        else: self._metrics["auth_fail"] += 1

    def record_latency(self, ms: float):
        if ms <= 0: return
        self._metrics["latency_sum"] += ms
        self._metrics["latency_count"] += 1

    def record_veto(self, symbol: str, reason: str):
        self._metrics["vetoes"].append((symbol, reason))
        # Mantener solo los últimos 20 vetos para el log de 30s
        if len(self._metrics["vetoes"]) > 20: self._metrics["vetoes"].pop(0)

    async def start_simulation_monitor(self):
        """Inicia el monitor de simulación de 30 segundos solicitado por el usuario."""
        if self._simulation_task: return
        self._simulation_task = asyncio.create_task(self._simulation_loop())
        logger.info("[SIMULATION] 🛡️ Monitor de Mercado Activado (Reporte cada 30s)")

    async def _simulation_loop(self):
        while True:
            await asyncio.sleep(30)
            avg_lat = self._metrics["latency_sum"] / self._metrics["latency_count"] if self._metrics["latency_count"] > 0 else 0
            
            report = f"\n{'─'*60}\n"
            report += f"📊 REPORT DE SIMULACIÓN (Radar Center v6.0)\n"
            report += f"1. Latencia Promedio (Magallanes Line): {avg_lat:.2f}ms\n"
            report += f"2. Sigma X-API-KEY: Authorized={self._metrics['auth_ok']} | Rejected={self._metrics['auth_fail']}\n"
            report += f"3. Trazabilidad de Veto (Últimos 5):\n"
            
            recent_vetos = self._metrics["vetoes"][-5:]
            if not recent_vetos: 
                report += "   - Ningún veto registrado.\n"
            for sym, res in recent_vetos:
                report += f"   - [{sym}] Veto: {res}\n"
            report += f"{'─'*60}\n"
            
            logger.info(report)
            
            # Resetear promedios de latencia para la siguiente ventana
            self._metrics["latency_sum"] = 0
            self._metrics["latency_count"] = 0

registry = BroadcasterRegistry()
