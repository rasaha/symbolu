# Validity Assessment — Acoustic-Semantic Latent Profiles (fusion)

> **Task:** decide, before implementing, whether the fusion experiment (A = semantic-only; B = semantic +
> real varṇa; C = semantic + scrambled varṇa; D = semantic + random symbolic) is scientifically valid,
> whether it escapes relabeling-invariance, and its odds. **Verdict: VALID and NON-DEGENERATE — it does
> not collapse, and is runnable. But it escapes relabeling-invariance precisely by *using gloss
> semantics*, which makes it a fair, strong re-test of the already-falsified sound→meaning channel in its
> best possible (fused) form. Predicted outcome: NO_ACOUSTIC_SEMANTIC_SIGNAL. Run only if a definitive
> negative is worth the cost.** Eight deliverables below.

---

## 0. Headline — why this one is different (and where it still lands)

Prior collapses (validator, topology) used **gloss-blind** representations, so scrambling — a pure
relabel — left them identical (B≡C). **This design feeds the gloss words' *meanings* into the profile**
(embedding "Patience", LLM-summarizing the arc). Scrambling now yields different gloss words ⇒ different
vectors ⇒ **B ≠ C is possible.** So it genuinely escapes the theorem and is a legitimate test.

The trade-off is unavoidable and is the crux: **the only way to escape relabeling-invariance is to use
gloss semantics — and "do the sound-derived glosses carry meaning the word's own semantics lack" is the
sound→meaning channel that tests #1–5 falsified.** For the *semantic* tasks (role, archetype, synonym,
context-fit), B can beat A only if the chain's glosses add label-relevant meaning beyond the word's
embedding — i.e., sound carries meaning. Six nulls say it does not. So the test is valid but predicted
null. It is not a duplicate of any single prior test (it is the *incremental-over-semantics, fused*
version), so running it is defensible as the strongest closing test — not as a new hope.

## 1. Latent-profile schema

```json
{
  "item_id": "uuid",                      // word never stored in features
  "semantic": {
    "definition": "short dictionary gloss",
    "embedding": [/* d-dim sentence-embedding of definition, model frozen */],
    "llm_summary": "1-2 line meaning summary (semantic only, no sound)"
  },
  "varna": {                              // deterministic, per lexicon variant
    "chain": [ {"slot": 0, "sign": "-", "worldly": "Shyness", "counter": "Fearlessness",
                "dissolution": true}, ... ],
    "polarity_seq": "-,+,-,+",
    "arc": [ {"from": "Shyness", "to": "Fearlessness"}, ... ]   // gloss text (this is the semantic hook)
  },
  "fused": [/* see §2 */]
}
```

Four variants of `varna` per item: **real / scrambled / random**, plus **A** has no `varna` block.

## 2. Fusion method (two options; recommend the objective one)

- **(F1, recommended) Frozen-vector concatenation.** `fused = [ sem_embedding ⊕ pool( emb(gloss_word) for
  gloss in chain ) ⊕ structural_onehot(polarity_seq) ]`. Gloss embeddings from a **frozen** sentence
  model (no task fine-tuning of the embedder). A simple, regularized classifier (logistic / small MLP)
  is trained on the fused vector. Identical pipeline across A/B/C/D — only the gloss source changes.
  This keeps "fusion" mechanical and auditable.
- **(F2, discouraged) LLM-authored fused summary.** Let an LLM write the "latent acoustic-semantic
  profile" from semantics+chain. **High leakage + reader-supplied-aptness risk** (the LLM rationalizes
  any arc, and may invert the chain to the word). If used at all, must be blinded and is not the primary
  arm.

The classifier — not a human, not a free-form LLM judge — makes predictions, so success is measured as
*incremental predictive accuracy*, not interpretive plausibility.

## 3. Task list (note which are semantic vs aesthetic)

| task | type | label source | note |
|---|---|---|---|
| role classification | semantic | held-out role categories | B>A needs sound→role-meaning |
| archetype classification | semantic | pre-set archetypes | ≈ test #5 in fused form |
| synonym clustering | semantic | thesaurus clusters | purity/NMI |
| context-fit prediction | semantic | masked-context fit | LLM-labeled, frozen |
| word-choice selection | mixed | human pairwise pref | partly aesthetic |
| naming suitability | aesthetic | human pref | euphony-driven |
| therapeutic phrasing | mixed | human pref | tone (mostly semantic connotation) |

⚠️ Even the **aesthetic** tasks won't rescue B: genuine sound-aesthetics live in *phonemes*, which are
**gloss-invariant**, so the *gloss-based* varṇa profile can't capture them — B≈C again. (A phoneme-feature
profile could, but that's the separate sound-control experiment, not this one.)

## 4. Control design

