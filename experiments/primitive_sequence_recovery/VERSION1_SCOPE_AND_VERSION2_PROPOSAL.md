# Version 1 Scope & Version 2 Research Proposal (docs only)

**Research boundary document. Nothing implemented, changed, or run.** No code, no schema, no
new ontology, no manifest change, no READY, no experiment. `manifest.json` remains NOT_READY;
the runner remains NOT_RUN; Stage A untouched. This document fixes what Version 1 scientifically
established and what Version 2 would actually have to test — it does **not** design or start
Version 2.

Basis (all committed): `PROJECT_STATUS_AND_NEXT_PHASE.md`, `TRACK_C_RUN_REPORT.md`,
`diagnose_track_c.py` results, `DROPPED_VOWEL_ANTONYM_PROBE.md`, `BASELINE_REALIZER.md`,
`CONCEPT_RESOLVER_CIRCULARITY_AUDIT.md`, `CANONICAL_PRIMITIVE_REPRESENTATION.md`, the frozen
artifacts, and the test suites.

---

## Section 1 — What Version 1 evaluated

**Version 1 evaluated the *consonant-only reduction* of Symbol-U, not Symbol-U.**

Precisely: it built and tested whether the ordered sequence of a word's **consonant varṇas**
(34 consonants → opaque atoms in `assignment.json`) carries recoverable semantic signal, under
frozen realizations and a pre-registered ranking/scramble protocol. It did **not** evaluate the
full theory, because:

- `assignment.json` contains **only the 34 consonants**. Vowels, vowel length, the a-privative,
  anusvāra, and visarga are **absent from the varṇa inventory** and are dropped at decomposition.
