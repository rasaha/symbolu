# Next Research Roadmap — Can Symbol-U latents become genuine semantic latent variables in a standard Transformer?

Implementation frozen. No new modules, no new patent algorithms, no new control
mechanisms. Goal: **validate or falsify** the hypothesis with the current code, at
minimum GPU cost. Written as the PI would write it — optimized for finding the truth,
not defending the patent.

## What "genuine semantic latent variable" must mean (the bar)

A latent is *genuine and semantic* only if it clears four rising bars:
1. **Grounded** — linearly decodable from the model's representations.
2. **Generalizing** — decodable on **unseen words/contexts** above majority + shuffled
   controls (not spelling/identity memorization).
3. **Non-arbitrary** — the specific Vritti/Aspect partition carves meaning better than a
   random relabeling of the same cardinality (and within range of an established
   taxonomy).
4. **Causal** — the model *uses* the variable: intervening on it changes behavior in
   the predicted way (not an epiphenomenal correlate).

Everything we've established says bars 1–2 fail on a **char-level** backbone (Aspect
generalizes at 0.0 to unseen words; Vritti only hits the majority baseline). So the
first question is not about Symbol-U at all — it's about the **backbone**.

---

## Critical unknowns, in priority order

### U1 — Is the backbone the bottleneck? (decisive)
- **Why it matters:** every grounding failure so far is confounded with a char-LM that
  encodes spelling, not meaning. If a *semantically-capable* (subword, pretrained)
  backbone also can't ground Vritti/Aspect above arbitrary controls, the hypothesis is
  essentially falsified. If it can, the whole program is unblocked.
- **Experiment:** E1 — frozen pretrained subword LM + existing `run_grounding.py`
  harness (`HFEncodeAdapter` already exists), with the unseen-word + shuffled controls,
  plus an **established-taxonomy positive control** (POS / sentiment) to prove the probe
  can decode *known* semantics on this backbone.
- **Cost:** trivial (no backbone training; linear probes on cached features).
- **Runtime:** minutes (CPU or 1 small GPU).
- **Expected outcome (honest):** positive control (POS/sentiment) passes easily; Vritti/
  Aspect generalize *better than char-LM* (lexical neighbors cluster) but the magnitude
  is the open question — plausibly partial.
- **Conclusion drawn:** if Vritti/Aspect unseen-word decoding ≫ majority/shuffled →
  latents *can* be semantic, proceed. If ≈ majority even here → arbitrary; stop.

### U2 — Are the Vritti/Aspect categories real structure or a fittable partition?
- **Why it matters:** any 5-/10-way head will *fit* something. The question is whether
  the patent's taxonomy carves meaning at non-arbitrary joints.
- **Experiment:** E2 — on the same frozen backbone, compare decodability + cluster
  purity of (a) patent labels, (b) a random relabeling into the same cardinality,
  (c) an established taxonomy.
- **Cost/runtime:** trivial (more probing on cached reps; minutes).
- **Expected outcome:** patent labels likely beat random relabeling somewhat (the
  lexicon is lexically coherent) but may trail an established taxonomy.
- **Conclusion:** patent ≈ random relabeling → arbitrary taxonomy (stop/redefine);
  patent ≫ random and ≈ established → genuine carving (proceed).

### U3 — Can the latents be *trained into* a working Transformer without breaking it?
- **Why it matters:** frozen probes show correlation, not integration. The hypothesis is
  about latents *inside* a standard Transformer that still does LM.
- **Experiment:** E3 — joint training (Stage-2 of the adopted policy): trainable subword
  LM + auxiliary Vritti/Aspect supervision, heads shape representation but do **not**
  control generation.
- **Cost:** moderate (real fine-tuning).
- **Runtime:** hours on 1×A100.
- **Expected outcome:** if U1/U2 passed, supervision should improve grounding without
  materially hurting LM; if they failed, this is moot.
- **Conclusion:** LM intact + grounding improves/generalizes → integratable genuine
  latents (proceed to causal test). Else → probeable but not integratable (stop).

### U4 — Are the latents causally used, or epiphenomenal?
- **Why it matters:** a decodable direction is not a *variable* unless the model's
  computation depends on it. This is the gold standard for "genuine latent."
