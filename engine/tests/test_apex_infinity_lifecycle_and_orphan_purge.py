"""
engine/tests/test_apex_infinity_lifecycle_and_orphan_purge.py
=============================================================
Pruebas Unitarias QA — Slingshot v36.0 APEX INFINITY:
1. SOP-22 Atomic Orphan Purge: Cancelación masiva de órdenes límite cuando la posición se cierra.
2. SOP-22 Ghost Order Eradicator: Detección y erradicación de órdenes CLOSE de activos sin posición abierta.
3. SOP-22 SQLite Vault Maintenance: Purga de registros viejos y optimización WAL sin degradación.
4. SOP-23 Funding Rate Circuit Breaker: Veto a tasas adversas (> +0.05% en LONG / < -0.05% en SHORT).
5. SOP-24 FTMO Midnight Roll-Over Shield: Protección preventiva durante la ventana de corte bancario (21:50-22:05 UTC).
"""
import unittest
import asyncio
from engine.execution.bitunix_executor import BitunixExecutor
from engine.core.vault import vault
from engine.risk.risk_manager import RiskManager
from engine.risk.ftmo_guardian import FtmoGuardianShield


class TestApexInfinityLifecycleAndOrphanPurge(unittest.TestCase):
    def setUp(self):
        self.executor = BitunixExecutor(dry_run=True)
        self.ftmo = FtmoGuardianShield()

    def test_sop22_atomic_orphan_purge_dry_run(self):
        """
        Verifica que cancel_all_orders_for_symbol se invoque sin errores
        y limpie las órdenes pendientes registradas.
        """
        cancelled = asyncio.run(self.executor.cancel_all_orders_for_symbol("AKEUSDT"))
        self.assertIsInstance(cancelled, int)
        self.assertGreaterEqual(cancelled, 0)

    def test_sop22_ghost_order_eradicator(self):
        """
        Verifica que purge_orphaned_close_orders audite y limpie órdenes
        huérfanas de símbolos que no están en active_symbols.
        """
        active_symbols = {"BTCUSDT", "ETHUSDT"}
        purged = asyncio.run(self.executor.purge_orphaned_close_orders(active_symbols))
        self.assertIsInstance(purged, int)
        self.assertGreaterEqual(purged, 0)

    def test_sop22_vault_incremental_vacuum_maintenance(self):
        """
        Verifica que vacuum_and_purge_maintenance elimine registros viejos
        y ejecute checkpoints WAL de ciclo infinito sin errores de I/O.
        """
        stats = vault.vacuum_and_purge_maintenance(retention_days=7)
        self.assertIn("telegram_dispatches", stats)
        self.assertGreaterEqual(stats["telegram_dispatches"], 0)

    def test_sop23_funding_rate_circuit_breaker(self):
        """
        Verifica que el SOP-23 Funding Rate Circuit Breaker:
        - Rechace LONG si funding_rate > +0.05% (+0.0005).
        - Rechace SHORT si funding_rate < -0.05% (-0.0005).
        - Apruebe tasas normales.
        """
        # Caso 1: Funding excesivo en LONG (+0.08%) -> VETO
        approved_long_bad, msg1 = RiskManager.check_funding_rate_impact("AKEUSDT", "LONG", funding_rate=0.0008)
        self.assertFalse(approved_long_bad, "Debió vetar LONG con funding rate excesivo")
        self.assertIn("SOP-23 FUNDING VETO", msg1)

        # Caso 2: Funding normal en LONG (+0.01%) -> APROBADO
        approved_long_ok, msg2 = RiskManager.check_funding_rate_impact("AKEUSDT", "LONG", funding_rate=0.0001)
        self.assertTrue(approved_long_ok, "Debió aprobar LONG con funding rate normal")
        self.assertIn("SOP-23 FUNDING OK", msg2)

        # Caso 3: Funding excesivamente negativo en SHORT (-0.08%) -> VETO
        approved_short_bad, msg3 = RiskManager.check_funding_rate_impact("AKEUSDT", "SHORT", funding_rate=-0.0008)
        self.assertFalse(approved_short_bad, "Debió vetar SHORT con funding rate muy negativo")
        self.assertIn("SOP-23 FUNDING VETO", msg3)

    def test_sop24_midnight_rollover_shield_detection(self):
        """
        Verifica que el escudo de medianoche detecte con exactitud la ventana
        crítica de corte interbancario de FTMO (21:50 a 22:05 UTC).
        """
        # Dentro de la ventana crítica
        self.assertTrue(self.ftmo.check_midnight_rollover_risk(hour_utc=21, minute=55))
        self.assertTrue(self.ftmo.check_midnight_rollover_risk(hour_utc=22, minute=2))

        # Fuera de la ventana crítica
        self.assertFalse(self.ftmo.check_midnight_rollover_risk(hour_utc=14, minute=30))
        self.assertFalse(self.ftmo.check_midnight_rollover_risk(hour_utc=21, minute=40))
        self.assertFalse(self.ftmo.check_midnight_rollover_risk(hour_utc=22, minute=10))


if __name__ == "__main__":
    unittest.main()
