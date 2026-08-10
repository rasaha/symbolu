# Hybrid LLM vNext — Architecture Decision

**Audit date:** 2026-08-03 · Machine-readable twin: [`artifacts/hybrid_llm_decision_matrix.json`](artifacts/hybrid_llm_decision_matrix.json)

**Maturity of this document: ARCHITECTURE_SELECTED → EXPERIMENT_REQUIRED.** This selects a canonical
architecture and topology on the current evidence; it does **not** assert production readiness, model
superiority, or state-of-the-art status. Packaging remains gated (see Packaging Readiness).

## 1. Binding directive applied

Per the binding architectural directive, the existing **Phase O(n)** mechanism is
`RESEARCH_ONLY / LEGACY_BENCHMARK / EXCLUDED_FROM_PACKAGING`. The verdicts `RETAIN_CURRENT_PHASE_CORE`,
`MODERNIZE_PHASE_CORE`, `PHASE_AS_OPTIONAL_AUXILIARY`, and `PHASE_PLUS_DELTA_CORE` are **removed from the
eligible set**. Phase is scored **nowhere** in the decision matrix; it appears only as the historical
baseline the replacement must outperform or avoid. The evidentiary basis is in the Internal Evidence
Ledger (Phase = micro-scale fluency only; no retrieval; decorative; shipped hybrid decodes by full-prefix
replay) and the Common Notation document (Phase is a strictly weaker special case of the modern delta-rule
family with no erase/correction and no kernel path).

## 2. Hard selection gates (applied to the winner)

| # | Gate | KDA-MLA hybrid |
|---|---|---|
| 1 | Exact algorithm definition | ✅ channel-wise gated delta rule + DPLR transition; MLA global (primary source) |
| 2 | Non-quadratic benefit | ✅ 3/4 layers are bounded-state KDA (no N×N) |
| 3 | Retained expressive path | ✅ periodic MLA preserves exact global attention |
| 4 | True incremental decoding | ✅ KDA layers O(1) recurrent; MLA compressed-KV; no full-prefix replay |
| 5 | Training path | ✅ bespoke chunkwise DPLR algorithm; FLA kernels |
| 6 | Kernel path | ✅ FLA + vLLM + SGLang (production) |
| 7 | Evidence | ✅ trained-LM at 48B-A3B / 5.7T tokens, matches/surpasses full attention (reported by primary source) |
| 8 | Falsifiability | ✅ matched baseline + causal ablation plan defined (Falsification Plan) |
| 9 | Packaging boundary | ✅ model core separable from Agent Runtime / governance / handover |
| 10 | Licensing | ✅ MIT weights + kernels |

The fallbacks also pass all gates except differentiation. **GDN-2 fails gate 10 (non-commercial license)
and is weak on gate 7 (single 1.3B point) / reproducibility (no checkpoints)** — hence excluded as the
*current* pick despite being latest.

## 3. Weighted decision (max 500)

| Candidate | Weighted total | % |
|---|---|---|
| **KDA-MLA hybrid (Kimi Linear)** | **449** | **89.8** |
| Gated DeltaNet hybrid (Qwen3-Next) | 422 | 84.4 |
| Conventional attention hybrid (fallback) | 392 | 78.4 |
| Gated DeltaNet-2 hybrid | 376 | 75.2 |
| Mamba-3 hybrid | 374 | 74.8 |
| Lightning Attention hybrid | 343 | 68.6 |

Weights are the prompt's suggested weights (unmodified — not tuned to favor any candidate; Phase is not a
candidate). Per-criterion scores and rationale are in the JSON.

### Sensitivity analysis (does the winner change?)
- **Quality-first:** KDA stays co-leader; conventional attention and GDN-2 rise to parity — winner could shift to the fully-open conventional hybrid or (license-blocked) GDN-2.
- **Efficiency-first:** KDA and Mamba-3 lead; conventional attention collapses (unbounded KV). KDA robust.
- **Low-compute-first:** **GDN wins** (most reproducible, easiest to train small, default kernels) — this is why GDN is the designated low-compute fallback / experiment starting point.
- **Novelty-first:** GDN-2 wins but is **unpackageable** (non-commercial license, no checkpoints) — novelty is not decisive.
- **Enterprise-memory-first:** the **bounded-slot sidecar** becomes the differentiator over any open backbone; KDA remains the top recurrent option.

