# Symbol-U L2 Validation Rulebook

**Status:** Governing memo (docs-only). Standalone. Forward-looking.
**Scope:** Defines the layered validation architecture and the rules any *future* Symbol-U
semantic-validation study must satisfy. It is a rulebook, not a study.
**It does not alter B1.3 v3, does not declare evidence freeze, and does not validate meaning.**
**Track B remains blocked. Structure, not validated meaning.**

---

## 1. Purpose

This document is the governing validation rulebook for **future** Symbol-U semantic testing. It fixes a
common vocabulary and a common evidentiary bar so that any later study — Milestone A foundations, a
gloss-independent validation, an L2 latent-semantic-formation test, a probe/baseline design — can be judged
against the same rules.

It is deliberately upstream of any experiment. It **does not alter B1.3 v3** and **does not alter any frozen
or already-audited study**. It introduces no result, declares no freeze, unblocks nothing, and reinterprets
no prior finding. Adopting this rulebook for a specific study requires a separate, explicit act (a
compatibility memo or a new versioned study); merely writing this rulebook applies it to nothing.

---

## 2. Layer separation

The Symbol-U pipeline is separated into three generative layers plus one evidentiary layer. The separation is
the point: a claim proven at one layer is not a claim proven at another, and the machinery that *produces* an
output is never the machinery that *validates* it.

- **L1 — Structural operator layer.** Composition of per-varṇa operators over a state. Frozen. Structural.
- **L2 — Latent semantic formation.** A candidate map from the operator trace to a latent semantic space.
  Not fixed, not validated.
- **L3 — Semantic decoders.** Interchangeable read-outs from the L2 latent to human-facing semantic labels.
- **Validation layer.** Probe `P`, baseline suite `B`, and failure state `⊥`. This layer, and only this
  layer, decides whether any L2/L3 semantic claim is real.

Each layer is defined in the sections below.

---

## 3. L1 — Structural layer (frozen)

**Definition.** L1 is the structural operator recurrence

```
t_i = M_{σ_i} · t_{i−1}
```

where `σ_i` is the i-th varṇa of a word and `M_{σ_i}` is that varṇa's operator. L1 is **frozen** and is
**structural only**.

**What L1 has and has not earned.** Under Stage A, the structural gates **G1, G2, G3 pass**; the **G4
factorization is not validated**. L1's passing gates are statements about *structure* (the operators compose,
recover sequences, and behave as an operator algebra to the tested extent). They are **not** a statement about
*meaning*. Passing G1–G3 does not license any semantic claim, and G4 remains unvalidated.

**Constraint.** L1 is not modified by this rulebook. Nothing here re-opens, re-scores, or re-labels L1 or
Stage A. L1 supplies structure; semantic validation lives entirely above it.

---

## 4. L2 — Latent semantic formation (candidate only)

**Definition.** L2 is a candidate map from the L1 operator trace and an initial state to a latent semantic
space `S`:

```
z = F(M_{σ_1}, …, M_{σ_n}, s_0) ∈ S
```

`z` is a latent semantic representation of the word; `F` is the formation function.

**Status.** L2 is a **candidate only**. `F` is **not yet fixed and not yet validated**. No particular `F` is
privileged by this document.

**Admissibility conditions on `F`.** For an `F` to even be *eligible* for validation, it must be:

1. **Gloss-independent** — `F` may not read, encode, or look up dictionary meaning, definitions, or glosses.
   Its inputs are the operators and the initial state, not the word's meaning.
2. **Non-additive** — `F` may not be a bag-of-varṇa sum or average; order/composition must matter, or the
   claim collapses to a set-of-letters claim already covered by ablation baselines.
3. **Operator-derived** — `F` must be a function of the L1 operators / trace, not an independent hand-tuned
   semantic embedding smuggled in beside them.
4. **Baseline-testable** — `F` must yield an output that a probe can score against the baseline suite (§7).

An `F` that fails any admissibility condition is not eligible; it is not "weak evidence," it is out of scope.

---

## 5. L3 — Semantic decoders (interchangeable)

**Definition.** L3 is a decoder from the L2 latent to a human-facing semantic output:

```
y = D(z)
```

**Interchangeability.** Multiple decoders are possible over the *same* `z`: a **DBP** (dual/binding-polarity)
decoder, a **transformation** decoder, a **polarity** decoder, and others. These are **interchangeable
decoders**, not competing theories of the primitive.

**DBP is one decoder, not the primitive theory.** The binding/liberating polarity read-out (DBP) is *one
possible decoder* `D`. It is not the definition of L2, not the definition of the primitive, and not
privileged. Swapping DBP for another decoder changes the read-out, not the underlying latent; a decoder's
success or failure is a statement about that decoder over `z`, not about Symbol-U as a whole.

---

## 6. Probe / decoder separation

A **decoder** and a **probe** are different objects and must never be conflated.

- A **decoder** `D` *generates* a semantic output. Generating an output is cheap and always possible: any
  latent can be read out into some label. **Producing a plausible semantic output is not evidence.**
- A **probe** `P` *tests* a decoder's output against the baseline suite `B`. Only a probe that beats all
  required baselines validates signal.

Therefore:

> **A probe is not a decoder. A decoder is not proof.**

A study that only exhibits a decoder producing sensible-looking outputs has shown nothing about signal. Signal
is what survives `P` against `B`.

---

## 7. Baseline suite

Any semantic claim must **beat all** of the following baselines. Beating some but not all is a failure, not a
partial success.

Required baselines (`B`):