- **Experiment:** E4 — activation patching / causal mediation on the grounded Vritti/
  Aspect subspace vs a random-subspace control.
- **Cost:** moderate (inference-time interventions; no training).
- **Runtime:** hours on 1 GPU.
- **Expected outcome:** uncertain — decodable ≠ causal; this is where many "interpretable
  features" die.
- **Conclusion:** intervening changes behavior semantically above the random-subspace
  control → genuine causal latent; else → readable correlate only (stop control work).

### U5 — Does genuine semantic structure translate to a compute advantage?
- **Why it matters:** the terminal payoff — does any of this beat equal compute?
- **Experiment:** E5 — capacity-/FLOP-matched study (existing `run_capacity_study`), now
  with grounded heads on a semantic backbone, multi-seed.
- **Cost:** highest (full training × seeds).
- **Runtime:** ~a day on 1×A100.
- **Expected outcome (honest, given everything so far):** most likely still no advantage
  at equal compute — but now with grounded latents the test is finally fair.
- **Conclusion:** beats controls across seeds → real computational role; else → genuine
  latents with no control payoff (a real, if humbler, scientific result).

---

## The research program — five experiments

| # | Objective | Dataset | Model | GPU | Metrics | Success | Failure | Decision enabled |
|---|---|---|---|---|---|---|---|---|
| **E1** | Backbone ceiling: can a semantic backbone ground Vritti/Aspect with unseen-word generalization? | repo corpus (weak lexicon labels) + a POS/sentiment positive-control set | **frozen** pretrained subword LM (e.g. GPT-2 small) via `HFEncodeAdapter` | none/1×small, ~minutes | unseen-word acc/macro-F1 vs majority & shuffled; POS/sentiment as positive control; per-layer | Vritti/Aspect unseen-word ≫ majority+shuffled, and POS/sentiment clearly decodes | Vritti/Aspect ≈ majority while POS/sentiment decodes | Is the backbone the blocker, or the concept? |
| **E2** | Non-arbitrariness of the taxonomy | same cached features | same frozen LM | none/1×small, ~minutes | unseen-word F1 + cluster purity: patent vs random-relabel vs established taxonomy | patent ≫ random-relabel, ≈ established | patent ≈ random-relabel | Are Vritti/Aspect real joints or any partition? |
| **E3** | Integratable grounding (Stage-2 joint training) | a small **human-labeled** Vritti/Aspect set (≥ few k tokens) + LM corpus | **trainable** small subword LM + aux heads, no control | 1×A100, hours | LM val loss vs baseline; head unseen-word generalization; grounding-before/after | LM ≤ baseline+ε **and** grounding improves & generalizes | LM harmed or grounding doesn't generalize | Can latents live inside a working LM? |
| **E4** | Causal reality | held-out probing/intervention set | E3 checkpoint (frozen) | 1 GPU, hours | behavior change under subspace patching vs random-subspace control | semantic, above-control causal effect | no effect beyond random subspace | Variable vs epiphenomenon |
| **E5** | Compute payoff | LM corpus | E3-style model, control-eligible grounded heads | 1×A100, ~1 day (multi-seed) | val loss vs FLOP-matched controls (`run_capacity_study`), ≥3 seeds | beats equal-compute controls across seeds | ties/loses to controls | Real computational role or not |

> **Note on E3/E4's missing ingredient:** a *human-labeled* Vritti/Aspect set. Weak
> lexicon labels suffice for E1/E2 (probing) but not for trustworthy integration/causal
> claims. ~1–5k human-labeled tokens is the single highest-leverage data investment;
> without it, stop at E2 and report.

---

## Ranking by expected information gain (and what to cut)

1. **E1** — by far the highest. One cheap experiment can falsify the hypothesis or
   unblock everything. Run first, always.
2. **E2** — cheap, decides "real vs arbitrary taxonomy." High value, near-zero cost.
3. **E3** — first expensive step; only justified if E1+E2 pass.
4. **E4** — gold-standard but only meaningful after grounding exists.
5. **E5** — terminal payoff; highest cost; run only if E1–E4 pass.

**E1 and E2 are cheap enough to run together before any GPU spend.** If either fails,
the program ends for < an hour of compute.

