"""Orchestrator, invariants, fairness, failure matrix, metrics, cost (Tasks 8/10/11/12/15)."""
from __future__ import annotations

import pytest

from comparative_governance_benchmark.benchmark import run_benchmark

_RES = run_benchmark()


def test_overall_pass():
    assert _RES.overall_pass


@pytest.mark.parametrize("inv", _RES.invariants, ids=[i.id for i in _RES.invariants])
def test_benchmark_invariant(inv):
    assert inv.passed, f"{inv.id} {inv.description}: {inv.detail}"


@pytest.mark.parametrize("chk", _RES.fairness, ids=[c.name for c in _RES.fairness])
def test_fairness_control(chk):
    assert chk.passed, f"{chk.name}: {chk.detail}"


def test_all_applicable_failures_are_fail_safe():
    below = [(c.profile, c.strategy_id, c.fail_safe_rate) for c in _RES.failure_matrix
             if c.applicable and c.fail_safe_rate is not None and c.fail_safe_rate < 1.0]
    assert not below, below


def test_non_applicable_failures_not_scored():
    for c in _RES.failure_matrix:
        if not c.applicable:
            assert c.scenarios == 0 and c.fail_safe == 0 and c.fail_open == 0


def test_metrics_reported_per_layer_per_strategy():
    for sid in _RES.strategy_ids:
        assert set(_RES.metrics[sid]) == {"assertion", "action", "workflow"}


def test_metric_definitions_are_strategy_neutral():
    # full governance dominates simpler strategies on unsafe prevention
    m = _RES.metrics
    assert m["full_governance"]["action"]["unsafe_dispatch_rate"] == 0.0
    assert m["no_governance"]["action"]["unsafe_dispatch_rate"] == 1.0
    assert m["full_governance"]["assertion"]["unsupported_assertion_promotion_rate"] == 0.0
    assert m["no_governance"]["assertion"]["unsupported_assertion_promotion_rate"] == 1.0


def test_cost_increases_with_governance():
    c = _RES.cost
    assert c["no_governance"]["total_operations"] < c["assertion_only"]["total_operations"]
    assert c["no_governance"]["total_operations"] < c["full_governance"]["total_operations"]


def test_changing_a_result_changes_metrics():
    # metrics are a function of results: a different result set yields different metrics
    from comparative_governance_benchmark.metrics.compute import assertion_metrics
    from comparative_governance_benchmark.evaluators.oracle import judge
    ng = [(s, r, judge(s, r)) for s, r in _RES.grid["no_governance"]]
    full = [(s, r, judge(s, r)) for s, r in _RES.grid["full_governance"]]
    assert assertion_metrics(ng) != assertion_metrics(full)


def test_paired_analysis_present():
    assert "full_governance_vs_no_governance" in _RES.paired
    d = _RES.paired["full_governance_vs_no_governance"]
    assert d["net_unsafe_reduction"] == 27
