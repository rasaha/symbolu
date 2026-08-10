# Agent Runtime — Read-Only Canary Results (Deliverable 6)

Read-only canary execution (§8). Labels: `FACT` · `INTERPRETATION`.

## Status: harness VALIDATED; real-model-driven canary `BLOCKED_NO_REAL_MODEL`
`FACT`. The canary HARNESS is validated (Phase 2 + this phase): read-only-only registry (governed
tools refused), kill switch, step + iteration budgets, cancellation, full trace, observation return,
explicit-no-silent audited legacy fallback; unauthorized-handler invocations 0; consequential tools
shadow-only. Tests: `test_parity_and_canary` (canary), `benchmark/phase2_metrics.py`.

`FACT`. **Running the canary with a REAL model driving planning is blocked** — no live/local model can
run. The canary is not exercised with real-model plans this phase.

## Interpretation
`INTERPRETATION`. The canary is mechanically ready and safe (kill switch + budgets + read-only
enforcement + explicit fallback all tested); the only missing element is a real model to generate the
plans it governs. With a model configured, `benchmark/real_model_eval.py` drives the canary unchanged.
