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

from _policy_fixtures import (
    T_CANDIDATE,
    T_MID,
    bounds_authority,
    issued,
    issued_bounds,
    port_for,
    verifier_for,
)
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


@pytest.mark.adversarial
@pytest.mark.parametrize("domain", ["", 0, None, b"cloud_scaling"])
def test_a_framed_digest_domain_that_is_not_a_non_empty_str_is_refused(domain):
    """Guard 1 — ``canonical.py:89``, ``type(domain) is not str or not domain``.

    The domain tag is the whole point of the frame: it is what keeps this package's artifact
    digests from ever being readable as Policy Authority body digests. An empty or absent
    domain collapses that separation, so it is refused rather than defaulted.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import framed_digest  # noqa: PLC0415

    with pytest.raises(PolicyAuthenticityFieldError):
        framed_digest(domain=domain, body={"a": 1})


@pytest.mark.adversarial
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
    with pytest.raises(PolicyAuthenticityFieldError):
        require_aware_utc("as_of", forged)


# --- resolution_port.py ---------------------------------------------------------------


@pytest.mark.adversarial
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
    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthorityResolutionPort(
            registry=None,
            signature_verifier=genuine._signature_verifier,
            adapters=genuine._adapters,
        )


# --- verification.py: the verifier's own configuration --------------------------------


@pytest.mark.adversarial
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

    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthenticityVerifier(resolution_port=PortWithoutTheMethod())


@pytest.mark.adversarial
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

    with pytest.raises(TypeError):
        PolicyAuthenticityResult(
            verified_policy=genuine.verified_policy,
            resolution=LookAlikeResolution(genuine.resolution),
        )


# --- verified.py: the R-3 gate on the artifact ----------------------------------------


@pytest.mark.adversarial
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
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        type(genuine)(
            **fields,
            artifact_digest=_recompute(fields),
            construction_token=genuine.construction_token,
        )


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


@pytest.mark.adversarial
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


@pytest.mark.adversarial
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


@pytest.mark.adversarial
def test_a_signed_bound_this_profile_cannot_read_is_refused():
    """Guard 105 — ``verification.py:775``, ``absent``. **The last obstacle before a mint.**

    A bound that is genuinely signed and still unreadable: an authority issuing capacity
    bounds under a schema this profile does not know, which is the ordinary consequence of
    two distributions versioning independently.

    Neutralised, this guard does not produce a different refusal — the verifier mints a
    **VERIFIED** artifact whose ``capacity_bounds_fact`` carries a delta ceiling no signature
    ever covered, and gate 16 then reconciles a candidate against it. That is R-8 defeated
    through a guard this branch had recorded as mattering only to the message.

    The isolating input is in ``test_a_projection_entry_that_lies_about_its_own_keys...``
    below; this test covers the plainer half, where the published projection is honest and
    the signed bound is simply short a field.

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


# --- canonical.py: the admission helpers ----------------------------------------------
#
# Nine guards, one call each. These are the primitives every field in the package is
# admitted through, and not one of them had been reached: the suite exercised the artifacts
# these helpers protect, never the helpers themselves, so every one could have been deleted
# without a test noticing.


@pytest.mark.adversarial
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


@pytest.mark.adversarial
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


@pytest.mark.adversarial
def test_text_that_is_not_exactly_a_str_is_refused():
    """Guard 4 — ``canonical.py:146``, ``type(value) is not str``.

    Exact: a ``str`` subclass can override every comparison below it and canonicalizes to
    the same bytes, so the admitted type is the only place the difference survives.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_nfc_text,
    )

    # Not a ``str`` subclass: one that lies in ``__eq__`` satisfies the empty-string check
    # on the next line and is refused there with the same error class, so it measures that
    # guard rather than this one. A plain ``int`` reaches ``unicodedata.normalize`` instead,
    # which raises ``TypeError`` — a different class, and therefore this guard's own work.
    with pytest.raises(PolicyAuthenticityFieldError):
        require_nfc_text("policy_id", 123)


@pytest.mark.adversarial
def test_empty_text_is_refused_unless_explicitly_permitted():
    """Guard 5 — ``canonical.py:151``, ``not allow_empty and value == ''``.

    ``allow_empty`` is opt-in per field. An empty identifier that reads as absent in one
    place and as a value in another is the difference this refuses to leave to the caller.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_nfc_text,
    )

    with pytest.raises(PolicyAuthenticityFieldError):
        require_nfc_text("policy_id", "")
    # And the opt-in genuinely opts in, so the guard is not simply unconditional.
    assert require_nfc_text("tenant_id", "", allow_empty=True) == ""


@pytest.mark.adversarial
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
    with pytest.raises(PolicyAuthenticityFieldError):
        require_nfc_text("policy_id", decomposed)


@pytest.mark.adversarial
def test_an_identifier_carrying_surrounding_whitespace_is_refused():
    """Guard 7 — ``canonical.py:169``, ``text != text.strip()``."""

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_canonical_identifier,
    )

    with pytest.raises(PolicyAuthenticityFieldError):
        require_canonical_identifier("policy_id", " p-1 ")


@pytest.mark.adversarial
def test_an_identifier_carrying_control_whitespace_is_refused():
    """Guard 8 — ``canonical.py:171``, control whitespace that is not a plain space.

    Distinct from guard 7, and the distinction is the point: ``"a\\tb"`` survives ``.strip()``
    untouched. A tab or newline inside an identifier renders invisibly in a log and digests
    differently.
    """

    from ugence_cloud_scaling_policy_authenticity.canonical import (  # noqa: PLC0415
        require_canonical_identifier,
    )

    with pytest.raises(PolicyAuthenticityFieldError):
        require_canonical_identifier("policy_id", "a\tb")


@pytest.mark.adversarial
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

    with pytest.raises(PolicyAuthenticityFieldError):
        require_aware_utc("as_of", datetime(2026, 1, 1, 0, 0))


@pytest.mark.adversarial
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


@pytest.mark.invariant
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


# --- resolution_port.py: the port's own composition ------------------------------------


def _genuine_port_parts():
    authority = bounds_authority()
    port = port_for(authority)
    return port._registry, port._signature_verifier, port._adapters


@pytest.mark.adversarial
def test_a_resolution_port_built_without_a_signature_verifier_is_refused():
    """Guard 18 — ``resolution_port.py:195``, ``signature_verifier is None``.

    There is no default key ring, no ambient trust store and no permissive fallback, so the
    absence is refused rather than filled in.
    """

    from ugence_cloud_scaling_policy_authenticity.resolution_port import (  # noqa: PLC0415
        PolicyAuthorityResolutionPort,
    )

    registry, _, adapters = _genuine_port_parts()
    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthorityResolutionPort(
            registry=registry, signature_verifier=None, adapters=adapters
        )


@pytest.mark.adversarial
@pytest.mark.parametrize("missing", ["get_issued", "revocations_for"])
def test_a_registry_missing_a_required_method_is_refused(missing):
    """Guard 20 — ``resolution_port.py:206``, ``not hasattr(registry, attribute)``.

    Parametrised over both attributes on purpose: a single case would leave the loop's other
    iteration unexercised, and "the registry has one of the two methods" is exactly the
    half-configured composition root this refuses.
    """

    from ugence_cloud_scaling_policy_authenticity.resolution_port import (  # noqa: PLC0415
        PolicyAuthorityResolutionPort,
    )

    registry, verifier, adapters = _genuine_port_parts()

    class PartialRegistry:
        pass

    partial = PartialRegistry()
    for name in ("get_issued", "revocations_for"):
        if name != missing:
            setattr(partial, name, getattr(registry, name))

    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthorityResolutionPort(
            registry=partial, signature_verifier=verifier, adapters=adapters
        )


