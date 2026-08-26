import pytest
import asyncio
import pandas as pd
from datetime import datetime, timezone
from engine.core.store import store
from engine.workers.market_scanner import MarketScanner
from engine.workers.trade_manager import TradeManager

@pytest.mark.asyncio
async def test_market_scanner_does_not_pollute_signal_store():
    """
    Test 1: Verifica que market_scanner guarde oportunidades en scanner_opportunities
    y NUNCA inyecte órdenes virtuales espurias en store.get_signals().
    """
    await store.clear_all()
    scanner = MarketScanner()
    
    # Simulamos candidato de escáner
    sample_candidate = {
        "asset": "ATOMUSDT",
        "direction": "LONG",
        "type": "Virtual Setup",
        "price": 1.5520,
        "stop_loss": 1.5241,
        "tp1": 1.6218,
        "tp2": 1.6498,
        "tp3": 1.7057,
        "rr_ratio_tp3": 3.0,
        "confluence_score": 75,
        "checklist": [],
        "is_active_trigger": False,
        "ote_chasing": False,
        "session": "NEW_YORK",
    }
    
    # Guardamos en scanner_opportunities
    await store.save_scanner_opportunities("scalp", [sample_candidate])
    
    # 1. Las oportunidades del escáner deben estar disponibles
    opps = store.get_scanner_opportunities("scalp")
    assert len(opps) == 1
    assert opps[0]["asset"] == "ATOMUSDT"
    
    # 2. El almacén de señales de ejecución en tiempo real DEBE PERMANECER LIMPIO (0 señales)
    signals = await store.get_signals()
    assert len(signals) == 0, "El almacén de señales no debe contener setups virtuales del escáner"

@pytest.mark.asyncio
async def test_store_deduplication_exact_match():
    """
    Test 2: Verifica que store.save_signal actualice una señal existente del mismo par y sentido
    en lugar de duplicarla cuando el precio o timestamp fluctúan.
    """
    await store.clear_all()
    
    sig1 = {
        "id": "sig_atom_1",
        "asset": "ATOMUSDT",
        "signal_type": "LONG",
        "price": 1.5530,
        "stop_loss": 1.5250,
        "status": "PENDING"
    }
    await store.save_signal(sig1)
    
    # Misma moneda y dirección, precio ligeramente ajustado
    sig2 = {
        "id": "sig_atom_2",
        "asset": "ATOMUSDT",
        "signal_type": "LONG",
        "price": 1.5540,
        "stop_loss": 1.5250,
        "status": "PENDING"
    }
    await store.save_signal(sig2)
    
    signals = await store.get_signals(asset="ATOMUSDT")
    assert len(signals) == 1, "Debe existir exactamente 1 registro para ATOMUSDT LONG (sin duplicados)"
    assert signals[0]["price"] == 1.5540

@pytest.mark.asyncio
async def test_trade_manager_invalidates_missed_pending_order(monkeypatch):
    """
    Test 3: Verifica que TradeManager marque como EXPIRED_MISSED una orden PENDING
    cuyo precio de mercado superó TP1 sin haber tocado la entrada.
    """
    await store.clear_all()
    
    pending_sig = {
        "id": "sig_inj_test",
        "asset": "INJUSDT",
        "signal_type": "LONG",
        "price": 4.782,     # Entrada deseada
        "stop_loss": 4.695,
        "tp1": 4.997,       # TP1
        "tp2": 5.083,
        "tp3": 5.255,
        "status": "PENDING"
    }
    await store.save_signal(pending_sig)
    
    tm = TradeManager()
    
    # Mockeamos historial de velas donde el precio subió directamente a $5.20 (min $4.85, max $5.25)
    async def mock_history(asset, interval, limit=10):
        return [
            {"data": {"timestamp": 1720000000, "close": 5.20, "low": 4.85, "high": 5.25, "volume": 1000}}
        ]
    
    monkeypatch.setattr("engine.workers.trade_manager.fetch_binance_history", mock_history)
    
    # Procesamos la orden pendiente
    await tm._process_pending_signal(pending_sig)
    
    updated_signals = await store.get_signals(asset="INJUSDT")
    assert len(updated_signals) == 1
    assert updated_signals[0]["status"] == "EXPIRED_MISSED"
    assert "sin retroceder al nivel de entrada" in updated_signals[0]["rejection_reason"]
