"""
engine/tests/test_architectural_excellence_suite.py
=============================================================================
Suite de Certificación QA de Excelencia Arquitectónica Slingshot
Valida:
1. Resiliencia de Telemetría Anti-Flicker (Preservación de Posiciones).
2. Etiquetado Cuantitativo Triple-Barrier & Meta-Labeling ML.
3. Blindaje de Cartera, Límite de Clusters y Portfolio VaR.
4. Paridad Matemática del Shared Execution Kernel (Zero-Parity Drift).
=============================================================================
"""

import pytest
import asyncio
import time
import numpy as np
import pandas as pd
from unittest.mock import AsyncMock, patch

from engine.execution.bitunix_executor import BitunixExecutor
from engine.risk.cluster_risk_guard import ClusterRiskGuard, cluster_risk_guard
from engine.core.execution_kernel import ExecutionKernel, execution_kernel
from engine.ml.features import FeatureEngineer, TripleBarrierLabeler


class TestTelemetryAntiFlicker:
    """Certifica la eliminación del parpadeo y la preservación de estado en telemetría."""

    @pytest.mark.asyncio
    async def test_telemetry_anti_flicker_retention(self):
        executor = BitunixExecutor(dry_run=True)
        mock_positions = [
            {
                "symbol": "BNBUSDT",
                "positionId": "pos_bnb_1",
                "side": "BUY",
                "holdAmount": "0.1",
                "openPrice": "620.0",
                "markPrice": "625.0",
                "leverage": "20"
            }
        ]

        # 1. Primera consulta exitosa: debe actualizar el cache
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"code": 0, "data": mock_positions}
            pos1 = await executor.get_pending_positions()
            assert pos1 is not None
            assert len(pos1) == 1
            assert executor._last_verified_positions == mock_positions

        # 2. Segunda consulta: simular micro-latencia o error de red (retorna error del exchange)
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req_err:
            mock_req_err.return_value = {"code": -1, "msg": "Transient network timeout"}
            # Debe activar Anti-Flapping y retornar el último snapshot verificado
            pos2 = await executor.get_pending_positions()
            assert pos2 is not None
            assert len(pos2) == 1
            assert pos2[0]["symbol"] == "BNBUSDT"

        # 3. Tercera consulta: excepción dura de conexión
        with patch.object(executor, "_request", side_effect=Exception("Connection reset by peer")):
            pos3 = await executor.get_pending_positions()
            assert pos3 is not None
            assert len(pos3) == 1
            assert pos3[0]["symbol"] == "BNBUSDT"


class TestTripleBarrierML:
    """Certifica la precisión del etiquetado Triple Barrier de López de Prado."""

    def test_triple_barrier_labeling_logic(self):
        # Crear 30 velas sintéticas con ATR controlado = 2.0
        n = 30
        timestamps = pd.date_range("2026-01-01", periods=n, freq="15min")
        
        # Caso LONG WIN: precio en 100, sube a 106 (+3 * ATR = +6.0) sin tocar 98 (-1 * ATR)
        prices_win = [100.0] + [100.5, 101.2, 103.0, 105.0, 106.0] + [105.0] * 24
        df_win = pd.DataFrame({
            "timestamp": timestamps,
            "open": prices_win,
            "high": [p + 0.5 for p in prices_win],
            "low": [p - 0.5 for p in prices_win],
            "close": prices_win,
            "atr": [2.0] * n
        })

        labeler = TripleBarrierLabeler(pt_mult=2.0, sl_mult=1.0, max_holding_bars=10)
        labels_win = labeler.compute_barriers(df_win, direction="LONG")
        assert labels_win.iloc[0] == 1, "Debe etiquetar como 1 (WIN) al tocar TP (+2.0 ATR) primero"

        # Caso LONG LOSS: precio en 100, cae a 97 (-1.5 * ATR) antes de subir
        prices_loss = [100.0] + [99.5, 98.5, 97.0, 96.5] + [98.0] * 25
        df_loss = pd.DataFrame({
            "timestamp": timestamps,
            "open": prices_loss,
            "high": [p + 0.5 for p in prices_loss],
            "low": [p - 0.5 for p in prices_loss],
            "close": prices_loss,
            "atr": [2.0] * n
        })

        labels_loss = labeler.compute_barriers(df_loss, direction="LONG")
        assert labels_loss.iloc[0] == 0, "Debe etiquetar como 0 (LOSS) al tocar SL (-1.0 ATR) primero"


