"""``CloudScalingRiskAdapter`` — the production entry point for Phase 4C.

The adapter is a thin, non-authoritative composition of three things it does not own:
the controller's canonical recommendation contract, the Risk Authority v2 request
contract, and an **injected** evaluation seam and trusted clock. It holds no policy, no
control catalog, no evidence source, no keys, no credentials and no execution surface.

It never instantiates a reference resolver, a permissive authority, a fake evidence
source, a default-allow policy, a test clock or a placeholder authenticator — there is no
factory, default argument or fallback anywhere in this module that could produce one.
Both dependencies are required at construction and neither has a default.

Ordered gates, all of which must pass **before** the seam is reached:

1. **Authenticity** — accept only the canonical controller artifact or its canonical
   serialized form; reconstruct strictly; recompute the recommendation digest;
   reconcile it against an independently carried or supplied expectation.
2. **Abstention** — a controller abstention short-circuits to a typed non-evaluation and
   never enters the seam.
3. **Projection** — build the curated neutral context and the full binding chain, and
   verify locally that it reconciles.
4. **Validity** — re-check the recommendation's validity window against the **injected
   trusted clock**; an expired or not-yet-valid recommendation never reaches evaluation.

Only then is ``seam.evaluate(request)`` called, with ``evaluation_time=None`` so the seam
uses its own trusted clock as the sole evaluation-time authority.

**Two boundaries this adapter does not police, stated plainly.**

*Seam grade.* The adapter cannot verify that an injected seam is production-grade: the
seam exposes no public production flag, and inferring one from a private attribute would
be a guess dressed as a control. Supplying a seam built by
``RiskEvaluationSeam.production(...)`` — which itself fails closed on any reference-grade
dependency — is the composition root's responsibility.

*Shared clock.* The adapter's validity re-check and the seam's own expiry check read
**different clock objects**. If they disagree across a validity boundary, the seam's
check governs and fails closed with its typed ``EXPIRED_SUBJECT`` non-decision — the
disagreement can never open the window, only close it. Composition roots should inject
**the same trusted clock** into both; that requirement is documented, not enforceable
from inside the adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Protocol, Union, runtime_checkable

from risk_authority.integrations import SubjectRiskDecision

from .authenticity import (
    AuthenticatedAbstention,
    AuthenticatedRecommendation,
    _validate_authenticated_abstention,
    _validate_authenticated_output,
    authenticate_controller_output,
)
from .errors import (
    AdapterConfigurationError,
    MissingIndependentDigestError,
    NonExecutableInvariantError,
    ProjectionError,
    RecommendationAuthenticityError,
    RecommendationInputError,
    RecommendationNotYetValidError,
    RecommendationValidityError,
    UnsupportedRecommendationSourceError,
)
from .outcomes import (
    AdapterOutcomeStatus,
    AdapterRejectionReason,
    CloudScalingRiskOutcome,
)
from .projection import CapacityRiskSubjectProjection, project_recommendation

__all__ = ["RiskEvaluationSeamPort", "CloudScalingRiskAdapter"]

_ControllerOutput = Union[Any, Mapping[str, Any]]


@runtime_checkable
class RiskEvaluationSeamPort(Protocol):
    """The narrow production-facing surface the adapter needs from Risk Authority.

    Exactly one method, and deliberately no more: the adapter must be structurally
    incapable of reaching envelope issuance, ActionGate authorization, credential
    issuance or any execution path, and the narrowest possible port is how that is
    guaranteed rather than merely promised.
    ``risk_authority.api.evaluation_seam.RiskEvaluationSeam`` satisfies it as-is.
    """

    def evaluate(self, request: Any) -> SubjectRiskDecision: ...


class CloudScalingRiskAdapter:
    """Project a Cloud Scaling recommendation to Risk Authority and stop at the decision."""

    def __init__(
        self,
        *,
        seam: RiskEvaluationSeamPort,
        clock: Callable[[], datetime],
    ) -> None:
        """
        :param seam: an **already-constructed** production ``RiskEvaluationSeam`` (or a
            narrow production-facing port satisfying :class:`RiskEvaluationSeamPort`).
            The adapter never builds one.
        :param clock: the injected trusted clock used **only** for the adapter-side
            recommendation-expiry re-check. It is never forwarded to Risk Authority and
            never becomes an evaluation time.
        """

        if seam is None:
            raise AdapterConfigurationError(
                "an already-constructed production RiskEvaluationSeam (or narrow "
                "production-facing port) is required; the adapter never builds one"
            )
        if not callable(getattr(seam, "evaluate", None)):
            raise AdapterConfigurationError(
                "seam must satisfy RiskEvaluationSeamPort (a callable 'evaluate')"
            )
        if clock is None or not callable(clock):
            raise AdapterConfigurationError(
                "an injected trusted clock is required; the adapter holds no clock of "
                "its own and substitutes no default"
            )
        self._seam = seam
        self._clock = clock

    # ------------------------------------------------------------------ public API
    def project(
        self,
        source: _ControllerOutput,
        *,
        expected_recommendation_digest: Optional[str] = None,
    ) -> CapacityRiskSubjectProjection:
        """Authenticate and project ``source`` **without** calling the seam.

        Raises rather than returning a typed outcome, so a caller composing the pure
        pieces directly cannot ignore a failure. Used by
        :meth:`evaluate` and available for offline verification of the binding chain.
        """

        authenticated = authenticate_controller_output(
            source, expected_recommendation_digest=expected_recommendation_digest
        )
        # Defensive revalidation at the public boundary. ``authenticate_controller_output``
        # cannot return an invalid token today, so this is redundant *now* — which is the
        # point: the invariant every consumer relies on is re-established at the boundary
        # that relies on it, not inherited from a caller's good behavior. It runs before
        # any context, binding or request exists and before the seam is reachable.
        _validate_authenticated_output(authenticated)
        if type(authenticated) is AuthenticatedAbstention:
            raise ProjectionError(
                "a controller abstention is not a recommendation and is never projected "
                "into a Risk Authority request"
            )
        return project_recommendation(authenticated)

    def evaluate(
        self,
        source: _ControllerOutput,
        *,
        expected_recommendation_digest: Optional[str] = None,
    ) -> CloudScalingRiskOutcome:
        """Run every adapter gate and, only if all pass, obtain a risk decision.

        Always returns a typed :class:`CloudScalingRiskOutcome`; never raises for an
        input-side failure, and never returns an approval for one.
        """

        # --- gate 1: authenticity ----------------------------------------------------
        # Each branch dispatches on the error TYPE, so the audit reason cannot drift out
        # of sync with the failure by way of an edited message string. Subclasses are
        # matched before their base classes.
        try:
            authenticated = authenticate_controller_output(
                source, expected_recommendation_digest=expected_recommendation_digest
            )
            # Defensive revalidation of the token before anything is done with it: the
            # exact token type, the exact embedded canonical type, the digest syntax and
            # the digest-equals-content invariant. Placed inside this try so a token that
            # fails it produces the same typed fail-closed outcome as a bad input would,
            # never an escaping exception. Nothing has yet read the clock, built a
            # context, a binding or a request, or touched the seam.
            _validate_authenticated_output(authenticated)
        except UnsupportedRecommendationSourceError as exc:
            return self._rejected(
                AdapterRejectionReason.UNSUPPORTED_INPUT_TYPE, str(exc)
            )
        except RecommendationInputError as exc:
            return self._rejected(
                AdapterRejectionReason.MALFORMED_RECOMMENDATION, str(exc)
            )
        except MissingIndependentDigestError as exc:
            return self._rejected(
                AdapterRejectionReason.MISSING_INDEPENDENT_RECOMMENDATION_DIGEST, str(exc)
            )
        except RecommendationAuthenticityError as exc:
            return self._rejected(
                AdapterRejectionReason.RECOMMENDATION_DIGEST_MISMATCH, str(exc)
            )

        # --- gate 2: upstream abstention ---------------------------------------------
        if type(authenticated) is AuthenticatedAbstention:
            return self._abstained(authenticated)

        # --- gate 3: projection -------------------------------------------------------
        try:
            projection = project_recommendation(authenticated)
        except RecommendationInputError as exc:
            # ``project_recommendation`` re-runs the token check independently of the
            # revalidation above; if the two ever disagreed, the stricter one must still
            # produce a typed outcome rather than an escaping exception.
            return self._rejected(
                AdapterRejectionReason.UNSUPPORTED_INPUT_TYPE,
                str(exc),
                tenant_id=_safe_tenant(authenticated),
                subject_id=_safe_subject(authenticated),
                recommendation_digest=getattr(authenticated, "recommendation_digest", None),
            )
        except RecommendationAuthenticityError as exc:
            return self._rejected(
                AdapterRejectionReason.RECOMMENDATION_DIGEST_MISMATCH,
                str(exc),
                tenant_id=_safe_tenant(authenticated),
                subject_id=_safe_subject(authenticated),
                recommendation_digest=getattr(authenticated, "recommendation_digest", None),
            )
        except ProjectionError as exc:
            return self._rejected(
                AdapterRejectionReason.PROJECTION_FAILED,
                str(exc),
                tenant_id=_safe_tenant(authenticated),
                subject_id=_safe_subject(authenticated),
                recommendation_digest=getattr(authenticated, "recommendation_digest", None),
            )

        # --- gate 4: validity against the injected trusted clock ----------------------
        try:
            now = self._trusted_now()
        except AdapterConfigurationError as exc:
            return self._rejected(
                AdapterRejectionReason.UNTRUSTED_CLOCK, str(exc), projection=projection
            )
        try:
            _require_within_validity(now, projection)
        except RecommendationNotYetValidError as exc:
            return self._rejected(
                AdapterRejectionReason.RECOMMENDATION_NOT_YET_VALID,
                str(exc),
                projection=projection,
            )
        except RecommendationValidityError as exc:
            return self._rejected(
                AdapterRejectionReason.RECOMMENDATION_EXPIRED,
                str(exc),
                projection=projection,
            )

        # --- only now may the seam be reached ----------------------------------------
        request = projection.request
        # Defence in depth: the projection has no parameter for an evaluation time and
        # asserts its absence, but the trusted-time invariant is re-checked immediately
        # before submission so no future refactor can quietly forward a caller's clock.
        if request.evaluation_time is not None:  # pragma: no cover - structurally absent
            raise NonExecutableInvariantError(
                "evaluation_time must be None on the trusted v2 path"
            )
        decision = self._seam.evaluate(request)
        if not isinstance(decision, SubjectRiskDecision):
            raise NonExecutableInvariantError(
                "the evaluation seam must return a canonical SubjectRiskDecision; "
                f"got {type(decision).__name__}"
            )
        return CloudScalingRiskOutcome(
            status=AdapterOutcomeStatus.RISK_DECISION,
            decision=decision,
            projection=projection,
            tenant_id=projection.tenant_id,
            subject_id=projection.subject_id,
            recommendation_digest=projection.recommendation_digest,
            evidence_references=projection.evidence_references,
        )

    # ------------------------------------------------------------------ internals
    def _trusted_now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime):
            raise AdapterConfigurationError("the injected clock must return a datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise AdapterConfigurationError(
                "the injected clock must return a timezone-aware datetime; a naive "
                "value is rejected rather than assumed UTC"
            )
        return now.astimezone(timezone.utc)

    def _rejected(
        self,
        reason: AdapterRejectionReason,
        detail: str,
        *,
        projection: Optional[CapacityRiskSubjectProjection] = None,
        tenant_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        recommendation_digest: Optional[str] = None,
    ) -> CloudScalingRiskOutcome:
        if projection is not None:
            tenant_id = projection.tenant_id
            subject_id = projection.subject_id
            recommendation_digest = projection.recommendation_digest
        return CloudScalingRiskOutcome(
            status=AdapterOutcomeStatus.PROJECTION_REJECTED,
            projection=projection,
            rejection_reason=reason,
            detail=detail,
            tenant_id=tenant_id,
            subject_id=subject_id,
            recommendation_digest=recommendation_digest,
            evidence_references=(
                projection.evidence_references if projection is not None else ()
            ),
        )

    def _abstained(self, authenticated: AuthenticatedAbstention) -> CloudScalingRiskOutcome:
        """Carry an upstream abstention through as a typed non-evaluation.

        No request is built, no subject digest is manufactured and the seam is not
        called. The controller's own typed reason and the input digests it had bound
        before abstaining are preserved so the record is auditable — and nothing beyond
        them is claimed, because nothing beyond them was evaluated.
        """

        # Symmetric defensive revalidation: exact token type, exact canonical abstention
        # type, and a carried digest that actually describes the carried abstention. An
        # abstention never reaches the seam by construction, so this closes the remaining
        # bypass — a fabricated abstention token reporting an upstream non-evaluation it
        # cannot substantiate.
        abstention = _validate_authenticated_abstention(authenticated)
        references = tuple(
            sorted(
                {
                    value
                    for value in (
                        abstention.forecast_evidence_digest,
                        abstention.canonical_state_digest,
                        abstention.topology_digest,
                        abstention.cost_evidence_digest,
                        abstention.constraint_digest,
                        abstention.policy_digest,
                    )
                    if isinstance(value, str) and value.startswith("sha256:")
                }
            )
        )
        return CloudScalingRiskOutcome(
            status=AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM,
            abstention_reason=abstention.reason.value,
            detail=abstention.detail,
            tenant_id=abstention.subject.tenant_id,
            subject_id=abstention.subject.workload_id,
            # Deliberately NOT the abstention's own digest: `recommendation_digest` names
            # the digest of an evaluated recommendation, and no recommendation existed.
            recommendation_digest=None,
            evidence_references=references,
        )


def _require_within_validity(
    now: datetime, projection: CapacityRiskSubjectProjection
) -> None:
    """Fail closed outside ``[subject_valid_from, subject_valid_until]``.

    The boundaries are inclusive on both ends, matching the seam's own comparison
    (``now > valid_until`` / ``now < valid_from``) so the adapter and Risk Authority
    agree on exactly which instants are admissible.
    """

    if now > projection.valid_until:
        raise RecommendationValidityError(
            f"the recommendation expired at {projection.valid_until.isoformat()} "
            f"(trusted now={now.isoformat()}); it never reaches risk evaluation"
        )
    if now < projection.valid_from:
        raise RecommendationNotYetValidError(
            f"the recommendation is not yet valid until "
            f"{projection.valid_from.isoformat()} (trusted now={now.isoformat()})"
        )


def _identity_field(authenticated: Any, name: str) -> Optional[str]:
    """Best-effort identity for an audit record, on a path that has already failed.

    Only ever called after a gate has rejected the input, so it must not itself raise:
    a crash here would replace a typed rejection with an untyped exception, losing the
    fail-closed outcome the caller is entitled to. Anything it cannot read becomes
    ``None`` rather than a guess.
    """

    subject = getattr(getattr(authenticated, "recommendation", None), "subject", None)
    value = getattr(subject, name, None)
    return value if isinstance(value, str) else None


def _safe_tenant(authenticated: Any) -> Optional[str]:
    return _identity_field(authenticated, "tenant_id")


def _safe_subject(authenticated: Any) -> Optional[str]:
    return _identity_field(authenticated, "workload_id")
