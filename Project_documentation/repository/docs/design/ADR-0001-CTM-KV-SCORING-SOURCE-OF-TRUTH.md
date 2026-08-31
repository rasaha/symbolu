# ADR-0001: CTM+ KV-Cache Scoring — Source of Truth for PCAM Alignment

**Status:** Accepted
**Date:** 2026-04-10
**Owners:** CTM+ / PCAM architecture
**Supersedes:** `Project_documentation/repository/docs/design/CTM_PLUS_LIMITATIONS_AND_DESIGN_UPDATES.md` § 2.1 (scoring formula only)

---

## Context

`CTM_PLUS_LIMITATIONS_AND_DESIGN_UPDATES.md` § 2.1 proposes a **six-signal** attention-aware KV-cache scoring formula:

```
score = 0.25·recency
      + 0.20·frequency
      + 0.25·attention_value
      + 0.15·position_importance
      + 0.10·sequence_priority
      + 0.05·reuse
```
(`Project_documentation/repository/docs/design/CTM_PLUS_LIMITATIONS_AND_DESIGN_UPDATES.md:67`)

The reference implementation at `CTM_plus/KVPolicy/kv_policy/attention_evictor.py` — which is 506 lines, wired into `kv_policy/__init__.py:20-26`, and already consumed by `vllm_evictor.py` and `vllm_adapter.py` — uses a **four-signal** phase-aware formula:

```
score = w.recency·recency
      + w.frequency·frequency
      + w.attention·attention
      + w.position·importance

PHASE_WEIGHTS = {
    PREFILL: (recency=0.15, frequency=0.20, attention=0.35, position=0.30),
    DECODE:  (recency=0.30, frequency=0.20, attention=0.30, position=0.20),
}
```
(`CTM_plus/KVPolicy/kv_policy/attention_evictor.py:170-173`, `:378-417`)

Two terms in the doc are absent from the code:

- **`reuse`** (weight 0.05 in the doc) — no reuse counter, no reuse signal, no fold-in.
- **`sequence_priority`** (weight 0.10 in the doc) — `SequenceState` tracks `phase` and `block_ids` but has no priority field; `PHASE_WEIGHTS` has no `sequence_priority` entry.

Additionally, the code collapses `attention_value` and `position_importance` into a pair of cooperating signals:

- `attention` = `block.attention_ema` (EMA of attention mass), lines 306-347
- `position` = `classify_block_importance(is_sink, attention_ema, adaptive_threshold)` returning 1.0 / 0.8 / 0.1, lines 48-62, 479-486
- plus a flat **entity bonus of +0.5** for non-sink blocks whose `attention_ema` exceeds the adaptive threshold (line 414)

Phase awareness, frequency sketching, and sink pinning are all implemented and exercised.

We must decide which of the two formulas is canonical before updating PCAM's spec, simulator, RTL, and tests, because divergence will create an ambiguous test oracle.

---

## Decision

**`CTM_plus/KVPolicy/kv_policy/attention_evictor.py` is the source of truth for KV-cache scoring.**

The canonical scoring model for all PCAM alignment work is the **four-signal phase-aware formula** currently implemented in that file:

| Signal | Source | PREFILL weight | DECODE weight |
|---|---|---:|---:|
| recency | `exp(-0.01 · (step − last_access_step))` | 0.15 | 0.30 |
| frequency | `min(1.0, sketch.estimate(block) / 10.0)` | 0.20 | 0.20 |
| attention | `block.attention_ema` | 0.35 | 0.30 |
| position | `classify_block_importance(is_sink, ema, adaptive_threshold)` → {1.0, 0.8, 0.1} | 0.30 | 0.20 |

