"""
engine/tests/test_multi_region_failover_coordinator.py
======================================================
Pruebas unitarias para Alta Disponibilidad Activo-Pasiva y Failover (SOP-110).
"""

import pytest
import time
from engine.resilience.multi_region_failover_coordinator import (
    MultiRegionFailoverCoordinator,
    get_default_cluster_health_report,
)


def test_coordinator_initial_healthy_state():
    """Valida estado inicial sincronizado con nodo Frankfurt como líder y Londres como centinela."""
    coord = MultiRegionFailoverCoordinator()
    report = coord.evaluate_cluster_health()

    assert report.cluster_status == "HEALTHY_SYNCED"
    assert report.active_leader_id == "node_frankfurt_vps"
    assert report.is_failover_ready is True
    assert report.nodes_count == 2
    assert report.lease_remaining_sec > 10.0


def test_coordinator_heartbeat_renewal():
    """Valida renovación del lease tras emisión de latidos periódicos."""
    coord = MultiRegionFailoverCoordinator(lease_ttl_sec=15.0)
    success = coord.send_heartbeat("node_frankfurt_vps", latency_ms=16.2)

    assert success is True
    report = coord.evaluate_cluster_health()
    assert report.lease_remaining_sec > 14.0


def test_coordinator_automatic_failover_on_leader_timeout():
    """Valida que si el líder deja de emitir latidos, el centinela sea promovido en sub-2s."""
    coord = MultiRegionFailoverCoordinator(lease_ttl_sec=0.1)  # TTL ultra corto para simulación
    time.sleep(0.15)  # Esperar que expire el lease

    # El centinela de Londres envía su latido fresco
    coord.send_heartbeat("node_london_sentinel", latency_ms=11.0)

    report = coord.evaluate_cluster_health()
    assert report.active_leader_id == "node_london_sentinel"
    assert report.cluster_status == "FAILOVER_ACTIVE"
    assert "FAILOVER_EJECUTADO" in report.last_failover_event


def test_default_cluster_health_report_helper():
    """Valida helper para contratos full-stack."""
    report = get_default_cluster_health_report()
    assert "activeLeaderId" in report
    assert "nodes" in report
    assert len(report["nodes"]) == 2
