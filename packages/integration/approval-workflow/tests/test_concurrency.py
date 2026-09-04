"""Exactly one consumption per approval under concurrency — threads on both
adapters, separate processes on SQLite.

Consumption is the only racing decision in the package. Every loser must report
``ALREADY_CONSUMED``, never a second ``CONSUMED_FIRST`` and never a silent success.
"""

from __future__ import annotations

import multiprocessing as mp
import threading

import pytest

from ugence_approval_workflow import (
    ApprovalState,
    ConsumptionResult,
    SqliteApprovalWorkflowStore,
)

from _fixtures import T2, directory, granted, memory_store, sqlite_path, sqlite_store

N = 12
CONSUMERS = tuple(f"decision_case:case_{i}/review_task:rev_{i}" for i in range(N))


def test_threads_on_a_shared_in_memory_store():
    store = memory_store()
    record = granted(store)
    barrier, results, lock = threading.Barrier(N), [], threading.Lock()

    def worker(consumer: str) -> None:
        barrier.wait()
        out = store.consume(record.approval_id, consumer_ref=consumer,
                            subject_digest=record.subject_digest, as_of=T2)
        with lock:
            results.append(out)

    threads = [threading.Thread(target=worker, args=(c,)) for c in CONSUMERS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(1 for o in results if o.is_consumed) == 1
    assert {o.result for o in results} <= {ConsumptionResult.CONSUMED_FIRST,
                                           ConsumptionResult.ALREADY_CONSUMED}
    assert store.get_approval(record.approval_id).state is ApprovalState.CONSUMED
    store.close()


def test_threads_each_with_their_own_sqlite_connection(tmp_path):
    path = sqlite_path(tmp_path)
    seed = sqlite_store(tmp_path)
    record = granted(seed)
    seed.close()
    barrier, results, lock = threading.Barrier(N), [], threading.Lock()

    def worker(consumer: str) -> None:
        store = SqliteApprovalWorkflowStore(path, directory())
        barrier.wait()
        out = store.consume(record.approval_id, consumer_ref=consumer,
                            subject_digest=record.subject_digest, as_of=T2)
        store.close()
        with lock:
            results.append(out)

    threads = [threading.Thread(target=worker, args=(c,)) for c in CONSUMERS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(1 for o in results if o.is_consumed) == 1
    assert {o.result for o in results} <= {ConsumptionResult.CONSUMED_FIRST,
                                           ConsumptionResult.ALREADY_CONSUMED}
    check = SqliteApprovalWorkflowStore(path, directory())
    assert check.verify_chain()
    assert check.get_approval(record.approval_id).state is ApprovalState.CONSUMED
    # One CONSUMED event, not twelve.
    consumed = [e for e in check.approval_events(record.approval_id)
                if e.event_type is ApprovalState.CONSUMED]
    assert len(consumed) == 1
    check.close()


def _process_worker(path, approval_id, digest, consumer, barrier, queue):
    store = SqliteApprovalWorkflowStore(path, directory())
    barrier.wait()
    out = store.consume(approval_id, consumer_ref=consumer, subject_digest=digest, as_of=T2)
    store.close()
    queue.put((out.result.value, out.consumption_id, out.holder))


@pytest.mark.skipif("fork" not in mp.get_all_start_methods(), reason="fork start method required")
def test_processes_each_with_their_own_connection(tmp_path):
    path = sqlite_path(tmp_path)
    seed = sqlite_store(tmp_path)
    record = granted(seed)
    seed.close()

    ctx = mp.get_context("fork")
    barrier, queue = ctx.Barrier(N), ctx.Queue()
    procs = [ctx.Process(target=_process_worker,
                         args=(path, record.approval_id, record.subject_digest, c, barrier, queue))
             for c in CONSUMERS]
    for p in procs:
        p.start()
    results = [queue.get(timeout=60) for _ in range(N)]
    for p in procs:
        p.join(timeout=60)

    assert all(p.exitcode == 0 for p in procs)
    assert sum(1 for r, _, _ in results if r == "CONSUMED_FIRST") == 1
    assert {r for r, _, _ in results} <= {"CONSUMED_FIRST", "ALREADY_CONSUMED"}
    winner = next(cid for r, cid, _ in results if r == "CONSUMED_FIRST")
    assert {holder for r, _, holder in results if r == "ALREADY_CONSUMED"} == {winner}

    check = SqliteApprovalWorkflowStore(path, directory())
    assert check.verify_chain()
    assert check.get_approval(record.approval_id).state is ApprovalState.CONSUMED
    check.close()
