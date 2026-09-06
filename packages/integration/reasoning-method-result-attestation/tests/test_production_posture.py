"""production_mode=True refuses the reference-grade resolver at construction:
by class, by subclass, and by an unstated posture. DenyAll is the one exact type
admitted without a production claim."""

from __future__ import annotations

import pytest

import ugence_reasoning_method_result_attestation as ra
from _fixtures import anchor_of, directory, engine_signer


def test_the_static_directory_is_refused_in_production_by_class():
    with pytest.raises(ra.ComparisonResultAttestationConfigurationError, match="refuses StaticTrustAnchorDirectory"):
        ra.Ed25519ComparisonResultVerifier(
            trust_anchor_resolver=directory(anchor_of(engine_signer())), production_mode=True
        )


def test_a_subclass_of_the_static_directory_is_refused_in_production():
    class Renamed(ra.StaticTrustAnchorDirectory):
        is_production_authoritative = True

    resolver = Renamed([anchor_of(engine_signer())], trust_anchor_set_id="comparison-result-anchors",
                       trust_anchor_set_version="1")
    with pytest.raises(ra.ComparisonResultAttestationConfigurationError, match="inherits"):
        ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=resolver, production_mode=True)
    with pytest.raises(ra.ComparisonResultAttestationConfigurationError):
        ra.require_production_resolver(resolver)


def test_a_resolver_without_a_production_claim_is_refused_in_production():
    class Quiet:
        def resolve(self, coordinate, *, as_of=None):
            return ra.DenyAllTrustAnchorDirectory().resolve(coordinate)

    with pytest.raises(ra.ComparisonResultAttestationConfigurationError):
        ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=Quiet(), production_mode=True)
    with pytest.raises(ra.ComparisonResultAttestationConfigurationError):
        ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=None, production_mode=True)


def test_the_same_static_directory_is_admitted_outside_production():
    v = ra.Ed25519ComparisonResultVerifier(
        trust_anchor_resolver=directory(anchor_of(engine_signer())), production_mode=False
    )
    assert v.production_mode is False
    assert ra.Ed25519ComparisonResultVerifier(
        trust_anchor_resolver=ra.DenyAllTrustAnchorDirectory(), production_mode=True
    ).production_mode is True
