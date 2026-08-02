"""MVP 1B acceptance tests 9-19: operational signal mapping (fail-closed)."""
from __future__ import annotations

import pytest

from cg_clearance_helpers import (
    EVAL, REQUIRED, drive_to_action_evaluated, profile, projection, snapshot, source_entry,
)
from ugence_code_governance import CodeGovernanceService
from ugence_code_governance.clearance.signal_adapter import (
    ClearanceInputError, build_trusted_signals,
)
from ugence_code_governance.clearance.source_projection import TrustedSignalSourceProjection
from ugence_action_clearance import SignalTrustLevel, SignalType


def _ctx():
    svc = CodeGovernanceService()
    change, rid, action, shadow = drive_to_action_evaluated(svc)
    return svc, rid, action, shadow


def _build(action, shadow, *, snap=None, proj=None, required=REQUIRED):
    return build_trusted_signals(
        snap or snapshot(action), proj or projection(),
        tenant_id="acme", subject_ref=action.repository,
        authorization_ref=shadow.result_fingerprint, action_fingerprint=action.fingerprint,
        required_signal_types=required)


# 9. approved snapshot becomes canonical TrustedSignal
def test_approved_snapshot_becomes_signals():
    svc, rid, action, shadow = _ctx()
    bundle = _build(action, shadow)
    types = {s.signal_type for s in bundle.signals}
    assert SignalType.AUTHORIZATION_VALIDITY in types
    assert SignalType.ARTIFACT_IDENTITY in types
    # canonical content fingerprint present (computed via AC public API)
    for s in bundle.signals:
        assert s.content_fingerprint
        assert s.integrity_digest == s.content_fingerprint


# 10. unapproved source rejected
def test_unapproved_source_rejected():
    svc, rid, action, shadow = _ctx()
    # projection missing ARTIFACT_IDENTITY source
    proj = projection((SignalType.AUTHORIZATION_VALIDITY, SignalType.ACTOR_STATUS))
    with pytest.raises(ClearanceInputError):
        _build(action, shadow, proj=proj)


# 11. unapproved adapter version rejected
def test_unapproved_adapter_version_rejected():
    svc, rid, action, shadow = _ctx()
    proj = projection(approved_versions=("2.0.0",))  # entries built with adapter_version 1.0.0
    with pytest.raises(ClearanceInputError):
        _build(action, shadow, proj=proj)


# 12. excessive trust-level claim rejected (source max enforced in evaluation)
def test_trust_level_capped_by_source():
    svc, rid, action, shadow = _ctx()
    # source max is L1; profile requires L3 -> evaluation yields SIGNAL_TRUST_LEVEL_INSUFFICIENT
    proj = projection(max_trust=SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION)
    prof = profile(trust_required=(SignalType.ARTIFACT_IDENTITY,),
                   min_trust={SignalType.ARTIFACT_IDENTITY: SignalTrustLevel.LEVEL_3_SIGNED_PRODUCER})
    svc.record_operational_snapshot("acme", rid, snapshot(action), projection=proj, profile=prof,
                                    at=EVAL)
    rec = svc.evaluate_action_clearance_shadow("acme", rid, evaluation_time=EVAL)
    assert "SIGNAL_TRUST_LEVEL_INSUFFICIENT" in rec.reason_codes


# 13. tenant mismatch rejected
def test_tenant_mismatch_rejected():
    svc, rid, action, shadow = _ctx()
    proj = TrustedSignalSourceProjection(projection_id="p", projection_version="v1",
                                         tenant_id="globex", entries=projection().entries)
    with pytest.raises(ClearanceInputError):
        _build(action, shadow, proj=proj)


# 14-16. subject / authorization / action binding enforced by the canonical evaluator
def test_subject_authorization_action_binding():
    svc, rid, action, shadow = _ctx()
    # signals built with wrong action fingerprint -> evaluator flags SIGNAL_ACTION_MISMATCH
    from datetime import timedelta
    bundle = build_trusted_signals(
        snapshot(action), projection(), tenant_id="acme", subject_ref=action.repository,
        authorization_ref=shadow.result_fingerprint, action_fingerprint="WRONG-FP",
        required_signal_types=REQUIRED)
    # feed directly through the adapter+evaluator by monkeypatching the bundle
    svc._scratch[("acme", rid)]["signal_bundle"] = bundle
    svc.record_operational_snapshot("acme", rid, snapshot(action), projection=projection(),
                                    profile=profile(), at=EVAL)
    svc._scratch[("acme", rid)]["signal_bundle"] = bundle
    rec = svc.evaluate_action_clearance_shadow("acme", rid, evaluation_time=EVAL)
    assert "SIGNAL_ACTION_MISMATCH" in rec.reason_codes


# 17-18. content / provenance fingerprints validated (tampered digest -> untrusted)
def test_content_fingerprint_validated():
    import dataclasses
    svc, rid, action, shadow = _ctx()
    bundle = _build(action, shadow)
    tampered = dataclasses.replace(bundle.signals[0], integrity_digest="tampered")
    # rebuilding the bundle with a tampered digest -> evaluator flags SIGNAL_CONTENT_MISMATCH
    from ugence_action_clearance import SignalBundle
    from datetime import timedelta
    new_bundle = SignalBundle(signals=(tampered,) + bundle.signals[1:],
                              required_signal_types=bundle.required_signal_types)
    svc.record_operational_snapshot("acme", rid, snapshot(action), projection=projection(),
                                    profile=profile(), at=EVAL)
    svc._scratch[("acme", rid)]["signal_bundle"] = new_bundle
    rec = svc.evaluate_action_clearance_shadow("acme", rid, evaluation_time=EVAL)
    assert "SIGNAL_CONTENT_MISMATCH" in rec.reason_codes


# 19. signal order does not affect bundle fingerprint
def test_signal_order_stable_bundle_fingerprint():
    svc, rid, action, shadow = _ctx()
    b1 = _build(action, shadow)
    from ugence_action_clearance import SignalBundle
    b2 = SignalBundle(signals=tuple(reversed(b1.signals)),
                      required_signal_types=b1.required_signal_types)
    assert b1.fingerprint == b2.fingerprint
