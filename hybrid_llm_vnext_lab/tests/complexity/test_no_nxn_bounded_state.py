"""Complexity/structural guarantees for the stdlib SlotReference — no torch/pytest.

Proves the three claims the audit flagged as load-bearing:
  * no [N, N] sequence-score tensor is built (declarative shape audit),
  * recurrent state size is independent of N (INV-STATE-O),
  * decode does not replay the full prefix (single-step == streamed).
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from _lab import basis  # noqa: E402
from src.binding_slots.slot_reference import SlotReference  # noqa: E402
from src.instrumentation.invariants import InvariantViolation, shape_audit  # noqa: E402
from src.instrumentation.probes import measure_state_growth  # noqa: E402

D = 8


def _r(num_slots=8):
    return SlotReference(key_dim=D, value_dim=D, num_slots=num_slots)


def _stream_len(n):
    r = _r()
    keys = [basis(i % D, D) for i in range(n)]
    vals = [basis((i + 1) % D, D) for i in range(n)]
    _, state = r.stream(keys, vals)
    return state


def test_no_nxn_declarative_audit():
    """Every registered score tensor has 0 sequence axes and size M (not N or N*N)."""
    r = _r(num_slots=8)
    n = 64
    keys = [basis(i % D, D) for i in range(n)]
    vals = [basis((i + 1) % D, D) for i in range(n)]
    try:
        with shape_audit(seq_len=n) as audit:
            r.stream(keys, vals)
    except InvariantViolation as e:  # pragma: no cover
        raise AssertionError(f"a two-sequence-axis (N x N) tensor was registered: {e}")
    assert audit.records, "expected slot_scores to be registered during reads"
    for rec in audit.records:
        assert rec.n_seq_axes == 0, f"{rec.name} registered with {rec.n_seq_axes} seq axes"
        assert rec.numel == 8, f"{rec.name} size {rec.shape} should be (M,) = (8,)"
    # peak single registered structure is M, independent of N -> not N x N, not N x M
    assert audit.peak_numel() == 8


def test_state_size_independent_of_N():
    growth = measure_state_growth(_stream_len, [32, 64, 128, 256, 512])
    assert len(set(growth.values())) == 1, f"state size varies with N: {growth}"


def test_scales_with_slots_not_sequence():
    small = _r(num_slots=4).init_state().numel()
    big = _r(num_slots=64).init_state().numel()
    assert big > small
    # 16x the slots -> 16x the state; sequence length is not a factor at all
    assert big == 16 * small


def test_no_full_prefix_replay_single_step_equals_stream():
    """Incremental one-token-at-a-time decode over a carried O(M) state reproduces the
    streamed result exactly — i.e. no need to re-run the whole prefix each step."""
    r = _r()
    n = 40
    keys = [basis(i % D, D) for i in range(n)]
    vals = [basis((i * 3) % D, D) for i in range(n)]
    ro_stream, s_stream = r.stream(keys, vals)

    # emulate true incremental decode: carry state, do one read+write per step
    s = r.init_state()
    ro_step = []
    per_step_state_sizes = set()
    for t in range(n):
        ro, _ = r.read(keys[t], s)
        ro_step.append(ro)
        s = r.write(keys[t], vals[t], s, source_id=s.position)
        per_step_state_sizes.add(s.numel())
    assert ro_step == ro_stream and s.values == s_stream.values
    # the carried state never grows across the N steps (constant-size decode state)
    assert len(per_step_state_sizes) == 1


def test_causal_read_before_write():
    """A read at token t must not see token t's own write (causal read-then-write)."""
    r = _r()
    s = r.init_state()
    # first token: read on empty state -> zero readout, then write
    ro, idx = r.read(basis(0, D), s)
    assert idx == -1 and ro == [0.0] * D
    s = r.write(basis(0, D), basis(1, D), s)
    # now the fact is retrievable on a subsequent read
    ro2, _ = r.read(basis(0, D), s)
    assert max(range(D), key=lambda i: ro2[i]) == 1


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"complexity: {len(fns)} passed")


if __name__ == "__main__":
    _run()
