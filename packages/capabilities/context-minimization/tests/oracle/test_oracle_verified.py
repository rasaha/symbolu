"""Oracle-verified (Mode B) minimization tests — required scenarios 17–28."""

from __future__ import annotations

import pytest

from ugence_context_minimization import reasons
from ugence_context_minimization.api import (
    EquivalenceStatus,
    OracleRequiredError,
    minimize_context,
)

from support import (
    AtLeastOneOracle,
    DriftingContractOracle,
    NonStringKeyOracle,
    ExpiringOracle,
    KeywordOracle,
    MalformedOracle,
    RaisingOracle,
    RecordingOracle,
    WrongCorrelationOracle,
    context,
    unit,
)


def _ctx():
    # Two 'critical' carriers (deploy, backup) and two pure-filler removable spans.
    return context([
        unit("crit1", "deploy service to prod", source_type="state_fact"),
        unit("crit2", "backup verified restorable", source_type="state_fact"),
        unit("fill1", "weekly sprint planning chatter", source_type="log_event"),
        unit("fill2", "on-call rotation historical note", source_type="log_event"),
    ])


def test_fully_invariant_removal_succeeds():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert r.equivalence_status is EquivalenceStatus.VERIFIED
    assert not r.fell_back
    # the two filler spans (no critical keyword) are removed; critical carriers kept
    assert "crit1" in r.surviving_ids and "crit2" in r.surviving_ids
    assert set(r.removed_ids) <= {"fill1", "fill2"}
    assert reasons.EQUIVALENCE_VERIFIED in r.reason_codes


def test_changed_key_restores_necessary_units():
    # A critical carrier is the lowest-priority (filler-hinted) — force it into the
    # removal set, then require restoration.
    ctx = context([
        unit("keep", "unrelated note", source_type="state_fact"),
        unit("crit", "historical deploy record", source_type="log_event"),  # filler-hinted + critical
    ])
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=1.0, evaluation_time=1.0)
    assert "crit" in r.surviving_ids            # restored
    assert "crit" in r.restored_ids
    assert r.equivalence_status is EquivalenceStatus.RESTORED
    assert reasons.SPANS_RESTORED in r.reason_codes


def test_unresolved_joint_effect_causes_full_fallback():
    # a & b are redundant carriers of a single requirement; removing either alone is
    # invariant, but the extractor removes BOTH — per-unit restoration cannot recover.
    ctx = context([
        unit("a", "first filler", source_type="log_event"),
        unit("b", "second filler", source_type="log_event"),
        unit("c", "anchor", source_type="state_fact"),
    ])
    r = minimize_context(ctx, oracle=AtLeastOneOracle({"a", "b"}), target_reduction=1.0, evaluation_time=1.0)
    assert r.fell_back
    assert r.surviving_ids == r.original_ids       # full context returned
    assert r.equivalence_status is EquivalenceStatus.FALLBACK
    assert reasons.JOINT_EFFECT_FALLBACK in r.reason_codes


def test_oracle_exception_causes_full_fallback():
    r = minimize_context(_ctx(), oracle=RaisingOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back and r.surviving_ids == r.original_ids
    assert reasons.ORACLE_RAISED in r.reason_codes


def test_malformed_oracle_result_fails_closed():
    r = minimize_context(_ctx(), oracle=MalformedOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back
    assert reasons.ORACLE_RESULT_MALFORMED in r.reason_codes


def test_non_string_key_fails_closed():
    r = minimize_context(_ctx(), oracle=NonStringKeyOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back
    assert reasons.ORACLE_RESULT_MALFORMED in r.reason_codes


def test_missing_oracle_is_rejected():
    with pytest.raises(OracleRequiredError):
        minimize_context(_ctx(), oracle=None, target_reduction=0.5)


def test_expired_evaluation_fails_closed():
    r = minimize_context(_ctx(), oracle=ExpiringOracle(), target_reduction=0.5, evaluation_time=1000.0)
    assert r.fell_back
    assert reasons.ORACLE_EVALUATION_EXPIRED in r.reason_codes


def test_correlation_mismatch_fails_closed():
    r = minimize_context(_ctx(), oracle=WrongCorrelationOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back
    assert reasons.ORACLE_CORRELATION_MISMATCH in r.reason_codes


def test_contract_drift_between_calls_fails_closed():
    # base (4 units) -> cv 1.0; reduced (<4) -> cv 2.0 => contract mismatch.
    r = minimize_context(_ctx(), oracle=DriftingContractOracle(threshold=4),
                         target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back
    assert reasons.ORACLE_CONTRACT_MISMATCH in r.reason_codes


def test_matching_oracle_reference_succeeds_and_records_identity():
    oracle = KeywordOracle(oracle_id="kw-42", contract_version="7.3")
    r = minimize_context(_ctx(), oracle=oracle, target_reduction=0.5, evaluation_time=1.0)
    assert r.oracle_id == "kw-42" and r.oracle_contract_version == "7.3"


def test_oracle_reached_only_through_declared_interface():
    rec = RecordingOracle(KeywordOracle())
    r = minimize_context(_ctx(), oracle=rec, target_reduction=0.5, evaluation_time=1.0)
    assert rec.evaluate_calls >= 2   # base + reduced, all via evaluate()
    assert not r.fell_back


def test_no_rewrite_output_units_are_input_units():
    ctx = _ctx()
    r = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    original = {u.id: u.text for u in ctx.units}
    for uid in r.surviving_ids:
        # every surviving span is byte-for-byte the input span
        assert ctx.unit(uid).text == original[uid]
    # nothing new was synthesized
    assert set(r.surviving_ids) <= set(original)
