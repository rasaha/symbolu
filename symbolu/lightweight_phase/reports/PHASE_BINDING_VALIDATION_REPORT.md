# Phase + Binding v1.5 — Stage Report

**Stage:** 8 — Bounded binding slots
**Status:** Structure, complexity, and streaming-memory behavior FROZEN. The
A/B/C/C-no-Phase training validation ladder and causal ablations are DEFERRED
(compute-bound), with the harness in place.
**Reproduce:** `python -m pytest symbolu/lightweight_phase/tests/test_binding_slots.py`

## Implemented (`binding_slots.py`)

`BoundedBindingSlots` — a bounded, content-addressable slot memory integrated as an
additive path:

- Slot state (fixed M):
  `slot_keys [B,M,Ds]`, `slot_values [B,M,Dv]`, `slot_source [B,M]`,
  `slot_version [B,M]`, `slot_usage [B,M]`, `slot_active [B,M]`.
- **Streaming read-then-write per token**, carrying only `BindingSlotState`
  (O(M·D)); never materializes `[B,N,M,D]`, `[B,N,N]`, or `[B,H,N,N]`.
- Content-based matching (cosine), **bounded Top-K read**, collision handling
  (match → in-place supersede + version bump), eviction (free slot, else LRU by
  usage), source attribution. Differentiable reads; discrete metadata under
  `no_grad`.
- First semantics implemented: **entity↔value** and **entity↔source**. Additional
  semantics (rule↔exception, document↔version, claim↔evidence, event↔time) are
  designed for but not yet added — each will be frozen independently.

## Tested / Demonstrated

| Criterion | Test | Result |
|---|---|---|
| No `[N,N]`/`[N,M,D]` sequence tensor | `test_no_sequence_squared_or_nmd_tensor` | PASS |
| State size independent of N (544 numel over N∈{5,20,100,400}) | `test_state_size_independent_of_n` | PASS |
| Slot count bounded (≤ M) | `test_slot_count_is_bounded` | PASS |
| Whole-seq ≡ chunked slot metadata | `test_streaming_chunked_equivalence_of_state_metadata` | PASS |
| Gradients finite | `test_gradients_finite` | PASS |
| Version bump on supersession | `test_version_bump_on_supersession` | PASS |
| Source attribution recorded | `test_source_attribution_recorded` | PASS |
| Bounded Top-K read | `test_top_k_read_bounded` | PASS |
| Reducing M changes capacity | `test_reducing_slot_count_changes_capacity` | PASS |

**Complexity/memory proof:** per-token compute O(M·D), total O(N·M·D), persistent
state O(M·D). The streaming loop keeps peak extra memory at O(M·D)+O(N·D) outputs,
never O(N·M·D).

## Unsupported / Deferred (explicitly)

The decisive binding validation ladder is **not yet run**:

- **A** sliding window · **B** +Phase · **C** +Phase +binding · **C-no-Phase**
  window+binding. Decisive comparisons **C−B** (binding value given Phase) and
  **C−C_no-Phase** (Phase value given binding) require training on a
  multi-fact / supersession / conflict task and are compute-deferred.
- Causal ablations for slots (randomize keys, shuffle values, reduce M, remove
  source/version metadata, vary Top-K, force collisions, disable supersession) are
  specified but not yet executed.

No binding capability is claimed as demonstrated. Only the bounded, streaming,
memory-efficient **structure** and its complexity are frozen. In particular, no
claim of "exact binding from Phase alone" is made anywhere.

## Freeze record

- Source SHA-256 for `binding_slots.py` in
  `frozen_manifest.json → stages["v1.5-binding"]`.
