# Phase Core v1.0 — Stage Report

**Stage:** 1 — Minimal Phase core
**Status:** FROZEN
**Package:** `symbolu/lightweight_phase`
**Reproduce:** `python -m symbolu.lightweight_phase.freeze`

## Implemented

- LayerNorm pre-norm, key/query phase projections (`W_phi_k`, `W_phi_q`),
  amplitude projections (`W_a_k`, `W_a_q`), value projection (`W_v`),
  bounded phase `φ = π·sin(raw)`, complex key/query phasors, causal cumulative
  complex state, **detached** amplitude normalizer, real-valued readout,
  output projection (`W_out`), residual connection.
- Typed state `PhaseState(complex_memory, amplitude_sum, position)` and result
  bundle `PhaseOutput`.
- Required API: `forward(x, *, initial_state=None, return_state=False, return_diagnostics=False)`.
- Explicit multi-head layout `[B, N, H, Dh]`, `D = H·Dh`.
- Runtime invariants module (no two-sequence-axis tensor; O(D) state).

Deliberately **excluded** (per contract): decay is present but defaults to
`"none"` (Stage 3 owns decay validation); no sliding window, binding slots,
auxiliary/head-diversity losses, controllers, adaptive routing, intent rotation,
quadratic attention, or fixed per-head phase offsets. See
`reference_equations.md` §7 for why offsets are omitted.

## Tested (freeze gate: 98 tests total in the suite)

| Criterion | Test | Result |
|---|---|---|
| Correct I/O shapes | `test_shapes.py` | PASS |
| Finite outputs & gradients | `test_gradients.py`, `test_numerical_stability.py` | PASS |
| Causal behavior | `test_causality.py` (future tokens don't affect past outputs; exact 0.0) | PASS |
| No tensor with two sequence axes | `test_complexity.py` (INV-NO-NN, declarative) | PASS |
| State size independent of N | `test_complexity.py` (128 numel constant over N∈{2,10,100,500}) | PASS |
| Hand-derived math match | `test_phase_math.py` (independent reimplementation, atol 1e-6) | PASS |
| Detached denominator | `test_phase_math.py::test_denominator_is_detached` | PASS |
| Bounded phase range | `test_phase_math.py::test_bounded_phase_range` (\|φ\| ≤ π) | PASS |

Batch scan vs token-by-token execution match is covered in Stage 2.

## Demonstrated

- The forward pass equals a from-scratch second implementation of
  `reference_equations.md` §1–§6 to 1e-6.
- Detaching the normalizer measurably changes the amplitude gradient (proving the
  `stopgrad` is real and load-bearing), while leaving the forward output unchanged.

## Unsupported / Not claimed

- Head specialization from phase offsets — offsets are omitted; specialization is
  treated as an empirical property, never an architectural guarantee.

## Deferred

- None for Stage 1.

## Freeze record

- Config hash (golden config `embed_dim=32, num_heads=4`): see
  `frozen_manifest.json → stages["v1.0-phase-core"].config_hash`.
- Source SHA-256 for `config.py`, `phase_core.py`, `invariants.py`,
  `reference_equations.md`: recorded in the manifest.
- Golden input/output/state fingerprints: `frozen_manifest.json → golden["v1.0-phase-core"]`.
- Environment (python/torch/platform): recorded in the manifest.
- Any later change to frozen behavior requires a version bump + `freeze --write`.