- Symbol-U (per the project's own "varṇa = written form" stance) treats **vowels as varṇas** too.
  A test whose primitive inventory excludes vowels therefore tests a **proper subset** of the
  theory's claim.
- The corpus had to **exclude** the only three words whose contrast is vowel-borne
  (`avidyā`, `ahimsā`, `nārī`) precisely because the consonant-only representation cannot
  express them (Section 3) — an operational admission that the representation is partial.

Support from completed work: the frozen `assignment.json` (consonants only), the exclusions
recorded in `word_list.json` / `REVIEW_ONTOLOGY_ARTIFACTS.md`, and the collision analysis in
`DROPPED_VOWEL_ANTONYM_PROBE.md`.

---

## Section 2 — Evidence produced (supported vs not)

| component | what it produced | conclusion it supports |
|---|---|---|
| **Track A** (ontology/framework) | opaque-atom ontology, relabeling-invariance theorem, freeze pipeline, readiness gate, pre-registration, tests | **Supported:** a deterministic, reproducible, falsifiable *framework*; content is testable only through a realization; the gate correctly refuses to run when inputs/engine are absent. |
| **Lexical baselines** (Jaccard, LCS) | MRR 0.3478, Top1 0.140, scramble delta 0.0059, p≈0.14; bootstrap CI **[0.297, 0.403]** (includes chance 0.340) | **Supported:** lexical/surface overlap gives **no signal** (at chance). |
| **Semantic baseline** (GloVe, en_gloss, RunPod) | MRR 0.3606, Top1 0.150, semantic gain over lexical **+0.0128** | **Supported:** a small *semantic* component over pure token overlap exists — nothing more. |
| **Scramble null** (assignment scramble) | seed-0 delta 0.0259, p≈0.046; across seeds p = **[0.047,0.047,0.043,0.048,0.064]** | **Supported:** the gate pass is **unstable** — one seed exceeds 0.05; not stably significant. |
| **Bootstrap** (family-aware, GloVe) | MRR 95% CI **[0.308, 0.417]** — includes chance; `ci_low_above_chance=false` | **Supported:** the effect is **not robust** to corpus resampling. |
| **Dropped-vowel probe** (mechanical) | exactly 3 consonant-skeleton collisions, all antonym/gender pairs; 0 among active words | **Supported:** meaning-flipping information can live **entirely in dropped vowels/prefixes**; consonant-only is lossy. |

**Conclusions that ARE supported:** (1) the framework is sound and honest; (2) on the
consonant-only rendering, there is **no robust semantic signal** (English channel) — a
negative-leaning, at-chance result; (3) the consonant-only representation is provably lossy for
a real class of contrasts.

**Conclusions that are NOT supported (and must not be claimed):** (a) that varṇas carry
intrinsic meaning (`ONTOLOGICAL_SIGNAL` — never emitted, never testable here); (b) any
cross-realization result (`sa_term`/`concept_id` were never runnable — no Sanskrit vectors, no
non-circular resolver); (c) that Symbol-U as a whole was tested or refuted; (d) that the small
GloVe > lexical gain is a stable or meaningful signal (bootstrap and multi-seed say it is not).

---

## Section 3 — Why consonant-only is a lossy representation

Consonant-only decomposition discards vowels, vowel length, and the a-privative prefix. For
three corpus words the *entire* contrastive meaning lives in exactly that discarded material, so
distinct words collapse to one canonical sequence:

- **vidyā (knowledge) vs avidyā (ignorance)** → both `va·da·ya`. Removed: the initial **vowel
  `a`** (the a-privative = negation). The only difference between "knowledge" and "ignorance" is
  a dropped vowel.
- **himsā (violence) vs ahimsā (nonviolence)** → both `ha·ma·sa`. Removed: the **a-privative
  `a`**. "violence" vs "nonviolence" differ only by a dropped vowel.
- **nara (man) vs nārī (woman)** → both `na·ra`. Removed: **vowel length and the gender vowel**
  (a-stem masculine vs ī/ā feminine). Gender is entirely vocalic here.

In each case the consonants are identical and the meanings are opposite/contrastive: the
representation is **information-losing** with respect to a real, productive class of Sanskrit
semantics (privatives, gender). This is a structural property, shown mechanically, with no model.

---

## Section 4 — Does this invalidate Version 1?

**Separate the two axes cleanly:**

- **Engineering validity: intact.** The pipeline is correct, deterministic, reproducible, and
  honest. It ran end-to-end on real hardware, reproduced bit-identically, kept every guardrail
  (no `ONTOLOGICAL_SIGNAL`, manifest NOT_READY, runner NOT_RUN, Stage A untouched), and its
  freeze/gate machinery correctly excluded the unrepresentable pairs and refused to overstate a
  fragile effect. **No engineering failure.**
- **Scientific scope: bounded, and stated up front.** Version 1 successfully evaluated a
  **reduced representation** (consonant-only) and returned a defensible **negative-leaning /
  no-robust-signal** result *for that representation*. It did **not**, and could not, evaluate
  full Symbol-U.

**So: Version 1 did not fail — it successfully evaluated a reduced representation.** The result
is a valid negative for the consonant-only hypothesis, not a botched test of the full theory.
Crucially, this does **not** weaken the negative: on the representation it *did* test, the signal
is at chance and non-robust. The lossy-representation finding limits the *scope* of that
negative; it does not soften it.

---

## Section 5 — What Version 2 would have to change (not a design)

Version 2 would have to change the **representation**, not the realizer:

- **Vowel primitives** — add the vowel varṇas (a, ā, i, ī, u, ū, e, ai, o, au, ṛ, …) as
  first-class atoms in the assignment.
- **Privative / morphological markers** — represent the a-privative (and, for nara/nārī,
  vowel-length/gender) as meaning-bearing varṇas rather than dropped material.
- **Revised canonical representation** — re-decompose words to full varṇa sequences so that
  vidyā/avidyā, himsā/ahimsā, nara/nārī receive **distinct** canonical sequences.

**Why these are representation changes, not semantic-realizer changes:** they alter *what the
opaque primitive sequence is* — the domain over which every realization and every score is
computed — **before** any realizer sees anything. The realizer (lexical, embedding, concept) is
unchanged in kind; it would simply operate over a different, larger primitive alphabet. Changing
the alphabet changes the *object of the hypothesis* (what counts as the carrier of meaning),
which is upstream of and independent from how content is attached or scored.

Note: none of this touches the **semantic** blockers. Sanskrit vectors and a non-circular
concept resolver remain unavailable, so Version 2 would still be **English-only / exploratory**
and **Track B would remain blocked** unless those are independently solved.

---

## Section 6 — Predictions (none assumed)

If Version 2 (vowel-aware representation) were eventually built and run under a new
pre-registration:

- **Outcome A — no improvement.** Vowel-aware recovery ≈ chance, like consonant-only.
  *Interpretation:* strengthens the negative — meaning is not recoverable from ordered varṇa
  primitives even with the fuller alphabet; the earlier collisions were a representational gap,
  not a hidden signal.
- **Outcome B — small improvement.** A modest, possibly non-robust gain (e.g., antonym pairs now
  separable but overall MRR barely above chance). *Interpretation:* the gain is most likely the
  **mechanical** effect of the a-privative being visible (avidyā now differs from vidyā by one
  atom), i.e. morphology, **not** evidence that vowels carry intrinsic vṛtti meaning — must be
  controlled by testing whether the improvement generalizes beyond the privative/gender cases.
- **Outcome C — large, robust improvement.** Vowel-aware recovery clears chance with a
  bootstrap CI above chance and stable across seeds. *Interpretation:* the **first** genuinely
  positive exploratory result — still English-only (`REALIZATION_ARTIFACT` ceiling) and still
  confounded by shared-source (F4); it would motivate, not constitute, a confirmatory test.

None of these is assumed; each requires its own null controls (a large improvement driven solely
by the privative morphology would be a confound, not a confirmation).

---

## Section 7 — Continuation or new hypothesis?

**Version 1 should be considered complete** for the hypothesis it posed (consonant-only), with a
clear negative-leaning result and a documented scope.

**Version 2 must be treated as an ENTIRELY NEW HYPOTHESIS, not a continuation.** Justification:

- It changes the **primitive alphabet** — the very carrier the hypothesis is about. "Ordered
  *consonant* primitives carry meaning" and "ordered *full-varṇa* primitives carry meaning" are
  **different claims** with different objects, different canonical representations, and different
  failure modes.
- Reusing Version 1's frozen artifacts, distractors, or (worse) its results across the two would
  be a **representation swap under a fixed conclusion** — a researcher degree of freedom. The
  pre-registration, ontology freeze, and manifest are all keyed to the consonant-only object.
- Therefore Version 2 requires a **new pre-registration, a new frozen ontology, new distractors,
  and a new evaluation pipeline instance** (a `manifest_v2`-style freeze that is a *new* record,
  not an edit of Version 1). Version 1's negative stands on its own and is not retro-actively
  reinterpreted by Version 2's existence.

---

## Section 8 — Final recommendation

**STOP AFTER VERSION 1.**

On methodology alone (not optimism, not attachment to the theory):

- Version 1 has a **clean, defensible result**: a sound, reproducible framework plus a
  **negative-leaning / no-robust-signal** finding for the consonant-only hypothesis. That is a
  complete, publishable unit.
- The two independent blockers on any *meaningful* Version-2 advance are **unsolved**: (1) the
  **semantic channels** (Sanskrit vectors, non-circular concept resolver) that would let a result
  escape the English-only `REALIZATION_ARTIFACT` ceiling, and (2) the **shared-source ceiling
  (F4)** — with no independent second meaning source, even a positive vowel-aware result is
  necessary-not-sufficient. Building Version 2 while these stand would produce, at best, another
  English-only exploratory number under the same ceiling.
- Version 2 is a **new hypothesis** (Section 7); it deserves its own pre-registration and a
  deliberate decision to open, **not** momentum from Version 1.

**Recommendation:** freeze and write up Version 1 as-is (framework + scoped negative). Record the
vowel-aware model as a **proposed new hypothesis (Version 2)** to be opened only with a fresh
pre-registration **and** a credible plan for the semantic/independence blockers — not before. Do
not begin Version 2 now.

---

## Report

- **File:** `experiments/primitive_sequence_recovery/VERSION1_SCOPE_AND_VERSION2_PROPOSAL.md`
- **Docs-only:** yes — no code, schema, ontology, manifest, or experiment.
- **No experiment executed;** manifest still NOT_READY; runner still NOT_RUN; Stage A untouched.

> structure, not validated meaning.
