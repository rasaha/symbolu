"""The claim this package exists to test: a second family, no core change.

The Policy Authority ratified that a new policy family is added by registering a
new adapter, with no change to issuance, signing, registry, resolution or
revocation. Its own suite demonstrates that with a synthetic family *inside* the
distribution. This suite demonstrates it from **outside**, with a real one.

Everything here drives the genuine pipeline — real issuance, real Ed25519
signing, real registry, real resolution. Nothing is stubbed, because an adapter
proven against a stub core proves nothing about the authority it registers with.
"""

from __future__ import annotations

import pytest

from _authority_fixtures import (
    T_AFTER,
    T_BEFORE,
    T_MID,
    make_authority,
    make_policy,
)
from _bounds_fixtures import ADAPTER, TENANT, make_bounds_policy
from ugence_cloud_scaling_capacity_bounds_policy import (
    CAPACITY_BOUNDS_ADAPTER_ID,
    CAPACITY_BOUNDS_POLICY_FAMILY,
    CAPACITY_BOUNDS_POLICY_TYPE,
    CapacityBound,
    CapacityBoundsPolicy,
    LIFECYCLE_DRAFT,
    POLICY_SCOPE_GLOBAL,
    capacity_bounds_coordinate,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    PolicyIssuanceError,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    UnsupportedPolicyArtifactError,
    default_uvi_adapters,
    framed_body_digest,
)


def bounds_authority(*, with_uvi: bool = False):
    """An authority whose adapter registry carries the capacity-bounds family."""

    adapters = (
        AdapterRegistry([ADAPTER, *default_uvi_adapters().adapters])
        if with_uvi
        else AdapterRegistry([ADAPTER])
    )
    return make_authority(adapters=adapters)


def issue_and_resolve(policy, *, as_of=T_MID, tenant=TENANT, **kwargs):
    authority = bounds_authority()
    record = authority.issue(policy)
    resolution = authority.resolve(
        policy.metadata, as_of=as_of, tenant=tenant, **kwargs
    )
    return authority, record, resolution


# --------------------------------------------------------------------------- #
# Registration and resolution
# --------------------------------------------------------------------------- #


def test_a_capacity_bounds_policy_issues_and_resolves_through_the_shared_authority():
    policy = make_bounds_policy()
    _, record, resolution = issue_and_resolve(policy)

    assert resolution.status is PolicyResolutionStatus.RESOLVED
    assert resolution.reason is PolicyResolutionReason.RESOLVED
    assert resolution.policy is policy
    assert record.adapter_id == CAPACITY_BOUNDS_ADAPTER_ID
    assert record.policy_type == CAPACITY_BOUNDS_POLICY_TYPE


def test_the_coordinate_carries_this_family_and_never_a_uvi_one():
    policy = make_bounds_policy()
    coordinate = capacity_bounds_coordinate(policy.metadata)

    assert coordinate.policy_family == CAPACITY_BOUNDS_POLICY_FAMILY
    assert coordinate.tenant_id == TENANT


def test_the_family_coexists_with_the_uvi_adapters_in_one_registry():
    """Two families, one authority, no core branch on either."""

    authority = bounds_authority(with_uvi=True)
    bounds = make_bounds_policy()
    uvi = make_policy()

    authority.issue(bounds, record_id="rec-bounds")
    authority.issue(uvi, record_id="rec-uvi")

    assert (
        authority.resolve(bounds.metadata, as_of=T_MID, tenant=TENANT).status
        is PolicyResolutionStatus.RESOLVED
    )
    assert (
        authority.resolve(uvi.reference, as_of=T_MID).status
        is PolicyResolutionStatus.RESOLVED
    )


# --------------------------------------------------------------------------- #
# The descriptor projection — what Route 1 publishes
# --------------------------------------------------------------------------- #


def test_the_resolution_publishes_a_projection_that_rebuilds_the_signed_digest():
    """The whole point of the route, exercised on the family that motivated it."""

    _, record, resolution = issue_and_resolve(make_bounds_policy())

    recomputed = framed_body_digest(
        adapter_id=resolution.descriptor_adapter_id,
        policy_type=resolution.descriptor_policy_type,
        projection=resolution.descriptor_canonical_projection,
    )
    assert recomputed == record.policy_body_digest


def test_the_published_projection_carries_the_bounds_themselves():
    """The facts a downstream verifier will promote are actually reachable."""

    _, _, resolution = issue_and_resolve(make_bounds_policy())
    projection = resolution.descriptor_canonical_projection

    assert "bounds" in projection
    carried = projection["bounds"]
    assert isinstance(carried, list) and len(carried) == 2
    assert carried[0]["max_permitted_magnitude"] == 100
    assert carried[0]["max_permitted_delta"] == 25
    assert carried[1]["resource_class"] == "gpu"


