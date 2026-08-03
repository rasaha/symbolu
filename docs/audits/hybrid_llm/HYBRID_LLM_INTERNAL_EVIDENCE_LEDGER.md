# Hybrid LLM vNext — Internal Evidence Ledger

**Audit date:** 2026-08-03 · Machine-readable twin: [`artifacts/hybrid_llm_internal_evidence_ledger.json`](artifacts/hybrid_llm_internal_evidence_ledger.json)

This ledger maps every important claim to **what actually tested it** and **which implementation the
result belongs to.** Results from different implementations are kept separate — there is no single
"Hybrid LLM score."

## 0. What is real evidence vs a documentation test

- **Model-performance evidence** = an executed study with committed raw metrics. There are four
  multi-seed studies (`phase_lc`, `lightweight_phase_natural_language`, `phase_quality_auxiliary`,
  `enterprise_slots_quadratic`) plus single-seed toys and self-reported A100 numbers.
- **Documentation test** (NOT model evidence): `tests/test_claims_validation.py` checks *string presence*
  (`"cumsum" in source`, `"16384" in source`, `"top_k" in source`; :157,167,506) and
  `tests/test_unvalidated_claims.py` checks *marketing arithmetic* (`0.03/0.001 ≥ 25`,
  `175e9/7e9 == 25.0`; :367-396). The "35 VALIDATED (97%)" figure is built from these — **flagged, not
  counted as model evidence.**
- **No Phase/Hybrid checkpoints or training logs are committed.** Maximum executed scale ≈ 2M params, CPU.

## 1. Claims table (abridged; full table in JSON)

| # | Claim | Implementation | Tier | Scale |
|---|---|---|---|---|
| C1 | 240K pure-phase → 100% needle @10K | Pure Phase O(n) | SYNTHETIC_PROBE | 240K, synthetic copy |
| C2 | O(n) memory 1.02x / 30x @32K | Hybrid tiny ckpt | REAL_HARDWARE_MEASURED (O(n) side) | tiny, PPL~120, A100 |
| C3 | Hybrid checkpoint needle = **0%** | Hybrid shipped ckpt | CONTRADICTED | tiny, PPL~120 |
| **C4** | **Phase improves PPL 73 vs 118** | **Window+real Phase** | **TRAINED_LM + MATCHED_ABLATION** | **~2M, 3 seeds, real prose** |
| C5 | Phase adds NO retrieval; phase-off null | Window+Phase | CONTRADICTED | as C4 |
| C6 | Fragile single-fact recall carried by **slots** (1/3 seeds) | Bounded slots | SYNTHETIC_PROBE + MATCHED_ABLATION | ~2M, M=32 |
| C7 | Binding/supersession/source/multi-hop at chance | window/+Phase/+slots | CONTRADICTED | as C4 |
| C8 | Distant-recall B−A=+0.741 | Lightweight frozen Phase (synthetic cue) | SYNTHETIC_PROBE | 3 seeds |
| C9 | Frozen Phase adds no NL capability; not load-bearing | Lightweight Phase (NL) | CONTRADICTED | 0.26–0.44M, 3 seeds |
| C10 | Frozen Phase < trained GRU on info-health | Frozen Phase auxiliary | CONTRADICTED | ~34–49K, 3 seeds |
| C11 | Protected-Phase superiority / removes decay tax | BindingCacheTransformer | SUPERSEDED (RETIRED) | none |
| C12 | Serial beats parallel (gradient competition) | design | PROPOSED_ONLY | none |
| C13 | Quad invoked conditionally (Top-K) | BindingCacheQuadQuery | CONTRADICTED (N×N first) | code only |
| C14–C21 | Slot survival / conflict F1 / version / capacity / normalization / TAP | **Deterministic governance, NO Phase** | SYNTHETIC_PROBE / UNIT_TESTED | synthetic, seed 0 |
| C22 | Ontological hybrid implemented | OntologicalHybridTransformer | IMPLEMENTED | code-path |
| C23 | "35 VALIDATED (97%)" | marketing | **DOCUMENTATION_TEST** | n/a |
| C24 | Real Mistral executed; token→EvidenceRecord brittle | Token/event + governed LM (no Phase) | RESOURCE_BLOCKED / IMPLEMENTED | Mistral-7B reported |
| C25 | Window beats phase & quad (toy) | separate toys | SYNTHETIC_PROBE | 60 steps, 1 seed |

## 2. The 13 reconciliation questions

