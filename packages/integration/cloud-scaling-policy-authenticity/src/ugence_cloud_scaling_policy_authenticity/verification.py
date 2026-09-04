"""The authoritative policy-authenticity verification routine.

The whole point, in one sentence
--------------------------------
The verifier asks the Policy Authority's own trusted-resolution path about **one exact
coordinate at one injected instant**, and then refuses to treat the answer as a
determination unless it is a non-historical ``RESOLVED`` about *that* coordinate at *that*
instant, whose record binds its own body digest into its own identity.

Why that is more than "call ``resolve_policy`` and check the status"
---------------------------------------------------------------------
Five gates exist here that the authority does not perform for a consumer:

#. **Historical refusal.** ``resolve_policy`` can legitimately return ``RESOLVED`` with
   ``historical=True`` under a configured rule. That answer describes the past and can never
   back an authorization (D-5B0B-1), so it is refused at admission rather than propagated
   with a flag every downstream consumer must remember to read.
#. **The port may not answer another question.** The resolution's own
   ``requested_coordinate`` and ``as_of`` are compared against what was asked. A port is
   injected by a composition root; a port that answers about a neighbouring coordinate, or
   at a different instant, is refused rather than trusted because its status said
   ``RESOLVED``.
#. **The coordinate/body-digest equality (ADR residual R-3).** ``issue_policy`` enforces both
   ``declared_content_digest == policy_body_digest`` **and**
   ``coordinate.content_digest == policy_body_digest``. ``resolve_policy`` re-enforces only
   the first. A record whose coordinate names one body while its signature covers another
   therefore resolves ``RESOLVED/RESOLVED`` today — latent under the one shipped adapter,
   reachable with any adapter that decouples the two. This boundary enforces the equality
   itself, and refuses with ``COORDINATE_DIGEST_UNBOUND``.
#. **The closed algorithm set.** A record naming an algorithm this profile does not admit is
   refused even if the configured verifier accepted it.
#. **The candidate is about this policy (5B-1).** When a candidate accompanies the question,
   its policy coordinate is reconciled against the resolved one — all six components, the
   signed body digest and the issuing identity — and a disagreement is
   ``CANDIDATE_COORDINATE_MISMATCH``. The authority is never asked about the candidate: it has
   no notion of one. This gate is only reachable since Phase 5A 0.2.0 gave a candidate a
   coordinate to compare; before that, one genuine proof verified alongside any candidate
   whatsoever (ADR residual R-4).

Ordered, stop at the first failing group, deterministic
--------------------------------------------------------
Identical inputs always yield the identical outcome, and no later group can rescue an
earlier failure:

#. **exact-type admission** — coordinate, tenant expectation, ``as_of``, optional candidate;
#. **tenant expectation** — the caller's expected tenant must be the coordinate's own tenant
   component, checked before the authority is asked anything;
#. **resolution** — through the injected port, inside a fail-closed boundary;
#. **answer identity** — the resolution is about the coordinate and instant that were asked;
#. **status** — ``RESOLVED``, else the authority's reason is carried across one-for-one;
#. **historicity** — a historical answer, or one that does not imply current validity, is
   refused;
#. **result shape** — the record and artifact are present and the record carries the
   resolved coordinate;
#. **coordinate/body-digest equality** — the R-3 gate above;
#. **algorithm admission** — the closed set;
#. **digest shape** — both digests are bare 64-hex Policy Authority digests;
#. **candidate reconciliation** — a supplied candidate names this exact policy.

Only after all eleven does a :class:`~.verified.VerifiedPolicyAuthenticity` exist.

Three checks deliberately sit **outside** that list, and the count stays eleven because none
of them is a gate on an input. The trust identity is snapshotted once, at *construction*, and
every determination is minted from the snapshot. The verified/resolution **pair** is
cross-checked by :class:`PolicyAuthenticityResult` itself, at *result construction*, because
it is a property of the pair rather than of anything the routine was handed. And the terminal
handler *classifies* an escaping exception rather than deciding anything about an input.

No placeholder, no optionality
-------------------------------
The resolution port is a **required** constructor argument with no default. There is no port
in this distribution that resolves anything unconditionally, no permissive fallback, no
hardcoded trusted key, no caller-supplied trust anchor and no path that converts an exception
into a success — an unexpected exception becomes ``VERIFICATION_UNAVAILABLE``, which is a
refusal. The only shipped "no trust configured" posture is
:class:`~.resolution_port.DenyAllPolicyResolutionPort`, which refuses everything.

No clock
--------
``as_of`` is an injected timezone-aware instant. Nothing here reads a wall clock, and a naive
datetime is refused rather than assumed UTC. R-2 is **closed as narrowed**: gate 13 bounds the
instant against the candidate's carried validity; it stays a recorded fact by ruling, and binding
it to Risk Authority's clock is Phase 5 envelope issuance. Honesty is bounded by the instant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Mapping, Optional

from ugence_cloud_scaling_authorization_contracts import CapacityAuthorizationCandidate
from ugence_policy_authority.api import (
    IssuedPolicyRecord,
    PolicyCoordinate,
    PolicyResolution,
    PolicyResolutionStatus,
    framed_body_digest,
)

from .canonical import (
    framed_digest,
    is_phase5a_digest,
    is_policy_digest,
    require_aware_utc,
)
from .errors import CloudScalingPolicyAuthenticityError as _PackageError
from .errors import PolicyAuthenticityConfigurationError as _ConfigError
from .errors import VerifiedPolicyArtifactIntegrityError as _IntegrityError
from .identifiers import (
    CAPACITY_BOUND_FIELDS,
    CAPACITY_BOUNDS_POLICY_FAMILY,
    CAPACITY_BOUNDS_PROJECTION_KEY,
    POLICY_AUTHENTICITY_DIGEST_DOMAIN,
    POLICY_AUTHORITY_CANONICALIZATION_VERSION,
    POLICY_AUTHORITY_PROTOCOL_ID,
    POLICY_TRUST_ANCHOR_OWNER,
    SUPPORTED_SIGNATURE_ALGORITHMS,
    VERIFICATION_PROFILE,
    VERIFICATION_PROFILE_VERSION,
)
from .identifiers import CANONICAL_ACTION_TYPES
from .outcomes import PolicyAuthenticityOutcome as _Outcome
from .outcomes import resolution_reason_outcome
from .resolution_port import require_production_resolution_port
from .verified import (
    _VERIFICATION_TOKEN,
    DERIVED_FACT_NAMES,
    VerifiedCapacityBound,
    VerifiedPolicyAuthenticity,
    _partitioned_digest,
    _record_minted,
    require_partition_agreement,
    require_verified_policy_authenticity,
)

__all__ = [
    "PolicyAuthenticityRefusal",
    "PolicyAuthenticityResult",
    "PolicyAuthenticityVerifier",
]


@dataclass(frozen=True)
class PolicyAuthenticityRefusal:
    """A typed refusal. The member is the answer; the detail is for humans."""

    outcome: _Outcome
    detail: str = ""

    def __post_init__(self) -> None:
        if type(self.outcome) is not _Outcome:
            raise TypeError(
                "PolicyAuthenticityRefusal.outcome must be exactly a "
                "PolicyAuthenticityOutcome"
            )
        if self.outcome is _Outcome.VERIFIED:
            raise ValueError(
                "VERIFIED is not a refusal; a refusal cannot carry the success member"
            )


@dataclass(frozen=True)
class PolicyAuthenticityResult:
    """Exactly one of a verified artifact or a typed refusal, never both and never neither.

    On success the Policy Authority's own :class:`PolicyResolution` is carried alongside, so
    a consumer reaches the resolved policy body through the authority's type rather than
    through this package. The verified artifact stays fully digest-covered and binds that
    body by digest; the resolution is the body itself.

    The verified branch is **revalidated** on construction. Assembling a result around a
    fabricated artifact therefore fails here, which means every verified artifact a caller
    can reach through a result is one this process genuinely reached.

    The **pair** is bound as well as each half. Both halves are individually genuine even
    when they are about different policies — a real determination for policy A and a real
    resolution for policy B are each valid objects — and a consumer that reads the body out
    of ``resolution`` while trusting the coordinate on ``verified_policy`` would then be
    reading a body the proof does not cover. So the two are cross-checked on the coordinate
    and on ``policy_body_digest``, which is the binding D-5B0B-2 makes load-bearing. The
    verifier cannot produce a mismatched pair; this refuses one that was assembled.
    """

    verified_policy: Optional[VerifiedPolicyAuthenticity] = None
    refusal: Optional[PolicyAuthenticityRefusal] = None
    resolution: Optional[PolicyResolution] = None

    def __post_init__(self) -> None:
        if (self.verified_policy is None) == (self.refusal is None):
            raise ValueError(
                "a PolicyAuthenticityResult must carry exactly one of a verified policy or "
                "a typed refusal"
            )
        if self.verified_policy is not None:
            if type(self.verified_policy) is not VerifiedPolicyAuthenticity:
                raise TypeError(
                    "PolicyAuthenticityResult.verified_policy must be exactly a "
                    "VerifiedPolicyAuthenticity"
                )
            # Deliberately AFTER the exact-type check, so a wrong type still raises the
            # typed TypeError, and this answers what the type cannot: did this process
            # actually reach this determination?
            require_verified_policy_authenticity(
                self.verified_policy, "PolicyAuthenticityResult.verified_policy"
            )
            if type(self.resolution) is not PolicyResolution:
                raise TypeError(
                    "a verified PolicyAuthenticityResult must carry the PolicyResolution it "
                    "was reached from; the policy body reaches a consumer through the "
                    "authority's own type, not through this package"
                )
            self._require_agreeing_pair()
        if self.refusal is not None and type(self.refusal) is not PolicyAuthenticityRefusal:
            raise TypeError(
                "PolicyAuthenticityResult.refusal must be exactly a PolicyAuthenticityRefusal"
            )

    def _require_agreeing_pair(self) -> None:
        """Refuse a verified branch whose resolution is not the one the artifact reports.

        Two questions, and binding only the first leaves the pair a misstatement.

        **Which policy** — the resolution must be *about* the coordinate the artifact names,
        it must have *found* a record under that coordinate, and that record's signed body
        digest must be the one the artifact binds.

        **Which answer** — a genuine artifact of policy X pairs cleanly with a genuine
        resolution of policy X that says something else entirely. A historical resolution is
        the sharp case: it is ``RESOLVED``, it is about the same coordinate, it carries the
        same body digest, and ``implies_current_validity`` is ``False`` — while every artifact
        this package mints reports ``historical=False``. A resolution reached at a different
        ``as_of`` is the same failure in the other dimension, and D-5B0B-5 measured that the
        instant is exactly what changes the answer. So both are bound.
        """

        artifact = self.verified_policy
        resolution = self.resolution
        coordinate = artifact.policy_coordinate
        if resolution.requested_coordinate != coordinate:
            raise _IntegrityError(
                "PolicyAuthenticityResult pairs a verified policy with a resolution about a "
                "different coordinate; both halves may be genuine and the pair is still a "
                "misstatement"
            )
        record = resolution.record
        if type(record) is not IssuedPolicyRecord or record.coordinate != coordinate:
            raise _IntegrityError(
                "PolicyAuthenticityResult pairs a verified policy with a resolution that "
                "carries no record for that coordinate"
            )
        if record.policy_body_digest != artifact.policy_body_digest:
            raise _IntegrityError(
                "PolicyAuthenticityResult pairs a verified policy with a resolution whose "
                "record binds a different policy body; policy_body_digest is the content "
                "binding, so a consumer reading the body out of the resolution would be "
                "reading a body the proof does not cover"
            )
        if resolution.as_of != artifact.resolved_as_of_fact:
            raise _IntegrityError(
                "PolicyAuthenticityResult pairs a verified policy with a resolution reached "
                "at a different instant than the artifact reports; the same record yields "
                "different answers at different instants, so the pair asserts a validity the "
                "resolution never established"
            )
        if resolution.historical or resolution.implies_current_validity is not True:
            raise _IntegrityError(
                "PolicyAuthenticityResult pairs a verified policy with a historical "
                "resolution. Every artifact this package mints reports historical=False, so "
                "the pair would present a statement about the past as one about now — the "
                "distinction D-5B0B-1 refuses to let downstream consumers carry"
            )

    @property
    def outcome(self) -> _Outcome:
        """The typed outcome, whichever branch is present. Derived, never stored."""

        if self.refusal is not None:
            return self.refusal.outcome
        return _Outcome.VERIFIED

    @property
    def verified(self) -> bool:
        return self.refusal is None


class PolicyAuthenticityVerifier:
    """The authoritative policy-authenticity verifier. Nothing else mints a verified artifact.

    The resolution port is a **required** keyword argument with no default, so there is no
    posture in which this class verifies against something it was not given. Under
    ``production_mode=True`` the port must be production-authoritative; that is checked at
    construction, so a reference component cannot reach a determination.

    The port's ``trust_configuration_digest`` is **snapshotted at construction** and every
    determination is minted from the snapshot. A port is an injected collaborator, so its
    attribute is something this class reads rather than something it controls: reading it
    again at mint time would let a port report one trust identity when it was admitted and
    another when the artifact is stamped. A verifier is therefore bound to one reported trust
    identity for its whole life; a changed configuration means a new port and a new verifier.

    The snapshot stops *drift*; it does not make the value true. A port reports its own trust
    identity, and this boundary cannot cross-check it — that is why the fact sits in the
    artifact's **recorded** half. See :data:`~.verified.RECORDED_FACT_NAMES`.
    """

    __slots__ = ("_port", "_production_mode", "_trust_configuration_digest")

    def __init__(self, *, resolution_port, production_mode: bool = False) -> None:
        if resolution_port is None:
            raise _ConfigError(
                "a policy resolution port is required; there is no default port, no ambient "
                "policy registry and no permissive fallback"
            )
        if not hasattr(resolution_port, "resolve_policy_version"):
            raise _ConfigError(
                "the resolution port must implement resolve_policy_version(...) -> "
                "PolicyResolution"
            )
        digest = getattr(resolution_port, "trust_configuration_digest", None)
        if not is_policy_digest(digest):
            raise _ConfigError(
                "the resolution port must report a trust_configuration_digest as a bare "
                "lowercase 64-hex digest; a determination that cannot name the trust "
                "configuration it ran under is not a determination this package will mint"
            )
        if production_mode:
            require_production_resolution_port(resolution_port)
        object.__setattr__(self, "_port", resolution_port)
        object.__setattr__(self, "_production_mode", bool(production_mode))
        # Snapshotted, deliberately: see this class's docstring. ``str()`` is not a
        # normalization — ``is_policy_digest`` above already refused anything but an exact
        # ``str`` of the right shape — it detaches the value from a property that could
        # answer differently next time.
        object.__setattr__(self, "_trust_configuration_digest", str(digest))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"PolicyAuthenticityVerifier is immutable; cannot set {name!r}. Rebinding the "
            "resolution port after construction is exactly the component swap the production "
            "guard exists to prevent."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"PolicyAuthenticityVerifier is immutable; cannot delete {name!r}"
        )

    @property
    def production_mode(self) -> bool:
        return self._production_mode

    @property
    def trust_configuration_digest(self) -> str:
        """The identity of the trust configuration every determination here is reached under.

        The value read from the port at construction, not a fresh read. See the class
        docstring for why that difference is load-bearing.
        """

        return self._trust_configuration_digest

    # -- the authoritative routine ------------------------------------------------------ #

    def verify(
        self,
        *,
        coordinate: PolicyCoordinate,
        expected_reference_tenant_id: str,
        as_of: datetime,
        candidate: Optional[CapacityAuthorizationCandidate] = None,
    ) -> PolicyAuthenticityResult:
        """Verify one exact policy coordinate at ``as_of``. Returns a typed result.

        ``candidate`` is **optional, and reconciled when supplied** (5B-1). Its policy
        coordinate is compared against the resolved policy on all six components, the signed
        body digest and the issuing identity; a disagreement refuses the pair with
        ``CANDIDATE_COORDINATE_MISMATCH`` rather than minting a determination that says
        nothing about the candidate it names. Omitting a candidate is not a refusal: the
        artifact then carries ``candidate_digest_fact=None``, which means no candidate
        accompanied the determination. See :mod:`.verified`.

        Never raises for an invalid input: an invalid input is an expected answer to the
        question, and raising would tempt a caller into treating a swallowed exception as a
        pass. An unexpected internal failure becomes ``VERIFICATION_UNAVAILABLE`` — still a
        refusal, never a success.
        """

        try:
            return self._verify(
                coordinate=coordinate,
                expected_reference_tenant_id=expected_reference_tenant_id,
                as_of=as_of,
                candidate=candidate,
            )
        except Exception as exc:  # noqa: BLE001 - deliberate fail-closed terminal
            outcome = _terminal_outcome(exc)
            return _refuse(
                outcome,
                f"verification could not reach a determination: {type(exc).__name__}",
            )

    def _verify(
        self,
        *,
        coordinate: PolicyCoordinate,
        expected_reference_tenant_id: str,
        as_of: datetime,
        candidate: Optional[CapacityAuthorizationCandidate],
    ) -> PolicyAuthenticityResult:
        # === 1. exact-type admission ====================================================
        if type(coordinate) is not PolicyCoordinate:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "coordinate must be exactly a Policy Authority PolicyCoordinate; a "
                "family-native reference must be mapped by the authority's adapter registry "
                "before it reaches this boundary",
            )
        if type(expected_reference_tenant_id) is not str:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "expected_reference_tenant_id must be exactly a str",
            )
        if type(as_of) is not datetime or as_of.tzinfo is None or as_of.utcoffset() is None:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "as_of must be an exact timezone-aware datetime; this package reads no clock "
                "and refuses a naive instant rather than assuming UTC",
            )
        if candidate is not None and type(candidate) is not CapacityAuthorizationCandidate:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "candidate, when supplied, must be exactly a CapacityAuthorizationCandidate",
            )
        instant = require_aware_utc("as_of", as_of)

        # === 2. tenant expectation, before the authority is asked anything ==============
        # The authority would report TENANT_SCOPE_MISMATCH for this, but asking it to answer
        # a question the caller has already contradicted is not a check — it is a round trip.
        if expected_reference_tenant_id != coordinate.tenant_id:
            return _refuse(
                _Outcome.TENANT_EXPECTATION_MISMATCH,
                "the expected reference tenant is not the coordinate's own tenant component; "
                "note this checks the REFERENCE's declared tenant, never the caller's right "
                "to it — no caller authorization happens anywhere in this chain",
            )

        # === 3. resolution, through the injected port ===================================
        try:
            resolution = self._port.resolve_policy_version(
                coordinate=coordinate,
                expected_reference_tenant_id=expected_reference_tenant_id,
                as_of=instant,
            )
        except Exception as exc:  # noqa: BLE001 - a port that raises is unavailable
            return _refuse(
                _Outcome.VERIFICATION_UNAVAILABLE,
                f"the policy resolution port raised {type(exc).__name__}",
            )
        if type(resolution) is not PolicyResolution:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "the resolution port returned something other than a PolicyResolution",
            )

        # === 4. the port may not answer a question it was not asked =====================
        if resolution.requested_coordinate != coordinate:
            return _refuse(
                _Outcome.RESOLUTION_ANSWERED_ANOTHER_QUESTION,
                "the resolution is about a different coordinate than the one presented",
            )
        if resolution.as_of != instant:
            return _refuse(
                _Outcome.RESOLUTION_ANSWERED_ANOTHER_QUESTION,
                "the resolution was reached at a different instant than the one injected",
            )

        # === 5. status ==================================================================
        if resolution.status is not PolicyResolutionStatus.RESOLVED:
            return _refuse(
                resolution_reason_outcome(resolution.reason),
                f"the policy authority did not resolve this coordinate: "
                f"{getattr(resolution.reason, 'value', resolution.reason)}",
            )

        # === 6. historicity — a statement about the past is not an authenticity proof ===
        if resolution.historical:
            return _refuse(
                _Outcome.HISTORICAL_RESOLUTION_REFUSED,
                "the answer is a historical resolution: it describes an instant before a "
                "verified revocation and never implies current validity, so it is refused "
                "here rather than carried forward labelled",
            )
        if resolution.implies_current_validity is not True:
            return _refuse(
                _Outcome.HISTORICAL_RESOLUTION_REFUSED,
                "the resolution does not imply current validity",
            )

        # === 7. result shape ============================================================
        record = resolution.record
        if type(record) is not IssuedPolicyRecord:
            return _refuse(
                _Outcome.RESOLUTION_MALFORMED,
                "a RESOLVED resolution arrived without its IssuedPolicyRecord",
            )
        if resolution.policy is None or record.policy is not resolution.policy:
            return _refuse(
                _Outcome.RESOLUTION_MALFORMED,
                "a RESOLVED resolution must return the record's own artifact",
            )
        if record.coordinate != coordinate:
            return _refuse(
                _Outcome.RESOLUTION_MALFORMED,
                "the resolved record does not carry the coordinate it was resolved for",
            )

        # === 8. the R-3 gate: the coordinate names the body the signature covered =======
        if record.coordinate.content_digest != record.policy_body_digest:
            return _refuse(
                _Outcome.COORDINATE_DIGEST_UNBOUND,
                "the record's coordinate carries a content digest other than its signed "
                "policy body digest. Issuance forbids this; resolution does not re-check it "
                "(ADR residual R-3), so this boundary refuses rather than binding a "
                "coordinate that names a body nobody signed",
            )

        # === 9. algorithm admission =====================================================
        if record.signature_alg not in SUPPORTED_SIGNATURE_ALGORITHMS:
            return _refuse(
                _Outcome.UNSUPPORTED_ALGORITHM,
                "the record names a signature algorithm outside the closed admitted set",
            )

        # === 10. digest shape ===========================================================
        if not is_policy_digest(record.policy_body_digest):
            return _refuse(
                _Outcome.COORDINATE_MALFORMED,
                "the record's policy_body_digest is not a bare lowercase 64-hex digest",
            )
        if candidate is not None and not is_phase5a_digest(candidate.candidate_digest):
            return _refuse(
                _Outcome.COORDINATE_MALFORMED,
                "the candidate's digest is not a canonical Phase 5A digest",
            )

        # === 11. the candidate is about THIS policy (5B-1, ADR residual R-4) ============
        # Only reachable since Phase 5A 0.2.0 gave the candidate a policy coordinate to
        # reconcile against. Before that this comparison could not be made at all, and a
        # genuine proof verified alongside any candidate whatsoever.
        if candidate is not None:
            mismatch = _coordinate_disagreement(candidate, coordinate, record)
            if mismatch is not None:
                return _refuse(_Outcome.CANDIDATE_COORDINATE_MISMATCH, mismatch)

        # === 12. the policy may bound THIS tenant's action (5B-2, ADR residual R-9) =====
        # Gate 11 establishes the two artifacts are about one policy. It does not establish
        # that the policy may bound this action: a TENANT-scoped policy belongs to exactly one
        # tenant, and nothing before 5B-2 compared that tenant against the candidate's. Phase
        # 5A refuses this at construction too, but this boundary accepts a candidate object it
        # did not build and so cannot inherit that discipline.
        #
        # The resolved coordinate is the authority here, not the candidate's copy of it —
        # gate 11 has already forced the two to agree, and reading the resolved side keeps the
        # answer independent of what the candidate claims about itself.
        if candidate is not None:
            crossing = _cross_tenant_binding(candidate, coordinate)
            if crossing is not None:
                return _refuse(_Outcome.CANDIDATE_CROSS_TENANT_POLICY, crossing)

        # === 13. the candidate must be valid AT the verified instant (5B-2, R-2) ========
        # `as_of` was already type-checked and round-tripped against the resolution, and the
        # authority already refuses a policy that is revoked or outside its effective window.
        # None of that says anything about the *candidate*: before this gate a candidate whose
        # decision expired five months earlier verified VERIFIED, because the instant was
        # recorded beside the candidate's six timestamps and never compared against them.
        if candidate is not None:
            # Typing first. The comparisons below cannot catch a value that lies about how
            # it compares, so the type is checked before anything is compared against it.
            # This precedes rather than reorders the validity refusals: their order among
            # themselves is unchanged, and an exactly-typed candidate reaches them exactly
            # as it did before.
            mistyped = _candidate_instant_type_problem(candidate)
            if mistyped is not None:
                outcome, detail = mistyped
                return _refuse(outcome, detail)
            staleness = _candidate_validity_problem(candidate, instant)
            if staleness is not None:
                outcome, detail = staleness
                return _refuse(outcome, detail)

        # === 14. the projection reproduces the signed body digest (5B-3, R-8) ===========
        # Until Route 1 published the descriptor projection on the resolution, this check was
        # impossible here: ``policy_body_digest`` is a one-way hash and this package holds no
        # adapter registry with which to re-derive the descriptor. That impossibility is what
        # kept ``policy_type`` in the recorded half, and it is what R-8 ran into — the
        # artifact carried 26 facts and not one was a bound, so there was nothing to compare.
        #
        # Reframing the published projection and comparing it against the digest the issuance
        # signature covered supplies the missing pre-image. It promotes ``policy_type``, which
        # is one of the three inputs to that frame, and it authenticates the bounds carried
        # inside the projection.
        reproduction = _projection_problem(resolution, record)
        if reproduction is not None:
            outcome, detail = reproduction
            return _refuse(outcome, detail)

        # === 15. the bounds inside the reproduced projection are readable ================
        # Separate from gate 14 on purpose: a digest match proves the bytes are the signed
        # bytes, and says nothing about whether they form a bound this profile can state.
        try:
            capacity_bounds = _extract_capacity_bounds(
                coordinate, resolution.descriptor_canonical_projection
            )
        except _BoundsShapeError as exc:
            return _refuse(_Outcome.POLICY_BOUNDS_MALFORMED, str(exc))

        # === 16. the candidate's ceilings reconcile with the authenticated ones (R-8) ====
        # This is R-8's remaining half. Gates 14 and 15 *extract* an authenticated bound;
        # until now nothing compared it against what the candidate carries, so a candidate
        # self-asserting 20/5 verified against a genuinely issued bound of 5/1 for its exact
        # selector. Extraction is not reconciliation.
        #
        # Reached only with a candidate: without one there is nothing to reconcile, and a
        # policy that states no bound remains a legitimate determination. It is the *pairing*
        # of a candidate with a policy that bounds nothing that is refused.
        if candidate is not None:
            mismatch = _bound_reconciliation_problem(candidate, capacity_bounds)
            if mismatch is not None:
                outcome, detail = mismatch
                return _refuse(outcome, detail)

        # === every gate succeeded — and only now does an artifact exist =================
        artifact = _mint_verified_artifact(
            record=record,
            coordinate=coordinate,
            expected_reference_tenant_id=expected_reference_tenant_id,
            resolved_as_of=instant,
            trust_configuration_digest=self._trust_configuration_digest,
            candidate_digest_fact=None if candidate is None else candidate.candidate_digest,
            capacity_bounds_fact=capacity_bounds,
        )
        return PolicyAuthenticityResult(verified_policy=artifact, resolution=resolution)

    def __repr__(self) -> str:
        return (
            f"PolicyAuthenticityVerifier(port={type(self._port).__name__}, "
            f"production_mode={self._production_mode})"
        )


class _BoundsShapeError(Exception):
    """The projection's bounds are not the shape this profile can state. Internal."""


