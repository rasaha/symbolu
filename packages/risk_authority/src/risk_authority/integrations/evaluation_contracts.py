"""Neutral, domain-agnostic contracts for the stop-at-decision risk-evaluation seam.

These types let an *external domain integration* (e.g. a future Cloud Scaling Phase-4
adapter) request a risk evaluation of a canonical subject and receive the canonical
:class:`~risk_authority.domain.decision.RiskDecision` — **without** importing Risk
Authority internals, selecting policy, supplying trusted control results, supplying
signing keys or evaluator identity, issuing an authorization envelope, or invoking
ActionGate. The request expresses *what* is being evaluated; it can never decide *how*
it is evaluated.

Trust boundary (see ``RISK_AUTHORITY_EVALUATION_SEAM.md``): the request may carry only
canonical subject facts + correlation/idempotency context. Authoritative risk policy,
the control catalog, trusted control results, evaluator identity, signing keys, the
clock and revocation state are all supplied by the trusted application composition root
through :class:`~risk_authority.api.evaluation_seam.RiskEvaluationSeam`, never through
the request.

Non-executable invariant: a :class:`SubjectRiskDecision` terminates at the canonical
risk decision. A ``RISK_PASSED`` / ``RISK_PASSED_WITH_CONDITIONS`` disposition means only
that *risk evaluation passed*; it is **not** ActionGate authorization and carries no
executable capability (``authorization_performed = envelope_issued = actiongate_invoked =
actuation_performed = effect_verified = executable = False``).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from ..crypto.canonical import to_canonical_obj
from ..crypto.hashing import DIGEST_PREFIX
from ..crypto.hashing import digest as _digest
from ..domain.enums import RiskClass, RiskOutcome
from ..domain.errors import RiskAuthorityError
from ..domain.scope import Scope
from ..domain.workflow_ir import WorkflowIR

__all__ = [
    "EVALUATION_REQUEST_SCHEMA_VERSION",
    "EVALUATION_REQUEST_SCHEMA_VERSION_V2",
    "EVALUATION_RESULT_SCHEMA_VERSION",
    "SUBJECT_BINDING_SCHEMA_VERSION",
    "SUBJECT_CONTEXT_SCHEMA_VERSION",
    "SUPPORTED_REQUEST_SCHEMA_VERSIONS",
    "SubjectRiskDisposition",
    "SubjectRiskNonDecisionReason",
    "SubjectRiskEvaluationRequest",
    "SubjectRiskEvaluationRequestV2",
    "SubjectContext",
    "SubjectBinding",
    "SubjectBindingValidation",
    "SubjectBindingError",
    "validate_subject_binding",
    "SubjectRiskDecision",
    "PolicyResolverPort",
    "TrustedControlEvidenceResolverPort",
    "ReferencePolicyResolver",
    "ReferenceControlEvidenceResolver",
    "SeamContractError",
]

EVALUATION_REQUEST_SCHEMA_VERSION = "risk-subject-evaluation-request-1"
EVALUATION_RESULT_SCHEMA_VERSION = "risk-subject-decision-1"

# --- v2 subject-context contract layer (Cloud Scaling Phase 4A, ADR §5.2-§5.4) ---
# Each of the three objects below carries its own fixed schema tag *inside* its own
# canonical form. Separation between them is achieved by that embedded tag plus strict
# validation — NOT by the hash construction, which is the existing bare SHA-256 over
# canonical bytes (``crypto.hashing.digest``). See the module note on schema-tagged
# canonical hashing below.
SUBJECT_CONTEXT_SCHEMA_VERSION = "risk-subject-context-1"
SUBJECT_BINDING_SCHEMA_VERSION = "risk-subject-binding-1"
EVALUATION_REQUEST_SCHEMA_VERSION_V2 = "risk-subject-evaluation-request-2"

# The seam's accepted request set is DELIBERATELY unchanged in Phase 4A: this PR ships
# contracts and pure validation only, and nothing wires ``validate_subject_binding``
# into ``RiskEvaluationSeam``. Widening this set before that wiring exists would let a
# v2 request reach policy resolution without its binding ever being reconciled. A v2
# request presented to the seam today therefore fails closed as
# ``NOT_EVALUATED(UNSUPPORTED_SCHEMA_VERSION)``. Widening is a Phase 4B step.
SUPPORTED_REQUEST_SCHEMA_VERSIONS = frozenset({EVALUATION_REQUEST_SCHEMA_VERSION})

_TS_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"

# The established repository digest syntax: the ``crypto.hashing`` prefix + lowercase
# SHA-256 hex. Built from DIGEST_PREFIX so it stays tied to the existing primitive.
_DIGEST_RE = re.compile("^" + re.escape(DIGEST_PREFIX) + "[0-9a-f]{64}$")


class SeamContractError(RiskAuthorityError):
    """Raised when a seam request/result contract is malformed (fail closed)."""


class SubjectRiskDisposition(str, Enum):
    """The typed outcome of a stop-at-decision evaluation.

    The four decision dispositions mirror the canonical :class:`RiskOutcome`; a risk
    PASS is *not* an authorization. ``NOT_EVALUATED`` is the typed non-decision — no
    binding risk decision was produced (with a :class:`SubjectRiskNonDecisionReason`)."""

    RISK_PASSED = "RISK_PASSED"
    RISK_PASSED_WITH_CONDITIONS = "RISK_PASSED_WITH_CONDITIONS"
    RISK_DENIED = "RISK_DENIED"
    RISK_ESCALATED = "RISK_ESCALATED"
    NOT_EVALUATED = "NOT_EVALUATED"


_OUTCOME_TO_DISPOSITION = {
    RiskOutcome.ALLOW: SubjectRiskDisposition.RISK_PASSED,
    RiskOutcome.ALLOW_WITH_CONDITIONS: SubjectRiskDisposition.RISK_PASSED_WITH_CONDITIONS,
    RiskOutcome.DENY: SubjectRiskDisposition.RISK_DENIED,
    RiskOutcome.ESCALATE: SubjectRiskDisposition.RISK_ESCALATED,
}

_DECISION_DISPOSITIONS = frozenset(_OUTCOME_TO_DISPOSITION.values())


class SubjectRiskNonDecisionReason(str, Enum):
    """Typed reasons a subject evaluation produced no binding risk decision."""

    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    INVALID_SUBJECT = "invalid_subject"
    EXPIRED_SUBJECT = "expired_subject"
    NO_AUTHORITATIVE_POLICY = "no_authoritative_policy"
    AMBIGUOUS_POLICY = "ambiguous_policy"
    EXPIRED_POLICY = "expired_policy"
    MISSING_TRUSTED_EVIDENCE_PROVIDER = "missing_trusted_evidence_provider"
    EVALUATOR_UNAVAILABLE = "evaluator_unavailable"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"
    SCOPE_BINDING_FAILED = "scope_binding_failed"
    TENANT_SCOPE_MISMATCH = "tenant_scope_mismatch"


def disposition_for_outcome(outcome: RiskOutcome) -> SubjectRiskDisposition:
    return _OUTCOME_TO_DISPOSITION[outcome]


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SeamContractError("timestamp must be an ISO-8601 UTC string")
    return datetime.strptime(value, _TS_FMT).replace(tzinfo=timezone.utc)


def _fmt_ts(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return aware.strftime(_TS_FMT)


def _scope_to_dict(scope: Scope) -> dict[str, Any]:
    return to_canonical_obj(scope.normalized())


def _scope_from_dict(data: Mapping[str, Any]) -> Scope:
    if not isinstance(data, Mapping):
        raise SeamContractError("scope must be a mapping")
    return Scope(
        purposes=tuple(data.get("purposes", ())),
        tools_allow=tuple(data.get("tools_allow", ())),
        tools_deny=tuple(data.get("tools_deny", ())),
        data_allow=tuple(data.get("data_allow", ())),
        data_deny=tuple(data.get("data_deny", ())),
        destinations=tuple(data.get("destinations", ())),
        jurisdictions=tuple(data.get("jurisdictions", ())),
        models=tuple(data.get("models", ())),
        actors=tuple(data.get("actors", ())),
        max_autonomy_level=int(data.get("max_autonomy_level", 0)),
        max_transaction_minor_units=data.get("max_transaction_minor_units"),
    ).normalized()


@dataclass(frozen=True)
class SubjectRiskEvaluationRequest:
    """A domain-neutral request to risk-evaluate a canonical subject.

    Carries *only* subject facts + correlation/idempotency context. It has no field
    for a policy id, control results, keys, an evaluator identity, a precomputed
    recommendation/decision, or an envelope — those authorities are structurally
    impossible to supply here and are owned by the trusted composition root.
    """

    subject_type: str
    subject_id: str
    subject_digest: str
    tenant_id: str
    requested_purpose: str
    requested_domain: str
    requested_scope: Scope
    requested_risk_class: Optional[RiskClass] = None
    jurisdictions: tuple[str, ...] = ()
    requested_tools: tuple[str, ...] = ()
    requested_autonomy_level: int = 0
    requested_data_classes: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    evaluation_time: Optional[datetime] = None
    schema_version: str = EVALUATION_REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("subject_type", "subject_id", "subject_digest", "tenant_id",
                     "requested_purpose", "requested_domain", "schema_version"):
            v = getattr(self, name)
            if not isinstance(v, str) or v == "":
                raise SeamContractError(f"{name} must be a non-empty string")
        if not isinstance(self.requested_scope, Scope):
            raise SeamContractError("requested_scope must be a Scope")
        if self.requested_risk_class is not None and not isinstance(self.requested_risk_class, RiskClass):
            raise SeamContractError("requested_risk_class must be a RiskClass or None")
        if isinstance(self.requested_autonomy_level, bool) or not isinstance(self.requested_autonomy_level, int) \
                or self.requested_autonomy_level < 0:
            raise SeamContractError("requested_autonomy_level must be an int >= 0")
        for name in ("jurisdictions", "requested_tools", "requested_data_classes", "evidence_references"):
            seq = getattr(self, name)
            if not isinstance(seq, tuple) or any(not isinstance(x, str) or x == "" for x in seq):
                raise SeamContractError(f"{name} must be a tuple of non-empty strings")
        if self.evaluation_time is not None and not isinstance(self.evaluation_time, datetime):
            raise SeamContractError("evaluation_time must be a datetime or None")
        # Normalize the embedded scope so identity is stable.
        object.__setattr__(self, "requested_scope", self.requested_scope.normalized())

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "subject_digest": self.subject_digest,
            "tenant_id": self.tenant_id,
            "requested_purpose": self.requested_purpose,
            "requested_domain": self.requested_domain,
            "requested_scope": _scope_to_dict(self.requested_scope),
            "requested_risk_class": (self.requested_risk_class.value if self.requested_risk_class else None),
            "jurisdictions": list(self.jurisdictions),
            "requested_tools": list(self.requested_tools),
            "requested_autonomy_level": self.requested_autonomy_level,
            "requested_data_classes": list(self.requested_data_classes),
            "evidence_references": list(self.evidence_references),
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "evaluation_time": _fmt_ts(self.evaluation_time),
        }

    def digest(self) -> str:
        return _digest(self.to_canonical_dict())

    _ALLOWED_KEYS = frozenset({
        "schema_version", "subject_type", "subject_id", "subject_digest", "tenant_id",
        "requested_purpose", "requested_domain", "requested_scope", "requested_risk_class",
        "jurisdictions", "requested_tools", "requested_autonomy_level",
        "requested_data_classes", "evidence_references", "correlation_id",
        "idempotency_key", "evaluation_time",
    })

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SubjectRiskEvaluationRequest":
        if not isinstance(data, Mapping):
            raise SeamContractError("request data must be a mapping")
        # Strict parsing (audit): unknown fields are rejected (never silently dropped
        # before digest computation), and schema_version is mandatory.
        unknown = set(data) - cls._ALLOWED_KEYS
        if unknown:
            raise SeamContractError(f"unknown request field(s): {sorted(unknown)}")
        if "schema_version" not in data:
            raise SeamContractError("request requires an explicit schema_version")
        rc = data.get("requested_risk_class")
        return cls(
            schema_version=data["schema_version"],
            subject_type=data["subject_type"],
            subject_id=data["subject_id"],
            subject_digest=data["subject_digest"],
            tenant_id=data["tenant_id"],
            requested_purpose=data["requested_purpose"],
            requested_domain=data["requested_domain"],
            requested_scope=_scope_from_dict(data["requested_scope"]),
            requested_risk_class=(RiskClass(rc) if rc is not None else None),
            jurisdictions=tuple(data.get("jurisdictions", ())),
            requested_tools=tuple(data.get("requested_tools", ())),
            requested_autonomy_level=int(data.get("requested_autonomy_level", 0)),
            requested_data_classes=tuple(data.get("requested_data_classes", ())),
            evidence_references=tuple(data.get("evidence_references", ())),
            correlation_id=data.get("correlation_id"),
            idempotency_key=data.get("idempotency_key"),
            evaluation_time=_parse_ts(data.get("evaluation_time")),
        )


@dataclass(frozen=True)
class SubjectRiskDecision:
    """The stop-at-decision result: a canonical risk outcome, or a typed non-decision.

    It terminates at the canonical Risk Authority artifacts and never carries an
    envelope or an ActionGate result; every executable-capability flag is fixed
    ``False`` — enforced at construction. A risk PASS is *not* authorization.

    Faithful to the kernel: a binding :class:`RiskDecision` is minted only for the
    ALLOW-family (a case that reached AUTHORITY_REVIEW with satisfied controls). A
    DENY/ESCALATE grants nothing, so it carries the canonical :class:`RiskEvaluation`
    as its backing artifact and **no** binding decision. Every decided disposition
    therefore carries ``evaluation_snapshot``/``evaluation_digest``; only a pass also
    carries ``decision_snapshot``/``decision_digest``. Snapshots are canonical dicts
    bound by their digest, so a reconstructed result re-validates content identity
    without a divergent domain deserializer.
    """

    request_digest: str
    subject_digest: str
    tenant_id: str
    disposition: SubjectRiskDisposition
    evaluator_principal_id: str
    evaluated_at: datetime
    risk_outcome: Optional[RiskOutcome] = None
    evaluation_snapshot: Optional[Mapping[str, Any]] = None
    evaluation_digest: Optional[str] = None
    decision_snapshot: Optional[Mapping[str, Any]] = None
    decision_digest: Optional[str] = None
    workflow_ir_digest: str = ""
    expires_at: Optional[datetime] = None
    non_decision_reason: Optional[SubjectRiskNonDecisionReason] = None
    reason_codes: tuple[str, ...] = ()
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    schema_version: str = EVALUATION_RESULT_SCHEMA_VERSION
    # Fixed non-executable invariants — a risk PASS is not an authorization.
    authorization_performed: bool = False
    envelope_issued: bool = False
    actiongate_invoked: bool = False
    actuation_performed: bool = False
    effect_verified: bool = False
    executable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, SubjectRiskDisposition):
            raise SeamContractError("disposition must be a SubjectRiskDisposition")
        for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                     "actuation_performed", "effect_verified", "executable"):
            if getattr(self, flag) is not False:
                raise SeamContractError(f"{flag} must be False — this seam is non-executing")
        if not isinstance(self.evaluated_at, datetime):
            raise SeamContractError("evaluated_at must be a datetime")

        if self.disposition in _DECISION_DISPOSITIONS:
            if self.non_decision_reason is not None:
                raise SeamContractError("a decided disposition must not carry a non_decision_reason")
            if not isinstance(self.risk_outcome, RiskOutcome):
                raise SeamContractError("a decided disposition requires a RiskOutcome")
            if disposition_for_outcome(self.risk_outcome) is not self.disposition:
                raise SeamContractError("disposition must match risk_outcome")
            # The canonical evaluation artifact backs EVERY decided disposition.
            if self.evaluation_snapshot is None:
                raise SeamContractError("a decided disposition requires the evaluation_snapshot")
            self._bind("evaluation_snapshot", "evaluation_digest")
            # A binding decision exists only for the ALLOW-family; a denial grants
            # nothing and must not carry one.
            allow_family = self.risk_outcome in (RiskOutcome.ALLOW, RiskOutcome.ALLOW_WITH_CONDITIONS)
            if allow_family:
                if self.decision_snapshot is None:
                    raise SeamContractError("a risk PASS requires the binding decision_snapshot")
                self._bind("decision_snapshot", "decision_digest")
            else:
                # A DENY/ESCALATE grants nothing. A canonical denial decision MAY still
                # be recorded (the reference ruler mints one), but it is optional: the
                # production facade never reaches issue_decision for a denial.
                if self.decision_snapshot is not None:
                    self._bind("decision_snapshot", "decision_digest")
                elif self.decision_digest is not None:
                    raise SeamContractError("decision_digest present without decision_snapshot")
        else:  # NOT_EVALUATED
            if not isinstance(self.non_decision_reason, SubjectRiskNonDecisionReason):
                raise SeamContractError("NOT_EVALUATED requires a typed non_decision_reason")
            if any(v is not None for v in (self.risk_outcome, self.evaluation_snapshot,
                                           self.evaluation_digest, self.decision_snapshot,
                                           self.decision_digest)):
                raise SeamContractError("NOT_EVALUATED must not carry an outcome/evaluation/decision")

    def _bind(self, snap_field: str, digest_field: str) -> None:
        """Re-derive and validate ``digest_field`` == digest(``snap_field``)."""
        snapshot = getattr(self, snap_field)
        expected = _digest(to_canonical_obj(snapshot))
        current = getattr(self, digest_field)
        if current is None:
            object.__setattr__(self, digest_field, expected)
        elif current != expected:
            raise SeamContractError(f"{digest_field} must equal digest({snap_field})")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_digest": self.request_digest,
            "subject_digest": self.subject_digest,
            "tenant_id": self.tenant_id,
            "disposition": self.disposition.value,
            "evaluator_principal_id": self.evaluator_principal_id,
            "evaluated_at": _fmt_ts(self.evaluated_at),
            "risk_outcome": (self.risk_outcome.value if self.risk_outcome else None),
            "evaluation_snapshot": (to_canonical_obj(self.evaluation_snapshot) if self.evaluation_snapshot is not None else None),
            "evaluation_digest": self.evaluation_digest,
            "decision_snapshot": (to_canonical_obj(self.decision_snapshot) if self.decision_snapshot is not None else None),
            "decision_digest": self.decision_digest,
            "workflow_ir_digest": self.workflow_ir_digest,
            "expires_at": _fmt_ts(self.expires_at),
            "non_decision_reason": (self.non_decision_reason.value if self.non_decision_reason else None),
            "reason_codes": list(self.reason_codes),
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "authorization_performed": self.authorization_performed,
            "envelope_issued": self.envelope_issued,
            "actiongate_invoked": self.actiongate_invoked,
            "actuation_performed": self.actuation_performed,
            "effect_verified": self.effect_verified,
            "executable": self.executable,
        }

    def digest(self) -> str:
        return _digest(self.to_canonical_dict())

    _ALLOWED_KEYS = frozenset({
        "schema_version", "request_digest", "subject_digest", "tenant_id", "disposition",
        "evaluator_principal_id", "evaluated_at", "risk_outcome", "evaluation_snapshot",
        "evaluation_digest", "decision_snapshot", "decision_digest", "workflow_ir_digest",
        "expires_at", "non_decision_reason", "reason_codes", "correlation_id",
        "idempotency_key", "authorization_performed", "envelope_issued",
        "actiongate_invoked", "actuation_performed", "effect_verified", "executable",
    })

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SubjectRiskDecision":
        if not isinstance(data, Mapping):
            raise SeamContractError("result data must be a mapping")
        # Strict parsing (audit): unknown fields rejected; schema_version mandatory.
        unknown = set(data) - cls._ALLOWED_KEYS
        if unknown:
            raise SeamContractError(f"unknown result field(s): {sorted(unknown)}")
        if "schema_version" not in data:
            raise SeamContractError("result requires an explicit schema_version")
        outcome = data.get("risk_outcome")
        ndr = data.get("non_decision_reason")

        def _flag(name: str) -> bool:
            # The executable flags are read and passed through so a forged True is
            # REJECTED by __post_init__ rather than silently normalized to False.
            v = data.get(name, False)
            if not isinstance(v, bool):
                raise SeamContractError(f"{name} must be a bool")
            return v

        return cls(
            schema_version=data["schema_version"],
            request_digest=data["request_digest"],
            subject_digest=data["subject_digest"],
            tenant_id=data["tenant_id"],
            disposition=SubjectRiskDisposition(data["disposition"]),
            evaluator_principal_id=data["evaluator_principal_id"],
            evaluated_at=_parse_ts(data["evaluated_at"]),
            risk_outcome=(RiskOutcome(outcome) if outcome is not None else None),
            evaluation_snapshot=data.get("evaluation_snapshot"),
            evaluation_digest=data.get("evaluation_digest"),
            decision_snapshot=data.get("decision_snapshot"),
            decision_digest=data.get("decision_digest"),
            workflow_ir_digest=data.get("workflow_ir_digest", ""),
            expires_at=_parse_ts(data.get("expires_at")),
            non_decision_reason=(SubjectRiskNonDecisionReason(ndr) if ndr is not None else None),
            reason_codes=tuple(data.get("reason_codes", ())),
            correlation_id=data.get("correlation_id"),
            idempotency_key=data.get("idempotency_key"),
            authorization_performed=_flag("authorization_performed"),
            envelope_issued=_flag("envelope_issued"),
            actiongate_invoked=_flag("actiongate_invoked"),
            actuation_performed=_flag("actuation_performed"),
            effect_verified=_flag("effect_verified"),
            executable=_flag("executable"),
        )


@runtime_checkable
class PolicyResolverPort(Protocol):
    """Trusted, authority-owned resolution of a subject to its governing WorkflowIR.

    The caller never selects policy: the resolver maps (tenant, purpose, domain, risk
    class, scope) to the authoritative policy. It returns ``None`` when no authoritative
    policy exists (the seam fails closed) and raises when multiple policies claim
    authority (ambiguity → fail closed). A production resolver sets
    ``is_production_authoritative = True``."""

    is_production_authoritative: bool

    def resolve(
        self,
        *,
        tenant_id: str,
        purpose: str,
        domain: str,
        risk_class: Optional[RiskClass],
        requested_scope: Scope,
        now: datetime,
    ) -> Optional[WorkflowIR]: ...


@runtime_checkable
class TrustedControlEvidenceResolverPort(Protocol):
    """Trusted resolution of evidence *references* to admittable control-evidence records.

    This is the explicit integration point RA-5 will implement. It resolves the request's
    opaque ``evidence_references`` to candidate ``ControlEvidenceRecord``s that then pass
    through the *existing* production ingress/admission/assurance gates — it does not
    itself promote evidence to trusted status. A production resolver sets
    ``is_production_authoritative = True``. Absent/failed resolution ⇒ no backing ⇒ the
    non-compensatory gate sees the control as MISSING (fail closed)."""

    is_production_authoritative: bool

    def resolve(
        self,
        *,
        tenant_id: str,
        risk_case_id: str,
        workflow_ir_digest: str,
        policy_digest: str,
        subject_id: str,
        evidence_references: tuple[str, ...],
        now: datetime,
    ) -> tuple[Any, ...]: ...


@dataclass(frozen=True)
class ReferencePolicyResolver:
    """Reference-only policy resolver backed by a fixed ``(purpose, domain) -> WorkflowIR``
    map. **Conformance/testing only** — never production-authoritative. The production
    factory rejects it."""

    by_purpose_domain: Mapping[tuple[str, str], WorkflowIR]
    is_production_authoritative: bool = field(default=False, init=False)

    def resolve(self, *, tenant_id, purpose, domain, risk_class, requested_scope, now):
        return self.by_purpose_domain.get((purpose, domain))


@dataclass(frozen=True)
class ReferenceControlEvidenceResolver:
    """Reference-only evidence resolver. **Conformance/testing only** — never
    production-authoritative; the production factory rejects it. By default it resolves
    nothing (so required controls fail closed to MISSING)."""

    records_by_reference: Mapping[str, Any] = field(default_factory=dict)
    is_production_authoritative: bool = field(default=False, init=False)

    def resolve(self, *, tenant_id, risk_case_id, workflow_ir_digest, policy_digest,
                subject_id, evidence_references, now):
        out = []
        for ref in evidence_references:
            rec = self.records_by_reference.get(ref)
            if rec is not None:
                out.append(rec)
        return tuple(out)


# ---------------------------------------------------------------------------
# v2 neutral subject-context contract layer (Cloud Scaling Phase 4A)
#
# Three canonical, frozen, closed, schema-tagged objects and one pure validator:
#
#     SubjectContext  --digest-->  context_digest
#     SubjectBinding  --digest-->  subject_digest      (carries context_digest)
#     SubjectRiskEvaluationRequestV2 --digest--> request_digest  (carries subject_digest)
#
# **Schema-tagged canonical hashing (honest description).** ``crypto.hashing.digest``
# is a *bare* SHA-256 over ``canonical_bytes`` — it is NOT a domain-separated or keyed
# construction, and this layer introduces no new hashing primitive and no cryptographic
# domain prefix. Separation between the three digests comes from each object embedding
# its own fixed ``schema_version`` inside its own canonical form (so different objects
# necessarily produce different canonical bytes) *plus* strict validation at every
# consumer: a digest computed under one schema tag is never automatically accepted in
# another semantic slot, because the only consumer that interprets a digest —
# ``validate_subject_binding`` — recomputes it from a re-validated object rather than
# trusting the carried value.
#
# **Authority boundary.** Nothing here resolves policy, evaluates risk, issues an
# envelope, calls ActionGate, mints or accepts a credential, actuates a provider, or
# verifies an effect. There is no field through which a caller can supply a PASS, a
# trusted control result, or a risk decision — the field sets are closed and exclude
# them structurally. ``SubjectBindingValidation`` is an integrity finding, not a grant.
#
# **Recorded Phase 4B requirement — evaluation-time authority (ADR §10, F6).**
# This PR deliberately changes NO evaluation-seam behavior, so caller time does not
# become authoritative here and the deliberately-separate reference/test seam keeps
# working. The requirement is recorded, not implemented:
#
#     A trusted PRODUCTION v2 evaluation MUST REJECT (fail closed, NOT_EVALUATED) a
#     caller-supplied ``evaluation_time``. It must never be silently ignored. Trusted
#     production time comes ONLY from Risk Authority's injected clock. Reference/test
#     mode remains the ONLY place an explicit clock may be supplied.
#
# That rejection belongs to the evaluation seam, not to this data contract: enforcing
# it here would also break the reference seam, which legitimately injects time. The
# ``evaluation_time`` field below is therefore validated for *shape* only.
# ---------------------------------------------------------------------------


class SubjectBindingError(SeamContractError):
    """Raised when a v2 subject binding cannot be reconstructed or does not reconcile.

    A subclass of :class:`SeamContractError` (and therefore of ``RiskAuthorityError``)
    so a caller may catch either. It signals a **fail-closed non-decision**: no risk
    evaluation happened and no authority of any kind was produced."""


def _require_nfc_str(name: str, value: Any, *, allow_empty: bool, token: bool = False) -> str:
    """Validate a canonical string: no silent NFC coercion by the canonicalizer.

    The RA canonicalizer NFC-normalizes every string, so accepting a non-NFC input here
    would silently change the value that ends up in the digest. Rejecting it keeps
    direct-construction and ``from_dict`` parity exact. ``token=True`` additionally
    rejects surrounding whitespace (``action_type`` is a canonical enum token, not a
    free-form label)."""

    if isinstance(value, bool) or not isinstance(value, str):
        raise SeamContractError(f"{name} must be a string")
    if value == "" and not allow_empty:
        raise SeamContractError(f"{name} must be a non-empty string")
    if unicodedata.normalize("NFC", value) != value:
        raise SeamContractError(f"{name} must already be NFC-normalized")
    if token and value.strip() != value:
        raise SeamContractError(f"{name} must not carry leading/trailing whitespace")
    return value


def _require_digest(name: str, value: Any) -> str:
    """Validate the repository's established digest syntax (``sha256:`` + 64 lc hex)."""

    if isinstance(value, bool) or not isinstance(value, str):
        raise SeamContractError(f"{name} must be a string")
    if not _DIGEST_RE.match(value):
        raise SeamContractError(
            f"{name} must be a canonical digest ('{DIGEST_PREFIX}' + 64 lowercase hex)"
        )
    return value


