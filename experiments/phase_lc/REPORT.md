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

<!-- SECTIONS 6-17 (results, ablations, verdict) are filled from results/main_tables.md -->
