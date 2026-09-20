"""
engine/risk/bio_connectome_guard.py
=============================================================================
SLINGSHOT FAST-PATH CIRCUIT BREAKER v1.1 (High-Velocity Anomaly Sentinel)
=============================================================================
Arquitectura de Baja Latencia:
1. FAST-PATH VELOCITY CIRCUIT BREAKER:
   - Monitorea aceleraciones de precio adversas violentas (ΔP / Δt) en tiempo real
     mediante ventanas rodantes de alta frecuencia.
   - Si detecta un flash crash o movimiento desestabilizador en contra de una
     posición abierta, emite una orden de evacuación a mercado para evitar
     slippage catastrófico o saltos de liquidez en el libro de órdenes.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
from engine.core.logger import logger


class GiantFiberReflex:
    """
    Circuito de escape de alta velocidad (Fast-Path Velocity Sentinel).
    Detecta anomalías de aceleración de precios adversos en tiempo real.
    """

    def __init__(
        self,
        velocity_threshold_pct: float = 0.015,  # 1.5% adverso en ventana ultracorta
        window_seconds: float = 15.0,           # Ventana rodante de 15 segundos
        spread_spike_multiplier: float = 3.0    # Multiplicador de spread anómalo
    ):
        self.velocity_threshold_pct = velocity_threshold_pct
        self.window_seconds = window_seconds
        self.spread_spike_multiplier = spread_spike_multiplier
        # Buffer de precios: {asset: deque([(timestamp, price)])}
        self._price_windows: Dict[str, deque] = {}

    def record_tick(self, asset: str, price: float, timestamp: Optional[float] = None) -> None:
        """Registra un nuevo precio en la ventana rodante."""
        t = timestamp or time.time()
        sym = asset.replace("/", "").upper()
        if sym not in self._price_windows:
            self._price_windows[sym] = deque()

        dq = self._price_windows[sym]
        dq.append((t, float(price)))

        # Purgar datos fuera de la ventana
        cutoff = t - self.window_seconds
        while dq and dq[0][0] < cutoff:
            dq.popleft()

    def check_emergency_escape(
        self,
        asset: str,
        current_price: float,
        position_side: str,
        entry_price: float
    ) -> Tuple[bool, str]:
        """
        Evalúa si la velocidad de desplazamiento adverso activa el escape de emergencia.
        
        Retorna:
            (debe_evacuar: bool, motivo: str)
        """
        sym = asset.replace("/", "").upper()
        self.record_tick(sym, current_price)

        dq = self._price_windows.get(sym)
        if not dq or len(dq) < 2:
            return False, ""

        earliest_time, earliest_price = dq[0]
        dt = dq[-1][0] - earliest_time
        if dt < 1.0:
            return False, ""

        side = str(position_side).upper()
        # Calcular variación porcentual en la ventana
        pct_change = (current_price - earliest_price) / earliest_price

        # Si estamos LONG y el precio cae a velocidad anómala
        if side in ("LONG", "BUY") and pct_change <= -self.velocity_threshold_pct:
            if current_price < entry_price:
                reason = (
                    f"🚨 [FAST-PATH ESCAPE] Evacuación de emergencia para {sym}: "
                    f"Caída anómala de {pct_change * 100:.2f}% en {dt:.1f}s (Threshold: -{self.velocity_threshold_pct * 100:.1f}%)"
                )
                logger.critical(reason)
                return True, reason

        # Si estamos SHORT y el precio sube a velocidad anómala
        if side in ("SHORT", "SELL") and pct_change >= self.velocity_threshold_pct:
            if current_price > entry_price:
                reason = (
                    f"🚨 [FAST-PATH ESCAPE] Evacuación de emergencia para {sym}: "
                    f"Subida anómala de +{pct_change * 100:.2f}% en {dt:.1f}s (Threshold: +{self.velocity_threshold_pct * 100:.1f}%)"
                )
                logger.critical(reason)
                return True, reason

        return False, ""


# Instancia Singleton para integración directa
giant_fiber_reflex = GiantFiberReflex()