@pytest.mark.adversarial
def test_a_signature_verifier_that_cannot_verify_is_refused():
    """Guard 21 — ``resolution_port.py:210``, ``not hasattr(verifier, 'verify')``."""

    from ugence_cloud_scaling_policy_authenticity.resolution_port import (  # noqa: PLC0415
        PolicyAuthorityResolutionPort,
    )

    registry, _, adapters = _genuine_port_parts()

    class VerifierWithoutVerify:
        pass

    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthorityResolutionPort(
            registry=registry,
            signature_verifier=VerifierWithoutVerify(),
            adapters=adapters,
        )


@pytest.mark.adversarial
def test_a_reference_grade_port_cannot_reach_a_production_determination(monkeypatch):
    """Guard 22 — ``resolution_port.py:354``, the reference-grade refusal.

    ``REFERENCE_GRADE_PORTS`` is an empty tuple today, and documented as a place for a later
    reference port to be named. An empty tuple short-circuits, so no input in this
    distribution reaches the ``isinstance`` — which would make this look like an equivalent
    mutant and leave the guard unmeasured until the day someone adds a port to the tuple and
    discovers whether it ever worked.

    Populating the extension point is what measures it. Note the deliberate ``isinstance``:
    here the class is what is being *refused*, so exact-type matching would be the hole
    rather than the guard, and the subclass case below is the reason.
    """

    from ugence_cloud_scaling_policy_authenticity import resolution_port as rp  # noqa: PLC0415

    class AReferencePort:
        is_production_authoritative = True

    class ASubclassOfOne(AReferencePort):
        pass

    monkeypatch.setattr(rp, "REFERENCE_GRADE_PORTS", (AReferencePort,))

    for port in (AReferencePort(), ASubclassOfOne()):
        with pytest.raises(PolicyAuthenticityConfigurationError):
            rp.require_production_resolution_port(port)


# --- verified.py: the artifact's own integrity -----------------------------------------
#
# Each of these builds a genuine artifact, changes one field, and re-derives the artifact
# digest and construction token so the change reaches the guard under test rather than dying
# at the self-digest. That is what a forger with the canonicalizer would do.


def _artifact_with(**overrides):
    """A genuine artifact's fields with ``**overrides``, digest re-derived."""

    from test_verified_artifact import _field_values, _genuine, _recompute  # noqa: PLC0415

    genuine = _genuine()
    fields = _field_values(genuine)
    fields.update(overrides)
    return genuine, fields, _recompute(fields)


def _build(genuine, fields, digest):
    return type(genuine)(
        **fields, artifact_digest=digest, construction_token=genuine.construction_token
    )


@pytest.mark.adversarial
def test_an_artifact_naming_an_unadmitted_signature_algorithm_is_refused():
    """Guard 34 — ``verified.py:476``, ``signature_alg not in SUPPORTED_...``.

    The admitted set is closed. The algorithm name is what a later reader has to go on, so
    one outside the set would reach them as though this routine had considered it.
    """

    genuine, fields, digest = _artifact_with(signature_alg="rsa-md5")
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        _build(genuine, fields, digest)


@pytest.mark.adversarial
def test_a_capacity_bounds_fact_that_is_not_a_tuple_is_refused():
    """Guard 37 — ``verified.py:496``, ``type(capacity_bounds_fact) is not tuple``.

    The artifact is frozen and digest-covered; a list member would let the value drift out
    from under a digest that already covered it.
    """

    # A *populated* list. An empty one is caught by the guard on the next line — "must be
    # None rather than an empty tuple" — with the same error class, so it would measure that
    # guard instead of this one.
    from ugence_cloud_scaling_policy_authenticity import VerifiedCapacityBound  # noqa: PLC0415

    bound = VerifiedCapacityBound(
        action_type="scale_up",
        resource_class="deploy/checkout-api",
        max_permitted_magnitude=100,
        max_permitted_delta=25,
    )
    genuine, fields, digest = _artifact_with(capacity_bounds_fact=[bound])
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        _build(genuine, fields, digest)


@pytest.mark.adversarial
def test_an_empty_capacity_bounds_fact_is_refused_in_favour_of_none():
    """Guard 38 — ``verified.py:501``, ``not self.capacity_bounds_fact``.

    "This policy states no bound" and "this policy states zero bounds" would otherwise be two
    spellings of one fact, and a consumer reading the second as the first would treat an
    unbounded policy as a bounded one.
    """

    genuine, fields, digest = _artifact_with(capacity_bounds_fact=())
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        _build(genuine, fields, digest)


@pytest.mark.adversarial
def test_a_bound_that_is_not_exactly_a_verified_capacity_bound_is_refused():
    """Guard 39 — ``verified.py:508``, ``type(bound) is not VerifiedCapacityBound``."""

    genuine, fields, digest = _artifact_with(
        capacity_bounds_fact=({"action_type": "scale_up"},)
    )
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        _build(genuine, fields, digest)


@pytest.mark.adversarial
def test_an_artifact_whose_digest_does_not_cover_its_facts_is_refused():
    """Guard 42 — ``verified.py:534``, ``artifact_digest != expected``.

    The self-digest, recomputed from the bound facts rather than read back. Every other test
    in this group re-derives the digest precisely so it can reach the guard it is aiming at;
    this one is what makes that necessary.
    """

    genuine, fields, _ = _artifact_with()
    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        _build(genuine, fields, "c" * 64)


@pytest.mark.adversarial
@pytest.mark.parametrize("name", ["resolved_as_of_fact", "trust_configuration_digest"])
def test_reading_a_recorded_fact_through_verified_fact_is_refused(name):
    """Guard 43 — ``verified.py:675``, ``name in RECORDED_FACT_NAMES``.

    A recorded fact is carried and digest-covered, and nothing checked it. Reading one
    through ``verified_fact()`` would let a caller treat it as attested; the refusal says so
    at the call site, which is where the mistake is made.
    """

    from test_verified_artifact import _genuine  # noqa: PLC0415

    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        _genuine().verified_fact(name)


@pytest.mark.adversarial
def test_a_look_alike_is_refused_at_the_consumption_boundary():
    """Guard 46 — ``verified.py:737``, ``type(value) is not VerifiedPolicyAuthenticity``.

    Distinct from the existing ``object.__new__`` test, which produces the *exact* type and
    therefore passes this guard to be caught by the provenance check below it. This is the
    other half: a duck-typed look-alike carrying every attribute a consumer reads.
    """

    from ugence_cloud_scaling_policy_authenticity import (  # noqa: PLC0415
        require_verified_policy_authenticity,
    )
    from test_verified_artifact import _genuine  # noqa: PLC0415

    genuine = _genuine()

    # Every field of a genuine artifact, so the field-presence check behind this guard has
    # nothing to complain about and only the exact-type gate can refuse it.
    import dataclasses as _dc  # noqa: PLC0415

    class LookAlike:
        def __init__(self, real):
            for field in _dc.fields(real):
                setattr(self, field.name, getattr(real, field.name))

    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        require_verified_policy_authenticity(LookAlike(genuine))


@pytest.mark.invariant
def test_the_fact_partition_is_total_and_disjoint():
    """Guards 50 and 51 — ``verified.py:775`` and ``:780``, the partition's import guards.

    Both are equivalent mutants and both are worth keeping. Every operand is a frozen set or
    a ``dataclasses.fields`` reading of a class in this module, in this distribution, so no
    dependency resolution can move either side and the conditions are false in every program
    this package can be part of.

    They are not idle, though: what they defend is the invariant that adding a field to the
    artifact without classifying it fails at import rather than shipping a fact that is
    digest-covered and unattested. This re-runs both against the module as it stands, so the
    exclusions are void the moment the partition stops holding.
    """

    from dataclasses import fields as dataclass_fields  # noqa: PLC0415

    from ugence_cloud_scaling_policy_authenticity import verified as v  # noqa: PLC0415

    # Guard 50 — a fact cannot be both verified and recorded.
    assert not (v.VERIFIED_FACT_NAMES & v.RECORDED_FACT_NAMES)

    # Guard 51 — every declared field is classified as one or the other.
    unpartitionable = {"artifact_digest", "construction_token"}
    declared = {f.name for f in dataclass_fields(v.VerifiedPolicyAuthenticity)} - unpartitionable
    assert (v.VERIFIED_FACT_NAMES | v.RECORDED_FACT_NAMES) == declared


