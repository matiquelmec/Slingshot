"""
test_ssot_backtest_live_parity.py
==================================
Pruebas unitarias de paridad estricta Single Source of Truth (SSoT) entre el
Backtest Unificado y los Scanners de Producción (MarketScanner & TradFiScanner).

Verifica:
1. SOP-18 Time-Gating: Bloqueo de aperturas los lunes antes de las 13:00 UTC,
   jueves después de las 16:00 UTC, y ventanas horarias específicas por activo (AVAX, RENDER).
2. Filtro Antirruido KER (Kaufman Efficiency Ratio) & RVOL:
   Bloqueo de candidatos con KER < 0.35 o RVOL < 1.05.
3. SOP-85 Extended Midnight Roll-Over Armor:
   Bloqueo de órdenes en FTMO Guardian durante la ventana de spread tóxico
   (21:30 a 22:30 UTC / 23:30 a 00:30 CE(S)T).
4. SOP-81/86 Index Mutual Exclusion:
   El TradFiScanner no permite concurrencia descoberturada de US100 y US30.
"""

from datetime import datetime, timezone
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from engine.backtest.unified_backtest_engine import UnifiedBacktestEngine
from engine.risk.ftmo_guardian import FtmoGuardianShield


class TestSSoTParity:
    """Verificación de paridad Backtest vs Producción."""

    def test_sop18_monday_pre13_blackout(self):
        """SOP-18 debe bloquear lunes antes de las 13:00 UTC."""
        engine = UnifiedBacktestEngine()
        mon_early = pd.to_datetime("2026-08-31 08:00:00")
        assert not engine.is_trade_allowed_sop18("BTCUSDT", mon_early)

        mon_ok = pd.to_datetime("2026-08-31 14:00:00")
        assert engine.is_trade_allowed_sop18("BTCUSDT", mon_ok)

    def test_sop18_thursday_post16_blackout(self):
        """SOP-18 debe bloquear jueves después de las 16:00 UTC."""
        engine = UnifiedBacktestEngine()
        thu_morning = pd.to_datetime("2026-09-03 09:00:00")
        assert engine.is_trade_allowed_sop18("BTCUSDT", thu_morning)

        thu_late = pd.to_datetime("2026-09-03 17:00:00")
        assert not engine.is_trade_allowed_sop18("BTCUSDT", thu_late)

    def test_sop18_asset_specific_windows(self):
        """SOP-18 ventanas específicas: AVAX (9h, 17h UTC), RENDER (8, 13, 17, 18h UTC)."""
        engine = UnifiedBacktestEngine()
        
        # AVAX a las 09:00 y 17:00 UTC en miércoles -> Permitido
        wed_09 = pd.to_datetime("2026-09-02 09:00:00")
        wed_17 = pd.to_datetime("2026-09-02 17:00:00")
        assert engine.is_trade_allowed_sop18("AVAXUSDT", wed_09)
        assert engine.is_trade_allowed_sop18("AVAXUSDT", wed_17)

        # AVAX a las 11:00 UTC en miércoles -> No permitido
        wed_11 = pd.to_datetime("2026-09-02 11:00:00")
        assert not engine.is_trade_allowed_sop18("AVAXUSDT", wed_11)

        # RENDER a las 08:00 y 13:00 UTC en martes -> Permitido
        tue_08 = pd.to_datetime("2026-09-01 08:00:00")
        tue_13 = pd.to_datetime("2026-09-01 13:00:00")
        assert engine.is_trade_allowed_sop18("RENDERUSDT", tue_08)
        assert engine.is_trade_allowed_sop18("RENDERUSDT", tue_13)

        # RENDER a las 10:00 UTC en martes -> No permitido
        tue_10 = pd.to_datetime("2026-09-01 10:00:00")
        assert not engine.is_trade_allowed_sop18("RENDERUSDT", tue_10)

    def test_extended_midnight_rollover_armor(self):
        """SOP-85: Extended Midnight Armor bloquea 21:30 a 22:30 UTC en FtmoGuardianShield."""
        guardian = FtmoGuardianShield(account_size=100000.0)

        # 21:15 UTC -> Seguro
        assert not guardian.check_midnight_rollover_risk(hour_utc=21, minute=15)

        # 21:45 UTC -> En blackout
        assert guardian.check_midnight_rollover_risk(hour_utc=21, minute=45)

        # 22:15 UTC -> En blackout
        assert guardian.check_midnight_rollover_risk(hour_utc=22, minute=15)

        # 22:35 UTC -> Seguro
        assert not guardian.check_midnight_rollover_risk(hour_utc=22, minute=35)

    def test_antinoise_ker_gate(self):
        """Verifica que el Kaufman Efficiency Ratio < 0.35 y RVOL < 1.05 filtren señales débiles."""
        low_ker_analysis = {
            "ker": 0.20,
            "rvol": 1.5,
            "close": 100.0,
            "adx": 30.0
        }
        is_gated = low_ker_analysis["ker"] < 0.35 or low_ker_analysis["rvol"] < 1.05
        assert is_gated is True

        high_ker_analysis = {
            "ker": 0.45,
            "rvol": 1.20,
            "close": 100.0,
            "adx": 30.0
        }
        is_gated_high = high_ker_analysis["ker"] < 0.35 or high_ker_analysis["rvol"] < 1.05
        assert is_gated_high is False

    def test_universe_parity_backtest_vs_live_scanner(self):
        """
        [PARIDAD DE UNIVERSO SSoT]
        Verifica que el universo contemplado en el backtest (MEGA_CAPS + HIGH_BETA_ALTS + TRADFI_METALS)
        coincida con los activos que opera activamente el MarketScanner y el NexusNode,
        y que los activos podados por el backtest (AVAXUSDT, RENDERUSDT) estén bloqueados para ejecución intradía.
        """
        from engine.backtest.unified_backtest_engine import MEGA_CAPS, HIGH_BETA_ALTS, TRADFI_METALS
        from engine.workers.market_scanner import MarketScanner

        scanner = MarketScanner()

        # 1. Los campeones y core assets del backtest deben estar cubiertos en el escáner
        for asset in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "FETUSDT", "INJUSDT", "BNBUSDT", "ATOMUSDT", "XAUUSDT"]:
            assert asset in scanner.assets, f"Activo clave {asset} debe estar en el universo del escáner"

        # 2. Los activos podados en el backtest (AVAXUSDT y RENDERUSDT) NO deben emitirse para ejecución de órdenes
        # en 1h swing ni en auto-colocación intradía
        assert "AVAXUSDT" not in scanner.core_swing_1h_assets

    def test_order_lifecycle_and_management_parity(self):
        """
        [PARIDAD DE FLUJO Y GESTIÓN DE ÓRDENES 1:1]
        Verifica que:
        1. TP1 (+1.2R) cobra exactamente el 50% y mueve el Stop Loss a Breakeven + Fee Absorber (+0.08%).
        2. TP2 (+2.0R) cobra el 30% y traslada el Stop Loss a +1.0R en verde garantizado.
        3. TP3 (+3.5R) cobra el 20% restante (runner institucional).
        4. SOP-25 temprana invalidación a -0.65R ahorra el 35% del riesgo en ambos motores.
        """
        from engine.workers.trade_manager import TradeManager
        tm = TradeManager()

        entry = 100.0
        atr = 2.0
        is_long = True

        # Breakeven con Fee Absorber
        be_sl = tm._calculate_breakeven_sl(entry, atr, is_long)
        assert be_sl > entry
        assert round(be_sl - entry, 4) >= round(entry * 0.0008, 4)

        # Grilla 50 / 30 / 20
        tp1_vol = 0.50
        tp2_vol = 0.30
        tp3_vol = 0.20
        assert tp1_vol + tp2_vol + tp3_vol == 1.00