def _projection_problem(resolution, record):
    """Return ``(outcome, detail)`` when the published projection does not reproduce the
    signed body digest, or ``None`` when it does.

    **Refusing ``None`` is the point, not an edge case.** A resolution without the projection
    is one whose body digest cannot be reproduced here, and this routine has no way to check
    ``policy_type`` or read a bound out of it. Carrying those facts unchecked is exactly the
    posture 5B-3 exists to end, so absence is a refusal rather than a quiet downgrade to the
    recorded half.

    The three fields arrive together or not at all — the Policy Authority's constructor
    enforces that — but this boundary re-checks each rather than inferring two from one: it
    accepts a ``PolicyResolution`` it did not construct, and a hand-assembled one reaches
    here exactly like a genuine one.
    """

    adapter_id = getattr(resolution, "descriptor_adapter_id", None)
    policy_type = getattr(resolution, "descriptor_policy_type", None)
    projection = getattr(resolution, "descriptor_canonical_projection", None)

    missing = [
        name
        for name, value in (
            ("descriptor_adapter_id", adapter_id),
            ("descriptor_policy_type", policy_type),
            ("descriptor_canonical_projection", projection),
        )
        if value is None
    ]
    if missing:
        return (
            _Outcome.POLICY_PROJECTION_ABSENT,
            f"the resolution published no descriptor projection ({', '.join(missing)} is "
            "None), so the signed body digest cannot be reproduced here and neither the "
            "policy type nor any bound inside the body can be established",
        )
    if type(adapter_id) is not str or type(policy_type) is not str:
        return (
            _Outcome.POLICY_PROJECTION_ABSENT,
            "the published descriptor identity is not a pair of strings",
        )
    if not isinstance(projection, Mapping):
        return (
            _Outcome.POLICY_PROJECTION_ABSENT,
            "the published descriptor projection is not a mapping",
        )

    # The record's own adapter id and policy type must be the ones being reframed. Reframing
    # with the projection's copy while the artifact carries the record's would let the two
    # disagree and still pass.
    if adapter_id != record.adapter_id:
        return (
            _Outcome.POLICY_PROJECTION_DIGEST_MISMATCH,
            f"the published projection names adapter {adapter_id!r} and the record names "
            f"{record.adapter_id!r}",
        )
    if policy_type != record.policy_type:
        return (
            _Outcome.POLICY_PROJECTION_DIGEST_MISMATCH,
            f"the published projection names policy type {policy_type!r} and the record "
            f"names {record.policy_type!r}",
        )

    try:
        reproduced = framed_body_digest(
            adapter_id=adapter_id, policy_type=policy_type, projection=projection
        )
    except Exception as exc:  # noqa: BLE001 - a projection that will not canonicalize
        return (
            _Outcome.POLICY_PROJECTION_DIGEST_MISMATCH,
            f"the published projection does not canonicalize: {type(exc).__name__}",
        )
    if reproduced != record.policy_body_digest:
        return (
            _Outcome.POLICY_PROJECTION_DIGEST_MISMATCH,
            "the published projection does not reproduce the body digest the issuance "
            f"signature covered: reframing yields {reproduced!r} and the record carries "
            f"{record.policy_body_digest!r}",
        )
    return None


