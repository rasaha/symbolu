"""Pinned fixtures for the suite. Fixed seeds, fixed instants, no clock, no randomness.

The independent isolated-install probe (``scripts/verify_isolated_install.py``)
does **not** import this module; it re-declares the same literals so a bug in a
shared helper cannot make a probe and a test agree with each other while both
disagree with reality.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ugence_governance_contracts import ExecutionBusinessOutcome, ExecutionObservation

import ugence_risk_authority_effect_attestation as ea

TENANT = "tenant-a"
OTHER_TENANT = "tenant-b"
PROVIDER_ID = "provider-alpha"
PROVIDER_KEY = "provider-key-1"
OBSERVER_ID = "observer-omega"
OBSERVER_KEY = "observer-key-1"
STRANGER_ID = "stranger-sigma"

PROVIDER_SEED = b"\x01" * 32
OBSERVER_SEED = b"\x02" * 32
STRANGER_SEED = b"\x03" * 32

ATTESTED_AT = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
AS_OF = datetime(2026, 9, 6, 12, 5, 0, tzinfo=timezone.utc)
VALID_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
VALID_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
ONE_US = timedelta(microseconds=1)

SET_ID = "effect-anchors"
SET_VERSION = "1"

PROVIDER = ea.EffectAttesterRole.EXECUTING_PROVIDER
OBSERVER = ea.EffectAttesterRole.INDEPENDENT_OBSERVER


def observation(**overrides) -> ExecutionObservation:
    kwargs = dict(
        business_outcome=ExecutionBusinessOutcome.SUCCEEDED,
        observed_parameters={"order_id": "o-1", "amount": "12.50"},
        final=True,
        reason="",
        provider_trace_id="trace-1",
        fingerprint="fp-1",
    )
    kwargs.update(overrides)
    return ExecutionObservation(**kwargs)


def provider_signer(seed: bytes = PROVIDER_SEED, **overrides):
    kwargs = dict(attester_identity=PROVIDER_ID, attester_key_id=PROVIDER_KEY, attester_role=PROVIDER)
    kwargs.update(overrides)
    return ea.ReferenceEd25519EffectAttestationSigner(seed, **kwargs)


def observer_signer(seed: bytes = OBSERVER_SEED, **overrides):
    kwargs = dict(attester_identity=OBSERVER_ID, attester_key_id=OBSERVER_KEY, attester_role=OBSERVER)
    kwargs.update(overrides)
    return ea.ReferenceEd25519EffectAttestationSigner(seed, **kwargs)


def anchor_of(signer, **overrides) -> ea.TrustAnchorRecord:
    kwargs = dict(trust_anchor_set_id=SET_ID, trust_anchor_set_version=SET_VERSION,
                  effective_from=VALID_FROM, effective_to=VALID_TO)
    kwargs.update(overrides)
    return signer.trust_anchor(**kwargs)


def directory(*anchors) -> ea.StaticTrustAnchorDirectory:
    return ea.StaticTrustAnchorDirectory(
        list(anchors), trust_anchor_set_id=SET_ID, trust_anchor_set_version=SET_VERSION
    )


def verifier(*anchors, production_mode: bool = False) -> ea.Ed25519EffectAttestationVerifier:
    return ea.Ed25519EffectAttestationVerifier(
        trust_anchor_resolver=directory(*anchors), production_mode=production_mode
    )


def attestation(signer=None, obs=None, tenant_id: str = TENANT, attested_at=ATTESTED_AT):
    return ea.mint_effect_attestation(
        obs if obs is not None else observation(),
        signer=signer if signer is not None else provider_signer(),
        tenant_id=tenant_id,
        attested_at=attested_at,
    )


def verify(v, att, *, role=PROVIDER, tenant=TENANT, obs=None, as_of=AS_OF, expected_anchor=None):
    return v.verify(
        attestation=att,
        expected_role=role,
        expected_tenant_id=tenant,
        expected_observation=obs if obs is not None else observation(),
        as_of=as_of,
        expected_anchor_record_digest=expected_anchor,
    )
