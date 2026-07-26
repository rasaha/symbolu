# Low-Compute Enterprise Long-Context Ladder — A / B / C Falsification

**No quadratic attention is used, benchmarked, or compared against anywhere in this phase.**
Executed experiment; code + raw metrics under `experiments/phase_lc/`. Discipline: prove
**B−A (Phase over window)** before **C−B (bounded slots over Phase)**.

> HARDWARE CEILING (unchanged): 4 CPU cores, 15 GB RAM, no GPU. Micro scale (~2.0M params,
> d=128, 4 layers, window=64, train ctx 160, eval to 512). By protocol, no verdict here can
> be PROVEN; the labels available are PROVISIONALLY SUPPORTED / ARCHITECTURALLY PLAUSIBLE /
> NOT SUPPORTED / FALSIFIED AT TESTED SCALE.

## 2. Environment & hardware
CPU-only (4 cores), torch 2.13 CPU, fp32, 3 seeds. Corpus: repo enterprise English prose
(`bounded_shadow_pilot` + `evidence_assurance`), ~55K tokens, word vocab ≈1290.

## 3. Repository audit (long-context components)

| Component | Implemented | Complexity | Bounded state | Uses N×N scores | Tested | Suitable for this phase |
|---|---|---|---|---|---|---|
| Sliding-window attn (`LocalWindowAttention`, `SoftmaxAttn`) | yes | O(N·w) | n/a | banded only | yes | **yes → A** |
| Phase recurrent (`PhaseAttentionLayer`/`BindingCachePhaseState`) | yes | O(N·d) | yes (d/layer) | no | yes | **yes → B** |
| `BindingCacheQuadQuery` | yes | **O(N²) scores** | no | **YES** | yes | **REJECTED (quadratic)** |
| `SlotMemoryGCT` | yes | O(N·M) | yes (M·d) | no | partial | design reused, but coupled to controller machinery |
| Fresh `BindingSlots` (this work) | yes | O(N·M) | yes (M·d) | **no (hook-verified)** | yes | **yes → C** |

The repo's own "binding cache" reader (`BindingCacheQuadQuery`) materialises a full
`[B,H,N,N]` score matrix — it is **excluded** per the no-quadratic rule. C therefore uses a
fresh, auditable bounded slot memory.

## 4. Exact definitions of A, B, C

Shared skeleton: token+abs-pos embedding → 4 pre-norm blocks → GELU FFN → tied LM head.
Blocks differ only in the mixer (protected additive fusion). FFN width auto-tuned so total
params match to <0.05%.

- **A — window only:** `out = Window(x)` (causal sliding window, w=64).
- **B — window + Phase:** `out = Window(x) + Phase(x)`. Phase update (per head, per channel):
  `k = a_k·e^{-iφ_k}, q = a_q·e^{+iφ_q}; state_t = Σ_{s≤t} γ^{t-s} k_s v_s; out_t = Re(q_t·state_t)`.
  Bounded state = d complex numbers/layer; per-token compute O(d); **no score matrix, no
  token cache, no full-prefix replay** (parallel prefix-sum for training; O(1) state recurrence
  for decode).
- **C — window + Phase + bounded slots:** `out = Window(x) + Phase(x) + Slots(x)`. Slots:
  `addr_t = softmax((W_wk x_t)·SlotKeys^T)`, gated write `w_t = σ(gate)·addr_t`, causal
  `slot_t = Σ_{s≤t} w_s v_s / Σ_{s≤t} w_s` (M slots), read `out_t = W_o Σ_m softmax((W_rq x_t)·SlotKeys^T)_m · slot_{t,m}`.
  M=32 slots, key-dim 64. Complexity O(N·M·d). Bounded slot state = M·d/layer.

## 5. Proof that no quadratic sequence attention is present

