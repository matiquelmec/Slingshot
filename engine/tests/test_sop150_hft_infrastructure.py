"""
SOP-150 Infrastructure & Vectorization Verification Suite:
1. BitunixExecutor TLS Keep-Alive pooling & 1.5s L2 burst cache
2. Vectorized NumPy/Polars Volume Profile parity & performance
3. /api/v1/analytics/forward-tracker endpoint contract
"""

import asyncio
import time
import numpy as np
import pandas as pd
import pytest

from engine.execution.bitunix_executor import BitunixExecutor
from engine.indicators.volume import calculate_volume_profile
from engine.indicators.polars_engine import PolarsEngine


def test_bitunix_executor_http_client_pooling_and_loop_resilience():
    ex = BitunixExecutor(api_key="k", secret_key="s", dry_run=True)

    async def _run():
        c1 = ex._get_http_client()
        c2 = ex._get_http_client()
        assert c1 is c2
        assert not c1.is_closed
        await ex.aclose()
        assert ex._http_client is None

    asyncio.run(_run())
    # New event loop must seamlessly allocate a fresh client
    asyncio.run(_run())


def test_bitunix_executor_l2_burst_cache():
    BitunixExecutor._shared_l2_depth_cache.clear()
    ex = BitunixExecutor(api_key="k", secret_key="s", dry_run=False)
    calls = {"count": 0}

    async def fake_request(method, path, params=None, json_body=None):
        calls["count"] += 1
        return {
            "code": 0,
            "data": {
                "bids": [["60000.0", "2.5"], ["59990.0", "1.5"]],
                "asks": [["60010.0", "2.0"], ["60020.0", "3.0"]],
            },
        }

    ex._request = fake_request  # type: ignore

    async def _run():
        res1 = await ex.get_orderbook_depth("BTCUSDT", limit=15)
        res2 = await ex.get_orderbook_depth("BTCUSDT", limit=15)
        assert res1 == res2
        assert res1 is not None
        assert len(res1["bids"]) == 2
        assert calls["count"] == 1

    asyncio.run(_run())
    BitunixExecutor._shared_l2_depth_cache.clear()


def test_vectorized_volume_profile_parity_and_speed():
    rng = np.random.default_rng(42)
    n = 300
    base = 60000 + np.cumsum(rng.normal(0, 50, size=n))
    df = pd.DataFrame({
        "open": base,
        "high": base + rng.uniform(5, 80, size=n),
        "low": base - rng.uniform(5, 80, size=n),
        "close": base + rng.normal(0, 20, size=n),
        "volume": rng.uniform(10, 500, size=n),
    })

    t0 = time.perf_counter()
    vp = calculate_volume_profile(df, bins=50)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert vp["vah"] >= vp["poc"] >= vp["val"]
    assert elapsed_ms < 100.0

    vp_polars = PolarsEngine.compute_volume_profile(df, bins=50)
    assert np.isclose(vp["poc"], vp_polars["poc"])
    assert np.isclose(vp["vah"], vp_polars["vah"])
    assert np.isclose(vp["val"], vp_polars["val"])


@pytest.mark.asyncio
async def test_forward_tracker_endpoint_contract():
    from engine.api.main import get_forward_tracker_audit

    res = await get_forward_tracker_audit()
    assert "frozen_mode" in res
    assert "summary" in res
    assert "policy_audit_log" in res
    summary = res["summary"]
    assert "drift_status" in summary
    assert "drift_z_score" in summary
    assert "implementation_shortfall_r" in summary
    assert "realized_expectancy_r" in summary
