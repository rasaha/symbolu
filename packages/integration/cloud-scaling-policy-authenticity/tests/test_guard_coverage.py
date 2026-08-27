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


# --- canonical.py: the admission helpers ----------------------------------------------
#
# Nine guards, one call each. These are the primitives every field in the package is
# admitted through, and not one of them had been reached: the suite exercised the artifacts
# these helpers protect, never the helpers themselves, so every one could have been deleted
# without a test noticing.


@pytest.mark.parametrize(
    "value",
    ["", "sha256:" + "a" * 64, "A" * 64, "z" * 64, "a" * 63, None, 0, b"a" * 64],
)
def test_a_value_that_is_not_a_bare_policy_digest_is_refused(value):
    """Guard 2 — ``canonical.py:111``, ``not is_policy_digest(value)``.

    The Policy Authority namespace: a bare lowercase 64-hex digest. Note what is refused —
    a ``sha256:``-prefixed value is a *Phase 5A* digest and is refused here, because the two
    namespaces are never interchanged.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_policy_digest,
    )

    with pytest.raises(PolicyAuthenticityFieldError):
        require_policy_digest("policy_body_digest", value)


@pytest.mark.parametrize(
    "value", ["", "a" * 64, "sha256:" + "A" * 64, "sha256:" + "a" * 63, None, 0]
)
def test_a_value_that_is_not_a_phase_5a_digest_is_refused(value):
    """Guard 3 — ``canonical.py:130``, ``not is_phase5a_digest(value)``.

    The mirror of guard 2: a bare 64-hex value is a *policy* digest and is refused where a
    Phase 5A one belongs.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_phase5a_digest,
    )

    with pytest.raises(PolicyAuthenticityFieldError):
        require_phase5a_digest("candidate_digest_fact", value)


def test_text_that_is_not_exactly_a_str_is_refused():
    """Guard 4 — ``canonical.py:146``, ``type(value) is not str``.

    Exact: a ``str`` subclass can override every comparison below it and canonicalizes to
    the same bytes, so the admitted type is the only place the difference survives.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_nfc_text,
    )

    class LyingText(str):
        def __eq__(self, other):  # pragma: no cover - the type gate refuses first
            return True

        __hash__ = str.__hash__

    with pytest.raises(PolicyAuthenticityFieldError) as excinfo:
        require_nfc_text("policy_id", LyingText("p-1"))
    assert "must be a string" in str(excinfo.value) or "str" in str(excinfo.value)


def test_empty_text_is_refused_unless_explicitly_permitted():
    """Guard 5 — ``canonical.py:151``, ``not allow_empty and value == ''``.

    ``allow_empty`` is opt-in per field. An empty identifier that reads as absent in one
    place and as a value in another is the difference this refuses to leave to the caller.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_nfc_text,
    )

    with pytest.raises(PolicyAuthenticityFieldError) as excinfo:
        require_nfc_text("policy_id", "")
    assert "must not be empty" in str(excinfo.value)
    # And the opt-in genuinely opts in, so the guard is not simply unconditional.
    assert require_nfc_text("tenant_id", "", allow_empty=True) == ""


def test_text_that_is_not_nfc_normalized_is_refused():
    """Guard 6 — ``canonical.py:153``, ``normalize('NFC', value) != value``.

    Two spellings of the same identifier digest to different bytes. Refusing the
    unnormalized form rather than normalizing it keeps the caller's bytes and this package's
    bytes identical, which is what makes a digest comparison meaningful.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_nfc_text,
    )

    decomposed = "café"  # 'café' as e + combining acute
    with pytest.raises(PolicyAuthenticityFieldError) as excinfo:
        require_nfc_text("policy_id", decomposed)
    assert "NFC" in str(excinfo.value)


def test_an_identifier_carrying_surrounding_whitespace_is_refused():
    """Guard 7 — ``canonical.py:169``, ``text != text.strip()``."""

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_canonical_identifier,
    )

    with pytest.raises(PolicyAuthenticityFieldError) as excinfo:
        require_canonical_identifier("policy_id", " p-1 ")
    assert "whitespace" in str(excinfo.value)


def test_an_identifier_carrying_control_whitespace_is_refused():
    """Guard 8 — ``canonical.py:171``, control whitespace that is not a plain space.

    Distinct from guard 7, and the distinction is the point: ``"a\\tb"`` survives ``.strip()``
    untouched. A tab or newline inside an identifier renders invisibly in a log and digests
    differently.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_canonical_identifier,
    )

    with pytest.raises(PolicyAuthenticityFieldError) as excinfo:
        require_canonical_identifier("policy_id", "a\tb")
    assert "control whitespace" in str(excinfo.value)


