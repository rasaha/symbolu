"""Every refusal names *which* decision refused it.

The guard-coverage ADR §3 found this family's typed refusal degenerate: fifteen
guards raised one ``CapacityBoundsFieldError`` and the package published no reason
vocabulary, so ``pytest.raises(CapacityBoundsFieldError)`` — which the artifact
suite asserts fourteen times — is satisfied by *any* of the fifteen firing. That is
a test that shows the program refused, not that this guard decided the refusal.

These tests assert the half that was missing. They add no new refusal: every input
below already refused, with the same class, before ``CapacityBoundsRejectionReason``
existed. What is new is that each one is now distinguishable from its neighbours.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from _bounds_fixtures import (
    DEFAULT_BOUNDS,
    T_FROM,
    make_bounds_policy,
)
from ugence_cloud_scaling_capacity_bounds_policy import (
    PLACEHOLDER_CONTENT_DIGEST,
    CapacityBound,
    CapacityBoundsPolicy,
    CapacityBoundsPolicyError,
    CapacityBoundsPolicyFamilyAdapter,
    CapacityBoundsPolicyMetadata,
    CapacityBoundsRejectionReason as Reason,
    LIFECYCLE_APPROVED_ACTIVE,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    capacity_bounds_coordinate,
    rejection_reason_of,
)
from ugence_policy_authority.api import (
    PolicyAuthorityRequestError,
    UnsupportedPolicyArtifactError,
)


def _meta(**overrides) -> dict:
    fields = dict(
        policy_id="cloud-scaling-capacity-bounds",
        version="1.0.0",
        content_digest=PLACEHOLDER_CONTENT_DIGEST,
        scope=POLICY_SCOPE_TENANT,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id="tenant-1",
    )
    fields.update(overrides)
    return fields


def _bound(**overrides) -> dict:
    fields = dict(
        action_type="cloud_scaling.scale_out",
        max_permitted_magnitude=100,
        max_permitted_delta=25,
    )
    fields.update(overrides)
    return fields


# --- the vocabulary itself -----------------------------------------------------


def test_the_reason_vocabulary_has_no_duplicate_values():
    """A reason that shares a value with another discriminates nothing."""

    values = [member.value for member in Reason]
    assert len(values) == len(set(values))


def test_every_reason_the_package_names_is_a_member_of_the_vocabulary():
    """The source is the inventory. A raise that invented a token would not be here."""

    import ast
    import pathlib

    src = (
        pathlib.Path(__file__).resolve().parents[1]
        / "src"
        / "ugence_cloud_scaling_capacity_bounds_policy"
    )
    named = set()
    for module in sorted(src.glob("*.py")):
        for node in ast.walk(ast.parse(module.read_text())):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "Reason"
            ):
                named.add(node.attr)
    assert named, "no raise site names a reason; the enum is not threaded through"
    assert named <= {member.name for member in Reason}


def test_every_published_reason_is_reachable_from_some_refusal():
    """No dead members: each one is produced by an input this suite can build.

    A vocabulary with unreachable members reports coverage it does not have.
    """

    assert {member.name for member in Reason} == set(REFUSALS)


# --- the refusals, one per reason ----------------------------------------------


def _policy_whose_envelope_was_removed() -> CapacityBoundsPolicy:
    """An exact ``CapacityBoundsPolicy`` whose envelope was taken away after it was built.

    A subclass would not reach the guard — recognition is an exact runtime type test —
    and ``__post_init__`` refuses a bad envelope at construction. Removing the field
    from a valid, frozen instance is the only input that reaches the adapter's second
    guard, which is exactly what that guard is defending against: an artifact whose
    shape changed after the constructor blessed it.
    """

    policy = make_bounds_policy()
    object.__setattr__(policy, "metadata", None)
    return policy


def _raised(callable_, *args, **kwargs):
    with pytest.raises(Exception) as caught:  # noqa: PT011 — the class is asserted below
        callable_(*args, **kwargs)
    return caught.value


REFUSALS = {
    "FIELD_NOT_A_STRING": lambda: CapacityBound(**_bound(action_type=7)),
    "FIELD_EMPTY": lambda: CapacityBound(**_bound(action_type="   ")),
    "CONTENT_DIGEST_MALFORMED": lambda: CapacityBoundsPolicyMetadata(
        **_meta(content_digest="not-a-digest")
    ),
    "MAGNITUDE_NOT_AN_INT": lambda: CapacityBound(
        **_bound(max_permitted_magnitude=True)
    ),
    "MAGNITUDE_NEGATIVE": lambda: CapacityBound(**_bound(max_permitted_magnitude=-1)),
    "TIMESTAMP_NOT_A_DATETIME": lambda: CapacityBoundsPolicyMetadata(
        **_meta(effective_from="2026-01-01")
    ),
    "TIMESTAMP_NAIVE": lambda: CapacityBoundsPolicyMetadata(
        **_meta(effective_from=datetime(2026, 1, 1))
    ),
    "SCOPE_UNSUPPORTED": lambda: CapacityBoundsPolicyMetadata(**_meta(scope="REGION")),
    "LIFECYCLE_STATE_UNSUPPORTED": lambda: CapacityBoundsPolicyMetadata(
        **_meta(lifecycle_state="RETIRED")
    ),
    "GLOBAL_SCOPE_CARRIES_TENANT": lambda: CapacityBoundsPolicyMetadata(
        **_meta(scope=POLICY_SCOPE_GLOBAL, tenant_id="tenant-1")
    ),
    "TENANT_SCOPE_NAMES_NO_TENANT": lambda: CapacityBoundsPolicyMetadata(
        **_meta(scope=POLICY_SCOPE_TENANT, tenant_id="")
    ),
    "BOUND_ORDERING_INCOHERENT": lambda: CapacityBound(
        **_bound(max_permitted_magnitude=10, max_permitted_delta=11)
    ),
    "EFFECTIVE_INTERVAL_EMPTY": lambda: CapacityBoundsPolicyMetadata(
        **_meta(
            effective_from=T_FROM,
            effective_to=T_FROM,
        )
    ),
    "METADATA_TYPE_MISMATCH": lambda: CapacityBoundsPolicy(
        metadata="not-metadata", bounds=DEFAULT_BOUNDS
    ),
    "BOUNDS_NOT_A_TUPLE": lambda: CapacityBoundsPolicy(
        metadata=CapacityBoundsPolicyMetadata(**_meta()), bounds=list(DEFAULT_BOUNDS)
    ),
    "BOUNDS_EMPTY": lambda: CapacityBoundsPolicy(
        metadata=CapacityBoundsPolicyMetadata(**_meta()), bounds=()
    ),
    "BOUND_TYPE_MISMATCH": lambda: CapacityBoundsPolicy(
        metadata=CapacityBoundsPolicyMetadata(**_meta()), bounds=("not-a-bound",)
    ),
    "DUPLICATE_SELECTOR": lambda: CapacityBoundsPolicy(
        metadata=CapacityBoundsPolicyMetadata(**_meta()),
        bounds=(CapacityBound(**_bound()), CapacityBound(**_bound())),
    ),
    "ARTIFACT_TYPE_MISMATCH": lambda: CapacityBoundsPolicyFamilyAdapter().describe(
        object()
    ),
    "METADATA_ENVELOPE_MISSING": lambda: CapacityBoundsPolicyFamilyAdapter().describe(
        _policy_whose_envelope_was_removed()
    ),
    "COORDINATE_INPUT_TYPE_MISMATCH": lambda: capacity_bounds_coordinate(object()),
    "PROJECTION_DIGEST_DECLARATION_MISSING": (
        lambda: CapacityBoundsPolicyFamilyAdapter()._canonical_projection(
            {"metadata": {"policy_id": "cloud-scaling-capacity-bounds"}}
        )
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_each_refusal_carries_its_own_reason(name):
    error = _raised(REFUSALS[name])
    assert rejection_reason_of(error) is Reason[name]


def test_two_guards_sharing_an_exception_class_are_now_distinguishable():
    """§6's within-class criterion, made falsifiable for the commonest pair.

    Both refusals below raise ``CapacityBoundsFieldError``. Before the enum, a test
    reading only the class could not tell which guard decided; now it can.
    """

    empty = _raised(lambda: CapacityBound(**_bound(action_type="  ")))
    negative = _raised(lambda: CapacityBound(**_bound(max_permitted_magnitude=-1)))
    assert type(empty) is type(negative)
    assert rejection_reason_of(empty) is not rejection_reason_of(negative)


def test_the_adapter_still_refuses_under_the_authoritys_own_class():
    """Attaching a reason must not change which class the authority sees."""

    assert isinstance(
        _raised(lambda: CapacityBoundsPolicyFamilyAdapter().describe(object())),
        UnsupportedPolicyArtifactError,
    )
    assert isinstance(
        _raised(lambda: capacity_bounds_coordinate(object())),
        PolicyAuthorityRequestError,
    )


def test_a_valid_policy_still_describes_without_refusing():
    """The enum changed no admitted input: the happy path is untouched."""

    policy = make_bounds_policy()
    descriptor = CapacityBoundsPolicyFamilyAdapter().describe(policy)
    assert descriptor.declared_content_digest == descriptor.body_digest()


def test_the_family_root_class_requires_a_reason():
    """A refusal with no reason is the defect §3 ruled against; it cannot compile."""

    with pytest.raises(TypeError):
        CapacityBoundsPolicyError("no reason given")


def test_a_naive_datetime_is_still_refused_and_now_says_why():
    """The one input whose refusal reason a caller most often has to act on."""

    error = _raised(
        lambda: CapacityBoundsPolicyMetadata(
            **_meta(effective_from=datetime(2026, 1, 1))
        )
    )
    assert rejection_reason_of(error) is Reason.TIMESTAMP_NAIVE
    assert datetime(2026, 1, 1, tzinfo=timezone.utc)  # the shape that is admitted
