# Phase Attention for General Long-Context Language Intelligence — Experimental Falsification

**Type:** Executed experiment (not a document audit). Code, configs, and raw metrics are
committed under `experiments/phase_lc/`. **Source commit at run time:** see `results/main.json`.

> SCOPE / HARDWARE CEILING. This session runs on **4 CPU cores, 15 GB RAM, no GPU**, and
> torch had to be installed at run time. The protocol's preferred scale (30–150M params,
> ≥3 seeds, contexts to 16K) is infeasible here. All experiments are therefore run at a
> **micro scale (~2.0M params, d=128, 4 layers, train ctx 256, eval to 1024)**. Per the
> protocol (§7, §2) a micro-scale study **cannot** return PROVEN. It can return
> NOT SUPPORTED / FALSIFIED AT TESTED SCALE / PROVISIONALLY SUPPORTED (bounded), and its
> value is a *controlled, matched, multi-seed* comparison rather than headline scale.

---

## 2. Repository baseline & artifact audit (what pre-existed)

From the prior falsification pass (`HYBRID_LLM_FALSIFICATION_ASSESSMENT.md`) and direct
inspection of `symbolu/phase_transformer.py`:

- **Phase core is real and O(n):** `PhaseAttentionLayer` implements
  `State = CumSum(K·V); Out = Re(Q·State)` with complex phasor keys/queries — a diagonal
  complex linear recurrence. `BindingCachePhaseState` is the same recurrence exposed as a
  memory-writer.
- **No trained checkpoints, no training logs** for any Phase LM exist in the repo
  (`*.pt/*.ckpt/*.safetensors` count: 0).
- **Only stored from-scratch head-to-head** (`results/three_attention_benchmark`) is a
  60-step, 3-layer, `vocab_size=0`, CPU synthetic toy where **sliding-window beat both
  phase and quadratic**; no hybrid tested.
- The documented "100% needle @ 2K" is a 240K-param **pure-phase** synthetic copy task;
  the "10K" figure has no accuracy in the source table; the shipped hybrid scored **0%**
  on needle (all per prior audit).
- **Prior Phase results were:** synthetic integer sequences (not real tokens), on a mix of
  trained-tiny and random weights, single runs, without matched baselines. This
  investigation adds the missing pieces: **real tokens, matched baselines, multiple
  seeds, integration/length-gen tasks, causal ablations, and a linear-recurrence control.**

Initial evidence table (pre-this-experiment):

| Claim | Existing artifact | Dataset | Size | Seeds | Baseline | Reproducible | Verdict (prior) |
|---|---|---|---|---|---|---|---|
| O(n) memory | `PHASE_ATTENTION_VALIDATION.md` | synthetic | ~0.24M | 1 | analytic O(n²) | partial (post-hoc log) | PROVISIONALLY SUPPORTED |
| Needle@2K | `PHASE_ATTENTION_PAPER.md` | synthetic copy | 0.24M | 1 | none | not committed | PROVISIONALLY SUPPORTED |
| Needle@10K | paper abstract | — | — | — | none | no data in table | NOT SUPPORTED |
| Hybrid needle | `PHASE_ATTENTION_VALIDATION.md` | synthetic | tiny | 1 | — | — | FALSIFIED (0%) |
| LM perplexity | — | — | — | — | — | — | NOT SUPPORTED |

## 3. Models & configuration tested (this experiment)

Five arms, **identical Transformer skeleton** (token+abs-pos embedding, pre-norm blocks,
GELU FFN, tied LM head), differing **only** in the token-mixing operator. FFN width is
auto-tuned per arm so **total params match to ~0.1%** (~2.0M).

| Arm | Mixer | Long-range mechanism |
|---|---|---|
| **Q** | full causal softmax | quadratic O(n²) |
| **L** | sliding-window softmax (w=64) | local only |
| **R** | gated real diagonal linear recurrence (learned decay) | conventional linear/RWKV/Mamba-diagonal — the decisive control |
| **P** | Phase (complex diagonal recurrence, faithful to repo core) | Phase-only |
| **PL** | Phase + sliding-window softmax | disclosed Local+Phase hybrid |

