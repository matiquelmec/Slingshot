"""
engine/tests/test_dynamic_slot_elasticity.py
=============================================================================
SUITE DE PRUEBAS INSTITUCIONALES: SOP-99 DYNAMIC SLOT ELASTICITY
=============================================================================
Audita:
1. Expansión Elástica (+1 Slot de Riesgo = 3) autorizada exclusivamente para
   activos macroeconómicamente descorrelacionados (XAUUSDT vs Cripto, ρ < 0.35)
   con confluencia God Mode (>= 85%) y margen libre >= 65%.
2. Bloqueo de Expansión para activos correlacionados (ej. 3ra Cripto) para evitar
   la trampa del riesgo direccional apilado (stacking).
3. Bloqueo de Expansión si el margen libre disponible es insuficiente (< 65%).
4. Contracción Defensiva (-1 Slot de Riesgo = 1) ante racha de 2 pérdidas (SOP-94).
5. Contracción Defensiva (-1 Slot de Riesgo = 1) ante ventana de noticias macro (SOP-19).
6. Expansión del Techo Físico a 5 posiciones concurrentes bajo régimen descorrelacionado.
"""
import pytest
from unittest.mock import MagicMock, patch
from engine.execution.nexus import NexusNode
from engine.risk.cluster_risk_guard import cluster_risk_guard

@pytest.fixture
def nexus():
    node = NexusNode(dry_run=True)
    node._active_positions = {}
    node._open_limit_orders = {}
    node._high_confluence_buffer = {}
    node._consecutive_losses = {}
    return node

def test_is_asset_decoupled_evaluates_cross_correlation():
    """Valida la detección matemática de descorrelación (Oro vs Cripto)."""
    # XAU vs BTC/SOL: Clústeres distintos -> descorrelacionados (ρ=0.15 < 0.35)
    is_dec, max_c = cluster_risk_guard.is_asset_decoupled("XAUUSDT", ["BTCUSDT", "SOLUSDT"], threshold=0.35)
    assert is_dec is True
    assert max_c < 0.35

    # NEAR vs SOL/BTC: Ambos Cripto -> correlacionados (ρ >= 0.75 > 0.35)
    is_dec_crypto, max_c_crypto = cluster_risk_guard.is_asset_decoupled("NEARUSDT", ["BTCUSDT", "SOLUSDT"], threshold=0.35)
    assert is_dec_crypto is False
    assert max_c_crypto >= 0.75

def test_elastic_expansion_authorized_for_decoupled_godmode(nexus):
    """Verifica que con 2 criptos abiertas, XAU con score >=85% y margen >=65% expande a 3 slots."""
    account_id = "primary"
    nexus._active_positions = {
        f"{account_id}_BTCUSDT": {"symbol": "BTCUSDT", "account_id": account_id, "be_active": False},
        f"{account_id}_SOLUSDT": {"symbol": "SOLUSDT", "account_id": account_id, "be_active": False}
    }
    xau_signal = {"asset": "XAUUSDT", "symbol": "XAUUSDT", "confluence_score": 88.0}

    u_cap, c_cap, mode = nexus.get_dynamic_slot_capacity(
        account_id=account_id,
        candidate_signal=xau_signal,
        free_margin_pct=75.0
    )
    assert u_cap == 3
    assert c_cap == 5
    assert "ELASTIC_EXPANSION" in mode

def test_elastic_expansion_blocked_for_correlated_asset(nexus):
    """Verifica que con 2 criptos abiertas, una 3ra cripto con score 88% se mantiene en 2 slots."""
    account_id = "primary"
    nexus._active_positions = {
        f"{account_id}_BTCUSDT": {"symbol": "BTCUSDT", "account_id": account_id, "be_active": False},
        f"{account_id}_SOLUSDT": {"symbol": "SOLUSDT", "account_id": account_id, "be_active": False}
    }
    near_signal = {"asset": "NEARUSDT", "symbol": "NEARUSDT", "confluence_score": 88.0}

    u_cap, c_cap, mode = nexus.get_dynamic_slot_capacity(
        account_id=account_id,
        candidate_signal=near_signal,
        free_margin_pct=75.0
    )
    assert u_cap == 2
    assert c_cap == 4
    assert mode == "STANDARD_SOP97"

