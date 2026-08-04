#!/usr/bin/env python3
"""H3: gradual curriculum handoff (training-only).

Drop-in replacement for the frozen `interventions.curriculum_batch` with the IDENTICAL signature
`(step, stream, vocab, B, N, rng, T) -> (x, y, mask, phase)`. Phases 1 and 2 are unchanged; only
the hard phase-2 -> original-distribution switch is replaced by a deterministic per-(seed,step,batch)
mixture that ramps the original ABC_MIX probability linearly from 0.0 at step 600 to 1.0 at step 900.

The frozen R0 objective and λ schedule are untouched — H3 changes ONLY the curriculum handoff.
"""
from __future__ import annotations


def curriculum_batch_gradual(step, stream, vocab, B, N, rng, T):
    import interventions as IV  # frozen phase-1/phase-2 primitives (unmodified on disk)
    if step < 300:
        x, y, m = IV._task_batch("needle", vocab, B, N, rng, T, distance=16)
        return x, y, m, 1
    if step < 600:
        return _phase2(vocab, B, N, rng, T)
    if step < 900:
        p_original = (step - 600) / 300.0  # 0.0 -> 1.0 across steps 600..900
        if rng.random() < p_original:
            x, y, m = T.train_batch(stream, B, N, vocab, rng)
            return x, y, m, 3
        return _phase2(vocab, B, N, rng, T)
    x, y, m = T.train_batch(stream, B, N, vocab, rng)
    return x, y, m, 3


def _phase2(vocab, B, N, rng, T):
    import interventions as IV
    if rng.random() < 0.7:
        d = 16 if rng.random() < 0.5 else 96
        x, y, m = IV._task_batch("needle", vocab, B, N, rng, T, distance=d)
    else:
        x, y, m = IV._task_batch("binding", vocab, B, N, rng, T, k=2)
    return x, y, m, 2
