"""F4 — InMemoryTokenAccountingSink is safe for concurrent use.

Deterministic barrier-synchronized threads (no sleep-based timing). Atomic duplicate
detection + insertion: unique inserts never lost, identical replays idempotent, conflicting
duplicates rejected, and snapshots never observe partial state.
"""

from __future__ import annotations

import threading

import pytest

from ugence_context_minimization.api import (
    AttemptStatus,
    InMemoryTokenAccountingSink,
    ProviderTokenUsage,
    prepare_api_call_measurement,
    reconcile_api_call_measurement,
)
from ugence_context_minimization.errors import InvalidRequestError

from support_accounting import sample_minimization_result


def _prep():
    return prepare_api_call_measurement(
        minimization_result=sample_minimization_result(), logical_request_id="lr", provider_id="prov"
    )


def _record(prep, aid, n):
    # Build the record WITHOUT a sink so we can hand identical objects to many threads.
    return reconcile_api_call_measurement(
        prep, attempt_id=aid, attempt_number=n, status=AttemptStatus.SUCCEEDED,
        provider_usage=ProviderTokenUsage(input_tokens=n, output_tokens=1),
    )


def _run_barrier(fns):
    """Run each callable in its own thread, released simultaneously by a barrier."""
    barrier = threading.Barrier(len(fns))
    errors = []

    def _wrap(fn):
        def inner():
            barrier.wait()
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 - collected for assertions
                errors.append(exc)
        return inner

    threads = [threading.Thread(target=_wrap(fn)) for fn in fns]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_concurrent_unique_inserts_all_land():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    n = 64
    recs = [_record(prep, f"a{i}", i + 1) for i in range(n)]
    errors = _run_barrier([lambda r=r: sink.record(r) for r in recs])
    assert errors == []
    assert len(sink.records) == n  # no lost inserts
    assert len({r.attempt_id for r in sink.records}) == n


def test_concurrent_identical_duplicates_are_idempotent():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    rec = _record(prep, "a1", 1)
    errors = _run_barrier([lambda: sink.record(rec) for _ in range(32)])
    assert errors == []
    assert len(sink.records) == 1  # exactly one stored despite 32 concurrent writers


def test_concurrent_conflicting_duplicates_are_rejected():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    good = _record(prep, "a1", 1)
    # A different record under the SAME attempt_id (conflicting content).
    conflicting = reconcile_api_call_measurement(
        prep, attempt_id="a1", attempt_number=1, status=AttemptStatus.FAILED,
    )
    errors = _run_barrier(
        [lambda: sink.record(good)] * 8 + [lambda: sink.record(conflicting)] * 8
    )
    # Atomicity: exactly ONE record is stored (whichever fingerprint won the race), and
    # every writer carrying the OTHER fingerprint is rejected — never a silent overwrite or
    # a second insert.
    assert len(sink.records) == 1
    stored = sink.records[0]
    assert stored.record_fingerprint in {good.record_fingerprint, conflicting.record_fingerprint}
    losing_fp = (
        conflicting.record_fingerprint
        if stored.record_fingerprint == good.record_fingerprint
        else good.record_fingerprint
    )
    # All 8 writers of the losing fingerprint were rejected (conflicting content).
    assert sum(isinstance(e, InvalidRequestError) for e in errors) == 8
    assert stored.record_fingerprint != losing_fp


def test_snapshot_never_partial_during_concurrent_writes():
    prep = _prep()
    sink = InMemoryTokenAccountingSink()
    recs = [_record(prep, f"a{i}", i + 1) for i in range(50)]
    observed_counts = []

    def writer(r):
        sink.record(r)

    def reader():
        # Reading concurrently must always yield a consistent tuple (no exception, no
        # partially-built record).
        observed_counts.append(len(sink.records))

    fns = [lambda r=r: writer(r) for r in recs] + [reader for _ in range(20)]
    errors = _run_barrier(fns)
    assert errors == []
    assert len(sink.records) == 50
    assert all(0 <= c <= 50 for c in observed_counts)
