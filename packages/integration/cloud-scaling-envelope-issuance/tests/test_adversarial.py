"""Attacks the composition must refuse, and capabilities it must not have."""

from __future__ import annotations

import copy
import inspect
from dataclasses import fields
from datetime import timedelta

import pytest

from risk_authority.api import VERIFIED, EnvelopeIssuanceRefusal as R
from ugence_cloud_scaling_authorization_contracts import CapacityAuthorizationCandidate
from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityVerifier
from ugence_cloud_scaling_producer_attestation import ProducerAttestationVerifier

from _issuance_fixtures import (
    EVALUATION_INSTANT,
    ISSUANCE_INSTANT,
    UNTRUSTED_PRODUCER_SEED,
    Clock,
    build_world,
    held_reference_seam,
    issue_request,
    mint_attestation,
    policy_verifier_for,
)
from _policy_fixtures import bounds_authority, revoke

from ugence_cloud_scaling_envelope_issuance import (
    BINDING_KIND_AUTHORIZATION_CANDIDATE,
    BINDING_KIND_POLICY_AUTHENTICITY,
    BINDING_KIND_PRODUCER_ATTESTATION,
    ArtifactBindingStatus as S,
    CloudScalingEnvelopeIssuance,
    CloudScalingEnvelopeIssuanceRequest,
    EnvelopeIssuanceExactTypeError,
)


def _refused(world, request=None, **kw):
    out = world.issuance(**kw).issue(request or issue_request(world))
    assert out.issued is False and out.envelope is None and out.grants_authority is False
    assert world.app.envelopes.get(world.candidate.tenant_id, "rae_1") is None
    return out


# --------------------------------------------------------------------------- #
# Producer authenticity (5B-0A) gates issuance
# --------------------------------------------------------------------------- #
def test_an_attestation_under_an_untrusted_key_refuses_issuance(world):
    forged = mint_attestation(world.candidate, seed=UNTRUSTED_PRODUCER_SEED)
    out = _refused(world, issue_request(world, producer_attestation=forged))
    assert out.refusal is R.VERIFICATION_NOT_VERIFIED
    assert out.report.status_of(BINDING_KIND_PRODUCER_ATTESTATION) == S.PRODUCER_ATTESTATION_REFUSED
    assert out.report.producer_outcome not in (None, VERIFIED)
    assert BINDING_KIND_PRODUCER_ATTESTATION in out.detail


def test_an_attestation_for_another_recommendation_refuses_issuance(world):
    other = mint_attestation(world.candidate, recommendation_digest="sha256:" + "a" * 64)
    out = _refused(world, issue_request(world, producer_attestation=other))
    assert out.refusal is R.VERIFICATION_NOT_VERIFIED
    assert out.report.status_of(BINDING_KIND_PRODUCER_ATTESTATION) == S.PRODUCER_ATTESTATION_REFUSED


# --------------------------------------------------------------------------- #
# Policy authenticity (5B-0B) gates issuance
# --------------------------------------------------------------------------- #
def test_a_revoked_policy_refuses_issuance(world):
    revoke(world.authority, world.record, revoked_at=EVALUATION_INSTANT)
    out = _refused(world)
    assert out.refusal is R.VERIFICATION_NOT_VERIFIED
    assert out.report.status_of(BINDING_KIND_POLICY_AUTHENTICITY) == S.POLICY_AUTHENTICITY_REFUSED
    assert out.report.policy_outcome not in (None, VERIFIED)


def test_a_policy_unknown_to_the_authority_refuses_issuance(world):
    out = _refused(world, policy_verifier=policy_verifier_for(bounds_authority()))
    assert out.refusal is R.VERIFICATION_NOT_VERIFIED
    assert out.report.status_of(BINDING_KIND_POLICY_AUTHENTICITY) == S.POLICY_AUTHENTICITY_REFUSED


def test_the_caller_cannot_point_the_verifier_at_another_policy(world):
    """The coordinate is read off the candidate; the request has no field for one."""

    assert "coordinate" not in {f.name for f in fields(CloudScalingEnvelopeIssuanceRequest)}
    assert "policy" not in " ".join(f.name for f in fields(CloudScalingEnvelopeIssuanceRequest))


# --------------------------------------------------------------------------- #
# Time: one instant, the seam's, and nothing the caller chose
# --------------------------------------------------------------------------- #
def test_an_instant_outside_the_candidate_window_refuses_issuance(world):
    world.clock.at = EVALUATION_INSTANT + timedelta(minutes=10)  # recommendation expired 00:08:10
    out = _refused(world)
    assert out.refusal is R.VERIFICATION_NOT_VERIFIED
    assert out.report.as_of == world.clock.at
    assert out.report.status_of(BINDING_KIND_POLICY_AUTHENTICITY) == S.POLICY_AUTHENTICITY_REFUSED


def test_an_expired_decision_refuses_before_any_verifier_runs(world, monkeypatch):
    world.clock.at = EVALUATION_INSTANT + timedelta(hours=2)
    calls = []
    original = ProducerAttestationVerifier.verify
    monkeypatch.setattr(ProducerAttestationVerifier, "verify",
                        lambda self, **kw: calls.append(kw) or original(self, **kw))
    out = _refused(world)
    assert out.refusal is R.DECISION_EXPIRED
    assert out.report is None and calls == []


