"""Independent Phase 4 reconciliation, run before any candidate exists.

This module answers one question: *do this projection and this decision describe the same
thing?* It answers it by re-deriving, not by trusting — every digest is recomputed from
the artifact it claims to cover, using Risk Authority's public canonicalization.

**The validated-pair discipline.** Reconciliation reads each source value exactly once and
returns the values it read, inside :class:`ReconciledPhase4Facts`. Callers construct the
candidate from *those returned values* and never re-read the source objects afterwards.
This is not stylistic. A projection or decision can be a subclass whose ``tenant_id`` is a
property returning ``"tenant-a"`` on the first read and ``"tenant-b"`` on the second; a
check-then-use pattern would validate the first and bind the second. Reading once and
returning the read value closes that window structurally — there is no second read to
divert. The regression test ``test_no_post_validation_source_reread`` fails if this
discipline is ever reintroduced as a re-read.

**No partial construction.** Nothing is built until every check below has passed. A failed
reconciliation leaves no candidate, no cached fragment and no observable side effect.

**No trusted clock.** ``expires_at`` and the validity window are checked for *presence and
canonical form*, never against "now". Phase 5A holds no clock; see :mod:`.candidate`. Where a
validity fact is carried twice — once bare and once inside a digest-bound snapshot — the two
copies are reconciled against each other (R-12b). That is self-consistency, not freshness: it
still takes no view on whether the instant has passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Mapping, Optional

from risk_authority.integrations import (
    SeamContractError,
    SubjectRiskDecision,
    SubjectRiskDisposition,
    validate_subject_binding,
)
from ugence_cloud_scaling_risk_integration import CapacityRiskSubjectProjection

from .canonical import (
    digest_of_snapshot,
    require_canonical_digest,
    require_canonical_identifier,
    to_canonical_obj,
)
from .errors import AuthorizationCandidateRejectionReason as _Reason
from .errors import ExactTypeError, ReconciliationError
from .identifiers import (
    CANONICAL_ACTION_TYPES,
    DOMAIN_CLOUD_SCALING,
    PURPOSE_CAPACITY_ACTION,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
)

__all__ = ["ALLOW_FAMILY_DISPOSITIONS", "ReconciledPhase4Facts", "reconcile_phase4"]

#: The ALLOW family. A denial or an escalation grants nothing and is not a candidate
#: input; ``NOT_EVALUATED`` is not a decision at all.
ALLOW_FAMILY_DISPOSITIONS: Final[frozenset[SubjectRiskDisposition]] = frozenset(
    {
        SubjectRiskDisposition.RISK_PASSED,
        SubjectRiskDisposition.RISK_PASSED_WITH_CONDITIONS,
    }
)


@dataclass(frozen=True)
class ReconciledPhase4Facts:
    """Every Phase 4 value the candidate needs, each read exactly once and validated.

    The candidate builder consumes **only** this record. It is deliberately a plain,
    exact-typed value object holding primitives and canonical strings: there is no live
    reference back to the projection or the decision that a second read could divert.
    """

    tenant_id: str
    subject_id: str
    subject_type: str
    recommendation_digest: str
    context_digest: str
    subject_digest: str
    request_digest: str
    idempotency_key: str
    evidence_references: tuple[str, ...]
    evidence_snapshot_digest: str
    purpose: str
    domain: str
    action_type: str
    magnitude_before: int
    magnitude_after: int
    # --- projected placement facts, read once here so no consumer re-reads the source ---
    environment: Optional[str]
    region: Optional[str]
    zone: Optional[str]
    compute_group: Optional[str]
    resource_class: Optional[str]
    decision_id: str
    decision_digest: str
    decision_snapshot_digest: str
    disposition: str
    risk_outcome: str
    # --- carried Phase 4 validity facts; NOT evaluated against any clock here ----------
    subject_valid_from: datetime
    subject_valid_until: datetime
    subject_asserted_at: datetime
    decision_evaluated_at: datetime
    decision_expires_at: datetime

    @property
    def requested_delta(self) -> int:
        return abs(self.magnitude_after - self.magnitude_before)


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReconciliationError(
            f"{name} must be an int >= 0 (got {value!r})",
            _Reason.PROJECTION_RECONCILIATION_FAILED,
        )
    return value


def _require_datetime(name: str, value: Any, reason: _Reason) -> datetime:
    if not isinstance(value, datetime):
        raise ReconciliationError(f"{name} must be a datetime (got {value!r})", reason)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReconciliationError(f"{name} must be timezone-aware", reason)
    return value


def reconcile_phase4(
    projection: CapacityRiskSubjectProjection,
    decision: SubjectRiskDecision,
) -> ReconciledPhase4Facts:
    """Reconcile a Phase 4C projection against its Risk Authority decision.

    :raises ExactTypeError: either argument is not the exact required type.
    :raises ReconciliationError: any binding, digest, identifier or disposition check fails.
    """

    # --- exact-type admission ---------------------------------------------------------
    # ``type(...) is not`` rather than ``isinstance``: a subclass can override any
    # attribute with a property, and admitting one would make every check below advisory.
    if type(projection) is not CapacityRiskSubjectProjection:
        raise ExactTypeError(
            "reconcile_phase4 requires an exact CapacityRiskSubjectProjection "
            f"(got {type(projection).__name__})",
            _Reason.UNSUPPORTED_EXACT_TYPE,
        )
    if type(decision) is not SubjectRiskDecision:
        raise ExactTypeError(
            f"reconcile_phase4 requires an exact SubjectRiskDecision "
            f"(got {type(decision).__name__})",
            _Reason.UNSUPPORTED_EXACT_TYPE,
        )

    # --- single read of every source value --------------------------------------------
    # From here on, only these locals are used. Nothing below re-reads ``projection`` or
    # ``decision``; see this module's docstring for why that is load-bearing.
    p_tenant = projection.tenant_id
    p_subject_id = projection.subject_id
    p_recommendation_digest = projection.recommendation_digest
    p_context_digest = projection.context_digest
    p_subject_digest = projection.subject_digest
    p_request_digest = projection.request_digest
    p_idempotency_key = projection.idempotency_key
    p_evidence_references = projection.evidence_references
    p_request = projection.request
    p_context = projection.context
    p_environment = p_context.environment
    p_region = p_context.region
    p_zone = p_context.zone
    p_compute_group = p_context.compute_group
    p_resource_class = p_context.resource_class
    p_magnitude_before = p_context.magnitude_before
    p_magnitude_after = p_context.magnitude_after
    p_action_type = p_context.action_type
    p_valid_from = projection.valid_from
    p_valid_until = projection.valid_until
    p_asserted_at = projection.asserted_at

    d_tenant = decision.tenant_id
    d_subject_digest = decision.subject_digest
    d_request_digest = decision.request_digest
    d_disposition = decision.disposition
    d_risk_outcome = decision.risk_outcome
    d_decision_snapshot = decision.decision_snapshot
    d_decision_digest = decision.decision_digest
    d_idempotency_key = decision.idempotency_key
    d_evaluated_at = decision.evaluated_at
    d_expires_at = decision.expires_at

    # --- projection self-consistency, re-derived independently -------------------------
    try:
        validation = validate_subject_binding(p_request)
    except SeamContractError as exc:
        raise ReconciliationError(
            f"the projected request does not reconcile: {exc}",
            _Reason.PROJECTION_RECONCILIATION_FAILED,
        ) from exc

    if validation.context_digest != p_context_digest:
        raise ReconciliationError(
            "revalidation produced a different context_digest",
            _Reason.CONTEXT_DIGEST_MISMATCH,
        )
    if validation.subject_digest != p_subject_digest:
        raise ReconciliationError(
            "revalidation produced a different subject_digest",
            _Reason.SUBJECT_DIGEST_MISMATCH,
        )
    if validation.recommendation_digest != p_recommendation_digest:
        raise ReconciliationError(
            "revalidation produced a different recommendation_digest",
            _Reason.RECOMMENDATION_MISMATCH,
        )
    if p_request.digest() != p_request_digest:
        raise ReconciliationError(
            "request_digest does not match the carried request",
            _Reason.REQUEST_DIGEST_MISMATCH,
        )
    if p_context.digest() != p_context_digest:
        raise ReconciliationError(
            "context_digest does not match the carried context",
            _Reason.CONTEXT_DIGEST_MISMATCH,
        )

    # --- projection ↔ decision binding -------------------------------------------------
    if p_tenant != d_tenant:
        raise ReconciliationError(
            f"tenant mismatch: projection {p_tenant!r} vs decision {d_tenant!r}",
            _Reason.TENANT_MISMATCH,
        )
    if p_request_digest != d_request_digest:
        raise ReconciliationError(
            "the decision was made against a different request_digest",
            _Reason.REQUEST_DIGEST_MISMATCH,
        )
    if p_subject_digest != d_subject_digest:
        raise ReconciliationError(
            "the decision was made against a different subject_digest",
            _Reason.SUBJECT_MISMATCH,
        )

    # --- D-4 ratified identifiers ------------------------------------------------------
    if p_request.subject_type != SUBJECT_TYPE_CAPACITY_SUBJECT:
        raise ReconciliationError(
            f"subject_type {p_request.subject_type!r} is not the D-4 ratified "
            f"{SUBJECT_TYPE_CAPACITY_SUBJECT!r}",
            _Reason.D4_IDENTIFIER_MISMATCH,
        )
    if p_request.requested_purpose != PURPOSE_CAPACITY_ACTION:
        raise ReconciliationError(
            f"requested_purpose {p_request.requested_purpose!r} is not the D-4 ratified "
            f"{PURPOSE_CAPACITY_ACTION!r}",
            _Reason.D4_IDENTIFIER_MISMATCH,
        )
    if p_request.requested_domain != DOMAIN_CLOUD_SCALING:
        raise ReconciliationError(
            f"requested_domain {p_request.requested_domain!r} is not the D-4 ratified "
            f"{DOMAIN_CLOUD_SCALING!r}",
            _Reason.D4_IDENTIFIER_MISMATCH,
        )

    action_type = p_action_type
    if action_type not in CANONICAL_ACTION_TYPES:
        raise ReconciliationError(
            f"action_type {action_type!r} is not a D-4 ratified canonical action type",
            _Reason.ACTION_SUBSTITUTION,
        )

    # --- disposition: ALLOW family only ------------------------------------------------
    if not isinstance(d_disposition, SubjectRiskDisposition):
        raise ReconciliationError(
            "disposition must be a SubjectRiskDisposition", _Reason.UNSUPPORTED_EXACT_TYPE
        )
    if d_disposition not in ALLOW_FAMILY_DISPOSITIONS:
        raise ReconciliationError(
            f"disposition {d_disposition.value} is not in the ALLOW family; a denial, an "
            "escalation and a non-evaluation are not candidate inputs",
            _Reason.DECISION_NOT_ALLOW_FAMILY,
        )
    if d_risk_outcome is None:
        raise ReconciliationError(
            "an ALLOW-family disposition must carry a risk_outcome",
            _Reason.MISSING_BINDING_DECISION,
        )

    # --- the binding decision: present, canonical, and re-derived ----------------------
    if d_decision_snapshot is None:
        raise ReconciliationError(
            "an ALLOW-family decision must carry the binding decision_snapshot",
            _Reason.MISSING_DECISION_SNAPSHOT,
        )
    if not isinstance(d_decision_snapshot, Mapping):
        raise ReconciliationError(
            "decision_snapshot must be a canonical mapping",
            _Reason.MISSING_DECISION_SNAPSHOT,
        )
    if d_decision_digest is None:
        raise ReconciliationError(
            "an ALLOW-family decision must carry a decision_digest",
            _Reason.MISSING_BINDING_DECISION,
        )
    # Independent recomputation over the public canonicalization primitives — never the
    # private ``SubjectRiskDecision._bind``, and never an unchecked snapshot.
    recomputed = digest_of_snapshot(d_decision_snapshot)
    require_canonical_digest("decision_digest", d_decision_digest)
    if recomputed != d_decision_digest:
        raise ReconciliationError(
            "decision_digest does not equal the recomputed digest of decision_snapshot",
            _Reason.DECISION_DIGEST_MISMATCH,
        )

    decision_id = d_decision_snapshot.get("decision_id")
    if decision_id is None:
        raise ReconciliationError(
            "decision_snapshot carries no decision_id", _Reason.MISSING_BINDING_DECISION
        )
    require_canonical_identifier("decision_snapshot.decision_id", decision_id)

    snapshot_tenant = d_decision_snapshot.get("tenant_id")
    if snapshot_tenant != p_tenant:
        raise ReconciliationError(
            "the decision snapshot names a different tenant", _Reason.TENANT_MISMATCH
        )
    snapshot_domain = d_decision_snapshot.get("domain")
    if snapshot_domain != DOMAIN_CLOUD_SCALING:
        raise ReconciliationError(
            f"the decision snapshot names domain {snapshot_domain!r}, not the D-4 "
            f"ratified {DOMAIN_CLOUD_SCALING!r}",
            _Reason.D4_IDENTIFIER_MISMATCH,
        )

    # --- D-6 idempotency key: present on both, and equal -------------------------------
    if not p_idempotency_key:
        raise ReconciliationError(
            "the projection carries no D-6 idempotency_key",
            _Reason.IDEMPOTENCY_KEY_MISMATCH,
        )
    if not d_idempotency_key:
        raise ReconciliationError(
            "the decision carries no D-6 idempotency_key", _Reason.IDEMPOTENCY_KEY_MISMATCH
        )
    if p_idempotency_key != d_idempotency_key:
        raise ReconciliationError(
            "the decision's idempotency_key differs from the projection's",
            _Reason.IDEMPOTENCY_KEY_MISMATCH,
        )

    # --- evidence references and the evidence-snapshot binding -------------------------
    if not isinstance(p_evidence_references, tuple) or not p_evidence_references:
        raise ReconciliationError(
            "the projection must carry at least one evidence reference",
            _Reason.INVALID_EVIDENCE_BINDING,
        )
    for reference in p_evidence_references:
        require_canonical_digest("evidence_reference", reference)
    if tuple(p_request.evidence_references) != tuple(p_evidence_references):
        raise ReconciliationError(
            "the request's evidence_references differ from the projection's",
            _Reason.INVALID_EVIDENCE_BINDING,
        )
    evidence_snapshot_digest = d_decision_snapshot.get("evidence_snapshot_digest")
    if not evidence_snapshot_digest:
        raise ReconciliationError(
            "the decision snapshot carries no evidence_snapshot_digest",
            _Reason.INVALID_EVIDENCE_BINDING,
        )
    require_canonical_digest("evidence_snapshot_digest", evidence_snapshot_digest)

    # --- validity facts: presence and canonical form only, never "is it valid now" -----
    subject_valid_from = _require_datetime(
        "valid_from", p_valid_from, _Reason.PROJECTION_RECONCILIATION_FAILED
    )
    subject_valid_until = _require_datetime(
        "valid_until", p_valid_until, _Reason.PROJECTION_RECONCILIATION_FAILED
    )
    subject_asserted_at = _require_datetime(
        "asserted_at", p_asserted_at, _Reason.PROJECTION_RECONCILIATION_FAILED
    )
    decision_evaluated_at = _require_datetime(
        "evaluated_at", d_evaluated_at, _Reason.PROJECTION_RECONCILIATION_FAILED
    )
    if d_expires_at is None:
        raise ReconciliationError(
            "the decision must carry an expires_at fact", _Reason.MISSING_EXPIRY_FACT
        )
    decision_expires_at = _require_datetime(
        "expires_at", d_expires_at, _Reason.MISSING_EXPIRY_FACT
    )
    # R-12b. ``expires_at`` is carried twice: once as an outer field of the decision, and
    # once inside ``decision_snapshot``, which the digest check above re-derived. Only the
    # snapshot copy is covered by a digest, so a public ``dataclasses.replace`` on the exact
    # frozen type moves the outer field alone — every check above still passes, the snapshot
    # and digest are untouched, and the candidate carries the moved instant as
    # ``decision_expires_at_fact``. Phase 5B's gate 13 decides CANDIDATE_DECISION_EXPIRED
    # from that field and from nothing else, so an expired decision is made to verify by
    # editing the one copy nobody hashed.
    #
    # The two copies are reconciled by canonicalizing the outer value with the same public
    # primitive the snapshot was rendered with, so the comparison is byte-for-byte in the
    # snapshot's own spelling rather than a second rendering invented here. This is a
    # *coherence* check, not a clock: it says the decision agrees with itself about when it
    # expires, and says nothing about whether that instant has passed.
    snapshot_expires_at = d_decision_snapshot.get("expires_at")
    if to_canonical_obj(decision_expires_at) != snapshot_expires_at:
        raise ReconciliationError(
            "the decision's outer expires_at disagrees with the digest-bound copy in "
            f"decision_snapshot: the decision states "
            f"{to_canonical_obj(decision_expires_at)!r} and the snapshot the digest covers "
            f"states {snapshot_expires_at!r}",
            _Reason.DECISION_EXPIRY_MISMATCH,
        )

    return ReconciledPhase4Facts(
        tenant_id=require_canonical_identifier("tenant_id", p_tenant),
        subject_id=require_canonical_identifier("subject_id", p_subject_id),
        subject_type=SUBJECT_TYPE_CAPACITY_SUBJECT,
        recommendation_digest=require_canonical_digest(
            "recommendation_digest", p_recommendation_digest
        ),
        context_digest=require_canonical_digest("context_digest", p_context_digest),
        subject_digest=require_canonical_digest("subject_digest", p_subject_digest),
        request_digest=require_canonical_digest("request_digest", p_request_digest),
        idempotency_key=require_canonical_digest("idempotency_key", p_idempotency_key),
        evidence_references=tuple(p_evidence_references),
        evidence_snapshot_digest=evidence_snapshot_digest,
        purpose=PURPOSE_CAPACITY_ACTION,
        domain=DOMAIN_CLOUD_SCALING,
        action_type=action_type,
        magnitude_before=_require_int("magnitude_before", p_magnitude_before),
        magnitude_after=_require_int("magnitude_after", p_magnitude_after),
        environment=p_environment,
        region=p_region,
        zone=p_zone,
        compute_group=p_compute_group,
        resource_class=p_resource_class,
        decision_id=decision_id,
        decision_digest=d_decision_digest,
        decision_snapshot_digest=recomputed,
        disposition=d_disposition.value,
        risk_outcome=d_risk_outcome.value,
        subject_valid_from=subject_valid_from,
        subject_valid_until=subject_valid_until,
        subject_asserted_at=subject_asserted_at,
        decision_evaluated_at=decision_evaluated_at,
        decision_expires_at=decision_expires_at,
    )
