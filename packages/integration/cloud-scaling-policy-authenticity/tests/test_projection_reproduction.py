"""Gates 14 and 15: the projection reproduces the signed digest, and its bounds are readable.

R-8's real shape was not "compare the bounds". The verified artifact carried 26 facts and not
one was a bound, so there was nothing to compare against — and the reason was structural:
``policy_body_digest`` is a one-way hash, and this package holds no adapter registry with
which to re-derive the descriptor that produced it.

Route 1 published the descriptor's projection on the resolution itself. These tests establish
that the verifier actually uses it, refuses its absence rather than degrading, and refuses a
projection that does not reproduce the digest the issuance signature covered.
"""

from __future__ import annotations

import copy

import pytest

from _policy_fixtures import (
    T_MID,
    issued,
    issued_bounds,
    verifier_for,
)
from ugence_cloud_scaling_policy_authenticity import (
    PolicyAuthenticityOutcome as O,
)
from ugence_cloud_scaling_policy_authenticity import (
    PolicyAuthenticityVerifier,
    VerifiedCapacityBound,
)


def _verify(authority, record, *, tenant=None):
    return verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=(
            record.coordinate.tenant_id if tenant is None else tenant
        ),
        as_of=T_MID,
    )


class _RewritingPort:
    """A genuine port whose resolutions are rewritten on the way out.

    Every refusal below needs a resolution that is real in every respect *except* the one
    under test. Rebuilding one by hand would test the fixture; rewriting a genuine one tests
    the gate.
    """

    is_production_authoritative = True

    def __init__(self, inner, **overrides):
        self._inner = inner
        self._overrides = overrides

    @property
    def trust_configuration_digest(self) -> str:
        return self._inner.trust_configuration_digest

    def resolve_policy_version(self, **kwargs):
        resolution = self._inner.resolve_policy_version(**kwargs)
        # ``copy`` + ``object.__setattr__`` rather than ``dataclasses.replace``: replace
        # re-runs the authority's own ``__post_init__``, which refuses most of the shapes
        # under test here. A hostile or buggy port is under no such obligation, and this
        # boundary must hold against what it can actually be handed.
        forged = copy.copy(resolution)
        for name, value in self._overrides.items():
            object.__setattr__(forged, name, value)
        return forged


def _port_returning(authority, **overrides):
    from _policy_fixtures import port_for

    return _RewritingPort(port_for(authority), **overrides)


# --------------------------------------------------------------------------- #
# Gate 14 — absence is a refusal, never a downgrade
# --------------------------------------------------------------------------- #


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "absent",
    [
        {"descriptor_adapter_id": None, "descriptor_policy_type": None,
         "descriptor_canonical_projection": None},
    ],
)
def test_a_resolution_without_a_projection_is_refused(absent):
    """The load-bearing posture: "cannot reproduce" is a refusal, not a recorded fact.

    A port that omits the projection is one whose answer cannot be independently reproduced
    here. Carrying ``policy_type`` and the bounds unchecked in that case would restore
    exactly the condition 5B-3 exists to end.
    """

    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(
        resolution_port=_port_returning(authority, **absent)
    )
    result = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.POLICY_PROJECTION_ABSENT
    assert result.verified_policy is None


@pytest.mark.adversarial
def test_a_partial_projection_triple_is_refused_at_this_boundary_too():
    """The authority's constructor forbids a partial triple; this boundary re-checks it.

    It accepts a ``PolicyResolution`` it did not construct, so it cannot inherit the
    upstream invariant — a hand-assembled resolution reaches here exactly like a genuine one.
    """

    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(
        resolution_port=_port_returning(authority, descriptor_policy_type=None)
    )
    result = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.POLICY_PROJECTION_ABSENT


# --------------------------------------------------------------------------- #
# Gate 14 — a projection that does not reproduce the digest
# --------------------------------------------------------------------------- #


