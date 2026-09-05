"""Decision Authority ``ExecutionRepository`` conformance — proved behaviourally.

The kernel's conformance kit checks that a platform's repositories are kernel
*types* by module, which a foreign adapter cannot satisfy by construction. So the
proof here is parity: the same operation sequence against the kernel's own
``InMemoryExecutionRepository`` and against both adapters yields identical values
and identical exceptions, and every adapter satisfies the runtime-checkable
protocol.
"""

from __future__ import annotations

import pytest

from ugence_decision_authority.errors import (
    CompensationNotFoundError,
    ExecutionAttemptNotFoundError,
    ExecutionIntentNotFoundError,
    VersionConflictError,
)
from ugence_decision_authority.execution.compensation import CompensationRequirement
from ugence_decision_authority.execution.execution_attempt import ExecutionAttempt
from ugence_decision_authority.execution.execution_intent import ExecutionIntent
from ugence_decision_authority.execution.execution_record import ExecutionRecord
from ugence_decision_authority.execution.reconciliation import ReconciliationResult
from ugence_decision_authority.execution.status import (
    BusinessOutcome,
    ExecutionStatus,
    ReconciliationStatus,
    TransportStatus,
)
from ugence_decision_authority.repositories.execution_repository import (
    ExecutionRepository,
    InMemoryExecutionRepository,
)

from _fixtures import STORE_KINDS, T0, key, make_store, ts

KEY = key().serialized


def intent(iid="int-1", **kw):
    base = dict(execution_intent_id=iid, tenant_id="acme", action_request_id="ar-1",
                action_request_version=1, authorization_id="authz-ref-1", cer_id="cer-1",
                action_type="merge", target_system="github", created_by="svc",
                execution_idempotency_key=KEY, created_at=T0)
    base.update(kw)
    return ExecutionIntent(**base)


def attempt(aid="att-1", n=1):
    return ExecutionAttempt(execution_attempt_id=aid, execution_intent_id="int-1", attempt_number=n,
                            adapter_id="adapter", adapter_version="1", request_payload_hash="h",
                            dispatched_at=ts(seconds=n), transport_status=TransportStatus.DISPATCHED,
                            external_request_id=f"ext-{n}")


def record(rid="rec-1", ext="ext-1"):
    return ExecutionRecord(execution_record_id=rid, execution_intent_id="int-1", execution_attempt_id="att-1",
                           tenant_id="acme", external_system="github", external_request_id=ext,
                           business_outcome=BusinessOutcome.SUCCEEDED, observed_at=ts(seconds=5))


def recon(rid="recon-1"):
    return ReconciliationResult(reconciliation_id=rid, execution_intent_id="int-1", tenant_id="acme",
                                execution_record_ids=("rec-1",), expected_action_type="merge",
                                expected_target_system="github", observed_outcome=BusinessOutcome.SUCCEEDED,
                                status=ReconciliationStatus.RECONCILED, reconciled_at=ts(seconds=6))


def comp(cid="comp-1", **kw):
    base = dict(compensation_id=cid, execution_intent_id="int-1", reconciliation_id="recon-1",
                tenant_id="acme", reason_codes=("MISMATCH",), created_at=ts(seconds=7))
    base.update(kw)
    return CompensationRequirement(**base)


