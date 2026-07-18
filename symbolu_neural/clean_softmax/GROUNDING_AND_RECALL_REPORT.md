# Grounding & Long-Range Recall — Implementing the Two "Verdict-Changing" Ingredients

The capacity study concluded the active Symbol-U mechanisms don't beat equal compute
on the LM task. I flagged two things that *could* change that verdict and have now
implemented both as runnable experiments. **Neither rescues the formula on a
full-attention LM — but each precisely characterizes the conditions under which a
component could matter.** Honest, adversarial; no quality claim.

---

## Item 1 — Grounding Vritti/Aspect on a real (weak-labeled) corpus

There is no ground-truth Vritti annotation, so I used **distant supervision**: a
documented lexicon (`lexicon.py`, 86 Vritti words / 107 Aspect words across the
5/10 classes) tags real corpus words with semantically meaningful categories — a
large step up from the earlier surface-feature labels. A char backbone is trained
and frozen; per-word hidden states are pooled at every layer; linear Vritti/Aspect
probes are trained. The **decisive test is generalization to UNSEEN words** (disjoint
word split): fitting seen words is spelling memorization; predicting the *category*
of never-seen words is evidence of encoded meaning. `run_grounding.py`.

### Results (4-layer char backbone, 1019 labeled words, seed 0)

| head | layer | in-vocab acc | **unseen-word acc** | shuffled ctrl | majority |
|---|---|---|---|---|---|
| Vritti (5) | block1→final | 0.80–0.90 | **0.74–0.77** | 0.44–0.58 | **0.759** |
| Aspect (10) | block1→final | 0.57–0.62 | **0.000** | 0.12–0.18 | 0.330 |

### Honest reading
- **Aspect: zero semantic generalization.** The probe fits seen words (in-vocab
  0.6) but scores **0.000 on unseen words at every layer** — worse than the shuffled
  control and far below the 0.33 majority. The head learned spelling→label, not
  meaning.
- **Vritti: only the majority baseline.** Unseen-word accuracy (0.74–0.77) ≈ the
  majority class frequency (0.759). It beats the shuffled control but **does not beat
  majority** — i.e. it mostly predicts the dominant class; no real grounding.
- **Conclusion: the backbone is the bottleneck, not just the labels.** A char-level
  LM encodes *spelling*, not lexical *meaning*, so Vritti/Aspect cannot be grounded
  on it even with semantically meaningful labels. Real grounding requires a
  **semantically-capable backbone** (subword / pretrained) **and real human labels**.
  The weak-supervision harness (`lexicon.py` + `run_grounding.py`, with the
  unseen-word + shuffled controls) is the reusable tool to run *that* experiment when
  those exist. (Caveat: distant labels, single seed, one small corpus — but the
  unseen-word=0.000 for Aspect is unambiguous.)

---

## Item 2 — A task that structurally rewards long-range deferred recall

The capacity study found memory ≈ a pointwise FFN on the LM task. Hypothesis: that
tie is because the LM backbone's **attention already provides cross-time mixing**,
making the memory redundant — not because memory is useless. To isolate the modules,
this experiment removes attention: each mini-model is `embedding → [module] → head`,
so the module is the *only* cross-time mechanism. Task `running_majority`: per
position, predict whether `#ones ≥ #zeros` so far — it needs the whole prefix, so a
pointwise FFN must score ~chance. `run_recall_study.py`.

### Results (seq 128, d 64, 600 steps, seed 0; late-position accuracy)

| module | acc | **late-pos acc** | params | role |
|---|---|---|---|---|
| none (embed+head) | 0.563 | 0.535 | 33k | no cross-time → chance |
| **FFN control** (pointwise) | 0.566 | **0.530** | 37k | no time mixing → chance ✓ |
| **Deferred-Insight memory** | 0.799 | **0.732** | 37k | decayed prefix-mean → cross-time |
| attention (1 block, reference) | 0.992 | 0.985 | 99k | upper bound |

### Honest reading
- **Memory has a genuine structural advantage over the FFN** (late-pos 0.73 vs 0.53)
  at **matched params** (37k each). The decayed causal prefix-mean can aggregate
  across time; a pointwise FFN provably cannot. So the LM-task tie was indeed because
  attention already did the aggregation — memory was *redundant* there, not useless.
- **But memory is a weak substitute for attention** (0.73 vs 0.985, at ~⅓ the params).
  Its niche is narrow: a cheap aggregator *only* where a backbone lacks/limits
  attention. On a standard full-attention Transformer (the clean-softmax model, and
  any real LLM) that niche does not exist, so the capacity-study verdict stands there.

---

## Net effect on the GPU-run verdict

Neither ingredient overturns "trains fine, scales fine, no advantage over equal
compute" **for a full-attention LM**:
- Grounding **fails on the char-LM backbone** (no semantic generalization) → the
  typed heads remain ungrounded clusters until a stronger backbone + real labels.
- Memory's advantage exists **only without attention** → redundant on a real LM.

What the implementations *do* give you: (1) a ready grounding harness with the
correct controls (unseen-word + shuffled), and a clear signal that the **backbone**
must change before Vritti/Aspect can be grounded; (2) a precise, isolated
characterization of the memory module's real-but-narrow structural role. Both are the
honest, decision-useful results — run before, not after, spending GPU budget.

Reproduce:
```bash
python -m symbolu_neural.clean_softmax.run_grounding   --layers 4 --backbone-steps 300 --n-blocks 1500
python -m symbolu_neural.clean_softmax.run_recall_study --steps 600 --seq 128
```
