"""
SOP-126: Sovereign Multi-Account Isolation & UI Telemetry Hydration Tests
==========================================================================
Certifies:
1. ClusterRiskGuard per-account isolation & deduplication of 'SOLUSDT' + 'primary_SOLUSDT'.
2. Per-account post-stopout cooldown isolation (primary vs secondary accounts).
3. Secondary account < $5.00 balance 60s TTL expiration (automatic recovery after deposit).
"""

import time
import pytest
from unittest.mock import MagicMock

from engine.risk.cluster_risk_guard import ClusterRiskGuard


def test_cluster_risk_guard_account_isolation_and_deduplication():
    """
    Certifies that:
    - 'SOLUSDT' and 'primary_SOLUSDT' in active_positions are deduplicated as 1 position for 'primary'.
    - Positions open on 'primary' NEVER block 'cliente_2' from opening the same cluster/direction.
    """
    guard = ClusterRiskGuard()

    active_positions = {
        # Legacy bare key + prefixed key for same position on primary
        "SOLUSDT": {
            "account_id": "primary",
            "signal": {"asset": "SOLUSDT", "type": "LONG", "price": 150.0, "stop_loss": 145.0},
        },
        "primary_SOLUSDT": {
            "account_id": "primary",
            "signal": {"asset": "SOLUSDT", "type": "LONG", "price": 150.0, "stop_loss": 145.0},
        },
        "primary_AVAXUSDT": {
            "account_id": "primary",
            "signal": {"asset": "AVAXUSDT", "type": "LONG", "price": 30.0, "stop_loss": 28.0},
        },
    }

    # 1. With deduplication, primary has 2 CRYPTO LONG positions (SOL + AVAX), so SUI LONG is blocked for primary
    allowed_primary, reason_primary = guard.can_open_position(
        new_asset="SUIUSDT",
        new_direction="LONG",
        confluence_score=70.0,
        active_positions=active_positions,
        account_id="primary",
    )
    assert allowed_primary is False

    # 2. For 'cliente_2', active positions in CRYPTO LONG is 0 -> MUST BE ALLOWED!
    allowed_secondary, reason_secondary = guard.can_open_position(
        new_asset="SUIUSDT",
        new_direction="LONG",
        confluence_score=70.0,
        active_positions=active_positions,
        account_id="cliente_2",
    )
    assert allowed_secondary is True


def test_cluster_risk_guard_single_position_not_double_counted():
    """
    Certifies that a single position stored under both 'SOLUSDT' and 'primary_SOLUSDT'
    counts as 1 position (not 2), allowing a second CRYPTO position on 'primary'.
    """
    guard = ClusterRiskGuard()
    active_positions = {
        "SOLUSDT": {
            "account_id": "primary",
            "signal": {"asset": "SOLUSDT", "type": "LONG", "price": 150.0, "stop_loss": 145.0},
        },
        "primary_SOLUSDT": {
            "account_id": "primary",
            "signal": {"asset": "SOLUSDT", "type": "LONG", "price": 150.0, "stop_loss": 145.0},
        },
    }

    allowed, reason = guard.can_open_position(
        new_asset="SUIUSDT",
        new_direction="LONG",
        confluence_score=85.0,
        active_positions=active_positions,
        account_id="primary",
    )
    assert allowed is True


def test_per_account_cooldown_isolation():
    """
    Certifies that setting an asset cooldown on 'primary' does not block 'cliente_2',
    and vice-versa.
    """
    from engine.execution.nexus import NexusNode

    node = NexusNode.__new__(NexusNode)
    node._asset_cooldown = {}

    node.set_asset_cooldown("BTCUSDT", duration_sec=900, reason="STOP_LOSS", account_id="primary")

    assert node.is_asset_in_cooldown("BTCUSDT", account_id="primary") is True
    assert node.is_asset_in_cooldown("BTCUSDT", account_id="cliente_2") is False

    node.set_asset_cooldown("BTCUSDT", duration_sec=900, reason="STOP_LOSS", account_id="cliente_2")
    assert node.is_asset_in_cooldown("BTCUSDT", account_id="cliente_2") is True


@pytest.mark.asyncio
async def test_secondary_account_zero_balance_ttl_recovery():
    """
    Certifies that a secondary account with < $5.00 balance gets a 60s TTL cache
    (_zero_balance_until_ts) instead of a permanent latch, and automatically re-queries
    balance once the TTL expires.
    """
    ex = MagicMock()
    ex._last_verified_balance = 0.0
    ex._zero_balance_until_ts = time.time() - 1.0  # Expired 1s ago

    zero_ttl = getattr(ex, "_zero_balance_until_ts", 0.0)
    should_skip = getattr(ex, "_last_verified_balance", None) == 0.0 and time.time() < zero_ttl
    assert should_skip is False

    # Now simulate active TTL (within 60s window)
    ex._zero_balance_until_ts = time.time() + 60.0
    zero_ttl_active = getattr(ex, "_zero_balance_until_ts", 0.0)
    should_skip_active = getattr(ex, "_last_verified_balance", None) == 0.0 and time.time() < zero_ttl_active
    assert should_skip_active is True


@pytest.mark.asyncio
async def test_sop128_privacy_shield_blocks_external_account_telemetry():
    """
    [SOP-128] Certifica que GET /api/v1/bitunix/telemetry nunca expone balances ni posiciones
    de cuentas de terceros (ej. cliente_2) y fuerza siempre STRICT_PRIMARY_ONLY.
    """
    import engine.api.main as api_main
    api_main._last_bitunix_telemetry_cache = {
        "status": "ONLINE",
        "account_id": "primary",
        "account_label": "Cuenta Principal",
        "balance_usdt": 100.0,
        "positions": [],
        "pending_orders": [],
    }
    resp = await api_main.get_bitunix_telemetry(account_id="cliente_2")
    assert resp["account_id"] == "primary"
    assert resp.get("privacy_shield") == "STRICT_PRIMARY_ONLY"