def _extract_capacity_bounds(coordinate, projection):
    """The authenticated bounds inside a reproduced projection, or ``None``.

    ``None`` means the resolved policy is not a capacity-bounds policy and states no bound.
    It never means unbounded: a consumer that needs a ceiling and finds none here has not
    been told the action is permitted, it has been told this policy does not speak to it.

    Keyed on the resolved coordinate's ``policy_family`` — the component the authority's
    registry matches on — rather than on the presence of a ``bounds`` key, so a foreign
    family that happens to carry that key is not read as a bounds statement.

    Called only after gate 14, so every value below is one the issuance signature covered.
    What this adds is that the bytes form a bound this profile can state exactly.
    """

    family = getattr(coordinate, "policy_family", None)
    if str(getattr(family, "value", family)) != CAPACITY_BOUNDS_POLICY_FAMILY:
        return None

    raw = projection.get(CAPACITY_BOUNDS_PROJECTION_KEY)
    if not isinstance(raw, (list, tuple)):
        raise _BoundsShapeError(
            f"a {CAPACITY_BOUNDS_POLICY_FAMILY} policy must carry a "
            f"{CAPACITY_BOUNDS_PROJECTION_KEY!r} sequence in its canonical projection; found "
            f"{type(raw).__name__}"
        )
    if not raw:
        raise _BoundsShapeError(
            f"a {CAPACITY_BOUNDS_POLICY_FAMILY} policy carrying no bound states nothing, and "
            "an artifact that states nothing must not read as one that bounds nothing"
        )

    bounds = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, Mapping):
            raise _BoundsShapeError(f"bounds[{index}] is not a mapping")
        absent = [key for key in CAPACITY_BOUND_FIELDS if key not in entry]
        if absent:
            raise _BoundsShapeError(f"bounds[{index}] omits {sorted(absent)}")
        extra = sorted(set(entry) - set(CAPACITY_BOUND_FIELDS))
        if extra:
            # A field this profile does not know is a field it cannot attest. Refusing keeps
            # "verified" meaning the routine evaluated everything it is carrying forward.
            raise _BoundsShapeError(
                f"bounds[{index}] carries {extra}, which this verification profile does not "
                "know how to state; a fact carried without being evaluated is not verified"
            )
        try:
            bounds.append(
                VerifiedCapacityBound(
                    action_type=entry["action_type"],
                    resource_class=entry["resource_class"],
                    max_permitted_magnitude=entry["max_permitted_magnitude"],
                    max_permitted_delta=entry["max_permitted_delta"],
                )
            )
        except Exception as exc:  # noqa: BLE001 - the typed refusal is the message
            raise _BoundsShapeError(f"bounds[{index}]: {exc}") from exc
    return tuple(bounds)