def _require_canonical_int(name: str, value: Any) -> Optional[int]:
    """Canonical integer or ``None``. ``bool`` and ``float`` are rejected outright.

    ``bool`` is a subclass of ``int`` in Python, so it must be excluded explicitly or
    ``True`` would silently canonicalize as a magnitude. ``float`` is rejected here as
    well as by ``to_canonical_obj`` so the failure is a typed contract error at
    construction rather than a ``TypeError`` at digest time."""

    if value is None:
        return None
    if isinstance(value, bool):
        raise SeamContractError(f"{name} must be an int, not a bool")
    if isinstance(value, float):
        raise SeamContractError(f"{name} must be an int, not a float")
    if not isinstance(value, int):
        raise SeamContractError(f"{name} must be an int or None")
    return value


def _require_utc(name: str, value: Any) -> datetime:
    """Require an explicit, timezone-aware UTC datetime.

    Naive datetimes are rejected rather than assumed-UTC, and a non-zero offset is
    rejected rather than converted: both would be silent coercions of a value that the
    digest is about to freeze. Callers pass ``tzinfo=timezone.utc`` explicitly, which is
    exactly what ``from_dict`` produces — so direct construction and reconstruction have
    identical validity rules."""

    if not isinstance(value, datetime):
        raise SeamContractError(f"{name} must be a datetime")
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise SeamContractError(f"{name} must be timezone-aware UTC (naive datetime rejected)")
    if offset != timedelta(0):
        raise SeamContractError(f"{name} must be UTC (non-UTC offset rejected)")
    return value


