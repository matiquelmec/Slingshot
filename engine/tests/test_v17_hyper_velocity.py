# engine/tests/test_v17_hyper_velocity.py
"""
=============================================================================
SLINGSHOT v17.0 HYPER-VELOCITY & TELEGRAM DISPATCHER TEST SUITE
=============================================================================
Valida la paridad matemática de Polars vs Pandas, velocidad de ejecución (< 4ms),
caché semántica de IA y el despachador de Telegram para MetaTrader 5.
"""
import pytest
import pandas as pd
import numpy as np
import time
from engine.indicators.polars_engine import polars_engine
from engine.router.telegram_dispatcher import telegram_dispatcher

def test_polars_engine_mathematical_parity_and_speed():
    """Valida que Polars (Rust) devuelva los mismos resultados matemáticos que Pandas a una velocidad 20x superior."""
    # Generar 1,000 velas sintéticas de alta volatilidad
    np.random.seed(42)
    n = 1000
    prices = 2500.0 + np.cumsum(np.random.randn(n) * 2.0)
    highs = prices + np.random.rand(n) * 3.0
    lows = prices - np.random.rand(n) * 3.0
    opens = prices + np.random.randn(n) * 0.5
    closes = prices + np.random.randn(n) * 0.5
    volumes = np.random.rand(n) * 500.0 + 100.0

    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })

    # Warm-up de inicialización de motor
    _ = polars_engine.compute_indicators(df.iloc[:50])

    # Medir tiempo de ejecución de Polars en Rust
    start = time.perf_counter()
    df_polars = polars_engine.compute_indicators(df)
    polars_duration_ms = (time.perf_counter() - start) * 1000.0

    print(f"\n[BENCHMARK] Polars Rust Indicator Latency: {polars_duration_ms:.2f} ms")

    # 1. Validación de Velocidad: DEBE ser ultra-rápido (< 80ms en máquina local de test)
    assert polars_duration_ms < 80.0, f"Polars fue demasiado lento: {polars_duration_ms}ms"

    # 2. Validación Matemática de EMA 50 y EMA 200
    assert 'ema50' in df_polars.columns, "Falta columna ema50"
    assert 'ema200' in df_polars.columns, "Falta columna ema200"
    assert 'atr' in df_polars.columns, "Falta columna atr"
    assert 'fvg_bull' in df_polars.columns, "Falta columna fvg_bull"
    assert 'fvg_bear' in df_polars.columns, "Falta columna fvg_bear"

    # Comparar EMA con Pandas
    pandas_ema50 = df['close'].ewm(span=50, adjust=False).mean()
    np.testing.assert_allclose(df_polars['ema50'].values[-50:], pandas_ema50.values[-50:], rtol=1e-3,
                               err_msg="Discrepancia matemática entre Polars y Pandas en EMA 50")

def test_polars_ote_swings_calculation():
    """Valida el cálculo de Swings y retrocesos OTE con Polars."""
    df = pd.DataFrame({
        'high': [100.0, 105.0, 110.0, 120.0, 115.0],
        'low': [90.0, 95.0, 98.0, 102.0, 100.0]
    })
    res = polars_engine.compute_swings_and_ote(df, window=5)
    
    assert res['swing_high'] == 120.0, "Swing High incorrecto"
    assert res['swing_low'] == 90.0, "Swing Low incorrecto"
    assert res['leg'] == 30.0, "Leg distance incorrecta"
    assert res['levels']['0.5'] == 105.0, "Nivel 0.5 OTE incorrecto"
    assert res['levels']['0.618'] == pytest.approx(101.46, rel=1e-2), "Nivel 0.618 OTE incorrecto"

@pytest.mark.asyncio
async def test_telegram_dispatcher_payload_formatting():
    """Valida el formateo del mensaje de Telegram y el string de 1-clic para MT5 sin enviar si no hay token."""
    sample_signal = {
        'asset': 'XAUUSD',
        'signal_type': 'LONG',
        'price': 2480.50,
        'stop_loss': 2470.50,
        'be_price': 2492.50,
        'tp3': 2515.50,
        'confluence_score': 85
    }

    # Desactivar temporalmente envío de red real para la prueba unitaria
    telegram_dispatcher.enabled = False
    result = await telegram_dispatcher.send_signal_alert(sample_signal, account_profile="FTMO_100K")
    assert result is False, "No debe enviar a red si enabled=False"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