Plus:
- **Entity bonus:** `+0.5` for non-sink blocks with `attention_ema > adaptive_threshold` (`:414`)
- **Sink pinning:** sink blocks are excluded from `available` in `select_victims()` (`:427`) — they are never scored and never selected
- **Filler fast path:** if the set of all-filler blocks is large enough to satisfy the request, they are sorted by `freq_sketch.estimate()` and returned without running the full scoring loop (`:431-439`)
- **Sampled scoring:** when the filler fast path is insufficient, a random sample of 48 candidates is scored and the lowest-scoring blocks are returned (`:441-450`)

The `FrequencySketch` class at `attention_evictor.py:69-112` (4-bit Count-Min, depth=4, power-of-two width, four fixed seed hashes, periodic halving at `capacity * 10` increments) is the canonical frequency tracker. PCAM RTL and simulator must match its structure exactly.

### Disposition of the two removed terms

**`reuse` (doc weight 0.05)** — Dropped entirely. Rationale: it was the lowest-weight term in the doc, and the code achieves equivalent scan resistance through the combination of the frequency sketch (which ages via halving) and the entity bonus (which protects genuinely re-referenced blocks via attention EMA). There is no `reuse_count` in the reference implementation, and nothing in `vllm_evictor.py` / `vllm_adapter.py` expects one. PCAM will not track reuse.

**`sequence_priority` (doc weight 0.10)** — Dropped from per-block scoring. Rationale: the reference treats sequence priority as an **orchestration-layer** concern (which sequences are admitted, which are evicted wholesale via `complete_sequence()` at `:240-248`), not a per-block scoring concern. Per-sequence phase (`PREFILL` vs `DECODE`) is honored and shifts the weight vector, which captures the most important variation the doc was trying to express. PCAM will honor phase but will not model a per-sequence priority scalar.

### Known deferred items (dead code in the reference)

The following appear in the reference file but are **not yet functional**. PCAM alignment must not assume they are active:

1. **`PositionClass.RECENT`** is declared at `:121` and `recent_window` is accepted as a constructor parameter at `:198, :205`, but the recent window is **never read** in `_classify_block()` or `score_block()`. The recent-window protection described in the doc (`:42, :87`) is not implemented. PCAM should match: no recent-window carve-out for now.
2. **`PositionClass.ENTITY` / `PositionClass.FILLER`** are declared in the enum but `_classify_block()` returns a raw float (1.0 / 0.8 / 0.1) rather than the enum value. PCAM should model the numeric importance, not the enum.
3. **The `position` parameter on `on_token_access()`** is used only to set `is_sink` (`:294-296`); no other position-derived signal feeds scoring.

Any future work that activates these paths is a **change to the reference**, and must update this ADR and the PCAM alignment together.

---

## Consequences

### Positive

- **Single test oracle.** PCAM's simulator, RTL, and vLLM integration all conform to the same scoring function — the one that actually runs in `attention_evictor.py`. Test parity can be asserted directly against the Python reference via a conformance harness.
- **Smaller RTL surface.** Four signals instead of six, no `reuse_count` field, no `sequence_priority` field. `block_entry_t` in `pcam_pkg.sv` gets strictly smaller, not larger, after the update.
- **Sketch port is direct.** The `FrequencySketch` class in Python maps almost 1:1 to RTL (4 BRAM rows × power-of-two columns, 4-bit counters, four fixed seed hashes). No algorithm design work required for the sketch itself — only timing closure.
- **Unblocks the PCAM update PR.** The formula question was the only architectural ambiguity gating the PR scope.

### Negative / accepted tradeoffs

- **The stale doc stays stale until someone updates it.** `CTM_PLUS_LIMITATIONS_AND_DESIGN_UPDATES.md` § 2.1 still shows the six-signal formula. Mitigation: a `> **Superseded by ADR-0001**` banner will be added to that section pointing at this file. The rest of the doc (S3-FIFO, training memory manager, Count-Min Sketch design sketch) remains valid as forward-looking design notes.
- **`reuse` and `sequence_priority` are not tracked.** If a customer workload shows a measurable win from either signal, we will need to extend the reference implementation first, then update PCAM. The work order is fixed: **code → ADR → PCAM**. PCAM never leads.
- **`RECENT` window protection is deferred.** On workloads where the recent sliding window matters more than attention EMA (e.g., pure streaming without strong attention concentration), both the reference and PCAM will under-protect recent tokens. This is a known gap, not a hidden one.