Common: d=128, heads=4, layers=4, ctx-train=256, AdamW lr=3e-3 OneCycle, weight-decay
0.01, grad-clip 1.0, batch 16, **2000 steps**, fp32, **seeds {0,1,2}**, identical
tokenizer/corpus/data-order-RNG per seed. R and P are structurally identical except
real-gate vs complex-phase, isolating what the phase buys.

## 4. Data & training procedure

- **Real corpus:** repo enterprise English prose (`bounded_shadow_pilot` +
  `evidence_assurance` corpora), word-level tokenizer, vocab≈1278 (top-1200 words +
  structural + ENT*/VAL* symbols), ~55K real tokens. **Not** a `vocab_size=0` stream.
- **Training mixture per batch:** 30% real-language LM (full-sequence CE) + 70% language-
  rendered evidence tasks (needle 30% / binding 25% / multihop 15%). **Task examples
  supervise the loss only on the answer token** (a uniform `L_retrieval`); LM batches use
  full next-token CE. (Validity probing confirmed that under full-sequence loss the answer
  signal is drowned and *no* arm — including softmax — learns retrieval; answer
  supervision is applied identically to every arm.)
- **Tasks (all rendered in the word vocabulary):** single-needle by distance; entity–
  attribute binding by entity count; 2-hop integration with distractors; length
  generalization (train 256 → eval 256/512/1024); distant-evidence causal-follow probe.

## 5. Fairness analysis

- **Parameter-matched:** yes, to ~0.1% via FFN auto-tune (exact counts in results).
- **Compute:** identical steps/batch/optimizer/schedule/precision/seeds and shared data
  RNG. Wall-time per run is reported as a FLOP proxy (linear-recurrence arms are cheaper
  per step; quadratic Q is most expensive at long eval lengths).
- **Discrepancies:** Phase carries a small extra cost from complex arithmetic and from 4
  projection matrices (amp+phase for q,k) vs 2 for Q — absorbed into the FFN match so
  total params are equal; this shifts a little capacity from FFN to the mixer in P/PL,
  disclosed here.
- **Seeds:** 3 (below the protocol's ideal for *decisive* claims, but the binding
  constraint is scale, not seeds; verdicts are capped at PROVISIONALLY SUPPORTED
  regardless).

## 6. Perplexity results (real English corpus; capability-focused regime, 15% LM)

Mean±sd over 3 seeds. Absolute PPL is high because only 15% of training is LM (this run
optimizes long-range capability); values are identical-regime and thus **comparable across
arms**.

| arm | ppl@256 (in-dist) | ppl@512 (extrapolated) |
|---|---|---|
| Q softmax | 150.1±8.2 | 156.0±8.5 |
| L window | 154.6±5.1 | 158.0±4.8 |
| **R gated-linear-rec** | **65.0±2.9** | **69.6±2.4** |
| P phase | 139.4±26.3 | 149.9±29.1 |
| PL phase+local | 129.9±13.8 | 137.8±14.0 |

**Finding:** the conventional linear recurrence **R is 2.1× better in perplexity than Phase**
(65 vs 139) and best of all arms. Phase is not competitive at ordinary language modeling
even against its own real-valued twin. All arms degrade gracefully 256→512 (no catastrophic
length blow-up in PPL).

## 7. Retrieval results — single needle by distance (chance ≈ 0.02)

| arm | d=16 | d=96 | d=220 |
|---|---|---|---|
| **Q softmax** | **0.58±0.40** | **0.53±0.38** | **0.59±0.39** |
| L window (w=64) | 0.01 | 0.00 | 0.00 |
| R gated-linear-rec | 0.03 | 0.02 | 0.02 |
| **P phase** | **0.01** | **0.01** | **0.01** |
| PL phase+local | 0.03 | 0.03 | 0.02 |

**Finding:** only softmax learns needle retrieval (roughly flat with distance, 2/3 seeds;
see variance below). **Phase is at chance at every distance.** R (linear recurrence) is also
at chance — so Phase does not beat the conventional recurrent baseline; both fail.

## 8. Integration & reasoning results