@pytest.mark.adversarial
def test_a_mutated_projection_is_refused():
    authority, record = issued()
    genuine = _verify(authority, record)
    assert genuine.outcome is O.VERIFIED

    from _policy_fixtures import port_for

    inner = port_for(authority)
    resolution = inner.resolve_policy_version(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    tampered = dict(resolution.descriptor_canonical_projection)
    tampered["injected"] = "value"

    verifier = PolicyAuthenticityVerifier(
        resolution_port=_port_returning(
            authority, descriptor_canonical_projection=tampered
        )
    )
    result = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.POLICY_PROJECTION_DIGEST_MISMATCH


@pytest.mark.adversarial
def test_a_projection_naming_another_adapter_is_refused():
    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(
        resolution_port=_port_returning(
            authority, descriptor_adapter_id="some.other.adapter/v1"
        )
    )
    result = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.POLICY_PROJECTION_DIGEST_MISMATCH


@pytest.mark.adversarial
def test_a_projection_naming_another_policy_type_is_refused():
    """The substitution the recorded half used to permit, refused from the other side."""

    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(
        resolution_port=_port_returning(
            authority, descriptor_policy_type="SomethingElseEntirely"
        )
    )
    result = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.POLICY_PROJECTION_DIGEST_MISMATCH


@pytest.mark.adversarial
def test_an_uncanonicalizable_projection_is_refused_rather_than_raising():
    """A verifier that cannot digest its input refuses; it does not propagate an exception."""

    authority, record = issued()
    verifier = PolicyAuthenticityVerifier(
        resolution_port=_port_returning(
            authority, descriptor_canonical_projection={"bad": 1.5}
        )
    )
    result = verifier.verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.POLICY_PROJECTION_DIGEST_MISMATCH


# --------------------------------------------------------------------------- #
# Gate 15 — the bounds, on a genuine capacity-bounds policy
# --------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_a_genuine_bounds_policy_carries_its_authenticated_bounds():
    authority, record = issued_bounds()
    result = _verify(authority, record, tenant="")

    assert result.outcome is O.VERIFIED
    bounds = result.verified_policy.capacity_bounds_fact
    assert len(bounds) == 1
    assert bounds[0] == VerifiedCapacityBound(
        action_type="cloud_scaling.scale_out",
        resource_class="",
        max_permitted_magnitude=100,
        max_permitted_delta=25,
    )


@pytest.mark.invariant
def test_a_non_bounds_family_carries_none_which_never_means_unbounded():
    """``None`` says this policy states no bound. It does not say the action is permitted."""

    authority, record = issued()
    result = _verify(authority, record)

    assert result.outcome is O.VERIFIED
    assert result.verified_policy.capacity_bounds_fact is None


@pytest.mark.invariant
def test_the_bounds_are_read_from_the_body_the_signature_covered():
    """Changing a ceiling changes the artifact, because it changed the signed body."""

    authority_a, record_a = issued_bounds()
    from _policy_fixtures import _Bound

    authority_b, record_b = issued_bounds(
        bounds=(
            _Bound(
                action_type="cloud_scaling.scale_out",
                resource_class="",
                max_permitted_magnitude=999,
                max_permitted_delta=25,
            ),
        )
    )
    a = _verify(authority_a, record_a, tenant="").verified_policy
    b = _verify(authority_b, record_b, tenant="").verified_policy

    assert a.capacity_bounds_fact[0].max_permitted_magnitude == 100
    assert b.capacity_bounds_fact[0].max_permitted_magnitude == 999
    assert a.artifact_digest != b.artifact_digest


@pytest.mark.invariant
def test_multiple_bounds_are_all_carried():
    from _policy_fixtures import _Bound

    authority, record = issued_bounds(
        bounds=(
            _Bound(
                action_type="cloud_scaling.scale_out",
                resource_class="",
                max_permitted_magnitude=100,
                max_permitted_delta=25,
            ),
            _Bound(
                action_type="cloud_scaling.scale_out",
                resource_class="gpu",
                max_permitted_magnitude=40,
                max_permitted_delta=10,
            ),
        )
    )
    result = _verify(authority, record, tenant="")
    assert len(result.verified_policy.capacity_bounds_fact) == 2


# --------------------------------------------------------------------------- #
# Gate 15 — a bound this profile cannot state exactly is not attested
# --------------------------------------------------------------------------- #

def _extract(bounds_value):
    """Run gate 15's extraction over a projection carrying ``bounds_value``.

    Called directly rather than through ``verify``. Reaching gate 15 end-to-end with a
    malformed body would require the record's signed digest, the coordinate's content digest
    and the projection to agree on that body — and mutating all three turns the test into a
    re-implementation of issuance rather than a test of the gate. The end-to-end path is
    already covered above; what is isolated here is the shape rule itself.
    """

    from ugence_cloud_scaling_policy_authenticity.verification import (
        _BoundsShapeError,
        _extract_capacity_bounds,
    )
    from ugence_policy_authority.api import PolicyCoordinate

    coordinate = PolicyCoordinate(
        policy_family="cloud_scaling.capacity_bounds",
        policy_id="p",
        version="1",
        content_digest="0" * 64,
        scope="GLOBAL",
        tenant_id="",
    )
    return _extract_capacity_bounds(coordinate, {"bounds": bounds_value}), _BoundsShapeError


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "bounds_value",
    [
        "not-a-sequence",
        {"action_type": "a"},
        [],
        [{"action_type": "a"}],
        [{"action_type": "a", "resource_class": "", "max_permitted_magnitude": 1}],
        [
            {
                "action_type": "a",
                "resource_class": "",
                "max_permitted_magnitude": 1,
                "max_permitted_delta": 1,
                "unexpected": "field",
            }
        ],
        [
            {
                "action_type": "a",
                "resource_class": "",
                "max_permitted_magnitude": -1,
                "max_permitted_delta": 0,
            }
        ],
        [
            {
                "action_type": "a",
                "resource_class": "",
                "max_permitted_magnitude": True,
                "max_permitted_delta": 0,
            }
        ],
        ["not-a-mapping"],
    ],
    ids=[
        "not-a-sequence",
        "mapping-not-sequence",
        "empty",
        "missing-three-fields",
        "missing-one-field",
        "unknown-field",
        "negative-ceiling",
        "bool-ceiling",
        "entry-not-a-mapping",
    ],
)
def test_an_unstateable_bound_is_refused_even_though_the_digest_reproduces(bounds_value):
    """The separation gate 15 exists for.

    Gate 14 proves the bytes are the ones the issuance signature covered. It says nothing
    about whether they form a bound this profile can state exactly — and a fact carried
    without being evaluated is not verified, however authentic its bytes.

    ``unknown-field`` is the case worth naming: the projection is genuine and merely carries
    a key this profile does not know. Reading the three it does know and dropping the fourth
    would mint an artifact whose bounds are a lossy summary of the signed body, so the whole
    determination is refused instead.
    """

    from ugence_cloud_scaling_policy_authenticity.verification import _BoundsShapeError

    with pytest.raises(_BoundsShapeError):
        _extract(bounds_value)


@pytest.mark.invariant
def test_a_well_formed_bound_extracts():
    """The negative control for the parametrized refusals above."""

    extracted, _ = _extract(
        [
            {
                "action_type": "cloud_scaling.scale_out",
                "resource_class": "",
                "max_permitted_magnitude": 10,
                "max_permitted_delta": 3,
            }
        ]
    )
    assert extracted == (
        VerifiedCapacityBound(
            action_type="cloud_scaling.scale_out",
            resource_class="",
            max_permitted_magnitude=10,
            max_permitted_delta=3,
        ),
    )


@pytest.mark.invariant
def test_a_foreign_family_carrying_a_bounds_key_is_not_read_as_a_bounds_statement():
    """Keyed on the coordinate's family, never on the presence of the key."""

    from ugence_cloud_scaling_policy_authenticity.verification import (
        _extract_capacity_bounds,
    )
    from ugence_policy_authority.api import PolicyCoordinate

    foreign = PolicyCoordinate(
        policy_family="DOMAIN",
        policy_id="p",
        version="1",
        content_digest="0" * 64,
        scope="GLOBAL",
        tenant_id="",
    )
    assert _extract_capacity_bounds(foreign, {"bounds": ["anything at all"]}) is None
