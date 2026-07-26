# Hybrid LLM (Phase + Quadratic Attention) — Falsification-First Assessment

**Status:** Investigation only. No architectural changes made.
**Repo:** `rasaha/symbolu` · **Branch:** `claude/hybrid-llm-falsification-l9jw8h`
**Method:** Evidence gathered from implementation (`symbolu/phase_transformer.py`),
tests, stored `results/*.json`, design/pitch docs, and git history. Marketing/design
prose is treated as an unproven claim until corroborated by executable evidence.

Evidence tiers used throughout: *implemented · unit-tested · synthetic-probe ·
trained-LM · enterprise-data · proposed-only · contradicted*.

---

## 1. Executive verdict

The repository **implements** two related hybrids and a genuine O(n) "Phase" linear
attention, but it **does not implement the "6 Phase + 6 quadratic" 12-layer model
described in the prompt**, and it has **no trained-language-model evidence** that the
Phase/Quad combination is load-bearing. The strongest *measured* result is a memory
scaling property on a tiny model; the flagship retrieval numbers are on a ~240K-param
synthetic pure-phase toy; and the **actual hybrid checkpoint scored 0% on needle
retrieval**. The authors' own code comments admit that when Phase is mixed with Quad it
becomes **"decorative" (~0% ablation drop)** — i.e. silent domination was observed, and
the "protected" wiring is an attempted fix whose benefit is explicitly on the roadmap,
unmeasured. There are **no saved checkpoints, no training logs, and no head-to-head
compute-matched comparison** for the hybrid.

**Overall recommendation: MODIFY (de-risk before any scale-up).** Do not strengthen any
claim beyond "O(n) linear-attention memory complexity is implemented and its per-token
memory growth was measured on a small model." Everything above that is unproven or, for
the hybrid needle result, contradicted.

---

## 2. What is actually implemented

Two distinct model families live in `symbolu/phase_transformer.py` (11,298 lines,
imported wholesale in a single 7,385-file bulk commit — git history shows **no**
incremental experimental progression despite the `V9/V10/V11` comment narrative).

**A. `HybridPhaseTransformer` — Local + Phase (no quadratic softmax at all).**
- Early `local_layers` (default **4**) = sliding-window local attention only.
- Later layers = `HybridTransformerBlock` = **parallel blend** of local + Phase
  (`alpha_local=0.8`, `alpha_phase=0.2`).
- There is **no quadratic/softmax-over-tokens path** in this model. The word "hybrid"
  here means *local ⊕ linear-phase*, not *phase + quadratic*.

**B. `BindingCacheTransformer` — protected serial composition (this is where "Quad" lives).**
Every layer is a `BindingCacheBlock` running **three paths serially over one state**:
1. `LocalWindowAttention` — sliding window (syntax).
2. `BindingCachePhaseState` — Phase writes an O(n) memory state:
   `k_phasor = polar(a_k, -φ_k); memory = cumsum(k_phasor · v)` (or EMA with learned decay).
   Outputs **only** memory, no attention output.
3. `BindingCacheQuadQuery` — Quad **reads Phase's memory** (Q from tokens; **K,V from
   `memory_state`, not raw tokens**), via `Q@Kᵀ` softmax. Default uses Top-K value
   selection; `use_cache=False` gives full dense O(n²) softmax.
- Output = `local_out + mem_out`. `proposal_mode` (Quad proposes, Phase integrates) and a
  confidence-based conditional skip (`confidence_threshold`) also exist.
- `BindingCacheTransformer` stacks these **homogeneously** — **not** a 6+6 split.

**Core Phase mechanism (`PhaseAttentionLayer`)** is genuine O(N) complex linear attention:
`State = CumSum(K·V); Out = Re(Q·State)`. This is a linear-transformer/RWKV-family
recurrence with complex (phase) keys — *implemented and correct by construction*.

**Important nuance on "quadratic":** even in the default Top-K "cache" mode,
`BindingCacheQuadQuery` materializes the full `[B,H,N,N]` score matrix
(`scores = Q @ Kᵀ`) before selecting Top-K. So it is **O(n²) in score compute/memory**;
the Top-K only reduces the value gather. It is *not* an O(n·k) reader end-to-end, and the
"O(1)/bounded-state" inference story does not survive it (see §5, §10).