def _bound_reconciliation_problem(candidate, capacity_bounds):
    """R-8's reconciliation: the candidate's ceilings against the authenticated ones.

    Returns ``None`` when the candidate reconciles, or ``(outcome, detail)``.

    Four refusals, in a fixed precedence, each pinned by a test:

    #. the policy states no bound at all — the family does not supply capacity bounds;
    #. no authenticated bound is for this selector;
    #. more than one is;
    #. the one that is, is narrower than what the candidate carries or asks for.

    Selector matching is **exact and fail-closed** by ratification. ``action_type`` must be
    one of the controller's four canonical values, and ``resource_class`` must match exactly.
    ``None``, ``""``, a normalization difference and an unspecified selector are none of them
    equivalent, and none of them is a wildcard: a bound written for one resource class must
    not silently apply to another. A wildcard, if it is ever wanted, is an explicit schema
    addition, not an emergent property of a comparison.
    """

    scope = candidate.target_scope

    # 1. no bound at all. `capacity_bounds_fact=None` is a legitimate determination on its
    #    own; paired with a candidate it would mean "checked against nothing", so an artifact
    #    that reads as a reconciliation must not be mintable here.
    if not capacity_bounds:
        return (
            _Outcome.CANDIDATE_POLICY_STATES_NO_BOUNDS,
            "a candidate accompanied this request and the resolved policy states no capacity "
            "bound, so there is nothing to reconcile its ceilings against. A determination "
            "must not read as one that bounded this action when no bound existed",
        )

    # The selector, taken from the candidate and refused if it is outside the ratified
    # vocabulary. A scope built through Phase 5A cannot carry an unratified action type, but
    # this boundary accepts a candidate object it did not build.
    action_type = scope.action_type
    if type(action_type) is not str or action_type not in CANONICAL_ACTION_TYPES:
        return (
            _Outcome.CANDIDATE_BOUND_SELECTOR_MISS,
            f"the candidate's action_type {action_type!r} is not one of the D-4 canonical "
            f"action types {sorted(CANONICAL_ACTION_TYPES)}, so no authenticated bound can "
            "be selected for it",
        )
    resource_class = scope.resource_class

    matches = [
        bound
        for bound in capacity_bounds
        if bound.action_type == action_type and bound.resource_class == resource_class
    ]

    # 2. selector miss.
    if not matches:
        return (
            _Outcome.CANDIDATE_BOUND_SELECTOR_MISS,
            f"no authenticated bound is stated for (action_type={action_type!r}, "
            f"resource_class={resource_class!r}); the policy states bounds for "
            f"{sorted((b.action_type, b.resource_class) for b in capacity_bounds)!r}. "
            "Selector matching is exact: an unspecified or differently-spelled selector is "
            "not a wildcard, and this policy does not bound this action",
        )

    # 3. ambiguity. Which ceiling applies is then not determined by the policy body, and a
    #    verifier that picked one would be inventing the answer rather than reading it.
    if len(matches) > 1:
        return (
            _Outcome.CANDIDATE_BOUND_SELECTOR_AMBIGUOUS,
            f"{len(matches)} authenticated bounds are stated for "
            f"(action_type={action_type!r}, resource_class={resource_class!r}); which "
            "ceiling applies is not determined by the policy body",
        )

    bound = matches[0]

    # 4. the ceilings themselves. Narrower is allowed — a candidate may bind itself more
    #    tightly than the policy does. Looser never is. The *request* is compared against the
    #    authenticated ceiling too, as defence in depth: Phase 5A already checks it against
    #    the candidate's own copy, and this check does not depend on that copy being honest.
    for label, carried, authenticated in (
        ("max_permitted_magnitude", scope.max_permitted_magnitude, bound.max_permitted_magnitude),
        ("max_permitted_delta", scope.max_permitted_delta, bound.max_permitted_delta),
        ("requested_magnitude", scope.requested_magnitude, bound.max_permitted_magnitude),
        ("requested_delta", scope.requested_delta, bound.max_permitted_delta),
    ):
        if type(carried) is not int or isinstance(carried, bool):
            return (
                _Outcome.CANDIDATE_BOUND_EXCEEDED,
                f"the candidate's {label} is {type(carried).__name__}, not an int; a ceiling "
                "this routine cannot compare exactly is not one it will attest",
            )
        if carried > authenticated:
            return (
                _Outcome.CANDIDATE_BOUND_EXCEEDED,
                f"the candidate's {label} ({carried}) exceeds the authenticated bound "
                f"({authenticated}) stated for (action_type={action_type!r}, "
                f"resource_class={resource_class!r}). A candidate may bound itself more "
                "tightly than the policy does; it may never bound itself more loosely",
            )
    return None


