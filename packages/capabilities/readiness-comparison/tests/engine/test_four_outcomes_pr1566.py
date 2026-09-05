"""The four-outcome fixtures and mutation checks proven in PR #1566, re-expressed
against the contracts (spec §9 item 2).

PR #1566's harness used classes "easy" and "hard" with three workflows:
Linear Chain (1 call), Tree of Thought (4 calls), Debate (5 calls), threshold
0.90. These are TEST INPUTS, not governed values.
"""

from __future__ import annotations

import matrix_fixtures as fx
from ugence_readiness_comparison import compare
from ugence_reasoning_method_governance.api import (
    COMPARISON_REQUEST_SCHEMA_VERSION,
    FitOutcome,
    QualityResult,
    ReadinessComparisonRequest,
)

LC, TOT, DEB = fx.c2_ref("linear_chain"), fx.c2_ref("tree_of_thought"), fx.c2_ref("debate")


def request(task_class_id, rows):
    """rows: [(method, quality, calls)]; baseline linear_chain; all three candidates."""
    tc = fx.c10_class(task_class_id=task_class_id)
    recs = tuple(fx.c15_record(m, fx.c12_telemetry(calls), tc, f"rec.{m.method_id}") for m, _q, calls in rows)
    qrs = tuple(QualityResult(m, f"claim.{m.method_id}", fx.UNIT, q, None) for m, q, _c in rows)
    claims = tuple(fx.claim(q.claim_ref, q.value) for q in qrs)
    return ReadinessComparisonRequest(COMPARISON_REQUEST_SCHEMA_VERSION, f"req.{task_class_id}", tc, fx.c1_catalog_ref(), LC, (LC, TOT, DEB), recs, qrs, claims)


def outcomes(res):
    return {a.method.method_id: a.outcome for a in res.assessments}


def test_all_four_outcomes_are_reachable():
    easy = compare(request("easy", [(LC, "0.92", 1), (TOT, "0.94", 4), (DEB, "0.95", 5)]), produced_at=fx.NOW)
    assert outcomes(easy) == {
        "linear_chain": FitOutcome.SUFFICIENT_PARETO_EFFICIENT,
        "tree_of_thought": FitOutcome.SUFFICIENT_RESOURCE_DOMINATED,
        "debate": FitOutcome.SUFFICIENT_RESOURCE_DOMINATED,
    }
    hard = compare(request("hard", [(LC, "0.72", 1), (TOT, "0.91", 4), (DEB, "0.93", 5)]), produced_at=fx.NOW)
    assert outcomes(hard) == {
        "linear_chain": FitOutcome.INSUFFICIENT_QUALITY,
        "tree_of_thought": FitOutcome.SUFFICIENT_PARETO_EFFICIENT,
        "debate": FitOutcome.SUFFICIENT_RESOURCE_DOMINATED,
    }
    absent = compare(request("absent", [(LC, "0.95", 1)]), produced_at=fx.NOW)
    assert outcomes(absent)["tree_of_thought"] is FitOutcome.COMPARISON_EVIDENCE_ABSENT
    assert outcomes(absent)["linear_chain"] is FitOutcome.SUFFICIENT_PARETO_EFFICIENT


def test_margins_and_deltas_are_attributes_not_a_score():
    res = compare(request("t", [(LC, "0.92", 1), (TOT, "0.94", 4)]), produced_at=fx.NOW)
    by = {a.method.method_id: a for a in res.assessments}
    assert by["linear_chain"].quality_margin == "0.02" and by["tree_of_thought"].quality_margin == "0.04"
    assert by["linear_chain"].deltas_vs_baseline[0].delta == "0" and by["tree_of_thought"].deltas_vs_baseline[0].delta == "3"
    assert [d.dominator for d in by["tree_of_thought"].dominated_by] == [LC]
    fields = set(by["tree_of_thought"].__dataclass_fields__)
    assert not any(n in fields for n in ("score", "composite", "total", "weight", "rank"))


def test_strict_ties_are_not_domination():
    res = compare(request("t", [(LC, "0.92", 4), (TOT, "0.94", 4)]), produced_at=fx.NOW)
    assert set(outcomes(res).values()) == {FitOutcome.SUFFICIENT_PARETO_EFFICIENT, FitOutcome.COMPARISON_EVIDENCE_ABSENT}
    assert outcomes(res)["linear_chain"] is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert outcomes(res)["tree_of_thought"] is FitOutcome.SUFFICIENT_PARETO_EFFICIENT


def test_cost_is_irrelevant_below_threshold():
    res = compare(request("t", [(LC, "0.70", 1), (TOT, "0.95", 4)]), produced_at=fx.NOW)
    assert outcomes(res)["linear_chain"] is FitOutcome.INSUFFICIENT_QUALITY
    assert outcomes(res)["tree_of_thought"] is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    tot = next(a for a in res.assessments if a.method == TOT)
    assert tot.dominated_by == (), "an insufficient cheaper method never dominates"


def test_missing_threshold_is_not_possible_by_construction_and_missing_baseline_is_absence():
    # A task class cannot exist without a SufficiencyRule (no default threshold exists).
    import pytest

    from ugence_reasoning_method_governance.api import ComparisonPolicy, ContractError

    with pytest.raises((ContractError, TypeError)):
        ComparisonPolicy("p", "1", None, (fx.ResourceDimension.LLM_CALLS,), None)  # type: ignore[arg-type]
    tc = fx.c10_class(task_class_id="nobase")
    recs = (fx.c15_record(TOT, fx.c12_telemetry(4), tc, "rec.tot"),)
    qrs = (QualityResult(TOT, "claim.tot", fx.UNIT, "0.95", None),)
    req = ReadinessComparisonRequest(COMPARISON_REQUEST_SCHEMA_VERSION, "req.nobase", tc, fx.c1_catalog_ref(), LC, (TOT,), recs, qrs, (fx.claim("claim.tot", "0.95"),))
    res = compare(req, produced_at=fx.NOW)
    assert outcomes(res)["tree_of_thought"] is FitOutcome.COMPARISON_EVIDENCE_ABSENT
    assert "baseline" in res.refusals[0].detail


def test_determinism_of_result():
    a = compare(request("t", [(LC, "0.92", 1), (TOT, "0.94", 4), (DEB, "0.95", 5)]), produced_at=fx.NOW)
    b = compare(request("t", [(LC, "0.92", 1), (TOT, "0.94", 4), (DEB, "0.95", 5)]), produced_at=fx.NOW)
    assert a.result_digest == b.result_digest
    assert [x.method.method_id for x in a.assessments] == ["debate", "linear_chain", "tree_of_thought"]
