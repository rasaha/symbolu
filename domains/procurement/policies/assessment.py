"""Procurement policy assessment — deterministic, no AI.

A ``ProcurementAssessmentService`` evaluates a :class:`PurchaseRequest` against a
fixed set of deterministic policy checks and produces a :class:`PolicyAssessment`
record. The assessment is the *upstream governance record* the kernel decision
case links to (through the neutral ``LinkedRecordPort``); the kernel never reads
its content, only its finalized/blocked status via the adapter.

Deterministic only — every check is a pure function of the request. No inference,
no scoring model, no autonomous approval.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field

from decision_governance.base import DomainModel
from decision_governance.common import Clock, IdFactory, new_id, utc_now

from ..requests.contracts import PurchaseRequest


class AssessmentStatus(str, Enum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"


class PolicyCheck(DomainModel):
    """One deterministic policy check and its outcome."""

    check_id: str
    passed: bool
    detail: str = ""


class PolicyAssessment(DomainModel):
    """The deterministic policy-assessment record for a purchase request."""

    assessment_id: str
    tenant_id: str
    request_id: str
    version: int
    status: AssessmentStatus
    subject_ref: str
    total_amount: int
    checks: tuple[PolicyCheck, ...]
    blocked: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def is_finalized(self) -> bool:
        return self.status is AssessmentStatus.FINALIZED

    @property
    def failed_checks(self) -> tuple[PolicyCheck, ...]:
        return tuple(c for c in self.checks if not c.passed)


class InMemoryProcurementAssessmentRepository:
    """Append-only, version-aware in-memory store of policy assessments."""

    def __init__(self) -> None:
        self._data: dict[str, PolicyAssessment] = {}

    def add(self, assessment: PolicyAssessment) -> PolicyAssessment:
        self._data[assessment.assessment_id] = assessment
        return assessment

    def get(self, assessment_id: str) -> Optional[PolicyAssessment]:
        return self._data.get(assessment_id)


# Checks that, when failed, block the assessment (fail-closed governance).
_BLOCKING_CHECKS = frozenset({"budget_exists", "supplier_exists", "required_fields_complete"})


class ProcurementAssessmentService:
    """Runs deterministic policy checks and produces a PolicyAssessment."""

    def __init__(
        self,
        repository: InMemoryProcurementAssessmentRepository,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = repository
        self._new_id = id_factory
        self._clock = clock

    def assess(self, request: PurchaseRequest) -> PolicyAssessment:
        checks = self._run_checks(request)
        blocked = any(
            (not c.passed) and c.check_id in _BLOCKING_CHECKS for c in checks
        )
        assessment = PolicyAssessment(
            assessment_id=self._new_id("passess"),
            tenant_id=request.tenant_id,
            request_id=request.request_id,
            version=request.version,
            status=AssessmentStatus.FINALIZED,
            subject_ref=request.request_id,
            total_amount=request.total_amount,
            checks=checks,
            blocked=blocked,
            created_at=self._clock(),
        )
        return self._repo.add(assessment)

    @staticmethod
    def _run_checks(request: PurchaseRequest) -> tuple[PolicyCheck, ...]:
        return (
            PolicyCheck(
                check_id="budget_exists",
                passed=bool(request.budget.budget_id.strip()),
                detail=f"budget={request.budget.budget_id}"),
            PolicyCheck(
                check_id="supplier_exists",
                passed=bool(request.supplier.supplier_id.strip()),
                detail=f"supplier={request.supplier.supplier_id}"),
            PolicyCheck(
                check_id="required_fields_complete",
                passed=bool(request.items) and bool(request.requester.strip()),
                detail=f"items={len(request.items)}"),
            PolicyCheck(
                check_id="justification_present",
                passed=bool(request.justification.strip()),
                detail="justification supplied" if request.justification.strip()
                else "no justification"),
            PolicyCheck(
                check_id="amount_calculated",
                passed=request.total_amount >= 0,
                detail=f"total={request.total_amount}"),
            PolicyCheck(
                check_id="budget_sufficient",
                passed=request.total_amount <= request.budget.available_amount,
                detail=f"total={request.total_amount} <= "
                       f"available={request.budget.available_amount}"),
        )
