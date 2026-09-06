"""production_mode=True refuses the reference-grade resolver at construction:
by class, by subclass, and by an unstated posture. DenyAll is the one exact type
admitted without a production claim."""

from __future__ import annotations

import pytest

import ugence_risk_authority_effect_attestation as ea
from _fixtures import anchor_of, directory, provider_signer


def test_the_static_directory_is_refused_in_production_by_class():
    with pytest.raises(ea.EffectAttestationConfigurationError, match="refuses StaticTrustAnchorDirectory"):
        ea.Ed25519EffectAttestationVerifier(
            trust_anchor_resolver=directory(anchor_of(provider_signer())), production_mode=True
        )


def test_a_subclass_of_the_static_directory_is_refused_in_production():
    class Renamed(ea.StaticTrustAnchorDirectory):
        is_production_authoritative = True

    resolver = Renamed([anchor_of(provider_signer())], trust_anchor_set_id="effect-anchors",
                       trust_anchor_set_version="1")
    with pytest.raises(ea.EffectAttestationConfigurationError, match="inherits"):
        ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=resolver, production_mode=True)
    with pytest.raises(ea.EffectAttestationConfigurationError):
        ea.require_production_resolver(resolver)


def test_a_resolver_without_a_production_claim_is_refused_in_production():
    class Quiet:
        def resolve(self, coordinate):
            return ea.DenyAllTrustAnchorDirectory().resolve(coordinate)

    with pytest.raises(ea.EffectAttestationConfigurationError):
        ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=Quiet(), production_mode=True)
    with pytest.raises(ea.EffectAttestationConfigurationError):
        ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=None, production_mode=True)


def test_the_same_static_directory_is_admitted_outside_production():
    verifier = ea.Ed25519EffectAttestationVerifier(
        trust_anchor_resolver=directory(anchor_of(provider_signer())), production_mode=False
    )
    assert verifier.production_mode is False
    assert ea.Ed25519EffectAttestationVerifier(
        trust_anchor_resolver=ea.DenyAllTrustAnchorDirectory(), production_mode=True
    ).production_mode is True