### Neutral

- The CTM+ updates doc's description of `AttentionAccumulator`, `PositionClassifier`, `SequencePriorityManager`, and `PhaseAwarePolicy` as four separate components is descriptive scaffolding, not a structural requirement. The reference implements all of their live behavior inside a single `KVCachePolicy` class. PCAM is free to match that flatter structure.

---

## Alternatives considered

**(A) Align to the doc (six-signal) and change the code.**
Rejected. The code is already deployed, wired into the package exports, and exercised by `vllm_evictor.py` and `vllm_adapter.py`. Changing it to match a stale design note would break working integration for a non-workload-driven reason. ADRs exist precisely to record when the map stops matching the territory — and to update the map.

**(B) Support both formulas behind a config flag.**
Rejected. It doubles the RTL surface, doubles the test matrix, and leaves the ambiguity live in every future conversation. A flag is the wrong tool for a source-of-truth question.

**(C) Defer the decision until a CTM+ owner weighs in.**
Rejected as the default path, but preserved as an escape hatch. If the CTM+ owner explicitly overrides this ADR, we document the override here and re-scope PCAM accordingly. In the absence of an explicit override, the code wins — it has to, because there's nothing else to test against.

---

## References

- **Reference implementation:** `CTM_plus/KVPolicy/kv_policy/attention_evictor.py`
  - `FrequencySketch` — lines 69-112
  - `PHASE_WEIGHTS` — lines 170-173
  - `KVCachePolicy.score_block()` — lines 378-417
  - `KVCachePolicy.select_victims()` — lines 419-450
  - Sink pinning — lines 293-296, 427
  - Filler fast path — lines 431-439
- **Package wiring:** `CTM_plus/KVPolicy/kv_policy/__init__.py:20-26`
- **Consumers:** `CTM_plus/KVPolicy/kv_policy/vllm_evictor.py`, `CTM_plus/KVPolicy/kv_policy/vllm_adapter.py`
- **Superseded design note:** `Project_documentation/repository/docs/design/CTM_PLUS_LIMITATIONS_AND_DESIGN_UPDATES.md:61-89`
- **Follow-up:** PCAM update PR scope (ADR-0002 or PR description), to be written against this ADR.

---

## Implementation note — vendored reference (Phase 0)

*This section is an operational addendum and does not change the
decision above.*

Phase 0 of the PCAM software-product roadmap vendored the CTM+
reference into the PCAM package at
`simulator/pcam/reference/attention_evictor_vendored.py` so that
`simulator.pcam` can be consumed as a standalone Python package
without requiring `CTM_plus/KVPolicy` on `sys.path` at runtime. The
vendored file is a **read-only specification reference**; it is not
the runtime policy. The runtime policy remains
`simulator/pcam/kv_policy.py::KVCachePolicy`, which is the bit-parity
port this ADR contracts for.

When the upstream reference changes, maintainers follow the ritual
at
[`Project_documentation/simulator/simulator/pcam/docs/VENDORED_REFERENCE_UPDATE_RITUAL.md`](../../../simulator/simulator/pcam/docs/VENDORED_REFERENCE_UPDATE_RITUAL.md):
re-copy the file, re-apply the vendoring header, run the parity
harness, update the runtime port only if behavior diverged, and
commit the bump with the new pinned commit hash in the header.

The parity harness at
`simulator/pcam/tests/test_sketch_conformance.py` and
`simulator/pcam/tests/test_attention_evictor_parity.py` imports the
vendored file directly — not the upstream path — and is the sole
mechanism that detects drift between the two.
