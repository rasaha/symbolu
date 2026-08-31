"""The claim this package exists to test: a third family, no core change.

The Policy Authority ratified that a new policy family is added by registering a
new adapter, with no change to issuance, signing, registry, resolution or
revocation. Its own suite demonstrates that with a synthetic family *inside* the
distribution, and the capacity-bounds package demonstrates it from outside with a
real one. This suite does the same for the family that Reasoning Strategy
Permission was ratified without.

Everything here drives the genuine pipeline — real issuance, real Ed25519
signing, real registry, real resolution. Nothing is stubbed, because an adapter
proven against a stub core proves nothing about the authority it registers with.

**What a ``RESOLVED`` answer here proves, and what it does not.** It proves that,
under the trust roots this call was configured with and at this explicit
``as_of``, the returned artifact was signed by an authorized, entitled,
un-revoked key over exactly this canonical body, that external approval evidence
verified, that the lifecycle and effective period admit it and that no verified
revocation applies. It proves nothing about whether the permitted set is wise,
correct or lawful; it does not prove any producer executed any procedure; and it
authorizes no runtime action.
"""

from __future__ import annotations

import dataclasses

import pytest
from _authority_fixtures import (
    T_AFTER,
    T_BEFORE,
    T_MID,
    approval_evidence,
    make_authority,
    make_policy,
)
from _strategy_permission_fixtures import (
    ADAPTER,
    DEFAULT_PERMITTED,
    STRATEGY_POLICY_REF,
    TENANT,
    make_permission_policy,
)
from ugence_agentic_proposer import ReasoningStrategy
from ugence_agentic_proposer_strategy_permission_policy import (
    LIFECYCLE_DRAFT,
    LIFECYCLE_SUPERSEDED,
    POLICY_SCOPE_GLOBAL,
    STRATEGY_PERMISSION_ADAPTER_ID,
    STRATEGY_PERMISSION_POLICY_FAMILY,
    STRATEGY_PERMISSION_POLICY_TYPE,
    STRATEGY_VOCABULARY_VERSION,
    StrategyPermissionPolicy,
    strategy_permission_coordinate,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    DenyAllApprovalVerifier,
    PolicyApprovalError,
    PolicyIssuanceError,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    UnsupportedPolicyArtifactError,
    UnsupportedSupersessionError,
    default_uvi_adapters,
    framed_body_digest,
    issue_policy,
)


def permission_authority(*, with_uvi: bool = False):
    """An authority whose adapter registry carries the strategy-permission family."""

    adapters = (
        AdapterRegistry([ADAPTER, *default_uvi_adapters().adapters])
        if with_uvi
        else AdapterRegistry([ADAPTER])
    )
    return make_authority(adapters=adapters)


def issue_and_resolve(policy, *, as_of=T_MID, tenant=TENANT, **kwargs):
    authority = permission_authority()
    record = authority.issue(policy)
    resolution = authority.resolve(
        policy.metadata, as_of=as_of, tenant=tenant, **kwargs
    )
    return authority, record, resolution


# --------------------------------------------------------------------------- #
# Registration and resolution
# --------------------------------------------------------------------------- #


def test_a_strategy_permission_policy_issues_and_resolves_through_the_shared_authority():
    policy = make_permission_policy()
    _, record, resolution = issue_and_resolve(policy)

    assert resolution.status is PolicyResolutionStatus.RESOLVED
    assert resolution.reason is PolicyResolutionReason.RESOLVED
    assert resolution.policy is policy
    assert record.adapter_id == STRATEGY_PERMISSION_ADAPTER_ID
    assert record.policy_type == STRATEGY_PERMISSION_POLICY_TYPE


def test_the_coordinate_carries_this_family_and_no_other():
    policy = make_permission_policy()
    coordinate = strategy_permission_coordinate(policy.metadata)

    assert coordinate.policy_family == STRATEGY_PERMISSION_POLICY_FAMILY
    assert coordinate.policy_family != "cloud_scaling.capacity_bounds"
    assert coordinate.tenant_id == TENANT
    assert coordinate.content_digest == policy.metadata.content_digest


def test_the_family_coexists_with_the_uvi_adapters_in_one_registry():
    """Two families, one authority, no core branch on either."""

    authority = permission_authority(with_uvi=True)
    permission = make_permission_policy()
    uvi = make_policy()

    authority.issue(permission, record_id="rec-permission")
    authority.issue(uvi, record_id="rec-uvi")

    assert (
        authority.resolve(permission.metadata, as_of=T_MID, tenant=TENANT).status
        is PolicyResolutionStatus.RESOLVED
    )
    assert (
        authority.resolve(uvi.reference, as_of=T_MID).status
        is PolicyResolutionStatus.RESOLVED
    )