1. **Random / relabel** — permuted or randomly reassigned varṇa→state labels.
2. **Bag / sequence ablation** — order-destroyed (bag-of-varṇa) and sequence-shuffled variants.
3. **Phonological similarity** — nearest phonological neighbors (sound-similar, meaning-unrelated), to catch
   sound-driven artifacts.
4. **Length / frequency** — word length and corpus-frequency matched controls.
5. **Sentiment / lexicon** — off-the-shelf sentiment or affect-lexicon predictors.
6. **Dictionary / gloss leakage** — a control that has access to the gloss; if the "signal" is matched by a
   gloss-reading control, the signal is gloss leakage, not varṇa structure.
7. **Chance / null** — the appropriate chance / null-distribution baseline for the endpoint.

**Rule.** A semantic claim is admissible only if the probe beats **every** baseline in `B` by the
pre-registered margin. Any baseline it fails to beat is dispositive against the claim.

---

## 8. Failure state (⊥)

`⊥` is a **valid and correct output**. When the system does not beat the baselines, the correct result is `⊥`
("no validated signal"), reported plainly.

`⊥` is not a bug, not an incomplete run, and not an invitation to re-tune until the sign flips. A study that
returns `⊥` has done its job. Reporting `⊥` honestly is the expected behavior of this program, given the
current priors (§10).

---

## 9. Gloss-independent essence table `E` (terminal rule)

**Definition.** `E` is a table assigning each varṇa its "essence" **independently of dictionary meaning**. `E`
is a **required foundation for Milestone A**: without a gloss-independent `E`, there is no non-circular source
for varṇa semantics to validate.

**Terminal rule.**

> If `E` cannot be defined **independently of dictionary meaning**, the semantic-validation program **must
> stop or return `⊥`.**

That is: if every attempt to specify `E` ends up covertly reading the gloss (defining a varṇa's essence by the
meanings of the words that contain it), then the essence table is circular, there is nothing gloss-independent
to test, and the program terminates at `⊥`. This is a hard stop, not a soft caution. A circular `E` cannot be
rescued by a cleverer decoder or a larger judge panel.

---

## 10. Relation to prior empirical reality (NEGATIVE priors — do not reset)

This rulebook is written **on top of an existing negative record**. Those priors stand and are **not reset**
by adopting this architecture:

- **O1.5 construct gate — failed.** The construct-validity gate did not pass.
- **Corpus norms — near-null.** S1/S2 corpus-norm signal is near null.
- **Synonyms share varṇa content at near-random.** Near-synonyms do not share varṇa structure above chance;
  phonetic similarity and semantic similarity are decoupled (arbitrariness of the sign).
- **Sound-vs-meaning sensitivity favors sound.** Where sensitivity exists, it tracks sound, not meaning.
- **Loss is upstream, at grapheme→varṇa decomposition.** The signal loss appears at the grapheme→varṇa
  decomposition step, upstream of any semantic layer.

Additional standing negatives preserved verbatim (not reset, not reinterpreted):

- **B1.1: `RANDOM_OR_SCRAMBLED_MATCHES`** — real varṇa assignment did not beat random/scrambled.
- **Scrambled ≈ real at 0.967** — blinded scrambled-vs-real agreement is ~0.967 (the pole layer is not
  distinguishing them).
- **Register-field: CLOSED.**
- **Vṛtti: CLOSED.**
- **Track G: `RANDOM_POLARITY_EXPLAINS`.**
- **Track F: `CORRECTNESS_DEGRADED`.**

The starting prior for any new semantic claim under this rulebook is therefore **low**, and the burden is on
the claim to beat the full baseline suite.

---

## 11. Relation to B1.3 v3

This rulebook **does not modify B1.3 v3**. Specifically:

- B1.3 v3 remains **artifact-ready but unscored**. It is not scored, frozen for evidence, or run by virtue of
  this document.
- Applying this rulebook to B1.3 v3 is **not automatic**. It would require a **separate compatibility memo**
  or a **new versioned study** that explicitly maps B1.3 v3's arms, scorer, and thresholds onto this
  architecture.
- Nothing here changes B1.3 v3's stimuli, scorer, thresholds, prompts, judge IDs, freeze manifest, or hashes.

Until such a separate act, B1.3 v3 and this rulebook are independent.

---

## 12. Allowed future use

This rulebook **may govern**:

- **Milestone A foundations** — including the definition and gloss-independence test of `E`.
- **B1.4 gloss-independent validation** — a future study built to the admissibility and baseline rules here.
- **L2 latent semantic-formation tests** — studies that fix and test a specific `F`.
- **Future probe / baseline design** — the design of `P` and extensions to `B`.

Any such use is a new, explicitly-declared study, subject to every rule above (admissibility, baseline suite,
failure state, terminal rule).

---

## 13. No-rescue rule

This rulebook **cannot be used to reinterpret prior null or negative results as positive**. It introduces no
mechanism, framing, or "layer" by which an existing `⊥`, a CLOSED track, or a `RANDOM_OR_SCRAMBLED_MATCHES` /
`RANDOM_POLARITY_EXPLAINS` / `CORRECTNESS_DEGRADED` verdict becomes a signal. Prior negatives are inputs to
this rulebook (§10), not targets for it to overturn. Any future use that would have the effect of relabeling a
past negative as positive is out of scope and prohibited.

---

## 14. Boundary statement

> This rulebook governs future Symbol-U semantic validation. It does not alter B1.3 v3, does not declare
> evidence freeze, and does not validate meaning. Track B remains blocked. Structure, not validated meaning.