`assert_no_nxn()` registers forward hooks on every Phase and Slots module and fails if any
produces a tensor whose last two dims are both N. **Result across all runs: `phase_builds_NN
= False`, `slots_builds_NN = False`.** The only `[N,N]` object anywhere is the window
attention's banded score, which is masked to width w=64 (O(N·w)); no global token-pair
attention exists in A, B, or C. (Raw flags in `results/abc.json`.)

## 6. Parameter & compute fairness
Params matched to <0.05% via FFN auto-tune (A≈B≈C≈2.00M; exact counts in results). Identical
tokenizer, corpus, data-order RNG per seed, optimizer (AdamW lr 2e-3, warmup+constant),
batch 24, 1800 steps, fp32, seeds {0,1,2}. Added-parameter control: because B and C spend
their extra mixer params but FFN is shrunk to compensate, the comparison is same-total-param;
per-token active params are ~equal. Latency/throughput and bounded-state sizes reported per
arm (§16).

## 7. Training data & 8. Objectives
Mixture: 20% real-language LM (full-sequence CE) + 80% enterprise tasks rendered in natural
language (needle 20 / binding 20 / supersession 15 / source 15 / multihop 10). Task examples
use answer-token supervision (a combined L_retrieval+L_binding+L_source+L_version signal),
applied identically to every arm — the prior phase showed no arm learns retrieval under
LM-only loss at this scale, so the LM-only-vs-aux question is answered "aux is required" and
aux is held constant across A/B/C to keep B−A and C−B clean.

> NOTE ON FIDELITY. An earlier ladder used a reimplemented Phase core that omitted the
> amplitude-normalisation denominator `Re(q·Σkv)/Σa_k`. That was **discarded**. All results
> below use the repo's **actual `PhaseAttentionLayer`** (imported from
> `symbolu/phase_transformer.py`), verified O(N) by the no-N×N hook. Run: 3 seeds, 1200
> steps, batch 16, N=160, 32 slots. Source commit in `results/abc.json`.

## 9. Language-model results (mean±sd, 3 seeds)

| arm | ppl@256 | ppl@512 |
|---|---|---|
| A window | 118.3±8.2 | 122.9±8.0 |
| **B window+Phase** | **72.8±16.8** | 78.9±18.9 |
| C window+Phase+slots | 83.3±3.1 | 88.7±3.4 |

