# Hybrid LLM vNext — Algorithm Lineage

**Audit date:** 2026-08-03 · **HEAD:** `69b3bb94`

> **Latest ≠ greatest.** This document is chronological/derivational. A later arm is *latest*; it is
> *better* only where evidence says so (see the Internal Evidence Ledger). Several later designs
> **regressed**.

## 0. Git history is unusable for dating — lineage is reconstructed from version tags

`git log --follow` returns the **same ~6 bulk-snapshot commits for every core model file** (e.g.
`5a4f3357`, 2026-07-31, = 13,180 files / 3.69M insertions; every model file's add-date is 2026-07-30).
This is a squashed/imported monorepo, not authoring history, so **commit dates cannot order the
lineage.** The lineage below is reconstructed from **in-document version tags** (`lightweight_phase`
v1.0–v1.5), **stage numbers**, and **arm ladders** (Q/L/R/P/PL, A/B/C, D, H0–H8). The only model-adjacent
files with commit history *beyond* the bulk import are the token/event `real_model/` harness (`97856a4e`
"RM1-v1.1", `9e5f9962`; 2026-07-30) — which is a RESOURCE_BLOCKED validation harness, not a new
architecture.

## 1. Canonical spine — `lightweight_phase` staged freeze

`symbolu/lightweight_phase/README.md` + `reports/FINAL_SUMMARY.md` define the authoritative ladder:

| Version | Stage | Transition | State |
|---|---|---|---|
| v1.0 | Phase Core | — → v1.1 | **Original Phase mechanism**, equations frozen, prod-equiv ≤2.4e-7. IMPLEMENTED+FROZEN |
| v1.1 | Streaming Phase | v1.0 → v1.2 | batched scan = token-by-token ≤2.4e-7; O(D) state. IMPROVED+FROZEN |
| v1.2 | Decay Phase | v1.1 → v1.3 | 4 decay modes; γ=1 reproduces core. IMPROVED+FROZEN |
| v1.3 | Phase Transformer | v1.2 → v1.4 | block + LM head. IMPLEMENTED+FROZEN |
| v1.4 | **Local + Phase** | v1.3 → v1.5 | sliding window fused with Phase (protected additive). Stage-7 A/B distant-recall **+0.741** on a *synthetic cue task*. IMPROVED (full study deferred) |
| v1.5 | **Phase + Binding** | v1.4 → phase_lc | bounded slots O(M·D). Structure/complexity FROZEN; **binding validation DEFERRED — "no binding capability claimed as demonstrated."** |

## 2. Falsification ladder (executed, layered on the spine)

| Step | Predecessor → Successor | Rationale | Implemented | Tested | Outcome |
|---|---|---|---|---|---|
| phase_lc Q/L/R/P/PL | v1.5 → matched-arm study | add real tokens, matched params (~2M, <0.1%), 3 seeds, and the decisive control **R = gated real diagonal linear recurrence** to isolate what *complex phase* buys over an ordinary linear recurrence | yes | 3 seeds | SUPERSEDES prior single-run synthetic "100% needle" claims |
| phase_lc A/B/C | Q/L/R/P/PL → ladder | A(window) → B(+real Phase) → C(+bounded slots) using the real `PhaseAttentionLayer` | yes | 3 seeds | **B−A(PPL) improved** (fluency); **B−A(retrieval)≈0** (Phase adds no retrieval); **C single-fact recall carried by slots, 1/3 seeds** |
| — (fidelity) | reimplemented-Phase ladder → real-layer ladder | earlier core omitted the amplitude normalizer | — | — | **DISCARDED / SUPERSEDED** |
| — (rejection) | `BindingCacheQuadQuery` → `BindingSlots` | quad reader builds N×N, violates no-quadratic rule | — | — | **REJECTED**, replaced by auditable slots |
| phase_guided_slots (arm D) | C → D | hypothesis: Phase guides slot writes | yes | 1–3× | **REGRESSED**: D−C = −0.14 to **−0.75**; Phase guidance hurt |
| phase_guided_slots_v2 | D → v2 | v1 task shown invalid (no evictions) | yes | yes | **NEGATIVE** on neural identity-key addressing; clean capacity baseline |
| enterprise_slots_quadratic | (governance track) | slot survival + bounded slot-to-slot quad | yes | seed 0 | slot-survival validated; **S5(slot-to-slot 0.69) > S6(query-to-slot 0.60)**; **no Phase** |
| hybrid_token_event_attention (H0–H8) | enterprise slots → dual-attention | bounded event operator on a Mistral token path | yes | CPU | event path **+0.63**; interaction marginal; deterministic rules sufficient; **no Phase**; RM1 real-model **RESOURCE_BLOCKED** |

## 3. Parallel production track (all in `phase_transformer.py`, not a clean ladder)

`PhaseAttentionLayer` → `BindingCachePhaseState` (memory writer) → `BindingCacheQuadQuery` (N×N reader) +
`LocalWindowAttention` → `BindingCacheBlock/Transformer` (protected serial) →
`OntologicalBindingCacheTransformer` → `HybridAttentionLayer/HybridPhaseTransformer` (blended) →
`SlotMemoryGCT` → `GCT*` (separate O(n²)+gating arch, design doc "March 2026, Implemented v1"). This track
accumulated features and version tags (V9–V20) **without a matched-baseline ladder or committed
checkpoints**; the falsification ladder in §2 is what actually tested (and largely falsified) its claims.

## 4. Document lineage (VC briefs)

`HYBRID_LLM_VC_BRIEF.md` (v1) → `_v2.md` → **`_v3.md` + `HYBRID_LLM_VC_CLAIM_LEDGER.json`**. v3 explicitly
**demotes Phase to "a separate research track… not a validated production dependency"**
(`HYBRID_LLM_VC_BRIEF_v3.md:17-19`; changelog v3), **RETIRES** the "Protected Phase superiority" claim,
and marks the enterprise-Phase-value claim **UNSUPPORTED**. v1/v2 are **SUPERSEDED**. The internal
documentation has therefore *already* converged on the skeptical reading this audit corroborates.

## 5. Transition-state summary

| Transition | Rationale | Implemented | Tested | Improved | Regressed | Superseded |
|---|---|---|---|---|---|---|
| Phase core → streaming/decay/transformer (v1.0→v1.3) | make Phase a usable LM block | ✅ | ✅ | ✅ | | |
| → Local+Phase (v1.4) | add local detail path | ✅ | synthetic | ✅ (fluency; synthetic recall) | | |
| → Phase+Binding (v1.5) | add addressable memory | ✅ | deferred | — | | |
| Phase+Quad reader | conditional exact retrieval | ✅ | — | | quad is N×N | ✅ (rejected for slots) |
| Protected serial / gradient-competition thesis | force role specialization | ✅ | — | | Phase decorative | ✅ (v3 retires) |
| Phase-guided slots (D) | Phase steers memory | ✅ | ✅ | | ✅ (−0.14…−0.75) | |
| Token/event dual-attention | evidence-typed second path | ✅ | CPU | ✅ (event path) | interaction marginal | (Phase dropped) |

## 6. What is "latest" vs "load-bearing"

- **Chronologically latest core model code:** the parallel production track (`phase_transformer.py`
  through the GCT block) driven by `train_unified_llm_clean.py` — but **zero committed checkpoints**.
- **Latest frozen canonical model:** `lightweight_phase` v1.5 (Phase+Binding, validation deferred).
- **Latest executed experiments:** `phase_guided_slots_v2` (NEGATIVE) and `hybrid_token_event_attention`
  (**Phase-free**), plus the RM1 real-model harness (**RESOURCE_BLOCKED**).
- **The direction of travel is away from Phase:** the newest executed work either regressed when adding
  Phase guidance (D) or omitted Phase entirely (token/event). This lineage is consistent with, and
  independently motivates, the binding directive to exclude Phase from the future package.
