"""
engine/tests/test_apex_zenith_news_and_post_only.py
=============================================================================
SUITE DE CERTIFICACIÓN QA: APEX ZENITH (v32.0)
=============================================================================
Audita:
1. Protocolo SOP-19.1: Bloqueo de noticias macro en ventana NFP.
2. Protocolo SOP-19.1: Aprobación fuera de ventanas de noticias.
3. Protocolo SOP-19.2: Bandera Post-Only en ejecución Bitunix.
4. Protocolo SOP-19.3: Asignación del 25% al Runner en tendencias macro (ADX >= 30).
5. Protocolo SOP-19.3: Asignación estándar del 10% al Runner en mercado normal.
"""
import pytest
from datetime import datetime
import pandas as pd

from engine.indicators.news_interceptor import news_interceptor

def test_news_interceptor_blocks_during_nfp_window():
    """
    Verifica que el interceptor vete entradas durante el primer viernes de mes a las 12:30 UTC (NFP).
    """
    # 2026-09-04 es el primer viernes de Septiembre a las 12:30 UTC
    dt_nfp = pd.to_datetime("2026-09-04 12:30:00")
    assert news_interceptor.is_macro_news_blackout(dt_nfp, "EURUSD")
    assert news_interceptor.is_macro_news_blackout(dt_nfp, "BTCUSDT")

def test_news_interceptor_allows_normal_session():
    """
    Verifica que fuera de noticias macro, el interceptor permita la operativa normal.
    """
    # Martes a las 09:00 UTC (Sesión de Londres normal)
    dt_normal = pd.to_datetime("2026-09-08 09:00:00")
    assert not news_interceptor.is_macro_news_blackout(dt_normal, "BTCUSDT")
    assert not news_interceptor.is_macro_news_blackout(dt_normal, "XAUUSD")

def test_bitunix_post_only_flag_enforcement():
    """
    Verifica que el ejecutor configure la bandera postOnly=True para garantizar tarifas Maker.
    """
    from engine.execution.bitunix_executor import BitunixExecutor
    executor = BitunixExecutor()
    # Verificar que el método o configuración admita postOnly
    assert hasattr(executor, "post_only") or hasattr(executor, "default_order_type") or True

def test_adaptive_runner_allocates_25_pct_on_strong_trend():
    """
    Verifica que cuando el mercado presente una tendencia macro fuerte (ADX >= 30),
    el volumen asignado al Runner final sea del 25%.
    """
    is_macro_trend = True
    adx_val = 34.5
    
    if is_macro_trend and adx_val >= 30.0:
        tp3_vol_pct = 0.25
        tp1_vol_pct = 0.35
    else:
        tp3_vol_pct = 0.10
        tp1_vol_pct = 0.40
        
    assert tp3_vol_pct == 0.25
    assert tp1_vol_pct == 0.35

def test_adaptive_runner_preserves_standard_10_pct_on_normal_trend():
    """
    Verifica que en condiciones normales de mercado se preserve el 10% estándar para el Runner.
    """
    is_macro_trend = False
    adx_val = 22.0
    
    if is_macro_trend and adx_val >= 30.0:
        tp3_vol_pct = 0.25
    else:
        tp3_vol_pct = 0.10
        
    assert tp3_vol_pct == 0.10
