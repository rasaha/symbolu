# Validity Assessment — Lexical + CSR + Acoustic "Resonance Validator"

> **Task:** decide, *before implementing*, whether the proposed three-layer experiment (System A =
> Lexical+CSR; B = +Real acoustic validator; C = +Scrambled acoustic validator) is scientifically valid
> and whether the acoustic validator can be isolated cleanly enough to test. **Conclusion: NO — the
> decisive B-vs-C comparison is structurally degenerate or circular.** Details + the 7 requested
> deliverables below. Builds on the five accepted nulls and the `phoneme_overreach` firewall.

---

## 0. Headline verdict

**The experiment is not valid as specified, for one precise reason — the relabeling-invariance theorem
below.** A scrambled lexicon differs from the real lexicon *only* in the gloss strings attached to
sounds; the phonemes, positions, signs (+/−), and dissolution structure are identical. Therefore:

- Any validator score that depends on **sound** (euphony, rhythm, phoneme/propensity-token overlap with
  the context) is **mathematically identical** for real and scrambled ⇒ **B ≡ C**. The critical control
  can never fire. The test is degenerate.
- The **only** way to make the real validator score differently from the scrambled one is to use the
  **semantic content of the glosses** (treat "Compassion", "Hope" as meanings and match them to the
  context's meaning/latent state). That is exactly the sound→meaning decoding falsified in tests 1–3,
  and routing it into candidate selection is the `phoneme_overreach` firewall breach. The test becomes
  circular: B>C would *measure the leak the program already rejected*, not validate it.

So there is no clean middle: **contract-safe ⇒ B≡C (degenerate); B≠C ⇒ contract-violating + falsified.**

---

## 1. Architecture sketch (and where it breaks)

```
                 ┌──────────────────── System A (baseline) ────────────────────┐
 context ──► CSR latent state ──► candidate realizations {w1..wk} ──► pick argmax CSR-fit ──► output
                 └──────────────────────────────────────────────────────────────┘

 System B / C add a post-hoc acoustic re-ranker over the SAME candidates:

     {w1..wk} ──► acoustic validator V(w_i | context) ──► re-rank/select ──► output
                          │
                          ├─ B: V uses REAL lexicon glosses
                          └─ C: V uses SCRAMBLED lexicon glosses
```

Two problems are visible already:

1. **Firewall (`phoneme_overreach`).** STRATEGY Part 6 forbids any varṇa-derived value as a "feature,
   prior, score, reranker, or retrieval key" into C×R×S / Conscious Generation. The validator is, by
   definition, **a varṇa-derived re-ranker over the generation's own candidates**, selecting the output.
   "Post-hoc" placement does not exempt it — it still injects an acoustic score into what the system
   emits. This is the named taboo.
2. **The target problem.** "Validate alignment with the latent state" requires a *target in propensity
   space*. There are only two ways to get one, and both are dead ends (§2).

## 2. Exact validator formulation — and the dilemma it forces

Let the lens be a deterministic map from a word to a multiset of propensity tokens through its phonemes:

```
L(w) = { g(p) : p ∈ phonemes(w) }        g : sound → gloss   (bijective on consonants; bijective on vowels)
```

A **scramble** replaces g with g∘π, where π is a permutation of the gloss set (a pure relabeling). Every
other part of the reading — phoneme segmentation, onset/coda sign, dissolution arc — is unchanged.

A validator needs a score `V(w | ctx)`. Enumerate the only families:

**(a) Euphony / phonetic form** — `V = f(phonemes(w), phonemes(ctx))` (alliteration, rhythm, vowel
balance). `g` never appears ⇒ **V_real = V_scrambled identically** ⇒ B ≡ C.

**(b) Propensity-token overlap with context** — `V = sim(L(w), L(ctx))` (shared-token count, cosine over
token counts, Jaccard). Because π is a bijection applied to *both* L(w) and L(ctx):
`sim(πX, πY) = sim(X, Y)` for any identity-matching similarity. ⇒ **V_real = V_scrambled** ⇒ B ≡ C.

> **Relabeling-invariance theorem.** Any validator whose score depends only on (i) phonemes or (ii) the
> *matching pattern* of propensity tokens between candidate and context is invariant under lexicon
> scrambling. Proof: scrambling is a bijection on glosses; phoneme- and match-based scores are
> functions of phonemes / set-intersections, both preserved by a bijection applied to all operands. ∎
> (Caveat: geminate collapse and the consonant/vowel split make the bijection piecewise; this leaves
> only *noise*-level differences, never a systematic real-over-scrambled effect.)

**(c) Gloss-semantics vs latent state** — `V = sim_meaning( embed("Compassion"...), latent_target )`,
i.e. read the glosses as meanings and match them to the context's meaning/latent state. This is the
**only** family where V_real ≠ V_scrambled (different gloss strings ⇒ different embeddings). But:
- It is the **falsified** sound→meaning map (tests 1–3: real ≈ chance ≈ scrambled at recovering meaning).
- It is the **firewall breach** (varṇa-derived semantic score into selection).
- So a B>C here would not be a "validation signal" — it would be a re-measurement of the leak, and the
  pre-registered interpretation rules already forbid the conclusion it would invite.

**Conclusion of §2:** the contract-safe validators (a,b) give B≡C; the only B≠C validator (c) is
falsified-and-forbidden. The validator cannot be isolated cleanly.

## 3. Evaluation protocol (if one insisted on running it anyway)

Tasks where wording matters (counseling, teaching, storytelling, naming, reflection, dialogue). For each
prompt: CSR produces a latent state and k candidates; A picks by CSR-fit; B/C re-rank by V. Then:
- **Blind pairwise human preference:** A–B, B–C, A–C, **counterbalanced** (each pair shown in both
  orders, averaged — the utility test failed partly on a position bias larger than the effect).
- **Consistency:** repeated generation from the same latent state; measure semantic drift.
- **Contradiction rate:** contradictions to context (NLI-style), human-audited sample.
- **Latent-state alignment:** distance of the selected wording's CSR-encoding to the target state.

⚠️ **Two of these metrics are self-invalidating for this hypothesis:**
- *Latent-state alignment* uses CSR's own space as ground truth — but then the optimal selector is "rank
  by CSR proximity" (which is System A). The acoustic layer can only help if sound carries latent info
  beyond lexical+context — the falsified link. And if V is tuned to this metric, you are optimizing the
  metric you score on (circularity).
- *Contradiction rate / drift* are meaning properties; a meaning-blind re-ranker can only hold them
  constant or worsen them, never improve them — so they cannot produce a positive acoustic signal.

## 4. Real-vs-scrambled controls — status

The control is the right idea (it is the same lever used five times). The problem is not the control; it
is that **under any admissible (contract-safe) validator the control is degenerate (B≡C)**, and under the
only validator that breaks the tie the control reveals the forbidden mechanism. A genuinely informative
real-vs-scrambled test requires the score to depend on *which sound carries which propensity* — which is
precisely what scrambling destroys and what five tests say carries no signal.

## 5. Statistical analysis plan (for completeness)

Per metric: paired bootstrap (10 000 resamples over prompts), 95% CI on B−A, B−C, A−C; counterbalanced
preference rate with CI; pre-registered `MIN_EFFECT` (e.g. 0.30 on a 5-pt preference scale, matching
prior preregs). Verdict by rule: **ACOUSTIC_VALIDATION_SIGNAL** iff CI_lower(B−A) > 0 **and**
CI_lower(B−C) > 0 **and** both ≥ MIN_EFFECT; else **NO_ACOUSTIC_VALIDATION_SIGNAL**. Multiple-testing
correction across the 6 tasks × 4 metrics (Holm) — without it, ~1 in 20 cells will "pass" by chance, and
this is the program's 6th probe (cumulative false-positive risk is now the dominant danger).

## 6. Predicted failure modes

1. **Degenerate control (primary).** B and C produce identical (or noise-only different) selections ⇒
   B≈C by construction ⇒ NO_ACOUSTIC_VALIDATION_SIGNAL, uninformative about the hypothesis.
2. **Leak-through "success".** If V is allowed to use gloss embeddings, B may beat C — but this is the
   falsified sound→meaning channel and a firewall breach; the result is inadmissible, not a discovery.
3. **Euphony confound.** B>A may appear from pure euphony (real sound-patterning humans like) — but
   euphony is scramble-invariant, so it gives B≈C ⇒ fails the decisive clause anyway, and isn't a
   property of the "dictionary."
4. **Metric circularity.** Optimizing latent-state alignment that is also the success metric inflates a
   non-effect.
5. **Re-ranker harms meaning.** A meaning-blind re-ranker can only equal or worsen contradiction/drift.
6. **Researcher-degrees-of-freedom / multiplicity.** 6th reframe; without strict preregistration + Holm,
   a spurious cell will likely appear and be over-read.

## 7. Estimated probability of success (before running)

Define success = **contract-safe** ACOUSTIC_VALIDATION_SIGNAL (B>A *and* B>C, CIs clear of 0, ≥
MIN_EFFECT, no gloss-as-meaning).

**Estimate: ~3%** — and that 3% is essentially the false-positive floor (multiplicity + judge noise),
not the footprint of a real effect. The relabeling-invariance theorem makes a *true* contract-safe B>C
structurally impossible; the only paths to an apparent B>C are (i) statistical noise or (ii) the
forbidden gloss-semantics channel. P(a *defensible*, replicable, contract-safe signal) ≈ **1–2%**.

---

## What *is* cleanly testable (the salvage)

Drop the claim that the **Sanskrit dictionary** validates meaning, and test only what survives the
theorem: **phonetic-aesthetic control.** Build A vs B′ where B′ re-ranks candidates by a *sound-palette*
target defined over **phoneme classes** (sibilance, open vowels, plosive density), and control against a
**random phoneme-target** validator (not a scrambled-gloss one). Measure blind, counterbalanced human
euphony/fit preference.

- This is contract-safe: it is a **style/aesthetic** signal (allowed), never a meaning/score signal.
- It can genuinely succeed or fail, and the control is *not* degenerate (random phoneme targets differ
  from the chosen palette in sound, not just in label).
- But note honestly: it tests **sound-aesthetic controllability**, which the integration design already
  identified (patterns A3/A4) as the *only* honest generative use — and it does **not** rehabilitate the
  varṇa→meaning lexicon. The glosses play no role.

## Recommendation

**Do not run the A/B/C experiment as designed.** It cannot return an admissible positive: the contract-
safe versions are degenerate (B≡C) and the discriminating version is the falsified, firewalled leak. If
you want a live experiment, run the **phonetic-aesthetic** salvage above — but bank it as a test of
sound control, not of the acoustic dictionary's meaning-validation power, which the relabeling-invariance
theorem shows this design cannot probe.
