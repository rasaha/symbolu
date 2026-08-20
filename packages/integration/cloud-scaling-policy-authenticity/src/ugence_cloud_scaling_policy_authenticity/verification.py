"""The authoritative policy-authenticity verification routine.

The whole point, in one sentence
--------------------------------
The verifier asks the Policy Authority's own trusted-resolution path about **one exact
coordinate at one injected instant**, and then refuses to treat the answer as a
determination unless it is a non-historical ``RESOLVED`` about *that* coordinate at *that*
instant, whose record binds its own body digest into its own identity.

Why that is more than "call ``resolve_policy`` and check the status"
---------------------------------------------------------------------
Four gates exist here that the authority does not perform for a consumer:

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
#. **digest shape** — both digests are bare 64-hex Policy Authority digests.

Only after all ten does a :class:`~.verified.VerifiedPolicyAuthenticity` exist.

Three checks deliberately sit **outside** that list, and the count stays ten because none of
them is a gate on an input. The trust identity is snapshotted once, at *construction*, and
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
datetime is refused rather than assumed UTC. Whose clock supplies it is ADR residual **R-2**,
open, and this implementation proceeds with ``as_of`` injected and **unvalidated** by explicit
owner authorization. A determination is therefore only as honest as the instant it was handed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_cloud_scaling_authorization_contracts import CapacityAuthorizationCandidate
from ugence_policy_authority.api import (
    IssuedPolicyRecord,
    PolicyCoordinate,
    PolicyResolution,
    PolicyResolutionStatus,
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
    POLICY_AUTHENTICITY_DIGEST_DOMAIN,
    POLICY_AUTHORITY_CANONICALIZATION_VERSION,
    POLICY_AUTHORITY_PROTOCOL_ID,
    POLICY_TRUST_ANCHOR_OWNER,
    SUPPORTED_SIGNATURE_ALGORITHMS,
    VERIFICATION_PROFILE,
    VERIFICATION_PROFILE_VERSION,
)
from .outcomes import PolicyAuthenticityOutcome as _Outcome
from .outcomes import resolution_reason_outcome
from .resolution_port import require_production_resolution_port
from .verified import (
    _VERIFICATION_TOKEN,
    VerifiedPolicyAuthenticity,
    _partitioned_digest,
    _record_minted,
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
        """Refuse a verified branch whose resolution is about a different policy.

        Three comparisons, each closing a way the two halves could disagree: the resolution
        must be *about* the coordinate the artifact names, it must have *found* a record
        under that coordinate, and that record's signed body digest must be the one the
        artifact binds.
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
    another when the artifact is stamped, which is the one fact the artifact exists to pin.
    A verifier is therefore bound to one trust configuration for its whole life; a changed
    configuration means a new port and a new verifier.
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

        ``candidate`` is **optional and never reconciled**. When supplied, its digest is
        recorded on the verified artifact as the scope of the determination — which candidate
        this proof accompanied — and nothing about it is compared against the policy. A Phase
        5A binding cannot name a coordinate (D-5B0B-3), so there is nothing here to compare
        it with; binding the two is 5B-1's work. See :mod:`.verified`.

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

        # === every gate succeeded — and only now does an artifact exist =================
        artifact = _mint_verified_artifact(
            record=record,
            coordinate=coordinate,
            expected_reference_tenant_id=expected_reference_tenant_id,
            resolved_as_of=instant,
            trust_configuration_digest=self._trust_configuration_digest,
            candidate_digest_fact=None if candidate is None else candidate.candidate_digest,
        )
        return PolicyAuthenticityResult(verified_policy=artifact, resolution=resolution)

    def __repr__(self) -> str:
        return (
            f"PolicyAuthenticityVerifier(port={type(self._port).__name__}, "
            f"production_mode={self._production_mode})"
        )


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
        "policy_type": record.policy_type,
        "expected_reference_tenant_id": expected_reference_tenant_id,
        "trust_configuration_digest": trust_configuration_digest,
        "policy_trust_anchor_owner": POLICY_TRUST_ANCHOR_OWNER,
        "authority_protocol_id": POLICY_AUTHORITY_PROTOCOL_ID,
        "authority_canonicalization_version": POLICY_AUTHORITY_CANONICALIZATION_VERSION,
        "policy_issued_at_fact": record.issued_at,
        "verification_profile": VERIFICATION_PROFILE,
        "verification_profile_version": VERIFICATION_PROFILE_VERSION,
        # Framed into the verified half deliberately: that this artifact establishes policy
        # authenticity, grants nothing and is not historical are all gate outcomes.
        "outcome": _Outcome.VERIFIED.value,
        "grants_authority": False,
        "historical": False,
    }
    recorded_map = {
        # R-2: injected, unvalidated. R-4: recorded, never reconciled.
        "resolved_as_of_fact": resolved_as_of,
        "candidate_digest_fact": candidate_digest_fact,
    }
    derived = ("outcome", "grants_authority", "historical")
    return _record_minted(
        VerifiedPolicyAuthenticity(
            **{key: value for key, value in verified_map.items() if key not in derived},
            **recorded_map,
            artifact_digest=_partitioned_digest(
                verified_map=verified_map, recorded_map=recorded_map
            ),
            construction_token=_VERIFICATION_TOKEN,
        )
    )
