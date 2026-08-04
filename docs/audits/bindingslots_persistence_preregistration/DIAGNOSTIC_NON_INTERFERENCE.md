# Diagnostic non-interference (step 700)

Step 700 is an **added diagnostic checkpoint**. Adding it must not change training. This is **proven**,
not asserted, by `experiments/bindingslots_persistence/diagnostic_noninterference.py` (report:
`results/diagnostic_noninterference.json`).

## Why it holds by design

The frozen diagnostics are observation-only: `routing_diagnostics` uses a local `Random(4321)` under
`@torch.no_grad()` and restores train/eval mode; `grad_norm_probe` uses a local `Random(777)`, zeroes
grads before and after, and never calls `opt.step`; `_needle_at` uses fixed seed 123 under `no_grad`.
The model has dropout 0, so the training loop consumes no global torch RNG (data order is driven by
the separate `Random(seed*991+7)`), and diagnostics touch neither.

## Proof (small deterministic fixture, seed 3, not a persistence seed)

- **Test 1 — state invariance:** snapshot params + optimizer state + python & torch RNG states, call
  the exact step-700 diagnostic bundle, re-snapshot → **byte-identical** (PASS).
- **Test 2 — A/B trajectory:** two identical short runs, one injecting the diagnostic bundle mid-loop →
  **identical final parameter hash and identical next-step loss** (PASS).

Result: `step_700_noninterference_proven = true`. The preregistration integrity verifier requires this.
No full training was run to establish it.
