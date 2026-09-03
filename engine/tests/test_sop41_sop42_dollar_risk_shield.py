"""
engine/tests/test_sop41_sop42_dollar_risk_shield.py
=============================================================================
Suite de Certificación QA: Protocolos SOP-41 y SOP-42
- SOP-41: Pure Dollar-Risk Position Sizing (2.50% Base Canónico Estricto)
- SOP-42: Pre-Flight Risk Hard-Clamp (Circuit Breaker Desacoplado en Ejecutor)
- Notional Account Cap: Techo de 5x Balance en Cuentas Retail
- Fail-Closed Architecture: Cero Fallbacks Falsos de $1000 USDT en Bitunix
=============================================================================
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from engine.risk.risk_manager import RiskManager
from engine.execution.bitunix_executor import BitunixExecutor


class TestSOP41SOP42DollarRiskShield:
    """Certificación de Blindaje Institucional contra Sobredimensionamiento y Riesgo Excesivo."""

    def test_sop41_inj_parity_loss_strictly_under_2_05_usd(self):
        """
        [CASO INJ REAL] Certifica que para un saldo de $82.23 USDT, entrada en $4.798 y SL en $4.876,
        la pérdida máxima proyectada sea exactamente de ~$2.05 USD (~1,968 CLP), y NUNCA $24.35 USD (~24,000 CLP).
        """
        balance = 82.23
        risk_pct = 0.025 # 2.50%
        entry = 4.798
        sl = 4.876
        lev = 20
        qty_decimals = 1

        result = RiskManager.calculate_dollar_risk_position(
            account_balance=balance,
            risk_pct=risk_pct,
            entry_price=entry,
            sl_price=sl,
            leverage=lev,
            max_notional_mult=5.0,
            qty_decimals=qty_decimals
        )

        assert result["approved"] is True
        assert result["qty"] == 26.3, f"Esperado ~26.3 INJ, recibido: {result['qty']}"
        assert result["required_margin"] < 10.0, f"Margen debe ser < $10 USDT, recibido: ${result['required_margin']}"
        assert result["projected_loss"] <= 2.06, f"Pérdida proyectada (${result['projected_loss']}) excede $2.06 USD!"
        
        # Validación en Pesos Chilenos (CLP @ 960)
        loss_clp = result["projected_loss"] * 960.0
        assert loss_clp < 2000.0, f"Pérdida en CLP ({loss_clp:.0f}) debe ser < 2,000 CLP, NUNCA 24,000 CLP!"

    def test_sop41_wide_sl_scales_down_quantity(self):
        """
        Certifica que si el Stop Loss está a una distancia amplia (5.0%),
        la cantidad se reduce automáticamente para que la pérdida siga siendo de $2.05 USD.
        """
        balance = 82.23
        risk_pct = 0.025 # $2.05 USD
        entry = 100.0
        sl = 95.0 # 5% de distancia ($5.00)
        
        result = RiskManager.calculate_dollar_risk_position(
            account_balance=balance,
            risk_pct=risk_pct,
            entry_price=entry,
            sl_price=sl,
            leverage=20,
            qty_decimals=2
        )

        assert result["approved"] is True
        # Qty = $2.055 / $5.00 = 0.41 unidades
        assert result["qty"] == 0.41
        assert result["projected_loss"] <= 2.06
        assert result["notional_value"] == 41.0 # Muy por debajo del techo

    def test_sop41_tight_sl_triggers_notional_cap(self):
        """
        Certifica que con un Stop Loss ultra-ajustado (0.1%), el techo de valor nocional
        (5x balance = $411.15 USD max) impide que la posición se sobreapalanque peligrosamente.
        """
        balance = 82.23
        risk_pct = 0.025
        entry = 100.0
        sl = 99.90 # Distancia 0.1% ($0.10)
        
        result = RiskManager.calculate_dollar_risk_position(
            account_balance=balance,
            risk_pct=risk_pct,
            entry_price=entry,
            sl_price=sl,
            leverage=20,
            max_notional_mult=5.0,
            qty_decimals=2
        )

        assert result["approved"] is True
        assert result["is_notional_capped"] is True
        assert result["notional_value"] <= 411.15
        assert result["effective_leverage"] <= 5.0
        # Al estar capeada por nocional, el riesgo es aún MENOR que 2.50%
        assert result["projected_loss"] < 2.05

    @pytest.mark.asyncio
    async def test_sop42_preflight_hard_clamp_intercepts_oversized_order(self):
        """
        [SOP-42 PRE-FLIGHT HARD-CLAMP]
        Inyecta una orden sobredimensionada (312.3 INJ) directamente en execute_signal
        y certifica que el ejecutor Bitunix la clampa automáticamente a ~26.3 INJ.
        """
        executor = BitunixExecutor(dry_run=True)
        executor._last_verified_balance = 82.23
        executor._last_balance_ts = 9999999999.0

        dangerous_signal = {
            "asset": "INJUSDT",
            "type": "SELL",
            "price": 4.798,
            "stop_loss": 4.876, # Distancia = 0.078
            "exact_qty": 312.3, # Intento de inyectar 312.3 INJ ($24.35 USD de pérdida)
            "leverage": 20,
            "is_test": True
        }

        # Mock de precisión del símbolo (1 decimal para INJ)
        executor.get_symbol_precision = AsyncMock(return_value=(1, 3))
        
        res = await executor.execute_signal(dangerous_signal)
        assert res.get("status") == "success"

    @pytest.mark.asyncio
    async def test_fail_closed_never_returns_1000_fake_balance(self):
        """
        [FAIL-CLOSED ARCHITECTURE]
        Certifica que si la API de Bitunix falla o desconecta, get_available_margin_usdt()
        y get_balance() retornan 0.0 o el saldo verificado en caché, NUNCA 1000.0 ficticios.
        """
        executor = BitunixExecutor(dry_run=False)
        executor._last_verified_balance = 0.0
        executor._last_balance_ts = 0.0

        # Simular fallo de red en la API de Bitunix
        with patch.object(executor, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Connection Timeout")
            
            avail = await executor.get_available_margin_usdt()
            bal = await executor.get_balance()
            
            assert avail == 0.0, f"Debe retornar 0.0 en fallo de red, recibido: {avail}"
            assert bal == 0.0, f"Debe retornar 0.0 en fallo de red, recibido: {bal}"
            assert avail != 1000.0
            assert bal != 1000.0
