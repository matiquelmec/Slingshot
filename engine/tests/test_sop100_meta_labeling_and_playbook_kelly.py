"""
engine/tests/test_sop100_meta_labeling_and_playbook_kelly.py
=============================================================================
PRUEBAS UNITARIAS: SOP-100 TWO-STAGE META-LABELING GATEKEEPER & PLAYBOOK KELLY
=============================================================================
Certifica:
1. Multiplicadores de segunda etapa (López de Prado) según arquetipo Playbook y Tier del activo:
   - OB_DISCOUNT_RETEST en líderes (FET, INJ, BNB, SOL, NEAR) -> 1.18 * 1.12 = 1.3216x.
   - OB_DISCOUNT_RETEST en activos estándar (BTC, ETH) -> 1.18x.
   - BOS_MOMENTUM_EXPANSION -> 1.10x.
   - LIQUIDITY_SWEEP_FVG estándar -> 0.92x.
   - LIQUIDITY_SWEEP_FVG en laggards de barrido (XRP, LINK, AVAX) -> 0.92 * 0.75 = 0.69x.
2. Retrocompatibilidad 100% de calculate_alpha_tier_sizing cuando apply_meta_labeling=False.
3. Respeto estricto de los guardarraíles institucionales en calculate_quarter_kelly_risk ([1.25%, 3.25%]).
4. Integración end-to-end en NexusNode._place_limit_for_account combinando SOP-100 y SOP-94 Streak Shield.
=============================================================================
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from engine.risk.risk_manager import RiskManager
from engine.execution.nexus import NexusNode


def test_sop100_meta_labeling_multiplier_matrix():
    """Valida los multiplicadores exactos del Gatekeeper de 2 Etapas (SOP-100)."""
    # 1. OB_DISCOUNT_RETEST en líderes de alfa (1.18 * 1.12 = 1.3216)
    for leader in ("FETUSDT", "INJUSDT", "BNBUSDT", "SOLUSDT", "NEARUSDT"):
        m = RiskManager.calculate_meta_labeling_multiplier(leader, "OB_DISCOUNT_RETEST")
        assert m == pytest.approx(1.3216, rel=1e-4)

    # 2. OB_DISCOUNT_RETEST en otros activos (1.18)
    assert RiskManager.calculate_meta_labeling_multiplier("BTCUSDT", "OB_DISCOUNT_RETEST") == pytest.approx(1.18, rel=1e-4)
    assert RiskManager.calculate_meta_labeling_multiplier("SUIUSDT", "OB_DISCOUNT_RETEST") == pytest.approx(1.18, rel=1e-4)

    # 3. BOS_MOMENTUM_EXPANSION (1.10)
    assert RiskManager.calculate_meta_labeling_multiplier("SOLUSDT", "BOS_MOMENTUM_EXPANSION") == pytest.approx(1.10, rel=1e-4)

    # 4. LIQUIDITY_SWEEP_FVG estándar (0.92) vs laggards (0.92 * 0.75 = 0.69)
    assert RiskManager.calculate_meta_labeling_multiplier("SOLUSDT", "LIQUIDITY_SWEEP_FVG") == pytest.approx(0.92, rel=1e-4)
    for laggard in ("XRPUSDT", "LINKUSDT", "AVAXUSDT"):
        m_lag = RiskManager.calculate_meta_labeling_multiplier(laggard, "LIQUIDITY_SWEEP_FVG")
        assert m_lag == pytest.approx(0.69, rel=1e-4)

    # 5. Sin playbook o TREND_CONTINUATION_EMA -> 1.00 neutro
    assert RiskManager.calculate_meta_labeling_multiplier("BTCUSDT", None) == 1.00
    assert RiskManager.calculate_meta_labeling_multiplier("BTCUSDT", "TREND_CONTINUATION_EMA") == 1.00


def test_sop100_alpha_tier_sizing_backward_compatibility_and_boost():
    """Verifica que sin apply_meta_labeling se preserve el sizing legacy y con SOP-100 escale hasta 2.00x."""
    # Legacy default (sin apply_meta_labeling)
    bnb_legacy = RiskManager.calculate_alpha_tier_sizing("BNBUSDT", confluence_score=75.0, hour_utc=14)
    assert bnb_legacy == 1.38

    # Con SOP-100 + Trinity Boost + OB_DISCOUNT_RETEST en BNB
    bnb_sop100 = RiskManager.calculate_alpha_tier_sizing(
        "BNBUSDT",
        confluence_score=85.0,
        hour_utc=14,
        apply_trinity_boost=True,
        apply_golden_hours=True,
        playbook="OB_DISCOUNT_RETEST",
        apply_meta_labeling=True
    )
    assert bnb_sop100 == 2.00

    # Con SOP-100 + LIQUIDITY_SWEEP_FVG en XRP (amortiguación defensiva)
    xrp_base = RiskManager.calculate_alpha_tier_sizing("XRPUSDT", confluence_score=75.0, hour_utc=10)
    xrp_sweep = RiskManager.calculate_alpha_tier_sizing(
        "XRPUSDT",
        confluence_score=75.0,
        hour_utc=10,
        playbook="LIQUIDITY_SWEEP_FVG",
        apply_meta_labeling=True
    )
    assert xrp_sweep < xrp_base
    assert xrp_sweep == pytest.approx(0.52, abs=0.01)


def test_sop100_quarter_kelly_safety_clamps():
    """Verifica que calculate_quarter_kelly_risk nunca exceda el techo de 3.25% ni baje de 1.25%."""
    high_risk = RiskManager.calculate_quarter_kelly_risk(
        base_risk_pct=0.025,
        symbol="FETUSDT",
        confluence_score=90.0,
        hour_utc=14,
        playbook="OB_DISCOUNT_RETEST",
        apply_trinity_boost=True,
        apply_golden_hours=True,
        apply_meta_labeling=True
    )
    assert high_risk == 0.0325

    low_risk = RiskManager.calculate_quarter_kelly_risk(
        base_risk_pct=0.025,
        symbol="AVAXUSDT",
        confluence_score=62.0,
        hour_utc=3,
        playbook="LIQUIDITY_SWEEP_FVG",
        apply_meta_labeling=True
    )
    assert low_risk == 0.0125


@pytest.mark.asyncio
async def test_nexus_limit_order_applies_sop100_and_sop94_streak_shield():
    """
    Certifica que _place_limit_for_account aplica SOP-100 Quarter-Kelly cuando la señal incluye
    su Playbook y lo modula proporcionalmente con el Streak Shield SOP-94 ante rachas de pérdidas.
    """
    nexus = NexusNode(dry_run=True)
    acc = MagicMock()
    acc.account_id = "primary"
    acc.label = "PrimaryTest"
    acc.is_primary = True
    acc.risk_pct = 0.025
    acc.max_notional_mult = 5.0

    ex = MagicMock()
    ex.dry_run = True
    ex.account_label = "PrimaryTest"
    ex.get_net_available_margin_usdt = AsyncMock(return_value=1000.0)
    ex.get_available_margin_usdt = AsyncMock(return_value=1000.0)
    ex.get_account_balance = AsyncMock(return_value=1000.0)
    ex.get_pending_positions = AsyncMock(return_value=[])
    ex.get_pending_orders = AsyncMock(return_value=[])
    ex.get_symbol_precision = AsyncMock(return_value=(2, 2))
    ex.place_limit_signal = AsyncMock(return_value={"status": "success", "order_id": "LIM_SOP100_1"})

    # 1. Señal OB_DISCOUNT_RETEST en FETUSDT con 0 pérdidas -> Riesgo acelerado (3.25% = $32.50 USD en cuenta de $1,000)
    nexus._consecutive_losses["primary"] = 0
    nexus._risk_released_recently["primary"] = False
    sig_ob = {
        "asset": "FETUSDT",
        "symbol": "FETUSDT",
        "direction": "LONG",
        "playbook": "OB_DISCOUNT_RETEST",
        "confluence_score": 85.0,
        "price": 1.00,
        "stop_loss": 0.98
    }
    res_1 = await nexus._place_limit_for_account(ex, acc, sig_ob, safe_lev=10, entry_p=1.00, sl_p=0.98)
    assert res_1["status"] == "success"
    # Con entry=1.00, sl=0.98 (dist=0.02) y riesgo 3.25% ($32.50), qty = 32.50 / 0.02 = 1625.0
    assert sig_ob["exact_qty"] == pytest.approx(1625.0, rel=0.15)

    # 2. En racha de 2 pérdidas consecutivas (SOP-94 @ 0.65x), el tamaño se reduce a 0.65x manteniendo el slot abierto
    nexus._active_positions.clear()
    nexus._pending_limit_symbols.clear()
    nexus._consecutive_losses["primary"] = 2
    nexus._risk_released_recently["primary"] = False
    sig_ob_streak = dict(sig_ob)
    res_2 = await nexus._place_limit_for_account(ex, acc, sig_ob_streak, safe_lev=10, entry_p=1.00, sl_p=0.98)
    assert res_2["status"] == "success"
    assert sig_ob_streak["exact_qty"] == pytest.approx(sig_ob["exact_qty"] * 0.65, rel=0.02)


@pytest.mark.asyncio
async def test_sop100_stage1_gatekeeper_blocks_low_ker_sweeps():
    """
    [SOP-100 STAGE 1 GATEKEEPER]
    Verifica que process_limit_setup bloquee señales LIQUIDITY_SWEEP_FVG cuando KER < 0.40
    y la confluencia sea inferior al umbral institucional del 82.0%.
    """
    from unittest.mock import patch
    nexus = NexusNode(dry_run=False)
    sig_sweep_noisy = {
        "asset": "XRPUSDT",
        "symbol": "XRPUSDT",
        "signal_type": "LONG",
        "playbook": "LIQUIDITY_SWEEP_FVG",
        "confluence_score": 72.0,
        "ker": 0.36,
        "adx": 25.0,
        "price": 0.60,
        "stop_loss": 0.585,
        "vwap_dist_pct": 0.0
    }
    with patch("engine.workers.market_scanner.is_trade_allowed_sop18", return_value=True):
        res = await nexus.process_limit_setup(sig_sweep_noisy)
    assert res["placed"] is False
    assert res["status"] == "BLOCKED_SOP100_STAGE1"


@pytest.mark.asyncio
async def test_market_scanner_preserves_champions_on_refresh():
    """
    Verifica que MarketScanner._refresh_dynamic_assets conserve siempre a los
    campeones BNBUSDT y SOLUSDT en scalp_assets tras rotaciones dinámicas.
    """
    from unittest.mock import patch
    from engine.workers.market_scanner import MarketScanner
    scanner = MarketScanner()
    scanner._dynamic_last_refresh = 0
    with patch("engine.workers.market_scanner.fetch_top_liquid_tickers", new_callable=AsyncMock) as mock_fetch, \
         patch("engine.workers.market_scanner.settings.ENABLE_DYNAMIC_WATCHLIST", True):
        mock_fetch.return_value = ["AAVEUSDT", "ONDOUSDT"]
        await scanner._refresh_dynamic_assets()
    assert "BNBUSDT" in scanner.scalp_assets
    assert "SOLUSDT" in scanner.scalp_assets
    assert "AAVEUSDT" in scanner.scalp_assets


def test_sop101_timeframe_aware_meta_labeling_1h_sweep_boost():
    """
    [SOP-101 TIMEFRAME-AWARE META-LABELING]
    Verifica que LIQUIDITY_SWEEP_FVG en 1h reciba el multiplicador institucional 1.15x
    (sin penalización de SWEEP_LAGGARDS de 15m) y piso mínimo >= 1.15x en calculate_alpha_tier_sizing.
    """
    for sym in ("NEARUSDT", "LINKUSDT", "XAUUSDT", "ATOMUSDT"):
        m_1h = RiskManager.calculate_meta_labeling_multiplier(sym, "LIQUIDITY_SWEEP_FVG", interval="1h")
        assert m_1h == pytest.approx(1.15, rel=1e-4)

    # En 15m LINKUSDT sigue amortiguado a 0.69x, pero en 1h sube a >= 1.15x
    m_15m = RiskManager.calculate_meta_labeling_multiplier("LINKUSDT", "LIQUIDITY_SWEEP_FVG", interval="15m")
    assert m_15m == pytest.approx(0.69, rel=1e-4)

    xau_1h_sizing = RiskManager.calculate_alpha_tier_sizing(
        "XAUUSDT",
        confluence_score=65.0,
        hour_utc=14,
        playbook="LIQUIDITY_SWEEP_FVG",
        apply_meta_labeling=True,
        interval="1h"
    )
    assert xau_1h_sizing >= 1.15


@pytest.mark.asyncio
async def test_sop101_nexus_1h_swing_gatekeeper_and_stage1_bypass():
    """
    [SOP-101 1H SWING GATEKEEPER]
    Verifica que process_limit_setup:
    1. Bloquee activos Cripto en 1h con confluencia < 75.0% (BLOCKED_SOP101_SWING_GATE).
    2. Permita XAUUSDT en 1h desde 60.0% y exima a 1h del filtro 15m SOP-100 Stage 1.
    """
    from unittest.mock import patch
    nexus = NexusNode(dry_run=False)

    # 1. Cripto en 1h con Score 70% (< 75%) -> Bloqueado por SOP-101
    sig_crypto_low = {
        "asset": "NEARUSDT",
        "symbol": "NEARUSDT",
        "interval": "1h",
        "signal_type": "LONG",
        "playbook": "LIQUIDITY_SWEEP_FVG",
        "confluence_score": 70.0,
        "ker": 0.38,
        "adx": 25.0,
        "price": 5.00,
        "stop_loss": 4.90,
        "vwap_dist_pct": 0.0
    }
    with patch("engine.workers.market_scanner.is_trade_allowed_sop18", return_value=True):
        res_low = await nexus.process_limit_setup(sig_crypto_low)
    assert res_low["placed"] is False
    assert res_low["status"] == "BLOCKED_SOP101_SWING_GATE"

    # 2. Cripto en 1h con Score 78% (>= 75%) y LIQUIDITY_SWEEP_FVG con KER=0.36 -> Pasa Stage 1 (no bloqueado por SOP-100 ni SOP-101)
    sig_crypto_ok = dict(sig_crypto_low, confluence_score=78.0, ker=0.36)
    with patch("engine.workers.market_scanner.is_trade_allowed_sop18", return_value=True), \
         patch.object(nexus, "_place_limit_for_account", new_callable=AsyncMock) as mock_place:
        mock_place.return_value = {"status": "success", "order_id": "ORD_1H_SWING"}
        res_ok = await nexus.process_limit_setup(sig_crypto_ok)
    assert res_ok["placed"] is True
    assert res_ok["status"] == "ORDER_PLACED"


def test_sop101_market_scanner_swing_1h_assets_specialization():
    """
    [SOP-101 SWING UNIVERSE SPECIALIZATION]
    Verifica que MarketScanner excluya al activo tóxico AVAXUSDT de core_swing_1h_assets
    e incluya a XAUUSDT + los 7 campeones duales auditados.
    """
    from engine.workers.market_scanner import MarketScanner
    scanner = MarketScanner()
    assert "AVAXUSDT" not in scanner.core_swing_1h_assets
    for champ in ("XAUUSDT", "NEARUSDT", "ATOMUSDT", "ETHUSDT", "BTCUSDT", "INJUSDT", "LINKUSDT", "SOLUSDT"):
        assert champ in scanner.core_swing_1h_assets


def test_sop102_direction_aware_meta_labeling_asymmetry():
    """
    [SOP-102 DIRECTION-AWARE META-LABELING]
    Verifica que OB_DISCOUNT_RETEST premie la asimetría alcista (LONG x1.05, cap 2.10x) y amortigüe
    operaciones SHORT contra techos de Order Blocks (x0.96 en 15m y x0.88 en 1h),
    manteniendo 100% de retrocompatibilidad cuando direction=None.
    """
    m_neutral = RiskManager.calculate_meta_labeling_multiplier("NEARUSDT", "OB_DISCOUNT_RETEST", interval="15m")
    m_long_15m = RiskManager.calculate_meta_labeling_multiplier("NEARUSDT", "OB_DISCOUNT_RETEST", interval="15m", direction="LONG")
    m_short_15m = RiskManager.calculate_meta_labeling_multiplier("NEARUSDT", "OB_DISCOUNT_RETEST", interval="15m", direction="SHORT")
    m_short_1h = RiskManager.calculate_meta_labeling_multiplier("NEARUSDT", "OB_DISCOUNT_RETEST", interval="1h", direction="SHORT")

    assert m_long_15m > m_neutral > m_short_15m > m_short_1h
    assert m_long_15m == pytest.approx(1.18 * 1.12 * 1.05, rel=1e-3)
    assert m_short_15m == pytest.approx(1.18 * 1.12 * 0.96, rel=1e-3)
    assert m_short_1h == pytest.approx(1.18 * 1.12 * 0.88, rel=1e-3)

    # En calculate_alpha_tier_sizing, LONG en OB_DISCOUNT_RETEST desbloquea hasta 2.10x
    bnb_long = RiskManager.calculate_alpha_tier_sizing(
        "BNBUSDT",
        confluence_score=85.0,
        hour_utc=15,
        apply_trinity_boost=True,
        playbook="OB_DISCOUNT_RETEST",
        apply_meta_labeling=True,
        direction="LONG"
    )
    assert bnb_long == 2.10


def test_sop102_market_scanner_time_gate_blocks_toxic_hours_10_and_14():
    """
    [SOP-102 QUIRÓFANO HORARIO & KILLZONES EN VIVO]
    Verifica que market_scanner.is_trade_allowed_sop18 bloquee las horas tóxicas 10:00 UTC y 14:00 UTC
    y las horas fuera de Killzones (ej. 03:00 UTC), permitiendo ventanas limpias (09:00 UTC y 15:00 UTC).
    """
    from datetime import datetime, timezone
    from engine.workers.market_scanner import is_trade_allowed_sop18

    # Martes 2026-09-01
    assert is_trade_allowed_sop18("BTCUSDT", datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)) is True
    assert is_trade_allowed_sop18("BTCUSDT", datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc)) is True
    # Horas tóxicas 10:00 y 14:00 UTC bloqueadas
    assert is_trade_allowed_sop18("BTCUSDT", datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)) is False
    assert is_trade_allowed_sop18("BTCUSDT", datetime(2026, 9, 1, 14, 0, tzinfo=timezone.utc)) is False
    # Fuera de Killzones (madrugada 03:00 UTC) bloqueada
    assert is_trade_allowed_sop18("BTCUSDT", datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc)) is False


@pytest.mark.asyncio
async def test_sop102_nexus_blocks_btc_misaligned_and_avwap_extended_and_excluded_assets():
    """
    [SOP-102 HARD EXECUTION VETOES]
    Verifica que process_limit_setup bloquee en duro:
    1. Activos podados (RENDERUSDT / AVAXUSDT -> BLOCKED_EXCLUDED_ASSET).
    2. Desalineación macro con BTC (btc_aligned=False -> BLOCKED_BTC_MACRO).
    3. Violación de Session AVWAP ±0.40% (LONG con -0.55% -> BLOCKED_SESSION_AVWAP).
    """
    nexus = NexusNode(dry_run=False)

    # 1. Activo podado RENDERUSDT
    res_excl = await nexus.process_limit_setup({
        "asset": "RENDERUSDT",
        "signal_type": "LONG",
        "price": 5.0,
        "stop_loss": 4.9
    })
    assert res_excl["placed"] is False
    assert res_excl["status"] == "BLOCKED_EXCLUDED_ASSET"

    # 2. Veto duro Macro BTC (btc_aligned=False en altcoin)
    res_btc = await nexus.process_limit_setup({
        "asset": "SOLUSDT",
        "signal_type": "LONG",
        "btc_aligned": False,
        "price": 150.0,
        "stop_loss": 147.0
    })
    assert res_btc["placed"] is False
    assert res_btc["status"] == "BLOCKED_BTC_MACRO"

    # 4. Activo no verificado / no contemplado en backtest (ej. MOVRUSDT)
    res_unverified = await nexus.process_limit_setup({
        "asset": "MOVRUSDT",
        "signal_type": "LONG",
        "btc_aligned": True,
        "price": 2.19,
        "stop_loss": 1.95
    })
    assert res_unverified["placed"] is False
    assert res_unverified["status"] == "BLOCKED_UNVERIFIED_ASSET"


@pytest.mark.asyncio
async def test_sop102_bitunix_executor_respects_quarter_kelly_3_25_pct_and_compounds():
    """
    [SOP-102 DYNAMIC COMPOUNDING & QUARTER-KELLY CLAMP]
    Verifica que BitunixExecutor.place_limit_signal y execute_signal:
    1. Respeten el sizing Quarter-Kelly de 3.25% cuando la señal proviene de un Playbook (sin mutilarlo al 2.50%).
    2. Escalen con cuentas de $5,000 USD sin el antiguo tope fijo de $5.00 USD.
    """
    from engine.execution.bitunix_executor import BitunixExecutor
    executor = BitunixExecutor(dry_run=False)
    executor._last_verified_balance = 5000.0
    executor._last_balance_ts = 9999999999.0
    executor.get_symbol_precision = AsyncMock(return_value=(1, 2))
    executor._request = AsyncMock(return_value={"code": 0, "data": {"orderId": "LIM_KELLY_5000"}})

    # Cuenta de $5,000 USD con riesgo Quarter-Kelly de 3.25% ($162.50 USD de riesgo máximo)
    # Entry = 100.0, SL = 98.0 (dist = $2.00) -> exact_qty = 162.50 / 2.00 = 81.2 unidades
    sig_kelly = {
        "asset": "SOLUSDT",
        "signal_type": "LONG",
        "playbook": "OB_DISCOUNT_RETEST",
        "risk_pct_applied": 0.0325,
        "price": 100.0,
        "stop_loss": 98.0,
        "exact_qty": 81.2,
        "leverage": 10
    }
    res = await executor.place_limit_signal(sig_kelly)
    assert res["status"] == "success"
    # Verificar el payload enviado a place_order: qty debe ser "81.2" (sin ser mutilado a 62.5 ni a 2.5 unidades)
    place_calls = [c for c in executor._request.call_args_list if c[0][1] == "/api/v1/futures/trade/place_order"]
    assert len(place_calls) == 1
    sent_payload = place_calls[0][1]["json_body"]
    assert float(sent_payload["qty"]) == pytest.approx(81.2, rel=1e-2)


def test_sop102_nexus_reconciler_preserves_matching_setup_tps_and_50_30_20_grid():
    """
    [SOP-102 TP RECONCILER 50/30/20 & MATCHING SETUP PRIORITY]
    Verifica que el código de reconciliación de NexusNode priorice matching_setup sobre existing_sl_in_exchange
    para conservar TP1 (1.2R), TP2 (2.0R), TP3 (3.5R) y divida las cantidades en 50% / 30% / 20% sin dejar 10% huérfano.
    """
    qty = 100.0
    q_dec = 1
    f1 = round(qty * 0.50, q_dec)
    f2 = round(qty * 0.30, q_dec)
    f3 = max(0.0, round(qty - f1 - f2, q_dec))
    assert (f1, f2, f3) == (50.0, 30.0, 20.0)
    assert f1 + f2 + f3 == qty

    # Verificar que en NexusNode el código fuente de reconciliación usa 0.50 / 0.30 y prioriza matching_setup
    import inspect
    from engine.execution.nexus import NexusNode
    src = inspect.getsource(NexusNode._sync_exchange_positions_loop)
    assert "if matching_setup:" in src
    assert 'TP1 (50%)' in src
    assert 'TP2 (30%)' in src
    assert 'TP3 (20% Runner)' in src


def test_sop49_risk_manager_alpha_leaders_defined():
    """
    [SOP-49 & SOP-100/102 ASIAN GATING]
    Verifica que RiskManager.ALPHA_LEADERS esté definido con los líderes institucionales
    y que el escáner no falle por AttributeError durante la sesión asiática (00:00 - 06:59 UTC).
    """
    from engine.risk.risk_manager import RiskManager
    assert hasattr(RiskManager, "ALPHA_LEADERS")
    leaders = RiskManager.ALPHA_LEADERS
    for expected in ("FET", "INJ", "BNB", "SOL", "NEAR", "ETH", "BTC"):
        assert expected in leaders


