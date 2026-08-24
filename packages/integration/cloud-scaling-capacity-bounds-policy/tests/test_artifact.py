"""The capacity-bounds artifact's own construction rules.

Every rejection here is fail-closed: no policy object is produced. A malformed
artifact never reaches the authority.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from _bounds_fixtures import DEFAULT_BOUNDS, T_FROM, T_TO, make_bounds_policy
from ugence_cloud_scaling_capacity_bounds_policy import (
    PLACEHOLDER_CONTENT_DIGEST,
    CapacityBound,
    CapacityBoundsDuplicateError,
    CapacityBoundsFieldError,
    CapacityBoundsOrderingError,
    CapacityBoundsPolicy,
    CapacityBoundsPolicyMetadata,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
)


# --------------------------------------------------------------------------- #
# CapacityBound
# --------------------------------------------------------------------------- #


def test_a_well_formed_bound_is_accepted():
    bound = CapacityBound(
        action_type="cloud_scaling.scale_out",
        max_permitted_magnitude=10,
        max_permitted_delta=3,
    )
    assert bound.selector == ("cloud_scaling.scale_out", "")


def test_a_delta_ceiling_above_the_magnitude_ceiling_is_refused():
    """Incoherent, not merely generous: the change could never be reached."""

    with pytest.raises(CapacityBoundsOrderingError):
        CapacityBound(
            action_type="cloud_scaling.scale_out",
            max_permitted_magnitude=5,
            max_permitted_delta=6,
        )


@pytest.mark.parametrize("value", [-1, -100])
def test_a_negative_ceiling_is_refused(value):
    with pytest.raises(CapacityBoundsFieldError):
        CapacityBound(
            action_type="a", max_permitted_magnitude=value, max_permitted_delta=0
        )


@pytest.mark.parametrize("value", [True, False])
def test_a_bool_ceiling_is_refused_even_though_bool_subclasses_int(value):
    """``True`` silently meaning ``1`` is exactly the coercion a bound must not do."""

    with pytest.raises(CapacityBoundsFieldError):
        CapacityBound(
            action_type="a", max_permitted_magnitude=value, max_permitted_delta=0
        )


@pytest.mark.parametrize("value", [1.0, "5", None, 3 + 0j])
def test_a_non_int_ceiling_is_refused(value):
    with pytest.raises(CapacityBoundsFieldError):
        CapacityBound(
            action_type="a", max_permitted_magnitude=value, max_permitted_delta=0
        )


@pytest.mark.parametrize("value", ["", "   ", None, 7])
def test_an_absent_action_type_is_refused(value):
    with pytest.raises(CapacityBoundsFieldError):
        CapacityBound(
            action_type=value, max_permitted_magnitude=10, max_permitted_delta=1
        )


# --------------------------------------------------------------------------- #
# CapacityBoundsPolicy
# --------------------------------------------------------------------------- #


def test_a_policy_bounding_nothing_is_refused():
    """Worse than no policy: it resolves RESOLVED and looks like coverage."""

    with pytest.raises(CapacityBoundsFieldError):
        CapacityBoundsPolicy(
            metadata=CapacityBoundsPolicyMetadata(
                policy_id="p",
                version="1",
                content_digest=PLACEHOLDER_CONTENT_DIGEST,
                scope=POLICY_SCOPE_GLOBAL,
                lifecycle_state="APPROVED_ACTIVE",
            ),
            bounds=(),
        )


def test_two_bounds_claiming_one_selector_are_refused():
    """The applicable bound must be unambiguous by construction."""

    duplicate = (
        CapacityBound(action_type="a", max_permitted_magnitude=10, max_permitted_delta=1),
        CapacityBound(action_type="a", max_permitted_magnitude=20, max_permitted_delta=2),
    )
    with pytest.raises(CapacityBoundsDuplicateError):
        make_bounds_policy(bounds=duplicate)


def test_bounds_differing_only_by_resource_class_coexist():
    policy = make_bounds_policy()
    assert len(policy.bounds) == 2


def test_a_list_of_bounds_is_refused_because_this_artifact_is_digested():
    with pytest.raises(CapacityBoundsFieldError):
        make_bounds_policy(bounds=list(DEFAULT_BOUNDS))


def test_a_bound_subclass_is_refused():
    class Sneaky(CapacityBound):
        pass

    sneaky = Sneaky(action_type="a", max_permitted_magnitude=1, max_permitted_delta=1)
    with pytest.raises(CapacityBoundsFieldError):
        make_bounds_policy(bounds=(sneaky,))


# --------------------------------------------------------------------------- #
# bound_for
# --------------------------------------------------------------------------- #


def test_the_most_specific_bound_wins():
    policy = make_bounds_policy()
    specific = policy.bound_for(
        action_type="cloud_scaling.scale_out", resource_class="gpu"
    )
    assert specific.max_permitted_magnitude == 40


def test_an_unmatched_resource_class_falls_back_to_the_action_default():
    policy = make_bounds_policy()
    fallback = policy.bound_for(
        action_type="cloud_scaling.scale_out", resource_class="cpu"
    )
    assert fallback.max_permitted_magnitude == 100


def test_an_unbounded_selector_returns_none_which_never_means_unbounded():
    policy = make_bounds_policy()
    assert policy.bound_for(action_type="cloud_scaling.scale_in") is None


# --------------------------------------------------------------------------- #
# Metadata: scope, tenant, lifecycle, window
# --------------------------------------------------------------------------- #


def test_a_global_scope_policy_naming_a_tenant_is_refused():
    with pytest.raises(CapacityBoundsFieldError):
        make_bounds_policy(scope=POLICY_SCOPE_GLOBAL, tenant_id="tenant-1")


def test_a_tenant_scope_policy_naming_no_tenant_is_refused():
    """It would otherwise resolve for the global tenant instead."""

    with pytest.raises(CapacityBoundsFieldError):
        make_bounds_policy(scope=POLICY_SCOPE_TENANT, tenant_id="")


def test_a_global_scope_policy_carries_the_canonical_empty_tenant():
    policy = make_bounds_policy(scope=POLICY_SCOPE_GLOBAL, tenant_id="")
    assert policy.metadata.tenant_id == ""


def test_an_unknown_lifecycle_state_is_refused():
    with pytest.raises(CapacityBoundsFieldError):
        make_bounds_policy(lifecycle_state="PROBABLY_FINE")


def test_an_unknown_scope_is_refused():
    with pytest.raises(CapacityBoundsFieldError):
        make_bounds_policy(scope="SOMEWHERE")


def test_a_naive_effective_instant_is_refused_and_never_assumed_utc():
    with pytest.raises(CapacityBoundsFieldError):
        make_bounds_policy(effective_from=datetime(2026, 1, 1))


def test_an_empty_effective_interval_is_refused():
    """A half-open [from, to) interval that is empty can never admit a resolution."""

    with pytest.raises(CapacityBoundsOrderingError):
        make_bounds_policy(effective_from=T_TO, effective_to=T_FROM)


def test_an_instantaneous_effective_interval_is_refused():
    with pytest.raises(CapacityBoundsOrderingError):
        make_bounds_policy(effective_from=T_FROM, effective_to=T_FROM)


def test_an_open_ended_window_is_permitted():
    policy = make_bounds_policy(effective_from=None, effective_to=None)
    assert policy.metadata.effective_from is None


def test_a_non_utc_aware_instant_is_accepted_and_normalized_by_canonicalization():
    """Aware is the requirement; the authority's canonicalization renders UTC."""

    from datetime import timedelta

    offset = timezone(timedelta(hours=5, minutes=30))
    policy = make_bounds_policy(effective_from=T_FROM.astimezone(offset))
    assert policy.metadata.effective_from.utcoffset() == timedelta(hours=5, minutes=30)


def test_a_malformed_declared_digest_is_refused():
    with pytest.raises(CapacityBoundsFieldError):
        CapacityBoundsPolicyMetadata(
            policy_id="p",
            version="1",
            content_digest="not-a-digest",
            scope=POLICY_SCOPE_GLOBAL,
            lifecycle_state="APPROVED_ACTIVE",
        )


def test_an_uppercase_declared_digest_is_refused():
    with pytest.raises(CapacityBoundsFieldError):
        CapacityBoundsPolicyMetadata(
            policy_id="p",
            version="1",
            content_digest="A" * 64,
            scope=POLICY_SCOPE_GLOBAL,
            lifecycle_state="APPROVED_ACTIVE",
        )
