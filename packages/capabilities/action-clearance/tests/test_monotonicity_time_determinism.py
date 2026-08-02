"""Acceptance tests 38-56: monotonicity, time, and determinism."""
from __future__ import annotations

from datetime import timedelta

import pytest

from ac_helpers import (
    ACTFP, T0, action, authorization, happy_signals, policy, request, signal, ts,
)
from ugence_action_clearance import (
    ClearanceStatus, ConstraintKind, EffectiveConstraint, SignalType,
)


def _auth_with(structured, constraints=()):
    return authorization(structured=structured, constraints=constraints)


# 38-41. effective sets/ranges never expand
def test_effective_max_never_expands(evaluator):
    auth = _auth_with((EffectiveConstraint("parallelism", ConstraintKind.MAX, 5),))
    pol = policy(clearance_constraints=(EffectiveConstraint("parallelism", ConstraintKind.MAX, 2),))
    r = evaluator.evaluate(request(happy_signals(), auth=auth), pol)
    assert "parallelism:MAX=2" in r.effective_constraints  # narrowed to smaller
    assert r.status is ClearanceStatus.CLEAR


def test_effective_operation_set_never_expands(evaluator):
    auth = _auth_with((EffectiveConstraint("operations", ConstraintKind.ALLOWED_SET, ("read", "apply")),))
    pol = policy(clearance_constraints=(EffectiveConstraint("operations", ConstraintKind.ALLOWED_SET, ("apply",)),))
    r = evaluator.evaluate(request(happy_signals(), auth=auth), pol)
    assert any(c.startswith("operations:ALLOWED_SET=") and "apply" in c for c in r.effective_constraints)
    assert r.status is ClearanceStatus.CLEAR


def test_parameter_range_never_expands_conflict(evaluator):
    # clearance tries to RAISE the ceiling -> conflict (would broaden)
    auth = _auth_with((EffectiveConstraint("amount", ConstraintKind.MAX, 100),))
    pol = policy(clearance_constraints=(EffectiveConstraint("amount", ConstraintKind.MAX, 200),))
    r = evaluator.evaluate(request(happy_signals(), auth=auth), pol)
    assert "CONSTRAINT_CONFLICT" in r.reason_codes
    assert r.status is ClearanceStatus.ESCALATE


def test_time_window_never_expands(evaluator):
    auth = _auth_with((EffectiveConstraint("window_end", ConstraintKind.TIME_WINDOW_END, 1000),))
    pol = policy(clearance_constraints=(EffectiveConstraint("window_end", ConstraintKind.TIME_WINDOW_END, 500),))
    r = evaluator.evaluate(request(happy_signals(), auth=auth), pol)
    assert "window_end:TIME_WINDOW_END=500" in r.effective_constraints


# 42. upstream obligation never removed
def test_upstream_obligation_preserved(evaluator):
    auth = authorization(obligations=("REQUIRE_AUDIT_LOG", "REQUIRE_TWO_PERSON"))
    pol = policy(added_obligations=("REQUIRE_REVALIDATION_AT_DISPATCH",))
    r = evaluator.evaluate(request(happy_signals(), auth=auth), pol)
    assert set(auth.authorization_obligations) <= set(r.obligations)
    assert "REQUIRE_REVALIDATION_AT_DISPATCH" in r.obligations


# 43. unsupported constraint interpretation fails closed
def test_unsupported_constraint_fails_closed(evaluator):
    auth = _auth_with((EffectiveConstraint("dim", ConstraintKind.MAX, 5),))
    pol = policy(clearance_constraints=(EffectiveConstraint("dim", ConstraintKind.ALLOWED_SET, ("x",)),))
    r = evaluator.evaluate(request(happy_signals(), auth=auth), pol)
    assert "CONSTRAINT_INTERPRETATION_UNSUPPORTED" in r.reason_codes
    assert r.status is ClearanceStatus.ESCALATE


# 44. conflict produces deterministic reason
def test_conflict_deterministic(evaluator):
    auth = _auth_with((EffectiveConstraint("amount", ConstraintKind.MAX, 100),))
    pol = policy(clearance_constraints=(EffectiveConstraint("amount", ConstraintKind.MAX, 200),))
    r1 = evaluator.evaluate(request(happy_signals(), auth=auth), pol)
    r2 = evaluator.evaluate(request(happy_signals(), auth=auth), pol)
    assert r1.reason_codes == r2.reason_codes
    assert r1.result_fingerprint == r2.result_fingerprint


# 45. caller-supplied time used
def test_caller_supplied_time_used(evaluator):
    et = ts(minutes=15)
    r = evaluator.evaluate(request(happy_signals(), evaluation_time=et), policy())
    assert r.evaluated_at == et


# 46. no system-clock dependency
def test_no_system_clock_in_core():
    import ugence_action_clearance.evaluation as ev
    import ugence_action_clearance.models.result as res
    import inspect
    for mod in (ev, res):
        src = inspect.getsource(mod)
        assert "datetime.now(" not in src
        assert "time.time(" not in src
        assert ".utcnow(" not in src


# 47. valid-until bounded by authorization
def test_valid_until_bounded_by_authorization(evaluator):
    auth = authorization(expires=ts(minutes=10))
    r = evaluator.evaluate(request(happy_signals(), auth=auth), policy())
    assert r.valid_until <= auth.authorization_expires_at


# 48. valid-until bounded by earliest mandatory signal
def test_valid_until_bounded_by_signal(evaluator):
    early = ts(minutes=5)
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}, valid_until=early),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.valid_until <= early


# 49. valid-until bounded by policy maximum
def test_valid_until_bounded_by_policy_max(evaluator):
    r = evaluator.evaluate(request(happy_signals()), policy(maximum_clearance_lifetime_s=60))
    assert r.valid_until <= T0 + timedelta(seconds=60)


# 50. exact expiry boundary is non-clear
def test_exact_expiry_boundary_non_clear(evaluator):
    auth = authorization(expires=T0)  # expires_at == evaluation_time
    r = evaluator.evaluate(request(happy_signals(), auth=auth), policy())
    assert r.status is not ClearanceStatus.CLEAR
    assert "AUTHORIZATION_EXPIRED" in r.reason_codes


# 51-52. repeated evaluation byte-equivalent + identical fingerprint
def test_repeated_evaluation_identical(evaluator):
    r1 = evaluator.evaluate(request(happy_signals()), policy())
    r2 = evaluator.evaluate(request(happy_signals()), policy())
    assert r1.result_fingerprint == r2.result_fingerprint
    assert r1.reason_codes == r2.reason_codes
    assert r1.effective_constraints == r2.effective_constraints
    assert r1.obligations == r2.obligations


# 53-55. reason/obligation/constraint ordering stable
def test_ordering_stable(evaluator):
    auth = authorization(obligations=("Z_OB", "A_OB"),
                         structured=(EffectiveConstraint("d", ConstraintKind.MAX, 9),))
    sigs = happy_signals() + [signal(SignalType.CHANGE_FREEZE, {"active": True}),
                              signal(SignalType.TARGET_AVAILABILITY, {"available": False})]
    r = evaluator.evaluate(request(sigs, auth=auth), policy())
    assert list(r.reason_codes) == sorted(r.reason_codes)
    assert list(r.obligations) == sorted(r.obligations)
    assert list(r.effective_constraints) == sorted(r.effective_constraints)


# 56. no random/time/network dependencies
def test_no_random_time_network():
    import ugence_action_clearance.evaluation as ev
    import inspect
    src = inspect.getsource(ev)
    for banned in ("import random", "random.", "urllib", "socket", "requests", "os.environ"):
        assert banned not in src
