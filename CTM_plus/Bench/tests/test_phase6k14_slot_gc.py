#!/usr/bin/env python3
# Phase 6K.14 — CPU regression for the slot lifecycle fix.
#
# Validates the bookkeeping that closes the Phase 6K.13 "PagedKVWriter slot
# pool exhausted" leak:
#   * evict-on-completion: gc_completed_slots() frees the slots of sequences
#     that dropped out of the running set, so the pool survives decode waves /
#     many completed requests instead of leaking one slot per distinct seq_id.
#   * auto-bump precedence: $PHASE6_MAX_ACTIVE_SLOTS pins the cap; otherwise
#     auto-bump (best-effort to vLLM max_num_seqs) applies; otherwise default 8.
#
# Torch-free by design — it exercises the REAL PagedKVWriter.gc_completed_slots
# and .evict_sequence (which are pure-Python when the device counter pools are
# absent) against a realistic _slot_map / _free_slots, so it runs on any box
# (the GPU pod runs the full write/read path; this guards the lifecycle logic).
#
# Run:  python CTM_plus/Bench/tests/test_phase6k14_slot_gc.py
#       (also pytest-collectable: pytest CTM_plus/Bench/tests/test_phase6k14_slot_gc.py)

import os
import sys
from pathlib import Path

# Make kv_policy importable whether run from repo root or this dir.
_KVP = Path(__file__).resolve().parents[2] / "KVPolicy"
if str(_KVP) not in sys.path:
    sys.path.insert(0, str(_KVP))

import kv_policy.phase5b_4c_paged_writer as m  # noqa: E402

W = m.PagedKVWriter


def _fresh(cap):
    """A torch-free PagedKVWriter shell: real lifecycle attributes, no device
    pools. With _seq_pos_pool=None the real evict_sequence skips its only
    torch branch, so gc_completed_slots/evict_sequence run pure-Python."""
    w = W.__new__(W)            # bypass __init__ (which requires torch)
    w._seq_states = {}
    w._slot_map = {}
    w._free_slots = list(range(cap))
    w._max_active_slots = cap
    w._allocated = True
    w._seq_pos_pool = None
    return w


def _ensure(w, sid):
    """Mimic ensure_seq_state's slot bookkeeping WITHOUT building a torch-
    backed SeqState. Raises like the real method when the pool is empty."""
    if sid in w._slot_map:
        return
    if not w._free_slots:
        raise RuntimeError("PagedKVWriter slot pool exhausted")
    slot = w._free_slots.pop(0)
    w._slot_map[sid] = slot
    w._seq_states[sid] = slot   # placeholder; real code stores a SeqState


# ----------------------------------------------------------------------


def test_leaked_seq_ids_pure():
    assert m._leaked_seq_ids([1, 2, 3, 4], {2, 4}) == [1, 3]
    assert m._leaked_seq_ids([1, 2, 3], [1, 2, 3]) == []
    assert m._leaked_seq_ids([], {1, 2}) == []
    assert m._leaked_seq_ids([5, 6, 7], set()) == [5, 6, 7]
    assert m._leaked_seq_ids([3, 1, 2], [2]) == [3, 1]   # order-preserving


def test_gc_frees_completed_slots():
    w = _fresh(cap=4)
    for sid in (1, 2, 3, 4):
        _ensure(w, sid)
    assert w._free_slots == []                  # pool full
    # Decode batch now only {1, 3}; 2 and 4 finished.
    freed = w.gc_completed_slots({1, 3})
    assert freed == 2
    assert set(w._slot_map) == {1, 3}
    assert len(w._free_slots) == 2
    # Idempotent: same active set frees nothing more.
    assert w.gc_completed_slots({1, 3}) == 0


def test_wave_leak_repro_and_fix():
    """The 6K.13 scenario: cap=8, three waves of 8 distinct seq_ids each
    (24 total) — e.g. vLLM running B=24 prompts in waves under a KV budget
    that fits ~8 concurrently."""
    # Pre-fix behavior (no GC between waves) -> exhaustion in wave 2.
    w = _fresh(cap=8)
    for sid in range(8):                          # wave 0 fills the pool
        _ensure(w, sid)
    raised = False
    try:
        for sid in range(8, 16):                  # wave 1: 8 NEW seq_ids
            _ensure(w, sid)
    except RuntimeError as exc:
        raised = "exhausted" in str(exc)
    assert raised, "expected slot pool exhaustion without GC"

    # With GC between waves -> never exhausts; pool recycles cleanly.
    w = _fresh(cap=8)
    completed = 0
    for wave in range(3):
        wave_ids = set(range(wave * 8, wave * 8 + 8))
        # Previous wave finished -> only this wave is "running".
        w.gc_completed_slots(wave_ids)
        for sid in wave_ids:
            _ensure(w, sid)                        # must NOT raise
        completed += len(wave_ids)
    assert completed == 24
    # Steady state: exactly the last wave holds slots.
    assert set(w._slot_map) == set(range(16, 24))
    assert len(w._free_slots) == 0                 # last wave is full at cap=8


def test_evict_disabled_toggle_reproduces_leak():
    os.environ["PHASE6K14_EVICT_ON_DECODE"] = "0"
    try:
        w = _fresh(cap=4)
        for sid in (1, 2, 3, 4):
            _ensure(w, sid)
        # GC is a no-op when disabled -> the leak persists (pre-fix behavior).
        assert w.gc_completed_slots({1}) == 0
        assert set(w._slot_map) == {1, 2, 3, 4}
        assert w._free_slots == []
    finally:
        os.environ.pop("PHASE6K14_EVICT_ON_DECODE", None)


def test_autobump_precedence():
    saved = {k: os.environ.get(k) for k in
             ("PHASE6_MAX_ACTIVE_SLOTS", "PHASE6K14_AUTOBUMP_SLOTS")}
    try:
        for k in saved:
            os.environ.pop(k, None)
        # No env, no vLLM on this box -> legacy default.
        assert m._vllm_max_num_seqs() is None
        assert m._max_active_slots() == 8
        # Explicit env wins and clamps to >= 1.
        os.environ["PHASE6_MAX_ACTIVE_SLOTS"] = "128"
        assert m._max_active_slots() == 128
        os.environ["PHASE6_MAX_ACTIVE_SLOTS"] = "0"
        assert m._max_active_slots() == 1
        os.environ["PHASE6_MAX_ACTIVE_SLOTS"] = "nope"
        assert m._max_active_slots() == 8          # bad value -> default
        os.environ.pop("PHASE6_MAX_ACTIVE_SLOTS")
        # Auto-bump explicitly disabled -> still default (no vLLM here).
        os.environ["PHASE6K14_AUTOBUMP_SLOTS"] = "0"
        assert m._autobump_slots_enabled() is False
        assert m._max_active_slots() == 8
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'} "
          f"({len(tests) - failed}/{len(tests)})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
