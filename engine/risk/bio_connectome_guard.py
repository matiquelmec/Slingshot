"""
engine/risk/bio_connectome_guard.py
=============================================================================
SLINGSHOT BIO-CONNECTOME GUARD v1.0 (Inspirado en Drosophila Connectome - FlyWire)
=============================================================================
Principios de Red Biológica aplicados a Sistemas Autónomos de Trading:

1. GIANT FIBER ESCAPE CIRCUIT (Fast-Path Reflex):
   - Circuit breaker de latencia mínima que monitorea aceleración adversa de precios
     (ΔP / Δt) y ensanchamiento de spreads.
   - Actúa como el reflejo de escape de la mosca: evacúa la posición en milisegundos
     sin esperar al ciclo de análisis de velas ni procesamiento macro.

2. LATERAL FEEDFORWARD INHIBITION (Inhibición Lateral por Clusters):
   - Inspirado en las interneuronas GABAérgicas del lóbulo óptico de Drosophila.
   - Si un activo ancla (ej. BTCUSDT) sufre un spike de estrés o rechazo violento,
     emite potencial inhibitorio que silencia temporalmente señales en la misma
     dirección para todos los activos subordinados del cluster.
   - Implementa un período refractario biológico para evitar sobreoperar en rebotes trampa.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
from engine.core.logger import logger


class GiantFiberReflex:
    """
    Circuito de escape de alta velocidad (Giant Fiber System).
    Detecta anomalías de aceleración de precios adversos en tiempo real.
    """

    def __init__(
        self,
        velocity_threshold_pct: float = 0.015,  # 1.5% adverso en ventana ultracorta
        window_seconds: float = 15.0,           # Ventana de 15 segundos
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
        Evalúa si la velocidad de desplazamiento adverso activa el reflejo de escape.
        
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
            # Verificar si además se mueve en contra de la entrada
            if current_price < entry_price:
                reason = (
                    f"🚨 [GIANT FIBER REFLEX] Escape activado para {sym}: "
                    f"Caída violenta de {pct_change * 100:.2f}% en {dt:.1f}s (Threshold: -{self.velocity_threshold_pct * 100:.1f}%)"
                )
                logger.critical(reason)
                return True, reason

        # Si estamos SHORT y el precio sube a velocidad anómala
        if side in ("SHORT", "SELL") and pct_change >= self.velocity_threshold_pct:
            if current_price > entry_price:
                reason = (
                    f"🚨 [GIANT FIBER REFLEX] Escape activado para {sym}: "
                    f"Subida violenta de +{pct_change * 100:.2f}% en {dt:.1f}s (Threshold: +{self.velocity_threshold_pct * 100:.1f}%)"
                )
                logger.critical(reason)
                return True, reason

        return False, ""


class LateralInhibitionEngine:
    """
    Motor de Inhibición Lateral Feedforward.
    Silencia señales subordinadas cuando un activo nodo-ancla entra en shock.
    """

    # Nodos ancla y sus colonias subordinadas
    ANCHOR_CLUSTERS = {
        "BTCUSDT": ["ETHUSDT", "SOLUSDT", "AVAXUSDT", "NEARUSDT", "INJUSDT", "SUIUSDT", "LINKUSDT", "RENDERUSDT"],
        "ETHUSDT": ["SOLUSDT", "AVAXUSDT", "NEARUSDT", "LINKUSDT", "INJUSDT"],
        "XAUUSD": ["PAXGUSDT", "XAGUSD", "SILVER"]
    }

    def __init__(
        self,
        refractory_period_seconds: float = 900.0,  # 15 minutos de período refractario
        stress_drop_threshold_pct: float = 0.012   # Caída de 1.2% en el ancla activa inhibición
    ):
        self.refractory_period_seconds = refractory_period_seconds
        self.stress_drop_threshold_pct = stress_drop_threshold_pct
        # Registro de inhibición activa: {subordinate_symbol: {direction: expiry_timestamp}}
        self._inhibited_until: Dict[str, Dict[str, float]] = {}
        # Historial de anclas para medir shock: {anchor: (timestamp, high_watermark)}
        self._anchor_states: Dict[str, Dict[str, Any]] = {}

    def register_anchor_shock(
        self,
        anchor_asset: str,
        shock_direction: str,
        reason: str = "Volatilidad sistémica anómala"
    ) -> List[str]:
        """
        Dispara un pulso inhibitorio desde el ancla hacia sus subordinados.
        Si el shock es bajista (caída en BTC), inhibe las compras (LONG) en altcoins.
        """
        anchor = anchor_asset.replace("/", "").upper()
        now = time.time()
        expiry = now + self.refractory_period_seconds
        inhibited_assets = []

        subordinates = self.ANCHOR_CLUSTERS.get(anchor, [])
        # El shock también afecta al ancla
        all_targets = [anchor] + subordinates

        # Si el ancla cayó bruscamente (shock bajista), inhibimos posiciones LONG
        target_dir = "LONG" if "BEAR" in shock_direction.upper() or "SHORT" in shock_direction.upper() or "DROP" in shock_direction.upper() else "SHORT"

        for sub in all_targets:
            if sub not in self._inhibited_until:
                self._inhibited_until[sub] = {}
            self._inhibited_until[sub][target_dir] = expiry
            inhibited_assets.append(sub)

        logger.warning(
            f"🧠 [LATERAL INHIBITION] Pulso inhibitorio emitido por {anchor} ({shock_direction}). "
            f"Inhibiendo señales {target_dir} en {len(inhibited_assets)} activos por {self.refractory_period_seconds / 60:.1f} min. Motivo: {reason}"
        )
        return inhibited_assets

    def is_inhibited(self, asset: str, direction: str) -> Tuple[bool, str]:
        """
        Verifica si el activo está en estado refractario/inhibido para la dirección dada.
        """
        sym = asset.replace("/", "").upper()
        dir_clean = "LONG" if str(direction).upper() in ("LONG", "BUY") else "SHORT"
        now = time.time()

        asset_inhibition = self._inhibited_until.get(sym, {})
        expiry = asset_inhibition.get(dir_clean, 0.0)

        if now < expiry:
            remaining_min = (expiry - now) / 60.0
            msg = (
                f"🛑 [INHIBICIÓN LATERAL] Señal {dir_clean} silenciada para {sym}: "
                f"Período refractario activo por shock en nodo ancla (restan {remaining_min:.1f} min)."
            )
            return True, msg

        return False, ""

    def clear_inhibition(self, asset: Optional[str] = None) -> None:
        """Limpia el estado inhibitorio (para testing o reset explícito)."""
        if asset:
            sym = asset.replace("/", "").upper()
            self._inhibited_until.pop(sym, None)
        else:
            self._inhibited_until.clear()


# Instancias Singleton para integración directa
giant_fiber_reflex = GiantFiberReflex()
lateral_inhibition_engine = LateralInhibitionEngine()
