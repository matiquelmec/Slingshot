"""
engine/core/execution_kernel.py — v1.0 (SHARED EXECUTION KERNEL - SSoT)
=============================================================================
Núcleo determinista de ejecución cuantitativa compartido entre el motor en vivo
(Nexus/MarketScanner) y el motor de Replay Histórico (UnifiedBacktestEngine).
Elimina el Parity Drift asegurando que las reglas matemáticas de entrada,
invalidación temprana (SOP-25) y harvesting de ganancias (SOP-26) sean idénticas.
=============================================================================
"""

from typing import Dict, Any, List, Tuple, Optional


class ExecutionKernel:
    """
    [SHARED EXECUTION KERNEL SSoT]
    Cálculos puros y deterministas sin dependencias de I/O de red.
    """

    @staticmethod
    def calculate_optimal_limit_entry(
        direction: str,
        current_price: float,
        smc_map: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calcula el punto de entrada límite óptimo en zona de descuento FVG u Order Block.
        Si no hay bloques válidos con descuento, retorna el current_price.
        """
        direction = direction.upper()
        if not smc_map or current_price <= 0:
            return current_price

        optimal_entry = current_price

        if direction == "LONG":
            bull_obs = smc_map.get("order_blocks", {}).get("bullish", []) if isinstance(smc_map, dict) else []
            valid_obs = [ob for ob in bull_obs if isinstance(ob, dict) and ob.get("top", 0) < current_price]
            if valid_obs:
                optimal_entry = max(valid_obs, key=lambda ob: ob.get("top", 0))["top"]
            else:
                bull_fvgs = smc_map.get("fvgs", {}).get("bullish", []) if isinstance(smc_map, dict) else []
                valid_fvgs = [fvg for fvg in bull_fvgs if isinstance(fvg, dict) and fvg.get("top", 0) < current_price]
                if valid_fvgs:
                    optimal_entry = max(valid_fvgs, key=lambda fvg: fvg.get("top", 0))["top"]
        else: # SHORT
            bear_obs = smc_map.get("order_blocks", {}).get("bearish", []) if isinstance(smc_map, dict) else []
            valid_obs = [ob for ob in bear_obs if isinstance(ob, dict) and ob.get("bottom", 0) > current_price]
            if valid_obs:
                optimal_entry = min(valid_obs, key=lambda ob: ob.get("bottom", 0))["bottom"]
            else:
                bear_fvgs = smc_map.get("fvgs", {}).get("bearish", []) if isinstance(smc_map, dict) else []
                valid_fvgs = [fvg for fvg in bear_fvgs if isinstance(fvg, dict) and fvg.get("bottom", 0) > current_price]
                if valid_fvgs:
                    optimal_entry = min(valid_fvgs, key=lambda fvg: fvg.get("bottom", 0))["bottom"]

        return float(optimal_entry)

    @staticmethod
    def calculate_bracket_levels(
        direction: str,
        entry_price: float,
        stop_loss: float,
        rr_tp1: float = 1.2,
        rr_tp2: float = 2.0,
        rr_tp3: float = 3.5
    ) -> Dict[str, float]:
        """
        Calcula con precisión matemática los niveles de Take Profit y Breakeven
        basados en la distancia del Stop Loss (1.0R).
        """
        direction = direction.upper()
        sl_dist = abs(entry_price - stop_loss)
        if sl_dist <= 0:
            sl_dist = entry_price * 0.01

        is_long = (direction == "LONG")

        if is_long:
            tp1 = entry_price + (sl_dist * rr_tp1)
            tp2 = entry_price + (sl_dist * rr_tp2)
            tp3 = entry_price + (sl_dist * rr_tp3)
            be_price = entry_price + (sl_dist * 1.0)
        else:
            tp1 = entry_price - (sl_dist * rr_tp1)
            tp2 = entry_price - (sl_dist * rr_tp2)
            tp3 = entry_price - (sl_dist * rr_tp3)
            be_price = entry_price - (sl_dist * 1.0)

        return {
            "entry_price": float(entry_price),
            "stop_loss": float(stop_loss),
            "sl_distance": float(sl_dist),
            "be_price": float(be_price),
            "tp1": float(tp1),
            "tp2": float(tp2),
            "tp3": float(tp3),
            "rr_ratio_tp3": float(rr_tp3)
        }

    @staticmethod
    def evaluate_structural_invalidation_sop25(
        direction: str,
        entry_price: float,
        stop_loss: float,
        current_low: float,
        current_high: float,
        threshold_r: float = 0.65
    ) -> Tuple[bool, float]:
        """
        [SOP-25 EARLY STRUCTURAL INVALIDATION]
        Determina si una posición debe invalidarse tempranamente a -0.65R
        antes de que toque el Stop Loss completo (-1.0R), ahorrando +0.35R.
        """
        direction = direction.upper()
        sl_dist = abs(entry_price - stop_loss)
        if sl_dist <= 0:
            return False, entry_price

        cutoff_dist = sl_dist * threshold_r

        if direction == "LONG":
            invalidation_price = entry_price - cutoff_dist
            if current_low <= invalidation_price:
                return True, invalidation_price
        else: # SHORT
            invalidation_price = entry_price + cutoff_dist
            if current_high >= invalidation_price:
                return True, invalidation_price

        return False, entry_price


# Instancia singleton
execution_kernel = ExecutionKernel()
