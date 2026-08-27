"""Coverage for the guards the CI mutation sweep found unscored.

These guards were not tested weakly — they were never reached, so neutralising them changed
nothing any test could see. They were invisible for longer than that: until the audit-
mandated green-baseline rule landed, this package's sweep copied it to a directory named
``package``, ``test_phase5a_untouched.py`` asserts its own directory name, and that one
permanent failure marked every mutant killed. The 115/115 result was an artefact. These are
the guards that result was hiding.

Each test reaches exactly one guard through the surface it defends and asserts the refusal
that guard alone produces. The guard number in each docstring is its index in
``guard_inventory.json``; the sweep re-runs against these tests, so a guard that stops being
load-bearing shows up as a survivor again rather than as silence.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest

from _policy_fixtures import T_MID, bounds_authority, issued, issued_bounds, port_for, verifier_for
from ugence_cloud_scaling_policy_authenticity import (
    PolicyAuthenticityResult,
    PolicyAuthenticityVerifier,
    VerifiedPolicyArtifactIntegrityError,
)
from ugence_cloud_scaling_policy_authenticity.errors import (
    PolicyAuthenticityConfigurationError,
    PolicyAuthenticityFieldError,
)


# --- canonical.py ---------------------------------------------------------------------


@pytest.mark.parametrize("domain", ["", 0, None, b"cloud_scaling"])
def test_a_framed_digest_domain_that_is_not_a_non_empty_str_is_refused(domain):
    """Guard 1 — ``canonical.py:89``, ``type(domain) is not str or not domain``.

    The domain tag is the whole point of the frame: it is what keeps this package's artifact
    digests from ever being readable as Policy Authority body digests. An empty or absent
    domain collapses that separation, so it is refused rather than defaulted.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import framed_digest  # noqa: PLC0415

    with pytest.raises(PolicyAuthenticityFieldError) as excinfo:
        framed_digest(domain=domain, body={"a": 1})
    assert "non-empty str" in str(excinfo.value)