# --- verification.py: the result pair and the verifier's entry ------------------------


@pytest.mark.adversarial
def test_a_refusal_carrying_a_foreign_outcome_type_is_refused():
    """Guard 52 — ``verification.py:152``, ``type(self.outcome) is not _Outcome``.

    The outcome is the one field a consumer is entitled to branch on, so a look-alike
    carrying the right ``.value`` would be read as a decision this package never made.
    """

    from ugence_cloud_scaling_policy_authenticity import (  # noqa: PLC0415
        PolicyAuthenticityRefusal,
    )

    class LookAlikeOutcome:
        value = "VERIFIED"

    with pytest.raises(TypeError):
        PolicyAuthenticityRefusal(outcome=LookAlikeOutcome(), detail="")


@pytest.mark.adversarial
def test_a_result_carrying_a_foreign_verified_artifact_type_is_refused():
    """Guard 56 — ``verification.py:196``, the verified half's exact type.

    Distinct from guard 46, which defends the *consumption* boundary; this defends the
    result's own construction, before ``require_verified_policy_authenticity`` is reached.
    """

    authority, record = issued_bounds()
    genuine = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )

    class LookAlikeArtifact:
        def __init__(self, real):
            for field in dataclasses.fields(real):
                setattr(self, field.name, getattr(real, field.name))

    with pytest.raises(TypeError):
        PolicyAuthenticityResult(
            verified_policy=LookAlikeArtifact(genuine.verified_policy),
            resolution=genuine.resolution,
        )


@pytest.mark.adversarial
def test_a_result_carrying_a_foreign_refusal_type_is_refused():
    """Guard 58 — ``verification.py:214``, the refusing half's exact type."""

    class LookAlikeRefusal:
        outcome = "RESOLUTION_MALFORMED"
        detail = ""

    with pytest.raises(TypeError):
        PolicyAuthenticityResult(refusal=LookAlikeRefusal())


@pytest.mark.adversarial
def test_a_result_pairing_two_genuine_halves_about_different_policies_is_refused():
    """Guard 59 — ``verification.py:240``, the pair's coordinate agreement.

    Both halves are individually genuine: a real determination for policy A and a real
    resolution for policy B are each valid objects. A consumer reading the body out of
    ``resolution`` while trusting the coordinate on ``verified_policy`` would then be reading
    a body the proof does not cover. The pair is the thing that is wrong, and only this guard
    looks at it.
    """

    authority, record = issued_bounds()
    genuine = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    other_coordinate = dataclasses.replace(
        genuine.resolution.requested_coordinate, policy_id="some.other-policy"
    )
    elsewhere = _bypass(genuine.resolution, requested_coordinate=other_coordinate)

    with pytest.raises(VerifiedPolicyArtifactIntegrityError):
        PolicyAuthenticityResult(
            verified_policy=genuine.verified_policy, resolution=elsewhere
        )


def _bypass(obj, **overrides):
    """A field-for-field copy with ``**overrides``, skipping ``__post_init__``."""

    forged = object.__new__(type(obj))
    for field in dataclasses.fields(obj):
        object.__setattr__(forged, field.name, getattr(obj, field.name))
    for name, value in overrides.items():
        object.__setattr__(forged, name, value)
    return forged


@pytest.mark.adversarial
def test_an_expected_tenant_id_that_is_not_exactly_a_str_is_refused():
    """Guard 69 — ``verification.py:419``, the caller's tenant argument.

    A refusal rather than a raise: this is inside the verify path, so the caller gets a typed
    ``UNSUPPORTED_EXACT_TYPE`` outcome like any other input it declines to act on.
    """

    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415

    authority, record = issued_bounds()
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=123,
        as_of=T_MID,
    )
    assert result.refusal is not None
    assert result.refusal.outcome is PolicyAuthenticityOutcome.UNSUPPORTED_EXACT_TYPE


@pytest.mark.adversarial
def test_a_verifier_built_without_a_resolution_port_is_refused():
    """Guard 64 — ``verification.py:310``, ``resolution_port is None``.

    There is no default port, no ambient policy registry and no permissive fallback.

    Classified ``diagnostic-only``, and the isolation attempt is why: ``None`` cannot reach
    this guard without also failing ``hasattr(port, 'resolve_policy_version')`` five lines
    below, which raises the same ``PolicyAuthenticityConfigurationError``. No input isolates
    it. The guard earns its place by telling a composition root that a port is *missing*
    rather than that its port is the wrong shape.
    """

    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthenticityVerifier(resolution_port=None)


# --- verification.py: the resolution the authority returned ----------------------------
#
# Thirteen guards on the shape of a RESOLVED answer. Each is reached by taking a genuine,
# signed, correct resolution and changing exactly one field of it — the shape of a
# compromised or merely buggy composition-root component, and the reason this package
# re-checks a resolution it did not construct.


def _refusal_for(**rewrite):
    """Verify a genuine bounds policy through a port that rewrites the answer."""

    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415

    authority, record = issued_bounds()
    result = _verify_with(_RewritingPort(port_for(authority), rewrite), record)
    assert result.refusal is not None, "the rewritten resolution was verified"
    return result.refusal, PolicyAuthenticityOutcome


@pytest.mark.adversarial
def test_the_historicity_guard_fires_when_the_authority_drops_the_historicity_term(
    tmp_path,
):
    """Guard 77 — ``verification.py:487``, ``resolution.historical``.

    Excluded as ``diagnostic-only``: removing it leaves ``implies_current_validity`` False
    on the next line, refusing with the same outcome. True of the installed Policy
    Authority, where the property is ``resolved and not historical`` — and that property is
    upstream's, under ``>=0.1.0``. The successor is only redundant *because* the property
    carries the historicity term. A 0.2.0 that drops it — ``return self.resolved``, a
    plausible simplification once historicity is modelled on the answer itself — makes the
    successor silent on a genuinely historical answer.

    Measured against a real revocation, resolved at an instant before it:

    ==========================  =======================================
    undrifted 0.1.0             refused HISTORICAL_RESOLUTION_REFUSED
    0.2.0, guard present        refused HISTORICAL_RESOLUTION_REFUSED
    0.2.0, guard neutralised    refused INVARIANT_VIOLATION
    ==========================  =======================================

    A changed typed pair, so the guard is authority-bearing under §9.1. Removing it does not
    lose a message; it loses the clean refusal and reaches the artifact-pairing invariant at
    ``verification.py:266`` instead, which reports an internal integrity failure for what is
    an ordinary, expected, refusable answer.
    """

    outcomes = _verify_a_historical_answer(tmp_path, neutralise_guard=False)
    assert outcomes["undrifted"] == "REFUSED HISTORICAL_RESOLUTION_REFUSED", (
        f"the control did not refuse as expected: {outcomes['undrifted']}"
    )
    assert outcomes["drifted"] == "REFUSED HISTORICAL_RESOLUTION_REFUSED", (
        f"a historical answer was not refused by this guard: {outcomes['drifted']}"
    )


@pytest.mark.invariant
def test_removing_the_historicity_guard_changes_the_refusal(tmp_path):
    """The other half of guard 77: what removing it costs."""

    outcomes = _verify_a_historical_answer(tmp_path, neutralise_guard=True)
    assert outcomes["drifted"] == "REFUSED INVARIANT_VIOLATION", (
        "removing the guard no longer changes the typed refusal; if this matches the "
        f"guarded outcome the diagnostic-only argument is back in play: {outcomes['drifted']}"
    )


