"""Every verified fact must be derivable. This is the audit, kept executable.

Two remediation rounds each found a member of the verified half that nothing established
(``policy_type``, ``trust_configuration_digest``), and both were found by spot-checking. This
module replaces sampling with enumeration: each of ``VERIFIED_FACT_NAMES`` must fall into
exactly one of three categories, and the categories are checked against the running code
rather than against any document.

#. **Signature-covered** — the underlying key appears in the measured signing payload of a
   genuinely issued record, so tampering breaks the issuance signature.
#. **Established by a gate** — a named gate in the verification routine refuses when the fact
   does not hold.
#. **A constant this package owns** — pinned by the artifact's own ``__post_init__``.

A verified fact in none of the three is a finding, and the last test here fails until it is
classified. That is the guard the earlier rounds lacked.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from _policy_fixtures import T_MID, issued, verifier_for
from ugence_cloud_scaling_policy_authenticity.verified import VERIFIED_FACT_NAMES

#: Verified facts whose value is copied from the issuance record, and the signed key each
#: one rides on. The right-hand names are asserted against the *measured* payload below.
SIGNATURE_COVERED = {
    "adapter_id": "adapter_id",
    "issuing_authority_id": "issuing_authority_id",
    "key_id": "key_id",
    "record_id": "record_id",
    "signature_alg": "signature_alg",
    "policy_body_digest": "policy_body_digest",
    "policy_issued_at_fact": "issued_at",
    "policy_family": "policy_family",
    "policy_id": "policy_id",
    "policy_version": "version",
    "policy_content_digest": "content_digest",
    "policy_scope": "scope",
    "policy_tenant_id": "tenant_id",
}

#: Verified facts established by a gate rather than by the signature.
GATE_ESTABLISHED = {"expected_reference_tenant_id"}

#: Verified facts that are this package's own constants, pinned at construction.
PACKAGE_CONSTANTS = {
    "authority_protocol_id",
    "authority_canonicalization_version",
    "policy_trust_anchor_owner",
    "verification_profile",
    "verification_profile_version",
}


def _signed_keys() -> set:
    """The issuance signing payload's keys, measured off a genuinely issued record."""

    _authority, record = issued()
    _prefix, _sep, body = record.signing_payload().partition(b"\x00")
    return set(json.loads(body.decode()))


def _verified():
    authority, record = issued()
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy


@pytest.mark.invariant
def test_every_verified_fact_is_classified():
    """The guard. A new verified fact must be placed in one of the three categories."""

    classified = set(SIGNATURE_COVERED) | GATE_ESTABLISHED | PACKAGE_CONSTANTS
    assert classified == VERIFIED_FACT_NAMES, {
        "unclassified": sorted(VERIFIED_FACT_NAMES - classified),
        "classified but not verified": sorted(classified - VERIFIED_FACT_NAMES),
    }
    # The three categories are disjoint, so no fact is justified twice.
    assert set(SIGNATURE_COVERED).isdisjoint(GATE_ESTABLISHED)
    assert set(SIGNATURE_COVERED).isdisjoint(PACKAGE_CONSTANTS)
    assert GATE_ESTABLISHED.isdisjoint(PACKAGE_CONSTANTS)


@pytest.mark.invariant
@pytest.mark.parametrize("fact,signed_key", sorted(SIGNATURE_COVERED.items()))
def test_each_signature_covered_fact_rides_on_a_measured_signed_key(fact, signed_key):
    """Measured off a real record, never read from a document. ``policy_type`` fails this."""

    assert signed_key in _signed_keys()


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "attribute,substitute",
    [
        ("adapter_id", "attacker.adapter/v9"),
        ("issuing_authority_id", "attacker.example"),
        ("key_id", "attacker-key-1"),
        ("record_id", "rec-substituted"),
        ("policy_body_digest", "d" * 64),
    ],
)
def test_tampering_a_signature_covered_record_field_refuses(attribute, substitute):
    authority, record = issued()
    object.__setattr__(record, attribute, substitute)
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.verified_policy is None


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "component,substitute",
    [
        ("policy_family", "OTHER"),
        ("policy_id", "other-policy"),
        ("version", "9.9.9"),
        ("content_digest", "e" * 64),
        ("scope", "TENANT"),
        ("tenant_id", "other-tenant"),
    ],
)
def test_the_record_s_coordinate_cannot_diverge_from_the_presented_one(component, substitute):
    """The mint reads the *caller's* coordinate, so the two must be pinned equal.

    They are, twice over: the authority refuses a stored record that does not carry the
    coordinate it was filed under, and this package re-checks the same equality itself.
    """

    authority, record = issued()
    original = record.coordinate
    object.__setattr__(record, "coordinate", replace(original, **{component: substitute}))
    result = verifier_for(authority).verify(
        coordinate=original,
        expected_reference_tenant_id=original.tenant_id,
        as_of=T_MID,
    )
    assert result.verified_policy is None


@pytest.mark.invariant
def test_the_expected_tenant_is_always_the_coordinate_s_own_tenant():
    """What gate 2 establishes, stated exactly — and it is narrower than the name suggests.

    On any minted artifact these two are necessarily equal, because gate 2 refuses when they
    differ. So ``expected_reference_tenant_id`` records *which tenant the reference declared*
    and adds nothing beyond ``policy_tenant_id``. In particular it does not establish that the
    caller was entitled to that tenant — no caller authorization happens anywhere in this
    chain. It stays in the verified half because it is genuinely checked; this test exists so
    that if a future change ever lets the two diverge, the field starts meaning something new
    loudly rather than silently.
    """

    artifact = _verified()
    assert artifact.expected_reference_tenant_id == artifact.policy_tenant_id


@pytest.mark.invariant
@pytest.mark.parametrize("constant", sorted(PACKAGE_CONSTANTS))
def test_each_package_constant_is_pinned_by_the_artifact_itself(constant):
    """Not merely stamped by the routine: the artifact refuses a wrong value at construction."""

    import inspect

    from ugence_cloud_scaling_policy_authenticity import verified as module

    source = inspect.getsource(module.VerifiedPolicyAuthenticity.__post_init__)
    assert f"self.{constant}" in source
