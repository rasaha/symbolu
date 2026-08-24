"""The descriptor projection a RESOLVED resolution publishes (R-8, Route 1).

``resolve_policy`` already enforces ``descriptor.body_digest() ==
record.policy_body_digest`` before it returns ``RESOLVED``. The three
``descriptor_*`` fields republish the inputs to that digest so a consumer holding
no adapter registry can rebuild the frame and reach the same value.

These tests establish four things, in the order they matter:

1. the projection a resolution carries **actually reproduces** the signed body
   digest through the public ``framed_body_digest`` helper — the whole point;
2. it is present only on a ``RESOLVED`` answer;
3. the triple is all-or-nothing, so a partial set cannot pose as checkable; and
4. it is defensively copied and read-only, so the mapping a verifier re-digests
   is not one a caller can still reach.
"""

from __future__ import annotations

import pytest

from _authority_fixtures import (
    T_AFTER,
    T_MID,
    make_authority,
    make_policy,
)
from ugence_policy_authority.api import (
    PolicyResolutionReason,
    PolicyResolutionStatus,
    framed_body_digest,
)
from ugence_policy_authority.core.errors import PolicyAuthorityRequestError
from ugence_policy_authority.core.records import PolicyResolution


def _resolved():
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    resolution = authority.resolve(policy.reference, as_of=T_MID)
    assert resolution.status is PolicyResolutionStatus.RESOLVED
    return authority, record, resolution


# --------------------------------------------------------------------------- #
# 1. The projection reproduces the signed body digest.
# --------------------------------------------------------------------------- #


def test_the_published_projection_reproduces_the_signed_body_digest():
    """The check a downstream verifier will make, made here against the record."""

    _, record, resolution = _resolved()

    recomputed = framed_body_digest(
        adapter_id=resolution.descriptor_adapter_id,
        policy_type=resolution.descriptor_policy_type,
        projection=resolution.descriptor_canonical_projection,
    )
    assert recomputed == record.policy_body_digest


def test_a_substituted_policy_type_no_longer_reproduces_the_digest():
    """Why the projection closes the one-way-hash gap.

    ``policy_type`` is framed into the body digest but absent from the 21-key
    signing payload, so nothing downstream could previously check it. Reframing
    with a substituted value must miss.
    """

    _, record, resolution = _resolved()

    forged = framed_body_digest(
        adapter_id=resolution.descriptor_adapter_id,
        policy_type="cloud_scaling.capacity_bounds",
        projection=resolution.descriptor_canonical_projection,
    )
    assert forged != record.policy_body_digest


def test_a_substituted_adapter_id_no_longer_reproduces_the_digest():
    _, record, resolution = _resolved()

    forged = framed_body_digest(
        adapter_id="some-other-adapter",
        policy_type=resolution.descriptor_policy_type,
        projection=resolution.descriptor_canonical_projection,
    )
    assert forged != record.policy_body_digest


def test_a_mutated_projection_value_no_longer_reproduces_the_digest():
    _, record, resolution = _resolved()

    tampered = dict(resolution.descriptor_canonical_projection)
    key = sorted(tampered)[0]
    tampered[key] = "tampered"
    forged = framed_body_digest(
        adapter_id=resolution.descriptor_adapter_id,
        policy_type=resolution.descriptor_policy_type,
        projection=tampered,
    )
    assert forged != record.policy_body_digest


def test_the_projection_agrees_with_the_record_the_resolution_returned():
    """The published adapter id and policy type are the record's own, not a guess."""

    _, record, resolution = _resolved()

    assert resolution.descriptor_adapter_id == record.adapter_id
    assert resolution.descriptor_policy_type == record.policy_type


# --------------------------------------------------------------------------- #
# 2. Present only on a RESOLVED answer.
# --------------------------------------------------------------------------- #


def test_an_unresolved_answer_publishes_no_projection():
    """Nothing was proven, so nothing is republished."""

    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    resolution = authority.resolve(policy.reference, as_of=T_AFTER)

    assert resolution.status is PolicyResolutionStatus.UNRESOLVED
    assert resolution.reason is PolicyResolutionReason.EXPIRED
    assert resolution.descriptor_adapter_id is None
    assert resolution.descriptor_policy_type is None
    assert resolution.descriptor_canonical_projection is None