A (no varṇa) · B (real) · C (scrambled, pairs permuted — same psychological vocabulary) · D (random
neutral-noun pool). S = 20 seeded scrambles/randoms, averaged. **Decisive clause = B vs C** (isolates the
sound→gloss assignment); B vs D only distinguishes "uses psychological vocabulary at all" (the vocabulary
effect already seen in #5). Held-out words by category; word string never in features; same classifier,
same hyperparameters, same CV folds across all arms.

## 5. Statistical plan

Nested CV (or grouped CV by category to prevent word leakage). Per task: accuracy/macro-F1 (semantic),
silhouette/NMI (clustering), preference rate (aesthetic, counterbalanced). Paired bootstrap (10 000) over
items for **B−A, B−C, B−D**; pre-registered `MIN_EFFECT`. **Holm correction across the 7 tasks × 3
contrasts** — this is the program's 8th probe; uncorrected, ≈1 in 7 cells will "pass" by chance.
Verdict **ACOUSTIC_SEMANTIC_SIGNAL** iff `CI_lower(B−A) > 0 ∧ CI_lower(B−C) > 0 ∧ CI_lower(B−D) > 0`
(all ≥ MIN_EFFECT, post-Holm); else **NO_ACOUSTIC_SEMANTIC_SIGNAL**.

## 6. Leakage risks (the real threats here)

1. **Word recoverable from chain.** The chain is a near-invertible function of the word's sounds, so a
   classifier/LLM can partially reconstruct the word. *Mitigation:* this leaks **equally** into B, C, D
   (all are sound-fingerprints), so it inflates B>A but **cannot** create B>C. → never trust B>A alone;
   the B>C clause is the guard. (This is why the conjunction rule is essential.)
2. **LLM sound-symbolic prior (F2).** An LLM reading glosses may apply its own English sound-symbolism —
   again applied equally to real/scrambled, so B≈C; but it can spuriously lift B,C,D over A.
3. **Embedder semantics of glosses correlating with label.** If "Compassion/ Healing" glosses embed near
   "doctor"'s role, that's the sound→meaning effect under test — legitimate signal *if and only if* it
   beats scrambled. Scramble preserves the vocabulary, so a generic "psychological-words-help" effect
   shows as B≈C>D, correctly classified as no acoustic signal.
4. **Multiplicity / researcher DoF.** 8th probe; without Holm + preregistration a false positive is
   likely and would be over-read.
5. **Embedder/classifier fine-tuning leak.** Freeze the embedder; regularize; group-CV by category.

## 7. Why this does NOT collapse under relabeling-invariance (deliverable's crux)

Relabeling-invariance bites only when the representation depends on glosses solely through *token
identity/structure*. Here the fused profile depends on **gloss meaning** (semantic embeddings / LLM
readings of the gloss words). A scramble maps gloss `Shyness → (some other word)`; the embedding of that
other word is a **different vector**, so `R_scr(w) ≠ ρ(R_real(w))` in general, and the B/C distance
matrices differ. **The theorem does not apply; the test is non-degenerate and valid.**

The honest corollary: *the very feature that saves it (using gloss meaning) is the falsified channel.* B
can exceed C only if the real sound→gloss assignment injects **label-relevant meaning** that scrambled
does not — i.e., the word's *sounds* carry meaning. That is the H1 falsified in #1–3 and #5. So validity
here is purchased at the price of testing exactly the thing already shown null. Non-degenerate, but
predicted to fail — different from the topology test (degenerate, *cannot* show signal) in that this one
*could* in principle, but evidence says it won't.

## 8. Estimated probability of success (before implementation)

- P(any cell flags positive) before correction: moderate (multiplicity) — but mostly noise/leakage.
- P(**defensible** ACOUSTIC_SEMANTIC_SIGNAL: B>A ∧ B>C ∧ B>D, post-Holm, leakage-controlled): **≈ 4–6%.**
- Of that, the share attributable to a *true* sound→incremental-meaning effect (vs residual leakage):
  small. Realistic P(true, replicable signal) ≈ **2–3%.**

Rationale: six nulls indicate the sound→gloss map carries ~no meaning; fusion cannot add information that
isn't there; the decisive B-vs-C clause directly probes the null mapping. The aesthetic tasks, which
*could* carry real signal, carry it in phonemes the gloss profile can't see.

---

## Recommendation

**This is the one proposal in the recent set that is scientifically valid and worth considering to run** —
not because it's likely positive, but because it is the **strongest, fairest, and most complete closing
test**: it fuses semantics + varṇa, uses three controls, blinds the word, and requires real to beat both
scrambled and random. If it returns NO_ACOUSTIC_SEMANTIC_SIGNAL (predicted), that is the definitive
"even combined with meaning, the varṇa mapping adds nothing" result — a clean capstone to the program. If
it surprises us, the conjunction + Holm + leakage controls make it credible.

So: **valid, non-degenerate, runnable, predicted null (~3% true-signal).** Per your instruction, I'll
**stop and wait** — tell me whether to implement the F1 (frozen-vector) version on a focused 2–3 tasks
first, or the full 7-task battery.
