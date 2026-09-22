"""
engine/tests/test_progressive_exposure_and_streak_sizing.py
=============================================================================
PRUEBAS UNITARIAS: SOP-94 PROGRESSIVE EXPOSURE & ASYMMETRIC DRAWDOWN PROTECTION
=============================================================================
Valida:
1. Multiplicador 1.00x en régimen normal (0 pérdidas).
2. Multiplicador 0.85x ante 1 pérdida aislada.
3. Multiplicador 0.65x (balanced) y 0.50x (prop_firm) ante >= 2 pérdidas consecutivas.
4. Quick Restore: Restauración inmediata a 1.00x cuando la última posición libera riesgo (TP/BE).
5. Integración con NexusNode en apertura de mercado y órdenes límite.
=============================================================================
"""

import pytest
from engine.risk.risk_manager import RiskManager
from engine.execution.nexus import NexusNode


def test_streak_multiplier_zero_losses():
    """Con 0 pérdidas, el multiplicador debe ser exactamente 1.00x."""
    mult = RiskManager.calculate_streak_exposure_multiplier(
        consecutive_losses=0,
        risk_released_recently=False,
        mode="balanced"
    )
    assert mult == 1.00


def test_streak_multiplier_one_loss():
    """Con 1 pérdida, aplica una reducción preventiva suave a 0.85x."""
    mult = RiskManager.calculate_streak_exposure_multiplier(
        consecutive_losses=1,
        risk_released_recently=False,
        mode="balanced"
    )
    assert mult == 0.85


def test_streak_multiplier_two_or_more_losses_balanced_and_prop_firm():
    """Con >= 2 pérdidas, reduce a 0.65x en balanced y a 0.50x en prop_firm."""
    mult_bal = RiskManager.calculate_streak_exposure_multiplier(
        consecutive_losses=2,
        risk_released_recently=False,
        mode="balanced"
    )
    assert mult_bal == 0.65

    mult_bal_3 = RiskManager.calculate_streak_exposure_multiplier(
        consecutive_losses=3,
        risk_released_recently=False,
        mode="balanced"
    )
    assert mult_bal_3 == 0.65

    mult_prop = RiskManager.calculate_streak_exposure_multiplier(
        consecutive_losses=2,
        risk_released_recently=False,
        mode="prop_firm"
    )
    assert mult_prop == 0.50


def test_streak_multiplier_quick_restore_on_risk_released():
    """
    Si una posición previa liberó riesgo (tocó TP1 o Breakeven),
    el multiplicador debe restaurarse INMEDIATAMENTE al 1.00x para capturar el rebote.
    """
    mult = RiskManager.calculate_streak_exposure_multiplier(
        consecutive_losses=3,
        risk_released_recently=True,
        mode="balanced"
    )
    assert mult == 1.00


def test_streak_multiplier_from_recent_outcomes_list():
    """Verifica que el método pueda inferir la racha perdedora desde una lista de outcomes en R."""
    outcomes = [1.5, 2.0, -0.65, -0.65] # Últimas dos fueron pérdidas
    mult = RiskManager.calculate_streak_exposure_multiplier(
        recent_outcomes=outcomes,
        mode="balanced"
    )
    assert mult == 0.65

    outcomes_win = [1.5, -0.65, -0.65, 1.2] # Última fue ganancia
    mult_win = RiskManager.calculate_streak_exposure_multiplier(
        recent_outcomes=outcomes_win,
        mode="balanced"
    )
    assert mult_win == 1.00


@pytest.mark.asyncio
async def test_nexus_node_streak_lifecycle():
    """Valida el ciclo de vida del contador de racha en NexusNode ante eventos on_risk_released."""
    nexus = NexusNode(dry_run=True)
    acc = "primary"

    # 1. Evento de Stop Loss incrementa racha
    await nexus.on_risk_released(account_id=acc, reason="STOP_LOSS_SOLUSDT")
    assert nexus._consecutive_losses.get(acc) == 1
    assert nexus._risk_released_recently.get(acc) is False

    # 2. Segundo Stop Loss lleva a racha = 2
    await nexus.on_risk_released(account_id=acc, reason="SOP25_EARLY_INVALIDATION_SUIUSDT")
    assert nexus._consecutive_losses.get(acc) == 2

    # 3. Evento de Fast Breakeven o Take Profit ejecuta Quick Restore
    await nexus.on_risk_released(account_id=acc, reason="FAST_BE_ACTIVADO_BTCUSDT")
    assert nexus._consecutive_losses.get(acc) == 0
    assert nexus._risk_released_recently.get(acc) is True
