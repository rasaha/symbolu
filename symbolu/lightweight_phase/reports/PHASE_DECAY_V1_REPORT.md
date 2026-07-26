# Decay Phase v1.2 — Stage Report

**Stage:** 3 — Optional decay
**Status:** FROZEN
**Reproduce:** `python -m pytest symbolu/lightweight_phase/tests/test_numerical_stability.py symbolu/lightweight_phase/tests/test_streaming_equivalence.py`

## Implemented

Four decay modes (config `decay_mode`):

| Mode | γ definition | Notes |
|---|---|---|
| `none` | γ = 1 (pure cumsum) | reproduces the Stage 1 core exactly |
| `fixed_scalar` | γ = `initial_gamma` (all heads) | scalar horizon |
| `fixed_per_head` | γ_h spread log-linearly across [γ_min, γ_max] | short→long horizons |
| `learned_per_head` | γ_h = γ_min + (γ_max−γ_min)·σ(θ_h) | trainable, range-bounded |

Configurable: `gamma_min`, `gamma_max`, `initial_gamma`, `decay_mode`. The
recurrence is `S_t = γ·S_{t-1} + k_t⊙v_t` with per-head γ broadcast over Dh,
applied identically to the state and the amplitude normalizer.

## Tested / Demonstrated

| Criterion | Test | Result |
|---|---|---|
| γ = 1 reproduces non-decay core | `gamma=1 reproduces none` (≈3e-8) | PASS |
| Lower decay forgets older evidence faster | `test_lower_decay_forgets_faster` | PASS |
| State remains bounded on long (512) sequences | `test_long_sequence_state_bounded_under_decay` (\|S\|max < 1e3) | PASS |
| Gradients finite (incl. learned γ) | `test_gradients.py` | PASS |
| Learned γ stays inside [γ_min, γ_max] under extreme θ | `test_learned_decay_stays_in_range` | PASS |
| Batch ≡ streaming under decay | `test_streaming_equivalence_with_decay` (≤ 2.4e-7) | PASS |

## Measured horizons

Approximate horizon `H ≈ 1/(1−γ)` (labeled an approximation, §9 of the reference):

| γ | approx H (tokens) |
|---|---|
| 0.5 | ~2 |
| 0.9 | ~10 |
| 0.95 | ~20 |
| 0.99 | ~100 |
| 0.999 | ~1000 |

`fixed_per_head` with defaults γ∈[0.90, 0.99999] spreads heads from ~10 to ~10⁵
tokens. The horizon is a first-order approximation of the geometric weighting, not
a hard cutoff.

## Limitations

- The learned-decay γ range is set by `gamma_min/gamma_max`; the production layer
  uses a *different* range (0.97 + 0.0295·σ(logit) ≈ [0.97, 0.9995]). The
  equivalence harness pins γ values explicitly rather than matching the
  parameterization (documented in the equivalence report).
- The reference decay scan is an exact sequential recurrence (auditability first);
  the production `parallel_ema_scan` is the fast path and is validated to agree.

## Freeze record

- Config hash of the learned-decay golden config and source SHA-256 for
  `phase_core.py`, `config.py`: `frozen_manifest.json → stages["v1.2-decay"]`.
- Golden output fingerprint: `golden["v1.2-decay"]`.