1. **Did Phase improve language modeling?** YES, but only at ~2M-param micro-scale as a **fluency** effect (C4: 72.8±16.8 vs 118.3±8.2 PPL, 3/3 seeds). No larger-scale Phase PPL exists in the repo.
2. **Long-range retrieval beyond the window?** **NOT DEMONSTRATED; contradicted where tested** (C5, C9). The only positive is a synthetic cue probe (C8) that fails to transfer to language; the actual hybrid scored **0%** (C3).
3. **Entity–attribute binding?** **NO** (C7; NL `entity_binding` B−A=−0.01).
4. **Slots — single-fact recall?** **YES but fragile** (1/3 seeds, single-fact; C6), plus independently validated slot *survival* (C14).
5. **Slots — relational tasks?** **NO** in the learned micro-scale ladder (C7); "yes" only in the **deterministic** governance study, which has **no Phase and no learned model** (C15–C16).
6. **Quadratic reader — measurable value?** **PARTIAL**, only in the synthetic enterprise study (C15). The decisive **Quad-reads-Phase-memory vs Quad-reads-raw-tokens** ablation was **never run**.
7. **Phase decorative / silently dominated?** **YES, repeatedly**, now conceded by the authors (C5, C9; falsification note "DECORATIVE"; v3 retires the superiority claim).
8. **Constant recurrent-state decode?** **Implementation-dependent:** true for pure/lightweight Phase; **false** for the shipped `BindingCacheTransformer` / `HybridPhaseTransformer` with `local_layers>0`.
9. **Full-prefix replay?** **YES — the shipped hybrid's default decode path** (verified firsthand, `phase_transformer.py:7746-7752`).
10. **Trained at meaningful scale?** **NO.** Every executed result is micro-scale; no committed checkpoints/logs; "7B" is a recipe only.
11. **Reproduced across seeds?** **YES for four studies (3 seeds each) — and those are the ones that falsify Phase.** The positive slot needle is **1/3 seeds**; the enterprise pilot ran seed 0 only.
12. **Valid after fidelity corrections?** Valid: (a) Phase micro-scale fluency gain; (b) bounded-state / no-N×N deployment properties of the **clean** arms; (c) **slots, not Phase**, carry fragile single-fact recall; (d) Phase adds no retrieval / is ablation-neutral; (e) the deterministic governance results (no Phase). Invalidated: the Protected-Phase-superiority / decay-tax narrative and any transfer of the synthetic needle to language.
13. **Obsolete evidence?** Reimplemented Phase core (no normalizer) **discarded**; the "6 Phase + 6 Quad" 12-layer model **never existed**; v1/v2 "HybridPhaseTransformer as product" **superseded by v3**; lightweight C8 superseded for external validity by C9; "35 VALIDATED" matrix obsolete/misleading.

## 3. Reconciled contradictions (optimistic briefs vs skeptical assessments)

- **A — "100% needle / removes decay tax" (v1/v2) vs "adds NO retrieval" (executed).** The 100% is real but on a **synthetic single-key copy** with a tiny pure-phase model; it does **not** transfer to language or to the hybrid (hybrid needle 0%). v3's ledger now marks the product-superiority claim **RETIRED** and the enterprise claim **UNSUPPORTED**. The briefs and assessments do not disagree about the *data* — v1/v2 over-generalized a mechanism probe into a product claim, which v3 retracts.
- **B — +0.741 vs ≈0 "B−A" retrieval.** +0.741 is a controlled synthetic cue task (short context, single-token answers); under NL multitask the same frozen Phase collapses to chance and is ablation-neutral. Cleanest internal demonstration that Phase's "retrieval" is a **probe artifact**, not a language capability.
- **C — "serial beats stacking / no silent domination" vs measured decorativeness.** Serial fusion is implemented but its *advantage* is unmeasured; the anti-domination claim is contradicted by decorative-Phase ablations. v3 concedes both.
- **D — "Full end-to-end hybrid [MEASURED]" vs "no trained-LM evidence."** "[MEASURED]" means *the classes instantiate and harnesses run* — existence, not quality; the comparative doc labels every hybrid retrieval/PPL cell **[ROADMAP]**.
- **E — "35 VALIDATED (97%)" vs "validates string presence / arithmetic."** The skeptic is correct on the mechanics (confirmed at the cited test lines); "97% validated" is a documentation-integrity metric, not model evidence.

## 4. Verification against saved reports (this audit)

Feasible checks were run on CPU-only hardware (see `docs/audits/hybrid_llm/verify_hybrid_llm_audit.py` and
the completion report). **The two load-bearing complexity claims were verified firsthand by reading the
source:** `BindingCacheQuadQuery` materializes `[B,H,N,N]` scores *before* Top-K
(`phase_transformer.py:3686`, value tensor `[B,H,N,N,D_h]` at :3731), and `HybridPhaseTransformer` decode
falls back to **full-prefix replay** for `local_layers>0` (`:7746-7752`). Large-scale training and GPU
runs were **not** undertaken (out of scope and infeasible on available hardware); the RM1 real-Mistral
harness is **RESOURCE_BLOCKED** in-sandbox. These limitations are recorded honestly and do not affect the
directive-level conclusions, which rest on the committed multi-seed studies and the repo's own v3
ledger.

## 5. Bottom line

- The **only** positive, multi-seed, real-corpus Phase result is a **perplexity/fluency gain at ~2M
  params** (C4). Everything framed as Phase *retrieval superiority* is a synthetic probe (C1, C8),
  contradicted at the mechanism level (C5, C9, C10), or retired by the authors (C11).
- The long-range capability that appears is carried by **bounded slots, not Phase**, is **single-fact
  only**, and forms in **1/3 seeds** (C6).
- The strongest validated results (C14–C21) are the **deterministic governance layer** and contain **no
  Phase and no trained hybrid**.
- **No hybrid was trained at meaningful scale; no checkpoints/logs are committed; the decisive
  Quad-reads-memory-vs-tokens ablation was never run; the shipped hybrid's decode uses full-prefix
  replay.**
- The repository's **own v3 brief and claim ledger already converged on this skeptical reading.** This
  ledger corroborates it and supplies the evidentiary basis for the Phase-exclusion directive.