### Do NOT run (wasted work)
- **Anything more on the char-level backbone** — grounding failure is already established;
  more char-LM runs cannot change the verdict.
- **More LM-loss capacity studies on the current char model** — done, negative, stable.
- **More control-module engineering** (refinement/memory variants, DHA) — the hypothesis
  is about the *latents*, not the controls; controls are already demoted.
- **Guna/Kosha as a primary grounding target** — they're diagnostic; fold in as a
  secondary readout of E1, never gate the program on them.
- **Generation-quality / benchmark runs** — irrelevant to "are the latents semantic."
- **Scaling-law sweeps** — premature before E1.
- **Unsupervised "emergence" experiments** — interesting but expensive and not decisive
  for the stated hypothesis (which supervised grounding addresses). Defer indefinitely.

---

## Final roadmap (decision tree)

```
E1  Backbone ceiling (frozen semantic LM probe; minutes, ~free)
│
├─ FAIL  (Vritti/Aspect ≈ majority while POS/sentiment decodes)
│        → STOP. Hypothesis falsified at the probing level: even a semantic backbone
│          does not encode these as recoverable categories. The latents are arbitrary.
│
└─ PASS  → E2  Non-arbitrariness (patent vs random-relabel vs established taxonomy; minutes)
          │
          ├─ FAIL (patent ≈ random-relabel) → STOP (taxonomy arbitrary) or redefine
          │        the taxonomy (which leaves the patent's claims behind).
          │
          └─ PASS → E3  Stage-2 joint training on a HUMAN-labeled set (1×A100, hours)
                    │   (gate: if no human labels, STOP here and report E1/E2.)
                    │
                    ├─ FAIL (LM harmed or grounding doesn't generalize) → STOP:
                    │        probeable but not integratable.
                    │
                    └─ PASS → E4  Causal intervention (patching; 1 GPU, hours)
                              │
                              ├─ FAIL → STOP control work. Result: real, grounded,
                              │         interpretable probes that the model does NOT
                              │         causally use — a genuine (lesser) finding.
                              │
                              └─ PASS → E5  Compute payoff, FLOP-matched, ≥3 seeds
                                        (1×A100, ~1 day)
                                        │
                                        ├─ FAIL → genuine causal semantic latents with
                                        │         NO control advantage at equal compute.
                                        │         Honest positive-but-humble result.
                                        │
                                        └─ PASS → hypothesis SUPPORTED: Symbol-U latents
                                                  are genuine semantic variables that
                                                  also confer a compute-fair advantage.
```

---

## Final answer — as PI with budget for five experiments

**Run them in exactly this order: E1 → E2 → E3 → E4 → E5, each gating the next.**

- **E1 first, and treat it as a kill switch.** It costs almost nothing and is the single
  most decisive test. Pair it with a POS/sentiment positive control so a Vritti failure
  can't be blamed on a broken probe. Most of the project's risk collapses here.
- **E2 immediately after E1**, same sitting, same cost — it separates "real taxonomy"
  from "any 5/10-way partition." If E1 and E2 both pass, you have earned the right to
  spend GPU.
- **Gate E3 on acquiring ~1–5k human-labeled tokens.** This is the real bottleneck, not
  compute. Without human labels, stop after E2 and report honestly; weak labels cannot
  carry integration or causal claims.
- **E4 before E5.** Decodable ≠ causal; many interpretable features die at the patching
  step. Don't spend the expensive E5 until you know the latent is causally real.
- **E5 last and only if everything passes.** Given every result so far, my honest prior
  is that the program **stops at E1 or E2** (latents fittable but largely arbitrary on a
  semantic backbone), or — best case — reaches E4 and shows grounded, partially-causal
  latents that still **fail E5** (no compute advantage). I would be genuinely surprised
  if E5 passed; if it did, that would be the first real evidence the Symbol-U latents
  are more than relabeled Transformer features.

**Brutal bottom line:** the cheapest experiment (E1) carries ~70% of the decision value.
Spend an hour on E1+E2 before another dollar of GPU. The expensive experiments only
exist to confirm a positive E1/E2 — and the most likely truthful outcome is that this
sequence *narrows or falsifies* the hypothesis rather than confirming it. That is the
result worth buying.
