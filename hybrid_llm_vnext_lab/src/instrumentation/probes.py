"""
probes.py — stdlib instrumentation for the bounded binding-slot subsystem.

These helpers observe a SlotReference run and expose the quantities the audit cares about:
bounded-state size, per-slot utilization, collision/eviction counts, source/version
retention, and — via the vendored declarative audit — the no-[N,N] guarantee. All stdlib;
runnable without PyTorch.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from .invariants import ShapeAudit, shape_audit


def state_numel(state) -> int:
    """Total scalar count carried between steps (bounded == constant in N)."""
    return state.numel()


def measure_state_growth(build_and_run, seq_lengths: Sequence[int]) -> Dict[int, int]:
    """Run `build_and_run(N) -> final_state` for each N and return {N: state_numel}.

    A constant mapping proves INV-STATE-O (state size independent of sequence length).
    """
    out: Dict[int, int] = {}
    for n in seq_lengths:
        state = build_and_run(n)
        out[n] = state_numel(state)
    return out


def peak_score_axes(run) -> ShapeAudit:
    """Run `run()` inside a declarative shape audit and return the audit.

    If any registered tensor had >=2 sequence axes the audit would have raised
    InvariantViolation; a returned audit therefore certifies no [N,N] work occurred.
    Scores are registered with n_seq_axes=0 (M is a fixed count, not a sequence axis).
    """
    with shape_audit(seq_len=0) as audit:
        run()
    return audit


def utilization(state) -> List[float]:
    """Per-slot usage vector (recency-weighted write mass)."""
    return list(state.usage)


def retention_summary(state) -> Dict[str, object]:
    """Discrete-metadata summary for source/version/supersession probes."""
    return {
        "n_active": state.n_active(),
        "versions": list(state.version),
        "sources": list(state.source),
        "collisions": state.collisions,
        "evictions": state.evictions,
        "max_version": max(state.version) if state.version else 0,
    }