def test_an_instant_that_is_not_exactly_a_datetime_is_refused():
    """Guard 9 — ``canonical.py:184``, ``type(value) is not datetime``.

    Exact, not ``isinstance``: a ``datetime`` subclass can override every comparison the
    freshness and validity gates decide with, and canonicalization renders it to the bytes a
    plain ``datetime`` produces, so no digest downstream can tell them apart.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_aware_utc,
    )

    class LyingInstant(__import__("datetime").datetime):
        def __lt__(self, other):  # pragma: no cover - never reached; the type gate refuses
            return True

    forged = LyingInstant(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc)
    with pytest.raises(PolicyAuthenticityFieldError) as excinfo:
        require_aware_utc("as_of", forged)
    assert "exactly a datetime" in str(excinfo.value)


# --- resolution_port.py ---------------------------------------------------------------


def test_a_resolution_port_built_without_a_registry_is_refused():
    """Guard 17 — ``resolution_port.py:193``, ``registry is None``.

    There is no ambient registry to fall back to. A port assembled without one would either
    fail later at an arbitrary point or, worse, resolve against something a composition root
    supplied implicitly.
    """

    from ugence_cloud_scaling_policy_authenticity.resolution_port import (  # noqa: PLC0415
        PolicyAuthorityResolutionPort,
    )

    authority = bounds_authority()
    genuine = port_for(authority)
    with pytest.raises(PolicyAuthenticityConfigurationError) as excinfo:
        PolicyAuthorityResolutionPort(
            registry=None,
            signature_verifier=genuine._signature_verifier,
            adapters=genuine._adapters,
        )
    assert "policy registry is required" in str(excinfo.value)


# --- verification.py: the verifier's own configuration --------------------------------


def test_a_resolution_port_that_cannot_resolve_is_refused_at_construction():
    """Guard 65 — ``verification.py:315``, ``not hasattr(port, 'resolve_policy_version')``.

    Structural, and deliberately so: the verifier refuses a port that cannot answer the one
    question it exists to ask, at construction rather than at the first resolution. A
    configuration error found at verification time is a refusal a caller cannot distinguish
    from a policy decision.
    """

    @dataclass
    class PortWithoutTheMethod:
        trust_configuration_digest: str = "0" * 64
        is_production_authoritative: bool = False

    with pytest.raises(PolicyAuthenticityConfigurationError) as excinfo:
        PolicyAuthenticityVerifier(resolution_port=PortWithoutTheMethod())
    assert "resolve_policy_version" in str(excinfo.value)


def test_a_result_carrying_a_foreign_resolution_type_is_refused():
    """Guard 57 — ``verification.py:207``, ``type(self.resolution) is not PolicyResolution``.

    The verified half is revalidated above this line, so a fabricated artifact never gets
    here. What this catches is the other half: a genuine determination paired with something
    that is not the authority's own resolution type. The policy body reaches a consumer
    through ``PolicyResolution``, and a look-alike would deliver a body no proof covers.
    """

    authority, record = issued_bounds()
    genuine = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )

    class LookAlikeResolution:
        """Every attribute the pair check reads, and the wrong type."""

        def __init__(self, real):
            self.status = real.status
            self.policy = real.policy
            self.requested_coordinate = real.requested_coordinate
            self.as_of = real.as_of

    with pytest.raises(TypeError) as excinfo:
        PolicyAuthenticityResult(
            verified_policy=genuine.verified_policy,
            resolution=LookAlikeResolution(genuine.resolution),
        )
    assert "PolicyResolution" in str(excinfo.value)


# --- verified.py: the R-3 gate on the artifact ----------------------------------------


def test_an_artifact_whose_content_digest_differs_from_its_body_digest_is_refused():
    """Guard 41 — ``verified.py:525``, ``policy_content_digest != policy_body_digest``.

    ADR residual R-3: the Policy Authority enforces this equality at issuance and does not
    re-enforce it at resolution. The verifier checks it before minting; this checks it on the
    artifact, so a mutated artifact cannot present a coordinate naming a different body than
    the one the signature covered. Both halves are needed — this is the half nothing reached.
    """

    from test_verified_artifact import _field_values, _genuine, _recompute  # noqa: PLC0415

    genuine = _genuine()
    fields = _field_values(genuine)
    fields["policy_content_digest"] = "b" * 64
    with pytest.raises(VerifiedPolicyArtifactIntegrityError) as excinfo:
        type(genuine)(
            **fields,
            artifact_digest=_recompute(fields),
            construction_token=genuine.construction_token,
        )
    assert "policy_content_digest must equal policy_body_digest" in str(excinfo.value)


# --- verification.py: the resolution's own shape --------------------------------------
#
# These three are reached by rewriting the authority's answer *after* it is produced. That is
# not a stub of the authority: the resolution is genuine, signed and correct, and one field
# of it is then changed — which is exactly the shape of a compromised or merely buggy
# composition-root component, and the reason the verifier re-checks a resolution it did not
# construct.


@dataclass
class _RewritingPort:
    """Wraps a genuine port and rewrites named attributes on the answer it returns."""

    inner: Any
    rewrite: dict = field(default_factory=dict)

    @property
    def trust_configuration_digest(self) -> str:
        return self.inner.trust_configuration_digest

    @property
    def is_production_authoritative(self) -> bool:
        return self.inner.is_production_authoritative

    def resolve_policy_version(self, *, coordinate, expected_reference_tenant_id, as_of):
        answer = self.inner.resolve_policy_version(
            coordinate=coordinate,
            expected_reference_tenant_id=expected_reference_tenant_id,
            as_of=as_of,
        )
        for name, value in self.rewrite.items():
            object.__setattr__(answer, name, value(answer) if callable(value) else value)
        return answer


def _verify_with(port, record, **kwargs):
    return PolicyAuthenticityVerifier(resolution_port=port).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
        **kwargs,
    )


def test_a_record_carrying_another_coordinate_is_refused():
    """Guard 81 — ``verification.py:512``, ``record.coordinate != coordinate``.

    The two guards above it check that the record is the right *type* and that it carries the
    resolution's own artifact. Neither asks whether the record is about the policy that was
    asked for. A record whose artifact and resolution agree with each other, and whose
    coordinate names a different policy, passes both and is caught only here.
    """

    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415

    authority, record = issued_bounds()
    other = dataclasses.replace(record.coordinate, policy_id="some.other-policy")

    def _swap_coordinate(answer):
        object.__setattr__(answer.record, "coordinate", other)
        return answer.record

    result = _verify_with(
        _RewritingPort(port_for(authority), {"record": _swap_coordinate}), record
    )
    assert result.refusal is not None
    assert result.refusal.outcome is PolicyAuthenticityOutcome.RESOLUTION_MALFORMED
    assert "coordinate it was resolved for" in result.refusal.detail


def test_a_descriptor_identity_that_is_not_a_pair_of_strings_is_refused():
    """Guard 97 — ``verification.py:692``, the descriptor identity's exact typing.

    The guard above it refuses an identity that is *absent*. This refuses one that is present
    and not a string — a ``bytes`` adapter id reframes to different bytes, so the body-digest
    reproduction below it would compare a frame nobody signed.
    """

    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415

    authority, record = issued_bounds()
    result = _verify_with(
        _RewritingPort(port_for(authority), {"descriptor_adapter_id": b"ugence.bytes/v1"}),
        record,
    )
    assert result.refusal is not None
    assert result.refusal.outcome is PolicyAuthenticityOutcome.POLICY_PROJECTION_ABSENT
    assert "pair of strings" in result.refusal.detail


def test_a_signed_bound_this_profile_cannot_read_is_refused():
    """Guard 105 — ``verification.py:775``, ``absent``.

    Not reachable by rewriting the projection: gate 14 reproduces the signed body digest from
    it, so a mutated projection is refused one gate earlier as unreproducible. What reaches
    this guard is a bound that is **genuinely signed** and still unreadable — an authority
    issuing a capacity-bounds policy under a schema this profile does not know, which is the
    ordinary consequence of two distributions versioning independently.

    Refusing keeps "verified" meaning the routine evaluated everything it carries forward. A
    bound missing its delta ceiling is not a bound with an unlimited delta.

    This test does not kill guard 105, and is not meant to. Measurement showed the guard is
    **diagnostic-only** under ADR Phase 5 §9.1: without it the same input reaches
    ``entry["max_permitted_delta"]`` inside a deliberate ``except Exception`` backstop
    nineteen lines below, which re-raises as the same ``_BoundsShapeError`` and so the same
    ``POLICY_BOUNDS_MALFORMED`` outcome. Only the message differs. This test is the
    measurement that exclusion rests on: it pins the outcome, so if the backstop ever stops
    covering this case the exclusion fails with it.
    """

    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415
    from _policy_fixtures import make_bounds_policy  # noqa: PLC0415

    @dataclasses.dataclass(frozen=True)
    class _BoundWithoutADeltaCeiling:
        action_type: str
        resource_class: str
        max_permitted_magnitude: int

    authority = bounds_authority()
    policy = make_bounds_policy(
        bounds=(
            _BoundWithoutADeltaCeiling(
                action_type="scale_up",
                resource_class="deploy/checkout-api",
                max_permitted_magnitude=100,
            ),
        )
    )
    record = authority.issue(policy)

    result = _verify_with(port_for(authority), record)
    assert result.refusal is not None, "a bound this profile cannot read was verified"
    assert result.refusal.outcome is PolicyAuthenticityOutcome.POLICY_BOUNDS_MALFORMED
    assert "max_permitted_delta" in result.refusal.detail
