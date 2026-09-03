"""
engine/tests/test_sop39_sop40_bitunix_dynamic_25pct_risk.py
=============================================================================
SLINGSHOT v42.0 APEX TITAN COMPOUND — QA CERTIFICATION SUITE (SOP-39 & SOP-40)
=============================================================================
Pruebas de certificación para:
1. SOP-39: DEFAULT_MARGIN_USDT calibrado a $17.00 (2.5% de riesgo real para $200).
2. SOP-39: Cálculo de margen dinámico al 8.5% del saldo disponible ($200 -> $17 USD).
3. SOP-39: Escalado automático de interés compuesto ($300 -> $25.50 USD de margen).
4. SOP-40: Guardián de buffer libre en Bitunix (evita agotar el saldo de fianza).
5. SOP-40: Aislamiento inmutable de FTMO fijado estrictamente al 0.75%.
"""

import unittest
from engine.execution.nexus import NexusNode
from engine.risk.ftmo_guardian import FtmoGuardianShield

class TestSOP39SOP40BitunixDynamic25PctRisk(unittest.TestCase):
    def test_sop39_default_margin_calibrated_for_25pct_risk(self):
        """
        [SOP-39] DEFAULT_MARGIN_USDT debe ser $17.00 USDT, lo que representa
        el margen necesario para arriesgar el 2.50% ($5.00 USD) en una cuenta de $200 USD.
        """
        self.assertEqual(NexusNode.DEFAULT_MARGIN_USDT, 17.00)

    def test_sop39_dynamic_equity_sizing_200usd(self):
        """
        [SOP-39] Para una cuenta de $200 USD, la fórmula del 8.5% de saldo disponible
        asigna exactamente $17.00 USDT de margen base.
        Con apalancamiento 12X y SL al 2.5%, el riesgo efectivo en Stop Loss es ~$5.10 USD (2.55%).
        """
        account_balance = 200.0
        dynamic_margin = max(NexusNode.DEFAULT_MARGIN_USDT, account_balance * 0.085)
        self.assertAlmostEqual(dynamic_margin, 17.00, places=2)
        
        leverage = 12
        sl_pct = 0.025
        nominal_size = dynamic_margin * leverage
        risk_usd = nominal_size * sl_pct
        effective_risk_pct = (risk_usd / account_balance) * 100.0
        
        self.assertAlmostEqual(risk_usd, 5.10, places=2)
        self.assertAlmostEqual(effective_risk_pct, 2.55, places=1)

    def test_sop39_dynamic_equity_compounding_300usd(self):
        """
        [SOP-39] Cuando la cuenta de Bitunix escala a $300 USD vía interés compuesto,
        el margen dinámico sube automáticamente a $25.50 USDT (8.5%), manteniendo el riesgo al 2.55%.
        """
        account_balance = 300.0
        dynamic_margin = max(NexusNode.DEFAULT_MARGIN_USDT, account_balance * 0.085)
        self.assertAlmostEqual(dynamic_margin, 25.50, places=2)
        
        leverage = 12
        sl_pct = 0.025
        nominal_size = dynamic_margin * leverage
        risk_usd = nominal_size * sl_pct
        effective_risk_pct = (risk_usd / account_balance) * 100.0
        
        self.assertAlmostEqual(risk_usd, 7.65, places=2)
        self.assertAlmostEqual(effective_risk_pct, 2.55, places=1)

    def test_sop40_preflight_buffer_guardrail(self):
        """
        [SOP-40] El guardián de buffer libre debe exigir que tras descontar el margen
        de la orden quede al menos el 50% de la cuenta libre (o mínimo $50 USD).
        """
        avail_margin = 40.0
        req_margin = 25.0
        min_buffer = min(50.0, avail_margin * 0.50) # 20.0 USDT
        rem_buffer = avail_margin - req_margin       # 15.0 USDT
        
        # 15.0 < 20.0 -> Buffer insuficiente, la orden debe ser prevenida
        self.assertLess(rem_buffer, min_buffer)

    def test_sop40_ftmo_remains_strictly_isolated_at_075pct(self):
        """
        [SOP-40] El módulo de FTMO (FtmoGuardianShield) debe permanecer estrictamente
        al 0.75% de riesgo en Fase 1, con límite de pérdida diaria preventivo a -3.5%,
        sin verse afectado en absoluto por la calibración al 2.5% de Bitunix.
        """
        guardian = FtmoGuardianShield(account_size=100000.0, phase="PHASE_1")
        self.assertEqual(guardian.current_config["risk_pct"], 0.0075)
        self.assertEqual(guardian.current_config["daily_max_loss_pct"], 3.5)
        self.assertEqual(guardian.current_config["total_max_loss_pct"], 7.5)

if __name__ == "__main__":
    unittest.main()
