"""Behavioral algorithmic probes for the bounded slot mechanics — stdlib, deterministic.

These mirror the phase_lc task families (single-fact, multi-fact, supersession/stale
suppression, source attribution, distractor resistance, capacity/eviction, long delay,
reset, chunk-boundary) at the MECHANISM level, controlling addressing directly. They test
what the slot LOGIC guarantees; whether SGD learns the projections that realize it is the
separate, RESOURCE_BLOCKED neural reproduction.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from _lab import argmax, basis  # noqa: E402
from src.binding_slots.slot_reference import SlotReference  # noqa: E402
from src.local_baseline.window_reference import LocalWindowReference  # noqa: E402

D = 12


def _r(num_slots=8, top_k=4, match_threshold=0.5):
    return SlotReference(key_dim=D, value_dim=D, num_slots=num_slots,
                         top_k=top_k, match_threshold=match_threshold)


def test_single_fact_beyond_window():
    """Slots retrieve a fact written far earlier — the capability the local window lacks."""
    r = _r()
    s = r.init_state()
    s = r.write(basis(0, D), basis(9, D), s, source_id=1)  # the needle, early
    for _ in range(100):  # long filler gap
        s = r.write(basis(1, D), basis(1, D), s, source_id=0)  # repeated distractor key
    ro, _ = r.read(basis(0, D), s)
    assert argmax(ro) == 9  # needle still retrievable after 100 filler tokens


def test_local_window_cannot_bridge_gap():
    """Contrast: the O(N*W) local baseline has no memory beyond W, so it cannot carry a
    fact across a gap larger than the window — motivating the slot subsystem."""
    win = LocalWindowReference(window=4)
    seq = [basis(9, D)] + [basis(1, D)] * 20  # needle then 20 filler
    out = win.forward(seq)
    # the last position's windowed mean contains no trace of the needle at position 0
    assert argmax(out[-1]) != 9


def test_multi_fact_retrieval():
    r = _r(num_slots=8)
    s = r.init_state()
    facts = {0: 2, 3: 5, 6: 8, 9: 11}
    for k, v in facts.items():
        s = r.write(basis(k, D), basis(v, D), s, source_id=k)
    for k, v in facts.items():
        assert argmax(r.read(basis(k, D), s)[0]) == v


def test_supersession_stale_suppression():
    r = _r()
    s = r.init_state()
    s = r.write(basis(0, D), basis(4, D), s, source_id=1)   # old value
    s = r.write(basis(0, D), basis(7, D), s, source_id=2)   # amendment
    ro, _ = r.read(basis(0, D), s)
    assert argmax(ro) == 7          # current value
    assert argmax(ro) != 4          # stale value suppressed
    assert s.version[0] == 2


def test_source_attribution():
    r = _r()
    s = r.init_state()
    s = r.write(basis(0, D), basis(3, D), s, source_id=42)
    s = r.write(basis(5, D), basis(6, D), s, source_id=99)
    # metadata retains which source supplied each binding
    assert s.source[0] == 42 and s.source[1] == 99


def test_conflicting_sources_latest_wins():
    r = _r()
    s = r.init_state()
    s = r.write(basis(0, D), basis(3, D), s, source_id=42)
    s = r.write(basis(0, D), basis(3, D), s, source_id=77)  # same fact, new source
    assert s.source[0] == 77 and s.version[0] == 2


def test_distractor_resistance():
    r = _r(num_slots=16)
    s = r.init_state()
    s = r.write(basis(0, D), basis(10, D), s)              # target
    for k in range(1, 11):                                  # 10 distinct distractors
        s = r.write(basis(k % D, D), basis(k % D, D), s)
    ro, _ = r.read(basis(0, D), s)
    assert argmax(ro) == 10


def test_collision_single_slot_version_grows():
    r = _r()
    s = r.init_state()
    for i in range(5):
        s = r.write(basis(0, D), basis((i + 1) % D, D), s)
    assert s.n_active() == 1 and s.version[0] == 5 and s.collisions == 4


def test_more_facts_than_slots_evicts_oldest():
    r = _r(num_slots=3)
    s = r.init_state()
    order = [0, 1, 2, 4, 5]  # 5 distinct keys, only 3 slots
    for k in order:
        s = r.write(basis(k, D), basis(k, D), s)
    assert s.n_active() == 3 and s.evictions == 2
    # the two most-recently-written survive; the earliest are evicted
    assert argmax(r.read(basis(5, D), s)[0]) == 5
    assert argmax(r.read(basis(4, D), s)[0]) == 4


def test_long_delay_between_write_and_read():
    r = _r()
    s = r.init_state()
    s = r.write(basis(2, D), basis(8, D), s)
    for _ in range(500):
        s = r.write(basis(2, D), basis(8, D), s)  # same fact refreshed (bounded state)
    assert argmax(r.read(basis(2, D), s)[0]) == 8


def test_reset_clears_memory():
    r = _r()
    s = r.init_state()
    s = r.write(basis(0, D), basis(1, D), s)
    s = r.init_state()
    assert s.n_active() == 0
    ro, idx = r.read(basis(0, D), s)
    assert idx == -1  # nothing retrievable after reset


def test_chunk_boundary_retention():
    """Streaming a sequence in two halves (carrying state) == streaming it whole."""
    r = _r()
    keys = [basis(i % D, D) for i in range(10)]
    vals = [basis((i + 2) % D, D) for i in range(10)]
    _, whole = r.stream(keys, vals)

    # two-chunk streaming carrying state across the boundary
    s = r.init_state()
    for k, v in zip(keys[:5], vals[:5]):
        r.read(k, s)
        s = r.write(k, v, s, source_id=s.position)
    for k, v in zip(keys[5:], vals[5:]):
        r.read(k, s)
        s = r.write(k, v, s, source_id=s.position)
    assert s.values == whole.values and s.version == whole.version


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"behavioral: {len(fns)} passed")


if __name__ == "__main__":
    _run()
