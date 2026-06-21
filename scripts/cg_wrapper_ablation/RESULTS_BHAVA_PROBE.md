# Bhava / Ontology Probe — RESULT (filled) + CG TRACK FINAL VERDICT

> Closeout of the **representation** question and the overall CG investigation. Numbers from
> `runs/bhava_probe/20260621T004503Z/`. Generation-quality research track only.

## Probe result — correctness (n=170; pos=49, neg=121; balanced graded pool)

| Feature set | AUROC | CI | decodable | bal_acc |
|-------------|------:|----|:---------:|--------:|
| bhava_only | 0.818 | [0.736, 0.892] | yes | 0.796 |
| cg_state_32d | 0.828 | [0.745, 0.902] | yes | 0.738 |
| delta_bhava_only | 0.748 | [0.647, 0.835] | yes | 0.647 |
| **hidden_only** (fair, PCA'd) | 0.777 | [0.690, 0.861] | yes | 0.713 |
| hidden_plus_bhava | 0.778 | [0.691, 0.862] | yes | 0.704 |
| hidden_plus_cg_state | 0.744 | [0.657, 0.828] | yes | 0.725 |

Paired: **hidden+bhava vs hidden_only Δacc = −0.029, p=0.473 (ns)** — Bhava adds nothing.
(bhava vs delta_bhava Δacc=+0.229, p=2.7e-7 sig — bhava value > its delta, as expected.)

**DECISION: `BHAVA_WEAK_SIGNAL` → PARK.** Bhava value is decodable (CI lo 0.736 > 0.5) but a
**fair** hidden baseline decodes correctness equally well (0.777) and Bhava adds nothing over it.
Bhava is a redundant compression of information already in the hidden state — not load-bearing.

Other label types: `reasoning_correctness` (1 pos → INSUFFICIENT) and `constraint_satisfaction`
(0 pos, single-class → degenerate). Base model failed all hard items; warnings fired as designed.

### Methodology note (why the earlier "signal" was an artifact)
The pre-fix run showed bhava 0.80 vs hidden **0.39** — which looked like Bhava beating hidden. That
was a **broken baseline**: a 4096-d logistic probe on ~100 examples overfit below chance. With
per-group PCA (fit per fold) the hidden baseline recovers to 0.777, and Bhava's apparent advantage
disappears. The "anomaly" was methodological, not real — caught by refusing to conclude on it.

## CG TRACK — FINAL VERDICT: **PARK** (both halves negative)

| Question | Instrument | Result |
|----------|-----------|--------|
| Can the design bootstrap an active gate? | `BOOTSTRAP_ANALYSIS.md` | No — ORIGINAL inert by construction; Active-CG needed just to make it non-inert |
| Does the wrapper improve **generation**? | `RESULTS_GENERATION_ABLATION.md` | **No** — `ACTIVE_NO_EFFECT`; B=A on all metrics; B≈C, ΔBhava=0 (dynamics dead) |
| Does the Bhava **value** carry unique signal? | this probe | **No** — `BHAVA_WEAK_SIGNAL`; decodable but redundant with hidden |

The whole chain is consistent end to end: the math predicted a static offset, the audit traced why
(generation consumes ΔBhava≈0), the ablation measured it (B≈C), and the probe showed the underlying
Bhava value — while real — adds nothing over generic hidden states.

**Action: stop CG-wrapper and CG-representation work for generation quality.** No measurable,
non-redundant benefit exists on objective metrics. Nothing here was claimed on subjective grounds.

### What would (and would not) reopen it
- Would NOT: a different injection layer / per-token signal — the representation it carries is
  redundant with hidden, so better plumbing delivers nothing new.
- Would (as a NEW, separately pre-registered question, not a continuation): a *fundamentally
  different training objective* that makes Bhava encode something hidden does not. There is no
  evidence to expect this; pursuing it would be speculative.

Probe = correlation only; this verdict rests on objective decodability + a fair baseline, not on a
causal generation test (which is unnecessary given the generation ablation already parked the path).
