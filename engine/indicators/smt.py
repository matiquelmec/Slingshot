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

def detect_smt_divergence(df_primary: pd.DataFrame, df_secondary: pd.DataFrame) -> dict:
    """
    Compara los extremos recientes de dos activos (ej: BTC y ETH).
    Retorna un dict con el estado de la divergencia SMT.
    """
    if len(df_primary) < 2 or len(df_secondary) < 2:
        return {"divergence": "NONE", "strength": 0}

    # Tomar los últimos dos fractales o mínimos/máximos recientes
    # (Simplificado: últimas dos velas de 15m para detectar el barrido inmediato)
    p1_low_0 = df_primary['low'].iloc[-2]
    p1_low_1 = df_primary['low'].iloc[-1]
    
    s1_low_0 = df_secondary['low'].iloc[-2]
    s1_low_1 = df_secondary['low'].iloc[-1]

    # --- SMT ALCISTA (Buscando Fondo) ---
    # BTC hace Lower Low, pero ETH hace Higher Low
    if p1_low_1 < p1_low_0 and s1_low_1 > s1_low_0:
        return {
            "divergence": "BULLISH_SMT",
            "reason": "Activo primario barrió liquidez, secundario mantuvo estructura (Acumulación)",
            "strength": 0.8
        }

    # --- SMT BAJISTA (Buscando Techo) ---
    p1_high_0 = df_primary['high'].iloc[-2]
    p1_high_1 = df_primary['high'].iloc[-1]
    
    s1_high_0 = df_secondary['high'].iloc[-2]
    s1_high_1 = df_secondary['high'].iloc[-1]

    if p1_high_1 > p1_high_0 and s1_high_1 < s1_high_0:
        return {
            "divergence": "BEARISH_SMT",
            "reason": "Activo primario barrió liquidez, secundario falló en hacer nuevo High (Distribución)",
            "strength": 0.8
        }

    return {"divergence": "NONE", "strength": 0}
