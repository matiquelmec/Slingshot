"""
engine/tests/test_dynamic_heat_and_slot_allocation.py
=============================================================================
SUITE DE PRUEBAS INSTITUCIONALES: SOP-97 & SOP-98
=============================================================================
Audita:
1. Priorización Cuantitativa Alpha Trinity (Multiplicador 1.25x en ETH, SOL, BNB, INJ).
2. Límite Estricto de Riesgo Flotante (MAX_UNPROTECTED_RISK_POSITIONS = 2).
3. Reciclaje Dinámico de Slots: Liberación de cupo al alcanzar Breakeven.
4. Techo Físico Absoluto de Margen (MAX_CONCURRENT_POSITIONS = 4).
5. Ordenamiento de la cola de alta confluencia por Priority Score.
6. Protección SOP-98 contra spreads anómalos (>0.12%) en el screener dinámico.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from engine.execution.nexus import NexusNode
from engine.indicators.data_utils import fetch_top_liquid_tickers

@pytest.fixture
def nexus():
    node = NexusNode()
    node._active_positions = {}
    node._open_limit_orders = {}
    node._high_confluence_buffer = {}
    return node

def test_calculate_priority_score_trinity_multiplier(nexus):
    """Verifica que Alpha Trinity (ETH, SOL, BNB, INJ) reciba boost de 1.25x."""
    sol_opp = {"symbol": "SOLUSDT", "confluence_score": 80.0}
    eth_opp = {"asset": "ETHUSDT", "confluence_score": 80.0}
    bnb_opp = {"symbol": "BNBUSDT", "confluence_score": 80.0}
    inj_opp = {"asset": "INJUSDT", "confluence_score": 80.0}
    near_opp = {"symbol": "NEARUSDT", "confluence_score": 80.0}

    assert nexus.calculate_priority_score(sol_opp) == 100.0  # 80 * 1.25
    assert nexus.calculate_priority_score(eth_opp) == 100.0
    assert nexus.calculate_priority_score(bnb_opp) == 100.0
    assert nexus.calculate_priority_score(inj_opp) == 100.0
    assert nexus.calculate_priority_score(near_opp) == 80.0  # 80 * 1.0

def test_unprotected_risk_count_and_breakeven_release(nexus):
    """Verifica que una posición en Breakeven NO consuma slot de riesgo flotante."""
    account_id = "test_acc"
    
    # 2 posiciones vivas: 1 desprotegida y 1 en Breakeven
    nexus._active_positions = {
        f"{account_id}_BTCUSDT": {
            "symbol": "BTCUSDT",
            "account_id": account_id,
            "be_active": False,
            "sl_at_be": False
        },
        f"{account_id}_ETHUSDT": {
            "symbol": "ETHUSDT",
            "account_id": account_id,
            "be_active": True,  # Ya en Breakeven
            "sl_at_be": True
        }
    }
    
    unprotected = nexus.get_unprotected_risk_count(account_id)
    assert unprotected == 1  # Solo BTCUSDT cuenta como riesgo flotante

    # Si BTCUSDT también pasa a Breakeven:
    nexus._active_positions[f"{account_id}_BTCUSDT"]["be_active"] = True
    assert nexus.get_unprotected_risk_count(account_id) == 0

def test_enqueue_orders_sorted_by_trinity_priority(nexus):
    """
    Verifica que la cola _high_confluence_buffer ordene por priority_score.
    NEAR (85%) vs SOL (80% * 1.25 = 100%): SOL debe encabezar la cola.
    """
    account_id = "test_acc"
    near_sig = {"asset": "NEARUSDT", "confluence_score": 85.0}
    sol_sig = {"asset": "SOLUSDT", "confluence_score": 80.0}

    nexus.enqueue_high_confluence_opportunity(near_sig, account_id)
    nexus.enqueue_high_confluence_opportunity(sol_sig, account_id)

    queue = nexus._high_confluence_buffer[account_id]
    assert len(queue) == 2
    assert queue[0]["asset"] == "SOLUSDT"  # 100.0 vs 85.0
    assert queue[1]["asset"] == "NEARUSDT"

@pytest.mark.asyncio
async def test_max_unprotected_risk_blocks_execution(nexus):
    """
    Si ya hay 2 posiciones desprotegidas, _execute_signal_for_account
    debe vetar la entrada y encolarla en el buffer institucional.
    """
    account_id = "primary"
    account = MagicMock()
    account.account_id = account_id
    account.label = "Primary Account"

    executor = MagicMock()
    executor.dry_run = True

    nexus._active_positions = {
        f"{account_id}_BTCUSDT": {"symbol": "BTCUSDT", "account_id": account_id, "be_active": False, "sl_at_be": False},
        f"{account_id}_ETHUSDT": {"symbol": "ETHUSDT", "account_id": account_id, "be_active": False, "sl_at_be": False}
    }
    
    opp = {
        "asset": "SOLUSDT",
        "symbol": "SOLUSDT",
        "type": "LONG",
        "price": 150.0,
        "stop_loss": 145.0,
        "confluence_score": 85.0
    }
    fragments = [{"percentage": 100, "price": 150.0}]
    
    res = await nexus._execute_signal_for_account(executor, account, opp, safe_lev=10, entry_val=150.0, sl_val=145.0, fragments=fragments)
    assert res is None
    # La oportunidad fue resguardada en buffer
    assert account_id in nexus._high_confluence_buffer
    assert any(x["asset"] == "SOLUSDT" for x in nexus._high_confluence_buffer[account_id])

@pytest.mark.asyncio
async def test_max_concurrent_absolute_cap_blocks_execution(nexus):
    """
    Incluso con 4 posiciones en Breakeven (0 riesgo flotante),
    el techo físico de 4 posiciones abiertas debe impedir la 5ta posición si está correlacionada.
    """
    account_id = "primary"
    account = MagicMock()
    account.account_id = account_id
    account.label = "Primary Account"

    executor = MagicMock()
    executor.dry_run = True

    nexus._active_positions = {
        f"{account_id}_BTCUSDT": {"symbol": "BTCUSDT", "account_id": account_id, "be_active": True},
        f"{account_id}_ETHUSDT": {"symbol": "ETHUSDT", "account_id": account_id, "be_active": True},
        f"{account_id}_SOLUSDT": {"symbol": "SOLUSDT", "account_id": account_id, "be_active": True},
        f"{account_id}_NEARUSDT": {"symbol": "NEARUSDT", "account_id": account_id, "be_active": True}
    }
    
    opp = {
        "asset": "BNBUSDT",
        "symbol": "BNBUSDT",
        "type": "LONG",
        "price": 600.0,
        "stop_loss": 580.0,
        "confluence_score": 90.0
    }
    fragments = [{"percentage": 100, "price": 600.0}]
    
    res = await nexus._execute_signal_for_account(executor, account, opp, safe_lev=10, entry_val=600.0, sl_val=580.0, fragments=fragments)
    assert res is None

@pytest.mark.asyncio
async def test_sop98_screener_spread_protection():
    """
    Verifica que el screener SOP-98 descarte activos con spread > 0.12%.
    """
    mock_data = [
        # Activo con volumen alto y spread normal (0.02%) -> Pasa
        {
            "symbol": "SOLUSDT",
            "quoteVolume": "150000000.0",
            "lastPrice": "150.0",
            "bidPrice": "149.98",
            "askPrice": "150.01"  # spread: 0.02%
        },
        # Activo con volumen alto pero spread anómalo (0.50%) -> Excluido
        {
            "symbol": "MANIPUSDT",
            "quoteVolume": "90000000.0",
            "lastPrice": "2.00",
            "bidPrice": "1.99",
            "askPrice": "2.00"  # spread: (2.00 - 1.99)/2.00 = 0.5% > 0.12%
        }
    ]
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data
    
    with patch("engine.indicators.data_utils._HTTP_CLIENT.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        
        # Invalidate cache
        from engine.indicators.data_utils import _LIQUID_TICKERS_CACHE
        _LIQUID_TICKERS_CACHE["timestamp"] = 0
        _LIQUID_TICKERS_CACHE["tickers"] = []
        
        tickers = await fetch_top_liquid_tickers(min_volume_usdt=30_000_000.0)
        assert "SOLUSDT" in tickers
        assert "MANIPUSDT" not in tickers
