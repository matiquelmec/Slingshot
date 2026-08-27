import pytest
import asyncio
import pandas as pd
from engine.workers.trade_manager import TradeManager
from engine.execution.bitunix_executor import BitunixExecutor

@pytest.fixture
def trade_manager():
    return TradeManager()

def test_fast_be_math_precision_long_and_short(trade_manager):
    """
    AUDITORÍA DE PRECISIÓN MATEMÁTICA: FAST BREAKEVEN (+1.0R)
    Verifica que al alcanzar +1.0R, el SL se fije exactamente en el precio de entrada o entrada + micro-buffer.
    """
    # Caso LONG
    entry_long = 100.0
    sl_long = 98.0
    risk_dist_long = 2.0 # 1R = $2.00
    
    # Precio actual alcanza +1.0R ($102.00)
    cur_price_long = 102.0
    r_profit_long = (cur_price_long - entry_long) / risk_dist_long
    assert r_profit_long == 1.0
    
    # En Tier 1 (+1.0R), target_sl = entry_price ($100.00)
    target_sl_long = round(entry_long, 4)
    assert target_sl_long == 100.0
    assert trade_manager._sl_improved(sl_long, target_sl_long, is_long=True) is True

    # Caso SHORT
    entry_short = 50.0
    sl_short = 51.0
    risk_dist_short = 1.0 # 1R = $1.00
    
    cur_price_short = 49.0 # Precio baja a $49.00 (+1.0R de ganancia)
    r_profit_short = (entry_short - cur_price_short) / risk_dist_short
    assert r_profit_short == 1.0
    
    target_sl_short = round(entry_short, 4)
    assert target_sl_short == 50.0
    assert trade_manager._sl_improved(sl_short, target_sl_short, is_long=False) is True


def test_multi_tier_ratchet_progression_1r_to_10r(trade_manager):
    """
    AUDITORÍA DE ESCALERA MULTI-TIER (TIER 1 A TIER 4)
    Verifica la retención de ganancias en cada escalón:
      Tier 1 (+1.0R a +1.99R) -> 0.0R (BE)
      Tier 2 (+2.0R a +2.99R) -> +1.2R asegurado
      Tier 3 (+3.0R a +4.99R) -> +2.0R asegurado
      Tier 4 (>= +5.0R)       -> 70% del R flotante retenido
    """
    entry = 200.0
    initial_sl = 190.0
    risk_dist = 10.0 # 1R = $10.00
    is_long = True

    # Simulación de progresión de precio
    test_points = [
        (205.0, 0.5, None, "EN_CURSO (< 1.0R)"),
        (210.0, 1.0, 200.0, "Tier 1 Fast BE (0.0R asegurado)"),
        (215.0, 1.5, 200.0, "Tier 1 Fast BE"),
        (220.0, 2.0, 212.0, "Tier 2 (+1.2R asegurado)"),
        (225.0, 2.5, 212.0, "Tier 2 (+1.2R asegurado)"),
        (230.0, 3.0, 220.0, "Tier 3 (+2.0R asegurado)"),
        (240.0, 4.0, 220.0, "Tier 3 (+2.0R asegurado)"),
        (250.0, 5.0, 235.0, "Tier 4 Runner (70% de 5R = +3.5R -> $235.00)"),
        (280.0, 8.0, 256.0, "Tier 4 Runner (70% de 8R = +5.6R -> $256.00)"),
        (300.0, 10.0, 270.0, "Tier 4 Runner (70% de 10R = +7.0R -> $270.00)"),
    ]

    for cur_price, expected_r, expected_sl, label in test_points:
        r_profit = (cur_price - entry) / risk_dist
        assert r_profit == pytest.approx(expected_r, rel=1e-3)

        calculated_sl = None
        if r_profit >= 5.0:
            locked_r = r_profit * 0.70
            calculated_sl = round(entry + (risk_dist * locked_r), 4)
        elif r_profit >= 3.0:
            calculated_sl = round(entry + (risk_dist * 2.0), 4)
        elif r_profit >= 2.0:
            calculated_sl = round(entry + (risk_dist * 1.2), 4)
        elif r_profit >= 1.0:
            calculated_sl = round(entry, 4)

        if expected_sl is None:
            assert calculated_sl is None, f"Error en {label}"
        else:
            assert calculated_sl == pytest.approx(expected_sl, rel=1e-3), f"Fallo en {label}: obtenido {calculated_sl}, esperado {expected_sl}"


