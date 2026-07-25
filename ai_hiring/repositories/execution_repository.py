"""Execution repository (port + in-memory adapter).

Append-only and immutable. Execution intents carry a version chain (lifecycle
projection); attempts, records, reconciliations, and compensation revisions are
immutable and append-only. Attempts (transport) are stored separately from
execution records (observed business outcomes). Idempotency-key and
external-request-id indexes are preserved for duplicate detection.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..executions.compensation import CompensationRequirement
from ..executions.execution_attempt import ExecutionAttempt
from ..executions.execution_intent import ExecutionIntent
from ..executions.execution_record import ExecutionRecord
from ..executions.reconciliation import ReconciliationResult
from ..executions.status import TERMINAL_EXECUTION_STATUSES
from ..errors import (
    CompensationNotFoundError,
    ExecutionAttemptNotFoundError,
    ExecutionIntentNotFoundError,
    VersionConflictError,
)


@runtime_checkable
class ExecutionRepository(Protocol):
    def create_execution_intent(self, intent: ExecutionIntent) -> ExecutionIntent: ...
    def save_execution_snapshot(self, intent: ExecutionIntent) -> ExecutionIntent: ...
    def get_execution_intent(self, intent_id: str) -> ExecutionIntent: ...
    def get_intent_history(self, intent_id: str) -> tuple[ExecutionIntent, ...]: ...
    def record_execution_attempt(self, attempt: ExecutionAttempt) -> ExecutionAttempt: ...
    def get_execution_attempt(self, attempt_id: str) -> ExecutionAttempt: ...
    def get_attempt_history(self, intent_id: str) -> tuple[ExecutionAttempt, ...]: ...
    def record_execution_record(self, record: ExecutionRecord) -> ExecutionRecord: ...
    def get_execution_records(self, intent_id: str) -> tuple[ExecutionRecord, ...]: ...
    def record_reconciliation_result(
        self, result: ReconciliationResult) -> ReconciliationResult: ...
    def get_reconciliation_history(
        self, intent_id: str) -> tuple[ReconciliationResult, ...]: ...
    def record_compensation_requirement(
        self, comp: CompensationRequirement) -> CompensationRequirement: ...
    def save_compensation_snapshot(
        self, comp: CompensationRequirement) -> CompensationRequirement: ...
    def get_compensation_history(
        self, intent_id: str) -> tuple[CompensationRequirement, ...]: ...
    def lookup_by_execution_idempotency_key(
        self, tenant_id: str, key: str) -> Optional[ExecutionIntent]: ...
    def lookup_by_external_request_id(
        self, external_request_id: str) -> tuple[ExecutionRecord, ...]: ...


class InMemoryExecutionRepository:
    def __init__(self) -> None:
        self._intents: dict[str, list[ExecutionIntent]] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._attempts: dict[str, ExecutionAttempt] = {}
        self._attempts_by_intent: dict[str, list[ExecutionAttempt]] = {}
        self._records: dict[str, ExecutionRecord] = {}
        self._records_by_intent: dict[str, list[ExecutionRecord]] = {}
        self._records_by_external: dict[str, list[ExecutionRecord]] = {}
        self._recons_by_intent: dict[str, list[ReconciliationResult]] = {}
        self._comps: dict[str, list[CompensationRequirement]] = {}  # id -> revisions
        self._comps_by_intent: dict[str, set[str]] = {}

    # --- intents ----------------------------------------------------------
    def create_execution_intent(self, intent: ExecutionIntent) -> ExecutionIntent:
        if intent.execution_intent_id in self._intents:
            raise VersionConflictError(
                f"execution intent '{intent.execution_intent_id}' already exists")
        self._intents[intent.execution_intent_id] = [intent]
        if intent.execution_idempotency_key:
            self._idempotency[(intent.tenant_id, intent.execution_idempotency_key)] = \
                intent.execution_intent_id
        return intent

    def save_execution_snapshot(self, intent: ExecutionIntent) -> ExecutionIntent:
        chain = self._intents.get(intent.execution_intent_id)
        if chain is None:
            raise ExecutionIntentNotFoundError(
                f"execution intent '{intent.execution_intent_id}' not found")
        chain.append(intent)
        return intent

    def get_execution_intent(self, intent_id: str) -> ExecutionIntent:
        chain = self._intents.get(intent_id)
        if not chain:
            raise ExecutionIntentNotFoundError(
                f"execution intent '{intent_id}' not found")
        return max(chain, key=lambda i: i.version)

    def get_intent_history(self, intent_id: str) -> tuple[ExecutionIntent, ...]:
        chain = self._intents.get(intent_id)
        if not chain:
            raise ExecutionIntentNotFoundError(
                f"execution intent '{intent_id}' not found")
        return tuple(sorted(chain, key=lambda i: i.version))

    def lookup_by_execution_idempotency_key(
        self, tenant_id: str, key: str) -> Optional[ExecutionIntent]:
        intent_id = self._idempotency.get((tenant_id, key))
        if intent_id is None:
            return None
        intent = self.get_execution_intent(intent_id)
        if intent.status in TERMINAL_EXECUTION_STATUSES:
            return None
        return intent

    # --- attempts ---------------------------------------------------------
    def record_execution_attempt(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        if attempt.execution_attempt_id in self._attempts:
            raise VersionConflictError(
                f"attempt '{attempt.execution_attempt_id}' already exists")
        self._attempts[attempt.execution_attempt_id] = attempt
        self._attempts_by_intent.setdefault(attempt.execution_intent_id, []).append(attempt)
        return attempt

    def get_execution_attempt(self, attempt_id: str) -> ExecutionAttempt:
        attempt = self._attempts.get(attempt_id)
        if attempt is None:
            raise ExecutionAttemptNotFoundError(f"attempt '{attempt_id}' not found")
        return attempt

    def get_attempt_history(self, intent_id: str) -> tuple[ExecutionAttempt, ...]:
        return tuple(sorted(self._attempts_by_intent.get(intent_id, ()),
                            key=lambda a: a.attempt_number))

    def attempt_count(self, intent_id: str) -> int:
        return len(self._attempts_by_intent.get(intent_id, ()))

    # --- records ----------------------------------------------------------
    def record_execution_record(self, record: ExecutionRecord) -> ExecutionRecord:
        if record.execution_record_id in self._records:
            raise VersionConflictError(
                f"execution record '{record.execution_record_id}' already exists")
        self._records[record.execution_record_id] = record
        self._records_by_intent.setdefault(record.execution_intent_id, []).append(record)
        if record.external_request_id:
            self._records_by_external.setdefault(
                record.external_request_id, []).append(record)
        return record

    def get_execution_records(self, intent_id: str) -> tuple[ExecutionRecord, ...]:
        return tuple(self._records_by_intent.get(intent_id, ()))

    def lookup_by_external_request_id(
        self, external_request_id: str) -> tuple[ExecutionRecord, ...]:
        return tuple(self._records_by_external.get(external_request_id, ()))

    # --- reconciliations --------------------------------------------------
    def record_reconciliation_result(
        self, result: ReconciliationResult) -> ReconciliationResult:
        self._recons_by_intent.setdefault(result.execution_intent_id, []).append(result)
        return result

    def get_reconciliation_history(
        self, intent_id: str) -> tuple[ReconciliationResult, ...]:
        return tuple(self._recons_by_intent.get(intent_id, ()))

    # --- compensation -----------------------------------------------------
    def record_compensation_requirement(
        self, comp: CompensationRequirement) -> CompensationRequirement:
        if comp.compensation_id in self._comps:
            raise VersionConflictError(
                f"compensation '{comp.compensation_id}' already exists")
        self._comps[comp.compensation_id] = [comp]
        self._comps_by_intent.setdefault(comp.execution_intent_id, set()).add(
            comp.compensation_id)
        return comp

    def save_compensation_snapshot(
        self, comp: CompensationRequirement) -> CompensationRequirement:
        revisions = self._comps.get(comp.compensation_id)
        if revisions is None:
            raise CompensationNotFoundError(
                f"compensation '{comp.compensation_id}' not found")
        revisions.append(comp)
        return comp

    def get_compensation(self, compensation_id: str) -> CompensationRequirement:
        revisions = self._comps.get(compensation_id)
        if not revisions:
            raise CompensationNotFoundError(
                f"compensation '{compensation_id}' not found")
        return max(revisions, key=lambda c: c.revision)

    def get_compensation_history(
        self, intent_id: str) -> tuple[CompensationRequirement, ...]:
        ids = self._comps_by_intent.get(intent_id, set())
        return tuple(sorted((self.get_compensation(cid) for cid in ids),
                            key=lambda c: c.created_at))
