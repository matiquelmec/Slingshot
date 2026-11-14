"""
SOP-132: Auditoría Minimalista y Privacidad en TelegramDispatcher.
Valida:
1. Hard Sanity Gate: geometría SL/Entrada, distancia SL (0.25%-3.5%), drift vs Spot y veto 1D no ejecutado.
2. Preservación exacta de TP1/TP2/TP3 reales sin sobrescritura ficticia.
3. Privacidad total: cero montos en USD, balances, lotajes o nombres de cuenta en mensajes públicos.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from engine.router.telegram_dispatcher import TelegramDispatcher


def _make_dispatcher() -> TelegramDispatcher:
    d = TelegramDispatcher()
    d.enabled = True
    d.bot_token = "mock_token"
    d.chat_ids = ["123456"]
    return d


@pytest.mark.asyncio
async def test_sop132_preserves_real_tps_and_hides_account_financials():
    d = _make_dispatcher()
    signal = {
        "asset": "BTCUSDT",
        "signal_type": "LONG",
        "price": 90000.0,
        "current_price": 90400.0,
        "stop_loss": 89000.0,  # -1.11%
        "tp1": 91200.0,        # +1.2R
        "tp2": 92000.0,        # +2.0R
        "tp3": 93000.0,        # +3.0R
        "confluence_score": 84,
        "timeframe": "1h",
        "is_test": True,
        "execution_status": {"placed": True, "order_id": "ord_987654321"},
    }

    mock_resp = MagicMock(status_code=200)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        sent = await d.send_signal_alert(signal, account_profile="FTMO_100K")
        assert sent is True
        text = mock_post.call_args[1]["json"]["text"]

        # Niveles reales preservados
        assert "91200.00" in text
        assert "92000.00" in text
        assert "93000.00" in text
        assert "+1.2R" in text
        assert "+2.0R" in text
        assert "+3.0R" in text
        assert "90400.00" in text
        assert "ORDEN LÍMITE ACTIVA EN BITUNIX" in text

        # Privacidad estricta: cero datos de cuenta o USD
        for forbidden in ("FTMO", "Lots", " USD", "$", "Margen", "cliente_2", "Primary"):
            assert forbidden not in text


@pytest.mark.asyncio
async def test_sop132_blocks_1d_unplaced_and_drifted_or_bad_geometry_signals():
    d = _make_dispatcher()

    # 1. Bloqueo 1D no ejecutada
    sig_1d = {
        "asset": "SOLUSDT",
        "signal_type": "LONG",
        "price": 150.0,
        "stop_loss": 147.0,
        "confluence_score": 85,
        "timeframe": "1d",
        "is_test": False,
    }
    with patch.object(d._vault, "is_signal_in_cooldown", return_value=(False, 0, 0.0)):
        assert await d.send_signal_alert(sig_1d) is False

    # 2. Bloqueo por drift excesivo vs spot (> 1.2% en 15m)
    sig_drift = {
        "asset": "ETHUSDT",
        "signal_type": "LONG",
        "price": 2500.0,
        "current_price": 2650.0,  # ~5.66% lejos
        "stop_loss": 2450.0,
        "confluence_score": 80,
        "timeframe": "15m",
        "is_test": True,
    }
    assert await d.send_signal_alert(sig_drift) is False

    # 3. Bloqueo por geometría invertida (LONG con SL >= Entrada)
    sig_bad_geom = {
        "asset": "ETHUSDT",
        "signal_type": "LONG",
        "price": 2500.0,
        "stop_loss": 2520.0,
        "confluence_score": 80,
        "timeframe": "1h",
        "is_test": True,
    }
    assert await d.send_signal_alert(sig_bad_geom) is False

    # 4. Bloqueo por SL demasiado amplio (> 3.5%)
    sig_wide_sl = {
        "asset": "ETHUSDT",
        "signal_type": "SHORT",
        "price": 2500.0,
        "stop_loss": 2650.0,  # 6%
        "confluence_score": 80,
        "timeframe": "1h",
        "is_test": True,
    }
    assert await d.send_signal_alert(sig_wide_sl) is False


@pytest.mark.asyncio
async def test_sop132_lifecycle_and_heartbeat_hide_usd_and_account_info(tmp_path, monkeypatch):
    import engine.router.telegram_dispatcher as td
    monkeypatch.setattr(td, "_STATE_FILE", tmp_path / "telegram_sent_state.json")
    d = _make_dispatcher()
    with patch.object(d, "send_raw_message", new_callable=AsyncMock, return_value=True) as mock_raw:
        await d.send_trade_fill_alert("BTCUSDT", "BUY", 90000.0, qty=0.45, account_label="cliente_2")
        fill_msg = mock_raw.call_args[0][0]
        assert "0.45" not in fill_msg
        assert "cliente_2" not in fill_msg
        assert "$" not in fill_msg

        await d.send_tp_hit_alert("BTCUSDT", "TP1 (50%)", 91200.0, pnl_usd=185.50, is_be=True, pnl_r=1.2)
        tp_msg = mock_raw.call_args[0][0]
        assert "185.50" not in tp_msg
        assert "USDT" not in tp_msg
        assert "+1.20R" in tp_msg

        await d.send_trade_closed_alert("BTCUSDT", "TP2_HIT", 92000.0, pnl_usd=420.00, pnl_r=2.0)
        close_msg = mock_raw.call_args[0][0]
        assert "420.00" not in close_msg
        assert " USD" not in close_msg
        assert "$" not in close_msg
        assert "+2.00R" in close_msg

        await d.send_heartbeat_report({
            "uptime_hours": 10.0,
            "latency_ms": 12.0,
            "ftmo_drawdown_pct": -1.5,
            "free_margin_usdt": 9999.99,
            "positions": [{"symbol": "BTCUSDT", "side": "LONG", "pnl": 350.0, "sl": "89000"}],
        })
        hb_msg = mock_raw.call_args[0][0]
        assert "9,999.99" not in hb_msg
        assert "350.0" not in hb_msg
        assert "FTMO" not in hb_msg
