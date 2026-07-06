# B1.2 R_deranged Control-Validity Review (review only — evaluates an objection, does not rescue B1.1)

## 1. Scope and non-rescue rule

This is a **review/proposal only**. It evaluates one objection to the B1.1 `R_deranged` control — that
treating every "wrong word" mapping as equally wrong is too crude, because some deranged bridges come from
semantically **near-neighbor** words and may legitimately fit. It does **not**:

- change or reinterpret the B1.1 result;
- rescue B1.1 or convert its null into a success;
- rerun scoring or judges, or edit any frozen artifact/manifest or any `varna_lens/` source;
- unblock Track B;
- claim ontology validation, Sanskrit privilege, or semantic truth.

**Locked facts:** the B1.1 verdict remains **`RANDOM_OR_SCRAMBLED_MATCHES`**; `LIMITED_GENERATION_UTILITY`
is **not earned**; Track B remains **BLOCKED**. Any revised control design (stratified R_deranged) is a
proposal for a **future B1.2** that requires its **own new prereg and new freeze**. B1.1 may not be reused as
a positive prior. **Structure, not validated meaning.**

## 2. The objection

B1.1's `R_deranged` arm assigned each target word the **real A bridge of another word** via a seeded
derangement π (π(w) ≠ w), and treated that mapping as simply "wrong." The objection:

- "Wrong word" was defined **formally** (any word other than the target), not **semantically**.
- Some deranged assignments land on **semantically near** words. A bridge built for a near-neighbor may
  share so much category-level structure with the target that a judge **reasonably** finds it fitting.
- A flat R_deranged therefore **conflates three distinct things** into one average:
  - **a. true wrong fit** — a genuinely mismatched mapping the target should reject;
  - **b. category-level fit** — a near-neighbor mapping that fits because target and source share a
    category (liquid, nourishment, warmth), not because of word-specific varṇa mapping;
  - **c. generic symbolic resonance** — the fluent-coherent-bridge effect that any real bridge supplies.

If near-neighbor derangements (b) and generic resonance (c) dominate the average, then A ≈ R_deranged
(observed AGG 0.516) could partly reflect **the control accidentally being right**, not only "no
word-specific mapping."

## 3. Why the objection is valid

The objection is conceptually sound. Under a purely formal derangement, some "wrong" bridges are only
mildly wrong:

- **milk vs juice** — both liquid, drinkable, nourishing, flowing, soft, ingested. A juice-derived bridge
  (flow, softness, intake, nourishment) plausibly fits milk.
- **doctor vs healer / medicine** — near-synonymous role framing (care, remedy, restoration); the "wrong"
  bridge describes the target's own semantic field.
- **fire vs heat / light** — direct physical entailments of fire; a heat- or light-derived bridge
  (radiance, warmth, intensity) overlaps fire's core associations.
- **mother vs nurturer / home** — shelter, care, warmth, belonging; a nurturer-derived bridge reads as
  on-target for mother.

In each case the derangement is **technically** wrong (assigned to the wrong word) but **not fully** wrong
in fit. A judge preferring such a bridge is not necessarily detecting word-specific varṇa mapping — and is
not necessarily making an error either. So a flat R_deranged average can understate A's separation from
**far** wrong mappings while overstating its difficulty against **near** ones. This is a real measurement
limitation of the flat control.

## 4. Why the objection does NOT rescue B1.1

The objection is a **design lesson for a future study**, not grounds to revise B1.1:

- **B1.1 preregistered a flat R_deranged.** The prereg, freeze, and result are locked. Re-partitioning that
  arm by semantic distance now would be a **post-hoc reanalysis of a frozen null** — exactly the move the
  adversarial protocol forbids. B1.1 cannot be re-cut after seeing its outcome.
- **R_deranged was not the only failure.** A also failed **R_domain (0.460, A loses)** and **R_same
  (0.471, A ties/loses)**, and merely **tied scrambled S (0.497)**. Even if R_deranged were entirely
  discounted, A still did not beat two other strong symbolic controls. The near-neighbor objection does not
  touch R_domain or R_same.
- **A showed no strong separation against *multiple* symbolic controls.** The B1.1 result is not "A lost one
  borderline control"; it is "A cannot distinguish itself from any fluent, real, coherent bridge." Stratified
  distance would refine *why*, but does not change *that*.
- **The direction of the confound is neutral-to-unfavorable for a rescue.** If near-neighbor derangements
  inflated R_deranged's fit, that means the flat control was, if anything, **partly a fair distractor** — it
  does not manufacture hidden A-superiority.

Therefore: **the verdict stands.** This review proposes a **stricter, better-resolved** control for B1.2, not
a reinterpretation of B1.1.

## 5. Revised B1.2 hypothesis

If the varṇa-derived bridge carries genuine **word-specific** fit (beyond category-level resonance), then
A_correct should beat wrong bridges **in proportion to semantic distance**:

- **A_correct > R_deranged_far** — largest, most robust margin;
- **A_correct > R_deranged_mid** — moderate margin;
- **A_correct ≥ R_deranged_near** — smallest margin expected; near-neighbor bridges are the hardest and A
  may only *match* them.

The **shape** of the result is the test. A **monotonic distance gradient** (far > mid > near margins) is the
signature of word-specific fit. A **flat** profile across tiers is the signature of generic resonance. And
**beating only far** while failing near/mid is the signature of **category-level resonance**, which must
**not** be overclaimed as word-specific mapping.

## 6. Deranged-distance tiers

Each tier is a separate control arm; the "wrong" bridge is another word's **real** A bridge, chosen so its
source word sits at the specified distance from the target.

- **R_deranged_near — near-neighbor wrong bridge.**
  - *Definition:* source word is a close semantic neighbor of the target (shared category, high similarity).
  - *Example:* milk ↔ juice; doctor ↔ healer; fire ↔ heat.
  - *Expected A margin:* **weakest** (A ≥ near, possibly a tie). Category overlap makes the wrong bridge fit.
  - *What failure means:* if A **loses** to near, word-specific fit is at best swamped by category resonance
    — expected, and not by itself fatal to a *category-level* reading, but fatal to a *word-specific* claim.

- **R_deranged_mid — related-but-not-equivalent wrong bridge.**
  - *Definition:* source word is in a **related** but distinct domain (adjacent, not equivalent).
  - *Example:* milk ↔ medicine, milk ↔ cloud, milk ↔ cloth.
  - *Expected A margin:* **moderate** (A > mid). Some thematic overlap, but not the same category.
  - *What failure means:* if A cannot beat mid, the "fit" A supplies is generic/broad, not target-tuned.

- **R_deranged_far — distant wrong bridge.**
  - *Definition:* source word is semantically **distant** (different domain, low similarity).
  - *Example:* milk ↔ hammer, milk ↔ contract, milk ↔ thunder.
  - *Expected A margin:* **strongest** (A ≫ far). A far bridge should visibly misfit the target.
  - *What failure means:* if A cannot even beat **far**, there is **no** recoverable word-specific signal —
    the mapping does not distinguish the target from an unrelated word's bridge. This is the strongest kill.

## 7. Semantic-distance assignment

Distance tiers must be assigned **before** generation/judging, by a documented, frozen procedure. Options
(a B1.2 would pick and pin one or a pre-specified combination):

- **Embedding similarity** — cosine between target and candidate-source word vectors (a fixed, named
  embedding model), with **pre-registered** thresholds partitioning near/mid/far. (Feasible now on a
  model-access host; would also satisfy the long-deferred real-embedding gate.)
- **WordNet / lexical-database distance** — path/Wu-Palmer similarity or shared-hypernym depth, where
  available, as a language-resource anchor independent of embeddings.
- **Human-blind semantic grouping** — annotators sort candidate source words into near/mid/far for each
  target **without** seeing bridges or outputs; inter-annotator agreement reported.
- **Manual pre-registered category labels** — a small, hand-audited target set with tiers fixed and
  justified in the prereg before any bridge is rendered.
- **Hard rule: no post-hoc reassignment.** Once frozen, a word's tier cannot move after seeing outputs or
  scores. Tier assignment is part of the freeze, seeded and hashed like every other B1.1 config.

Best practice: assign by **embedding + WordNet agreement**, break ties by blind human grouping, freeze the
result. Divergent cases (embedding says near, WordNet says far) are either dropped or pre-labeled by rule —
never resolved after the fact.

## 8. Controls against overfitting

- **Assign-before, freeze-before.** All tier labels, distractor source words, and seeds are fixed and hashed
  **before** any generation or judging. No tier is defined after seeing a single output.
- **No goalpost migration.** A far control that A fails **may not** be relabeled "actually mid/near" to
  explain the failure away. Tier membership is immutable post-freeze.
- **Controls stay fluent and plausible in every tier.** Far bridges are **real bridges from distant words**,
  not nonsense, truncation, or ugliness. "Far" means *semantically distant source word*, **not**
  *degraded text*. Making far controls bad would fake an A gradient (the B1.1 §6 failure mode).
- **A is not hand-tuned to the examples.** A_correct uses the **frozen** varṇa→bridge composition; it may
  not be re-authored after inspecting B1.1 outputs or the milk/juice examples in this review.
- **Length/register/pole matching across tiers.** All distractors matched on length, register, and
  pole-structure so the judge cannot win on surface form instead of fit — matching must be *uniform* across
  near/mid/far so tier differences reflect semantics, not style drift.
- **Leakage pre-scan with real G2P.** No varṇa labels, Sanskrit terms, or mapping metadata in any bridge
  (cf. the `artha` catch); scanned under real G2P, not illustrative spelling.

## 9. Revised success and kill criteria

**Primary success:**