def test_a_naive_instant_is_refused_rather_than_assumed_utc():
    """Guard 10 — ``canonical.py:186``, ``tzinfo is None or utcoffset() is None``.

    This package reads no clock. Every instant it handles was injected by a caller, and an
    instant whose offset nobody stated is one nobody can reconstruct — so it is refused
    rather than assumed to be UTC.
    """

    from datetime import datetime  # noqa: PLC0415

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_aware_utc,
    )

    with pytest.raises(PolicyAuthenticityFieldError) as excinfo:
        require_aware_utc("as_of", datetime(2026, 1, 1, 0, 0))
    assert "timezone-aware" in str(excinfo.value)


def test_a_value_of_the_wrong_exact_type_is_refused():
    """Guard 11 — ``canonical.py:202``, ``type(value) is not expected``."""

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_exact_type,
    )
    from ugence_cloud_scaling_policy_authenticity.errors import (  # noqa: PLC0415
        PolicyAuthenticityExactTypeError,
    )

    with pytest.raises(PolicyAuthenticityExactTypeError):
        require_exact_type("bounds", [1, 2], tuple)
    assert require_exact_type("bounds", (1, 2), tuple) == (1, 2)


# --- identifiers.py: the import-time separations ---------------------------------------
#
# Guards 12-16 are not killable by this operator: each compares two constants, and in the
# installed checkout each comparison is false, so `if False:` is the same program on every
# path this fixture can produce. Four of the five are *not* equivalent mutants, though — see
# ADR Phase 5 §9.2. This package pins `ugence-policy-authority>=0.1.0` and
# `ugence-cloud-scaling-authorization-contracts>=0.1.0`, both open-ended, and four of these
# comparisons have an operand that comes from one of those distributions. Under a resolution
# either pin permits, the condition can be true and the guard fires. Their falsity is a
# property of this installation, not of the program.
#
# The test below is what those classifications rest on: it re-runs every comparison against
# whatever is actually installed, so the exclusions are void the moment they stop holding.


def test_the_import_time_separations_hold_for_the_installed_distributions():
    """The test-time half of the import-time separations (guards 12-16).

    Import-time alone is green in any process that imports a stale wheel, an editable install
    pointing at an older checkout, or a resolution that satisfied a dependency from
    elsewhere. Running them explicitly is what makes the exclusions checkable rather than
    asserted.
    """

    from ugence_cloud_scaling_policy_authenticity import identifiers as ids  # noqa: PLC0415

    # Guard 12 — this package consumes the Policy Authority protocol; it is not a version
    # of it. ``POLICY_AUTHORITY_PROTOCOL_ID`` comes from ``ugence_policy_authority.api``.
    assert ids.VERIFICATION_PROFILE != ids.POLICY_AUTHORITY_PROTOCOL_ID

    # Guard 13 — a verification artifact is not a policy body, so the two digest domains
    # must differ. ``POLICY_BODY_DIGEST_DOMAIN`` is the Policy Authority's.
    from ugence_policy_authority.api import POLICY_BODY_DIGEST_DOMAIN  # noqa: PLC0415

    assert ids.POLICY_AUTHENTICITY_DIGEST_DOMAIN != POLICY_BODY_DIGEST_DOMAIN

    # Guard 14 — three distinct frames. Collapsing any two would let a recorded fact occupy
    # an attested frame. All three are this package's own literals.
    assert (
        len(
            {
                ids.POLICY_AUTHENTICITY_DIGEST_DOMAIN,
                ids.POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
                ids.POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
            }
        )
        == 3
    )

    # Guard 15 — collapsing these would let a revoke-only key authenticate an issued policy.
    # Both are members of the Policy Authority's own ``KeyEntitlement``.
    assert ids.REQUIRED_KEY_ENTITLEMENT is not ids.FORBIDDEN_KEY_ENTITLEMENT

    # Guard 16 — gate 16 selects an authenticated bound by this vocabulary and fails closed
    # rather than selecting by an unratified one. The left operand is Phase 5A's.
    from ugence_cloud_scaling_authorization_contracts import (  # noqa: PLC0415
        CANONICAL_ACTION_TYPES,
    )

    assert CANONICAL_ACTION_TYPES == ids._RATIFIED_ACTION_TYPES
