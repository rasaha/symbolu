"""Correction C — the result preserves the caller's actual request (v0.1.1).

``requested_reduction`` must equal what the caller asked (not a hardcoded 0.0), on
every path; ``requested_token_budget`` records the absolute budget when supplied;
and the result must not infer a fractional target from a token budget.
"""

from __future__ import annotations

import dataclasses

from ugence_context_minimization.api import (
    MinimizationMode,
    minimize_context,
    structural_minimize,
)

from support import (
    AtLeastOneOracle,
    KeywordOracle,
    RaisingOracle,
    WrongCorrelationOracle,
    context,
    unit,
)


def _ctx():
    return context([
        unit("crit", "deploy anchor", source_type="state_fact"),
        unit("f1", "filler one two three", source_type="log_event"),
        unit("f2", "filler four five six", source_type="log_event"),
    ])


def test_target_zero_reported_as_zero():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.0, evaluation_time=1.0)
    assert r.requested_reduction == 0.0


def test_target_half_reported_as_half():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert r.requested_reduction == 0.5


def test_target_one_reported_as_one():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=1.0, evaluation_time=1.0)
    assert r.requested_reduction == 1.0


def test_fallback_preserves_original_target():
    r = minimize_context(_ctx(), oracle=RaisingOracle(), target_reduction=0.7, evaluation_time=1.0)
    assert r.fell_back and r.requested_reduction == 0.7


def test_restoration_preserves_original_target():
    ctx = context([
        unit("keep", "unrelated note", source_type="state_fact"),
        unit("crit", "historical deploy record", source_type="log_event"),
    ])
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.9, evaluation_time=1.0)
    assert r.restored_ids and r.requested_reduction == 0.9


def test_no_reduction_preserves_original_target():
    # single protected unit → nothing removable, but the request is still reported.
    ctx = context([unit("only", "deploy anchor", source_type="state_fact", protected=True)])
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.4,
                         protected_ids=["only"], evaluation_time=1.0)
    assert r.requested_reduction == 0.4


def test_correlation_failure_preserves_target():
    r = minimize_context(_ctx(), oracle=WrongCorrelationOracle(), target_reduction=0.3, evaluation_time=1.0)
    assert r.fell_back and r.requested_reduction == 0.3


def test_impossible_budget_preserves_requested_budget():
    ctx = context([unit("crit", "deploy anchor", source_type="state_fact", protected=True),
                   unit("f1", "filler", source_type="log_event")])
    r = minimize_context(ctx, oracle=KeywordOracle(), token_budget=0,
                         protected_ids=["crit"], evaluation_time=1.0)
    assert r.requested_token_budget == 0
    # a token budget is NOT reported as a fractional target
    assert r.requested_reduction == 0.0


def test_token_budget_recorded_and_distinct_from_reduction():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5,
                         token_budget=5, evaluation_time=1.0)
    assert r.requested_reduction == 0.5
    assert r.requested_token_budget == 5
    # achieved reduction is distinct from either request
    assert isinstance(r.achieved_reduction, float)


def test_structural_mode_reports_request_semantics():
    ctx = context([unit("a", "x"), unit("b", "x")])
    r = structural_minimize(ctx)
    assert r.mode is MinimizationMode.STRUCTURAL
    assert r.requested_reduction == 0.0
    assert r.requested_token_budget is None


def test_result_serialization_preserves_request_fields():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5,
                         token_budget=7, evaluation_time=1.0)
    d = dataclasses.asdict(r)
    assert d["requested_reduction"] == 0.5
    assert d["requested_token_budget"] == 7
    assert "outcome_fingerprint" in d and "run_fingerprint" in d