@dataclass(frozen=True)
class SubjectContext:
    """Strict, closed, frozen **neutral subject facts** (schema ``risk-subject-context-1``).

    This is a neutral subject-fact contract, **not** a generic attribute map. The field
    set is closed and deliberately excludes ``tenant_id``, ``subject_id``, evidence
    references, caller-selected policy identifiers, risk decisions, control results,
    keys/credentials, authorization envelopes, execution instructions and executable
    flags — identity and evidence references are authoritative on the **outer** request
    (ADR §5.1 F2), and the rest have no legitimate home in a subject fact.

    Encoding rules (ADR §5.2): canonical enum string for ``action_type``; canonical
    integers only for magnitudes (``bool``/``float`` rejected); explicit UTC timestamps;
    ``None`` is a distinct sentinel that is never coerced to ``""`` or ``0``, so
    "no environment" and ``environment = ""`` yield **different** ``context_digest``s."""

    action_type: str
    subject_asserted_at: datetime
    subject_valid_from: datetime
    subject_valid_until: datetime
    environment: Optional[str] = None
    region: Optional[str] = None
    zone: Optional[str] = None
    compute_group: Optional[str] = None
    resource_class: Optional[str] = None
    magnitude_before: Optional[int] = None
    magnitude_after: Optional[int] = None
    schema_version: str = SUBJECT_CONTEXT_SCHEMA_VERSION

    _OPTIONAL_STRINGS = ("environment", "region", "zone", "compute_group", "resource_class")

    def __post_init__(self) -> None:
        # The schema tag is fixed, not caller-chosen: a foreign tag is a cross-schema
        # substitution attempt and fails closed here rather than at digest comparison.
        if self.schema_version != SUBJECT_CONTEXT_SCHEMA_VERSION:
            raise SeamContractError(
                f"schema_version must be {SUBJECT_CONTEXT_SCHEMA_VERSION!r}"
            )
        _require_nfc_str("action_type", self.action_type, allow_empty=False, token=True)
        for name in self._OPTIONAL_STRINGS:
            value = getattr(self, name)
            if value is not None:
                # "" is a legitimate *named* value, distinct from the None sentinel
                # (ADR §5.2 "Missing-vs-named", §6).
                _require_nfc_str(name, value, allow_empty=True)
        for name in ("magnitude_before", "magnitude_after"):
            _require_canonical_int(name, getattr(self, name))
        for name in ("subject_asserted_at", "subject_valid_from", "subject_valid_until"):
            _require_utc(name, getattr(self, name))
        if not (self.subject_valid_from <= self.subject_asserted_at <= self.subject_valid_until):
            raise SeamContractError(
                "temporal ordering must satisfy "
                "subject_valid_from <= subject_asserted_at <= subject_valid_until"
            )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "environment": self.environment,
            "region": self.region,
            "zone": self.zone,
            "compute_group": self.compute_group,
            "resource_class": self.resource_class,
            "action_type": self.action_type,
            "magnitude_before": self.magnitude_before,
            "magnitude_after": self.magnitude_after,
            "subject_asserted_at": _fmt_ts(self.subject_asserted_at),
            "subject_valid_from": _fmt_ts(self.subject_valid_from),
            "subject_valid_until": _fmt_ts(self.subject_valid_until),
        }

    def digest(self) -> str:
        """The schema-tagged canonical identity of these neutral facts."""

        return _digest(self.to_canonical_dict())

    _ALLOWED_KEYS = frozenset({
        "schema_version", "environment", "region", "zone", "compute_group",
        "resource_class", "action_type", "magnitude_before", "magnitude_after",
        "subject_asserted_at", "subject_valid_from", "subject_valid_until",
    })

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SubjectContext":
        if not isinstance(data, Mapping):
            raise SeamContractError("subject_context data must be a mapping")
        unknown = set(data) - cls._ALLOWED_KEYS
        if unknown:
            raise SeamContractError(f"unknown subject_context field(s): {sorted(unknown)}")
        if "schema_version" not in data:
            raise SeamContractError("subject_context requires an explicit schema_version")
        for name in ("action_type", "subject_asserted_at", "subject_valid_from",
                     "subject_valid_until"):
            if name not in data:
                raise SeamContractError(f"subject_context requires {name}")
        return cls(
            schema_version=data["schema_version"],
            environment=data.get("environment"),
            region=data.get("region"),
            zone=data.get("zone"),
            compute_group=data.get("compute_group"),
            resource_class=data.get("resource_class"),
            action_type=data["action_type"],
            # Magnitudes are passed through untouched so a float/bool is REJECTED by
            # __post_init__ rather than silently narrowed by an int() coercion.
            magnitude_before=data.get("magnitude_before"),
            magnitude_after=data.get("magnitude_after"),
            subject_asserted_at=_parse_ts(data["subject_asserted_at"]),
            subject_valid_from=_parse_ts(data["subject_valid_from"]),
            subject_valid_until=_parse_ts(data["subject_valid_until"]),
        )


