"""Deterministic structural validation for governed action requests.

Returns typed results (blockers + warnings), never a bare boolean. It never infers
missing values: missing required context is a blocker (fail closed). It performs no
business action and never reinterprets assessment or evidence content.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..actions.action_request import ActionRequest
from ..actions.status import ActionRequestStatus
from ..actions.validation import (
    ActionRequestValidationIssue,
    ActionRequestValidationResult,
)
from ..common import Clock, utc_now
from ..decisions.status import CaseStatus, EffectiveStatus
from ..repositories.action_request_repository import ActionRequestRepository
from ..repositories.decision_case_repository import DecisionCaseRepository

_DEAD_CASE_STATUSES = frozenset({CaseStatus.CANCELLED, CaseStatus.CLOSED})


class ActionRequestValidationService:
    def __init__(
        self,
        action_request_repository: ActionRequestRepository,
        decision_case_repository: DecisionCaseRepository,
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = action_request_repository
        self._cases = decision_case_repository
        self._clock = clock

    def decision_is_superseded(self, case_id: str, decision_id: str) -> bool:
        """True if a later decision on the case supersedes this one."""
        for other in self._cases.list_decisions(case_id):
            if other.supersedes_decision_id == decision_id:
                return True
        return False

    def validate(self, request: ActionRequest) -> ActionRequestValidationResult:
        """Structural readiness of an existing request for its next step."""
        now = self._clock()
        blockers: list[ActionRequestValidationIssue] = []
        warnings: list[ActionRequestValidationIssue] = []

        def block(code: str, msg: str, field: str = "") -> None:
            blockers.append(ActionRequestValidationIssue(code=code, message=msg, field=field))

        # decision existence + effectiveness + supersession
        try:
            decision = self._cases.get_decision(request.decision_id)
        except Exception:  # noqa: BLE001
            decision = None
            block("DECISION_NOT_FOUND", f"decision '{request.decision_id}' not found")
        if decision is not None:
            if decision.tenant_id != request.tenant_id:
                block("CROSS_TENANT_DECISION", "decision belongs to a different tenant")
            if decision.effective_status is not EffectiveStatus.EFFECTIVE:
                block("DECISION_NOT_EFFECTIVE",
                      f"decision is {decision.effective_status.value}")
            if self.decision_is_superseded(request.decision_case_id, request.decision_id):
                block("DECISION_SUPERSEDED", "a later decision supersedes this one")

        # case status
        try:
            case = self._cases.get_case(request.decision_case_id)
            if case.status in _DEAD_CASE_STATUSES:
                block("CASE_NOT_ACTIVE", f"case is {case.status.value}")
        except Exception:  # noqa: BLE001
            block("CASE_NOT_FOUND", f"case '{request.decision_case_id}' not found")

        # mapping still resolvable at the pinned version
        try:
            self._repo.get_action_mapping(
                request.action_mapping_ref.ref_id, request.action_mapping_ref.version)
        except Exception:  # noqa: BLE001
            block("MAPPING_VERSION_MISSING",
                  "the pinned action-mapping version is not resolvable")

        # parameters must be explicit (no inference)
        if not request.target_system.strip():
            block("TARGET_SYSTEM_MISSING", "target system is required")

        # CER presence is required only from CER_BOUND onward
        if request.status in (ActionRequestStatus.CER_BOUND,
                              ActionRequestStatus.READY_FOR_AUTHORIZATION):
            if not request.cer_id:
                block("CER_MISSING", "a bound CER is required at this stage")

        return ActionRequestValidationResult(
            valid=not blockers, blockers=tuple(blockers), warnings=tuple(warnings),
            validated_at=now)