def _script(repo):
    """One operation sequence; returns a list of outcomes (values or exception class names)."""

    log = []

    def step(fn):
        try:
            log.append(fn())
        except Exception as exc:  # noqa: BLE001 — parity of exception *classes* is the point
            log.append(type(exc).__name__)

    step(lambda: repo.create_execution_intent(intent()))
    step(lambda: repo.create_execution_intent(intent()))                      # VersionConflictError
    step(lambda: repo.get_execution_intent("int-1").version)
    step(lambda: repo.get_execution_intent("nope"))                           # not found
    step(lambda: repo.save_execution_snapshot(intent("nope")))                # not found
    step(lambda: repo.lookup_by_execution_idempotency_key("acme", KEY).execution_intent_id)
    step(lambda: repo.lookup_by_execution_idempotency_key("other", KEY))     # None
    step(lambda: repo.save_execution_snapshot(
        repo.get_execution_intent("int-1").evolve(intent_version_id="v2", status=ExecutionStatus.DISPATCHED)).version)
    step(lambda: [i.version for i in repo.get_intent_history("int-1")])
    step(lambda: repo.record_execution_attempt(attempt()).execution_attempt_id)
    step(lambda: repo.record_execution_attempt(attempt()))                    # dup
    step(lambda: repo.record_execution_attempt(attempt("att-2", 2)).attempt_number)
    step(lambda: [a.attempt_number for a in repo.get_attempt_history("int-1")])
    step(lambda: repo.get_execution_attempt("att-x"))                         # not found
    step(lambda: repo.attempt_count("int-1"))
    step(lambda: repo.record_execution_record(record()).execution_record_id)
    step(lambda: repo.record_execution_record(record()))                      # dup
    step(lambda: repo.record_execution_record(record("rec-2", "ext-1")).execution_record_id)
    step(lambda: [r.execution_record_id for r in repo.get_execution_records("int-1")])
    step(lambda: [r.execution_record_id for r in repo.lookup_by_external_request_id("ext-1")])
    step(lambda: repo.lookup_by_external_request_id("ext-none"))
    step(lambda: repo.record_reconciliation_result(recon()).reconciliation_id)
    step(lambda: repo.record_reconciliation_result(recon()).reconciliation_id)  # appends, no dup check
    step(lambda: len(repo.get_reconciliation_history("int-1")))
    step(lambda: repo.record_compensation_requirement(comp()).compensation_id)
    step(lambda: repo.record_compensation_requirement(comp()))                # dup
    step(lambda: repo.save_compensation_snapshot(comp("comp-x")))             # not found
    step(lambda: repo.save_compensation_snapshot(comp(revision=2)).revision)
    step(lambda: repo.get_compensation("comp-1").revision)
    step(lambda: [c.revision for c in repo.get_compensation_history("int-1")])
    step(lambda: repo.save_execution_snapshot(
        repo.get_execution_intent("int-1").evolve(intent_version_id="v3", status=ExecutionStatus.CANCELLED)).status)
    step(lambda: repo.lookup_by_execution_idempotency_key("acme", KEY))      # terminal → None
    step(lambda: repo.get_execution_intent("int-1") == repo.get_intent_history("int-1")[-1])
    return log


@pytest.mark.parametrize("kind", STORE_KINDS)
def test_parity_with_the_kernel_reference_repository(kind, tmp_path):
    reference = _script(InMemoryExecutionRepository())
    adapter = make_store(kind, tmp_path)
    try:
        assert _script(adapter) == reference
    finally:
        adapter.close()
    assert "VersionConflictError" in reference and "ExecutionIntentNotFoundError" in reference
    assert "ExecutionAttemptNotFoundError" in reference and "CompensationNotFoundError" in reference
    assert VersionConflictError and ExecutionIntentNotFoundError and ExecutionAttemptNotFoundError and CompensationNotFoundError


@pytest.mark.parametrize("kind", STORE_KINDS)
def test_adapters_satisfy_the_frozen_protocol_structurally(kind, tmp_path):
    adapter = make_store(kind, tmp_path)
    try:
        assert isinstance(adapter, ExecutionRepository)
        for name in ("create_execution_intent", "save_execution_snapshot", "get_execution_intent",
                     "get_intent_history", "record_execution_attempt", "get_execution_attempt",
                     "get_attempt_history", "record_execution_record", "get_execution_records",
                     "record_reconciliation_result", "get_reconciliation_history",
                     "record_compensation_requirement", "save_compensation_snapshot",
                     "get_compensation_history", "lookup_by_execution_idempotency_key",
                     "lookup_by_external_request_id"):
            assert callable(getattr(adapter, name)), name
    finally:
        adapter.close()


def test_sqlite_records_survive_reopen(tmp_path):
    from _fixtures import sqlite_path
    from ugence_execution_reservation import SqliteExecutionReservationStore
    path = sqlite_path(tmp_path)
    s = SqliteExecutionReservationStore(path)
    s.create_execution_intent(intent()); s.record_execution_attempt(attempt()); s.close()
    s = SqliteExecutionReservationStore(path)
    assert s.get_execution_intent("int-1") == intent()
    assert s.get_execution_attempt("att-1") == attempt()
    s.close()
