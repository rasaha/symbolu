"""The Cloud Scaling recommendation authenticity boundary (ADR §7, Phase 4C).

Read this before relying on any guarantee in this package.

What Phase 4A/4B established
----------------------------
``validate_subject_binding`` proves *internal canonical consistency* of a v2 request: the
carried ``subject_digest`` reconciles with a binding reconstructed from authoritative
outer fields over a re-validated context. It detects **inconsistent or partial
tampering** — an altered field left paired with a stale digest. It does **not** detect a
*fully self-consistent fabricated request*, because a caller who recomputes every digest
produces an internally consistent object by construction. Phase 4A/4B therefore establish
integrity, never source authenticity.

What Phase 4C establishes here
------------------------------
This module establishes the *Cloud Scaling recommendation boundary* that Phase 4A/4B
deliberately left open. For a serialized recommendation it:

1. accepts **only** the canonical controller type or its canonical serialized form —
   a duck-typed look-alike is refused at the type boundary;
2. reconstructs the serialized form through the controller's own strict
   ``CapacityActionRecommendation.from_dict``, which rejects unknown and missing fields
   and re-runs the full ``__post_init__`` revalidation (digest rebinding, candidate-set
   equality, score/feasibility/cost recomputation, temporal safety);
3. **independently recomputes** ``rec.digest()`` from that reconstruction;
4. compares the recomputation with the **independently carried** ``evidence_digest``
   from the input document.

Step 4 is genuinely independent, and this is the load-bearing fact: the controller's
``from_dict`` accepts ``evidence_digest`` as a known field but **never validates it and
never passes it to the constructor** — it is discarded. The recomputed value is therefore
derived purely from the record's *content*, while the compared value comes purely from
the *input document*. A payload whose content was altered while ``evidence_digest`` was
left stale reconstructs successfully and then fails here. This is not the forbidden
self-referential check (``rec.digest() == rec.digest()``), which would prove nothing.

The in-process object path
--------------------------
A live :class:`CapacityActionRecommendation` carries no digest field of its own —
``evidence_digest`` is excluded from the dataclass and computed on demand. An in-process
object has also, by construction, already passed ``__post_init__``, so recomputing its
own digest is exactly the self-referential check that proves nothing. On that path the
caller **must** therefore supply ``expected_recommendation_digest``: an independently
carried expectation (from a decision log, an audit record, or the transport that
delivered the recommendation). Absent it, this module raises
:class:`~.errors.MissingIndependentDigestError` rather than proceeding — it will not
claim an authenticity it cannot establish.

What Phase 4C still does NOT prove
----------------------------------
* **Not a signature.** The controller digest is a canonical content *identity*, computed
  with an unkeyed SHA-256 over a domain-separated preimage. It proves that the content
  hashes to the expected value; it proves nothing about **who** produced it.
* **The expectation's own provenance is assumed, not verified.** On the object path the
  adapter cannot verify where ``expected_recommendation_digest`` came from. A caller that
  computes it from the same object it passes in has performed the self-referential check
  itself; the adapter has no way to detect that.
* **A fully self-consistent forgery still passes.** An attacker able to author a complete,
  internally valid ``CapacityActionRecommendation`` — one whose forecast evidence, cost
  book, topology, constraints, policy and candidate set all recompute consistently — and
  to serialize it with a matching ``evidence_digest`` produces an authentic-looking input.
  Detecting *that* requires a signed provenance chain over the controller's output, which
  does not exist anywhere in the repository today and which Phase 4C does not invent.
* **Evidence provenance is out of scope.** The evidence references projected onto the
  outer request are opaque digest strings. Whether they resolve to admitted, trusted,
  fresh evidence is RA-5's question, answered behind the seam.

**The remaining upstream trust assumption, stated plainly:** Phase 4C trusts that the
canonical recommendation document (or the independently carried digest expectation)
reached the adapter over a channel the composition root trusts. Establishing *that* is a
transport/provenance concern and remains unaddressed. No placeholder authenticator is
added here, because a placeholder would read as a control while providing none.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final, Mapping, Optional, Union

from ugence_cloud_scaling_controller.planning.recommendation import (
    RECOMMENDATION_ABSTENTION_SCHEMA_VERSION,
    RECOMMENDATION_SCHEMA_VERSION,
    CapacityActionRecommendation,
    RecommendationAbstention,
    RecommendationError,
)

from .errors import (
    MissingIndependentDigestError,
    RecommendationAuthenticityError,
    RecommendationInputError,
    UnsupportedRecommendationSourceError,
)

__all__ = [
    "CARRIED_DIGEST_FIELD",
    "AuthenticatedRecommendation",
    "AuthenticatedAbstention",
    "DigestExpectationSource",
    "authenticate_controller_output",
]

#: The field name under which the controller's canonical serialized form carries the
#: recommendation's own digest. ``from_dict`` accepts but never validates it, which is
#: precisely what makes it usable as an independent expectation here.
CARRIED_DIGEST_FIELD: Final[str] = "evidence_digest"

_DIGEST_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")

_ControllerOutput = Union[
    CapacityActionRecommendation, RecommendationAbstention, Mapping[str, Any]
]


class DigestExpectationSource:
    """Where the independent digest expectation that was checked came from.

    A namespace of canonical strings recorded on the authenticated result purely for
    auditability — it carries no authority and selects no behavior.
    """

    #: Carried inside the canonical serialized document, ignored by ``from_dict``.
    CARRIED_CANONICAL_FORM: Final[str] = "carried_canonical_form"
    #: Supplied by the caller as an independently obtained expectation.
    CALLER_SUPPLIED_EXPECTATION: Final[str] = "caller_supplied_expectation"
    #: Both were present and both matched the recomputation.
    CARRIED_AND_CALLER_SUPPLIED: Final[str] = "carried_and_caller_supplied"

    ALL: Final[frozenset[str]] = frozenset(
        {
            "carried_canonical_form",
            "caller_supplied_expectation",
            "carried_and_caller_supplied",
        }
    )


@dataclass(frozen=True)
class AuthenticatedRecommendation:
    """A reconstructed recommendation whose digest reconciled with an independent value.

    An **integrity-and-source finding, not a grant**. Reaching it means the content
    hashes to an independently carried expectation; it grants nothing, evaluates nothing
    and authorizes nothing. Every authority flag is fixed ``False`` at construction.
    """

    recommendation: CapacityActionRecommendation
    recommendation_digest: str
    expectation_source: str
    # Fixed non-authority invariants — authenticating an input is not an evaluation.
    risk_evaluated: bool = False
    authority_granted: bool = False
    envelope_issued: bool = False
    actiongate_invoked: bool = False
    credential_issued: bool = False
    actuation_performed: bool = False
    effect_verified: bool = False
    executable: bool = False

    def __post_init__(self) -> None:
        _assert_no_authority(self)
        if not isinstance(self.recommendation, CapacityActionRecommendation):
            raise RecommendationInputError(
                "recommendation must be a CapacityActionRecommendation"
            )
        _require_digest_syntax("recommendation_digest", self.recommendation_digest)


@dataclass(frozen=True)
class AuthenticatedAbstention:
    """A reconstructed controller abstention — a typed **non**-recommendation.

    It never becomes a scaling recommendation, never enters the Risk Authority
    evaluation seam and never manufactures a subject digest. It exists so the adapter can
    report the upstream non-evaluation faithfully, carrying the controller's own typed
    reason and whatever input digests the controller had bound before abstaining.
    """

    abstention: RecommendationAbstention
    abstention_digest: Optional[str] = None
    expectation_source: Optional[str] = None
    risk_evaluated: bool = False
    authority_granted: bool = False
    envelope_issued: bool = False
    actiongate_invoked: bool = False
    credential_issued: bool = False
    actuation_performed: bool = False
    effect_verified: bool = False
    executable: bool = False

    def __post_init__(self) -> None:
        _assert_no_authority(self)
        if not isinstance(self.abstention, RecommendationAbstention):
            raise RecommendationInputError("abstention must be a RecommendationAbstention")
        if self.abstention_digest is not None:
            _require_digest_syntax("abstention_digest", self.abstention_digest)


_AUTHORITY_FLAGS = (
    "risk_evaluated",
    "authority_granted",
    "envelope_issued",
    "actiongate_invoked",
    "credential_issued",
    "actuation_performed",
    "effect_verified",
    "executable",
)


def _assert_no_authority(record: Any) -> None:
    for flag in _AUTHORITY_FLAGS:
        if getattr(record, flag) is not False:
            raise RecommendationAuthenticityError(
                f"{flag} must be False — authenticating an input grants no authority"
            )


def _require_digest_syntax(name: str, value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, str):
        raise RecommendationAuthenticityError(f"{name} must be a string")
    if not _DIGEST_RE.match(value):
        raise RecommendationAuthenticityError(
            f"{name} must be a canonical digest ('sha256:' + 64 lowercase hex)"
        )
    return value


def _reconcile(
    recomputed: str,
    *,
    carried: Optional[str],
    expected: Optional[str],
    artifact: str,
) -> str:
    """Require the recomputation to equal every independent expectation supplied.

    At least one independent expectation is mandatory: with none, there is nothing to
    compare against but the object itself, and asserting authenticity from that would be
    the self-referential check this module exists to avoid.
    """

    expectations: list[tuple[str, str]] = []
    if carried is not None:
        expectations.append(
            (DigestExpectationSource.CARRIED_CANONICAL_FORM, _require_digest_syntax(
                f"carried {artifact} digest", carried))
        )
    if expected is not None:
        expectations.append(
            (DigestExpectationSource.CALLER_SUPPLIED_EXPECTATION, _require_digest_syntax(
                f"expected {artifact} digest", expected))
        )
    if not expectations:
        raise MissingIndependentDigestError(
            f"no independent {artifact} digest is available to check: the canonical "
            f"serialized form carried no {CARRIED_DIGEST_FIELD!r} and no "
            "expected_recommendation_digest was supplied. Recomputing the object's own "
            "digest and comparing it to itself would prove nothing, so this fails closed."
        )
    for source, value in expectations:
        if value != recomputed:
            raise RecommendationAuthenticityError(
                f"{artifact} digest mismatch: recomputed {recomputed} but the "
                f"{source} expectation is {value} (fail closed, no request constructed, "
                "no evaluation performed)"
            )
    if len(expectations) == 2:
        return DigestExpectationSource.CARRIED_AND_CALLER_SUPPLIED
    return expectations[0][0]


def _carried_digest(document: Mapping[str, Any]) -> Optional[str]:
    value = document.get(CARRIED_DIGEST_FIELD)
    return value if value is not None else None


def _schema_tag(document: Mapping[str, Any]) -> Optional[str]:
    tag = document.get("schema_version")
    return tag if isinstance(tag, str) else None


def authenticate_controller_output(
    source: _ControllerOutput,
    *,
    expected_recommendation_digest: Optional[str] = None,
) -> Union[AuthenticatedRecommendation, AuthenticatedAbstention]:
    """Establish the Cloud Scaling recommendation boundary for ``source``.

    ``source`` is either a live controller artifact (``CapacityActionRecommendation`` or
    ``RecommendationAbstention``) or its canonical serialized form (a mapping carrying an
    explicit ``schema_version``). Nothing else is accepted: a duck-typed look-alike is
    refused here, before any digest is computed and long before the seam exists.

    :param expected_recommendation_digest: an independently obtained expectation.
        **Required** on the live-object path (see the module docstring); optional — and
        checked as an *additional* independent constraint — on the serialized path.
    :raises RecommendationInputError: unsupported input type, unrecognized schema tag, or
        a strict reconstruction failure reported by the controller.
    :raises RecommendationAuthenticityError: no independent digest was available, or a
        supplied one did not equal the recomputation.
    """

    if expected_recommendation_digest is not None:
        _require_digest_syntax(
            "expected_recommendation_digest", expected_recommendation_digest
        )

    # --- live controller artifacts -------------------------------------------------
    if isinstance(source, CapacityActionRecommendation):
        # No carried digest exists on an in-process object, so the caller's independent
        # expectation is the only thing that can make this check load-bearing.
        expectation_source = _reconcile(
            source.digest(),
            carried=None,
            expected=expected_recommendation_digest,
            artifact="recommendation",
        )
        return AuthenticatedRecommendation(
            recommendation=source,
            recommendation_digest=source.digest(),
            expectation_source=expectation_source,
        )

    if isinstance(source, RecommendationAbstention):
        # An abstention is never projected, so an expectation is optional here; when one
        # is supplied it is still checked, and a mismatch still fails closed.
        object_abstention_source = None
        if expected_recommendation_digest is not None:
            object_abstention_source = _reconcile(
                source.digest(),
                carried=None,
                expected=expected_recommendation_digest,
                artifact="abstention",
            )
        return AuthenticatedAbstention(
            abstention=source,
            abstention_digest=source.digest(),
            expectation_source=object_abstention_source,
        )

    # --- canonical serialized forms --------------------------------------------------
    if not isinstance(source, Mapping):
        raise UnsupportedRecommendationSourceError(
            "source must be a CapacityActionRecommendation, a RecommendationAbstention, "
            f"or one of their canonical serialized forms; got {type(source).__name__}"
        )

    tag = _schema_tag(source)
    if tag is None:
        raise UnsupportedRecommendationSourceError(
            "a canonical serialized controller artifact requires an explicit "
            "string 'schema_version'"
        )

    carried = _carried_digest(source)

    if tag == RECOMMENDATION_SCHEMA_VERSION:
        try:
            # Strict reconstruction: unknown fields, missing fields, non-canonical values
            # and every internally inconsistent relationship fail closed in the
            # controller's own __post_init__. `evidence_digest` is accepted as a known
            # key here but is never fed to the constructor, which is what keeps the
            # comparison below independent of the reconstruction.
            recommendation = CapacityActionRecommendation.from_dict(source)
        except RecommendationError as exc:
            raise RecommendationInputError(
                f"canonical recommendation failed strict reconstruction: {exc}"
            ) from exc
        recomputed = recommendation.digest()
        expectation_source = _reconcile(
            recomputed,
            carried=carried,
            expected=expected_recommendation_digest,
            artifact="recommendation",
        )
        return AuthenticatedRecommendation(
            recommendation=recommendation,
            recommendation_digest=recomputed,
            expectation_source=expectation_source,
        )

    if tag == RECOMMENDATION_ABSTENTION_SCHEMA_VERSION:
        try:
            abstention = RecommendationAbstention.from_dict(source)
        except RecommendationError as exc:
            raise RecommendationInputError(
                f"canonical abstention failed strict reconstruction: {exc}"
            ) from exc
        recomputed = abstention.digest()
        abstention_source = None
        if carried is not None or expected_recommendation_digest is not None:
            abstention_source = _reconcile(
                recomputed,
                carried=carried,
                expected=expected_recommendation_digest,
                artifact="abstention",
            )
        return AuthenticatedAbstention(
            abstention=abstention,
            abstention_digest=recomputed,
            expectation_source=abstention_source,
        )

    raise UnsupportedRecommendationSourceError(
        f"unsupported controller schema_version: {tag!r} (expected "
        f"{RECOMMENDATION_SCHEMA_VERSION!r} or "
        f"{RECOMMENDATION_ABSTENTION_SCHEMA_VERSION!r})"
    )
