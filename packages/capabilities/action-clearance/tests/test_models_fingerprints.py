"""Acceptance tests 1-13: models, normalization, and fingerprinting."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from ac_helpers import (
    ACTFP, T0, action, authorization, happy_signals, policy, provenance,
    request, signal,
)
from ugence_action_clearance import (
    ClearanceStatus, SignalStatus, SignalType, TrustedSignal, ValidationError,
)
from ugence_action_clearance.normalization import canonical_json, normalize_value
from ugence_action_clearance.models.signals import SignalBundle


# 1. immutable request/result/signal models
def test_models_are_frozen(evaluator):
    s = signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.signal_id = "x"  # type: ignore
    r = evaluator.evaluate(request(happy_signals()), policy())
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.status = ClearanceStatus.BLOCK  # type: ignore


# 2. canonical serialization stable
def test_canonical_serialization_stable():
    a = {"b": 1, "a": 2, "c": {"y": 1, "x": 2}}
    b = {"c": {"x": 2, "y": 1}, "a": 2, "b": 1}
    assert canonical_json(a) == canonical_json(b)


# 3. unsupported normalized value rejected
def test_unsupported_value_rejected():
    with pytest.raises(ValidationError):
        normalize_value(object())
    with pytest.raises(ValidationError):
        normalize_value(float("nan"))


# 4. enum ordering stable / encoded by value
def test_enum_encoded_by_value():
    assert canonical_json(SignalType.ACTOR_STATUS) == '"ACTOR_STATUS"'


# 5. mapping ordering does not affect fingerprint
def test_mapping_order_irrelevant(evaluator):
    r1 = evaluator.evaluate(request(happy_signals()), policy())
    r2 = evaluator.evaluate(request(list(reversed(happy_signals()))), policy())
    assert r1.result_fingerprint == r2.result_fingerprint


# 6. timestamp normalization stable
def test_timestamp_normalization():
    from ugence_action_clearance.normalization import normalize_timestamp
    utc = datetime(2026, 1, 1, tzinfo=timezone.utc)
    other = datetime(2026, 1, 1, 5, tzinfo=timezone(timedelta(hours=5)))
    assert normalize_timestamp(utc) == normalize_timestamp(other)
    with pytest.raises(ValidationError):
        normalize_timestamp(datetime(2026, 1, 1))  # naive


# 7. identical signal -> identical content fingerprint
def test_identical_signal_same_content_fp():
    a = signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"})
    b = signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"})
    assert a.content_fingerprint == b.content_fingerprint


# 8. provenance change -> provenance fingerprint changes
def test_provenance_fingerprint_changes():
    from ugence_action_clearance import SignalTrustLevel
    p1 = provenance(trust=SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION)
    p2 = provenance(trust=SignalTrustLevel.LEVEL_3_SIGNED_PRODUCER)
    assert p1.fingerprint != p2.fingerprint


# 9. signal order does not change bundle fingerprint
def test_bundle_fingerprint_order_independent():
    sigs = happy_signals()
    b1 = SignalBundle(tuple(sigs), (SignalType.ACTOR_STATUS,))
    b2 = SignalBundle(tuple(reversed(sigs)), (SignalType.ACTOR_STATUS,))
    assert b1.fingerprint == b2.fingerprint


# 10. signal content change changes bundle fingerprint
def test_bundle_fingerprint_content_sensitive():
    b1 = SignalBundle(tuple(happy_signals()), (SignalType.ACTOR_STATUS,))
    changed = [signal(SignalType.ACTOR_STATUS, {"state": "DISABLED"}),
               signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    b2 = SignalBundle(tuple(changed), (SignalType.ACTOR_STATUS,))
    assert b1.fingerprint != b2.fingerprint


# 11. identical request -> identical request fingerprint
def test_identical_request_same_fingerprint():
    assert request(happy_signals()).fingerprint == request(happy_signals()).fingerprint


# 12. identical result -> identical result fingerprint
def test_identical_result_same_fingerprint(evaluator):
    r1 = evaluator.evaluate(request(happy_signals()), policy())
    r2 = evaluator.evaluate(request(happy_signals()), policy())
    assert r1.result_fingerprint == r2.result_fingerprint
    assert r1.result_id == r2.result_id
    assert r1.result_id.startswith("acr_")


# 13. storage metadata does not affect evaluator fingerprint
def test_receipt_metadata_excluded_from_fingerprint(evaluator):
    from ugence_action_clearance import ClearanceReceiptBody
    r = evaluator.evaluate(request(happy_signals()), policy())
    body = ClearanceReceiptBody.from_result(r)
    # the receipt body's content address equals the result fingerprint (no storage metadata)
    assert body.result_fingerprint == r.result_fingerprint
    assert body.receipt_id == r.result_id


# duplicate signal id -> ValidationError (malformed, not an outcome)
def test_duplicate_signal_id_rejected():
    dup = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}, signal_id="same"),
           signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP}, signal_id="same")]
    with pytest.raises(ValidationError):
        SignalBundle(tuple(dup), ())
