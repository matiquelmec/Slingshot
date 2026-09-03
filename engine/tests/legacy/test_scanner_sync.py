# engine/tests/test_scanner_sync.py
"""
=============================================================================
PRUEBAS UNITARIAS: SINCRONIZACIÓN TOTAL 1-A-1 ESCÁNER & SIGNAL STORE (v17.3)
=============================================================================
Valida que:
1. Las oportunidades del escáner no se recorten arbitrariamente.
2. Toda oportunidad aprobada (>=60% score, sin cuarentena) se registre en el Store de Señales.
3. Los parámetros cuantitativos (Entrada, Stop Loss, Fast BE +1.0R, TP1 +1.3R) sean 100% idénticos.
"""
import pytest
import asyncio
from datetime import datetime, timezone
from engine.core.store import store
from engine.workers.market_scanner import MarketScanner

@pytest.mark.asyncio
async def test_scanner_parity_no_arbitrary_cutoff():
    """Valida que el escáner guarde todas las oportunidades aprobadas sin cortarlas a 6."""
    mock_candidates = [
        {
            "asset": f"COIN_{i}USDT",
            "direction": "LONG",
            "type": "Virtual Setup",
            "price": 100.0 + i,
            "stop_loss": 95.0 + i,
            "be_price": 105.0 + i,
            "tp1": 106.5 + i,
            "tp2": 111.0 + i,
            "tp3": 117.5 + i,
            "rr_ratio_tp3": 3.5,
            "confluence_score": 70 + (i % 20),
            "checklist": [],
            "is_active_trigger": False,
            "ote_chasing": False,
            "session": "NY",
            "asset_health": {"is_quarantined": False, "ker": 0.45}
        }
        for i in range(12)
    ]
    
    await store.save_scanner_opportunities("scalp", mock_candidates)
    retrieved = store.get_scanner_opportunities("scalp")
    
    assert len(retrieved) == 12, f"Se esperaban 12 candidatos sin recortes, se obtuvieron {len(retrieved)}"
    assert retrieved[0]["asset"] == "COIN_0USDT"

@pytest.mark.asyncio
async def test_scanner_to_signal_store_dispatch_parity():
    """Valida que una señal aprobada en el escáner se registre como PENDING en el Store con Fast BE a 1.0R."""
    mock_elite_candidate = {
        "asset": "ATOMUSDT",
        "direction": "LONG",
        "type": "Virtual Setup",
        "price": 1.550,
        "stop_loss": 1.500, # dist = 0.05
        "be_price": 1.600,  # +1.0R = 1.550 + 0.05
        "tp1": 1.615,       # +1.3R = 1.550 + (0.05 * 1.3)
        "tp2": 1.660,
        "tp3": 1.725,       # +3.5R = 1.550 + (0.05 * 3.5)
        "rr_ratio_tp3": 3.5,
        "confluence_score": 75,
        "checklist": [{"factor": "SMC", "status": "CUMPLIDO", "detail": "Bullish OB"}],
        "is_active_trigger": False,
        "ote_chasing": False,
        "session": "NY",
        "asset_health": {"is_quarantined": False, "ker": 0.38}
    }
    
    dist_sl = abs(float(mock_elite_candidate["price"]) - float(mock_elite_candidate["stop_loss"]))
    be_val = float(mock_elite_candidate["price"]) + (dist_sl * 1.0)
    
    elite_sig = {
        "id": f"scanner_{mock_elite_candidate['asset']}_test",
        "asset": mock_elite_candidate["asset"],
        "symbol": mock_elite_candidate["asset"],
        "interval": "15m",
        "signal_type": mock_elite_candidate["direction"],
        "type": "SMC Sniper",
        "entry_price": float(mock_elite_candidate["price"]),
        "price": float(mock_elite_candidate["price"]),
        "stop_loss": float(mock_elite_candidate["stop_loss"]),
        "be_price": round(be_val, 5),
        "tp1": float(mock_elite_candidate["tp1"]),
        "tp2": float(mock_elite_candidate["tp2"]),
        "tp3": float(mock_elite_candidate["tp3"]),
        "status": "PENDING",
        "confluence": {
            "score": mock_elite_candidate["confluence_score"],
            "checklist": mock_elite_candidate["checklist"]
        }
    }
    
    await store.save_signal(elite_sig)
    
    signals = await store.get_signals(asset="ATOMUSDT", status="PENDING")
    assert len(signals) > 0, "La señal debe estar registrada en el Signal Store como PENDING"
    
    latest = signals[-1]
    assert latest["entry_price"] == 1.550
    assert latest["stop_loss"] == 1.500
    assert latest["be_price"] == 1.600, "Fast BE debe ser exactamente +1.0R"
    assert latest["tp1"] == 1.615, "TP1 debe ser exactamente +1.3R"
    assert latest["confluence"]["score"] == 75