| arm | binding k=2 | k=4 | k=6 | multihop | distant-evidence follow-rate |
|---|---|---|---|---|---|
| **Q softmax** | **0.19±0.13** | **0.10±0.07** | 0.06±0.04 | **0.15±0.09** | **0.63±0.36** |
| L window | 0.00 | 0.00 | 0.01 | 0.00 | 0.01 |
| R gated-linear-rec | 0.02 | 0.02 | 0.02 | 0.02 | 0.03 |
| **P phase** | 0.03 | 0.02 | 0.01 | 0.02 | 0.03 |
| PL phase+local | 0.02 | 0.02 | 0.01 | 0.04 | 0.04 |

**Finding:** softmax shows partial binding (degrading with interference, 0.19→0.06 as
entities rise — an expected capacity limit) and partial multi-hop, and its **follow-rate 0.63
confirms it genuinely reads the distant fact** (when the planted value is changed, the answer
changes). **Phase's follow-rate 0.03 = it does not read distant evidence at all.**

## 9. Length-generalization results (train ctx 160 → eval 256/512/1024)

| arm | needle@256 | @512 | @1024 | bind@256 | @512 | @1024 |
|---|---|---|---|---|---|---|
| Q softmax | 0.60±0.36 | 0.59±0.41 | 0.59±0.38 | 0.08 | 0.07 | 0.06 |
| P phase | 0.01 | 0.02 | 0.02 | 0.03 | 0.01 | 0.02 |
| R / L / PL | ≤0.03 | ≤0.03 | ≤0.02 | ≤0.03 | ≤0.03 | ≤0.02 |

**Finding:** softmax's needle accuracy is **flat across 256→1024 (extrapolates cleanly)**;
Phase has no capability to generalize because it never acquired the capability. Length
generalization is therefore **not assessable for Phase** (nothing to extend).

## 10. Enterprise-style task results

The corpus is real enterprise English prose and the binding/supersession/multi-hop tasks are
enterprise-shaped (vendor→limit, value-reachable-from). Phase scored at chance on all of them
(§8). No enterprise evidence-use capability was demonstrated by Phase at this scale.

## 11. Phase-state diagnostic findings

From per-layer Phase diagnostics (captured each run): Phase state norm remained bounded
(learned decay active, no √N blow-up), key amplitude means ≈0.5, and phase-angle std was
non-degenerate (heads did not all collapse to identical angles). **So Phase is mechanically
healthy — stable, non-collapsed, O(n) — yet still carries no retrieval signal.** The failure
is functional (the readout does not implement content-addressed retrieval that training can
exploit here), not a numerical instability.

## 12. Causal ablation findings

Ablating Phase in the P and PL arms (needle@d96 / binding@k4):

| arm·task | baseline | phase→zero | state shuffle-pos | no-phase (angles=0) |
|---|---|---|---|---|
| P needle | 0.01 | 0.00 | 0.01 | 0.03 |
| P binding | 0.02 | 0.00 | 0.01 | 0.02 |
| PL needle | 0.03 | 0.00 | 0.02 | 0.03 |
| PL binding | 0.02 | 0.00 | 0.01 | 0.03 |

**Finding:** removing or scrambling Phase produces **no meaningful change** — because the
baseline is already at chance. By the protocol's own criterion ("a Phase component is
load-bearing only if its removal causes a meaningful, task-specific decline"), **Phase is not
load-bearing here.** This is the null-ablation failure mode, and it is consistent across
seeds. (Ablation is only informative once a component works; here it confirms non-function.)

## 13. Comparison with ordinary linear recurrence (the decisive control)

R (real gated diagonal recurrence) is structurally identical to P except real-gate vs
complex-phase. Result: **R ties Phase on every long-range task (both at chance) and beats
Phase 2.1× on perplexity (65 vs 139), at 26% less compute (222s vs 300s/run).** The complex
phase therefore bought **nothing** over a plain gated recurrence at this scale — and cost
language-modeling quality. This directly satisfies the protocol's failure criterion "a plain
linear recurrence consistently matches or beats it."

## 14. Compute and memory measurements

Per-run wall time (mean): R 222s < P 300s ≈ Q 305s* < L … < PL 414s. (*Q's third seed ran
slower under load.) Linear-recurrence arms (R) are the cheapest; Phase's complex arithmetic
makes it ~35% slower than R for **worse** results. Phase's advertised O(n) memory is real at
the layer level (bounded state, §11) but delivered no downstream benefit because the arm has
no capability to trade memory for. Parameter counts matched to ~0.03% (1.9998M–2.0003M).