#: What a candidate's policy coordinate must agree with, field by field: the six coordinate
#: components that identify the policy version, the content binding its signature covers, and
#: the issuing identity. Left is the candidate's field name; the pair beside it is where the
#: determination reads the truth from.
_RECONCILED_FIELDS: tuple = (
    ("policy_family", "coordinate", "policy_family"),
    ("policy_id", "coordinate", "policy_id"),
    ("policy_version", "coordinate", "version"),
    ("policy_content_digest", "coordinate", "content_digest"),
    ("policy_scope", "coordinate", "scope"),
    ("policy_tenant_id", "coordinate", "tenant_id"),
    ("policy_body_digest", "record", "policy_body_digest"),
    ("issuing_authority_id", "record", "issuing_authority_id"),
    ("key_id", "record", "key_id"),
    ("signature_alg", "record", "signature_alg"),
)


def _coordinate_disagreement(candidate, coordinate, record) -> Optional[str]:
    """Return why the candidate is about a different policy, or ``None`` if it is not.

    **Complete, not sampled.** All six coordinate components are compared, because exact-match
    lookup is the only lookup the authority's registry performs and a subset comparison would
    read as a binding while establishing less than one (D-5B1-5). ``policy_body_digest`` is
    compared too: it is the content binding the issuance signature covers (D-5B0B-2). The
    issuing identity is compared because the candidate asserts it and the determination knows
    it; a candidate naming another authority or key is not a candidate about this policy.

    The candidate's own ``binding_digest`` is not re-derived here. Phase 5A's type validates it
    at construction and refuses a mutated one, and a candidate that reached this boundary is
    one Phase 5A built — this package does not re-implement a neighbour's validation.
    """

    binding = getattr(candidate, "policy_coordinate_binding", None)
    if binding is None:
        return (
            "the candidate carries no policy coordinate binding; a candidate built before "
            "Phase 5A 0.2.0 cannot name a policy version, so this determination cannot be "
            "reconciled against it"
        )
    sources = {"coordinate": coordinate, "record": record}
    for field, source, attribute in _RECONCILED_FIELDS:
        expected = getattr(sources[source], attribute)
        actual = getattr(binding, field, None)
        if actual != expected:
            return (
                f"the candidate's policy coordinate disagrees on {field}: the candidate "
                f"names {actual!r} and the resolved policy is {expected!r}. Both artifacts "
                "may be individually genuine and the pair is still a misstatement"
            )
    return None