# --------------------------------------------------------------------------- #
# The descriptor projection — what a downstream verifier may reproduce
# --------------------------------------------------------------------------- #


def test_the_resolution_publishes_a_projection_that_rebuilds_the_signed_digest():
    """Recomputed independently, not read back from the adapter's own output."""

    _, record, resolution = issue_and_resolve(make_permission_policy())

    recomputed = framed_body_digest(
        adapter_id=resolution.descriptor_adapter_id,
        policy_type=resolution.descriptor_policy_type,
        projection=resolution.descriptor_canonical_projection,
    )
    assert recomputed == record.policy_body_digest


def test_the_published_projection_carries_every_body_fact_that_matters():
    _, _, resolution = issue_and_resolve(make_permission_policy())
    projection = resolution.descriptor_canonical_projection

    assert projection["permitted_strategies"] == list(DEFAULT_PERMITTED)
    assert projection["strategy_policy_ref"] == STRATEGY_POLICY_REF
    assert projection["vocabulary_version"] == STRATEGY_VOCABULARY_VERSION


def test_the_published_projection_omits_exactly_the_declared_content_digest():
    """Removed by path, not blanked, and nothing else is dropped."""

    policy = make_permission_policy()
    _, _, resolution = issue_and_resolve(policy)
    metadata = resolution.descriptor_canonical_projection["metadata"]

    assert "content_digest" not in metadata
    assert set(metadata) == {
        "policy_id",
        "version",
        "scope",
        "lifecycle_state",
        "tenant_id",
        "supersedes_ref",
        "effective_from",
        "effective_to",
    }
    assert metadata["policy_id"] == policy.metadata.policy_id


def test_the_published_policy_type_is_the_constant_not_the_class_name():
    _, _, resolution = issue_and_resolve(make_permission_policy())
    assert resolution.descriptor_policy_type == STRATEGY_PERMISSION_POLICY_TYPE


# --------------------------------------------------------------------------- #
# Adapter discipline
# --------------------------------------------------------------------------- #


def test_a_subclass_of_the_policy_is_not_recognized():
    """A subclass could add fields this family never validates."""

    class Extended(StrategyPermissionPolicy):
        pass

    genuine = make_permission_policy()
    sneaky = Extended(
        metadata=genuine.metadata,
        strategy_policy_ref=genuine.strategy_policy_ref,
        permitted_strategies=genuine.permitted_strategies,
    )

    assert ADAPTER.recognizes(genuine) is True
    assert ADAPTER.recognizes(sneaky) is False
    with pytest.raises(UnsupportedPolicyArtifactError):
        ADAPTER.describe(sneaky)


def test_the_adapter_claims_no_foreign_artifact():
    assert ADAPTER.recognizes(make_policy()) is False
    assert ADAPTER.coordinate_for(make_policy().reference) is None
    assert ADAPTER.coordinate_for(object()) is None


def test_the_adapter_id_is_the_stable_constant():
    assert ADAPTER.adapter_id == STRATEGY_PERMISSION_ADAPTER_ID
    assert STRATEGY_PERMISSION_ADAPTER_ID == "ugence.agentic-proposer.strategy-permission/v1"


def test_the_declared_digest_binds_the_body():
    descriptor = ADAPTER.describe(make_permission_policy())
    assert descriptor.body_digest() == descriptor.declared_content_digest


def test_a_tampered_artifact_fails_resolution_rather_than_resolving():
    """A record whose body no longer matches its signed digest fails closed."""

    authority = permission_authority()
    policy = make_permission_policy()
    authority.issue(policy)

    # Same coordinate slot, a wider permitted set: the declared digest no longer
    # binds, and the widening is exactly the change an attacker would want.
    tampered = StrategyPermissionPolicy(
        metadata=policy.metadata,
        strategy_policy_ref=policy.strategy_policy_ref,
        permitted_strategies=tuple(sorted(m.value for m in ReasoningStrategy)),
    )
    assert ADAPTER.describe(tampered).body_digest() != policy.metadata.content_digest

    # Substitute the body under the same coordinate, leaving the signed record's
    # own fields untouched: this is the shape a storage-layer compromise takes.
    coordinate = strategy_permission_coordinate(policy.metadata)
    stored = authority.registry._issued[coordinate]
    authority.registry._issued[coordinate] = dataclasses.replace(stored, policy=tampered)

    resolution = authority.resolve(policy.metadata, as_of=T_MID, tenant=TENANT)
    assert resolution.status is PolicyResolutionStatus.UNRESOLVED
    assert resolution.reason in {
        PolicyResolutionReason.CONTENT_DIGEST_MISMATCH,
        PolicyResolutionReason.BODY_DIGEST_MISMATCH,
    }
    assert resolution.policy is None


