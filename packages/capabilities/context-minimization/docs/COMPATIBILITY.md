# Compatibility & consumer migration

## Consumers discovered (live audit)

| Consumer | Path | What it uses | Outcome |
| --- | --- | --- | --- |
| **Console Agent Gateway** | `ugence_console_api/capabilities/context_gateway.py` | structural dedup only (`structural_compress`), no oracle | **A — migrated now** |
| **Robotics reliability bench** | `robotics_reliability_bench/acp_control_plane/context_pipeline.py` | full `compress(...)` with the signed **ActionGate policy** as oracle | **C — intentional coexistence** (frozen benchmark) |
| CER v0.1 / v0.2 / v0.3 control planes | `cer_v0_*/control_plane.py` | a string status field only (`"APPLIED"` / `"SKIPPED_NO_ACTIONGATE_CONTEXT"`) | **Not a code consumer** — no migration |

## Outcome A — Console (migrated)

The gateway now imports `ugence_context_minimization` and calls `structural_minimize`
instead of injecting `experiments/` onto `sys.path`. This is semantically equivalent
for the structural path and comes with one **hardening**: a protected unit is now
never removed even when a duplicate remains (the old `structural_compress` ignored the
protected set). Parity is proven by
`tests/compatibility/test_compatibility.py::test_console_structural_path_parity` and
the console's own `test_governed_loop.py` (unchanged, still green).

A consumer is **not** migrated from structural dedup to the oracle-verified path unless
it already supplies a valid deterministic oracle. The Console supplies none, so it stays
on structural mode.

## Outcome C — Robotics bench (coexistence)

The robotics bench drives the full ActionGate-oracle `compress(...)` and persists
benchmark results with a provenance string
(`"actiongate_context_ablation.compressor.compress (unchanged)"`). Rewiring it to the
canonical core would change the frozen benchmark surface, so it is **left unchanged** as
frozen legacy evidence. When an ActionGate integration oracle is packaged, this bench is
the natural first migration in a later phase.

## Frozen experiment (coexistence, not rewired)

The experimental compressor under `experiments/actiongate_context_ablation/` is **not**
modified. Its frozen invariance fingerprint (`sha256:ac4e0692…`), corpus manifest, and
committed real-model results are preserved bit-for-bit. A test asserts the experiment
does not import the canonical package, so the frozen path cannot silently drift.