#: The one policy scope whose artifacts belong to a single tenant (R-9). Compared as a string
#: because the resolved coordinate reports it as one; the authoritative definition is
#: ``PolicyScope.TENANT`` in ``uvi-policy-contracts``, whose ``contracts/context.py`` refuses
#: cross-tenant binding in exactly this shape.
_TENANT_SCOPE: Final = "TENANT"


def _cross_tenant_binding(candidate, coordinate) -> Optional[str]:
    """Return why this policy may not bound this action, or ``None`` if it may.

    Keyed on the scope, never on a bare tenant equality: a ``GLOBAL`` policy carries the empty
    tenant, so ``!=`` alone would refuse every global policy in the platform. That asymmetry is
    the whole reason the guard reads the scope first.
    """

    scope = getattr(coordinate, "scope", None)
    if str(getattr(scope, "value", scope)) != _TENANT_SCOPE:
        return None
    policy_tenant = coordinate.tenant_id
    action_tenant = getattr(candidate, "tenant_id", None)
    if policy_tenant == action_tenant:
        return None
    return (
        f"cross-tenant policy binding: the resolved policy is {_TENANT_SCOPE}-scoped to "
        f"tenant {policy_tenant!r}, and the candidate's action is for tenant "
        f"{action_tenant!r}. A tenant's policy does not bound another tenant's action"
    )


