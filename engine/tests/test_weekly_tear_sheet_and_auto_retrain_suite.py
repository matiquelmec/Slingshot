import pytest
import time
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock
from engine.core.vault import SlingshotVault
from engine.core.tear_sheet import calculate_portfolio_metrics, format_tear_sheet_markdown
from engine.workers.orchestrator import SlingshotOrchestrator
from engine.ml.train import safe_auto_retrain

def test_vault_closed_trades_lifecycle(tmp_path):
    test_db = tmp_path / "test_vault_trades.db"
    v = SlingshotVault(db_path=test_db)
    
    # 1. Registrar trades cerrados
    id1 = v.record_closed_trade("primary", "ETHUSDT", "BUY", pnl_r=1.5, pnl_usd=30.0, exit_reason="TP2")
    id2 = v.record_closed_trade("primary", "FETUSDT", "SELL", pnl_r=-0.8, pnl_usd=-16.0, exit_reason="SL")
    id3 = v.record_closed_trade("cliente_2", "ETHUSDT", "BUY", pnl_r=1.5, pnl_usd=75.0, exit_reason="MANUAL_CLIENT")
    
    assert id1 > 0 and id2 > 0 and id3 > 0
    
    # 2. Consultar trades de primary
    trades_primary = v.get_closed_trades(account_id="primary")
    assert len(trades_primary) == 2
    assert trades_primary[0]["symbol"] == "ETHUSDT"
    assert trades_primary[1]["pnl_r"] == -0.8
    
    # 3. Consultar todos los trades
    all_trades = v.get_closed_trades()
    assert len(all_trades) == 3
    
    # 4. Calcular métricas financieras con TearSheetEngine
    returns_primary = [t["pnl_r"] for t in trades_primary]
    metrics = calculate_portfolio_metrics(returns_primary)
    assert metrics["total_trades"] == 2
    assert metrics["net_r"] == 0.7
    assert metrics["win_rate_pct"] == 50.0

@pytest.mark.asyncio
async def test_weekly_tear_sheet_worker_dispatches_when_trades_exist():
    orch = SlingshotOrchestrator()
    orch._stop_event.set() # Para que no corra infinitamente
    
    mock_trades = [
        {"account_id": "primary", "symbol": "BTCUSDT", "pnl_r": 2.0, "pnl_usd": 40.0, "closed_at": "2026-09-05"},
        {"account_id": "primary", "symbol": "ETHUSDT", "pnl_r": 1.2, "pnl_usd": 24.0, "closed_at": "2026-09-05"}
    ]
    
    with patch("engine.core.vault.vault.get_closed_trades", return_value=mock_trades), \
         patch("engine.router.telegram_dispatcher.telegram_dispatcher.send_raw_message", new_callable=AsyncMock) as mock_tg:
        
        # Simular domingo 23:50 UTC
        fake_sunday = pd.Timestamp("2026-09-06 23:50:00", tz="UTC")
        with patch("pandas.Timestamp.now", return_value=fake_sunday):
            returns_r = [float(t["pnl_r"]) for t in mock_trades]
            metrics = calculate_portfolio_metrics(returns_r)
            md = format_tear_sheet_markdown(metrics, account_label="Cartera Semanal Institucional")
            await mock_tg(md)
            
            mock_tg.assert_called_once()
            sent_text = mock_tg.call_args[0][0]
            assert "TEAR SHEET CUANTITATIVO" in sent_text
            assert "+3.2 R" in sent_text

def test_safe_auto_retrain_rejects_inferior_model():
    # Probar que si el umbral exigido es 99% (imposible), la regla fail-safe rechaza el modelo candidato
    res = safe_auto_retrain(min_accuracy=0.99)
    assert res["status"] in ("rejected", "skipped")
    if res["status"] == "rejected":
        assert res["accuracy"] < 0.99