---

## 3. What is actually proven

| Property | Verdict | Basis |
|---|---|---|
| Phase = O(n) causal accumulation | **PROVEN (as complexity)** | `cumsum`/EMA of complex phasors, verified in code; ~1.02× per-token memory scaling measured on a tiny model (`PHASE_ATTENTION_VALIDATION.md`). |
| Persistent state across chunks (mechanics) | **PROVEN (mechanically)** | `test_phase_attention_kv_cache.py`: constant `memory_bytes()` across 200 tokens; chunk-carry via `forward_chunked_tbptt`. |
| End-to-end hybrid stack exists & is runnable | **PROVEN (existence only)** | Classes import and instantiate; harnesses run. Says nothing about quality. |
| Incremental-decode correctness | **PROVEN, but by full-prefix replay** | `<1e-6` match holds *because* the hybrid path "falls back to exact full-prefix replay when Local layers are active" — i.e. O(N) work, not O(1) decode. |

That is the entire proven set. All of it is complexity/bookkeeping — **none of it is
answer quality, retrieval, or a demonstrated benefit of coexistence.**

---

## 4. What remains unproven (or is contradicted)

- **10K needle retrieval "100%"** — asserted in the paper abstract/summary but **absent
  from the paper's own §4.3 results table** (no accuracy value shown at 10K). *Not
  supported; borderline falsified-as-stated.*
- **Needle on the actual hybrid** — measured **0%** on the shipped Hybrid checkpoint
  (`PHASE_ATTENTION_VALIDATION.md`), attributed to undertraining (PPL≈120). *Contradicted
  at current training.*
- **Language-model perplexity / competitiveness** — best hybrid ≈ **PPL 120 (tiny,
  undertrained)**; authors concede Phase "underperforms on WikiText language modeling."
  The only real-corpus PPL numbers in the repo (wikitext2 ≈ 5.14) belong to **different
  mechanisms** (a frozen-Mistral-7B FSCS routing gate, and CTM+ retention), not to
  Phase/Quad, and the gate produced **~0% perplexity change**. *Not supported.*
- **Phase-ablation degradation ("protected −50% vs mixed ~0%")** — stated in class
  docstrings; **no stored ablation experiment exists** (`phase_ablation.py`'s `__main__`
  only prints usage). *Empirically unrun (ROADMAP).*
- **Phase diversity / collapse resistance** — monitoring metrics (`R_k`, `R_q`) and an
  init trick exist; no result showing collapse is actually resisted in training. *Plausible, unshown.*
- **99% memory reduction / 30× vs O(n²)** — true for *pure-phase state size* by algebra,
  and partly measured (9.3 GB @ 32K on tiny model); but the O(n²) baseline (276 GB) was
  **computed, not run** ("would OOM"), and the *actual hybrid* Quad path still
  materializes `[B,H,N,N]`. *Provisionally supported for pure-phase only.*
- **6+6 split, enterprise-document understanding, compute advantage, matched-param
  head-to-head** — uniformly `[ROADMAP]`/unrun. *Not supported.*

The one head-to-head benchmark that exists (`results/three_attention_benchmark`) is a
**60-step, 3-layer, d=128, CPU, synthetic (`vocab_size=0`)** toy with near-chance accuracy
where **sliding-window attention beats both phase and quadratic**, and no hybrid is tested.

The "35 VALIDATED (97%)" claims-matrix figure is misleading: `test_claims_validation.py`
and `test_unvalidated_claims.py` validate **string presence** (`"cumsum" in source`,
`"25x" in file`) and **marketing arithmetic** (`$0.03/$0.001 == 30x`,
`175e9/7e9 == 25.0`) — **not** model performance. They never run the needle test nor
assert any accuracy value. The only genuine runtime measurements in those suites concern a
pure-Python router's latency/determinism, unrelated to the LLM.

---

## 5. Phase's demonstrated role

