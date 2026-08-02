"""Acceptance tests 14-37: authority boundary and signal evaluation."""
from __future__ import annotations

from datetime import timedelta

import pytest

from ac_helpers import (
    ACTFP, AUTHZ, T0, TARGET, action, authorization, happy_signals, policy,
    provenance, request, signal, ts,
)
from ugence_action_clearance import (
    ClearanceStatus, ConsumptionStatus, SignalStatus, SignalTrustLevel,
    SignalType,
)


def _st(evaluator, signals, **kw):
    pol = kw.pop("pol", policy())
    return evaluator.evaluate(request(signals, **kw), pol).status


# --- Authority boundary (14-21) -------------------------------------------
# 14. missing authorization -> BLOCK  (ineligible outcome / empty auth)
def test_missing_authorization_blocks(evaluator):
    r = evaluator.evaluate(
        request(happy_signals(), auth=authorization(outcome="DENIED")), policy())
    assert r.status is ClearanceStatus.BLOCK
    assert "AUTHORIZATION_NOT_ELIGIBLE" in r.reason_codes


# 15. upstream denial cannot become CLEAR
def test_denial_never_clear(evaluator):
    for outcome in ("DENIED", "INDETERMINATE", "EXPIRED"):
        r = evaluator.evaluate(request(happy_signals(), auth=authorization(outcome=outcome)), policy())
        assert r.status is not ClearanceStatus.CLEAR


# 16. action mismatch -> BLOCK
def test_action_mismatch_blocks(evaluator):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": "DIFFERENT"})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is ClearanceStatus.BLOCK
    assert "ACTION_FINGERPRINT_MISMATCH" in r.reason_codes


# 17. target mismatch -> BLOCK
def test_target_mismatch_blocks(evaluator):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP, "target_ref": "other-target"})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is ClearanceStatus.BLOCK
    assert "TARGET_MISMATCH" in r.reason_codes


# 18. tenant mismatch -> BLOCK
def test_tenant_mismatch_blocks(evaluator):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}, tenant="globex"),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is ClearanceStatus.BLOCK
    assert "TENANT_MISMATCH" in r.reason_codes


# 19. authorization expired -> BLOCK
def test_authorization_expired_blocks(evaluator):
    auth = authorization(expires=ts(hours=-1), issued=ts(hours=-3))
    r = evaluator.evaluate(request(happy_signals(), auth=auth), policy())
    assert r.status is ClearanceStatus.BLOCK
    assert "AUTHORIZATION_EXPIRED" in r.reason_codes


# 20. authorization stale (current-state signal says invalid) -> not CLEAR
def test_authorization_stale_signal(evaluator):
    sigs = happy_signals() + [signal(SignalType.AUTHORIZATION_VALIDITY, {"state": "STALE"})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is not ClearanceStatus.CLEAR
    assert "AUTHORIZATION_STALE" in r.reason_codes


# 21. clearance cannot extend authorization expiry
def test_valid_until_never_exceeds_authorization(evaluator):
    auth = authorization(expires=ts(minutes=30))
    r = evaluator.evaluate(request(happy_signals(), auth=auth), policy())
    assert r.valid_until <= auth.authorization_expires_at


# --- Signals (22-37) ------------------------------------------------------
# 22. all mandatory valid signals -> eligible for CLEAR
def test_all_valid_signals_clear(evaluator):
    r = evaluator.evaluate(request(happy_signals()), policy())
    assert r.status is ClearanceStatus.CLEAR


# 23. missing mandatory signal -> not CLEAR
def test_missing_mandatory_not_clear(evaluator):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"})]  # no ARTIFACT_IDENTITY
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is not ClearanceStatus.CLEAR
    assert "SIGNAL_MISSING" in r.reason_codes


# 24. stale mandatory signal -> not CLEAR
def test_stale_mandatory_not_clear(evaluator):
    old = signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP}, captured_at=ts(hours=-5))
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}), old]
    pol = policy(maximum_signal_age_s=3600)
    r = evaluator.evaluate(request(sigs), pol)
    assert r.status is not ClearanceStatus.CLEAR
    assert "SIGNAL_STALE" in r.reason_codes


# 25. expired mandatory signal -> not CLEAR
def test_expired_mandatory_not_clear(evaluator):
    expired = signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP}, valid_until=ts(hours=-1))
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}), expired]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is not ClearanceStatus.CLEAR
    assert "SIGNAL_EXPIRED" in r.reason_codes


# 26 & 27. untrusted / insufficient-trust mandatory signal -> not CLEAR
def test_untrusted_and_insufficient_trust(evaluator):
    pol = policy(trust_required_signal_types=(SignalType.ARTIFACT_IDENTITY,),
                 minimum_signal_trust_levels={"ARTIFACT_IDENTITY": SignalTrustLevel.LEVEL_3_SIGNED_PRODUCER})
    # missing provenance -> untrusted
    art = signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})
    r = evaluator.evaluate(request([signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}), art]), pol)
    assert r.status is not ClearanceStatus.CLEAR
    assert "SIGNAL_PROVENANCE_MISSING" in r.reason_codes
    # provenance present but too low a level, with a valid integrity digest
    art2 = signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP},
                  provenance=provenance(trust=SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION))
    art2 = _with_matching_digest(art2)
    r2 = evaluator.evaluate(request([signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}), art2]), pol)
    assert "SIGNAL_TRUST_LEVEL_INSUFFICIENT" in r2.reason_codes


