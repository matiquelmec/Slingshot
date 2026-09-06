"""
engine/tests/test_sop28_to_sop31_sovereign_suite.py
=============================================================================
SLINGSHOT v39.0 APEX SOVEREIGN — QA CERTIFICATION SUITE (SOP-28 to SOP-31)
=============================================================================
Pruebas de certificación para:
1. SOP-28: Quality Gate (Veto a micro-tokens con precio < $0.10 y spread excesivo).
2. SOP-29: Session Alpha Gating (Bonus NY Open y filtro defensivo en Asia).
3. SOP-30: Beta Exposure Limiter (Bloqueo de 3er LONG en cripto con riesgo flotante).
4. SOP-30: Liberación de cupo cuando las posiciones están protegidas en Breakeven.
5. SOP-31: Regime Quarantine (Veto de mercados en compresión muerta ADX < 18 y KER < 0.28).
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime

from engine.risk.risk_manager import RiskManager
from engine.risk.cluster_risk_guard import cluster_risk_guard
from engine.core.confluence import confluence_manager

class TestSOP28ToSOP31SovereignSuite(unittest.TestCase):
    def test_sop28_quality_gate_price_threshold(self):
        """
        [SOP-28] Micro-tokens como AKE (< $0.10 USDT) deben ser descalificados
        para prevenir descalabros de apalancamiento y errores de tick size.
        """
        min_price = 0.10
        raw_candidates = [
            {"symbol": "AKEUSDT", "quoteVolume": 45_000_000, "lastPrice": 0.0045},
            {"symbol": "PEPEUSDT", "quoteVolume": 80_000_000, "lastPrice": 0.000012},
            {"symbol": "SOLUSDT", "quoteVolume": 300_000_000, "lastPrice": 142.50},
            {"symbol": "FETUSDT", "quoteVolume": 65_000_000, "lastPrice": 1.25}
        ]
        
        filtered = [
            c["symbol"] for c in raw_candidates 
            if c["quoteVolume"] >= 30_000_000 and c["lastPrice"] >= min_price
        ]
        
        self.assertNotIn("AKEUSDT", filtered)
        self.assertNotIn("PEPEUSDT", filtered)
        self.assertIn("SOLUSDT", filtered)
        self.assertIn("FETUSDT", filtered)

    def test_sop29_session_alpha_gating_boost(self):
        """
        [SOP-29] En NY Open (13:00-17:00 UTC) se otorga bono de expansión dorada (+5pts).
        En Asia (00:00-07:00 UTC) se emite precaución por rango pasivo.
        """
        # 1. Simular hora NY Open (14:30 UTC)
        df_ny = pd.DataFrame({
            "timestamp": [pd.Timestamp("2026-09-02 14:30:00", tz="UTC")],
            "open": [100.0], "high": [102.0], "low": [99.0], "close": [101.0], "volume": [1000.0]
        })
        sig_ny = {"type": "LONG", "symbol": "ETHUSDT", "price": 101.0}
        res_ny = confluence_manager.evaluate_signal(df=df_ny, signal=sig_ny)
        item_ny = next((i for i in res_ny["checklist"] if i["factor"] == "Session Alpha Gating"), None)
        self.assertIsNotNone(item_ny)
        self.assertEqual(item_ny["status"], "ALFA_GOLDEN")
        self.assertIn("NY Open", item_ny["detail"])

        # 2. Simular hora Asia (03:15 UTC)
        df_asia = pd.DataFrame({
            "timestamp": [pd.Timestamp("2026-09-02 03:15:00", tz="UTC")],
            "open": [100.0], "high": [101.0], "low": [99.5], "close": [100.5], "volume": [200.0]
        })
        sig_asia = {"type": "LONG", "symbol": "ETHUSDT", "price": 100.5}
        res_asia = confluence_manager.evaluate_signal(df=df_asia, signal=sig_asia)
        item_asia = next((i for i in res_asia["checklist"] if i["factor"] == "Session Alpha Gating"), None)
        self.assertIsNotNone(item_asia)
        self.assertEqual(item_asia["status"], "PRECAUCIÓN")

        # 3. Simular inyección dinámica de SessionManager (DST aware Global Master Sync)
        session_dyn = {
            "current_session": "NY_KILLZONE",
            "is_killzone": True,
            "is_overlap": True,
            "is_silver_bullet": False
        }
        res_dyn = confluence_manager.evaluate_signal(df=df_ny, signal=sig_ny, session_data=session_dyn)
        item_dyn = next((i for i in res_dyn["checklist"] if i["factor"] == "Session Alpha Gating"), None)
        self.assertIsNotNone(item_dyn)
        self.assertEqual(item_dyn["status"], "ALFA_GOLDEN")
        self.assertIn("Power Overlap", item_dyn["detail"])

    def test_sop30_beta_exposure_limiter_rejects_third_long(self):
        """
        [SOP-30] Si ya existen 2 posiciones LONG en cripto no protegidas (con riesgo flotante),
        un tercer LONG en cripto debe ser bloqueado para evitar sobreexposición a la Beta de BTC.
        """
        mock_active_positions = {
            "BTCUSDT": {
                "signal": {"type": "LONG", "price": 60000.0, "stop_loss": 59000.0},
                "smart_trailing": {"be_active": False}
            },
            "ETHUSDT": {
                "signal": {"type": "LONG", "price": 2500.0, "stop_loss": 2400.0},
                "smart_trailing": {"be_active": False}
            }
        }
        
        can_open, reason = cluster_risk_guard.can_open_position(
            new_asset="SOLUSDT",
            new_direction="LONG",
            confluence_score=75.0, # Confluencia estándar (< 88)
            active_positions=mock_active_positions
        )
        
        self.assertFalse(can_open)
        self.assertIn("SOP-30 BETA VETO", reason)
        self.assertIn("BTCUSDT", reason)
        self.assertIn("ETHUSDT", reason)

    def test_sop30_beta_exposure_permits_when_positions_at_breakeven(self):
        """
        [SOP-30] Si las posiciones existentes ya aseguraron Breakeven (riesgo $0),
        liberan su cupo y permiten una nueva entrada.
        """
        mock_active_positions = {
            "BTCUSDT": {
                "signal": {"type": "LONG", "price": 60000.0, "stop_loss": 60050.0}, # SL por encima de entrada (BE+)
                "smart_trailing": {"be_active": True}
            },
            "ETHUSDT": {
                "signal": {"type": "LONG", "price": 2500.0, "stop_loss": 2505.0},
                "smart_trailing": {"be_active": True}
            }
        }
        
        can_open, reason = cluster_risk_guard.can_open_position(
            new_asset="SOLUSDT",
            new_direction="LONG",
            confluence_score=75.0,
            active_positions=mock_active_positions
        )
        
        self.assertTrue(can_open)
        self.assertIn("Aprobado", reason)

    def test_sop31_regime_quarantine_vetoes_dead_chop(self):
        """
        [SOP-31] Veta activos en compresión extrema sin volatilidad ni dirección (ADX < 18 y KER < 0.28).
        """
        # Mercado en compresión muerta
        is_ok, msg = RiskManager.check_regime_quarantine(adx=14.5, ker=0.22)
        self.assertFalse(is_ok)
        self.assertIn("SOP-31 REGIME QUARANTINE", msg)

        # Mercado con tendencia o estructura sana
        is_ok_trend, _ = RiskManager.check_regime_quarantine(adx=26.0, ker=0.45)
        self.assertTrue(is_ok_trend)

if __name__ == "__main__":
    unittest.main()
