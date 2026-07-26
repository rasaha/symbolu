# Streaming Phase v1.1 — Stage Report

**Stage:** 2 — Streaming equivalence
**Status:** FROZEN
**Reproduce:** `python -m pytest symbolu/lightweight_phase/tests/test_streaming_equivalence.py`

## Implemented

- Incremental API `layer.step(token_t, previous_state) -> (output_t, next_state)`.
- `forward(x, initial_state=...)` for chunk continuation, plus helpers in
  `streaming.py`: `stream_tokens`, `run_chunked`, `max_abs_error`.
- Carried state is the fixed-size `PhaseState` — no per-token history retained.

## Tested / Demonstrated

Tolerance contract: **float32 max abs error ≤ 1e-5**; bfloat16 uses a documented
looser tolerance (3e-2) because projections run in reduced precision even though
the scan accumulates in float32.

| Scenario | Measured max abs error | Tol | Result |
|---|---|---|---|
| Token-by-token, N∈{1,2,5,16}, B∈{1,3}, H∈{1,4} | ≤ ~2.4e-7 | 1e-5 | PASS |
| Chunked [3,3],[1,2,3],[4,1,1],[6],[2,2,2] | ≤ ~2.4e-7 | 1e-5 | PASS |
| With decay (fixed scalar / fixed per-head / learned) | ≤ ~2.4e-7 | 1e-5 | PASS |
| Random initial state, whole vs split continuation | ≤ ~2.4e-7 | 1e-5 | PASS |
| State reset → independent stream | ≤ ~2.4e-7 | 1e-5 | PASS |
| bfloat16 token-by-token | ≤ 3e-2 | 3e-2 | PASS |

**State-memory bound:** carried-state numel is constant across N∈{2,8,64,256}
(`test_state_memory_constant_across_context_length`) — the O(D) recurrent-state
contract holds; state does not grow with context length.

## Unsupported / Deferred

- None. Reduced-precision equivalence is stated with an explicit, documented
  tolerance rather than claimed at 1e-5.

## Freeze record

- Source SHA-256 for `streaming.py` in `frozen_manifest.json → stages["v1.1-streaming"]`.
- Equivalence is a property test (no separate golden vector needed); the Stage 1
  golden state is the anchor for the single-pass reference.