def test_a_verified_artifact_recorded_at_another_instant_is_refused(world, monkeypatch):
    original = ProducerAttestationVerifier.verify

    def skewed(self, *, candidate, attestation, as_of):
        return original(self, candidate=candidate, attestation=attestation,
                        as_of=as_of - timedelta(seconds=1))

    monkeypatch.setattr(ProducerAttestationVerifier, "verify", skewed)
    out = _refused(world)
    assert out.refusal is R.VERIFICATION_NOT_VERIFIED
    assert out.report.status_of(BINDING_KIND_PRODUCER_ATTESTATION) == S.ARTIFACT_INSTANT_MISMATCH


def test_no_entry_point_accepts_a_caller_supplied_instant():
    for target in (CloudScalingEnvelopeIssuance.issue, CloudScalingEnvelopeIssuanceRequest):
        names = set(inspect.signature(target).parameters)
        assert not names & {"as_of", "now", "issued_at", "not_before", "evaluation_time"}, names


def test_the_clock_is_read_exactly_once_even_on_refusal(world):
    revoke(world.authority, world.record, revoked_at=EVALUATION_INSTANT)
    _refused(world)
    assert world.clock.reads == 1


# --------------------------------------------------------------------------- #
# The decision must be this application's, unchanged
# --------------------------------------------------------------------------- #
def test_a_candidate_whose_decision_this_application_never_evaluated_is_refused(world):
    stranger = held_reference_seam(Clock(at=ISSUANCE_INSTANT))._app
    out = _refused(world, app=stranger)
    assert out.refusal is R.DECISION_NOT_FOUND and out.report is None


def test_a_candidate_bound_to_a_different_decision_is_refused(world):
    other = build_world(Clock(at=EVALUATION_INSTANT + timedelta(seconds=1)))
    assert other.candidate.decision_id == world.candidate.decision_id  # same id, other content
    assert other.candidate.decision_digest != world.candidate.decision_digest
    out = _refused(world, issue_request(other))
    assert out.refusal is R.DECISION_DIGEST_MISMATCH and out.report is None


# --------------------------------------------------------------------------- #
# The candidate must be exactly a candidate, and must re-derive
# --------------------------------------------------------------------------- #
def test_a_candidate_subclass_is_refused_at_the_boundary(world):
    class LookAlike(CapacityAuthorizationCandidate):
        @property
        def grants_authority(self):  # pragma: no cover - never consulted
            return True

    fake = LookAlike(**{f.name: getattr(world.candidate, f.name) for f in fields(world.candidate)})
    with pytest.raises(EnvelopeIssuanceExactTypeError):
        issue_request(world, candidate=fake)


def test_a_candidate_mutated_after_construction_is_refused(world):
    tampered = copy.copy(world.candidate)
    object.__setattr__(tampered, "idempotency_key", "sha256:" + "0" * 64)
    out = _refused(world, issue_request(world, candidate=tampered))
    assert out.refusal is R.VERIFICATION_NOT_VERIFIED
    assert out.report.status_of(BINDING_KIND_AUTHORIZATION_CANDIDATE) == S.CANDIDATE_NOT_REDERIVED


def test_a_verified_artifact_naming_another_candidate_is_refused(world, monkeypatch):
    other = build_world(Clock(at=EVALUATION_INSTANT + timedelta(seconds=1)))
    original = ProducerAttestationVerifier.verify
    monkeypatch.setattr(
        ProducerAttestationVerifier, "verify",
        lambda self, *, candidate, attestation, as_of: original(
            self, candidate=other.candidate, attestation=other.attestation, as_of=as_of),
    )
    out = _refused(world)
    assert out.refusal is R.VERIFICATION_NOT_VERIFIED
    assert out.report.status_of(BINDING_KIND_PRODUCER_ATTESTATION) == S.ARTIFACT_NOT_BOUND_TO_CANDIDATE


# --------------------------------------------------------------------------- #
# A failing verifier is never a pass
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cls", [ProducerAttestationVerifier, PolicyAuthenticityVerifier])
def test_a_raising_verifier_refuses_as_unavailable(world, monkeypatch, cls):
    def boom(self, **kw):
        raise RuntimeError("verifier down")

    monkeypatch.setattr(cls, "verify", boom)
    out = _refused(world)
    assert out.refusal is R.VERIFICATION_UNAVAILABLE
    assert out.report is not None and out.report.bindings == () and "raised" in out.report.detail


# --------------------------------------------------------------------------- #
# Request hygiene
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field, value", [
    ("audience", ""), ("session_id", " s "), ("nonce", None), ("ttl", timedelta(0)),
    ("ttl", 30), ("producer_attestation", object()),
])
def test_malformed_request_fields_are_refused(world, field, value):
    with pytest.raises(EnvelopeIssuanceExactTypeError):
        issue_request(world, **{field: value})


def test_a_foreign_request_type_is_refused(world):
    with pytest.raises(EnvelopeIssuanceExactTypeError):
        world.issuance().issue(object())  # type: ignore[arg-type]
