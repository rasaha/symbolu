# Varṇa-Attribute / KCPR Experiment Rules (Hardened)

**Status:** Governing rules memo (docs-only). Hardens how any *future* varṇa-attribute / KCPR experiment must
be designed. Not a run, not a dataset, not code.
**Governed by:** `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.
**No meaning validated. No B1.3 v3 artifact modified. No evidence freeze declared. Nothing run or scored.**
**Track B remains blocked. Structure, not validated meaning.**

Related documents:
- `SYMBOL_U_L2_VALIDATION_RULEBOOK.md` (governing framework: L1/L2/L3, probe P, baselines B, failure state ⊥)
- `MILESTONE_A_L2_FOUNDATION_SPEC.md` / `MILESTONE_A_CANDIDATE_E_AUDIT.md` (gloss-independent essence `E`)
- `B1_3_V3_L2_RULEBOOK_COMPATIBILITY_MEMO.md` (B1.3 v3 parked as pre-rulebook exploratory)

---

## 1. Purpose

This memo **hardens the experimental interpretation** of varṇa mappings. It fixes, once, the framing that any
future study must follow: a varṇa mapping is a candidate **attribute / propensity profile**, not a dictionary
meaning. Its job is to prevent the specific design leaks that make a varṇa-attribute or KCPR test look like
evidence when it is not — chiefly a generator that sees the target word, and a pole rule that confounds mapping
with kosha. It validates nothing; it constrains how future validation must be run.

---

## 2. Core correction

Stated plainly and bindingly:

- **Varṇa mappings are not dictionary meanings.**
- **They are candidate attribute / propensity / tendency profiles** proposed for a word or concept.
- **Tests must not ask whether varṇas recover the dictionary definition** of a word. That is the wrong
  question and, when a generator is shown the word, a trivially circular one.

The right question is narrow: *does the varṇa-derived attribute profile fit / predict the target concept
better than controls?*

---

## 3. Dictionary meaning vs attribute profile

- **Dictionary meaning / referent** — what the word *denotes*: its lexical definition and the thing it points
  to (e.g. *kiss* = "a touch with the lips as a sign of affection"). This is a fact about the language, known
  to any competent speaker or LLM.
- **Varṇa attribute profile** — a proposed bundle of *propensities/tendencies* assembled from the word's
  varṇas (e.g. an axis like Hope↔Detachment from *ka*, a Clarity tendency from *sa*), each resolved to a
  binding or liberating pole. This is a *claim of the theory*, not a fact about the language.
- **Why they are different test objects.** The dictionary meaning is given and shared; the attribute profile
  is the thing under test. A valid experiment must isolate the attribute profile as the *only* route to the
  judged output. If the dictionary meaning is allowed to reach the output by a second route (a word-sighted
  generator), the two objects are fused and nothing is tested. **The whole design exists to keep these two
  objects on separate wires.**

---

## 4. Clean pipeline (required, in order)

Every varṇa-attribute / KCPR experiment must implement exactly this pipeline:

1. **Target concept selected** — chosen and recorded privately; it is the hidden answer, not an input to
   generation.
2. **Generator does not see the target word** — enforced from here on (see §6).
3. **Varṇa split** — decompose the concept's word into its varṇas.
4. **Frozen varṇa attribute table** — map each varṇa to its attribute/propensity axis from a **pre-registered,
   frozen** table (never hand-edited per item, never target-fitted).
5. **Experimentally assigned kosha condition** — the kosha level is *assigned by the design* and frozen
   *before* generation (see §7), never inferred from the word afterward.
6. **Fixed KCPR pole rule** — apply the frozen KCPR rule to resolve each axis to a binding/liberating pole
   using the assigned kosha condition.
7. **Profile assembled** — ordered attributes + selected poles (see §5). This is the only carrier of varṇa
   signal.
8. **Generator writes from profile only** — a word-blind generator renders the profile into a passage; it sees
   the profile / bridge representation and nothing that reveals the target.
9. **Independent blinded judge** — a *different* model compares outputs against the target concept, blind to
   arm identity and provenance (see §10).
10. **Frozen scorer** — evaluates `A_real` against the controls with pre-registered thresholds; emits its
    label as-is.

Any experiment that deviates from this order — especially by letting the word reach Step 8 or letting the word
set the kosha at Step 5 — is out of spec and its result is not evidence.

---

## 5. Profile definition

The **profile** is the ordered bundle handed to the generator. It **is**:

- an **ordered** sequence of varṇa-derived **attributes** (order preserved from the varṇa split), and
- the **selected binding/liberating poles** for each attribute (from the frozen KCPR rule + assigned kosha).

The profile **must not contain**:

- the **target word** (or any orthographic/phonetic form of it),
- the **dictionary definition** or referent,
- the **arm identity** (real / deranged / scrambled / random / baseline),
- **source metadata** or provenance (which lexicon, which word it came from), or
- any **hidden answer key** or scorer label.

If it isn't an attribute or a pole, it does not belong in the profile.

---

## 6. Generator-word blindness rule

The **generator must not see**:

- the **target word**,
- its **dictionary meaning** / referent,
- the **candidate label** (any name for the concept),
- the **arm label**,
- **source metadata**, or
- **context wording that trivially reveals the target** (e.g. a sentence that names or unmistakably points to
  the word).

The generator **may see only** the **profile / bridge representation** (attributes + poles) plus generic,
target-neutral style instructions.

Rationale (the core leak this memo closes): if the generator sees the word, its own knowledge of the word —
not the varṇa attributes — can shape the passage, and the judge then reacts to word-knowledge rather than to
the attribute profile. A leak scan should confirm no target-revealing token reaches the generator.

---

## 7. KCPR pole rule

- **KCPR is a decoder-side pole-selection rule** (it lives at the attribute→pole step; it does not add
  meaning or language). It selects binding vs liberating for each attribute axis.
- The **kosha condition must be experimentally assigned and frozen before generation** — part of the item
  design, recorded in advance, not read off the word.
- Within a **paired comparison**, the **same kosha condition** must be applied to all arms (see §8).
- **Kosha levels may vary across items** (different items at different assigned kosha levels) or be
  manipulated in a **separate ablation** — but not inside a single A-vs-control pair.
- **Pole choice must never be inferred opportunistically from the target word's dictionary meaning after
  seeing the item.** Assign the kosha condition first; apply the rule mechanically; do not adjust the pole to
  "fit" the word.

---

## 8. Why the same kosha condition within a pair

Within one paired comparison the manipulated variable must be **the attribute mapping only**. If `A_real` and
its control arm were run under *different* kosha conditions, then two things would differ at once — the mapping
**and** the kosha/pole — and any judged difference could not be attributed to the mapping. That confounds the
thing under test (varṇa attributes) with the pole condition.

Therefore: **within a paired comparison, fix the kosha/pole and vary only the attribute mapping.** Kosha
variation is legitimate *across* items or as a *dedicated* ablation, where it is the deliberately manipulated
variable and is analyzed as such — never as an uncontrolled difference inside a single pair.

---

## 9. Arms

Allowed arms (a study need not use all, but every semantic claim must clear the controls in §11):

- **`A_real`** — the true varṇa-derived attribute profile for the target concept.
- **`R_deranged`** — a profile built from **another word** or a **mismatched varṇa sequence**.
- **`R_scrambled`** — the target's varṇa-attribute mapping with the **varṇa order scrambled**.
- **`R_random`** — a **random / relabelled** attribute profile.
- **`semantic_only_baseline`** — an ordinary **word/context meaning** baseline (no varṇa profile); the
  gloss-leakage control the claim must beat.
- **phonological baseline** — a **sound-similar, meaning-unrelated** control (required where applicable; the
  standing prior is sound-over-meaning).
- **Barnum / generic attribute baseline** — a **vague, universally-fitting** attribute profile ("Barnum"
  statements) that would fit almost any concept; guards against generic-flattery fit.

---

## 10. Judge blindness

The judge **may see the target concept** *iff* the task is explicitly **fit-to-target** evaluation ("which
passage better fits concept X"). The judge **must not see**:

- **which output is `A_real`**,
- **which output is a control**,
- the **varṇa sequence**,
- the **profile source** / provenance,
- the **arm label**,
- the **hidden key**, or
- the **scorer labels**.

The judge must be a **different model** from the generator, and it rates only the finished passages against the
target — never the machinery that produced them.

---

## 11. What counts as signal

A varṇa-derived profile is credited with signal **only if `A_real` beats all** of:

- the **deranged** profile,
- the **scrambled** profile,
- the **random / relabel** profile,
- the **semantic-only** baseline,
- the **phonological / sound** baseline,
- the **Barnum / generic** profile, and
- the **sentiment / lexicon** baseline where relevant.

Beating some but not all is **not** signal. Each un-beaten control is dispositive against the claim.

---

## 12. What does not count

The result is **not** signal (and must not be reported as such) if any hold:

- the **generator saw the target word** (or any target-revealing token),
- the **pole was chosen after reading** the target's meaning,
- the **profile was hand-tuned** for the word,
- **scrambled / random performs similarly** to `A_real`,
- the **semantic-only baseline explains** the result,
- the **judge only rated plausibility** (generic "does this read well") rather than fit-to-target against
  controls, or
- **post-hoc interpretation** is used to rescue a failed comparison.

Any of these → the correct output is a null / `⊥`, reported plainly. No rescue.

---

## 13. Relation to the L2 rulebook

This memo **operationalizes** the L2 rulebook for varṇa-attribute / KCPR tests: it is the concrete design
discipline that a probe `P` over an essence table `E` must follow for this family of studies. It **does not
itself validate `E`.** Admissibility of the attribute table remains the open, upstream question (Milestone A /
candidate-`E` audit): **if the attribute table cannot be independently sourced** — i.e. if it is derived from
the test words' dictionary meanings rather than an independent source — **the result returns `⊥`**, no matter
how cleanly the pipeline is run. Clean mechanics cannot rescue a circular `E`.

---

## 14. Relation to B1.3 v3

- **B1.3 v3 is not modified in place** by this memo. Its stimuli, scorer, thresholds, judge config, freeze
  manifest, and hashes are untouched.
- **Applying these hardened rules requires a new versioned study** — e.g. **B1.4** or **Milestone B** — built
  to this pipeline from the start.
- **B1.3 v3 remains parked / pre-rulebook exploratory** unless separately frozen and run under its **original**
  framing (the operator sequence already documented for it). It is not retroactively bound by these rules.

---

## 15. Boundary statement

> Varṇa-attribute/KCPR rules hardened for future experiments only. No meaning validated. No B1.3 v3 artifact
> modified. No evidence freeze declared. Nothing run or scored. Track B remains blocked. Structure, not
> validated meaning.
