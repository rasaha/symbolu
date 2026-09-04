"""Exactly one ACQUIRED under concurrency — threads on both adapters, processes on SQLite."""

from __future__ import annotations

import multiprocessing as mp
import threading

import pytest

from ugence_execution_reservation import (
    InMemoryExecutionReservationStore,
    ReservationResult,
    SqliteExecutionReservationStore,
)

from _fixtures import ACTFP, AUTHZ, T0, clear_result, key, receipt_for, sqlite_path

N = 12


def _reserve(store):
    return store.reserve_once(key(), receipt_for(clear_result()).receipt_id, AUTHZ, ACTFP, 300, as_of=T0)


def test_threads_on_a_shared_in_memory_store():
    store = InMemoryExecutionReservationStore()
    store.put_receipt(receipt_for(clear_result()))
    barrier, results = threading.Barrier(N), []
    lock = threading.Lock()

    def worker():
        barrier.wait()
        out = _reserve(store)
        with lock:
            results.append(out)

    threads = [threading.Thread(target=worker) for _ in range(N)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert sum(1 for o in results if o.result is ReservationResult.ACQUIRED) == 1
    assert all(o.result in (ReservationResult.ACQUIRED, ReservationResult.ALREADY_RESERVED) for o in results)
    assert len({o.reservation.reservation_id for o in results}) == 1


def test_threads_each_with_their_own_sqlite_connection(tmp_path):
    path = sqlite_path(tmp_path)
    seed = SqliteExecutionReservationStore(path)
    seed.put_receipt(receipt_for(clear_result()))
    seed.close()
    barrier, results, lock = threading.Barrier(N), [], threading.Lock()

    def worker():
        store = SqliteExecutionReservationStore(path)
        barrier.wait()
        out = _reserve(store)
        store.close()
        with lock:
            results.append(out)

    threads = [threading.Thread(target=worker) for _ in range(N)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert sum(1 for o in results if o.result is ReservationResult.ACQUIRED) == 1
    assert all(o.result in (ReservationResult.ACQUIRED, ReservationResult.ALREADY_RESERVED) for o in results)
    check = SqliteExecutionReservationStore(path)
    assert check.verify_chain() and check.get_head(key()) is not None
    assert len(check.reservation_events(check.get_head(key()).reservation_id)) == 1
    check.close()


def _process_worker(path, barrier, queue):
    store = SqliteExecutionReservationStore(path)
    barrier.wait()
    out = _reserve(store)
    store.close()
    queue.put((out.result.value, out.reservation.reservation_id if out.reservation else None))


@pytest.mark.skipif("fork" not in mp.get_all_start_methods(), reason="fork start method required")
def test_processes_each_with_their_own_connection(tmp_path):
    path = sqlite_path(tmp_path)
    seed = SqliteExecutionReservationStore(path)
    seed.put_receipt(receipt_for(clear_result()))
    seed.close()
    ctx = mp.get_context("fork")
    barrier, queue = ctx.Barrier(N), ctx.Queue()
    procs = [ctx.Process(target=_process_worker, args=(path, barrier, queue)) for _ in range(N)]
    for p in procs: p.start()
    results = [queue.get(timeout=60) for _ in range(N)]
    for p in procs: p.join(timeout=60)
    assert all(p.exitcode == 0 for p in procs)
    assert sum(1 for r, _ in results if r == "ACQUIRED") == 1
    assert {r for r, _ in results} <= {"ACQUIRED", "ALREADY_RESERVED"}
    assert len({rid for _, rid in results}) == 1
    check = SqliteExecutionReservationStore(path)
    assert check.verify_chain()
    check.close()
