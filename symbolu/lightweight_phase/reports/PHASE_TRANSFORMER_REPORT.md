# Phase Transformer v1.3 — Stage Report

**Stage:** 5 — Lightweight Phase Transformer block
**Status:** FROZEN
**Reproduce:** `python -m pytest symbolu/lightweight_phase/tests/test_transformer.py`

## Implemented

Minimal pre-norm block (`phase_block.py`):

```
y = x + Phase(LN1(x))          # phase attention (Phase-only when local disabled)
z = y + FFN(LN2(y))            # GELU FFN, ratio configurable
```

`LightweightPhaseTransformerLM`: token + positional embeddings, N stacked blocks,
final LayerNorm, LM head. Configurable layers/heads/hidden/FFN-ratio; causal LM
loss; **tied embeddings** option; deterministic init; Phase-state caching for
generation. No quadratic attention anywhere.

## Tested / Demonstrated

| Criterion | Test | Result |
|---|---|---|
| LM forward + causal loss | `test_forward_and_loss_shapes` | PASS |
| Backward pass finite | `test_backward_finite` | PASS |
| Tied vs untied embeddings | `test_tied_embeddings` | PASS |
| Generation with cached Phase state == full scan | `test_generation_matches_full_scan` (bit-exact greedy) | PASS |
| Checkpoint save/load | `test_checkpoint_save_load` (atol 1e-6) | PASS |
| Deterministic initialization | `test_deterministic_initialization` (bit-exact) | PASS |
| Parameter count stable | `test_parameter_count_stable` | PASS |
| Learns a trivial pattern | `test_learns_a_trivial_pattern` (loss ↓ >10%) | PASS |

The full-scan vs incremental-generation equivalence confirms the O(1)-per-step
Phase state cache is exact (Phase is truly recurrent; embeddings/FFN are
position-wise).

## Golden freeze

- Golden LM config hash + parameter count + logits fingerprint:
  `frozen_manifest.json → golden["v1.3-transformer"]`.
- Source SHA-256 for `phase_block.py` in `stages["v1.3-transformer"]`.

## Unsupported / Deferred

- No sliding-window path in Stage 5 (Phase-only). Local fusion is Stage 6.
- Large-scale LM quality is not claimed here; the block is validated structurally
  and on a trivial learnable pattern.
