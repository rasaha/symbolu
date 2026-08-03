"""Determinism: identical inputs -> identical readouts and state. Stdlib, no randomness."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from _lab import basis  # noqa: E402
from src.binding_slots.slot_reference import SlotReference  # noqa: E402

D = 8


def _run_once():
    r = SlotReference(key_dim=D, value_dim=D, num_slots=8)
    keys = [basis(i % D, D) for i in range(20)]
    vals = [basis((i * 5) % D, D) for i in range(20)]
    return r.stream(keys, vals)


def test_repeated_runs_identical():
    (ro1, s1), (ro2, s2) = _run_once(), _run_once()
    assert ro1 == ro2
    assert s1.keys == s2.keys and s1.values == s2.values
    assert s1.version == s2.version and s1.source == s2.source
    assert s1.collisions == s2.collisions and s1.evictions == s2.evictions


def test_independent_instances_identical():
    a = SlotReference(key_dim=D, value_dim=D, num_slots=4)
    b = SlotReference(key_dim=D, value_dim=D, num_slots=4)
    sa, sb = a.init_state(), b.init_state()
    for i in range(10):
        k, v = basis(i % D, D), basis((i + 1) % D, D)
        sa = a.write(k, v, sa, source_id=i)
        sb = b.write(k, v, sb, source_id=i)
    assert sa.values == sb.values and sa.version == sb.version


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"determinism: {len(fns)} passed")


if __name__ == "__main__":
    _run()
