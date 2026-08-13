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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from ..crypto.canonical import to_canonical_obj
from ..crypto.hashing import digest as _digest
from ..domain.enums import RiskClass, RiskOutcome
from ..domain.errors import RiskAuthorityError
from ..domain.scope import Scope
from ..domain.workflow_ir import WorkflowIR

__all__ = [
    "EVALUATION_REQUEST_SCHEMA_VERSION",
    "EVALUATION_RESULT_SCHEMA_VERSION",
    "SUPPORTED_REQUEST_SCHEMA_VERSIONS",
    "SubjectRiskDisposition",
    "SubjectRiskNonDecisionReason",
    "SubjectRiskEvaluationRequest",
    "SubjectRiskDecision",
    "PolicyResolverPort",
    "TrustedControlEvidenceResolverPort",
    "ReferencePolicyResolver",
    "ReferenceControlEvidenceResolver",
    "SeamContractError",
]

EVALUATION_REQUEST_SCHEMA_VERSION = "risk-subject-evaluation-request-1"
EVALUATION_RESULT_SCHEMA_VERSION = "risk-subject-decision-1"
SUPPORTED_REQUEST_SCHEMA_VERSIONS = frozenset({EVALUATION_REQUEST_SCHEMA_VERSION})

_TS_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


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
