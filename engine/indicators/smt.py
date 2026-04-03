"""
Capa 4: Auditoría SMT (Smart Money Tool) - Divergencias de Activos
================================================================
Compara dos activos altamente correlacionados para detectar fallos en la estructura
que indican que el 'Smart Money' está acumulando mientras el retail es barrido.

Lógica SMT:
- SMT Alcista: Activo A hace un Low más bajo, Activo B hace un Low más alto.
- SMT Bajista: Activo A hace un High más alto, Activo B hace un High más bajo.
"""

import pandas as pd
from typing import Dict, Union

def detect_smt_divergence(df_primary: pd.DataFrame, df_secondary: pd.DataFrame, window: int = 10) -> Dict[str, Union[str, float]]:
    """
    Compara los extremos recientes de dos activos (ej: BTC y ETH) en una ventana de tiempo.
    Retorna un dict con el estado de la divergencia SMT y su fuerza (0.0 a 1.0).
    """
    if len(df_primary) < window or len(df_secondary) < window:
        return {"divergence": "NONE", "strength": 0}

    # Slice a la ventana de observación
    p_window = df_primary.tail(window)
    s_window = df_secondary.tail(window)

    p_lows = p_window['low'].values
    s_lows = s_window['low'].values
    
    # ── SMT ALCISTA (Buscando Acumulación) ──────────────────────────────────
    # Activo Primario hace un Lower Low (LL) comparado con el inicio de la ventana
    # Activo Secundario hace un Higher Low (HL) en el mismo periodo
    p_ll = p_lows[-1] < p_lows[0]
    s_hl = s_lows[-1] > s_lows[0]
    
    if p_ll and s_hl:
        # Calcular fuerza basada en la profundidad de la divergencia relativa
        p_drop = (p_lows[0] - p_lows[-1]) / p_lows[0]
        s_rise = (s_lows[-1] - s_lows[0]) / s_lows[0]
        strength = min(1.0, (p_drop + s_rise) * 100) # Sensibilidad 100x

        return {
            "divergence": "BULLISH_SMT",
            "reason": "Smart Money Acumulación: Primario barrió, Secundario aguantó.",
            "strength": round(max(0.5, strength), 2)
        }

    # ── SMT BAJISTA (Buscando Distribución) ─────────────────────────────────
    p_highs = p_window['high'].values
    s_highs = s_window['high'].values
    
    p_hh = p_highs[-1] > p_highs[0]
    s_lh = s_highs[-1] < s_highs[0]
    
    if p_hh and s_lh:
        p_pump = (p_highs[-1] - p_highs[0]) / p_highs[0]
        s_drop = (s_highs[0] - s_highs[-1]) / s_highs[0]
        strength = min(1.0, (p_pump + s_drop) * 100)

        return {
            "divergence": "BEARISH_SMT",
            "reason": "Smart Money Distribución: Primario barrió, Secundario falló.",
            "strength": round(max(0.5, strength), 2)
        }

    return {"divergence": "NONE", "strength": 0}