class TestPortfolioVarAndClusterRisk:
    """Certifica el blindaje de cartera por correlación cruzada."""

    def test_portfolio_var_cluster_rejection(self):
        guard = ClusterRiskGuard(correlation_threshold=0.75, max_per_cluster=2)

        active_positions = {
            "SOLUSDT": {
                "qty": 1.0,
                "signal": {"asset": "SOLUSDT", "type": "LONG", "price": 150.0, "stop_loss": 145.0}
            },
            "INJUSDT": {
                "qty": 10.0,
                "signal": {"asset": "INJUSDT", "type": "LONG", "price": 20.0, "stop_loss": 18.5}
            }
        }

        # Con 2 LONGs en Crypto High-Beta con riesgo activo, un 3er LONG en NEARUSDT debe ser rechazado
        can_open, reason = guard.can_open_position(
            new_asset="NEARUSDT",
            new_direction="LONG",
            confluence_score=75.0,
            active_positions=active_positions
        )
        assert can_open is False, "Debe bloquear el 3er LONG en activos correlacionados"
        assert "Límite de cluster alcanzado" in reason

        # Pero si la confluencia es élite (>= 88%), se aprueba con bypass excepcional
        can_open_elite, _ = guard.can_open_position(
            new_asset="NEARUSDT",
            new_direction="LONG",
            confluence_score=89.0,
            active_positions=active_positions
        )
        assert can_open_elite is True, "Confluencia élite (>=88%) debe autorizar el trade"

    def test_portfolio_var_calculation(self):
        guard = ClusterRiskGuard()
        active_positions = {
            "BTCUSDT": {
                "qty": 0.1,
                "signal": {"asset": "BTCUSDT", "type": "LONG", "price": 60000.0, "stop_loss": 59000.0} # $100 risk
            },
            "ETHUSDT": {
                "qty": 1.0,
                "signal": {"asset": "ETHUSDT", "type": "LONG", "price": 3000.0, "stop_loss": 2900.0}   # $100 risk
            }
        }
        var_res = guard.calculate_portfolio_var(active_positions, account_balance=10000.0)
        assert "portfolio_var_usd" in var_res
        assert var_res["portfolio_var_usd"] > 0
        assert var_res["status"] == "SAFE"


class TestSharedExecutionKernel:
    """Certifica la paridad matemática idéntica del Shared Execution Kernel."""

    def test_shared_execution_kernel_parity(self):
        # 1. Bracket Levels Long
        levels_long = execution_kernel.calculate_bracket_levels(
            direction="LONG",
            entry_price=100.0,
            stop_loss=95.0,
            rr_tp1=1.2,
            rr_tp2=2.0,
            rr_tp3=3.5
        )
        assert levels_long["sl_distance"] == 5.0
        assert levels_long["tp1"] == 106.0
        assert levels_long["tp2"] == 110.0
        assert levels_long["tp3"] == 117.5
        assert levels_long["be_price"] == 105.0

        # 2. Bracket Levels Short
        levels_short = execution_kernel.calculate_bracket_levels(
            direction="SHORT",
            entry_price=100.0,
            stop_loss=105.0,
            rr_tp1=1.2,
            rr_tp2=2.0,
            rr_tp3=3.5
        )
        assert levels_short["sl_distance"] == 5.0
        assert levels_short["tp1"] == 94.0
        assert levels_short["tp2"] == 90.0
        assert levels_short["tp3"] == 82.5
        assert levels_short["be_price"] == 95.0

        # 3. SOP-25 Early Invalidation
        is_inv_long, exit_p = execution_kernel.evaluate_structural_invalidation_sop25(
            direction="LONG",
            entry_price=100.0,
            stop_loss=90.0,
            current_low=93.4,
            current_high=100.2,
            threshold_r=0.65
        )
        # Cutoff es 100 - (10 * 0.65) = 93.5. Como current_low fue 93.4, debe invalidar a 93.5
        assert is_inv_long is True
        assert exit_p == 93.5