# --------------------------------------------------------------------------- #
# The authority's own gates still apply to this family
# --------------------------------------------------------------------------- #


def test_the_shipped_deny_by_default_verifier_refuses_issuance():
    """`S2B-PF-E=A`'s companion: approval is external, and unconfigured means no.

    An incompletely configured deployment cannot issue this family's policy at
    all — the failure mode is a refusal, never an unapproved issuance.
    """

    authority = permission_authority()
    with pytest.raises((PolicyApprovalError, PolicyIssuanceError)):
        issue_policy(
            policy=make_permission_policy(),
            record_id="rec-deny",
            approval=approval_evidence(),
            approval_verifier=DenyAllApprovalVerifier(),
            signer=authority.signer,
            registry=authority.registry,
            adapters=authority.adapters,
            issued_at=T_MID,
        )
    assert not authority.registry._issued


@pytest.mark.parametrize(
    "lifecycle", [LIFECYCLE_DRAFT, LIFECYCLE_SUPERSEDED], ids=["draft", "superseded"]
)
def test_a_non_active_policy_is_refused_at_issuance_not_merely_at_resolution(lifecycle):
    """Stronger than the resolution gate: it never enters the registry."""

    policy = make_permission_policy(lifecycle_state=lifecycle)
    authority = permission_authority()

    with pytest.raises(PolicyIssuanceError):
        authority.issue(policy)

    resolution = authority.resolve(policy.metadata, as_of=T_MID, tenant=TENANT)
    assert resolution.status is PolicyResolutionStatus.UNRESOLVED
    assert resolution.reason is PolicyResolutionReason.NOT_FOUND


@pytest.mark.parametrize(
    "as_of,expected",
    [
        (T_BEFORE, PolicyResolutionReason.NOT_YET_EFFECTIVE),
        (T_AFTER, PolicyResolutionReason.EXPIRED),
    ],
)
def test_the_effective_window_is_enforced(as_of, expected):
    _, _, resolution = issue_and_resolve(make_permission_policy(), as_of=as_of)

    assert resolution.status is PolicyResolutionStatus.UNRESOLVED
    assert resolution.reason is expected


def test_a_cross_tenant_request_does_not_resolve():
    _, _, resolution = issue_and_resolve(
        make_permission_policy(), tenant="tenant-elsewhere"
    )

    assert resolution.status is PolicyResolutionStatus.UNRESOLVED
    assert resolution.reason is PolicyResolutionReason.TENANT_SCOPE_MISMATCH


def test_a_global_scope_policy_resolves_only_for_the_canonical_empty_tenant():
    policy = make_permission_policy(scope=POLICY_SCOPE_GLOBAL, tenant_id="")
    authority = permission_authority()
    authority.issue(policy)

    assert (
        authority.resolve(policy.metadata, as_of=T_MID, tenant="").status
        is PolicyResolutionStatus.RESOLVED
    )
    assert (
        authority.resolve(policy.metadata, as_of=T_MID, tenant=TENANT).reason
        is PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    )


def test_a_non_empty_supersession_reference_is_refused_at_issuance():
    """The family adds no interpretation: the authority refuses it outright."""

    policy = make_permission_policy(supersedes_ref="POL-2025-0001")
    authority = permission_authority()
    with pytest.raises(UnsupportedSupersessionError):
        authority.issue(policy)
    assert not authority.registry._issued


def test_an_unregistered_family_is_refused_rather_than_guessed_at():
    """Without the adapter, the authority does not silently accept the artifact."""

    authority = make_authority()  # UVI adapters only
    with pytest.raises(UnsupportedPolicyArtifactError):
        authority.issue(make_permission_policy())


def test_a_new_permitted_set_is_a_new_version_never_a_silent_re_point():
    """`[V]` No floating reference is representable: the digest is in the identity."""

    narrow = make_permission_policy(permitted=(ReasoningStrategy.REVISED_ADVISORY.value,))
    wide = make_permission_policy()

    assert narrow.metadata.content_digest != wide.metadata.content_digest
    assert strategy_permission_coordinate(
        narrow.metadata
    ) != strategy_permission_coordinate(wide.metadata)
    assert (
        strategy_permission_coordinate(narrow.metadata).identity_slot
        == strategy_permission_coordinate(wide.metadata).identity_slot
    )