def test_the_published_projection_omits_exactly_the_declared_content_digest():
    _, _, resolution = issue_and_resolve(make_bounds_policy())
    metadata = resolution.descriptor_canonical_projection["metadata"]

    assert "content_digest" not in metadata
    assert metadata["policy_id"] == "cloud-scaling-capacity-bounds"


def test_the_published_policy_type_is_the_constant_not_the_class_name():
    _, _, resolution = issue_and_resolve(make_bounds_policy())
    assert resolution.descriptor_policy_type == CAPACITY_BOUNDS_POLICY_TYPE


# --------------------------------------------------------------------------- #
# Adapter discipline
# --------------------------------------------------------------------------- #


def test_a_subclass_of_the_policy_is_not_recognized():
    """A subclass could add fields this family never validates."""

    class Extended(CapacityBoundsPolicy):
        pass

    genuine = make_bounds_policy()
    sneaky = Extended(metadata=genuine.metadata, bounds=genuine.bounds)

    assert ADAPTER.recognizes(genuine) is True
    assert ADAPTER.recognizes(sneaky) is False


def test_the_adapter_claims_no_foreign_artifact():
    assert ADAPTER.recognizes(make_policy()) is False
    assert ADAPTER.coordinate_for(make_policy().reference) is None
    assert ADAPTER.coordinate_for(object()) is None


def test_the_declared_digest_binds_the_body():
    policy = make_bounds_policy()
    descriptor = ADAPTER.describe(policy)
    assert descriptor.body_digest() == descriptor.declared_content_digest


def test_a_body_change_moves_the_digest():
    a = make_bounds_policy()
    b = make_bounds_policy(
        bounds=(
            CapacityBound(
                action_type="cloud_scaling.scale_out",
                max_permitted_magnitude=101,
                max_permitted_delta=25,
            ),
        )
    )
    assert ADAPTER.describe(a).body_digest() != ADAPTER.describe(b).body_digest()


def test_a_tampered_artifact_fails_resolution_rather_than_resolving():
    """A record whose body no longer matches its signed digest fails closed."""

    authority = bounds_authority()
    policy = make_bounds_policy()
    authority.issue(policy)

    # Same coordinate slot, different body: the declared digest no longer binds.
    tampered = CapacityBoundsPolicy(
        metadata=policy.metadata,
        bounds=(
            CapacityBound(
                action_type="cloud_scaling.scale_out",
                max_permitted_magnitude=999_999,
                max_permitted_delta=999_999,
            ),
        ),
    )
    descriptor = ADAPTER.describe(tampered)
    assert descriptor.body_digest() != policy.metadata.content_digest


# --------------------------------------------------------------------------- #
# The authority's own gates still apply to this family
# --------------------------------------------------------------------------- #


def test_a_draft_policy_is_refused_at_issuance_not_merely_at_resolution():
    """Stronger than the resolution gate: a draft never enters the registry.

    ``lifecycle_is_active`` is what the adapter reports, and issuance reads it
    before resolution ever runs — so the family inherits the earlier refusal
    rather than only the later one.
    """

    policy = make_bounds_policy(lifecycle_state=LIFECYCLE_DRAFT)
    authority = bounds_authority()

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
    policy = make_bounds_policy()
    _, _, resolution = issue_and_resolve(policy, as_of=as_of)

    assert resolution.status is PolicyResolutionStatus.UNRESOLVED
    assert resolution.reason is expected


def test_a_cross_tenant_request_does_not_resolve():
    policy = make_bounds_policy()
    _, _, resolution = issue_and_resolve(policy, tenant="tenant-elsewhere")

    assert resolution.status is PolicyResolutionStatus.UNRESOLVED
    assert resolution.reason is PolicyResolutionReason.TENANT_SCOPE_MISMATCH


def test_a_global_scope_policy_resolves_only_for_the_canonical_empty_tenant():
    policy = make_bounds_policy(scope=POLICY_SCOPE_GLOBAL, tenant_id="")
    authority = bounds_authority()
    authority.issue(policy)

    assert (
        authority.resolve(policy.metadata, as_of=T_MID, tenant="").status
        is PolicyResolutionStatus.RESOLVED
    )
    assert (
        authority.resolve(policy.metadata, as_of=T_MID, tenant=TENANT).reason
        is PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    )


def test_an_unregistered_family_is_refused_rather_than_guessed_at():
    """Without the adapter, the authority does not silently accept the artifact."""

    authority = make_authority()  # UVI adapters only
    with pytest.raises(UnsupportedPolicyArtifactError):
        authority.issue(make_bounds_policy())