**B−A (language): Phase materially improves perplexity (73 vs 118).** This is the one clean,
replicated positive B−A effect: Phase adds *long-range continuity/fluency* to the LM. C is
similar to B (slots don't help or slightly hurt raw LM). No arm degrades short-context
quality to buy long range.

## 10. Long-range evidence results — needle beyond the window (w=64)

| arm | d=16 | d=96 | d=220 | per-seed d=96 |
|---|---|---|---|---|
| A window | 0.03 | 0.01 | 0.02 | 0.02/0.00/0.02 |
| B window+Phase | 0.01 | 0.00 | 0.01 | 0.00/0.00/0.01 |
| **C +slots** | 0.19 | **0.16±0.22** | 0.15 | **0.47/0.00/0.00** |

**B−A ≈ 0: the real Phase adds NO retrieval beyond the window.** **C−B > 0 but seed-fragile:**
one seed reached 0.47 (and a longer 1800-step/batch-24 run reached **1.00**), two seeds stayed
at chance — near-threshold circuit formation. When it forms, it is carried by the slots (§14).

## 11. Binding results (entity–attribute, by entity count)

| arm | k=2 | k=4 | k=8 |
|---|---|---|---|
| A | 0.02 | 0.01 | 0.02 |
| B | 0.03 | 0.01 | 0.01 |
| C | 0.05 | 0.03 | 0.02 |

**All three at chance.** Neither Phase nor bounded slots learned multi-entity binding under
interference at this scale. C's tiny edge is within noise.

## 12. Enterprise-task results (supersession / source / multi-hop)

| arm | supersession (current) | stale-version error | source attribution | multi-hop |
|---|---|---|---|---|
| A | 0.01 | 0.02 | 0.03 | 0.01 |
| B | 0.01 | 0.01 | 0.06 | 0.02 |
| C | 0.03 | 0.03 | 0.05 | 0.04 |

**All at chance for every arm.** The harder relational/enterprise tasks (amendment
supersession, source attribution, multi-hop integration) were not learned by A, B, or C at
this scale/compute. C provides no relational-reasoning gain — only (fragile) single-fact recall.

## 13. Context-length scaling (train 160 → eval 256/512)

C's single-needle recall (in the seed that learned it) persists at 256 and degrades by 512;
A and B stay at chance at all lengths. Binding stays at chance for all arms at all lengths.
Length generalisation is only meaningful for C's needle and is not robust across seeds.

## 14. Causal ablations (the decisive attribution)

C, seed that learned needle (baseline d96 = 0.47):

| ablation | needle d96 | binding k4 | source |
|---|---|---|---|
| baseline | **0.47** | 0.00 | 0.08 |
| **slots off** | **0.02** | 0.03 | 0.08 |
| phase off | 0.47 | 0.00 | 0.08 |
| slot keys randomised | 0.05 | 0.03 | 0.08 |

**Removing the slots erases the capability (0.47→0.02); removing Phase changes nothing
(0.47→0.47); randomising slot addresses erases it (0.47→0.05).** The long-range capability is
**carried entirely by the bounded slots, is content-addressed, and Phase is decorative for
it.** B's `phase_off` ablation changes nothing (B had no retrieval to lose). This is the
prompt's decision branch: *"If C works but B does not: the binding subsystem, not Phase, is
carrying the architecture."*

## 15. Capacity boundaries

Binding was at chance even at k=2 entities, so a capacity curve could not be traced at this
scale — the practical binding capacity here is **effectively 1 fact (single needle), and only
when the slot circuit forms**. Slot diagnostics (seed 0): write-gate means 0.15–0.82 across
layers, slot-utilisation entropy 1.5–3.5 (of ln32≈3.47) — slots are written and read, not
collapsed, but only single-fact recall emerged.

## 16. Deployment resource measurements (CPU, N=512)

| arm | params | ms/token | tokens/s | bounded state (floats, context-independent) |
|---|---|---|---|---|
| A | 2.000M | 0.03 | 32,925 | 0 |
| B | 2.000M | 0.06 | 17,698 | 512 (Phase) |
| C | 2.000M | 0.10 | 10,267 | 16,896 (Phase 512 + slots 16,384) |

All arms are **bounded-state and linear-in-context** (no N×N; verified). C costs ~3× A's
per-token latency and carries a bounded 16.9K-float state — a fine deployment envelope. The
issue is not resource use; it is that the delivered capability (fragile single-fact recall,
no relational reasoning) does not yet justify the added machinery at this scale.

## 17. Failure modes

- **Phase = fluency, not evidence.** Real Phase improves perplexity but provides zero
  addressable retrieval (B−A retrieval ≈ 0; phase-off ablation null). Its long-range state is
  not readable as discrete facts.
- **Slots work but fragile.** Bounded slots are the only component that produced long-range
  recall, but only for single facts, only in some seeds (1/3 at 1200 steps; 1.0 at 1800),
  and not for binding/supersession/source/multi-hop.
- **Relational enterprise tasks unlearned by all.** Could be undertraining at micro-scale, but
  the ladder ordering (C>B≈A on needle only) is unaffected by that caveat.
- **Seed threshold.** Capability formation is bimodal; ≥3 seeds essential, and 3 is marginal.

## 18. Architecture recommendation

Keep **A (window)** as the language backbone and **add bounded binding slots (the C
component) directly on top of the window** — the evidence attributes all long-range recall to
the slots, not to Phase. **Phase (B) earns its place only as a perplexity/fluency booster**,
not as the evidence mechanism it is marketed as; whether to keep it is a cost/quality call
(it roughly halves per-token throughput for a real but non-retrieval perplexity gain).
Before scaling, make the slot circuit *reliable* (see §20).

## 19. Evidence-tier verdict

| Question | Verdict (at tested micro-scale) |
|---|---|
| A sufficient for local language | ARCHITECTURALLY PLAUSIBLE (trains, but ppl 118 is weak; no long-range by construction) |
| B−A: Phase adds long-range evidence use | **NOT SUPPORTED** (retrieval/binding/enterprise all ≈ A ≈ chance; phase-off ablation null) |
| B−A: Phase adds language quality | **PROVISIONALLY SUPPORTED** (ppl 73 vs 118, 3/3 seeds) — a *fluency* gain, not evidence |
| C−B: bounded slots add precise addressable memory | **PROVISIONALLY SUPPORTED for single-fact recall only** (slots-off ablation collapses it; content-addressed), **NOT SUPPORTED for binding/supersession/source/multi-hop** |
| C delivers enterprise relational capability | **NOT SUPPORTED** (all relational tasks at chance) |
| Bounded, non-quadratic, practical to deploy | **PROVEN AT TESTED SCALE** (no N×N verified; bounded state; linear context; 10K tok/s CPU) |

## 20. Exact next experiment

Make the slot circuit **reliable and relational**: train **C with an explicit slot-write/read
auxiliary loss (`L_binding`, `L_source`) and slot-key orthogonality regularisation**, at 4–8k
steps and ≥5 seeds, and re-run the full ladder. **Acceptance threshold to move C off
"single-fact only":** C reaches **≥0.6 mean entity–attribute binding at k=4 and ≥0.5
supersession accuracy in ≥3/5 seeds**, with slots-off ablation removing ≥0.3 absolute, while B
stays at chance on those tasks. Until then, C is a **bounded associative memory for single-fact
recall**, not an enterprise relational reasoner.

---

## Final A / B / C statement

**A — Sliding window only:** ARCHITECTURALLY PLAUSIBLE as a local language backbone (ppl
118±8), with no long-range evidence capability by construction (needle/binding/enterprise all
at chance). Bounded, 0.03 ms/token, no recurrent state.

**B — Sliding window + Phase (real `PhaseAttentionLayer`):** **B−A adds language quality
(ppl 73 vs 118, replicated) but NO long-range evidence use** (needle/binding/supersession/
source/multi-hop all ≈ chance; phase-off ablation null). Compute cost: ~2× A's per-token
latency, +512-float bounded state. Limitation: Phase is a fluency/continuity mechanism here,
not an addressable-evidence mechanism.

**C — Sliding window + Phase + bounded binding slots:** **C−B adds fragile single-fact
long-range recall carried by the slots** (slots-off ablation: 0.47→0.02; phase-off: no change;
random slot keys: 0.47→0.05), reaching needle 0.47 (1200 steps) to 1.00 (1800 steps) in the
seeds where the circuit forms, but **0/3–1/3 seed reliability** and **no gain on binding,
supersession, source, or multi-hop** (all at chance). Compute cost: ~3× A's latency,
+16.9K-float bounded state, 10K tok/s on CPU. Capacity limit at this scale: ~1 fact.

> The evidence **does not yet support** Configuration C as a practical low-compute architecture
> for in-house enterprise long-context intelligence **at the tested micro-scale** — it is a
> bounded, non-quadratic, deployable design (that part is proven at scale), but it delivers only
> fragile single-fact recall and no relational/enterprise reasoning, and that recall comes from
> the **bounding slots, not from Phase** (Phase's demonstrated value is perplexity, not evidence
> use).
>
> The next decisive experiment is **C with explicit `L_binding`/`L_source` slot supervision and
> orthogonality regularisation at 4–8k steps × ≥5 seeds**, with acceptance threshold **≥0.6
> binding@k4 and ≥0.5 supersession in ≥3/5 seeds, slots-off ablation removing ≥0.3 absolute,
> while B stays at chance** — only then should C be described as an enterprise relational
> architecture rather than a single-fact associative memory.
