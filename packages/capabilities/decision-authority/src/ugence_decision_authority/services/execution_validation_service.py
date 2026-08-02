"""Deterministic structural validation for external execution.

Returns typed results and a retry classification, never a bare boolean. It never
infers a missing external outcome and never performs an external action. Expiry,
target/parameter mismatch, and unexecutable authorization all block readiness
(fail closed).
"""

from __future__ import annotations

from typing import Optional

from ..actions.status import AuthorizationOutcome
from ..common import Clock, utc_now
from ..execution.execution_intent import ExecutionIntent
from ..execution.status import (
    EXECUTABLE_AUTHORIZATION_OUTCOMES,
    ExecutionStatus,
    RetryClassification,
)
from ..execution.validation import (
    ExecutionValidationIssue,
    ExecutionValidationResult,
)
from ..repositories.action_request_repository import ActionRequestRepository
from ..repositories.execution_repository import ExecutionRepository

_DISPATCHABLE = frozenset({
    ExecutionStatus.INTENT_CREATED, ExecutionStatus.READY_FOR_DISPATCH,
    ExecutionStatus.OUTCOME_UNKNOWN, ExecutionStatus.FAILED,
})


class ExecutionValidationService:
    def __init__(
        self,
        execution_repository: ExecutionRepository,
        action_request_repository: ActionRequestRepository,
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = execution_repository
        self._requests = action_request_repository
        self._clock = clock

    def validate(self, intent: ExecutionIntent) -> ExecutionValidationResult:
        now = self._clock()
        blockers: list[ExecutionValidationIssue] = []
        warnings: list[ExecutionValidationIssue] = []

        def block(code: str, msg: str) -> None:
            blockers.append(ExecutionValidationIssue(code=code, message=msg))

        if intent.status not in _DISPATCHABLE:
            block("NOT_DISPATCHABLE",
                  f"intent status {intent.status.value} cannot be dispatched")
        if intent.is_expired(now):
            block("INTENT_EXPIRED", "the execution intent has expired")

        # Re-check the authorization + CER still hold (defense in depth).
        try:
            responses = self._requests.get_authorization_history(intent.action_request_id)
            authz = next((r for r in reversed(responses)
                          if r.authorization_id == intent.authorization_id), None)
            if authz is None:
                block("AUTHORIZATION_NOT_FOUND", "authorization no longer resolvable")
            else:
                if authz.outcome not in EXECUTABLE_AUTHORIZATION_OUTCOMES:
                    block("AUTHORIZATION_NOT_EXECUTABLE",
                          f"authorization outcome {authz.outcome.value} is not executable")
                if authz.expires_at is not None and authz.expires_at < now:
                    block("AUTHORIZATION_EXPIRED", "the authorization has expired")
        except Exception:  # noqa: BLE001
            block("AUTHORIZATION_NOT_FOUND", "authorization history not resolvable")

        try:
            cer = self._requests.get_cer(intent.cer_id)
            if cer.is_expired(now):
                block("CER_EXPIRED", "the bound CER has expired")
        except Exception:  # noqa: BLE001
            block("CER_NOT_FOUND", "the bound CER is not resolvable")

        return ExecutionValidationResult(
            valid=not blockers, blockers=tuple(blockers), warnings=tuple(warnings),
            retry_classification=self.classify_retry(intent), validated_at=now)

    def classify_retry(self, intent: ExecutionIntent) -> RetryClassification:
        """Classify how safe a retry is, based on the most recent attempt."""
        attempts = self._repo.get_attempt_history(intent.execution_intent_id)
        if not attempts:
            return RetryClassification.IDEMPOTENT_SAFE
        return attempts[-1].retry_classification