def test_an_unresolved_resolution_may_not_carry_a_projection():
    """Nothing was proven, so republishing a pre-image would read as evidence."""

    _, _, resolution = _resolved()

    with pytest.raises(PolicyAuthorityRequestError):
        PolicyResolution(
            status=PolicyResolutionStatus.UNRESOLVED,
            reason=PolicyResolutionReason.NOT_FOUND,
            requested_coordinate=resolution.requested_coordinate,
            as_of=T_MID,
            descriptor_adapter_id=resolution.descriptor_adapter_id,
            descriptor_policy_type=resolution.descriptor_policy_type,
            descriptor_canonical_projection=dict(
                resolution.descriptor_canonical_projection
            ),
        )


def test_the_unresolved_constructor_publishes_no_projection():
    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)
    coordinate = authority.resolve(policy.reference, as_of=T_MID).requested_coordinate

    resolution = PolicyResolution.unresolved(
        PolicyResolutionReason.NOT_FOUND,
        requested_coordinate=coordinate,
        as_of=T_MID,
    )
    assert resolution.descriptor_canonical_projection is None


# --------------------------------------------------------------------------- #
# 3. All three or none.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "partial",
    [
        {"descriptor_adapter_id": "a"},
        {"descriptor_policy_type": "t"},
        {"descriptor_canonical_projection": {"k": "v"}},
        {"descriptor_adapter_id": "a", "descriptor_policy_type": "t"},
        {"descriptor_adapter_id": "a", "descriptor_canonical_projection": {"k": "v"}},
        {"descriptor_policy_type": "t", "descriptor_canonical_projection": {"k": "v"}},
    ],
)
def test_a_partial_projection_triple_is_refused(partial):
    """A partial triple cannot rebuild the frame; admitting it would look checkable."""

    _, _, resolution = _resolved()

    with pytest.raises(PolicyAuthorityRequestError):
        PolicyResolution(
            status=PolicyResolutionStatus.RESOLVED,
            reason=PolicyResolutionReason.RESOLVED,
            requested_coordinate=resolution.requested_coordinate,
            as_of=T_MID,
            policy=resolution.policy,
            record=resolution.record,
            **partial,
        )


@pytest.mark.parametrize(
    "bad",
    [
        {"descriptor_adapter_id": 1, "descriptor_policy_type": "t",
         "descriptor_canonical_projection": {"k": "v"}},
        {"descriptor_adapter_id": "a", "descriptor_policy_type": 2,
         "descriptor_canonical_projection": {"k": "v"}},
        {"descriptor_adapter_id": "a", "descriptor_policy_type": "t",
         "descriptor_canonical_projection": ["not", "a", "mapping"]},
    ],
)
def test_a_wrongly_typed_projection_member_is_refused(bad):
    _, _, resolution = _resolved()

    with pytest.raises(PolicyAuthorityRequestError):
        PolicyResolution(
            status=PolicyResolutionStatus.RESOLVED,
            reason=PolicyResolutionReason.RESOLVED,
            requested_coordinate=resolution.requested_coordinate,
            as_of=T_MID,
            policy=resolution.policy,
            record=resolution.record,
            **bad,
        )


# --------------------------------------------------------------------------- #
# 4. Defensively copied and read-only.
# --------------------------------------------------------------------------- #


def test_the_published_projection_is_read_only():
    _, _, resolution = _resolved()

    with pytest.raises(TypeError):
        resolution.descriptor_canonical_projection["injected"] = "value"


def test_mutating_the_caller_mapping_does_not_reach_the_resolution():
    """The mapping a verifier re-digests is not one the caller still holds."""

    _, _, resolution = _resolved()
    source = {"a": "1", "b": "2"}

    built = PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_coordinate=resolution.requested_coordinate,
        as_of=T_MID,
        policy=resolution.policy,
        record=resolution.record,
        descriptor_adapter_id="a",
        descriptor_policy_type="t",
        descriptor_canonical_projection=source,
    )
    source["a"] = "tampered"
    source["c"] = "added"

    assert built.descriptor_canonical_projection["a"] == "1"
    assert "c" not in built.descriptor_canonical_projection


def test_the_resolution_does_not_expose_the_adapters_own_projection_object():
    """Two resolutions of the same policy must not share a mutable projection."""

    authority = make_authority()
    policy = make_policy()
    authority.issue(policy)

    first = authority.resolve(policy.reference, as_of=T_MID)
    second = authority.resolve(policy.reference, as_of=T_MID)

    assert first.descriptor_canonical_projection is not second.descriptor_canonical_projection
    assert dict(first.descriptor_canonical_projection) == dict(
        second.descriptor_canonical_projection
    )
