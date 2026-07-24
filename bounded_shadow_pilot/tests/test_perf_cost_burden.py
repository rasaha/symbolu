"""Phase 15-16 tests: governance overhead is bounded and deterministic; reviewer burden is measured and
frozen content excludes wall-clock (byte-reproducible).
"""
from bounded_shadow_pilot import perf_cost_burden as pcb


def test_governance_overhead_bounded_and_deterministic():
    a = pcb.compute()
    b = pcb.compute()
    assert a == b                                             # no wall-clock in the frozen content
    assert a["governance_cost"]["total_estimated_usd"] == 0.0  # governance makes no provider call
    assert a["governance_latency_units"]["p95"] <= a["governance_latency_units"]["max"]


def test_reviewer_burden_measured():
    m = pcb.compute()
    rb = m["reviewer_burden"]
    assert 0 <= rb["artifacts_routed_to_review"] <= m["n"]
    assert 0.0 <= rb["burden_rate"] <= 1.0
    # over-qualified deliveries dominate but do not all add burden (they deliver with caveats)
    assert rb["artifacts_routed_to_review"] < m["n"]
