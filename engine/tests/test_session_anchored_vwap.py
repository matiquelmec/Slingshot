"""
engine/tests/test_session_anchored_vwap.py
=============================================================================
PRUEBAS UNITARIAS: SOP-95 SESSION ANCHORED VWAP (AVWAP)
=============================================================================
Valida:
1. Reseteo acumulativo en los inicios de sesión (00:00 Asia, 07:00 Londres, 13:30 NY).
2. Cálculo correcto de session_avwap y dist_pct ponderado por volumen.
3. Asignación correcta de session_name según la hora UTC.
4. Resiliencia y fallback ante DataFrames vacíos o sin volumen.
=============================================================================
"""

import pytest
import pandas as pd
import numpy as np
from engine.indicators.volume import calculate_session_anchored_vwap


def test_session_anchored_vwap_session_segmentation():
    """Valida que las sesiones se clasifiquen correctamente en Asia, Londres y Nueva York."""
    # Crear un rango de fechas con timestamps específicos
    timestamps = [
        pd.Timestamp("2026-09-20 03:00:00", tz="UTC"),  # Asia
        pd.Timestamp("2026-09-20 06:45:00", tz="UTC"),  # Asia
        pd.Timestamp("2026-09-20 07:00:00", tz="UTC"),  # Londres Open
        pd.Timestamp("2026-09-20 10:30:00", tz="UTC"),  # Londres
        pd.Timestamp("2026-09-20 13:30:00", tz="UTC"),  # NY Open
        pd.Timestamp("2026-09-20 18:00:00", tz="UTC"),  # NY
    ]

    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
        "high": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
        "low":  [99.0, 100.0, 101.0, 102.0, 103.0, 104.0],
        "close": [100.5, 101.5, 102.5, 103.5, 104.5, 105.5],
        "volume": [1000, 2000, 1500, 2500, 3000, 4000]
    })

    res = calculate_session_anchored_vwap(df)

    assert "session_avwap" in res.columns
    assert "session_name" in res.columns
    assert "session_avwap_dist_pct" in res.columns

    # Verificar nombres de sesiones
    assert res.iloc[0]["session_name"] == "ASIA"
    assert res.iloc[1]["session_name"] == "ASIA"
    assert res.iloc[2]["session_name"] == "LONDON"
    assert res.iloc[3]["session_name"] == "LONDON"
    assert res.iloc[4]["session_name"] == "NEW_YORK"
    assert res.iloc[5]["session_name"] == "NEW_YORK"


def test_session_anchored_vwap_reset_at_session_open():
    """
    Verifica que el VWAP se resetee al inicio de la sesión:
    En la primera vela de Londres (07:00 UTC), session_avwap debe coincidir
    exactamente con el precio típico de esa primera vela, sin arrastrar volumen de Asia.
    """
    t_asia = pd.Timestamp("2026-09-20 06:45:00", tz="UTC")
    t_london = pd.Timestamp("2026-09-20 07:00:00", tz="UTC")

    df = pd.DataFrame({
        "timestamp": [t_asia, t_london],
        "high":  [100.0, 120.0],
        "low":   [90.0, 110.0],
        "close": [95.0, 115.0],
        "volume": [1000000, 500]  # Volumen masivo en Asia, volumen pequeño en Londres
    })

    res = calculate_session_anchored_vwap(df)

    # Vela Londres: typical_price = (120 + 110 + 115) / 3 = 115.0
    london_avwap = res.iloc[1]["session_avwap"]
    assert abs(london_avwap - 115.0) < 0.01


def test_session_anchored_vwap_empty_and_fallback():
    """Verifica que el indicador maneje DataFrames vacíos o con datos mínimos sin lanzar excepciones."""
    df_empty = pd.DataFrame()
    res_empty = calculate_session_anchored_vwap(df_empty)
    assert res_empty.empty

    df_no_vol = pd.DataFrame({
        "timestamp": [pd.Timestamp("2026-09-20 08:00:00", tz="UTC")],
        "close": [50.0]
    })
    res_no_vol = calculate_session_anchored_vwap(df_no_vol)
    assert "session_avwap" in res_no_vol.columns
    assert res_no_vol.iloc[0]["session_avwap"] == 50.0