#: The candidate's carried instants, classified by what each *means* — read off the upstream
#: contracts rather than inferred from the field names:
#:
#: * ``subject_valid_from_fact`` / ``subject_valid_until_fact`` are an explicit interval,
#:   inclusive on both ends. ``cloud-scaling-risk-integration``'s ``_require_within_validity``
#:   fails on ``now > valid_until`` and ``now < valid_from``, and this gate matches it exactly
#:   so the two boundaries cannot disagree about an instant.
#: * ``decision_expires_at_fact`` is an upper bound. Risk Authority's envelope issuer refuses
#:   on ``now > decision.expires_at``; same comparison, same inclusivity.
#: * the remaining three are *occurrence* instants — moments the candidate asserts already
#:   happened. A determination cannot be about a moment before its own evidence existed.
#: Every instant gate 13 compares. The two windows, the decision expiry, and the three
#: occurrence facts — six, and the same six Phase 5A admits exactly at construction.
_CARRIED_INSTANTS: Final = (
    "subject_valid_from_fact",
    "subject_valid_until_fact",
    "subject_asserted_at_fact",
    "decision_evaluated_at_fact",
    "decision_expires_at_fact",
    "attestation_issued_at_fact",
)


def _candidate_instant_type_problem(candidate):
    """Every carried instant is exactly a ``datetime``, re-checked at this boundary.

    Phase 5A admits these six exactly in ``__post_init__``. This package accepts a candidate
    object it did not build, and both ``object.__new__`` and ``pickle`` construct one without
    ever running ``__post_init__`` — so the admission upstream is not something this boundary
    may inherit. Measured before this check existed: a forged candidate carrying a single
    ``datetime`` subclass that overrides the comparison operators verified ``VERIFIED``
    against an instant outside every one of its windows, once for each of the six fields.

    No digest sees it. ``to_canonical_obj`` renders a subclass to exactly the string a plain
    ``datetime`` produces, so ``candidate_digest`` is unmoved. The type is the only place the
    difference survives.

    Runs **before** the comparisons, not beside them: a value that lies about ``<`` and ``>``
    cannot be caught by comparing it.
    """

    for name in _CARRIED_INSTANTS:
        value = getattr(candidate, name)
        if type(value) is not datetime:
            return (
                _Outcome.CANDIDATE_FACT_NOT_EXACT_INSTANT,
                f"the candidate's {name} is a {type(value).__name__}, not exactly a "
                "datetime. A subclass can override every comparison this gate makes and no "
                "digest can distinguish it, so the window checks below would be deciding "
                "against a value that answers them by fiat",
            )
    return None


_OCCURRENCE_FACTS: Final = (
    "subject_asserted_at_fact",
    "decision_evaluated_at_fact",
    "attestation_issued_at_fact",
)


