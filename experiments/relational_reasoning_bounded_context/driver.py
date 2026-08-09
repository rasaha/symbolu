"""Top-level BTRR orchestration (fail-closed). torch is lazy; nothing runs without authorization.

Flow for a FUTURE authorized seed:
    guard_seed(seed, token)              # fail-closed; reserved seeds raise until authorization
    -> train_checkpoint(seed, ...)       # ONE checkpoint (trainer.py, torch)
    -> run_single_checkpoint(ckpt, P0, R1-R12)   # byte-identical checkpoint for P0 and R1-R12 (eval.py)
    -> gates.evaluate_gates(...) -> verdict.decide(...)

This module performs NO training/evaluation at import and refuses reserved seeds. It exists to document
and wire the frozen flow; the actual run is gated behind an unsigned EXECUTION_AUTHORIZATION.md.
"""
from __future__ import annotations

from .execution import guard_seed, is_unit_fixture


def dry_run_plan(seed: int) -> dict:
    """Describe what WOULD run for `seed` without running it. Reserved seeds are reported as blocked."""
    try:
        guard_seed(seed)
        reachable = True
        note = "non-reserved seed (implementation only)" if is_unit_fixture(seed) else "non-reserved"
    except Exception as exc:  # ExecutionNotAuthorized
        reachable = False
        note = str(exc)
    return {
        "seed": seed,
        "execution_reachable": reachable,
        "note": note,
        "flow": ["guard_seed", "train_checkpoint", "run_single_checkpoint(P0, R1-R12)",
                 "evaluate_gates", "verdict.decide"],
        "execution_status": "BTRR_EXECUTION_NOT_AUTHORIZED",
    }