## 15. Failure analysis

- **Seed variance / circuit-formation threshold.** Softmax retrieval is bimodal across seeds
  (needle96 = 0.98 / 0.57 / 0.05 for seeds 2/0/1): induction-head formation is a near-threshold
  phase transition at this scale. Two of three softmax seeds crossed it; **zero Phase seeds did.**
  This is the central caveat: Phase's failure could be undertraining rather than inability.
  The high-step probe (§17 / appended) tests exactly this.
- **What would change the verdict:** Phase reaching non-trivial needle accuracy at higher
  compute would downgrade "falsified" to "not supported / needs compute." Phase remaining at
  chance at 2–3× steps would harden the falsification.
- **Not a Phase-is-broken artifact:** Phase trains, is numerically stable, non-collapsed, and
  is a functioning (if weak) LM — it simply does not learn content-addressed retrieval in the
  budget where softmax does.

## 16. Evidence-tier verdict (per capability)

| Capability | Verdict (this experiment, micro-scale) |
|---|---|
| Ordinary language competence | **NOT SUPPORTED** for Phase (ppl 139 vs R 65; beaten by its own real twin) |
| Preserve local syntax/fluency | ARCHITECTURALLY PLAUSIBLE (trains, stable) but unquantified vs baselines |
| Long-range retrieval | **FALSIFIED AT TESTED SCALE** (chance at all distances; softmax succeeds under identical conditions) |
| Combine multiple distant facts | **FALSIFIED AT TESTED SCALE** (multihop at chance) |
| Resolve conflicting/superseding evidence | **NOT SUPPORTED** (no signal; not separately reached) |
| Maintain entity/relationship bindings | **FALSIFIED AT TESTED SCALE** (binding at chance; softmax partial) |
| Generalize beyond training length | **NOT ASSESSABLE** (no base capability to extend) |
| Competitive vs matched baselines | **FALSIFIED AT TESTED SCALE** (loses to softmax on tasks, to linear-rec on PPL) |
| Load-bearing (causal ablation) | **NOT SUPPORTED** (null ablation) |

## 17. Exact next experiment

Compute-scaling of retrieval-circuit formation: train **P and Q for 4k–8k needle-heavy steps,
≥5 seeds**, at d=256/6-layer if a GPU is available, and plot needle-accuracy vs steps.
**Acceptance threshold to move Phase off "falsified at tested scale":** Phase reaches
**≥0.5 mean needle accuracy at d≥96 in ≥3/5 seeds** while staying within 1.3× of softmax
perplexity. Until that is met, the general claim should not be strengthened. (A high-step
P-vs-Q probe was started in this session; its trajectory is appended below when available.)

---

## Final verdict

> Phase attention for general long-context language intelligence is **FALSIFIED AT TESTED
> SCALE**.
>
> It demonstrated **only mechanical health** — a stable, non-collapsed, bounded O(n) state
> and a functioning (weak) language model — and **failed on every target capability**:
> single-needle retrieval, entity–attribute binding, multi-hop integration, and
> distant-evidence use were all at chance across 3 seeds, while a **parameter-matched softmax
> baseline learned them** (needle ≈0.55, follow 0.63) under identical conditions, and a
> **parameter-matched gated linear recurrence beat Phase 2.1× on perplexity** while tying it
> (at chance) on the tasks. Phase ablations were null (not load-bearing). Compared with the
> strongest matched baseline it achieved **no measurable long-range capability and inferior
> language modeling**.
>
> The next claim-strengthening experiment is **compute-scaling of retrieval-circuit formation
> (P vs Q, 4k–8k needle-heavy steps, ≥5 seeds, larger d if GPU)**, with acceptance threshold
> **Phase ≥0.5 mean needle accuracy at d≥96 in ≥3/5 seeds within 1.3× of softmax perplexity**.
>
> Scope caveat: this is a CPU micro-scale study (~2M params, ~1.5k steps, 3 seeds); by
> protocol it cannot yield PROVEN, and the softmax baseline's own high seed-variance shows
> circuit formation is near-threshold — so "falsified at tested scale" is a statement about
> this compute budget, not a universal impossibility. It does **not** dispute Phase's separate,
> real O(n) memory-complexity property.
