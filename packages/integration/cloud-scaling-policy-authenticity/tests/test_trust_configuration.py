"""A determination names the trust configuration it was reached under, and cannot drift from it.

D-5B0B-1 requires the proof to carry the trust-configuration identity. That is only worth
carrying if it actually moves when trust moves, so these tests measure exactly that: which
changes must move the digest, which must not, and that the artifact digest follows.
"""

from __future__ import annotations

import pytest

from _policy_fixtures import T_MID, issued, make_authority, port_for, verifier_for
from ugence_policy_authority.api import (
    AdapterRegistry,
    KeyEntitlement,
    PolicyKeyRing,
    default_uvi_adapters,
)

from ugence_cloud_scaling_policy_authenticity import (
    DenyAllPolicyResolutionPort,
    PolicyAuthenticityVerifier,
    PolicyAuthorityResolutionPort,
    is_policy_digest,
    policy_trust_configuration_digest,
)


def _digest(**overrides):
    base = dict(
        key_ring=PolicyKeyRing(),
        adapters=AdapterRegistry(),
        approval_verifier_configured=False,
    )
    base.update(overrides)
    return policy_trust_configuration_digest(**base)


@pytest.mark.invariant
def test_the_trust_configuration_digest_is_a_bare_policy_authority_digest():
    assert is_policy_digest(_digest())


@pytest.mark.invariant
def test_equal_configurations_produce_equal_digests_regardless_of_insertion_order():
    authority = make_authority()
    keys = list(authority.key_ring.keys.values())
    forward = PolicyKeyRing(keys)
    reversed_ring = PolicyKeyRing(list(reversed(keys)))
    assert _digest(key_ring=forward) == _digest(key_ring=reversed_ring)


@pytest.mark.adversarial
def test_revoking_a_key_moves_the_trust_configuration_digest():
    authority = make_authority()
    before = _digest(key_ring=authority.key_ring)
    revoked = PolicyKeyRing([k.revoke() for k in authority.key_ring.keys.values()])
    assert _digest(key_ring=revoked) != before


@pytest.mark.adversarial
def test_adding_a_key_moves_the_trust_configuration_digest():
    authority = make_authority()
    before = _digest(key_ring=authority.key_ring)
    from _policy_fixtures import make_signer

    extra = make_signer(key_id="another-key", seed=11).verification_key()
    assert _digest(key_ring=authority.key_ring.with_key(extra)) != before


@pytest.mark.adversarial
def test_changing_an_entitlement_moves_the_trust_configuration_digest():
    authority = make_authority()
    before = _digest(key_ring=authority.key_ring)
    widened = PolicyKeyRing(
        [
            authority.signer.verification_key(
                entitlements=(KeyEntitlement.ISSUE_POLICY, KeyEntitlement.REVOKE_POLICY)
            )
        ]
    )
    assert _digest(key_ring=widened) != before


@pytest.mark.adversarial
def test_registering_an_adapter_moves_the_trust_configuration_digest():
    assert _digest(adapters=default_uvi_adapters()) != _digest(adapters=AdapterRegistry())


@pytest.mark.adversarial
def test_configuring_approval_re_verification_moves_the_trust_configuration_digest():
    assert _digest(approval_verifier_configured=True) != _digest()


@pytest.mark.adversarial
def test_the_verified_artifact_digest_follows_the_trust_configuration():
    """The same policy, verified under two trust configurations, is two determinations."""

    authority, record = issued()
    first = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy

    widened_ring = authority.key_ring.with_key(
        authority.signer.verification_key(
            entitlements=(KeyEntitlement.ISSUE_POLICY, KeyEntitlement.REVOKE_POLICY)
        )
    )
    port = PolicyAuthorityResolutionPort(
        registry=authority.registry,
        signature_verifier=widened_ring,
        adapters=authority.adapters,
    )
    second = PolicyAuthenticityVerifier(resolution_port=port).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy

    assert first.trust_configuration_digest != second.trust_configuration_digest
    assert first.artifact_digest != second.artifact_digest
    assert first.policy_body_digest == second.policy_body_digest


@pytest.mark.invariant
def test_the_empty_trust_configuration_is_distinct_from_any_populated_one():
    authority = make_authority()
    assert (
        DenyAllPolicyResolutionPort().trust_configuration_digest
        != port_for(authority).trust_configuration_digest
    )


@pytest.mark.invariant
def test_no_public_key_material_enters_the_trust_configuration_digest():
    """The identity answers "which configuration", and this package handles no key bytes."""

    import inspect

    from ugence_cloud_scaling_policy_authenticity import resolution_port as module

    source = inspect.getsource(module.policy_trust_configuration_digest)
    for forbidden in ("verify_key", "public_bytes", "seed", "encode()"):
        assert forbidden not in source


# --------------------------------------------------------------------------- #
# The port reports; the verifier snapshots
# --------------------------------------------------------------------------- #
class DriftingPort:
    """A port whose reported trust identity changes on every read.

    Not a hypothetical: ``trust_configuration_digest`` is a property on an injected
    collaborator, so a port backed by a mutable key store recomputes it, and one that
    rebuilds its ring in the background genuinely answers differently over time. A verifier
    that read it at mint time would stamp an identity it never admitted.
    """

    def __init__(self, inner):
        self._inner = inner
        self.reads = 0

    @property
    def trust_configuration_digest(self) -> str:
        self.reads += 1
        return f"{self.reads:064x}"

    @property
    def is_production_authoritative(self) -> bool:
        return self._inner.is_production_authoritative

    def resolve_policy_version(self, **kwargs):
        return self._inner.resolve_policy_version(**kwargs)


@pytest.mark.adversarial
def test_the_verifier_snapshots_the_trust_identity_and_mints_from_the_snapshot():
    authority, record = issued()
    port = DriftingPort(port_for(authority))
    verifier = PolicyAuthenticityVerifier(resolution_port=port)
    admitted = verifier.trust_configuration_digest
    assert port.reads == 1  # read once, at construction

    verified = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy

    # The port has drifted; the determination names what was admitted, not what it now says.
    assert verified.trust_configuration_digest == admitted
    assert verified.trust_configuration_digest != port.trust_configuration_digest


@pytest.mark.adversarial
def test_the_snapshot_is_stable_across_repeated_reads_and_repeated_verifications():
    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(resolution_port=DriftingPort(port_for(authority)))
    seen = {verifier.trust_configuration_digest for _ in range(5)}
    for _ in range(3):
        seen.add(
            verifier.verify(
                coordinate=record.coordinate,
                expected_reference_tenant_id=record.coordinate.tenant_id,
                as_of=T_MID,
            ).verified_policy.trust_configuration_digest
        )
    assert len(seen) == 1


@pytest.mark.adversarial
def test_the_snapshot_cannot_be_rebound_after_construction():
    authority = make_authority()
    verifier = PolicyAuthenticityVerifier(resolution_port=port_for(authority))
    with pytest.raises(AttributeError):
        verifier._trust_configuration_digest = "d" * 64


@pytest.mark.happy
def test_two_verifiers_over_the_same_configuration_snapshot_the_same_identity():
    authority = make_authority()
    first = PolicyAuthenticityVerifier(resolution_port=port_for(authority))
    second = PolicyAuthenticityVerifier(resolution_port=port_for(authority))
    assert first.trust_configuration_digest == second.trust_configuration_digest
