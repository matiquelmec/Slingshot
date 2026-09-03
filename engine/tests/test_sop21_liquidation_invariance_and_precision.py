"""
engine/tests/test_sop21_liquidation_invariance_and_precision.py
===============================================================
Pruebas Unitarias QA — Protocolo SOP-21:
1. Invarianza de Liquidación y Safe Leverage Calculation.
2. Pre-Flight Liquidation Clearance Guard.
3. Precisión dinámica de 6 decimales para tokens de microprecio (AKEUSDT).
4. Blindaje de colisión entre Stop Loss y Precio de Liquidación.
"""
import unittest
import asyncio
from engine.risk.risk_manager import RiskManager
from engine.execution.bitunix_executor import BitunixExecutor


class TestSOP21LiquidationInvarianceAndPrecision(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager()
        self.executor = BitunixExecutor(dry_run=True)

    def test_akeusdt_safe_leverage_prevents_20x_liquidation(self):
        """
        Caso Real Forense AKEUSDT:
        Entry = 0.015444, SL = 0.014900 (-3.52%).
        Con 20X, la liquidación ocurría exactamente en 0.014900 (misma distancia de 3.5%).
        SOP-21 debe reducir el apalancamiento a <= 14X (típicamente 12X o 10X).
        """
        entry_p = 0.015444
        sl_p = 0.014900
        safe_lev = RiskManager.calculate_safe_leverage(entry_p, sl_p, mmr=0.015, safety_factor=1.50)
        
        self.assertLessEqual(safe_lev, 14, f"Apalancamiento {safe_lev}x es demasiado alto para SL al -3.52%")
        self.assertGreaterEqual(safe_lev, 5, f"Apalancamiento {safe_lev}x es innecesariamente bajo")
        
        liq_dist = (1.0 / safe_lev) - 0.015
        sl_dist = abs(entry_p - sl_p) / entry_p
        
        self.assertGreater(liq_dist, sl_dist * 1.40, "La liquidación no tiene el colchón de seguridad de 1.40x requerido")

    def test_tight_sl_allows_20x_leverage(self):
        """
        Caso de Scalping con SL Ceñido:
        Entry = 100.0, SL = 99.0 (-1.0%).
        Con un SL de solo 1.0%, 20X es perfectamente seguro (liquidación al 3.5% vs SL al 1.0%).
        """
        entry_p = 100.0
        sl_p = 99.0
        safe_lev = RiskManager.calculate_safe_leverage(entry_p, sl_p, mmr=0.015, safety_factor=1.50)
        
        self.assertEqual(safe_lev, 20, f"Para SL de 1.0%, se debe permitir el tope de 20x. Obtenido: {safe_lev}x")

    def test_pre_flight_liquidation_clearance_guard(self):
        """
        Verifica que el guardián de pre-vuelo detecte colisiones inminentes:
        Si intentamos forzar 20X con un SL del 3.52%, verify_liquidation_clearance debe dar is_safe = False.
        """
        entry_p = 0.015444
        sl_p = 0.014900
        
        # 1. Con 20x forzado: DEBE FALLAR (colisión inminente)
        is_safe, msg, ratio = RiskManager.verify_liquidation_clearance(entry_p, sl_p, leverage=20)
        self.assertFalse(is_safe, "El guardián debió rechazar 20X con SL del 3.52%")
        self.assertLess(ratio, 1.10, f"El ratio debió ser cercano a 1.0x (colisión). Obtenido: {ratio}")
        
        # 2. Con apalancamiento seguro (12x): DEBE APROBAR
        safe_lev = RiskManager.calculate_safe_leverage(entry_p, sl_p)
        is_safe_2, msg_2, ratio_2 = RiskManager.verify_liquidation_clearance(entry_p, sl_p, leverage=safe_lev)
        self.assertTrue(is_safe_2, f"Apalancamiento seguro {safe_lev}x debió ser aprobado por el guardián")
        self.assertGreaterEqual(ratio_2, 1.40, f"Ratio {ratio_2} debió ser >= 1.40x")

    def test_micro_token_dynamic_decimal_precision(self):
        """
        Verifica que AKEUSDT y tokens micro (< $0.10) reciban 6 decimales de precio
        y no sean truncados a 4 decimales.
        """
        q_dec, p_dec = asyncio.run(self.executor.get_symbol_precision("AKEUSDT"))
        
        self.assertEqual(p_dec, 6, f"AKEUSDT debe tener 6 decimales de precisión de precio. Obtenido: {p_dec}")
        self.assertEqual(q_dec, 0, f"AKEUSDT debe tener 0 decimales de cantidad (enteros). Obtenido: {q_dec}")
        
        # Simular formateo de Take Profit en AKEUSDT
        tp_price = 0.016216
        formatted = f"{tp_price:.{p_dec}f}"
        self.assertEqual(formatted, "0.016216", f"El TP debió formatearse con 6 decimales: {formatted}")

    def test_calculate_position_integrates_sop21(self):
        """
        Verifica que el método principal calculate_position de RiskManager
        asigne el safe_leverage automáticamente en el dict devuelto.
        """
        pos_data = self.rm.calculate_position(
            current_price=0.015444,
            signal_type="LONG",
            atr_value=0.0005,
            asset="AKEUSDT"
        )
        
        lev = pos_data.get("leverage")
        self.assertIsNotNone(lev)
        self.assertLessEqual(lev, 20)
        self.assertGreaterEqual(lev, 1)


if __name__ == "__main__":
    unittest.main()
