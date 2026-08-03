# Hybrid LLM vNext — Falsification Plan

**Audit date:** 2026-08-03 · Machine-readable thresholds: [`artifacts/hybrid_llm_acceptance_thresholds.json`](artifacts/hybrid_llm_acceptance_thresholds.json)

> **This is a plan, pre-registered before any training. H22 (the experiment itself) is NOT implemented in
> this audit.** No training was run. The plan exists so the architecture decision has a defined, matched,
> causal test before any packaging.

## 1. Arms (Phase-free candidates; Phase is a non-candidate reference)

| Arm | Description |
|---|---|
| **A** | Sliding-window (SWA) baseline |
| **B** | Selected modern recurrent mechanism (**KDA**; fallback **GDN**) — pure recurrent stack |
| **C** | B + periodic MLA/full attention at **3:1** — **the selected canonical core** |
| **D** | C + bounded slots — **only if slots remain under consideration** |
| **E** | Conventional attention hybrid (GQA/SWA/MLA + full) — conservative baseline |
| **HISTORICAL** | Current Phase-based best internal architecture — **NON-CANDIDATE**, included only to show the replacement outperforms/avoids its failure modes |

The old Phase architecture's result **must not** affect packaging selection except as evidence the
replacement must beat or avoid (no retrieval; decorative path; full-prefix-replay decode).

## 2. Matched conditions

Matched **parameter count** (total and active for any MoE), matched **training tokens** (~15B, aligned with
the July-2026 comparative study `arXiv:2607.07953`), matched **tokenizer**, matched **data order**, matched
**optimizer** (AdamW primary; Muon compared *separately* so optimizer gains are not attributed to
architecture), and **≥5 seeds** for threshold-sensitive tasks. First model scale: **dense ~150–350M**.

**Fidelity guards (learned from the Phase era):** no hidden quadratic path (forward hooks assert no
`[.,N,N]` tensor in linear-only layers); true recurrent decode (state-size + logits-equivalence hook — no
full-prefix replay); resource measurements (prefill/decode throughput, peak memory, recurrent-state bytes)
recorded, not computed.

## 3. Required task families

Next-token LM; long-range **single-key** retrieval; **multi-key** retrieval; **entity–attribute binding**;
**source attribution**; **supersession / version replacement**; **contradiction**; **multi-hop** evidence
integration; **distractor resistance**; long-output generation; recurrent-state stress; context-length
extrapolation.

These directly target the capabilities the Phase era **failed** (binding, supersession, multi-hop, robust
multi-seed retrieval) so the replacement is tested exactly where the predecessor broke.

## 4. Required causal ablations

Recurrent path off · full-attention/MLA path off · slots off (if present) · **write gate disabled** ·
**erase gate disabled** · **decay disabled** · randomized slot addresses · memory reset · raw-token vs
compressed-memory read (where relevant). Every claimed path must show causal degradation under ablation —
**no decorative path** (the specific failure that made Phase unpackageable).

## 5. Training-objective audit

| Loss | Status | Note |
|---|---|---|
| `L_LM` | **required** | next-token |
| `L_retrieval` | required **only if** slots retained | auxiliary supervision to prevent path domination |
| `L_binding` | required if slots retained | targets the failed capability |
| `L_source`, `L_supersession` | required if slots retained | slot metadata supervision |
| `L_slot_write`, `L_slot_read` | required if slots retained | explicit write/read supervision |
| `L_memory_reconstruction` | experimental | |
| `L_path_balance` | required if any path is at risk of domination | |
| `L_diversity`, `L_router` | experimental | only for adaptive-routing topology F |

**Silent path domination (the Phase failure mode) is addressed explicitly:** if ordinary next-token loss
would make one route decorative, require **stochastic path dropout**, **auxiliary supervision**, **causal
contribution monitoring**, **route-usage metrics**, and **ablation checkpoints**.

## 6. Optimizer & training-system audit

Compare AdamW vs Muon (or current verified alternative); LR schedule, initialization, normalization,
precision, chunk size, recurrent-state checkpointing, sequence parallelism. **Do not attribute an optimizer
benefit to architecture.** Do not recommend an optimizer unsupported by the intended training stack without
a migration plan. (The KDA/GDN stack targets the FLA kernels + standard AdamW; a Muon migration is optional
and separately gated.)

## 7. Acceptance thresholds (numeric, pre-registered)

See the JSON. Hard gates, summarized:
- statistically meaningful LM improvement **or parity** vs A and E (≥5 seeds);
- **robust multi-seed** retrieval (not a 1/3-seed artifact — the exact fragility seen in the Phase slots);
- **binding beyond single-fact recall**;
- **supersession** demonstrated, with erase/write-gate-off causal degradation;
- every claimed path shows causal ablation degradation;
- **no N×N** tensor in linear-only layers; **bounded recurrent decode state**; **no full-prefix replay**;
- measured throughput and memory;
- thresholds not reused from tiny synthetic runs without justification.

## 8. Decision rule

If **C** (KDA + periodic MLA) clears the LM, retrieval, and binding gates and beats/holds parity with **E**
at matched budget, and **HISTORICAL** does not — proceed toward packaging (subject to the packaging gate).
If C fails but **B**/**E** clears, fall back accordingly. If **no** arm clears, the verdict stays
`NO_ARCHITECTURE_READY` and packaging does not begin. Bounded slots enter the package **only** if **D**
independently clears T4–T6 with causal slots-off degradation.