@dataclass(frozen=True)
class SubjectBinding:
    """Frozen, closed binding anchors (schema ``risk-subject-binding-1``).

    Carries **only** binding anchors. ``tenant_id`` / ``subject_id`` / ``subject_type``
    are **derived** from the outer request when validating one (they are not independent
    second sources of truth, and ``SubjectContext`` carries no identity copy at all), and
    both digest fields must satisfy the established digest syntax."""

    tenant_id: str
    subject_id: str
    subject_type: str
    recommendation_digest: str
    context_digest: str
    schema_version: str = SUBJECT_BINDING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SUBJECT_BINDING_SCHEMA_VERSION:
            raise SeamContractError(
                f"schema_version must be {SUBJECT_BINDING_SCHEMA_VERSION!r}"
            )
        for name in ("tenant_id", "subject_id", "subject_type"):
            _require_nfc_str(name, getattr(self, name), allow_empty=False)
        for name in ("recommendation_digest", "context_digest"):
            _require_digest(name, getattr(self, name))

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "recommendation_digest": self.recommendation_digest,
            "context_digest": self.context_digest,
        }

    def digest(self) -> str:
        """The schema-tagged canonical identity of this binding (the ``subject_digest``)."""

        return _digest(self.to_canonical_dict())

    _ALLOWED_KEYS = frozenset({
        "schema_version", "tenant_id", "subject_id", "subject_type",
        "recommendation_digest", "context_digest",
    })

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SubjectBinding":
        if not isinstance(data, Mapping):
            raise SeamContractError("subject_binding data must be a mapping")
        unknown = set(data) - cls._ALLOWED_KEYS
        if unknown:
            raise SeamContractError(f"unknown subject_binding field(s): {sorted(unknown)}")
        for name in sorted(cls._ALLOWED_KEYS):
            if name not in data:
                raise SeamContractError(f"subject_binding requires {name}")
        return cls(
            schema_version=data["schema_version"],
            tenant_id=data["tenant_id"],
            subject_id=data["subject_id"],
            subject_type=data["subject_type"],
            recommendation_digest=data["recommendation_digest"],
            context_digest=data["context_digest"],
        )


