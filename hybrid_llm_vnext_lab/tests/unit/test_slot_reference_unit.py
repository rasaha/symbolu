"""Unit tests for the stdlib SlotReference — deterministic, no torch/numpy/pytest."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from _lab import argmax, basis  # noqa: E402
from src.binding_slots.slot_reference import SlotReference, SlotState  # noqa: E402

D = 8


def _r(num_slots=8, top_k=4, match_threshold=0.5, gate=1.0):
    return SlotReference(key_dim=D, value_dim=D, num_slots=num_slots,
                         top_k=top_k, match_threshold=match_threshold, write_gate=gate)


def test_deterministic_initialization():
    r = _r()
    s1, s2 = r.init_state(), r.init_state()
    assert s1.keys == s2.keys and s1.values == s2.values
    assert s1.active == s2.active == [False] * 8
    assert s1.version == [0] * 8 and s1.source == [-1] * 8


def test_state_creation_shape():
    r = _r(num_slots=5)
    s = r.init_state()
    assert len(s.keys) == 5 and len(s.keys[0]) == D
    assert len(s.values) == 5 and len(s.values[0]) == D
    assert len(s.source) == len(s.version) == len(s.usage) == len(s.active) == 5


def test_bounded_state_size_constant():
    r = _r(num_slots=8)
    s = r.init_state()
    n0 = s.numel()
    for i in range(50):  # far more writes than slots
        s = r.write(basis(i % D, D), basis((i + 1) % D, D), s, source_id=i)
    assert s.numel() == n0  # bounded: writing 50 tokens never grows the state
    assert s.n_active() <= 8


def test_write_gate_limits_and_finite():
    r = _r(gate=0.3)
    s = r.init_state()
    s = r.write(basis(0, D), basis(2, D), s, source_id=1)
    ro, _ = r.read(basis(0, D), s)
    assert all(abs(x) < 1e6 for x in ro)  # finite
    # cosine addressing is scale-invariant: gentle gate still retrieves the right value dir
    assert argmax(ro) == 2


def test_empty_state_read():
    r = _r()
    ro, idx = r.read(basis(0, D), r.init_state())
    assert ro == [0.0] * D and idx == -1  # no active slots -> zero readout


def test_one_slot():
    r = _r(num_slots=1, top_k=1)
    s = r.init_state()
    s = r.write(basis(0, D), basis(4, D), s)
    ro, idx = r.read(basis(0, D), s)
    assert idx == 0 and argmax(ro) == 4


def test_multiple_slots_distinct_facts():
    r = _r(num_slots=8)
    s = r.init_state()
    facts = {0: 1, 2: 3, 4: 5, 6: 7}
    for k, v in facts.items():
        s = r.write(basis(k, D), basis(v, D), s, source_id=k)
    for k, v in facts.items():
        ro, _ = r.read(basis(k, D), s)
        assert argmax(ro) == v, f"entity {k} should retrieve value {v}"


def test_repeated_key_supersedes():
    r = _r()
    s = r.init_state()
    s = r.write(basis(0, D), basis(1, D), s, source_id=10)
    active_after_first = s.n_active()
    s = r.write(basis(0, D), basis(6, D), s, source_id=20)  # same key, new value
    ro, _ = r.read(basis(0, D), s)
    assert argmax(ro) == 6                       # new value wins
    assert s.n_active() == active_after_first    # supersede in place, not a new slot
    assert s.version[0] == 2                      # version bumped
    assert s.source[0] == 20                      # source updated
    assert s.collisions == 1


def test_conflicting_values_last_write_wins_per_key():
    r = _r()
    s = r.init_state()
    for v in (1, 2, 3, 7):
        s = r.write(basis(0, D), basis(v, D), s)
    ro, _ = r.read(basis(0, D), s)
    assert argmax(ro) == 7 and s.version[0] == 4


def test_full_capacity_then_evict():
    r = _r(num_slots=4)
    s = r.init_state()
    for k in range(4):
        s = r.write(basis(k, D), basis(k, D), s)
    assert s.n_active() == 4
    s = r.write(basis(5, D), basis(5, D), s)  # 5th distinct key -> eviction
    assert s.n_active() == 4 and s.evictions >= 1
    ro, _ = r.read(basis(5, D), s)
    assert argmax(ro) == 5  # newest retained


def test_reset_between_sequences():
    r = _r()
    s = r.init_state()
    s = r.write(basis(0, D), basis(1, D), s)
    s2 = r.init_state()  # explicit reset
    assert s2.n_active() == 0 and s2.version == [0] * 8


def test_repeated_key_chunk_vs_token_equivalence():
    # process the same writes as one stream vs token-by-token -> identical final state
    r = _r()
    keys = [basis(i % D, D) for i in range(6)]
    vals = [basis((i * 2) % D, D) for i in range(6)]
    _, s_stream = r.stream(keys, vals)
    s_tok = r.init_state()
    for k, v in zip(keys, vals):
        ro, _ = r.read(k, s_tok)  # read-then-write mirrors stream()
        s_tok = r.write(k, v, s_tok, source_id=s_tok.position)
    assert s_stream.values == s_tok.values and s_stream.version == s_tok.version


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"unit: {len(fns)} passed")


if __name__ == "__main__":
    _run()