@pytest.mark.adversarial
def test_the_adapter_identity_guard_fires_when_the_frame_stops_binding_the_adapter(
    tmp_path,
):
    """Guard 99 — ``verification.py:706``, ``adapter_id != record.adapter_id``.

    Excluded as ``diagnostic-only``: any adapter id that trips this guard also fails the
    digest reproduction below it, with the same outcome, because the adapter id is an input
    to the frame that digest is taken over. That is true only while the authority's frame
    *binds* adapter identity — ``framed_body_bytes`` puts ``"adapter": adapter_id`` in the
    framed mapping, and that mapping is upstream's, under ``>=0.1.0``.

    A 0.2.0 that stops binding it — moving adapter identity out of the frame and onto the
    record, say — makes the reproduced digest independent of the adapter. A projection
    naming a different adapter then reproduces the *correct* digest, and this guard is the
    only thing left between that projection and a verified artifact.

    ==========================  ===========================================
    undrifted 0.1.0             refused POLICY_PROJECTION_DIGEST_MISMATCH
    0.2.0, guard present        refused POLICY_PROJECTION_DIGEST_MISMATCH
    0.2.0, guard neutralised    **VERIFIED**
    ==========================  ===========================================

    Not a changed refusal: a mint. Under a resolution the pin admits, removing this guard
    lets a descriptor that names one adapter be verified against a record that names
    another — the disagreement the comment above it says must not pass.
    """

    outcomes = _verify_a_reframed_adapter(tmp_path, neutralise_guard=False)
    assert outcomes["undrifted"] == "REFUSED POLICY_PROJECTION_DIGEST_MISMATCH", (
        f"the control did not refuse as expected: {outcomes['undrifted']}"
    )
    assert outcomes["drifted"] == "REFUSED POLICY_PROJECTION_DIGEST_MISMATCH", (
        f"a projection naming another adapter was not refused: {outcomes['drifted']}"
    )


@pytest.mark.invariant
def test_removing_the_adapter_identity_guard_mints(tmp_path):
    """The other half of guard 99, and the reason it is the more serious of the two."""

    outcomes = _verify_a_reframed_adapter(tmp_path, neutralise_guard=True)
    assert outcomes["drifted"] == "VERIFIED", (
        "removing the guard no longer mints; if it now refuses, the reproduction below it "
        f"is binding the adapter again and this measurement is stale: {outcomes['drifted']}"
    )


#: Source of the probe the guard-77 measurements run: a real revocation, resolved before it.
HISTORICAL_ANSWER_PROBE = (
    "import sys\n"
    "sys.path.insert(0, PKG_TESTS)\n"
    "from _policy_fixtures import issued, revoke, T_MID, T_TO, ONE_SECOND\n"
    "from test_historical_refusal import HistoricalAllowingPort\n"
    "from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityVerifier\n"
    "authority, record = issued()\n"
    "revoke(authority, record, revoked_at=T_TO - ONE_SECOND)\n"
    "port = HistoricalAllowingPort(authority=authority)\n"
    "result = PolicyAuthenticityVerifier(resolution_port=port).verify(\n"
    "    coordinate=record.coordinate,\n"
    "    expected_reference_tenant_id=record.coordinate.tenant_id,\n"
    "    as_of=T_MID,\n"
    ")\n"
    "print('VERIFIED' if result.refusal is None\n"
    "      else 'REFUSED ' + result.refusal.outcome.name)\n"
)

#: Source of the probe the guard-99 measurements run.
REFRAMED_ADAPTER_PROBE = (
    "import sys\n"
    "sys.path.insert(0, PKG_TESTS)\n"
    "from _policy_fixtures import issued_bounds, port_for\n"
    "from test_guard_coverage import _RewritingPort, _verify_with\n"
    "authority, record = issued_bounds()\n"
    "result = _verify_with(\n"
    "    _RewritingPort(port_for(authority),\n"
    "                   {'descriptor_adapter_id': 'ugence.some-other-adapter/v1'}),\n"
    "    record,\n"
    ")\n"
    "print('VERIFIED' if result.refusal is None\n"
    "      else 'REFUSED ' + result.refusal.outcome.name)\n"
)


def _verify_a_historical_answer(tmp_path, *, neutralise_guard):
    """Guard 77 under a 0.2.0 whose `implies_current_validity` drops the historicity term."""

    return _measure_under_a_drifted_authority(
        tmp_path,
        edits=(
            (
                "core/records.py",
                "        return self.resolved and not self.historical",
                "        return self.resolved",
            ),
        ),
        guard="if resolution.historical:",
        neutralise_guard=neutralise_guard,
        probe=HISTORICAL_ANSWER_PROBE,
    )


def _verify_a_reframed_adapter(tmp_path, *, neutralise_guard):
    """Guard 99 under a 0.2.0 whose framed body digest stops binding adapter identity."""

    return _measure_under_a_drifted_authority(
        tmp_path,
        edits=(("core/canonical.py", '            "adapter": adapter_id,\n', ""),),
        guard="if adapter_id != record.adapter_id:",
        neutralise_guard=neutralise_guard,
        probe=REFRAMED_ADAPTER_PROBE,
    )


def _measure_under_a_drifted_authority(
    tmp_path, *, edits, guard, neutralise_guard, probe
):
    """Run the same verification against 0.1.0 and against a drifted 0.2.0.

    The 0.2.0 is the real Policy Authority source with the named edits applied, so what is
    measured is a distribution the ``>=0.1.0`` pin admits rather than a stub standing in for
    one. Each edit is asserted to match exactly once, so an upstream rename fails the test
    instead of quietly producing an undrifted copy.
    """

    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    declared = os.environ.get("UGENCE_REPO_ROOT")
    repo = Path(declared).resolve() if declared else Path(__file__).resolve().parents[4]
    here = Path(__file__).resolve().parent

    authority = tmp_path / "policy-authority-0.3.0" / "ugence_policy_authority"
    shutil.copytree(
        repo / "packages/policy-authority/src/ugence_policy_authority",
        authority,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    init = authority / "__init__.py"
    init.write_text(
        init.read_text(encoding="utf-8").replace(
            '__version__ = "0.3.0"', '__version__ = "0.4.0"'
        ),
        encoding="utf-8",
    )
    for relative, old, new in edits:
        path = authority / relative
        body = path.read_text(encoding="utf-8")
        assert body.count(old) == 1, (
            f"{relative}: expected exactly one {old!r}; the drift this resolution "
            "introduces may not have been introduced at all"
        )
        path.write_text(body.replace(old, new), encoding="utf-8")

    package = tmp_path / "phase5b" / "ugence_cloud_scaling_policy_authenticity"
    shutil.copytree(
        here.parent / "src" / "ugence_cloud_scaling_policy_authenticity",
        package,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    if neutralise_guard:
        path = package / "verification.py"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        marked = [i for i, line in enumerate(lines) if line.strip() == guard]
        assert len(marked) == 1, f"{guard!r} is not uniquely located: {marked}"
        indent = " " * (len(lines[marked[0]]) - len(lines[marked[0]].lstrip()))
        lines[marked[0]] = f"{indent}if False:  # neutralised, as the sweep would\n"
        path.write_text("".join(lines), encoding="utf-8")

    script = tmp_path / "drifted_authority_probe.py"
    script.write_text(f"PKG_TESTS = {str(here)!r}\n" + probe, encoding="utf-8")

    def _run(roots):
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=300,
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join([*roots, *(p for p in sys.path if p)]),
                "UGENCE_REPO_ROOT": str(repo),
            },
        )
        output = result.stdout.strip().splitlines()
        assert output, f"the probe printed nothing: {result.stderr[-600:]}"
        return output[-1]

    return {
        "undrifted": _run([str(package.parent)]),
        "drifted": _run([str(package.parent), str(authority.parent)]),
    }