@dataclass(frozen=True)
class SubjectRiskEvaluationRequestV2:
    """A v2 subject-risk evaluation request (schema ``risk-subject-evaluation-request-2``).

    A **successor** contract, not a subclass of :class:`SubjectRiskEvaluationRequest`:
    v1 is left byte-for-byte untouched, and because a v2 request is not an instance of
    the v1 type it cannot silently flow into a v1-typed call site. There is no automatic
    v1↔v2 conversion in either direction.

    The **outer request remains the sole authority** for tenant, subject identity and
    type, evidence references, requested purpose/domain/scope, and correlation and
    idempotency data. It adds exactly two fields over v1:

    * ``subject_context`` — the raw, immutable, inspectable layered commitment (ADR §5.3);
    * ``recommendation_digest`` — the authoritative recommendation digest.

    **Why ``recommendation_digest`` is an outer field.** ADR §5.3 step 3 requires Risk
    Authority to reconstruct :class:`SubjectBinding` from ``{outer tenant_id, outer
    subject_id, subject_type, recommendation_digest, recomputed context_digest}`` before
    policy resolution, but the ADR's illustrated v2 request carries no such field: the
    recommendation digest's only home there is *inside* ``SubjectBinding`` (§5.1 row 1),
    it is absent from ``evidence_references`` (§5.1 rows 12-13, §5.3), and it cannot be
    recovered from ``subject_digest`` or ``idempotency_key`` because both are one-way
    SHA-256 outputs. Reconstruction was therefore impossible as illustrated. This
    explicit outer field is the narrowest versioned correction: it is additive, confined
    to v2, keeps ``SubjectContext`` free of it, and preserves the derived-anchor rule.
    Recorded as a divergence from the merged ADR §5.3 illustration; the ADR is unedited.

    ``subject_context`` and ``recommendation_digest`` are required **together** — a
    request carrying one without the other is a half-bound request that could never be
    reconciled, so it fails closed at construction rather than at validation time. With
    both absent the request is behaviorally equivalent to v1."""

    subject_type: str
    subject_id: str
    subject_digest: str
    tenant_id: str
    requested_purpose: str
    requested_domain: str
    requested_scope: Scope
    requested_risk_class: Optional[RiskClass] = None
    jurisdictions: tuple[str, ...] = ()
    requested_tools: tuple[str, ...] = ()
    requested_autonomy_level: int = 0
    requested_data_classes: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    evaluation_time: Optional[datetime] = None
    subject_context: Optional[SubjectContext] = None
    recommendation_digest: Optional[str] = None
    schema_version: str = EVALUATION_REQUEST_SCHEMA_VERSION_V2

    def __post_init__(self) -> None:
        if self.schema_version != EVALUATION_REQUEST_SCHEMA_VERSION_V2:
            raise SeamContractError(
                f"schema_version must be {EVALUATION_REQUEST_SCHEMA_VERSION_V2!r}"
            )
        for name in ("subject_type", "subject_id", "tenant_id",
                     "requested_purpose", "requested_domain"):
            v = getattr(self, name)
            if not isinstance(v, str) or v == "":
                raise SeamContractError(f"{name} must be a non-empty string")
        # Stricter than v1: the subject digest is recomputed by validate_subject_binding,
        # so it must be a real digest rather than any non-empty string.
        _require_digest("subject_digest", self.subject_digest)
        if not isinstance(self.requested_scope, Scope):
            raise SeamContractError("requested_scope must be a Scope")
        if self.requested_risk_class is not None and not isinstance(self.requested_risk_class, RiskClass):
            raise SeamContractError("requested_risk_class must be a RiskClass or None")
        if isinstance(self.requested_autonomy_level, bool) or not isinstance(self.requested_autonomy_level, int) \
                or self.requested_autonomy_level < 0:
            raise SeamContractError("requested_autonomy_level must be an int >= 0")
        for name in ("jurisdictions", "requested_tools", "requested_data_classes", "evidence_references"):
            seq = getattr(self, name)
            if not isinstance(seq, tuple) or any(not isinstance(x, str) or x == "" for x in seq):
                raise SeamContractError(f"{name} must be a tuple of non-empty strings")
        if self.evaluation_time is not None:
            # NOTE (Phase 4B): a *shape* check only. Whether a caller-supplied
            # evaluation_time is permitted at all belongs to the evaluation seam, which
            # this PR leaves unchanged — see the recorded Phase 4B requirement in the
            # section banner above.
            _require_utc("evaluation_time", self.evaluation_time)
        if self.subject_context is not None and not isinstance(self.subject_context, SubjectContext):
            raise SeamContractError("subject_context must be a SubjectContext or None")
        if self.recommendation_digest is not None:
            _require_digest("recommendation_digest", self.recommendation_digest)
        if (self.subject_context is None) != (self.recommendation_digest is None):
            raise SeamContractError(
                "subject_context and recommendation_digest must be supplied together "
                "(a half-bound request can never be reconciled)"
            )
        object.__setattr__(self, "requested_scope", self.requested_scope.normalized())

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "subject_digest": self.subject_digest,
            "tenant_id": self.tenant_id,
            "requested_purpose": self.requested_purpose,
            "requested_domain": self.requested_domain,
            "requested_scope": _scope_to_dict(self.requested_scope),
            "requested_risk_class": (self.requested_risk_class.value if self.requested_risk_class else None),
            "jurisdictions": list(self.jurisdictions),
            "requested_tools": list(self.requested_tools),
            "requested_autonomy_level": self.requested_autonomy_level,
            "requested_data_classes": list(self.requested_data_classes),
            "evidence_references": list(self.evidence_references),
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "evaluation_time": _fmt_ts(self.evaluation_time),
            "subject_context": (self.subject_context.to_canonical_dict()
                                if self.subject_context is not None else None),
            "recommendation_digest": self.recommendation_digest,
        }

    def digest(self) -> str:
        return _digest(self.to_canonical_dict())

    _ALLOWED_KEYS = frozenset({
        "schema_version", "subject_type", "subject_id", "subject_digest", "tenant_id",
        "requested_purpose", "requested_domain", "requested_scope", "requested_risk_class",
        "jurisdictions", "requested_tools", "requested_autonomy_level",
        "requested_data_classes", "evidence_references", "correlation_id",
        "idempotency_key", "evaluation_time", "subject_context", "recommendation_digest",
    })

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SubjectRiskEvaluationRequestV2":
        if not isinstance(data, Mapping):
            raise SeamContractError("request data must be a mapping")
        unknown = set(data) - cls._ALLOWED_KEYS
        if unknown:
            raise SeamContractError(f"unknown request field(s): {sorted(unknown)}")
        if "schema_version" not in data:
            raise SeamContractError("request requires an explicit schema_version")
        rc = data.get("requested_risk_class")
        ctx = data.get("subject_context")
        return cls(
            schema_version=data["schema_version"],
            subject_type=data["subject_type"],
            subject_id=data["subject_id"],
            subject_digest=data["subject_digest"],
            tenant_id=data["tenant_id"],
            requested_purpose=data["requested_purpose"],
            requested_domain=data["requested_domain"],
            requested_scope=_scope_from_dict(data["requested_scope"]),
            requested_risk_class=(RiskClass(rc) if rc is not None else None),
            jurisdictions=tuple(data.get("jurisdictions", ())),
            requested_tools=tuple(data.get("requested_tools", ())),
            requested_autonomy_level=int(data.get("requested_autonomy_level", 0)),
            requested_data_classes=tuple(data.get("requested_data_classes", ())),
            evidence_references=tuple(data.get("evidence_references", ())),
            correlation_id=data.get("correlation_id"),
            idempotency_key=data.get("idempotency_key"),
            evaluation_time=_parse_ts(data.get("evaluation_time")),
            subject_context=(SubjectContext.from_dict(ctx) if ctx is not None else None),
            recommendation_digest=data.get("recommendation_digest"),
        )