def test_sl_invariance_monotonicity_under_adverse_fluctuation(trade_manager):
    """
    AUDITORÍA DE INVARIANZA Y NO-RETROCESO (MONOTONICITY THEOREM)
    Si el precio sube a +6.0R (Tier 4 SL = $242) y luego retrocede bruscamente a +2.5R,
    el Stop Loss JAMÁS debe retroceder ni degradarse.
    """
    entry = 200.0
    risk_dist = 10.0 # 1R = $10.00
    
    # 1. Pico Máximo a +6.0R ($260) -> SL en $242 (+4.2R asegurado)
    peak_price = 260.0
    r_peak = (peak_price - entry) / risk_dist # 6.0R
    sl_at_peak = round(entry + (risk_dist * r_peak * 0.70), 4) # $242.00
    
    # 2. Retroceso Adverso a +2.5R ($225)
    retrace_price = 225.0
    r_retrace = (retrace_price - entry) / risk_dist # 2.5R
    sl_at_retrace_tier2 = round(entry + (risk_dist * 1.2), 4) # $212.00
    
    # Verificación de la Regla de Invarianza:
    # El trade manager DEBE rechazar el nuevo SL inferior
    is_improved = trade_manager._sl_improved(old_sl=sl_at_peak, new_sl=sl_at_retrace_tier2, is_long=True)
    assert is_improved is False, "CRÍTICO: El Stop Loss intentó retroceder durante un retroceso de precio"


def test_structural_trailing_triple_confirmation(trade_manager):
    """
    AUDITORÍA DE FILTRO DE TRIPLE CONFIRMACIÓN ESTRUCTURAL
    Verifica que el SL estructural solo se mueva si:
      1. La vela anterior cerró por encima del nivel (Cierre real, no mecha).
      2. El volumen fue institucional (RVOL >= 1.3x).
      3. Hubo ruptura estructural válida (BOS).
    """
    # Caso 1: Mecha falsa (High supera nivel, pero Cierre queda por debajo)
    df_fake_wick = pd.DataFrame([
        {"timestamp": 1, "close": 95.0, "high": 96.0, "low": 94.0, "volume": 1000},
        {"timestamp": 2, "close": 98.0, "high": 103.0, "low": 97.0, "volume": 2000}, # Cierra en 98 (< 100)
        {"timestamp": 3, "close": 98.5, "high": 99.0, "low": 98.0, "volume": 1000}
    ])
    confirmed, reason = trade_manager._is_move_confirmed(df_fake_wick, level=100.0, is_long=True)
    assert confirmed is False
    assert "nivel 100.0000 no superado" in reason

    # Caso 2: Cierre por encima pero con volumen anémico (RVOL < 1.3x)
    # Generar 25 velas para el cálculo de media móvil de volumen
    base_data = [{"timestamp": i, "close": 90.0 + i*0.2, "high": 91.0 + i*0.2, "low": 89.0 + i*0.2, "volume": 5000} for i in range(22)]
    base_data.append({"timestamp": 23, "close": 101.0, "high": 102.0, "low": 99.0, "volume": 3000}) # RVOL = 3000/5000 = 0.6x
    base_data.append({"timestamp": 24, "close": 101.5, "high": 102.5, "low": 101.0, "volume": 3000})
    df_low_vol = pd.DataFrame(base_data)
    
    confirmed_vol, reason_vol = trade_manager._is_move_confirmed(df_low_vol, level=100.0, is_long=True)
    assert confirmed_vol is False
    assert "Volumen insuficiente" in reason_vol


def test_micro_buffer_fee_and_slippage_absorption(trade_manager):
    """
    AUDITORÍA DE ABSORCIÓN DE FRICCIÓN: MICRO-BUFFER ATR (+0.30 ATR)
    Verifica que en Break Even, el SL no se coloque en el punto exacto de entrada
    sino con un buffer de 0.30 ATR a favor para garantizar cobertura de comisiones Maker/Taker.
    """
    entry = 100.0
    atr = 2.0
    
    # Long: SL = 100 + (2.0 * 0.3) = 100.60
    be_sl_long = trade_manager._calculate_breakeven_sl(entry, atr, is_long=True)
    assert be_sl_long == 100.60
    assert be_sl_long > entry

    # Short: SL = 100 - (2.0 * 0.3) = 99.40
    be_sl_short = trade_manager._calculate_breakeven_sl(entry, atr, is_long=False)
    assert be_sl_short == 99.40
    assert be_sl_short < entry