@pytest.mark.adversarial
def test_a_historical_resolution_is_refused():
    """Guard 77 — ``verification.py:487``, ``resolution.historical``."""

    refusal, outcomes = _refusal_for(historical=True)
    assert refusal.outcome is outcomes.HISTORICAL_RESOLUTION_REFUSED


@pytest.mark.adversarial
def test_the_current_validity_guard_fires_when_the_authority_returns_a_truthy_flag(
    tmp_path,
):
    """Guard 78 — ``verification.py:494``, ``implies_current_validity is not True``.

    Excluded as ``unreachable-behind-earlier-guard``: the property is ``resolved and not
    historical``, both halves are gated above, so nothing can reach a resolution that is
    non-historical, resolved, and still not ``True``. Every step of that is true of the
    *installed* Policy Authority — and the property is defined in it
    (``core/records.py:334``), a separate distribution under an open-ended ``>=0.1.0`` pin.
    The exclusion was a statement about one resolution, which is precisely what ADR Phase 5
    §9.2 refuses to accept for ``equivalent-mutant`` and now refuses here too.

    ``is not True`` reads like a defence against a truthy non-``True``, and it is one. A
    0.2.0 that returns an ``int`` flag rather than the ``bool`` singleton — an ordinary
    refactor, and the property is annotated ``-> bool`` only by convention — passes the
    status gate and the historicity gate and arrives here as ``1``.

    Measured against a resolution built from the real Policy Authority source:

    ==========================  ==========================================
    undrifted 0.1.0             VERIFIED
    0.2.0, guard present        refused HISTORICAL_RESOLUTION_REFUSED
    0.2.0, guard neutralised    refused INVARIANT_VIOLATION
    ==========================  ==========================================

    A changed typed pair, so the guard is authority-bearing under §9.1. The neutralised case
    is the worse of the two: the pairing invariant at ``verification.py:266`` catches it
    instead, which reports an internal integrity failure where the guard would have given a
    caller the specific, actionable refusal.
    """

    outcomes = _verify_under_a_drifted_validity_flag(tmp_path, neutralise_guard=False)
    assert outcomes["undrifted"] == "VERIFIED", (
        "the control did not verify, so the drifted runs prove nothing about this guard: "
        f"{outcomes['undrifted']}"
    )
    assert outcomes["drifted"] == "REFUSED HISTORICAL_RESOLUTION_REFUSED", (
        "a resolution whose implies_current_validity is truthy but not True was not refused "
        f"by this guard: {outcomes['drifted']}"
    )


@pytest.mark.invariant
def test_removing_the_current_validity_guard_changes_the_refusal(tmp_path):
    """The other half of guard 78: what the guard is worth.

    Kept separate so a failure says which half broke — that the guard fires, or that
    removing it matters.
    """

    outcomes = _verify_under_a_drifted_validity_flag(tmp_path, neutralise_guard=True)
    assert outcomes["drifted"] == "REFUSED INVARIANT_VIOLATION", (
        "removing the guard no longer changes the typed refusal; if this now matches the "
        f"guarded outcome the exclusion argument is back in play: {outcomes['drifted']}"
    )


#: Source of the probe both guard-78 measurements run.
VALIDITY_FLAG_PROBE = (
    "import sys\n"
    "sys.path.insert(0, PKG_TESTS)\n"
    "from _policy_fixtures import issued_bounds, port_for, T_MID\n"
    "from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityVerifier\n"
    "authority, record = issued_bounds()\n"
    "result = PolicyAuthenticityVerifier(resolution_port=port_for(authority)).verify(\n"
    "    coordinate=record.coordinate,\n"
    "    expected_reference_tenant_id=record.coordinate.tenant_id,\n"
    "    as_of=T_MID,\n"
    ")\n"
    "print('VERIFIED' if result.refusal is None\n"
    "      else 'REFUSED ' + result.refusal.outcome.name)\n"
)


def _verify_under_a_drifted_validity_flag(tmp_path, *, neutralise_guard):
    """Run a genuine verification twice: against 0.1.0, and against a drifted 0.2.0.

    The 0.2.0 is the real Policy Authority source with one edit — the property returns an
    ``int`` — so what is measured is a distribution the pin admits, not a stub standing in
    for one.
    """

    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    declared = os.environ.get("UGENCE_REPO_ROOT")
    repo = Path(declared).resolve() if declared else Path(__file__).resolve().parents[4]
    here = Path(__file__).resolve().parent

    authority = tmp_path / "policy-authority-0.3.0" / "ugence_policy_authority"
    shutil.copytree(
        repo / "packages/policy-authority/src/ugence_policy_authority",
        authority,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    init = authority / "__init__.py"
    init.write_text(
        init.read_text(encoding="utf-8").replace(
            '__version__ = "0.3.0"', '__version__ = "0.4.0"'
        ),
        encoding="utf-8",
    )
    records = authority / "core/records.py"
    body = records.read_text(encoding="utf-8")
    ratified = "        return self.resolved and not self.historical"
    assert body.count(ratified) == 1, (
        "implies_current_validity is no longer spelled as expected upstream, so this "
        "resolution may not introduce the drift it claims to"
    )
    records.write_text(
        body.replace(ratified, "        return int(self.resolved and not self.historical)"),
        encoding="utf-8",
    )

    package = tmp_path / "phase5b" / "ugence_cloud_scaling_policy_authenticity"
    shutil.copytree(
        here.parent / "src" / "ugence_cloud_scaling_policy_authenticity",
        package,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    if neutralise_guard:
        path = package / "verification.py"
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        marked = [
            i for i, line in enumerate(lines)
            if line.strip() == "if resolution.implies_current_validity is not True:"
        ]
        assert len(marked) == 1, f"guard 78 is not where this test expects it: {marked}"
        indent = " " * (len(lines[marked[0]]) - len(lines[marked[0]].lstrip()))
        lines[marked[0]] = f"{indent}if False:  # neutralised, as the sweep would\n"
        path.write_text("".join(lines), encoding="utf-8")

    probe = tmp_path / "validity_flag_probe.py"
    probe.write_text(
        f"PKG_TESTS = {str(here)!r}\n" + VALIDITY_FLAG_PROBE, encoding="utf-8"
    )

    def _run(roots):
        result = subprocess.run(
            [sys.executable, str(probe)],
            capture_output=True,
            text=True,
            timeout=300,
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    [*roots, *(p for p in sys.path if p)]
                ),
                "UGENCE_REPO_ROOT": str(repo),
            },
        )
        output = result.stdout.strip().splitlines()
        assert output, f"the probe printed nothing: {result.stderr[-600:]}"
        return output[-1]

    return {
        "undrifted": _run([str(package.parent)]),
        "drifted": _run([str(package.parent), str(authority.parent)]),
    }


@pytest.mark.adversarial
def test_a_resolution_arriving_without_its_issued_record_is_refused():
    """Guard 79 — ``verification.py:502``, ``type(record) is not IssuedPolicyRecord``."""

    class LookAlikeRecord:
        pass

    refusal, outcomes = _refusal_for(record=LookAlikeRecord())
    assert refusal.outcome is outcomes.RESOLUTION_MALFORMED


@pytest.mark.adversarial
def test_a_resolution_not_returning_the_records_own_artifact_is_refused():
    """Guard 80 — ``verification.py:507``, the record and resolution must agree on identity.

    ``is not``, not ``!=``: two equal artifacts are still two objects, and the one the
    signature was checked against is the one that must travel on.
    """

    refusal, outcomes = _refusal_for(policy=None)
    assert refusal.outcome is outcomes.RESOLUTION_MALFORMED