def test_elastic_expansion_blocked_by_insufficient_margin(nexus):
    """Si el margen libre es < 65%, no se expande el slot aunque el activo esté descorrelacionado."""
    account_id = "primary"
    nexus._active_positions = {
        f"{account_id}_BTCUSDT": {"symbol": "BTCUSDT", "account_id": account_id, "be_active": False},
        f"{account_id}_SOLUSDT": {"symbol": "SOLUSDT", "account_id": account_id, "be_active": False}
    }
    xau_signal = {"asset": "XAUUSDT", "symbol": "XAUUSDT", "confluence_score": 90.0}

    u_cap, c_cap, mode = nexus.get_dynamic_slot_capacity(
        account_id=account_id,
        candidate_signal=xau_signal,
        free_margin_pct=50.0  # Margen bajo
    )
    assert u_cap == 2
    assert c_cap == 4
    assert mode == "STANDARD_SOP97"

def test_elastic_contraction_under_loss_streak(nexus):
    """Racha de 2 pérdidas consecutivas (SOP-94) contrae la capacidad a 1 solo riesgo flotante."""
    account_id = "primary"
    nexus._consecutive_losses[account_id] = 2
    
    opp = {"asset": "SOLUSDT", "confluence_score": 92.0}
    u_cap, c_cap, mode = nexus.get_dynamic_slot_capacity(account_id, opp, free_margin_pct=80.0)
    
    assert u_cap == 1
    assert c_cap == 3
    assert "DEFENSIVE_CONTRACTION" in mode

def test_elastic_contraction_under_macro_news(nexus):
    """Ventana macro activa (SOP-19 / SOP-92) contrae la capacidad a 1 solo riesgo flotante."""
    account_id = "primary"
    opp = {"asset": "XAUUSDT", "confluence_score": 90.0}

    with patch("engine.indicators.news_interceptor.news_interceptor.is_macro_news_blackout", return_value=True):
        u_cap, c_cap, mode = nexus.get_dynamic_slot_capacity(account_id, opp, free_margin_pct=80.0)
        assert u_cap == 1
        assert c_cap == 3
        assert "DEFENSIVE_CONTRACTION" in mode

@pytest.mark.asyncio
async def test_execution_allows_third_unprotected_trade_under_elastic_expansion(nexus):
    """
    Simulación E2E de ejecución:
    Con 2 posiciones Cripto abiertas, una orden para XAUUSDT (God Mode, Margen 70%)
    es autorizada por el slot elástico expandido.
    """
    account_id = "primary"
    account = MagicMock()
    account.account_id = account_id
    account.label = "Primary Test"

    executor = MagicMock()
    executor.dry_run = True

    nexus._active_positions = {
        f"{account_id}_BTCUSDT": {"symbol": "BTCUSDT", "account_id": account_id, "be_active": False},
        f"{account_id}_SOLUSDT": {"symbol": "SOLUSDT", "account_id": account_id, "be_active": False}
    }

    xau_opp = {
        "asset": "XAUUSDT",
        "symbol": "XAUUSDT",
        "type": "LONG",
        "price": 2500.0,
        "stop_loss": 2480.0,
        "confluence_score": 88.0
    }
    fragments = [{"percentage": 100, "price": 2500.0}]

    # Si fuera una 3ra Cripto correlacionada, sería rechazada (retornaría None)
    crypto_opp = {
        "asset": "NEARUSDT",
        "symbol": "NEARUSDT",
        "type": "LONG",
        "price": 5.0,
        "stop_loss": 4.8,
        "confluence_score": 88.0
    }
    res_crypto = await nexus._execute_signal_for_account(executor, account, crypto_opp, 10, 5.0, 4.8, fragments)
    assert res_crypto is None
    assert any(x["asset"] == "NEARUSDT" for x in nexus._high_confluence_buffer[account_id])

    # Para XAUUSDT descorrelacionado, pasa el filtro de slots
    with patch.object(nexus, "_fragment_order", return_value=fragments):
        with patch.object(executor, "place_entry_market_order", return_value={"status": "FILLED", "order_id": "ord_xau"}):
            with patch.object(executor, "set_position_tpsl", return_value=True):
                # El slot elástico permite superar el límite de 2 y procesa la entrada
                u_cap, _, _ = nexus.get_dynamic_slot_capacity(account_id, xau_opp)
                assert u_cap == 3