def _with_matching_digest(sig):
    import dataclasses
    return dataclasses.replace(sig, integrity_digest=sig.content_fingerprint)


# 28. unknown source (status UNKNOWN) -> not CLEAR
def test_unknown_source_not_clear(evaluator):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP}, status=SignalStatus.UNKNOWN)]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is not ClearanceStatus.CLEAR
    assert "SIGNAL_MISSING" in r.reason_codes


# 29. adapter-version mismatch -> not CLEAR
def test_adapter_version_unapproved(evaluator):
    pol = policy(trust_required_signal_types=(SignalType.ARTIFACT_IDENTITY,),
                 approved_adapter_versions={"adapter-a": ("2.0.0",)})
    art = signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP},
                 provenance=provenance(adapter_version="1.0.0"))
    art = _with_matching_digest(art)
    r = evaluator.evaluate(request([signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}), art]), pol)
    assert "SIGNAL_ADAPTER_VERSION_UNAPPROVED" in r.reason_codes


# 30. digest mismatch -> not CLEAR
def test_digest_mismatch_not_clear(evaluator):
    import dataclasses
    art = signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})
    tampered = dataclasses.replace(art, integrity_digest="not-the-real-digest")
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}), tampered]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is ClearanceStatus.BLOCK
    assert "SIGNAL_CONTENT_MISMATCH" in r.reason_codes


# 31. conflicting signals -> ESCALATE (or BLOCK by policy)
def test_conflicting_signals_escalate(evaluator):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}, signal_id="a1"),
            signal(SignalType.ACTOR_STATUS, {"state": "DISABLED"}, signal_id="a2"),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    r = evaluator.evaluate(request(sigs), policy())
    assert "SIGNAL_CONFLICT" in r.reason_codes
    assert r.status in (ClearanceStatus.ESCALATE, ClearanceStatus.BLOCK)


# 32. active freeze -> HOLD
def test_active_freeze_hold(evaluator):
    sigs = happy_signals() + [signal(SignalType.CHANGE_FREEZE, {"active": True})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is ClearanceStatus.HOLD
    assert "ACTIVE_CHANGE_FREEZE" in r.reason_codes


# 33. active incident -> HOLD or ESCALATE per policy
def test_active_incident_policy(evaluator):
    sigs = happy_signals() + [signal(SignalType.ACTIVE_INCIDENT, {"active": True})]
    r_hold = evaluator.evaluate(request(sigs), policy())
    assert r_hold.status is ClearanceStatus.HOLD
    r_esc = evaluator.evaluate(request(sigs), policy(incident_response=ClearanceStatus.ESCALATE))
    assert r_esc.status is ClearanceStatus.ESCALATE


# 34. target unavailable -> HOLD
def test_target_unavailable_hold(evaluator):
    sigs = happy_signals() + [signal(SignalType.TARGET_AVAILABILITY, {"available": False})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is ClearanceStatus.HOLD
    assert "TARGET_UNAVAILABLE" in r.reason_codes


# 35. actor invalid -> BLOCK
def test_actor_invalid_block(evaluator):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "DISABLED"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is ClearanceStatus.BLOCK
    assert "ACTOR_INVALID" in r.reason_codes


# 36. prior consumption CONSUMED -> BLOCK
def test_prior_consumption_consumed_block(evaluator):
    sigs = happy_signals() + [signal(SignalType.PRIOR_CONSUMPTION, {"state": ConsumptionStatus.CONSUMED.value})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is ClearanceStatus.BLOCK
    assert "ALREADY_CONSUMED" in r.reason_codes


# 37. prior consumption UNKNOWN -> fail closed (HOLD)
def test_prior_consumption_unknown_fail_closed(evaluator):
    sigs = happy_signals() + [signal(SignalType.PRIOR_CONSUMPTION, {"state": ConsumptionStatus.UNKNOWN.value})]
    r = evaluator.evaluate(request(sigs), policy())
    assert r.status is not ClearanceStatus.CLEAR
    assert "CONSUMPTION_STATUS_UNKNOWN" in r.reason_codes


def test_prior_consumption_reserved_policy(evaluator):
    sigs = happy_signals() + [signal(SignalType.PRIOR_CONSUMPTION, {"state": ConsumptionStatus.RESERVED.value})]
    r = evaluator.evaluate(request(sigs), policy(consumption_reserved_response=ClearanceStatus.BLOCK))
    assert r.status is ClearanceStatus.BLOCK
    assert "CONSUMPTION_RESERVED" in r.reason_codes