@pytest.mark.adversarial
def test_a_record_naming_an_unadmitted_signature_algorithm_is_refused():
    """Guard 83 — ``verification.py:529``, the record's algorithm against the closed set."""

    def _rewrite(answer):
        object.__setattr__(answer.record, "signature_alg", "rsa-md5")
        return answer.record

    refusal, outcomes = _refusal_for(record=_rewrite)
    assert refusal.outcome is outcomes.UNSUPPORTED_ALGORITHM


@pytest.mark.adversarial
def test_a_record_whose_body_digest_is_malformed_is_refused():
    """Guard 84 — ``verification.py:536``, ``not is_policy_digest(policy_body_digest)``."""

    # Both sides, not just one. The R-3 gate seventeen lines above compares
    # ``record.coordinate.content_digest`` against ``record.policy_body_digest``; changing
    # only the digest trips *that* guard with COORDINATE_DIGEST_UNBOUND and never reaches
    # this one. Making them equal-and-malformed is what isolates the shape check.
    def _rewrite(answer):
        record = answer.record
        object.__setattr__(record, "policy_body_digest", "not-a-digest")
        object.__setattr__(record.coordinate, "content_digest", "not-a-digest")
        return record

    refusal, outcomes = _refusal_for(record=_rewrite)
    assert refusal.outcome is outcomes.COORDINATE_MALFORMED


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "field",
    ["descriptor_adapter_id", "descriptor_policy_type", "descriptor_canonical_projection"],
)
def test_a_resolution_publishing_no_descriptor_projection_is_refused(field):
    """Guard 96 — ``verification.py:685``, ``missing``.

    Parametrised over all three published fields: the signed body digest cannot be
    reproduced without the projection, and neither the policy type nor any bound inside the
    body can be established. One case would leave the other two unexercised.
    """

    refusal, outcomes = _refusal_for(**{field: None})
    assert refusal.outcome is outcomes.POLICY_PROJECTION_ABSENT


@pytest.mark.adversarial
def test_a_descriptor_projection_that_is_not_a_mapping_is_refused():
    """Guard 98 — ``verification.py:697``, ``not isinstance(projection, Mapping)``."""

    refusal, outcomes = _refusal_for(descriptor_canonical_projection=[("bounds", [])])
    assert refusal.outcome is outcomes.POLICY_PROJECTION_ABSENT


@pytest.mark.adversarial
def test_a_descriptor_naming_another_adapter_than_the_records_is_refused():
    """Guard 99 — ``verification.py:706``, ``adapter_id != record.adapter_id``.

    The published identity must be the one the record was described by. A projection framed
    under a different adapter id reproduces a digest nobody signed.
    """

    refusal, outcomes = _refusal_for(descriptor_adapter_id="ugence.some-other-adapter/v1")
    assert refusal.outcome is outcomes.POLICY_PROJECTION_DIGEST_MISMATCH


# --- verification.py: signed bounds this profile cannot read, and R-8's typing ---------
#
# Like guard 105, none of these is reachable by rewriting the projection: gate 14 reproduces
# the signed body digest from it, so a mutated projection dies an entire gate earlier. What
# reaches them is a bound that is *genuinely signed* and still unreadable — an authority
# issuing capacity bounds under a shape this profile does not know.


def _issue_with_bounds(bounds):
    from _policy_fixtures import make_bounds_policy  # noqa: PLC0415

    authority = bounds_authority()
    return authority, authority.issue(make_bounds_policy(bounds=bounds))


@pytest.mark.adversarial
def test_a_signed_bounds_key_that_is_not_a_sequence_is_refused():
    """Guard 102 — ``verification.py:758``, ``not isinstance(raw, (list, tuple))``.

    An **int**, not a dict or a string. Those two are iterable, so without this guard they
    reach the entry-Mapping check below and are refused with the same
    ``POLICY_BOUNDS_MALFORMED`` outcome — nothing measured. An int is not iterable at all:
    ``enumerate(7)`` raises, and the routine's outermost handler classifies that as
    ``VERIFICATION_UNAVAILABLE``.

    The difference is the guard's whole authority, and it is not cosmetic. "This policy's
    bounds are malformed" is a determination *about the policy*; "this routine could not
    reach a determination" is an availability failure that invites a retry. Without this
    guard a caller is told to retry a policy that will never become readable.
    """

    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415

    authority, record = _issue_with_bounds(7)
    result = _verify_with(port_for(authority), record)
    assert result.refusal is not None
    assert result.refusal.outcome is PolicyAuthenticityOutcome.POLICY_BOUNDS_MALFORMED


@pytest.mark.adversarial
def test_a_signed_bound_entry_that_is_not_a_mapping_is_refused():
    """Guard 104 — ``verification.py:772``, ``not isinstance(entry, Mapping)``.

    A **scalar** entry, not a string or a sequence. This guard was classified
    ``diagnostic-only`` on the recorded ground that no input separates it from its
    successors; that claim was false, and it was false because all three isolation attempts
    came from one family. A string trips the absent-field check, a string containing the four
    field names trips the ``extra`` check on its characters, and a list of the four names
    reaches ``entry["action_type"]`` inside the ``except Exception`` backstop — all
    ``POLICY_BOUNDS_MALFORMED``.

    A scalar does none of that. ``"action_type" not in 5`` raises ``TypeError``, and that
    line sits *outside* the backstop, which wraps only the ``VerifiedCapacityBound(...)``
    construction below. The outcome moves to ``VERIFICATION_UNAVAILABLE`` — an availability
    failure inviting a retry, in place of a determination about the policy.
    """

    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415

    for entry in (5, None, True):
        authority, record = _issue_with_bounds((entry,))
        result = _verify_with(port_for(authority), record)
        assert result.refusal is not None, f"a bounds entry of {entry!r} was verified"
        assert result.refusal.outcome is PolicyAuthenticityOutcome.POLICY_BOUNDS_MALFORMED


@pytest.mark.adversarial
def test_a_candidate_action_type_outside_the_ratified_vocabulary_selects_no_bound():
    """Guard 108 — ``verification.py:836``, R-8's selector vocabulary.

    A scope built through Phase 5A cannot carry an unratified action type — Phase 5A refuses
    one at construction. This boundary accepts a candidate object it did not build, which is
    exactly why the check is here and why the attack has to fabricate the scope rather than
    build it.
    """

    from _policy_fixtures import genuine_candidate  # noqa: PLC0415
    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415

    from _policy_fixtures import _Bound  # noqa: PLC0415

    # The authenticated bound is signed under the *same* unratified action type. Without
    # that the attack measures nothing: removing this guard would merely produce a selector
    # miss from the "no matching bound" refusal below, with the same outcome. With it, the
    # selector matches and the candidate is attested against a bound whose action type D-4
    # never ratified — measured: neutralising this guard turns this case VERIFIED.
    unratified = _Bound(
        action_type="scale_sideways",
        resource_class="deploy/checkout-api",
        max_permitted_magnitude=10_000,
        max_permitted_delta=10_000,
    )
    authority, record = _issue_with_bounds((unratified,))
    candidate = genuine_candidate(record)
    if candidate is None:  # pragma: no cover - no Phase 5A checkout available
        pytest.skip("no source checkout; the Phase 5A candidate builder is unavailable")

    forged = _bypass(
        candidate, target_scope=_bypass(candidate.target_scope, action_type="scale_sideways")
    )
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_CANDIDATE,
        candidate=forged,
    )
    assert result.refusal is not None, (
        "a candidate was attested against a bound signed under an action type D-4 never "
        "ratified"
    )
    assert result.refusal.outcome is PolicyAuthenticityOutcome.CANDIDATE_BOUND_SELECTOR_MISS


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "field",
    # Three of the loop's four positions. The fourth, ``requested_delta``, is a derived
    # *property* of ``ExecutionTargetScope`` — ``requested_magnitude - magnitude_before`` —
    # with no setter and no dataclass field behind it, so it is an ``int`` by construction
    # and that position of the guard cannot be reached with anything else. Recorded here
    # rather than left as a silently missing case.
    ["max_permitted_magnitude", "max_permitted_delta", "requested_magnitude"],
)
def test_a_candidate_ceiling_that_is_a_bool_is_refused(field):
    """Guard 111 — ``verification.py:884``, R-8's exact-int admission.

    ``bool`` is the case the guard names explicitly, and it is not pedantry: ``True > 1`` is
    ``False``, so a bool ceiling would compare as satisfied against any authenticated bound
    above 1. All four carried values are parametrised — a single case would leave three
    positions of the loop unexercised.
    """

    from _policy_fixtures import genuine_candidate  # noqa: PLC0415
    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415

    authority, record = issued_bounds()
    candidate = genuine_candidate(record)
    if candidate is None:  # pragma: no cover - no Phase 5A checkout available
        pytest.skip("no source checkout; the Phase 5A candidate builder is unavailable")

    forged = _bypass(
        candidate, target_scope=_bypass(candidate.target_scope, **{field: True})
    )
    result = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_CANDIDATE,
        candidate=forged,
    )
    assert result.refusal is not None
    assert result.refusal.outcome is PolicyAuthenticityOutcome.CANDIDATE_BOUND_EXCEEDED


