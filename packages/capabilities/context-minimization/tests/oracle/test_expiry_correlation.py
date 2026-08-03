"""Correction A (inclusive expiry + mandatory evaluation_time) and Correction B
(mandatory correlation binding) — v0.1.1 contract corrections."""

from __future__ import annotations

import pytest

from ugence_context_minimization import reasons
from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    EquivalenceStatus,
    minimize_context,
)

from support import (
    ExpiryHorizonOracle,
    KeywordOracle,
    LenGatedOracle,
    MissingCorrelationOracle,
    NoCorrelationOracle,
    WrongCorrelationOracle,
    context,
    unit,
)


def _ctx():
    return context([
        unit("crit1", "deploy service to prod", source_type="state_fact"),
        unit("crit2", "backup verified restorable", source_type="state_fact"),
        unit("fill1", "weekly sprint planning chatter", source_type="log_event"),
        unit("fill2", "on-call rotation historical note", source_type="log_event"),
    ])


def _triple():
    # 3 unprotected units; target 1.0 removes all → reduced len 0.
    return context([unit("crit", "anchor"), unit("f1", "one"), unit("f2", "two")])


# --------------------------------------------------------------------------- #
# Correction A — inclusive expiry.
# --------------------------------------------------------------------------- #
def test_before_expiry_succeeds():
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=10.0),
                         target_reduction=0.5, evaluation_time=9.0)
    assert not r.fell_back
    assert r.equivalence_status is EquivalenceStatus.VERIFIED


def test_exact_expiry_instant_fails_closed():
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=10.0),
                         target_reduction=0.5, evaluation_time=10.0)
    assert r.fell_back
    assert reasons.ORACLE_EVALUATION_EXPIRED in r.reason_codes
    assert r.surviving_ids == r.original_ids


def test_after_expiry_fails_closed():
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=10.0),
                         target_reduction=0.5, evaluation_time=11.0)
    assert r.fell_back
    assert reasons.ORACLE_EVALUATION_EXPIRED in r.reason_codes


def test_valid_until_with_missing_evaluation_time_fails_closed():
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=10.0),
                         target_reduction=0.5, evaluation_time=None)
    assert r.fell_back
    assert reasons.ORACLE_EVALUATION_TIME_REQUIRED in r.reason_codes
    assert r.surviving_ids == r.original_ids


def test_expired_base_evaluation_returns_full_context():
    # ok_lens empty → base (len 4) expired.
    r = minimize_context(_ctx(), oracle=LenGatedOracle(ok_lens=()),
                         target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back and r.surviving_ids == r.original_ids
    assert reasons.ORACLE_EVALUATION_EXPIRED in r.reason_codes


def test_expired_reduced_evaluation_returns_full_context():
    # base (len 4) valid; any reduced context expired.
    r = minimize_context(_ctx(), oracle=LenGatedOracle(ok_lens={4}),
                         target_reduction=1.0, evaluation_time=1.0)
    assert r.fell_back and r.surviving_ids == r.original_ids
    assert reasons.ORACLE_EVALUATION_EXPIRED in r.reason_codes
    assert r.removed_ids == ()


def test_expired_restoration_evaluation_returns_full_context():
    # base (3) and reduced (0) valid, but the per-unit restoration evals (len 2) are
    # expired → every removed unit is treated as necessary → full context retained.
    r = minimize_context(
        _triple(),
        oracle=LenGatedOracle(key_members={"f1"}, ok_lens={3, 0}),
        target_reduction=1.0, evaluation_time=1.0,
    )
    assert r.surviving_ids == r.original_ids
    assert r.removed_ids == ()


def test_no_expired_path_ever_removes_a_unit():
    for oracle in (
        LenGatedOracle(ok_lens=()),
        LenGatedOracle(ok_lens={4}),
        LenGatedOracle(key_members={"f1"}, ok_lens={3, 0}),
    ):
        ctx = _triple() if oracle.ok_lens == {3, 0} else _ctx()
        r = minimize_context(ctx, oracle=oracle, target_reduction=1.0, evaluation_time=1.0)
        assert r.removed_ids == ()


def test_expiry_reason_codes_are_deterministic():
    a = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=10.0),
                         target_reduction=0.5, evaluation_time=10.0)
    b = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=10.0),
                         target_reduction=0.5, evaluation_time=10.0)
    assert a.reason_codes == b.reason_codes


# --------------------------------------------------------------------------- #
# Correction B — mandatory correlation binding.
# --------------------------------------------------------------------------- #
def test_matching_correlation_succeeds():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert not r.fell_back


def test_missing_correlation_fails_closed():
    r = minimize_context(_ctx(), oracle=MissingCorrelationOracle(),
                         target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back and r.surviving_ids == r.original_ids
    assert reasons.ORACLE_CORRELATION_MISSING in r.reason_codes


def test_mismatched_correlation_fails_closed():
    r = minimize_context(_ctx(), oracle=WrongCorrelationOracle(),
                         target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back
    assert reasons.ORACLE_CORRELATION_MISMATCH in r.reason_codes
    # missing and mismatch are NOT collapsed into one ambiguous code
    assert reasons.ORACLE_CORRELATION_MISSING not in r.reason_codes


def test_context_without_correlation_accepts_evaluation_without_correlation():
    ctx = Context(id="c", correlation_id=None, units=(
        ContextUnit(id="crit", text="deploy anchor", source_type="state_fact"),
        ContextUnit(id="fill", text="weekly filler", source_type="log_event"),
    ))
    r = minimize_context(ctx, oracle=NoCorrelationOracle(), target_reduction=1.0, evaluation_time=1.0)
    assert not r.fell_back


def test_reduced_context_evaluation_cannot_omit_correlation():
    # base (len 4) carries correlation; reduced omits it → fail closed.
    r = minimize_context(_ctx(), oracle=LenGatedOracle(ok_lens={4}, dimension="correlation"),
                         target_reduction=1.0, evaluation_time=1.0)
    assert r.fell_back and r.surviving_ids == r.original_ids
    assert reasons.ORACLE_CORRELATION_MISSING in r.reason_codes


def test_restoration_evaluation_cannot_change_correlation():
    # base (3) and reduced (0) carry correlation, restoration evals (len 2) omit it →
    # every removed unit is treated as necessary → full context retained.
    r = minimize_context(
        _triple(),
        oracle=LenGatedOracle(key_members={"f1"}, ok_lens={3, 0}, dimension="correlation"),
        target_reduction=1.0, evaluation_time=1.0,
    )
    assert r.surviving_ids == r.original_ids and r.removed_ids == ()


def test_correlation_reason_code_preserved_in_result():
    r = minimize_context(_ctx(), oracle=MissingCorrelationOracle(),
                         target_reduction=0.5, evaluation_time=1.0)
    assert r.reason_codes and r.reason_codes[-1] == reasons.ORACLE_CORRELATION_MISSING
