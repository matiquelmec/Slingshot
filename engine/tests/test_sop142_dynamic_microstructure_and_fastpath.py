import pytest
from unittest.mock import patch
from engine.core.strategy_ssot import (
    is_directional_setup_allowed_sop137,
    is_toxic_hour_sop137,
)
from engine.analytics.order_book_microstructure_sentinel import OrderBookMicrostructureSentinel
from engine.analytics.funding_rate_drag_sentinel import FundingRateDragSentinel
from engine.workers.trade_manager import TradeManager


def test_sop142_dynamic_directional_override_and_backcompat():
    # Retrocompatibilidad sin telemetría viva (SOP-137)
    assert is_directional_setup_allowed_sop137("INJUSDT", "LONG") is False
    assert is_directional_setup_allowed_sop137("INJUSDT", "SHORT") is True
    assert is_directional_setup_allowed_sop137("SOLUSDT", "SHORT") is False
    assert is_directional_setup_allowed_sop137("SOLUSDT", "LONG") is True

    # Override dinámico por ruptura institucional (>= +1.5σ y OBI >= +0.20)
    assert is_directional_setup_allowed_sop137("INJUSDT", "LONG", rs_zscore_vs_btc=1.65, obi_score=0.25) is True
    assert is_directional_setup_allowed_sop137("SOLUSDT", "SHORT", rs_zscore_vs_btc=-1.70, obi_score=-0.30) is True

    # Veto dinámico contra fuerza relativa extrema
    assert is_directional_setup_allowed_sop137("SOLUSDT", "LONG", rs_zscore_vs_btc=-1.90, obi_score=0.10) is False


def test_sop142_continuous_hour_toxicity_gate():
    # Sin telemetría L2 mantiene calendario estático
    assert is_toxic_hour_sop137(7) is True
    assert is_toxic_hour_sop137(15) is False

    # Con liquidez L2 excepcional desbloquea hora marcada como tóxica
    assert is_toxic_hour_sop137(7, spread_bps=2.5, depth_usd=220000.0, ker=0.55) is False

    # Cualquier hora se bloquea si spread > 8 bps o KER < 0.20
    assert is_toxic_hour_sop137(15, spread_bps=9.5, depth_usd=200000.0, ker=0.55) is True
    assert is_toxic_hour_sop137(15, spread_bps=2.0, depth_usd=200000.0, ker=0.15) is True


def test_sop142_liquidation_exhaustion_and_adverse_selection():
    sentinel = OrderBookMicrostructureSentinel()

    # Barrido bajista extremo + absorción compradora L2 -> LONG Maker Post-Only
    sig_long = sentinel.detect_liquidation_exhaustion_reversion(
        asset="SOLUSDT",
        price_change_atr=-2.8,
        obi_score=0.28,
        spread_bps=3.2,
    )
    assert sig_long.triggered is True
    assert sig_long.direction == "LONG"
    assert sig_long.execution_mode == "MAKER_POST_ONLY"

    # Escudo anti-selección adversa en orden límite LONG con libro vendedor extremo
    should_cancel, reason = sentinel.evaluate_limit_order_adverse_selection("LONG", obi_score=-0.62, spread_bps=4.0)
    assert should_cancel is True
    assert "SELECCION_ADVERSA_LONG" in reason


def test_sop142_funding_squeeze_harvester():
    sentinel = FundingRateDragSentinel()
    # Funding +0.08% cada 8h (~87.6% APR) favorece SHORT cobrando carry
    opp = sentinel.detect_funding_squeeze_opportunity(
        asset="FETUSDT",
        direction="SHORT",
        funding_rate_8h=0.0008,
        obi_score=-0.10,
    )
    assert opp.triggered is True
    assert opp.recommended_direction == "SHORT"
    assert opp.confluence_boost_pts == 8.0
    assert opp.priority_multiplier == 1.30


@pytest.mark.asyncio
async def test_sop142_trade_manager_fast_path_and_debounce():
    tm = TradeManager()
    fake_positions = {
        "primary_INJUSDT": {
            "asset": "INJUSDT",
            "direction": "LONG",
            "interval": "15m",
            "entry_price": 20.0,
            "initial_stop_loss": 19.0,  # 1R = $1.00
        }
    }
    with patch("engine.execution.nexus.nexus") as mock_nexus:
        mock_nexus._active_positions = fake_positions

        # Perforación de -0.65R con OBI adverso -> SOP25_FAST_PATH_EXIT
        res1 = await tm.evaluate_realtime_tick_protection("INJUSDT", live_price=19.30, obi_score=-0.20, cooldown_sec=5.0)
        assert len(res1) == 1
        assert res1[0]["action"] == "SOP25_FAST_PATH_EXIT"

        # Debounce inmediato evita ráfagas duplicadas en el siguiente tick
        res2 = await tm.evaluate_realtime_tick_protection("INJUSDT", live_price=19.25, obi_score=-0.25, cooldown_sec=5.0)
        assert res2 == []
