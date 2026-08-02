"""ContextEnvelopeRecord (CER) — the minimum governance context for authorization.

The CER is a **governance context record, not an execution command**. It carries
only the minimum context a runtime authorizer needs: who, under what authority and
policy, for what approved action, on what target, with what parameter bounds and
required controls. It deliberately excludes raw evidence, free-form subject text,
credentials, model secrets, access tokens, hidden subject comparisons, and
unapproved parameters — those cannot even be represented in its typed fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import canonical_hash, utc_now
from ..decisions.status import AuthorityType, DecisionOutcome
from ..decisions.subject import SubjectRef, VersionedRef
from ..base import DomainModel
from ..errors import DomainValidationError
from ..vocabulary import ReasonCode


class SubjectContext(DomainModel):
    subject_refs: tuple[SubjectRef, ...]
    data_classifications: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "SubjectContext":
        if not self.subject_refs:
            raise DomainValidationError("subject context requires at least one subject")
        return self


class AuthoritySummary(DomainModel):
    """A minimized view of the deciding authority — type and scope, no secrets."""

    authority_type: AuthorityType
    authority_id: str = ""
    decision_scope: str = ""
    segregation_of_duties: bool = False
    required_approvals: int = 0
    granting_policy_ref: Optional[VersionedRef] = None


class PolicyContext(DomainModel):
    policy_refs: tuple[VersionedRef, ...] = ()
    jurisdiction: str = ""


class DecisionContext(DomainModel):
    decision_case_id: str
    decision_case_version: int
    decision_id: str
    decision_outcome: DecisionOutcome
    override_record_id: Optional[str] = None
    reason_codes: tuple[ReasonCode, ...] = ()


class ContextEnvelopeRecord(DomainModel):
    """An immutable, minimized governance context bound to one action request."""

    cer_id: str
    tenant_id: str
    decision_case_id: str
    decision_id: str
    action_request_id: str
    action_type: str
    target_system: str
    subject_context: SubjectContext
    authority_context: AuthoritySummary
    policy_context: PolicyContext
    decision_context: DecisionContext
    runtime_constraints: tuple[str, ...] = ()
    data_classifications: tuple[str, ...] = ()
    permitted_parameters: tuple[str, ...] = ()
    prohibited_parameters: tuple[str, ...] = ()
    required_controls: tuple[str, ...] = ()
    issued_at: datetime = Field(default_factory=utc_now)
    expires_at: Optional[datetime] = None
    schema_version: str = "cer.v1"
    content_hash: str = ""
    correlation_id: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ContextEnvelopeRecord":
        for req in ("cer_id", "tenant_id", "decision_case_id", "decision_id",
                    "action_request_id", "action_type", "target_system"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if (self.expires_at is not None and self.expires_at < self.issued_at):
            raise DomainValidationError("expires_at must be >= issued_at")
        overlap = set(self.permitted_parameters) & set(self.prohibited_parameters)
        if overlap:
            raise DomainValidationError(
                f"parameters both permitted and prohibited: {sorted(overlap)}")
        return self

    def compute_hash(self) -> str:
        """Deterministic content hash: identical governance context ⇒ identical hash."""
        return canonical_hash({
            "tenant_id": self.tenant_id,
            "decision_case_id": self.decision_case_id,
            "decision_id": self.decision_id,
            "action_request_id": self.action_request_id,
            "action_type": self.action_type,
            "target_system": self.target_system,
            "subjects": sorted(s.subject_id for s in self.subject_context.subject_refs),
            "authority_type": self.authority_context.authority_type.value,
            "authority_scope": self.authority_context.decision_scope,
            "policy_refs": sorted(
                f"{r.ref_id}:{r.version}" for r in self.policy_context.policy_refs),
            "decision_outcome": self.decision_context.decision_outcome.value,
            "override_record_id": self.decision_context.override_record_id or "",
            "permitted_parameters": sorted(self.permitted_parameters),
            "prohibited_parameters": sorted(self.prohibited_parameters),
            "required_controls": sorted(self.required_controls),
            "data_classifications": sorted(self.data_classifications),
            "schema_version": self.schema_version,
        })

    def is_expired(self, at: datetime) -> bool:
        return self.expires_at is not None and at > self.expires_at
