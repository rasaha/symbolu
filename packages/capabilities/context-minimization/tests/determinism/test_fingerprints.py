"""Correction D — two-fingerprint contract (v0.1.1).

``run_fingerprint`` binds the complete run identity (request + policy + oracle +
outcome); ``outcome_fingerprint`` binds only the selected outcome; ``fingerprint``
is a byte-identical deprecated alias of ``outcome_fingerprint``.
"""

from __future__ import annotations

import pytest

from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    MinimizationPolicy,
    minimize_context,
    structural_minimize,
)

from support import KeywordOracle, WordCounter, context, unit


def _units():
    return [
        ContextUnit(id="crit", text="deploy anchor", source_type="state_fact"),
        ContextUnit(id="f1", text="weekly sprint filler", source_type="log_event"),
        ContextUnit(id="f2", text="on-call historical note", source_type="log_event"),
    ]


def _ctx(correlation_id="corr-1", **kw):
    return Context(id="c", correlation_id=correlation_id, units=tuple(_units()), **kw)


def _run(ctx, **kw):
    kw.setdefault("target_reduction", 0.5)
    kw.setdefault("evaluation_time", 1.0)
    return minimize_context(ctx, oracle=KeywordOracle(), **kw)


def test_identical_runs_produce_identical_fingerprints():
    a, b = _run(_ctx()), _run(_ctx())
    assert a.run_fingerprint == b.run_fingerprint
    assert a.outcome_fingerprint == b.outcome_fingerprint


def test_changed_context_text_changes_run_fingerprint():
    base = _run(_ctx())
    units = _units()
    units[0] = ContextUnit(id="crit", text="deploy anchor CHANGED", source_type="state_fact")
    changed = _run(Context(id="c", correlation_id="corr-1", units=tuple(units)))
    assert changed.run_fingerprint != base.run_fingerprint


def test_changed_correlation_changes_run_fingerprint():
    base = _run(_ctx(correlation_id="corr-1"))
    changed = _run(_ctx(correlation_id="corr-2"))
    assert changed.run_fingerprint != base.run_fingerprint


def test_changed_requested_reduction_changes_run_fingerprint():
    base = _run(_ctx(), target_reduction=0.5)
    changed = _run(_ctx(), target_reduction=0.9)
    assert changed.run_fingerprint != base.run_fingerprint


def test_changed_token_budget_changes_run_fingerprint():
    base = _run(_ctx(), token_budget=None)
    changed = _run(_ctx(), token_budget=3)
    assert changed.run_fingerprint != base.run_fingerprint


def test_changed_policy_changes_run_fingerprint():
    base = _run(_ctx())
    custom = MinimizationPolicy(filler_hints=("totally", "different"), version="cm-policy/custom")
    changed = _run(_ctx(), policy=custom)
    assert changed.run_fingerprint != base.run_fingerprint


def test_changed_token_counts_change_run_fingerprint():
    base = _run(_ctx())
    # inject a different counting mode → resolved per-unit counts change
    changed = _run(_ctx(), token_counter=WordCounter())
    assert changed.run_fingerprint != base.run_fingerprint


def test_changed_outcome_changes_outcome_fingerprint():
    a = _run(_ctx(), target_reduction=0.0)   # removes nothing extractively
    b = _run(_ctx(), target_reduction=1.0)   # removes filler
    assert a.surviving_ids != b.surviving_ids
    assert a.outcome_fingerprint != b.outcome_fingerprint


def test_reason_code_change_affects_run_fingerprint_only():
    # Same outcome (full context retained) but different reason codes: a raising oracle
    # (ORACLE_RAISED) vs a correlation-missing oracle. The run fingerprint includes
    # reason codes; the outcome fingerprint (per the chosen contract) does not.
    from support import MissingCorrelationOracle, RaisingOracle
    a = minimize_context(_ctx(), oracle=RaisingOracle(), target_reduction=0.5, evaluation_time=1.0)
    b = minimize_context(_ctx(), oracle=MissingCorrelationOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert a.surviving_ids == b.surviving_ids  # both full fallback
    assert a.reason_codes != b.reason_codes
    assert a.run_fingerprint != b.run_fingerprint


def test_fingerprint_is_alias_of_outcome_fingerprint():
    r = _run(_ctx())
    assert r.fingerprint == r.outcome_fingerprint
    assert r.fingerprint.startswith("sha256:")


def test_run_and_outcome_fingerprints_are_distinct_digests():
    r = _run(_ctx())
    assert r.run_fingerprint != r.outcome_fingerprint  # different domain separators


def test_metadata_ordering_does_not_change_fingerprints():
    import collections
    m1 = {"a": "1", "b": "2"}
    m2 = collections.OrderedDict([("b", "2"), ("a", "1")])
    u1 = (ContextUnit(id="x", text="deploy", source_type="state_fact", metadata=m1),)
    u2 = (ContextUnit(id="x", text="deploy", source_type="state_fact", metadata=m2),)
    r1 = minimize_context(Context(id="c", correlation_id="k", units=u1),
                          oracle=KeywordOracle(), target_reduction=0.0, evaluation_time=1.0)
    r2 = minimize_context(Context(id="c", correlation_id="k", units=u2),
                          oracle=KeywordOracle(), target_reduction=0.0, evaluation_time=1.0)
    assert r1.run_fingerprint == r2.run_fingerprint


def test_structural_mode_populates_both_fingerprints():
    r = structural_minimize(context([unit("a", "x"), unit("b", "x")]))
    assert r.run_fingerprint.startswith("sha256:")
    assert r.outcome_fingerprint.startswith("sha256:")
    assert r.fingerprint == r.outcome_fingerprint


def test_non_scalar_metadata_value_rejected_at_construction():
    # v0.1.2: a non-scalar metadata value is rejected (never str()-coerced with a
    # nondeterministic repr), deterministically, at model construction.
    import pytest
    from ugence_context_minimization.api import InvalidUnitError
    with pytest.raises(InvalidUnitError):
        ContextUnit(id="x", text="deploy", source_type="state_fact", metadata={"k": [1, 2, 3]})
