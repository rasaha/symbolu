"""Tests for the Workflow-Fit offline validation study harness.

Assessment logic is tested on synthetic run records; one integration test runs
real workflows with scripted clients. No LLM key is needed.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from agentic.agentic_framework.reasoning_workflows import WorkflowType
from experiments.workflow_fit_study.study import (
    FitOutcome,
    RunRecord,
    StudyConfig,
    TaskCase,
    assess,
    aggregate,
    render_report,
    run_full_study,
    validate_selector,
)

LC, TOT, DEB = WorkflowType.LINEAR_CHAIN, WorkflowType.TREE_OF_THOUGHT, WorkflowType.DEBATE


def rec(tc, wf, q, calls, self_q=0.5, case="c1"):
    return RunRecord(case, tc, wf, Decimal(str(q)), calls, calls, 1.0, self_q)


def cfg(sufficiency, workflows=(LC, TOT, DEB), baseline=LC):
    return StudyConfig(workflows=workflows, baseline=baseline, sufficiency=sufficiency, max_llm_calls=10)


# ------------------------------------------------------------------ outcomes
def test_all_four_outcomes_are_reachable():
    records = [rec("easy", LC, 0.92, 1), rec("easy", TOT, 0.94, 4), rec("easy", DEB, 0.95, 5),
               rec("hard", LC, 0.72, 1), rec("hard", TOT, 0.91, 4), rec("hard", DEB, 0.93, 5)]
    a = assess(records, cfg({"easy": Decimal("0.90"), "hard": Decimal("0.90")}))
    assert a[("easy", LC)].outcome is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert a[("easy", TOT)].outcome is FitOutcome.SUFFICIENT_RESOURCE_DOMINATED
    assert a[("easy", DEB)].outcome is FitOutcome.SUFFICIENT_RESOURCE_DOMINATED
    assert a[("hard", LC)].outcome is FitOutcome.INSUFFICIENT_QUALITY
    assert a[("hard", TOT)].outcome is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert a[("hard", DEB)].outcome is FitOutcome.SUFFICIENT_RESOURCE_DOMINATED  # threshold-only reading
    # a workflow with no runs in a class is evidence-absent
    a2 = assess([rec("easy", LC, 0.95, 1)], cfg({"easy": Decimal("0.9")}))
    assert a2[("easy", TOT)].outcome is FitOutcome.COMPARISON_EVIDENCE_ABSENT


def test_margins_and_deltas_are_attributes_not_a_score():
    a = assess([rec("t", LC, 0.92, 1), rec("t", TOT, 0.94, 4)], cfg({"t": Decimal("0.90")}, (LC, TOT)))
    assert a[("t", LC)].quality_margin == Decimal("0.0200")
    assert a[("t", TOT)].quality_margin == Decimal("0.0400")
    assert a[("t", LC)].resource_delta_calls == Decimal("0")
    assert a[("t", TOT)].resource_delta_calls == Decimal("3")
    assert a[("t", TOT)].dominated_by == (LC,)
    ins = assess([rec("t", LC, 0.70, 1), rec("t", TOT, 0.95, 4)], cfg({"t": Decimal("0.90")}, (LC, TOT)))
    assert ins[("t", LC)].quality_margin == Decimal("-0.2000")
    assert ins[("t", LC)].resource_delta_calls is None


def test_calls_only_strict_ties_are_not_domination():
    a = assess([rec("t", LC, 0.92, 3), rec("t", TOT, 0.94, 3)], cfg({"t": Decimal("0.90")}, (LC, TOT)))
    assert a[("t", LC)].outcome is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert a[("t", TOT)].outcome is FitOutcome.SUFFICIENT_PARETO_EFFICIENT


def test_cost_is_irrelevant_below_threshold():
    # cheapest workflow fails quality: it is INSUFFICIENT, and cannot dominate anyone
    a = assess([rec("t", LC, 0.50, 1), rec("t", TOT, 0.95, 4), rec("t", DEB, 0.96, 4)], cfg({"t": Decimal("0.90")}))
    assert a[("t", LC)].outcome is FitOutcome.INSUFFICIENT_QUALITY
    assert a[("t", TOT)].outcome is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert a[("t", DEB)].outcome is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert a[("t", TOT)].dominated_by == ()


# ------------------------------------------------------------------ evidence absent
def test_missing_threshold_and_missing_baseline_yield_evidence_absent():
    recs = [rec("t", LC, 0.95, 1), rec("t", TOT, 0.95, 4)]
    a = assess(recs, cfg({}, (LC, TOT)))  # no tau declared
    assert {f.outcome for f in a.values()} == {FitOutcome.COMPARISON_EVIDENCE_ABSENT}
    assert all(f.quality_margin is None for f in a.values())
    b = assess([rec("t", TOT, 0.95, 4)], cfg({"t": Decimal("0.9")}, (LC, TOT)))  # baseline never ran
    assert b[("t", TOT)].outcome is FitOutcome.COMPARISON_EVIDENCE_ABSENT
    assert "baseline" in b[("t", TOT)].reason


def test_no_default_threshold_exists():
    # a class with no declared tau must not be assessed against any implicit default
    a = assess([rec("undeclared", LC, 0.99, 1), rec("undeclared", TOT, 0.99, 4)], cfg({}, (LC, TOT)))
    assert a[("undeclared", LC)].outcome is FitOutcome.COMPARISON_EVIDENCE_ABSENT
    assert a[("undeclared", TOT)].outcome is FitOutcome.COMPARISON_EVIDENCE_ABSENT
    assert a[("undeclared", LC)].quality_margin is None
    assert a[("undeclared", TOT)].quality_margin is None
    with pytest.raises(ValueError):
        cfg({"t": Decimal("1.5")})
    with pytest.raises(ValueError):
        StudyConfig(workflows=(TOT,), baseline=LC, sufficiency={}, max_llm_calls=5)


# ------------------------------------------------------------------ self-score isolation
def test_self_reported_quality_never_affects_assessment():
    base = [rec("t", LC, 0.92, 1, self_q=0.0), rec("t", TOT, 0.94, 4, self_q=0.0)]
    flip = [rec("t", LC, 0.92, 1, self_q=1.0), rec("t", TOT, 0.94, 4, self_q=1.0)]
    c = cfg({"t": Decimal("0.90")}, (LC, TOT))
    assert assess(base, c) == assess(flip, c)


def test_determinism_of_report():
    # two task classes, two workflows, independently built record lists in differing input order
    forward = [rec("alpha", LC, 0.92, 1), rec("alpha", TOT, 0.94, 4),
               rec("beta", LC, 0.72, 1), rec("beta", TOT, 0.91, 4)]
    reverse = [rec("beta", TOT, 0.91, 4), rec("beta", LC, 0.72, 1),
               rec("alpha", TOT, 0.94, 4), rec("alpha", LC, 0.92, 1)]
    c = cfg({"alpha": Decimal("0.90"), "beta": Decimal("0.90")}, (LC, TOT))
    from experiments.workflow_fit_study.study import StudyResult
    # aggregate() must impose (task_class, workflow) order regardless of input order
    assert list(aggregate(forward)) == list(aggregate(reverse)) == [("alpha", LC), ("alpha", TOT), ("beta", LC), ("beta", TOT)]
    r1 = StudyResult(c, tuple(forward), aggregate(forward), assess(forward, c), ())
    r2 = StudyResult(c, tuple(reverse), aggregate(reverse), assess(reverse, c), ())
    rep1, rep2 = render_report(r1), render_report(r2)
    assert rep1 == rep2
    # class sections are emitted in sorted order even when the aggregates mapping is not
    unsorted = dict(reversed(list(aggregate(reverse).items())))
    r3 = StudyResult(c, tuple(reverse), unsorted, assess(reverse, c), ())
    rep3 = render_report(r3)
    assert rep3 == rep1
    assert rep3.index("## Task class `alpha`") < rep3.index("## Task class `beta`")
    assert "diagnostic only" in rep1
    assert "never used here" in rep1
    assert "Sufficiency rule:" in rep1 and "ballot 3" in rep1


# ------------------------------------------------------------------ integration with real workflows
class ScriptedLLM:
    """Deterministic client: every response carries the marker the scorer looks for."""

    def __init__(self, marker: str):
        self.marker = marker

    def call(self, prompt: str) -> str:
        return f"Reasoned answer. FINAL: {self.marker}. " + "detail " * 30


def contains_scorer(marker: str):
    return lambda text: Decimal("1") if marker in text else Decimal("0")


def test_integration_runs_real_workflows_and_counts_calls():
    cases = [TaskCase("q1", "routine", "How do I reset my password?", contains_scorer("RESET"))]
    c = cfg({"routine": Decimal("0.90")}, (LC, TOT), baseline=LC)
    result = run_full_study(cases, c, lambda: ScriptedLLM("RESET"))
    by = {r.workflow: r for r in result.records}
    # runtime-reported and harness-observed counts agree, and ToT costs more than Linear
    for r in result.records:
        assert r.calls_runtime_reported == r.calls_harness_observed
        assert r.quality == Decimal("1")
    assert by[TOT].calls_runtime_reported > by[LC].calls_runtime_reported
    assert result.assessments[("routine", LC)].outcome is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert result.assessments[("routine", TOT)].outcome is FitOutcome.SUFFICIENT_RESOURCE_DOMINATED
    # the self-reported score is captured as a bounded diagnostic; its isolation from
    # `quality` is established by the scorer assertion above, not by this range check
    assert all(0.0 <= r.self_reported_quality <= 1.0 for r in result.records)
    report = render_report(result)
    assert "`routine`" in report and "SUFFICIENT_RESOURCE_DOMINATED" in report


def test_selector_validation_reports_routed_outcome_or_absence():
    cases = [TaskCase("q1", "routine", "How do I reset my password?", contains_scorer("X"))]
    recs = [rec("routine", LC, 0.95, 1, case="q1"), rec("routine", TOT, 0.95, 4, case="q1")]
    c_full = cfg({"routine": Decimal("0.9")}, (LC, TOT))
    v = validate_selector(cases, assess(recs, c_full), c_full)
    assert len(v) == 1 and v[0].routed in (LC, TOT)
    assert v[0].routed_outcome in (FitOutcome.SUFFICIENT_PARETO_EFFICIENT, FitOutcome.SUFFICIENT_RESOURCE_DOMINATED)
    # a study set that excludes whatever the selector routes to yields evidence absent
    c_narrow = cfg({"routine": Decimal("0.9")}, (DEB,), baseline=DEB)
    v2 = validate_selector(cases, assess([rec("routine", DEB, 0.95, 5, case="q1")], c_narrow), c_narrow)
    assert v2[0].routed_outcome is FitOutcome.COMPARISON_EVIDENCE_ABSENT