def _candidate_validity_problem(candidate, instant):
    """Return ``(outcome, detail)`` when ``instant`` falls outside the candidate's validity.

    Ordered so the refusal a reader gets is the most specific one available: the two windows
    the owner named explicitly first, then the occurrence family.
    """

    valid_from = candidate.subject_valid_from_fact
    valid_until = candidate.subject_valid_until_fact
    if instant < valid_from:
        return (
            _Outcome.CANDIDATE_RECOMMENDATION_NOT_YET_VALID,
            f"the verified instant {instant.isoformat()} precedes the recommendation's "
            f"validity, which opens at {valid_from.isoformat()}",
        )
    if instant > valid_until:
        return (
            _Outcome.CANDIDATE_RECOMMENDATION_EXPIRED,
            f"the recommendation expired at {valid_until.isoformat()} and the verified "
            f"instant is {instant.isoformat()}; a determination about a dead recommendation "
            "is not a determination about this action",
        )
    expires_at = candidate.decision_expires_at_fact
    if instant > expires_at:
        return (
            _Outcome.CANDIDATE_DECISION_EXPIRED,
            f"the Risk Authority decision expired at {expires_at.isoformat()} and the "
            f"verified instant is {instant.isoformat()}. A live recommendation can carry a "
            "dead decision, so this is checked independently of the window above",
        )
    for name in _OCCURRENCE_FACTS:
        occurred_at = getattr(candidate, name)
        if instant < occurred_at:
            return (
                _Outcome.CANDIDATE_FACT_NOT_YET_OCCURRED,
                f"the candidate states {name} = {occurred_at.isoformat()}, which is after "
                f"the verified instant {instant.isoformat()}; the determination would be "
                "about a moment before the evidence it rests on came into being",
            )
    return None


def _terminal_outcome(exc: BaseException) -> _Outcome:
    """Classify an exception that escaped the routine. Every answer is a refusal.

    This package's own errors already carry the member they mean — a malformed field is
    ``COORDINATE_MALFORMED``, a failed artifact integrity check is ``INVARIANT_VIOLATION`` —
    and flattening all of them to ``VERIFICATION_UNAVAILABLE`` would tell a caller "the
    check could not run" when what happened is "the check ran and the artifact is bad".
    Those are different facts and a caller may reasonably act on them differently.

    Anything else is genuinely unavailable: a collaborator's exception, a stdlib error, a
    programming failure. ``VERIFIED`` can never be returned, whatever an exception claims to
    carry — an exception is not a success, and an attacker-influenced ``outcome`` attribute
    must not become one.
    """

    outcome = getattr(exc, "outcome", None) if isinstance(exc, _PackageError) else None
    if type(outcome) is not _Outcome or outcome is _Outcome.VERIFIED:
        return _Outcome.VERIFICATION_UNAVAILABLE
    return outcome


def _refuse(outcome: _Outcome, detail: str) -> PolicyAuthenticityResult:
    """Every refusal path in this module goes through here. No path returns success."""

    return PolicyAuthenticityResult(
        refusal=PolicyAuthenticityRefusal(outcome=outcome, detail=detail)
    )


def _mint_verified_artifact(
    *,
    record: IssuedPolicyRecord,
    coordinate: PolicyCoordinate,
    expected_reference_tenant_id: str,
    resolved_as_of: datetime,
    trust_configuration_digest: str,
    candidate_digest_fact: Optional[str],
    capacity_bounds_fact: Optional[tuple],
) -> VerifiedPolicyAuthenticity:
    """Assemble the verified artifact. Reached only after every gate above has succeeded."""

    # The two halves are assembled separately here, in the same partition the artifact's own
    # digest_payload() reports (D-5B0B-7). Nothing lands in `recorded` by omission: a fact is
    # there because nothing checked it, and an import-time guard in .verified refuses a field
    # that is in neither half.
    verified_map = {
        "policy_family": coordinate.policy_family,
        "policy_id": coordinate.policy_id,
        "policy_version": coordinate.version,
        "policy_content_digest": coordinate.content_digest,
        "policy_scope": coordinate.scope,
        "policy_tenant_id": coordinate.tenant_id,
        "policy_body_digest": record.policy_body_digest,
        "issuing_authority_id": record.issuing_authority_id,
        "key_id": record.key_id,
        "signature_alg": record.signature_alg,
        "record_id": record.record_id,
        "adapter_id": record.adapter_id,
        "expected_reference_tenant_id": expected_reference_tenant_id,
        "policy_trust_anchor_owner": POLICY_TRUST_ANCHOR_OWNER,
        "authority_protocol_id": POLICY_AUTHORITY_PROTOCOL_ID,
        "authority_canonicalization_version": POLICY_AUTHORITY_CANONICALIZATION_VERSION,
        "policy_issued_at_fact": record.issued_at,
        "verification_profile": VERIFICATION_PROFILE,
        "verification_profile_version": VERIFICATION_PROFILE_VERSION,
        # Verified since 5B-1: a supplied candidate is reconciled against the resolved
        # coordinate by gate 11, and ``None`` means no candidate accompanied this
        # determination — never that one was carried unchecked.
        "candidate_digest_fact": candidate_digest_fact,
        # Promoted in 5B-3 (R-8): gate 14 reproduces the body digest this value is framed
        # into, so substituting it changes the digest and is caught.
        "policy_type": record.policy_type,
        # New in 5B-3 (R-8): read out of a projection gate 14 already reproduced, so these
        # are the bounds the issuance signature covered. ``None`` means the resolved policy
        # states no bound — never that the action is unbounded.
        "capacity_bounds_fact": capacity_bounds_fact,
        # Framed into the verified half deliberately: that this artifact establishes policy
        # authenticity, grants nothing and is not historical are all gate outcomes.
        "outcome": _Outcome.VERIFIED.value,
        "grants_authority": False,
        "historical": False,
    }
    recorded_map = {
        # R-2: injected, unvalidated. trust_configuration_digest: reported by the port about
        # itself. See RECORDED_FACT_NAMES for each reason in full. Two facts have left this
        # half: candidate_digest_fact in 5B-1 when gate 11 began reconciling it, and
        # policy_type in 5B-3 when gate 14 began reproducing the digest it is framed into.
        "resolved_as_of_fact": resolved_as_of,
        "trust_configuration_digest": trust_configuration_digest,
    }
    # R-7: the maps and the canonical declaration are compared before anything is minted, so
    # a name added here and forgotten in verified.py (or the reverse) fails loudly and says
    # which side is short. `DERIVED_FACT_NAMES` is why the two sets differ at all.
    require_partition_agreement(verified_map=verified_map, recorded_map=recorded_map)
    return _record_minted(
        VerifiedPolicyAuthenticity(
            **{k: v for k, v in verified_map.items() if k not in DERIVED_FACT_NAMES},
            **recorded_map,
            artifact_digest=_partitioned_digest(
                verified_map=verified_map, recorded_map=recorded_map
            ),
            construction_token=_VERIFICATION_TOKEN,
        )
    )
