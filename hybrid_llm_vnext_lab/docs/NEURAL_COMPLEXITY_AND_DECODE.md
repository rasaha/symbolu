# Neural Complexity & Decode-State Validation

**Date:** 2026-08-03 · Probe: [`../scripts/neural_complexity_probe.py`](../scripts/neural_complexity_probe.py) · Data: [`../artifacts/neural_complexity_probe.json`](../artifacts/neural_complexity_probe.json)

Stronger than the historical output-only hook: the probe patches `torch.cumsum/einsum/matmul/bmm/
softmax` to record **every** intermediate tensor shape during a slot forward, then asserts the
complexity claims from real execution (torch 2.13.0, CPU fp32).

## Historical parallel-scan `BindingSlots` (training implementation)

For B=2, N=48, D=128, M=32:
- **No global `[·,N,N]` score tensor** is ever built (`materializes_NxN_global_score = false`).
- Slot **routing** `[B,N,M]` is materialized (`materializes_routing_BxNxM = true`).
- A **training scan tensor** `[B,N,M,D]` **is** materialized (`materializes_training_scan_BxNxMxD =
  true`).

**Precise statement (do not overclaim):** the historical *training* implementation is **not
constant-memory** — it materializes an `N×M×D` scan tensor for the parallel prefix-sum. It does
**not** materialize an `N×N` global token-pair score tensor. Constant `M×D` memory is a property of
the *streaming/deployed* path, not the parallel-scan training path.

## Streaming `BoundedBindingSlots` (deployed/decode path)

- Deployed recurrent state shape: `[B,M,D]` + `[B,M]` metadata.
- **State size independent of N:** `state_numel` = 8320 at N ∈ {16, 64, 256} (identical).
- One-token incremental update; chunked and token-wise agree (stdlib determinism + streaming
  tests); reset and batch separation covered by the stdlib behavioral tests.
- **Decode-state bytes across the (M,D) grid** (floats):

  | M \ D | 64 | 128 | 256 |
  |---|---|---|---|
  | 8 | 1056 | 2080 | 4128 |
  | 16 | 2112 | 4160 | 8256 |
  | 32 | 4224 | 8320 | 16512 |
  | 64 | 8448 | 16640 | 33024 |

  Grows with M·D, never with N.

## Algorithm relationship

| | historical `BindingSlots` | streaming `BoundedBindingSlots` |
|---|---|---|
| write | soft cumulative distributed writes to **fixed** learned slots (parallel cumsum) | dynamic keys, cosine **threshold** match, **discrete** allocation + LRU eviction |
| metadata | none | version / source / usage / active |
| training tensor | `[B,N,M,D]` scan | `[B,M,D]` streaming state |

**Classification: `RELATED_BUT_DIFFERENT_ALGORITHM`.** No numerical parity is claimed between them.
Neural `EXACT_PARITY` is asserted **only** between the incubated `legacy_phase_lc_slots.BindingSlots`
and the historical `BindingSlots` (same algorithm) — see the parity report.