- A_correct beats **R_deranged_far** with corrected CI lower bound **> 0.5**; **and**
- A_correct beats **R_deranged_mid** with corrected CI lower bound **> 0.5**; **and**
- A_correct **does not collapse** against **R_deranged_near** (A ≥ near; a tie is acceptable, a loss is not
  required to fail the study but weakens any word-specific claim).

**Stronger success (word-specificity signature):**

- A **monotonic distance gradient**: margin(A vs far) > margin(A vs mid) > margin(A vs near), each step
  surviving Holm correction and word-clustered CIs. This gradient — not any single comparison — is the
  distinctive evidence for word-specific mapping.

**Kill / down-labeling criteria:**

- **A beats far only, fails mid and near** → claim at most **broad category-level resonance**, explicitly
  **not** strong word-specific mapping.
- **A fails mid and near** → no strong word-specific mapping supported.
- **near ≈ mid ≈ far (flat profile)** → **generic symbolic resonance** remains the best explanation; the
  varṇa mapping adds nothing distance-sensitive.
- **A cannot beat far** → no recoverable word-specific signal at all (strongest kill).
- **R_same or R_domain still matches/beats A** → mapping fidelity remains **unsupported** regardless of the
  deranged gradient (these arms carry over from B1.1 and must still be beaten).

Every criterion uses word-clustered paired bootstrap CIs, Holm–Bonferroni across all co-primaries and
tiers, and the pre-specified sensitivities (drop-judge, drop-parse-fail, drop-repaired), as B1.1 required.
The only positive label a distance-stratified B1.2 may earn remains **`MAPPING_FIDELITY_SIGNAL`** (and a
gradient qualifier) — never `LIMITED_GENERATION_UTILITY`, never ontology/Sanskrit/semantic-truth, never a
Track-B unblock.

## 10. What this would clarify

Stratifying R_deranged by semantic distance separates three explanations that the flat control blends:

- **Word-specific mapping** — A shows a **monotonic gradient**, beating far most, mid moderately, near least;
  fit tracks distance, which only a word-specific signal predicts.
- **Category-level resonance** — A beats **far** but not **near/mid**; the "fit" is shared-category
  structure, not the target word's own varṇa mapping. Real but weaker, and must be labeled as such.
- **Generic symbolic resonance** — A performs the **same** across all tiers (and still can't beat R_same /
  R_domain); any fluent bridge conditions equally, distance-independent. This is the B1.1 reading, and a
  flat B1.2 profile would confirm it at higher resolution.

In short: the flat R_deranged told us A ≈ one blend of wrong bridges; the stratified version tells us
**which kind** of wrongness A can and cannot detect — turning a single number into a diagnostic curve.

## 11. Recommendation

- **Do not remove R_deranged.** It is the crux control; the fix is resolution, not deletion.
- **Replace flat R_deranged with stratified `R_deranged_near / _mid / _far`** in any B1.2, with tiers
  assigned and frozen before generation (§7) and protected against overfitting (§8).
- **Keep R_same and R_domain.** B1.1 also failed against these; dropping them would narrow the test unfairly.
  Mapping fidelity must beat them too.
- **Frame this as a stricter, fairer test — not an easier one.** Stratification adds comparisons and a
  gradient requirement; it makes a positive **harder** to earn, not easier. It exists to keep a near-neighbor
  win from being overclaimed as word-specific mapping, and to force a category-level result to be labeled
  honestly as category-level.
- **Sequencing:** this refinement composes with the `B1_2_MAPPING_FIDELITY_PROPOSAL` — a distance-stratified
  R_deranged is the deranged-arm design *within* a discriminative mapping-fidelity B1.2. It does not justify
  re-opening the generation task, and does not, on its own, warrant running anything.

## 12. Final status block

```
document:                  B1.2 R_deranged control-validity REVIEW (review only; nothing run)
reran scoring/judges:      NO
B1.1 verdict:              UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
objection status:          VALID as a design critique; does NOT rescue B1.1
LIMITED_GENERATION_UTILITY: NOT earned
only allowed positive:     MAPPING_FIDELITY_SIGNAL (with distance-gradient qualifier) — NOT utility
Track B:                   BLOCKED (unchanged; no B1.2 outcome would unblock it)
R_domain / R_same:         still beat/tied A in B1.1 — carry over as controls
Track G negative:          RANDOM_POLARITY_EXPLAINS (1fe5562; A_vs_R -0.1917, A_vs_X -0.075) — preserved
Track F negative:          CORRECTNESS_DEGRADED — preserved
ontology validation:       NONE
Sanskrit privilege:        NONE
semantic-truth claim:      NONE
requires:                  new prereg + new freeze (B1.1 not reusable as a positive prior)
```

**Structure, not validated meaning.** A refined control is proposed for a future study; the B1.1 verdict
stands, no result is rescued, Track B remains BLOCKED, and any B1.2 requires its own preregistration and
freeze.