@pytest.mark.adversarial
def test_a_projection_entry_that_lies_about_its_own_keys_cannot_mint_a_bound():
    """Guard 105 — ``verification.py:775``, isolated. The reason it is SCORED, not excluded.

    This guard was classified ``diagnostic-only`` on the recorded ground that removing it
    only changes the message. That was wrong, and the attack that shows it needs nothing
    exotic.

    A ``Mapping`` is not obliged to make ``in`` and ``[...]`` agree. A
    ``collections.defaultdict`` reports a missing key *absent* to ``in`` — so the canonical
    key set is unchanged and gate 14 still reproduces the signed body digest — while
    fabricating a value on subscript. The policy is genuinely issued and genuinely signed
    with a three-key bound; only the published projection lies, which is exactly the
    compromised-resolution-port threat this boundary re-checks for.

    With the guard, the answer is ``POLICY_BOUNDS_MALFORMED``. Without it, the verifier mints
    a VERIFIED artifact carrying ``max_permitted_delta=999999`` as an **attested** fact.
    """

    import collections  # noqa: PLC0415

    from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityOutcome  # noqa: PLC0415
    from _policy_fixtures import make_bounds_policy  # noqa: PLC0415

    @dataclasses.dataclass(frozen=True)
    class _BoundWithoutADeltaCeiling:
        action_type: str
        resource_class: str
        max_permitted_magnitude: int

    authority = bounds_authority()
    record = authority.issue(
        make_bounds_policy(
            bounds=(
                _BoundWithoutADeltaCeiling(
                    action_type="scale_up",
                    resource_class="deploy/checkout-api",
                    max_permitted_magnitude=100,
                ),
            )
        )
    )

    def _fabricate_on_subscript(answer):
        projection = dict(answer.descriptor_canonical_projection)
        entry = collections.defaultdict(lambda: 999_999, dict(projection["bounds"][0]))
        projection["bounds"] = [entry, *projection["bounds"][1:]]
        return projection

    result = _verify_with(
        _RewritingPort(
            port_for(authority),
            {"descriptor_canonical_projection": _fabricate_on_subscript},
        ),
        record,
    )
    assert result.verified_policy is None, (
        "a bound ceiling no signature covered was minted as an attested fact: "
        f"{getattr(result.verified_policy, 'capacity_bounds_fact', None)!r}"
    )
    assert result.refusal is not None
    assert result.refusal.outcome is PolicyAuthenticityOutcome.POLICY_BOUNDS_MALFORMED


#: Source of the probe the second-resolution measurements below run.
UPSTREAM_RESOLUTION_PROBE = (
    "try:\n"
    "    import ugence_cloud_scaling_policy_authenticity.identifiers  # noqa: F401\n"
    "    print('NO-REFUSAL')\n"
    "except AssertionError as exc:\n"
    "    print('REFUSED AssertionError ' + str(exc))\n"
    "except ImportError as exc:\n"
    "    print('REFUSED ImportError ' + str(exc))\n"
)


def _second_resolution(tmp_path, label, origin, edits):
    """A second resolution of one upstream distribution, built from its real source.

    ``origin`` is the installed package directory; it is copied verbatim and then each
    ``(relative_path, old, new)`` edit is applied, each asserted to match exactly once so a
    rename upstream fails the test rather than silently producing an undrifted copy. A stub
    would prove something about the stub; this proves something about the distribution.
    """

    import shutil  # noqa: PLC0415

    root = tmp_path / label
    root.mkdir(parents=True, exist_ok=True)
    destination = root / origin.name
    shutil.copytree(origin, destination, ignore=shutil.ignore_patterns("__pycache__"))
    for relative, old, new in edits:
        path = destination / relative
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, (
            f"{origin.name}/{relative}: expected exactly one occurrence of {old!r}, found "
            f"{text.count(old)} — the drift this resolution introduces may not have been "
            "introduced at all"
        )
        path.write_text(text.replace(old, new), encoding="utf-8")
    return root


def _import_phase5b_under(tmp_path, roots):
    """Import this package's identifiers with ``roots`` ahead of everything else.

    Returns the probe's single line of stdout: ``NO-REFUSAL``, or ``REFUSED <class> …``.
    The roots go first, so within that process they *are* the installed distributions.
    Everything after them is whatever this suite is already running against — under the
    sweep, that is the mutated copy.

    In a subprocess because the measurement re-runs module-level import code; doing it
    in-process would leave a drifted upstream in ``sys.modules`` for every later test.
    """

    import os  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    probe = tmp_path / "resolution_probe.py"
    probe.write_text(UPSTREAM_RESOLUTION_PROBE, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(probe)],
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                [*(str(r) for r in roots), *(p for p in sys.path if p)]
            ),
        },
    )
    output = result.stdout.strip()
    assert output, f"the probe printed nothing: {result.stderr[-600:]!r}"
    return output


def _upstream(name):
    """The installed source directory of one first-party upstream distribution."""

    import os  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    declared = os.environ.get("UGENCE_REPO_ROOT")
    repo = Path(declared).resolve() if declared else Path(__file__).resolve().parents[4]
    where = {
        "ugence_policy_authority": "packages/policy-authority",
        "ugence_cloud_scaling_controller": "packages/capabilities/cloud-scaling-controller",
        "ugence_cloud_scaling_risk_integration": (
            "packages/integration/cloud-scaling-risk-integration"
        ),
        "ugence_cloud_scaling_authorization_contracts": (
            "packages/integration/cloud-scaling-authorization-contracts"
        ),
    }[name]
    origin = repo / where / "src" / name
    assert origin.is_dir(), f"{name} source not found at {origin}"
    return origin


