"""HiringActionRequest — the hiring-domain action contract.

Carries candidate, role, level, compensation bounds, location, employment type,
and decision/contract provenance. It is translated by an adapter into the
platform CER / shared ActionGate contract via :meth:`to_cer_payload` — this
package neither authorizes nor executes the action (that is ActionGate + Runtime
Assurance + HRIS, reached through ports).
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from ..common import canonical_hash, new_id
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .enums import EmploymentType
from .refs import ContractRef


class HiringActionSnapshot(DomainModel):
    """A comparable snapshot of a concrete hiring action.

    Used to compare the *authorized* action against the *executed* action during
    reconciliation. Frozen models compare by value, so ``==`` is the equivalence
    test.
    """

    level: str
    salary: float = Field(ge=0)
    salary_currency: str = "USD"
    role_id: str
    location: str
    employment_type: EmploymentType


class CompensationBounds(DomainModel):
    """Approved compensation bounds for the action (mirrors the contract ceiling)."""

    salary_ceiling: float = Field(ge=0)
    salary_floor: float = Field(default=0.0, ge=0)
    currency: str = "USD"

    @model_validator(mode="after")
    def _validate(self) -> "CompensationBounds":
        if self.salary_floor > self.salary_ceiling:
            raise DomainValidationError("salary_floor must be <= salary_ceiling")
        if not self.currency.strip():
            raise DomainValidationError("currency is required")
        return self


class HiringActionRequest(DomainModel):
    """A governed hiring action, pending shared-ActionGate authorization."""

    action_request_id: str = Field(default_factory=lambda: new_id("hact"))
    candidate_id: str
    role_id: str
    level: str
    compensation: CompensationBounds
    location: str
    employment_type: EmploymentType
    contract_ref: ContractRef
    decision_id: str
    recommendation_id: str

    @model_validator(mode="after")
    def _validate(self) -> "HiringActionRequest":
        for field in ("candidate_id", "role_id", "level", "location", "decision_id", "recommendation_id"):
            if not getattr(self, field).strip():
                raise DomainValidationError(f"{field} is required")
        return self

    def _digest_body(self) -> dict:
        """The semantic action payload the content digest covers (excludes the
        random ``action_request_id`` so the digest is a pure function of the action)."""
        return {
            "action_type": "HIRING_OFFER",
            "subject": {"candidate_id": self.candidate_id, "role_id": self.role_id},
            "action": {
                "level": self.level,
                "salary_ceiling": self.compensation.salary_ceiling,
                "salary_floor": self.compensation.salary_floor,
                "currency": self.compensation.currency,
                "location": self.location,
                "employment_type": self.employment_type.value,
            },
            "provenance": {
                "contract_id": self.contract_ref.contract_id,
                "contract_version": self.contract_ref.version,
                "ir_digest": self.contract_ref.ir_digest,
                "decision_id": self.decision_id,
                "recommendation_id": self.recommendation_id,
            },
        }

    @property
    def content_digest(self) -> str:
        """SHA-256 over the semantic action payload. Binds authorization to the
        exact action; any post-authorization mutation changes this digest."""
        return canonical_hash(self._digest_body())

    def snapshot(self) -> HiringActionSnapshot:
        """A comparable snapshot of the authorized action (salary = ceiling)."""
        return HiringActionSnapshot(
            level=self.level,
            salary=self.compensation.salary_ceiling,
            salary_currency=self.compensation.currency,
            role_id=self.role_id,
            location=self.location,
            employment_type=self.employment_type,
        )

    def to_cer_payload(self) -> dict:
        """Translate to the neutral CER / shared-ActionGate payload.

        Deliberately platform-agnostic (a plain dict): an adapter maps this onto
        the concrete Context Envelope Record / ActionGate request. Carries full
        decision + contract provenance and the action digest so the shared gate
        can bind its authorization to the exact action presented.
        """
        body = self._digest_body()
        return {
            **body,
            "action_request_id": self.action_request_id,
            "action_digest": self.content_digest,
        }
