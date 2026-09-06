"""The positive controls every refusal test below is measured against."""

from __future__ import annotations

import pytest

import ugence_risk_authority_effect_attestation as ea
from _fixtures import (
    AS_OF,
    OBSERVER,
    OBSERVER_ID,
    OBSERVER_KEY,
    PROVIDER,
    PROVIDER_ID,
    PROVIDER_KEY,
    TENANT,
    anchor_of,
    attestation,
    observation,
    observer_signer,
    provider_signer,
    verifier,
    verify,
)

OUT = ea.EffectAttestationVerificationOutcome


@pytest.mark.parametrize(
    "signer_factory,role,identity,key",
    [
        (provider_signer, PROVIDER, PROVIDER_ID, PROVIDER_KEY),
        (observer_signer, OBSERVER, OBSERVER_ID, OBSERVER_KEY),
    ],
    ids=["executing-provider", "independent-observer"],
)
def test_happy_a_genuine_attestation_verifies_under_its_own_role_and_binds_every_fact(
    signer_factory, role, identity, key
):
    signer = signer_factory()
    anchor = anchor_of(signer)
    att = attestation(signer)
    result = verify(verifier(anchor), att, role=role)
    assert result.outcome is OUT.VERIFIED
    assert result.refusal_reason is None
    assert result.attester_role is role
    assert result.attester_identity == identity
    assert result.attester_key_id == key
    assert result.tenant_id == TENANT
    assert result.observation_digest == ea.observation_digest(observation())
    assert result.signing_payload_digest == att.signing_payload_digest
    assert result.anchor_record_digest == ea.anchor_record_digest(anchor)
    assert result.anchor_coordinate_digest == ea.anchor_coordinate_digest(
        ea.effect_attester_coordinate(role=role, attester_identity=identity, attester_key_id=key)
    )
    assert result.evaluated_at == AS_OF
    assert result.establishes == "PROVENANCE_AND_INTEGRITY_ONLY"
    assert result.role_establishes == ea.EFFECT_ATTESTER_ROLE_ESTABLISHES[role]
    assert result.factual_correctness_established is False


def test_happy_the_wrapper_holds_the_observation_unchanged_and_by_identity():
    obs = observation()
    att = attestation(obs=obs)
    assert att.observation is obs
    assert att.observation_digest == ea.observation_digest(obs)
    assert ea.canonical_observation(att.observation) == ea.canonical_observation(obs)


def test_happy_both_directories_and_both_verifiers_satisfy_the_ports():
    assert isinstance(verifier(), ea.EffectAttestationVerifierPort)
    assert isinstance(ea.DenyAllTrustAnchorDirectory(), ea.TrustAnchorResolverPort)
    assert isinstance(provider_signer(), ea.EffectAttestationSignerPort)
    assert ea.MATURITY == "REFERENCE_GRADE_NOT_PRODUCTION_READY"


def test_happy_deny_all_in_production_composes_and_refuses_everything():
    v = ea.Ed25519EffectAttestationVerifier(
        trust_anchor_resolver=ea.DenyAllTrustAnchorDirectory(), production_mode=True
    )
    result = verify(v, attestation())
    assert result.outcome is OUT.REFUSED
    assert result.refusal_reason in (
        ea.EffectAttestationRefusalReason.ANCHOR_UNKNOWN,
        ea.EffectAttestationRefusalReason.ANCHOR_UNAVAILABLE,
    )
    assert v.production_mode is True
