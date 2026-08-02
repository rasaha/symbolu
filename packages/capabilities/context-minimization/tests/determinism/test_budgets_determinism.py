"""Budget, invalid-input and determinism tests — required scenarios 34–40."""

from __future__ import annotations

import pytest

from ugence_context_minimization import reasons
from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    EquivalenceStatus,
    InvalidRequestError,
    MinimizationPolicy,
    minimize_context,
)

from support import KeywordOracle, WordCounter, context, unit


def _ctx():
    return context([
        unit("crit", "deploy anchor", source_type="state_fact"),
        unit("f1", "filler one two three", source_type="log_event"),
        unit("f2", "filler four five six", source_type="log_event"),
    ])


def test_zero_reduction_removes_nothing_extractive():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.0, evaluation_time=1.0)
    # no target => extractive removes nothing (structural may still dedup, but here none)
    assert r.removed_extractive == ()
    assert r.equivalence_status is EquivalenceStatus.VERIFIED


def test_full_reduction_request_keeps_only_what_the_oracle_needs():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=1.0, evaluation_time=1.0)
    assert "crit" in r.surviving_ids
    assert set(r.removed_ids) == {"f1", "f2"}


def test_impossible_budget_returns_safest_achievable_and_flags_it():
    # budget of 0 tokens is impossible without removing the protected/critical anchor.
    ctx = context([unit("crit", "deploy anchor", source_type="state_fact", protected=True),
                   unit("f1", "filler", source_type="log_event")])
    r = minimize_context(ctx, oracle=KeywordOracle(), token_budget=0,
                         protected_ids=["crit"], evaluation_time=1.0)
    assert "crit" in r.surviving_ids
    assert reasons.BUDGET_UNREACHABLE_WITHOUT_PROTECTED in r.reason_codes


def test_invalid_target_rejected():
    with pytest.raises(InvalidRequestError):
        minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=1.5)
    with pytest.raises(InvalidRequestError):
        minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=-0.1)


def test_negative_token_budget_rejected():
    with pytest.raises(InvalidRequestError):
        minimize_context(_ctx(), oracle=KeywordOracle(), token_budget=-1)


def test_identical_inputs_produce_identical_results_and_fingerprints():
    a = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    b = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert a.surviving_ids == b.surviving_ids
    assert a.removed_ids == b.removed_ids
    assert a.fingerprint == b.fingerprint


def test_changed_policy_produces_a_different_policy_fingerprint():
    p1 = MinimizationPolicy()
    p2 = MinimizationPolicy(filler_hints=("totally", "different"), version="cm-policy/custom")
    assert p1.fingerprint() != p2.fingerprint()


def test_changed_context_identity_produces_different_result_identity():
    r1 = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    ctx2 = Context(id="different-id", units=_ctx().units, correlation_id="corr-1")
    r2 = minimize_context(ctx2, oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert r1.fingerprint != r2.fingerprint  # context_id is part of the digest


def test_caller_token_counts_and_injected_counter_agree_on_budget_math():
    # caller-supplied token_count on units
    units = [
        ContextUnit(id="crit", text="deploy anchor", source_type="state_fact", token_count=2),
        ContextUnit(id="f1", text="filler one two three", source_type="log_event", token_count=4),
    ]
    ctx = Context(id="ctx", units=tuple(units), correlation_id="corr-1")
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert r.original_tokens == 6
    # injected counter path
    units2 = [ContextUnit(id="crit", text="deploy anchor", source_type="state_fact"),
              ContextUnit(id="f1", text="filler one two three", source_type="log_event")]
    ctx2 = Context(id="ctx", units=tuple(units2), correlation_id="corr-1")
    r2 = minimize_context(ctx2, oracle=KeywordOracle(), target_reduction=0.5,
                          token_counter=WordCounter(), evaluation_time=1.0)
    assert r2.original_tokens == 6


def test_zero_and_negative_token_counts_are_handled():
    with pytest.raises(ValueError):
        ContextUnit(id="x", text="t", token_count=-1)
    # zero-token span is legal
    u = ContextUnit(id="x", text="", token_count=0)
    assert u.counted_tokens() == 0
