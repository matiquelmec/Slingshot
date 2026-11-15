"""
SOP-133: Pruebas unitarias del Bucle de Aprendizaje Autónomo Acotado y Centinelas en Vivo.
Valida:
1. Auto-inicialización de DriftMonitor en SlingshotML.predict_live.
2. Embargo temporal (16 velas) y lectura prioritaria de MemoryStore en RollingWalkForwardTrainer.
3. Bandit Bayesiano acotado [-8, +8] en BlackBox (neutro si < 15 trades).
4. Veto L2 en vivo (SOP-108) dentro de NexusNode.process_limit_setup.
5. Ajuste de Chandelier (1.5x -> 1.0x ATR) por Funding Drag (SOP-109) en TradeManager.
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.core.memory import BlackBox
from engine.execution.nexus import NexusNode
from engine.ml.drift_monitor import drift_monitor
from engine.ml.inference import SlingshotML
from engine.ml.train_rolling import RollingWalkForwardTrainer
from engine.workers.trade_manager import TradeManager


def test_sop133_blackbox_bounded_adaptive_bonus(tmp_path):
    bb = BlackBox(storage_path=str(tmp_path / "bb.json"))

    sig = {
        "asset": "BTCUSDT",
        "regime": "BULL_EXPANSION",
        "confluence": {
            "rvol": 2.0,
            "checklist": [
                {"factor": "Zonas POI", "status": "CONFIRMADO"},
                {"factor": "Liquidez", "status": "Sweep: True"},
            ],
        },
        "fib_ote": {"is_in_ote": True},
    }

    # Con < 15 trades debe devolver 0 para evitar overfitting
    bonus, _ = bb.get_adaptive_factor_bonus(sig, min_samples=15, max_bonus=8)
    assert bonus == 0

    # Poblar 20 trades: los que tienen OB + Sweep ganan, los que no pierden
    for i in range(12):
        bb.memory.append({
            "asset": "BTCUSDT",
            "result": "TAKE_PROFIT",
            "fingerprint": {"regime": "BULL_EXPANSION", "rvol": 2.0, "has_ob": True, "has_sweep": True, "is_in_ote": True},
        })
    for i in range(8):
        bb.memory.append({
            "asset": "SOLUSDT",
            "result": "STOP_LOSS",
            "fingerprint": {"regime": "CHOPPY", "rvol": 0.8, "has_ob": False, "has_sweep": False, "is_in_ote": False},
        })

    bonus_pos, detail = bb.get_adaptive_factor_bonus(sig, min_samples=15, max_bonus=8)
    assert 0 < bonus_pos <= 8
    assert "Bandit Bayesiano" in detail


def test_sop133_rolling_trainer_embargo_and_store_priority():
    trainer = RollingWalkForwardTrainer(n_splits=3)
    assert trainer.embargo_bars == 16

    n = 400
    X = pd.DataFrame({"f1": np.linspace(0, 1, n), "f2": np.random.RandomState(7).randn(n)})
    y = pd.Series(np.random.RandomState(7).randint(0, 2, n))

    mean_acc, mean_prec, model = trainer.execute_walk_forward_validation(X, y)
    assert model is not None
    assert 0.0 <= mean_acc <= 1.0
    assert 0.0 <= mean_prec <= 1.0

    fake_candles = [{"timestamp": i, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 100.0} for i in range(600)]
    with patch("engine.core.store.store._candle_history", {"BTCUSDT_15m": fake_candles}):
        loaded = trainer.load_recent_candles_from_store("BTCUSDT")
        assert loaded is not None
        assert len(loaded) == 600


def test_sop133_drift_monitor_auto_initializes_on_predict_live():
    ml = SlingshotML()
    ml.is_loaded = True
    ml.model = MagicMock()
    ml.model.feature_names_in_ = np.array(["rsi", "rvol_feature"])
    ml.model.predict_proba.return_value = np.array([[0.3, 0.7]])

    # Simular features_df de 40 filas con columnas de KEY_FEATURES
    fake_feat = pd.DataFrame({
        "rsi": np.linspace(35, 65, 40),
        "macd": np.linspace(-1, 1, 40),
        "macd_signal": np.linspace(-0.5, 0.5, 40),
        "bb_width": np.full(40, 0.03),
        "sma_fast": np.full(40, 100.0),
        "sma_slow": np.full(40, 99.0),
        "volume": np.full(40, 1000.0),
        "atr": np.full(40, 1.5),
        "rvol_feature": np.full(40, 1.4),
        "ob_bullish": np.zeros(40),
        "ob_bearish": np.zeros(40),
        "fvg_bullish": np.zeros(40),
        "fvg_bearish": np.zeros(40),
        "dist_ema21": np.zeros(40),
        "return_5": np.zeros(40),
    })

    drift_monitor._reference_df = None
    drift_monitor._reference_bins = {}

    df_raw = pd.DataFrame({"close": np.full(60, 100.0)})
    with patch.object(ml.engineer, "generate_features", return_value=fake_feat):
        res = ml.predict_live(df_raw)
        assert res["direction"] == "ALCISTA"
        assert drift_monitor._reference_df is not None
        assert len(drift_monitor._reference_bins) > 0


@pytest.mark.asyncio
async def test_sop133_nexus_l2_microstructure_blocks_heavy_ask_wall():
    nexus = NexusNode(dry_run=False)
    mock_executor = MagicMock()
    mock_executor.dry_run = False
    mock_executor.get_ticker_price = AsyncMock(return_value=100.0)
    mock_executor.get_pending_positions = AsyncMock(return_value=[])
    mock_executor.get_pending_orders = AsyncMock(return_value=[])
    mock_executor.get_available_margin_usdt = AsyncMock(return_value=1000.0)
    mock_executor.get_net_available_margin_usdt = AsyncMock(return_value=1000.0)
    mock_executor.get_account_balance = AsyncMock(return_value=1000.0)
    mock_executor.get_symbol_precision = AsyncMock(return_value=(3, 2))
    mock_executor.get_orderbook_depth = AsyncMock(return_value={
        "bids": [(100.0 - i * 0.05, 5.0) for i in range(20)],
        "asks": [(100.02 + i * 0.05, 100.0) for i in range(20)],  # Muro vendedor masivo
    })
    mock_executor.place_limit_signal = AsyncMock(return_value={"status": "success", "order_id": "should_not_place"})

    mock_account = MagicMock(
        account_id="primary",
        label="Primary",
        is_primary=True,
        risk_pct=0.025,
        risk_multiplier=1.0,
        max_risk_pct=1.0,
        max_notional_mult=5.0,
    )
    nexus.account_manager.get_all_accounts = MagicMock(return_value=[mock_account])
    nexus.account_manager.get_enabled_accounts = MagicMock(return_value=[mock_account])
    nexus.account_manager.get_executor = MagicMock(return_value=mock_executor)

    signal = {
        "asset": "SOLUSDT",
        "symbol": "SOLUSDT",
        "signal_type": "LONG",
        "direction": "LONG",
        "type": "SMC Sniper",
        "price": 99.8,
        "stop_loss": 98.8,
        "tp1": 101.0,
        "tp2": 101.8,
        "tp3": 102.8,
        "confluence_score": 82,
        "interval": "15m",
        "atr_value": 1.0,
        "asset_health": {"ker": 0.45, "adx": 30.0},
    }

    with patch("engine.workers.market_scanner.is_trade_allowed_sop18", return_value=True), \
         patch("engine.execution.nexus.logger.warning") as mock_warn:
        res = await nexus.process_limit_setup(signal)

    assert res["placed"] is False
    assert res["status"] == "REJECTED_EXCHANGE"
    warn_msgs = " ".join(str(call.args[0]) for call in mock_warn.call_args_list if call.args)
    assert "OBI_VENTA_DOMINANTE" in warn_msgs
    mock_executor.get_orderbook_depth.assert_awaited_once()
    mock_executor.place_limit_signal.assert_not_awaited()


def test_sop133_trade_manager_funding_drag_tightens_chandelier():
    tm = TradeManager()
    sig = {
        "asset": "FETUSDT",
        "signal_type": "LONG",
        "entry_price": 1.00,
        "price": 1.00,
        "stop_loss": 0.98,  # r_dist = 0.02
        "tp2": 1.04,
        "tp3": 1.06,
        "days_open": 4.0,
        "position_size_usdt": 5000.0,
        "risk_amount_usdt": 125.0,
    }
    atr_val = 0.02
    current_price = 1.07  # +3.5R

    with patch("engine.core.store.store._market_states", {"FETUSDT": {"funding_rate": 0.0001}}):
        sl_normal = tm._calculate_runner_ratchet_sl(sig, current_price, is_long=True, atr_val=atr_val, df=None)

    with patch("engine.core.store.store._market_states", {"FETUSDT": {"funding_rate": 0.0006}}):  # ~65.7% APR -> WARNING_TIGHTEN
        sl_tight = tm._calculate_runner_ratchet_sl(sig, current_price, is_long=True, atr_val=atr_val, df=None)

    # Normal: max(tp2=1.04, 1.07 - 1.5*0.02 = 1.04) = 1.04
    # Tight:  max(tp2=1.04, 1.07 - 1.0*0.02 = 1.05) = 1.05
    assert sl_normal == pytest.approx(1.04, abs=1e-6)
    assert sl_tight == pytest.approx(1.05, abs=1e-6)
    assert sl_tight > sl_normal