@dataclass(frozen=True)
class SubjectBindingValidation:
    """The typed successful outcome of :func:`validate_subject_binding`.

    An **integrity finding, not a grant**: it states that the request's carried
    ``subject_digest`` reconciles with a binding reconstructed from authoritative outer
    fields over a re-validated context. It is an in-process return value and is never
    serialized or transported, so it deliberately carries no schema tag of its own — it
    is not a wire contract and must not become one.

    Every authority flag is fixed ``False`` and enforced at construction, mirroring
    :class:`SubjectRiskDecision`: reaching this result grants nothing."""

    tenant_id: str
    subject_id: str
    subject_type: str
    recommendation_digest: str
    context_digest: str
    subject_digest: str
    binding: SubjectBinding
    # Fixed non-authority invariants — validating a binding is not an evaluation.
    policy_resolved: bool = False
    risk_evaluated: bool = False
    authority_granted: bool = False
    envelope_issued: bool = False
    actiongate_invoked: bool = False
    actuation_performed: bool = False
    effect_verified: bool = False
    executable: bool = False

    def __post_init__(self) -> None:
        for flag in ("policy_resolved", "risk_evaluated", "authority_granted",
                     "envelope_issued", "actiongate_invoked", "actuation_performed",
                     "effect_verified", "executable"):
            if getattr(self, flag) is not False:
                raise SeamContractError(
                    f"{flag} must be False — binding validation grants no authority"
                )
        if not isinstance(self.binding, SubjectBinding):
            raise SeamContractError("binding must be a SubjectBinding")