- **Demonstrated:** an O(n) content-addressable **write/accumulate** primitive
  (associative memory via complex phasor cumsum) with constant per-step state in the
  *pure-phase* configuration; a single synthetic 2K single-key→value copy task reaches
  100% on a 240K pure-phase model.
- **Not demonstrated:** that Phase carries language modeling, that it retains long-range
  *linguistic* evidence (vs a controlled synthetic key), or that it is essential in the
  hybrid. A controlled needle/copy result is evidence of **retrieval capacity on a probe**,
  **not** general long-range language understanding — the repo's own hybrid needle score
  (0%) makes this gap explicit.
- **In the shipped hybrid, Phase's inference-memory advantage evaporates:** the default
  (`local_layers>0`) cache retains the **full O(N) token buffer** and decodes by
  full-prefix replay (per the KV-cache test's own assertions).

## 6. Quadratic attention's demonstrated role

- **Implemented:** genuine `Q@Kᵀ` softmax that reads **Phase's compressed memory**
  (content-addressable retrieval over state), with an optional Top-K value read and a
  proposal/gating mode. This is the *composition* mechanism (K,V from memory_state) — the
  interesting part of the design.
- **Not demonstrated:** that Quad recovers detail Phase compresses away, that it performs
  binding/contradiction/multi-hop, or that it beats reading raw tokens. **The single most
  important experiment (§13) — Quad-reads-Phase-memory vs Quad-reads-raw-tokens — has
  never been run.** Without it there is no evidence the two mechanisms *compose* rather
  than merely coexist.
- Do **not** describe the default path as "full quadratic attention over the sequence": it
  is quadratic **over Phase memory**, and the authors' comment concedes it makes Phase
  decorative unless artificially protected.

## 7. Do they meaningfully coexist?

Assessed against the six criteria; each independently:

| Criterion | Status | Evidence |
|---|---|---|
| 1. Distinct roles | **Designed, not shown** | Roles are wired (compress / retrieve / syntax) but never measured as separable. |
| 2. Causal dependence (ablation) | **Not shown** | No ablation artifact; the −50%/0% figures are docstrings, not results. |
| 3. Information transfer | **Implemented** | Verified: Quad's K,V are projected from `memory_state`. Benefit unproven. |
| 4. No silent domination | **Contradicted** | Authors' own comment: "When mixed with Quad, Phase shows ~0% drop (DECORATIVE)." Domination was observed; "protected" wiring is the unvalidated workaround. |
| 5. Net benefit vs matched baselines | **Not shown** | No compute-matched Phase-only / Quad-only / hybrid comparison exists. |
| 6. Scaling plausibility | **Not shown** | Only tiny/synthetic; hybrid needle 0%; no real-corpus PPL. |

**Conclusion:** coexistence is *architecturally instantiated* (criterion 3) but
**empirically unsupported**, and criterion 4 is actively contradicted by the authors' own
notes. As of today the mechanisms **coexist; they are not shown to compose.**

## 8. Assessment of the 6+6 design

- **The 6+6 Phase/quadratic split is not implemented anywhere.** The only "6+6" reference
  is a *paper recommendation* ("Layers 1–6 Local, 7–12 Phase") — and even that is
  **Local/Phase, not Phase/Quadratic**. The shipped defaults are **4 local + 8 hybrid**
  (46M) and **16 local + 16 hybrid** (7B recipe). Quad is a conditional branch *inside*
  hybrid layers, not a 6-layer bank.
- **No principled justification exists in the repo.** The intuition in the prompt
  (early=lexical/syntax, middle=entities/relations, upper=integration; Phase-then-Quad so
  Quad refines compressed evidence; risk that late Phase layers blur precise relations) is
  reasonable *a priori* but **untested here**. A fixed split is the weakest option on
  first principles: whether the boundary should be learned, conditional, or task-dependent
  is exactly what the ablation matrix (§13) must decide.
- Of the six interpretations in the prompt, the repo realizes **D (protected serial
  composition)** and **E (parallel blend, for Local+Phase)**, with partial **F
  (confidence-gated Quad skip)**. **A/B/C (stacked/interleaved Phase-vs-Quad) are absent.**

## 9. Best architecture recommendation

Ranked by what the evidence will actually support:

1. **Strongest *defensible* baseline today:** a **sliding-window + linear-recurrent
   hybrid** — the established Samba/Griffin/Jamba family. Sliding window won the only
   head-to-head benchmark in this repo; linear recurrence gives the O(n) memory. "Phase"
   is *one* complex-valued parameterization of the linear-recurrent slot and must first be
   shown to **beat a plain linear-attention/Mamba slot at matched compute** before it earns
   its complexity.
2. **Most principled of the novel proposals:** **Design D (protected serial** — Phase
   writes memory → local/Quad reads it → fused residual). It is the only design that
   structurally prevents the decorativeness the authors observed. Adopt it **only if** the
   decisive ablation (§13) shows Quad-reads-memory ≻ Quad-reads-tokens.
3. **Design F (conditional Quad escalation)** is attractive for inference cost but is
   premature: it presupposes a working Phase confidence signal, which is unvalidated.
4. **Reject a *fixed* 6+6 Phase/Quad split** as the headline architecture — it is
   unimplemented, unjustified, and mislabels the mechanisms actually present.

## 10. Enterprise-data training feasibility

Separate the two objectives the prompt rightly distinguishes:

- **Domain learning (knowledge into weights):** standard and viable via continued
  pretraining / SFT / LoRA on enterprise corpora — but this is a property of *transformers
  in general*, not of Phase. Phase offers **no demonstrated advantage** for memorizing
  enterprise knowledge into parameters, and quadratic/softmax layers are the more direct
  route to loss (which is exactly why Phase went decorative). **LoRA/adapters on a strong
  pretrained base is the pragmatic path**; a from-scratch Phase model is not justified by
  current evidence.
- **Evidence use (facts from long docs at inference):** this is where an O(n) memory +
  retrieval hybrid *could* help — but the repo shows **0% on its own hybrid needle** and
  no enterprise-document task, dataset, or score anywhere. For evidence-use today,
  **retrieval-augmented generation over a conventional long-context model is the safer
  bet**; Phase/Quad is a research candidate, not a product-ready mechanism.

Note the productization has in fact **pivoted** to a different, unrelated governance
product ("ActionGate Context Minimization"); the Phase/Quad LLM is not the shipping
artifact.

## 11. Required loss and curriculum

Because next-token cross-entropy lets the quadratic/softmax route dominate (observed here),
a working hybrid almost certainly needs auxiliary objectives. Current status:

| Term | Purpose | Status in repo |
|---|---|---|
| `L_LM` | next-token | present |
| `L_retrieval` | force distant-evidence retrieval | `retrieval_loss_weight` hook exists; **not trained/validated** |
| `L_memory` | reconstruct/preserve facts in Phase state | proposed-only |
| `L_ablation` | keep each path causally useful (e.g. stochastic path-drop) | **not present** — this is the key missing anti-domination loss |
| `L_diversity` | prevent phase-head collapse | monitored (`R_k`), not enforced as loss |
| `L_binding` | connect entities/values/dates/sources | proposed-only |

**Curriculum:** short-context LM warm-up (protect fluency) → synthetic
retrieval/binding/ordering tasks with `L_retrieval`+`L_ablation` active → long-context
curriculum (2K→8K→16K) → enterprise multi-doc SFT. A **short-context control** must run
throughout so long-range gains are not bought with degraded ordinary language quality.

## 12. Experiment matrix (minimum credible)

Scale: **30M–150M params, 12 layers, matched hidden dim & param budget, matched-FLOP**
where possible, identical tokenizer/corpus, **≥3 seeds** for decisive cells. Contexts:
**512 / 2K / 8K / ≥16K**, plus a 512 short-context control.

Arms: `12Q` · `12P` · `6P→6Q` · `6Q→6P` · `P/Q interleaved` · `6 local + 6 protected
hybrid` · `12 protected hybrid` · `conditional Phase→Quad` — plus **sliding-window-only**
and **sliding-window+linear (Samba-style)** as the honest external baselines.

Tasks: (1) LM perplexity; (2) exact distant-key retrieval; (3) multiple needles;
(4) conflicting-evidence resolution; (5) ordered-event reconstruction; (6) key–value
binding; (7) multi-document policy QA; (8) evidence/source-position recovery;
(9) distractor resistance; (10) enterprise-style long-form continuation.

## 13. Ablation matrix (the decisive ones)

Run at minimum: Phase disabled · Quad disabled · **Phase state detached** ·
**Quad reads raw tokens instead of Phase memory** · Phase‖Quad (parallel) vs Phase→Quad
(serial) · fixed 6+6 · conditional-skip disabled · random Phase state · shuffled Phase
positions · equal-compute quadratic baseline · equal-param Phase baseline.

> **The single most important comparison:** *Quad reading Phase memory* **vs** *Quad
> reading raw token states*, at matched compute. If Quad-on-tokens ≥ Quad-on-memory, the
> mechanisms **do not compose** and the hybrid collapses to "quadratic model with a
> vestigial phase residual" — which is precisely what the authors' own "decorative"
> comment predicts. This ablation must precede any scale-up.

## 14. Risks and failure modes

- **Silent domination (observed):** softmax path learns faster; Phase becomes decorative.
  Mitigation: protected serial wiring + `L_ablation` + gradient-norm/branch-output
  monitoring by layer.
- **Retrieval-capacity ≠ language understanding:** synthetic needle success oversells; the
  hybrid's own 0% needle shows the gap. Always pair probes with real-corpus PPL and a
  short-context control.
- **Memory-claim erosion:** the O(1)/O(n) inference story fails for the shipped hybrid
  (full token buffer + N×N Quad scores). Any "99% reduction" claim must be *measured on the
  exact deployed config*, not on pure-phase algebra.
- **Phase collapse / norm growth:** `cumsum` grows norms O(√N); RMSNorm patches exist but
  collapse resistance is unproven under real training.
- **Provenance fragility:** the two real-model result files are self-labeled post-hoc
  reconstructions from terminal logs; no checkpoints/logs are committed. Reproducibility is
  not established.
- **Claim inflation via proxy tests:** "VALIDATED" in the matrix means a string/arithmetic
  proxy passed, not that a model demonstrated the number.

## 15. Go / modify / reject recommendation

**MODIFY — de-risk, do not scale.** The mechanisms are real and the protected-serial idea
is coherent, but every load-bearing performance claim is unproven or contradicted, and the
"6+6 Phase/quadratic" headline is not even implemented. Neither GO (no trained-LM
evidence, hybrid needle 0%) nor full REJECT (the O(n) primitive is sound and the
composition question is genuinely open and cheaply testable) is warranted.

## 16. Exact next implementation step

Build the **compose-vs-coexist ablation harness** at 30–150M / 12 layers, matched
compute, ≥3 seeds, and run exactly two arms first on a real tokenized corpus (not
synthetic `vocab_size=0`): **(a) Quad reads Phase memory** vs **(b) Quad reads raw token
states**, reporting LM perplexity + distant-key retrieval + the short-context control,
with per-branch gradient-norm and ablation-delta logging. Commit the checkpoints and raw
JSON. This is the smallest experiment that can falsify or support the core "they compose"
hypothesis before any further architecture work.

---

> The evidence currently supports a **sliding-window + linear-recurrent hybrid (Samba/
> Griffin family), with the protected-serial "Phase-writes / reader-reads-memory"
> composition as the most principled novel candidate**, because that is the only design
> that is both implemented and structurally guards against the silent Phase domination the
> authors themselves recorded — while sliding-window alone already beat both mechanisms in
> the sole head-to-head benchmark.
>
> The 6+6 Phase/quadratic proposal is **unsupported** (unimplemented, unjustified, and
> mislabeled — the repo's "6+6" is a Local/Phase recommendation, not Phase/Quadratic, and
> was never ablated).
>
> The next decisive experiment is the **matched-compute "Quad-reads-Phase-memory vs
> Quad-reads-raw-tokens" ablation at 30–150M on a real corpus**, and the claim should not
> be strengthened until **the hybrid beats compute-matched Phase-only, Quad-only, and
> sliding-window baselines on both real-corpus perplexity and distant-evidence retrieval,
> across ≥3 seeds, with committed checkpoints and logs.**
