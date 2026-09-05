"""Positive controls: the genuine chain issues one signed envelope with five bindings."""

from __future__ import annotations

from datetime import timedelta

from risk_authority.api import VERIFIED
from risk_authority.domain import ArtifactBinding
from risk_authority.services.envelope_issuer import DEFAULT_ENVELOPE_TTL

from _issuance_fixtures import ISSUANCE_INSTANT, KEY_RECORD, issue_request

from ugence_cloud_scaling_envelope_issuance import (
    BINDING_KIND_AUTHORIZATION_CANDIDATE,
    BINDING_KIND_IDEMPOTENCY_KEY,
    BINDING_KIND_POLICY_AUTHENTICITY,
    BINDING_KIND_PRODUCER_ATTESTATION,
    BINDING_KIND_TARGET_SCOPE,
    REQUIRED_BINDING_KINDS,
    CloudScalingEnvelopeIssuanceOutcome,
    bare_digest,
)


def test_the_genuine_chain_issues_a_signed_envelope(world):
    out = world.issuance().issue(issue_request(world))
    assert type(out) is CloudScalingEnvelopeIssuanceOutcome
    assert out.refusal is None, (out.refusal, out.detail, out.report)
    assert out.issued and out.envelope is not None
    assert out.report is not None and out.report.all_verified
    assert out.report.producer_outcome == VERIFIED and out.report.policy_outcome == VERIFIED


def test_one_clock_read_and_one_instant_everywhere(world):
    out = world.issuance().issue(issue_request(world))
    env = out.envelope
    assert world.clock.reads == 1
    assert out.issued_at == ISSUANCE_INSTANT
    assert env.issued_at == env.not_before == ISSUANCE_INSTANT
    assert out.report.as_of == ISSUANCE_INSTANT
    assert all(b.resolved_as_of == ISSUANCE_INSTANT for b in out.report.bindings)


def test_the_five_bindings_are_the_ladder_digests_in_ratified_order(world):
    env = world.issuance().issue(issue_request(world)).envelope
    kinds = tuple(b.kind for b in env.bindings.artifact_bindings)
    assert kinds == REQUIRED_BINDING_KINDS
    by = {b.kind: b.digest for b in env.bindings.artifact_bindings}
    c = world.candidate
    assert by[BINDING_KIND_AUTHORIZATION_CANDIDATE] == bare_digest(c.candidate_digest)
    assert by[BINDING_KIND_TARGET_SCOPE] == bare_digest(c.target_scope_digest)
    assert by[BINDING_KIND_IDEMPOTENCY_KEY] == bare_digest(c.idempotency_key)
    # The two verified artifacts, recomputed through the verifiers at the same instant.
    producer = world.producer_verifier.verify(
        candidate=c, attestation=world.attestation, as_of=ISSUANCE_INSTANT
    ).verified_attestation
    assert by[BINDING_KIND_PRODUCER_ATTESTATION] == bare_digest(producer.artifact_digest)
    from ugence_cloud_scaling_envelope_issuance import policy_coordinate_of
    coordinate = policy_coordinate_of(c)
    proof = world.policy_verifier.verify(
        coordinate=coordinate, expected_reference_tenant_id=coordinate.tenant_id,
        as_of=ISSUANCE_INSTANT, candidate=c,
    ).verified_policy
    assert by[BINDING_KIND_POLICY_AUTHENTICITY] == proof.artifact_digest
    assert all(type(b) is ArtifactBinding for b in env.bindings.artifact_bindings)


def test_the_envelope_is_bound_to_the_decision_and_persisted(world):
    env = world.issuance().issue(issue_request(world)).envelope
    assert env.decision_id == world.candidate.decision_id
    assert env.tenant_id == world.candidate.tenant_id
    assert world.app.envelopes.get(env.tenant_id, env.envelope_id) is env
    assert env.bindings.authority_epoch == world.app.revocation.current_epoch(env.tenant_id)


def test_the_signature_verifies_and_covers_the_bindings(world):
    from dataclasses import replace
    env = world.issuance().issue(issue_request(world)).envelope
    assert env.key_id == KEY_RECORD.key_id
    assert KEY_RECORD.verify_key.verify(env.signing_payload(), env.signature)
    first = env.bindings.artifact_bindings[0]
    forged = replace(env, bindings=replace(env.bindings, artifact_bindings=(
        ArtifactBinding(first.kind, "f" * 64),) + env.bindings.artifact_bindings[1:]))
    assert not KEY_RECORD.verify_key.verify(forged.signing_payload(), forged.signature)


def test_the_application_verifies_its_own_envelope(world):
    env = world.issuance().issue(issue_request(world)).envelope
    verification = world.app.verify_envelope(env.tenant_id, env.envelope_id)
    assert verification.valid, verification


def test_expiry_is_capped_by_the_decision(world):
    decision = world.app.decisions.get(world.candidate.tenant_id, world.candidate.decision_id)
    long = world.issuance().issue(issue_request(world, ttl=timedelta(days=30))).envelope
    assert long.expires_at == decision.expires_at
    short = world.issuance().issue(issue_request(world, nonce="n2")).envelope
    assert short.expires_at <= min(ISSUANCE_INSTANT + DEFAULT_ENVELOPE_TTL, decision.expires_at)


def test_an_issued_envelope_is_authority_and_never_execution(world):
    out = world.issuance().issue(issue_request(world))
    assert out.grants_authority is True
    assert out.executable is False
    assert "executable" not in {f.name for f in __import__("dataclasses").fields(out)}