def validate_subject_binding(
    request: "SubjectRiskEvaluationRequestV2",
) -> SubjectBindingValidation:
    """Pure, deterministic, fail-closed reconciliation of a v2 request's subject binding.

    Performs the ADR §5.3 pre-resolution steps **in order**:

    1. validate the closed :class:`SubjectContext` (re-validated through ``from_dict``
       over its own canonical form, so a mutated instance cannot slip past);
    2. recompute ``context_digest`` from the supplied **raw** context;
    3. reconstruct :class:`SubjectBinding` **exclusively** from authoritative outer
       request fields, the authoritative ``recommendation_digest``, and the recomputed
       ``context_digest`` — never from any value carried inside the binding itself;
    4. recompute ``subject_digest`` from that reconstruction;
    5. require equality with the request's carried ``subject_digest``;
    6. return the typed :class:`SubjectBindingValidation`.

    An altered raw context paired with a stale ``subject_digest`` fails deterministically
    at step 5, because step 2 re-derives the context digest rather than trusting the one
    committed inside the stale binding.

    This function performs **no** policy resolution, risk evaluation, authority issuance,
    ActionGate call, credential handling or execution, and it is not wired into
    :class:`~risk_authority.api.evaluation_seam.RiskEvaluationSeam` by Phase 4A. It reads
    only its argument — no clock, no I/O, no ambient state — so it is a pure function.

    :raises SubjectBindingError: the request is not a reconcilable v2 request, or the
        reconstructed ``subject_digest`` does not equal the carried one.
    :raises SeamContractError: the carried context is not a valid closed
        ``risk-subject-context-1`` object.
    """

    if not isinstance(request, SubjectRiskEvaluationRequestV2):
        raise SubjectBindingError(
            "binding validation requires a SubjectRiskEvaluationRequestV2 "
            f"({EVALUATION_REQUEST_SCHEMA_VERSION_V2}); no v1 conversion is performed"
        )
    if request.schema_version != EVALUATION_REQUEST_SCHEMA_VERSION_V2:
        raise SubjectBindingError(
            f"unsupported request schema_version: {request.schema_version!r}"
        )
    context = request.subject_context
    if context is None:
        raise SubjectBindingError("v2 request carries no subject_context to reconcile")
    if request.recommendation_digest is None:
        raise SubjectBindingError("v2 request carries no authoritative recommendation_digest")

    # (1) validate the closed context — re-parsed from its own canonical form so that a
    #     frozen-dataclass bypass (object.__setattr__) is caught here, not trusted.
    validated_context = SubjectContext.from_dict(context.to_canonical_dict())

    # (2) recompute the context digest from the supplied raw context.
    context_digest = validated_context.digest()

    # (3) reconstruct the binding from AUTHORITATIVE OUTER fields only.
    binding = SubjectBinding(
        tenant_id=request.tenant_id,
        subject_id=request.subject_id,
        subject_type=request.subject_type,
        recommendation_digest=request.recommendation_digest,
        context_digest=context_digest,
    )

    # (4) recompute the subject digest.
    subject_digest = binding.digest()

    # (5) require equality with the carried commitment — fail closed on any mismatch.
    if subject_digest != request.subject_digest:
        raise SubjectBindingError(
            "subject_digest mismatch: the reconstructed binding does not reconcile with "
            "the digest carried on the request (fail closed, no evaluation performed)"
        )

    # (6) typed success — an integrity finding that grants nothing.
    return SubjectBindingValidation(
        tenant_id=request.tenant_id,
        subject_id=request.subject_id,
        subject_type=request.subject_type,
        recommendation_digest=request.recommendation_digest,
        context_digest=context_digest,
        subject_digest=subject_digest,
        binding=binding,
    )
