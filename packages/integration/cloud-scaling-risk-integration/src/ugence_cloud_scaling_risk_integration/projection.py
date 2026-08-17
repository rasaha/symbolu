"""The deterministic recommendation → v2 request projection (ADR §5).

This module is a **pure function of an authenticated recommendation**. It reads no clock,
performs no I/O, touches no ambient state, selects no policy, admits no evidence and
calls nothing — it builds three canonical objects and their three schema-tagged digests,
then verifies locally that the chain reconciles.

The curated-object rule (ADR §5.4 F3) is structural here: :class:`SubjectContext` is
populated **field by field** from a curated set of approved neutral facts. The
controller's ``to_canonical_dict()`` is never handed to the Risk Authority canonicalizer,
so the controller's float-valued analytics (confidence, forecast coverage, cost ratios,
``timing_seconds``) cannot reach the Risk Authority digest chain — there is no code path
that could carry them, not merely a filter that declines to.

The binding chain, in order:

1. ``recommendation_digest`` — recomputed and reconciled upstream in :mod:`.authenticity`;
2. ``SubjectContext``       — curated neutral facts only;
3. ``context_digest``       — ``digest(SubjectContext)``;
4. ``SubjectBinding``       — anchors **derived** from the authoritative outer values;
5. ``subject_digest``       — ``digest(SubjectBinding)``;
6. ``SubjectRiskEvaluationRequestV2``;
7. ``request_digest``;
8. ``idempotency_key``      — D-6: tenant + subject + recommendation digest + purpose +
   request schema version. **Never a timestamp**, so it is stable across retries of the
   same recommendation and cannot be used as a nonce.

The outer request is authoritative for ``tenant_id``, ``subject_id``,
``recommendation_digest`` and ``evidence_references``. None of the four is duplicated
inside ``SubjectContext``: the closed v2 context contract has no field for any of them,
so there is structurally no second source to disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Final, Optional

from risk_authority.crypto.hashing import digest as _ra_digest
from risk_authority.domain import Scope
from risk_authority.integrations import (
    EVALUATION_REQUEST_SCHEMA_VERSION_V2,
    SeamContractError,
    SubjectBinding,
    SubjectContext,
    SubjectRiskEvaluationRequestV2,
    validate_subject_binding,
)
from ugence_cloud_scaling_controller.canonical.identity import CapacitySubject
from ugence_cloud_scaling_controller.planning.candidates import ResourceChange

from .authenticity import (
    AuthenticatedRecommendation,
    _validate_authenticated_recommendation,
)
from .errors import ProjectionError
from .identifiers import (
    DOMAIN_CLOUD_SCALING,
    PURPOSE_CAPACITY_ACTION,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
    canonical_action_type,
)

__all__ = [
    "PROJECTION_SCHEMA_VERSION",
    "CapacityRiskSubjectProjection",
    "project_recommendation",
    "build_idempotency_key",
]

#: The adapter-owned projection record's schema tag (ADR §16).
PROJECTION_SCHEMA_VERSION: Final[str] = "cloud-scaling-risk-subject-projection-1"

_AUTHORITY_FLAGS = (
    "policy_resolved",
    "risk_evaluated",
    "authority_granted",
    "envelope_issued",
    "actiongate_invoked",
    "credential_issued",
    "actuation_performed",
    "effect_verified",
    "executable",
)


@dataclass(frozen=True)
class CapacityRiskSubjectProjection:
    """The complete, locally reconciled Phase 4C binding chain for one recommendation.

    An **integrity finding, not a grant**. Holding one means a canonical v2 request was
    constructed from a recommendation whose digest reconciled with an independent
    expectation, and that the chain re-derives locally. It grants nothing: every
    authority flag is fixed ``False`` and enforced at construction, and Risk Authority
    still performs its own Phase 4B validation over the request.
    """

    recommendation_digest: str
    tenant_id: str
    subject_id: str
    context: SubjectContext
    context_digest: str
    binding: SubjectBinding
    subject_digest: str
    request: SubjectRiskEvaluationRequestV2
    request_digest: str
    idempotency_key: str
    evidence_references: tuple[str, ...]
    valid_from: datetime
    valid_until: datetime
    asserted_at: datetime
    schema_version: str = PROJECTION_SCHEMA_VERSION
    # Fixed non-authority invariants — projecting a subject is not an evaluation.
    policy_resolved: bool = False
    risk_evaluated: bool = False
    authority_granted: bool = False
    envelope_issued: bool = False
    actiongate_invoked: bool = False
    credential_issued: bool = False
    actuation_performed: bool = False
    effect_verified: bool = False
    executable: bool = False

    def __post_init__(self) -> None:
        for flag in _AUTHORITY_FLAGS:
            if getattr(self, flag) is not False:
                raise ProjectionError(
                    f"{flag} must be False — a projection grants no authority"
                )
        if self.schema_version != PROJECTION_SCHEMA_VERSION:
            raise ProjectionError(
                f"schema_version must be {PROJECTION_SCHEMA_VERSION!r}"
            )
        if not isinstance(self.request, SubjectRiskEvaluationRequestV2):
            raise ProjectionError("request must be a SubjectRiskEvaluationRequestV2")
        # The trusted v2 path must never carry a caller-supplied evaluation time; the
        # projection has no parameter for one, and this asserts the absence structurally.
        if self.request.evaluation_time is not None:
            raise ProjectionError(
                "evaluation_time must be None on the trusted v2 path — trusted "
                "evaluation time comes only from Risk Authority's injected clock"
            )

        # Re-derive the whole chain rather than trusting the values handed in. This is
        # the same reconciliation Risk Authority performs in Phase 4B, run locally so a
        # non-reconciling request is never submitted in the first place. RA still runs
        # its own; this does not replace it.
        if self.context.digest() != self.context_digest:
            raise ProjectionError("context_digest does not match the carried context")
        if self.binding.digest() != self.subject_digest:
            raise ProjectionError("subject_digest does not match the carried binding")
        if self.request.digest() != self.request_digest:
            raise ProjectionError("request_digest does not match the carried request")
        try:
            validation = validate_subject_binding(self.request)
        except SeamContractError as exc:
            raise ProjectionError(
                f"the projected request does not reconcile locally: {exc}"
            ) from exc
        if validation.context_digest != self.context_digest:
            raise ProjectionError("local revalidation produced a different context_digest")
        if validation.subject_digest != self.subject_digest:
            raise ProjectionError("local revalidation produced a different subject_digest")
        if validation.recommendation_digest != self.recommendation_digest:
            raise ProjectionError(
                "local revalidation produced a different recommendation_digest"
            )


def build_idempotency_key(
    *, tenant_id: str, subject_id: str, recommendation_digest: str
) -> str:
    """The D-6 idempotency key: canonical identity + purpose + request schema version.

    Deliberately **timestamp-free**: two evaluations of the same recommendation for the
    same tenant and subject produce the same key, which is what makes it an idempotency
    key at all. A request timestamp would make it a nonce that changes on every call —
    ADR §5.1 row 14a forbids exactly that.
    """

    return _ra_digest(
        {
            "tenant_id": tenant_id,
            "subject_id": subject_id,
            "recommendation_digest": recommendation_digest,
            "purpose": PURPOSE_CAPACITY_ACTION,
            "schema_version": EVALUATION_REQUEST_SCHEMA_VERSION_V2,
        }
    )


def _require_utc(name: str, value: Any) -> datetime:
    """Normalize an aware datetime to UTC; reject a naive one.

    An aware non-UTC offset is converted (lossless — the same instant, and exactly what
    the Risk Authority canonicalizer would render). A **naive** datetime is rejected
    rather than assumed-UTC: assuming would silently pick an instant on the caller's
    behalf and then freeze that guess into the digest chain.
    """

    if not isinstance(value, datetime):
        raise ProjectionError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProjectionError(
            f"{name} must be timezone-aware; a naive datetime is rejected rather than "
            "assumed UTC"
        )
    return value.astimezone(timezone.utc)


def _require_identity(name: str, value: Any) -> str:
    if not isinstance(value, str) or value == "":
        raise ProjectionError(f"{name} is required and must be a non-empty string")
    return value


def _primary_change(recommendation: Any) -> ResourceChange:
    """The selected plan's unique ``primary`` resource change.

    Every ``CandidateActionPlan`` requires exactly one ``primary`` change, including a
    ``COORDINATED`` plan. Dependency changes are deliberately **not** projected as
    neutral magnitudes: ``magnitude_before``/``magnitude_after`` describe one quantity,
    and flattening several resources into them would misreport the subject. They remain
    bound transitively through ``recommendation_digest``, which covers the whole plan.
    """

    try:
        return recommendation.selected_plan.primary_change
    except Exception as exc:  # noqa: BLE001 - a plan without a primary is unprojectable
        raise ProjectionError(
            f"the selected plan has no projectable primary resource change: {exc}"
        ) from exc


def _evidence_references(recommendation: Any) -> tuple[str, ...]:
    """Deterministic, validated, deduplicated, canonically ordered evidence references.

    Only opaque digest strings are carried — never an evidence body, a control result or
    a PASS/FAIL claim. The forecast evidence reference is mandatory (ADR §6); the
    topology digest is legitimately absent when the recommendation carries no topology.
    Ordering is lexicographic so a reordered or duplicated input cannot produce a
    different ``request_digest`` for the same evidence set.
    """

    candidates = [
        ("forecast_evidence_digest", recommendation.forecast_evidence_digest()),
        ("cost_evidence_digest", recommendation.cost_evidence_digest()),
        ("topology_digest", recommendation.topology_digest()),
        ("canonical_state_digest", recommendation.canonical_state_digest()),
    ]
    if candidates[0][1] is None:
        raise ProjectionError("forecast_evidence_digest is required (ADR §6)")

    seen: set[str] = set()
    for name, value in candidates:
        if value is None:
            if name == "topology_digest":
                continue  # a recommendation without topology has no topology digest
            raise ProjectionError(f"{name} is required and must not be None")
        if not isinstance(value, str) or not value.startswith("sha256:"):
            raise ProjectionError(f"{name} must be a canonical 'sha256:' digest string")
        seen.add(value)
    return tuple(sorted(seen))


def project_recommendation(
    authenticated: AuthenticatedRecommendation,
) -> CapacityRiskSubjectProjection:
    """Project an authenticated recommendation into the canonical v2 request.

    Pure and deterministic: the same authenticated recommendation always yields the same
    three digests, the same idempotency key and the same request bytes.

    :raises ProjectionError: a required subject fact is missing, a controller value is
        not canonically representable at the Risk Authority boundary, or the chain does
        not reconcile locally.
    """

    # --- consumption boundary: re-establish the token's own invariant ------------------
    # Exact type, not ``isinstance``, and re-validated rather than trusted from
    # construction. Holding an ``AuthenticatedRecommendation`` is what entitles a caller
    # to project, so a token that was never validly constructed must not be projectable:
    # ``object.__new__`` skips ``__post_init__`` entirely, ``object.__setattr__`` rewrites
    # a frozen field after the fact, and a token subclass can make ``recommendation`` a
    # property returning a different object on each read. All of this happens **before**
    # any context, binding or request is constructed — nothing downstream observes a token
    # that failed here.
    if type(authenticated) is not AuthenticatedRecommendation:
        raise ProjectionError(
            "project_recommendation requires an AuthenticatedRecommendation — a "
            "recommendation may not be projected before its digest has been reconciled "
            "against an independent expectation "
            f"(got {type(authenticated).__name__})"
        )
    # The validated values are used from here on rather than re-read from the token, so
    # there is no window between the check and the use.
    recommendation, recommendation_digest = _validate_authenticated_recommendation(
        authenticated
    )

    subject: CapacitySubject = recommendation.subject

    # --- authoritative outer identity (never duplicated inside SubjectContext) --------
    tenant_id = _require_identity("subject.tenant_id (outer tenant_id)", subject.tenant_id)
    subject_id = _require_identity("subject.workload_id (outer subject_id)", subject.workload_id)

    # --- curated neutral subject facts ------------------------------------------------
    change = _primary_change(recommendation)
    asserted_at = _require_utc("recommendation_time", recommendation.recommendation_time)
    # The controller's own validity arithmetic, reused verbatim so the adapter's window
    # is the same instant the controller bounded against the forecast horizon. The float
    # `validity_seconds` never enters the digest chain — only the resulting canonical UTC
    # timestamp does.
    valid_until = asserted_at + timedelta(seconds=float(recommendation.validity_seconds))

    try:
        context = SubjectContext(
            # Neutral facts only. `None` stays `None` — a missing optional is a distinct
            # sentinel and must never be normalized into an empty named value.
            environment=subject.environment,
            region=subject.region,
            zone=subject.zone,
            compute_group=subject.cluster,
            resource_class=subject.resource_id,
            action_type=canonical_action_type(recommendation.selected_plan.action_kind),
            magnitude_before=change.current_capacity,
            magnitude_after=change.proposed_capacity,
            subject_asserted_at=asserted_at,
            subject_valid_from=asserted_at,
            subject_valid_until=valid_until,
        )
    except SeamContractError as exc:
        # Non-NFC strings, non-integer magnitudes and non-UTC timestamps are refused by
        # the closed RA contract; surface them as the adapter's typed failure.
        raise ProjectionError(
            f"the curated neutral subject context is not canonically representable: {exc}"
        ) from exc

    context_digest = context.digest()

    # --- binding anchors, DERIVED from the authoritative outer values ------------------
    try:
        binding = SubjectBinding(
            tenant_id=tenant_id,
            subject_id=subject_id,
            subject_type=SUBJECT_TYPE_CAPACITY_SUBJECT,
            recommendation_digest=recommendation_digest,
            context_digest=context_digest,
        )
    except SeamContractError as exc:
        raise ProjectionError(f"the subject binding could not be built: {exc}") from exc
    subject_digest = binding.digest()

    evidence_references = _evidence_references(recommendation)
    correlation_id = recommendation.forecast_evidence.forecast.correlation_id
    if correlation_id is not None and not isinstance(correlation_id, str):
        raise ProjectionError("correlation_id must be a string or None")

    try:
        request = SubjectRiskEvaluationRequestV2(
            subject_type=SUBJECT_TYPE_CAPACITY_SUBJECT,
            subject_id=subject_id,
            subject_digest=subject_digest,
            tenant_id=tenant_id,
            requested_purpose=PURPOSE_CAPACITY_ACTION,
            requested_domain=DOMAIN_CLOUD_SCALING,
            # Minimal scope — never overloaded with topology or capacity dimensions.
            requested_scope=Scope(purposes=(PURPOSE_CAPACITY_ACTION,)),
            # Risk Authority classifies; the adapter never asserts a risk class.
            requested_risk_class=None,
            evidence_references=evidence_references,
            correlation_id=correlation_id,
            idempotency_key=build_idempotency_key(
                tenant_id=tenant_id,
                subject_id=subject_id,
                recommendation_digest=recommendation_digest,
            ),
            # Never caller-populated: the seam uses its own trusted clock (ADR §10).
            evaluation_time=None,
            subject_context=context,
            recommendation_digest=recommendation_digest,
        )
    except SeamContractError as exc:
        raise ProjectionError(f"the v2 request could not be built: {exc}") from exc

    return CapacityRiskSubjectProjection(
        recommendation_digest=recommendation_digest,
        tenant_id=tenant_id,
        subject_id=subject_id,
        context=context,
        context_digest=context_digest,
        binding=binding,
        subject_digest=subject_digest,
        request=request,
        request_digest=request.digest(),
        idempotency_key=request.idempotency_key or "",
        evidence_references=evidence_references,
        valid_from=asserted_at,
        valid_until=valid_until,
        asserted_at=asserted_at,
    )