@pytest.mark.adversarial
def test_the_protocol_separation_holds_under_a_policy_authority_that_renamed_its_protocol(
    tmp_path,
):
    """Guard 12 — ``identifiers.py:186``, ``VERIFICATION_PROFILE == …PROTOCOL_ID``.

    Excluded as ``unscorable-by-single-checkout-fixture`` until the fixture was asked to
    vary the resolution rather than assumed unable to. ``ugence-policy-authority`` is pinned
    ``>=0.1.0``, which admits a 0.2.0 that renames its protocol — and a rename onto this
    package's own verification profile is the collision the guard names.

    Built here from the real Policy Authority source: ``AUTHORITY_PROTOCOL_ID`` is composed
    from two constants, so both are moved to land on
    ``ugence.cloud-scaling/policy-authenticity/v1``.

    Present, the package refuses to import. Removed, it imports and every verified artifact
    then carries a profile identifier indistinguishable from the protocol it merely
    consumes — a determination that reads as though this package *were* the Policy
    Authority. Refusal versus no refusal is a change to the typed refusal under §9.1.
    """

    resolution = _second_resolution(
        tmp_path,
        "policy-authority-0.3.0",
        _upstream("ugence_policy_authority"),
        (
            ("__init__.py", '__version__ = "0.3.0"', '__version__ = "0.4.0"'),
            (
                "core/statuses.py",
                'AUTHORITY_PROTOCOL = "ugence.policy-authority"',
                'AUTHORITY_PROTOCOL = "ugence.cloud-scaling/policy-authenticity"',
            ),
            (
                "core/statuses.py",
                'AUTHORITY_PROTOCOL_VERSION = "v0.1"',
                'AUTHORITY_PROTOCOL_VERSION = "v1"',
            ),
        ),
    )
    outcome = _import_phase5b_under(tmp_path, [resolution])
    assert outcome.startswith("REFUSED AssertionError"), (
        "the verification profile collided with the Policy Authority protocol identifier "
        f"and the package imported anyway: {outcome!r}"
    )
    assert "verification profile" in outcome, (
        f"the refusal came from some separation other than the protocol one: {outcome!r}"
    )


@pytest.mark.adversarial
def test_the_digest_domains_stay_apart_under_an_authority_that_adopted_this_ones(tmp_path):
    """Guard 13 — ``identifiers.py:191``, ``…DIGEST_DOMAIN == POLICY_BODY_DIGEST_DOMAIN``.

    Same pin, same reasoning, a different constant: a 0.2.0 that adopts this package's
    artifact domain as its policy-body domain. One side of this comparison has always been
    upstream's to move.

    Present, the package refuses to import. Removed, it imports with one domain tag serving
    both frames, and the only bytes this package originates — its verification artifact's
    integrity digest — become forgeable as a policy body digest and vice versa. The
    docstring's claim that the two "cannot collide" holds because of this guard, not
    independently of it.
    """

    resolution = _second_resolution(
        tmp_path,
        "policy-authority-0.3.0",
        _upstream("ugence_policy_authority"),
        (
            ("__init__.py", '__version__ = "0.3.0"', '__version__ = "0.4.0"'),
            (
                "core/canonical.py",
                'POLICY_BODY_DIGEST_DOMAIN = "ugence.policy-authority/policy-body/v1"',
                'POLICY_BODY_DIGEST_DOMAIN = '
                '"ugence.cloud-scaling/policy-authenticity/artifact/v1"',
            ),
        ),
    )
    outcome = _import_phase5b_under(tmp_path, [resolution])
    assert outcome.startswith("REFUSED AssertionError"), (
        "the artifact digest domain collided with the policy-body digest domain and the "
        f"package imported anyway: {outcome!r}"
    )
    assert "digest domain" in outcome, (
        f"the refusal came from some separation other than the domain one: {outcome!r}"
    )


@pytest.mark.adversarial
def test_the_entitlements_stay_distinct_under_an_authority_that_collapsed_them(tmp_path):
    """Guard 15 — ``identifiers.py:210``, ``REQUIRED… is FORBIDDEN_KEY_ENTITLEMENT``.

    Both operands are members of the Policy Authority's ``KeyEntitlement``, so *both* sides
    are upstream's to move — the case where a single-resolution fixture is least entitled to
    conclude anything. The drift is one line: give ``REVOKE_POLICY`` the value
    ``"ISSUE_POLICY"``. Python's ``Enum`` makes equal values *aliases*, so the two names
    become one member and the ``is`` comparison the guard uses becomes true. That is what a
    release merging the two entitlements would actually look like.

    Present, the package refuses to import. Removed, it imports with
    ``REQUIRED_KEY_ENTITLEMENT is FORBIDDEN_KEY_ENTITLEMENT``, and D-5B0B-4's whole basis
    for choosing the Policy Authority's key ring over a TEV anchor — that entitlement
    granularity is expressible — is gone: a revoke-only key satisfies the issuing
    requirement, which the module docstring says cannot happen because there is no parameter
    to divert. There is no parameter, and this guard is why that is enough.
    """

    resolution = _second_resolution(
        tmp_path,
        "policy-authority-0.3.0",
        _upstream("ugence_policy_authority"),
        (
            ("__init__.py", '__version__ = "0.3.0"', '__version__ = "0.4.0"'),
            (
                "core/statuses.py",
                '    REVOKE_POLICY = "REVOKE_POLICY"',
                '    REVOKE_POLICY = "ISSUE_POLICY"',
            ),
        ),
    )
    outcome = _import_phase5b_under(tmp_path, [resolution])
    assert outcome.startswith("REFUSED AssertionError"), (
        "issuing and revoking entitlements collapsed to one member and the package "
        f"imported anyway: {outcome!r}"
    )
    assert "entitlements" in outcome, (
        f"the refusal came from some separation other than the entitlement one: {outcome!r}"
    )


@pytest.mark.adversarial
def test_the_action_vocabulary_guard_fires_when_the_whole_chain_ratifies_a_fifth_type(
    tmp_path,
):
    """Guard 16 — ``identifiers.py:224``, ``CANONICAL_ACTION_TYPES != _RATIFIED_…``.

    The one of the four that needs more than a single distribution moved, and the first
    attempt at it measured nothing. Adding a fifth ``ActionKind`` to the controller alone
    is refused by *Phase 5A's* own drift guard, one package upstream — the same ImportError
    with and without this guard, which is a selector miss, not a measurement.

    Reaching this guard means the chain agreeing: the controller's enum, Phase 4C's
    ``CANONICAL_ACTION_TYPES`` and Phase 5A's, all carrying ``scale_sideways``. That is a
    coordinated release the open-ended pins admit, and it is exactly the situation this
    guard exists for — 5B ratified four types in R-8 and does not follow an upstream that
    ratifies five.

    Present, the package refuses to import. Removed, it imports and gate 16 selects an
    authenticated capacity bound by a five-member vocabulary R-8 never ratified.
    """

    fifth = '    {"no_change", "scale_up", "scale_down", "coordinated"}'
    widened = (
        '    {"no_change", "scale_up", "scale_down", "coordinated", "scale_sideways"}'
    )
    chain = tmp_path / "action-vocabulary-0.2.0"
    for origin, edits in (
        (
            _upstream("ugence_cloud_scaling_controller"),
            (
                (
                    "planning/candidates.py",
                    '    COORDINATED = "coordinated"',
                    '    COORDINATED = "coordinated"\n    SIDEWAYS = "scale_sideways"',
                ),
            ),
        ),
        (
            _upstream("ugence_cloud_scaling_risk_integration"),
            (
                ("version.py", '__version__ = "0.1.0"', '__version__ = "0.2.0"'),
                ("identifiers.py", fifth, widened),
            ),
        ),
        (
            _upstream("ugence_cloud_scaling_authorization_contracts"),
            (
                ("version.py", '__version__ = "0.7.0"', '__version__ = "0.8.0"'),
                ("identifiers.py", fifth, widened),
            ),
        ),
    ):
        _second_resolution(chain.parent, chain.name, origin, edits)

    outcome = _import_phase5b_under(tmp_path, [chain])
    assert outcome.startswith("REFUSED ImportError"), (
        "the upstream chain ratified a fifth action type and this package imported anyway, "
        f"leaving gate 16 to select a bound by an unratified vocabulary: {outcome!r}"
    )
    assert "action-type drift" in outcome, (
        "the refusal came from a guard upstream of this one, which measures nothing about "
        f"this one: {outcome!r}"
    )