**Robustness:** KDA is first or co-first under every weighting except low-compute (GDN) and novelty (GDN-2,
blocked). GDN is the natural fallback because it is in the same family and dominates the low-compute view.

## 4. Verdict

- **Primary architecture verdict: `SELECT_KDA_HYBRID`.**
- **Fallback 1: `SELECT_GATED_DELTANET_HYBRID`** — lower-risk, most mature, best low-compute score; adopt if KDA's DPLR kernels or complexity prove impractical at the first training scale.
- **Fallback 2: `SELECT_CONVENTIONAL_ATTENTION_HYBRID`** (Candidate G) — if **no** recurrent candidate clears the acceptance thresholds.
- **Adopt-later target: Gated DeltaNet-2** — its decoupled channel-wise erase/write is the capability frontier; revisit once a commercial license and released checkpoints exist.

### Specification
| Field | Decision |
|---|---|
| Canonical sequence mixer | **Kimi Delta Attention (KDA)** — channel-wise gated delta-rule linear attention |
| Full-attention mechanism | **Multi-head Latent Attention (MLA)** as the periodic global layer (GQA/SWA acceptable fallback) |
| Layer ratio | **3:1 (KDA : MLA)** — matches Kimi Linear / Qwen3-Next evidence |
| Local-window policy | Optional SWA inside KDA layers; not required (KDA already bounded) |
| Topology | **Candidate C** (KDA + periodic MLA) as canonical core; extensible to **Candidate E** (+ bounded-slot enterprise-memory sidecar) **only if slots pass their thresholds** |
| Bounded-slot disposition | **`EXPERIMENT_REQUIRED` → `OPTIONAL_ENTERPRISE_MEMORY`** — independent of the backbone; backbone must not depend on slots for basic LM |
| Phase disposition | **`RESEARCH_ONLY` / `EXCLUDED_FROM_PACKAGING`** |
| MoE disposition | **OPTIONAL / DEFERRED** — first model dense; MoE is a scaling decision |
| Training objective | `L_LM` required; auxiliary retrieval/binding/path-balance losses required **only if** slots retained (to prevent path domination); details in the Falsification Plan |
| Cache/state contract | KDA layers: true O(1) bounded recurrent state; MLA layers: compressed-KV cache; **no full-prefix replay; no N×N in linear layers** |
| Inference target | vLLM / SGLang via FLA kernels |
| First model scale | Modest **dense ~150–350M** for the decisive experiment |
| First training scale | Matched **~15B tokens** (aligned with the July-2026 comparative study), matched tokenizer/data order, ≥5 seeds for threshold-sensitive tasks |
| Fallback architecture | GDN hybrid → conventional attention hybrid |

## 5. Ugence differentiation (why this is not merely renamed public work)

Adopting KDA-MLA as the *sequence mixer* is deliberately **non-novel** — it buys a proven, licensable,
kernel-mature core instead of re-litigating a mechanism the Phase era already failed to validate. Ugence's
**technical differentiation moves up the stack**: the **governed bounded-slot enterprise memory** (source,
version, supersession, inspectable slots — the clean `BoundedBindingSlots` capability the public cores do
*not* expose) plus the existing governance / handover / control-plane systems. That is a defensible product
reason for the composed topology (Candidate E) without pretending the sequence mixer is novel. The slot
layer is gated behind its own evidence thresholds precisely so the differentiation claim stays honest.

## 6. What this decision is NOT

It does not authorize packaging, reimplementation, or the decisive experiment (H22). It does not claim KDA
will win at Ugence's scale — the matched experiment must confirm that, including against the conservative
conventional-attention fallback and the historical Phase baseline (as a non-candidate reference). It does
not adopt GDN-2 despite it being latest, for the license/evidence reasons above.
