"""
engine/tests/test_mega_kelly_and_runner_ratchet.py
==================================================
SUITE INSTITUCIONAL DE PRUEBAS:
1. SOP-103: Asymmetric Mega-Kelly Scaling en la Trinidad (BNB, SOL, FET).
2. SOP-104: Trailing Ratchet Chandelier en Runners Post-TP3.
3. AssetIncubator: Rotación Cuantitativa y Sharpe Rodante.
"""

import pytest
import pandas as pd
from engine.risk.risk_manager import RiskManager
from engine.workers.trade_manager import TradeManager
from engine.workers.asset_incubator import AssetIncubator


class TestMegaKellyAndRunnerRatchetSuite:

    # ── 1. SOP-103 MEGA-KELLY TESTS ──────────────────────────────────────────

    def test_mega_kelly_trinity_base_acceleration(self):
        """Certifica que apply_mega_kelly=True otorgue 1.35x base en la Trinidad (BNB, SOL, FET)."""
        # BNBUSDT base tier: 1.25x
        # Con Mega-Kelly: 1.25 * 1.35 = 1.6875 -> 1.69
        sizing_bnb = RiskManager.calculate_alpha_tier_sizing(
            "BNBUSDT",
            confluence_score=75.0,
            hour_utc=None,
            apply_mega_kelly=True
        )
        assert sizing_bnb == pytest.approx(1.69, abs=0.02)

        # Sin Mega-Kelly pero con apply_trinity_boost: 1.25 * 1.20 = 1.50
        sizing_bnb_old = RiskManager.calculate_alpha_tier_sizing(
            "BNBUSDT",
            confluence_score=75.0,
            hour_utc=None,
            apply_trinity_boost=True,
            apply_mega_kelly=False
        )
        assert sizing_bnb_old == pytest.approx(1.50, abs=0.01)

    def test_mega_kelly_trinity_elite_killzone_super_boost(self):
        """Certifica que confluencia >= 85 en Killzone horaria (14 UTC) otorgue 1.50x en la Trinidad."""
        # FETUSDT base tier: 1.40x
        # Confluencia >= 82: * 1.15
        # NY Open (14 UTC): * 1.10
        # Mega-Kelly Elite (conf >= 85, hour 14): * 1.50
        # Multiplicador total: 1.40 * 1.15 * 1.10 * 1.50 = 2.6565 -> Clampeado al max_cap institucional de 2.35
        sizing_fet = RiskManager.calculate_alpha_tier_sizing(
            "FETUSDT",
            confluence_score=88.0,
            hour_utc=14,
            apply_mega_kelly=True
        )
        assert sizing_fet == 2.35  # Cap institucional para Mega-Kelly

    def test_mega_kelly_non_trinity_isolation(self):
        """Certifica que activos fuera de la Trinidad (ej. BTC, ETH) NO reciban el boost Mega-Kelly."""
        sizing_btc_mega = RiskManager.calculate_alpha_tier_sizing(
            "BTCUSDT",
            confluence_score=75.0,
            apply_mega_kelly=True
        )
        sizing_btc_normal = RiskManager.calculate_alpha_tier_sizing(
            "BTCUSDT",
            confluence_score=75.0,
            apply_mega_kelly=False
        )
        assert sizing_btc_mega == sizing_btc_normal

    def test_mega_kelly_quarter_kelly_expansion_to_3_50_pct(self):
        """Certifica que calculate_quarter_kelly_risk expanda el hard cap de 3.25% a 3.50% solo con Mega-Kelly."""
        # Setup élite que genera multiplicador máximo
        risk_mega = RiskManager.calculate_quarter_kelly_risk(
            base_risk_pct=0.025,
            symbol="SOLUSDT",
            confluence_score=90.0,
            hour_utc=14,
            playbook="OB_DISCOUNT_RETEST",
            apply_meta_labeling=True,
            apply_mega_kelly=True
        )
        assert risk_mega == 0.0350  # Cap expandido

        risk_standard = RiskManager.calculate_quarter_kelly_risk(
            base_risk_pct=0.025,
            symbol="SOLUSDT",
            confluence_score=90.0,
            hour_utc=14,
            playbook="OB_DISCOUNT_RETEST",
            apply_meta_labeling=True,
            apply_mega_kelly=False
        )
        assert risk_standard == 0.0325  # Cap estándar histórico protegido

    # ── 2. SOP-104 TRAILING RATCHET TESTS ────────────────────────────────────

    def test_runner_ratchet_guarantees_tp2_floor_on_tp3_activation(self):
        """Certifica que al alcanzar TP3, el piso mínimo del SL en RUNNER_EXPANSION sea TP2."""
        tm = TradeManager.__new__(TradeManager)
        tm.ATR_BE_BUFFER = 0.30

        signal = {
            "symbol": "FETUSDT",
            "entry_price": 1.0000,
            "stop_loss": 0.9800,  # 1R = 0.0200
            "tp1": 1.0260,         # +1.3R
            "tp2": 1.0400,         # +2.0R
            "tp3": 1.0640,         # +3.2R
            "current_sl": 1.0400,
            "direction": "LONG"
        }

        # Precio apenas toca TP3 (1.0650)
        current_price = 1.0650
        atr_val = 0.0050

        runner_sl = tm._calculate_runner_ratchet_sl(
            signal=signal,
            current_price=current_price,
            is_long=True,
            atr_val=atr_val
        )

        assert runner_sl is not None
        # Debe ser al menos TP2 (1.0400) o Chandelier (1.0650 - 0.0075 = 1.0575)
        assert runner_sl >= signal["tp2"]
        assert runner_sl == pytest.approx(1.0575, abs=0.001)

    def test_runner_ratchet_escalates_at_4r_6r_and_8r(self):
        """Certifica que el ratchet bloquee pisos crecientes a +4R, +6R y +8R."""
        tm = TradeManager.__new__(TradeManager)
        tm.ATR_BE_BUFFER = 0.30

        signal = {
            "symbol": "SOLUSDT",
            "entry_price": 100.0,
            "stop_loss": 95.0,    # 1R = $5.00
            "tp1": 106.5,
            "tp2": 110.0,         # +2.0R
            "tp3": 116.0,         # +3.2R
            "current_sl": 110.0,
            "direction": "LONG"
        }

        # Caso 1: Precio alcanza +4.5R ($122.50) -> Piso debe ser al menos TP3 ($116.0)
        sl_4r = tm._calculate_runner_ratchet_sl(
            signal=signal,
            current_price=122.50,
            is_long=True,
            atr_val=2.0
        )
        assert sl_4r >= signal["tp3"]

        # Caso 2: Precio alcanza +6.5R ($132.50) -> Piso debe ser al menos entry + 4.5R ($122.50)
        sl_6r = tm._calculate_runner_ratchet_sl(
            signal=signal,
            current_price=132.50,
            is_long=True,
            atr_val=2.0
        )
        assert sl_6r >= (100.0 + 4.5 * 5.0)  # >= $122.50

        # Caso 3: Precio alcanza +9.0R ($145.00) -> Piso debe ser al menos entry + 6.5R ($132.50)
        sl_9r = tm._calculate_runner_ratchet_sl(
            signal=signal,
            current_price=145.00,
            is_long=True,
            atr_val=2.0
        )
        assert sl_9r >= (100.0 + 6.5 * 5.0)  # >= $132.50

    def test_runner_ratchet_short_direction_symmetry(self):
        """Certifica paridad simétrica estricta en posiciones SHORT bajo SOP-104."""
        tm = TradeManager.__new__(TradeManager)
        tm.ATR_BE_BUFFER = 0.30

        signal_short = {
            "symbol": "BNBUSDT",
            "entry_price": 600.0,
            "stop_loss": 610.0,   # 1R = $10.00
            "tp1": 587.0,
            "tp2": 580.0,         # +2.0R
            "tp3": 568.0,         # +3.2R
            "current_sl": 580.0,
            "direction": "SHORT"
        }

        # Precio cae a $530.00 (+7.0R a favor del SHORT)
        # Piso de 6R en short: entry - 4.5R = 600 - 45 = 555.0
        sl_short = tm._calculate_runner_ratchet_sl(
            signal=signal_short,
            current_price=530.0,
            is_long=False,
            atr_val=3.0
        )
        assert sl_short is not None
        assert sl_short <= 555.0  # El SL baja para asegurar ganancias
        assert sl_short > 530.0   # Pero permanece por encima del precio actual

    # ── 3. ASSET INCUBATOR TESTS ─────────────────────────────────────────────

    def test_asset_incubator_healthy_leader_classification(self):
        """Certifica que un activo con alta expectativa y Sharpe rodante sea calificado HEALTHY_LEADER."""
        incubator = AssetIncubator()
        mock_trades = [
            {"asset": "BNBUSDT", "pnl_r": 1.50},
            {"asset": "BNBUSDT", "pnl_r": -0.65},
            {"asset": "BNBUSDT", "pnl_r": 2.20},
            {"asset": "BNBUSDT", "pnl_r": 1.30},
            {"asset": "BNBUSDT", "pnl_r": -0.65},
            {"asset": "BNBUSDT", "pnl_r": 3.20},
            {"asset": "BNBUSDT", "pnl_r": 1.20},
        ] * 6  # 42 trades con claro sesgo ganador

        health = incubator.evaluate_asset_health("BNBUSDT", mock_trades)
        assert health["is_canonical"] is True
        assert health["status"] == "HEALTHY_LEADER"
        assert health["profit_factor"] > 2.0
        assert health["recommendation"] == "MAINTAIN_CAPITAL"

    def test_asset_incubator_pruned_asset_permanent_exclusion(self):
        """Certifica que AVAX o RENDER reciban veto permanente si son evaluados."""
        incubator = AssetIncubator()
        health_avax = incubator.evaluate_asset_health("AVAXUSDT", [{"asset": "AVAXUSDT", "pnl_r": 1.0}])
        assert health_avax["status"] == "PRUNED_VETOED"
        assert health_avax["recommendation"] == "PERMANENT_EXCLUSION"

    @pytest.mark.asyncio
    async def test_nexus_limit_order_applies_mega_kelly_when_enabled(self):
        """Certifica que NexusNode aplique Mega-Kelly (3.50% risk) cuando la señal lo activa explícitamente."""
        from unittest.mock import MagicMock, AsyncMock
        from engine.execution.nexus import NexusNode

        nexus = NexusNode(dry_run=True)
        acc = MagicMock()
        acc.account_id = "mega_acc"
        acc.label = "MegaAccount"
        acc.is_primary = True
        acc.risk_pct = 0.025
        acc.max_notional_mult = 5.0

        ex = MagicMock()
        ex.dry_run = True
        ex.account_label = "MegaAccount"
        ex.get_net_available_margin_usdt = AsyncMock(return_value=1000.0)
        ex.get_available_margin_usdt = AsyncMock(return_value=1000.0)
        ex.get_account_balance = AsyncMock(return_value=1000.0)
        ex.get_pending_positions = AsyncMock(return_value=[])
        ex.get_pending_orders = AsyncMock(return_value=[])
        ex.get_symbol_precision = AsyncMock(return_value=(2, 2))
        ex.place_limit_signal = AsyncMock(return_value={"status": "success", "order_id": "LIM_MEGA_1"})

        # Señal en SOLUSDT (Trinidad) con apply_mega_kelly=True
        sig_mega = {
            "asset": "SOLUSDT",
            "symbol": "SOLUSDT",
            "direction": "LONG",
            "playbook": "OB_DISCOUNT_RETEST",
            "confluence_score": 88.0,
            "price": 100.0,
            "stop_loss": 98.0,  # dist = 2.0
            "apply_mega_kelly": True
        }
        res = await nexus._place_limit_for_account(ex, acc, sig_mega, safe_lev=10, entry_p=100.0, sl_p=98.0)
        assert res["status"] == "success"
        # Riesgo de 3.50% en balance $1000 = $35.00 USDT. Con dist=2.0 -> exact_qty = 17.50
        assert sig_mega["exact_qty"] == pytest.approx(17.50, rel=0.05)
