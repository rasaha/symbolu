"""Correction B (v0.1.2) — strict canonical fingerprint serialization.

Canonical JSON rejects non-finite numbers (`allow_nan=False`), so no digest can
ever contain `NaN` / `Infinity`. The outcome digest stays byte-compatible with a
frozen v0.1.1 fixture; run and outcome digests stay distinct.
"""

from __future__ import annotations

import math

import pytest

from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    minimize_context,
    structural_minimize,
)
from ugence_context_minimization.fingerprint import _canonical_json, run_fingerprint
from ugence_context_minimization.policy import DEFAULT_POLICY

from support import KeywordOracle, context, unit


# --------------------------------------------------------------------------- #
# allow_nan=False on the canonical serializer
# --------------------------------------------------------------------------- #
def test_canonical_json_rejects_nan():
    with pytest.raises(ValueError):
        _canonical_json({"x": math.nan})


def test_canonical_json_rejects_infinity():
    with pytest.raises(ValueError):
        _canonical_json({"x": math.inf})
    with pytest.raises(ValueError):
        _canonical_json({"x": -math.inf})


def test_canonical_json_is_sorted_and_compact():
    assert _canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_run_fingerprint_helper_rejects_nonfinite_defensively():
    # A hostile policy whose fingerprint payload smuggles a non-finite number must
    # not yield an unstable digest — the serializer raises deterministically.
    class BadPolicy:
        version = "bad"

        def fingerprint(self):
            return math.inf  # not a str; becomes a non-finite number in the payload

    ctx = context([unit("a", "x")])
    with pytest.raises(ValueError):
        run_fingerprint(
            ctx, mode="ORACLE_VERIFIED", requested_reduction=0.0, requested_token_budget=None,
            evaluation_time=1.0, policy=BadPolicy(), token_counter=None, base_eval=None,
            surviving_ids=["a"], removed_structural=[], removed_extractive=[], restored_ids=[],
            protected_ids=[], original_tokens=1, resulting_tokens=1,
            equivalence_status="VERIFIED", fell_back=False, reason_codes=(),
        )


# --------------------------------------------------------------------------- #
# Determinism + byte-compatibility of the outcome digest
# --------------------------------------------------------------------------- #
_FROZEN_STRUCT_OUTCOME = "sha256:5115c884409533f070532508fce2f6fc049c136ea387c979dcd98e436ba1011a"


def _frozen_ctx():
    return Context(id="fx", correlation_id=None, units=(
        ContextUnit(id="a", text="same", source_type="state_fact"),
        ContextUnit(id="b", text="same", source_type="state_fact"),
        ContextUnit(id="c", text="unique", source_type="state_fact"),
    ))


def test_outcome_fingerprint_byte_compatible_with_frozen_v011_fixture():
    r = structural_minimize(_frozen_ctx(), protected_ids=["a"])
    assert r.outcome_fingerprint == _FROZEN_STRUCT_OUTCOME
    assert r.fingerprint == _FROZEN_STRUCT_OUTCOME  # deprecated alias unchanged


def test_identical_valid_runs_produce_identical_fingerprints():
    ctx = context([unit("crit", "deploy"), unit("f", "weekly filler")])
    a = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    b = minimize_context(ctx, oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.0)
    assert a.run_fingerprint == b.run_fingerprint
    assert a.outcome_fingerprint == b.outcome_fingerprint


def test_run_and_outcome_fingerprints_distinct():
    r = structural_minimize(_frozen_ctx())
    assert r.run_fingerprint != r.outcome_fingerprint
