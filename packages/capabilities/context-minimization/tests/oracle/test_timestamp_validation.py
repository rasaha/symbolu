"""Correction A (v0.1.2) — strict timestamp value contract.

Caller ``evaluation_time`` is validated at the public boundary and raises
``InvalidRequestError`` (never reaching the oracle); oracle ``valid_until`` is
validated as oracle OUTPUT and fails closed with ``ORACLE_RESULT_MALFORMED``.
"""

from __future__ import annotations

import math

import pytest

from ugence_context_minimization import reasons
from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    EquivalenceStatus,
    InvalidRequestError,
    OracleEvaluation,
    minimize_context,
)

from support import ExpiryHorizonOracle, KeywordOracle, RecordingOracle, context, unit


def _ctx():
    return context([
        unit("crit", "deploy service to prod", source_type="state_fact"),
        unit("fill", "weekly sprint filler", source_type="log_event"),
    ])


# --------------------------------------------------------------------------- #
# Caller-controlled evaluation_time  (malformed -> InvalidRequestError)
# --------------------------------------------------------------------------- #
def test_finite_int_evaluation_time_accepted():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1)
    assert not r.fell_back


def test_finite_float_evaluation_time_accepted():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=1.5)
    assert not r.fell_back


def test_zero_evaluation_time_accepted():
    r = minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=0)
    assert not r.fell_back


@pytest.mark.parametrize("bad", [True, False, math.nan, math.inf, -math.inf, "tomorrow", object()])
def test_malformed_caller_evaluation_time_raises(bad):
    with pytest.raises(InvalidRequestError):
        minimize_context(_ctx(), oracle=KeywordOracle(), target_reduction=0.5, evaluation_time=bad)


def test_oracle_not_called_for_malformed_caller_time():
    rec = RecordingOracle(KeywordOracle())
    with pytest.raises(InvalidRequestError):
        minimize_context(_ctx(), oracle=rec, target_reduction=0.5, evaluation_time=math.nan)
    assert rec.evaluate_calls == 0  # nothing reached the oracle


# --------------------------------------------------------------------------- #
# Oracle-controlled valid_until  (malformed -> fail closed, ORACLE_RESULT_MALFORMED)
# --------------------------------------------------------------------------- #
def test_finite_int_valid_until_accepted():
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=100),
                         target_reduction=0.5, evaluation_time=1)
    assert not r.fell_back
    assert r.equivalence_status is EquivalenceStatus.VERIFIED


def test_finite_float_valid_until_accepted():
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=100.0),
                         target_reduction=0.5, evaluation_time=1)
    assert not r.fell_back


@pytest.mark.parametrize("bad", [True, False, math.nan, math.inf, -math.inf, "later", object()])
def test_malformed_valid_until_fails_closed(bad):
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=bad),
                         target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back
    assert r.surviving_ids == r.original_ids
    assert reasons.ORACLE_RESULT_MALFORMED in r.reason_codes


def test_malformed_valid_until_never_raises_typeerror():
    # An arbitrary object as valid_until must not reach a raw comparison.
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=object()),
                         target_reduction=0.5, evaluation_time=1.0)
    assert r.fell_back and reasons.ORACLE_RESULT_MALFORMED in r.reason_codes


def test_nan_valid_until_is_malformed_not_expired():
    # NaN would make >= comparisons silently False; it must be caught as malformed.
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=math.nan),
                         target_reduction=0.5, evaluation_time=1.0)
    assert reasons.ORACLE_RESULT_MALFORMED in r.reason_codes
    assert reasons.ORACLE_EVALUATION_EXPIRED not in r.reason_codes


# --------------------------------------------------------------------------- #
# Inclusive expiry preserved (v0.1.1) + deterministic validation ordering
# --------------------------------------------------------------------------- #
def test_before_exact_after_expiry():
    o = ExpiryHorizonOracle(valid_until=10.0)
    assert not minimize_context(_ctx(), oracle=o, target_reduction=0.5, evaluation_time=9.0).fell_back
    assert minimize_context(_ctx(), oracle=o, target_reduction=0.5, evaluation_time=10.0).fell_back
    assert minimize_context(_ctx(), oracle=o, target_reduction=0.5, evaluation_time=11.0).fell_back


def test_missing_evaluation_time_with_horizon_fails_closed():
    r = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=10.0),
                         target_reduction=0.5, evaluation_time=None)
    assert reasons.ORACLE_EVALUATION_TIME_REQUIRED in r.reason_codes


def _oracle_returning(**kw):
    defaults = dict(equivalence_key="k", oracle_id="o", contract_version="1.0")
    defaults.update(kw)

    class _O:
        def evaluate(self, ctx, *, evaluation_time=None):
            d = dict(defaults)
            if "correlation_id" not in d:
                d["correlation_id"] = ctx.correlation_id
            return OracleEvaluation(**d)
    return _O()


def test_validation_order_key_before_horizon():
    # non-string key AND malformed valid_until -> key checked first (MALFORMED).
    r = minimize_context(_ctx(), oracle=_oracle_returning(equivalence_key=None, valid_until=object()),
                         target_reduction=0.5, evaluation_time=1.0)
    assert reasons.ORACLE_RESULT_MALFORMED in r.reason_codes


def test_validation_order_correlation_before_horizon():
    # valid identity, missing correlation, malformed valid_until -> correlation first.
    r = minimize_context(_ctx(), oracle=_oracle_returning(correlation_id=None, valid_until=math.inf),
                         target_reduction=0.5, evaluation_time=1.0)
    assert reasons.ORACLE_CORRELATION_MISSING in r.reason_codes
    assert reasons.ORACLE_RESULT_MALFORMED not in r.reason_codes


def test_reason_codes_deterministic():
    a = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=math.nan),
                         target_reduction=0.5, evaluation_time=1.0)
    b = minimize_context(_ctx(), oracle=ExpiryHorizonOracle(valid_until=math.nan),
                         target_reduction=0.5, evaluation_time=1.0)
    assert a.reason_codes == b.reason_codes
