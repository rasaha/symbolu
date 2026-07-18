# PRE-REGISTRATION (DRAFT) — Symbolic-Resonance Generation-Conditioning Evaluation

**Status:** `DOCS_ONLY — PREREG DRAFT — NOT APPROVED FOR EXECUTION`
**No model run. No generation. No scoring. No files. No code. No commit of results.**
This is a protocol proposal only. Nothing below has been executed. Freezing (§5, §6, and the Pre-execution readiness gate) and execution require **separate explicit approval**.

**Provenance:** revised 5-layer architecture `06f9bb5`; Layer 2 bridge expansion `eb95226`; no-model prompt demo shows A/R/S/C/X/D are format-matched, R/S fluent, D strongest on-topic baseline.

**Framing (binding):** engineering utility only — *not* semantic proof, *not* ontology, *not* Sanskrit privilege, *not* a Track G rescue, *not* a Track B unblock. **Informed-negative / null prior.** Track F prior remains `CORRECTNESS_DEGRADED`. Prior PSE negatives remain valid. Track G negative preserved.

---

## 1. Research question

Does **real symbolic-resonance conditioning (A)** improve generation *quality*, *steerability*, or *human preference* compared with **neutral (X)**, **dictionary-only (D)**, **random (R)**, **scrambled (S)**, and **surface-form (C)** controls — under a fixed model/task/prompt set, with all arms sharing an identical wrapper and differing **only** in the conditioning slot?

The question is deliberately narrow: it is about **prompt-conditioning behavior of a specific model on a specific task set**, not about the varṇa lexicon being true.

## 2. What this can and cannot prove

**Can prove — at most:**
- Architecture-bound **prompt-conditioning utility** (does injecting arm A's slot help *this* wrapper, *this* model, *this* task set).
- A **preference / quality difference** under the frozen model + task set.
- A **steerability difference** across controlled arms.

**Cannot prove — under any outcome:**
- That varṇas/phonemes encode meaning.
- Semantic truth, ontology, or "the process is real."
- Sanskrit privilege (any effect, if found, is a property of *a frozen table used as a conditioning prior*, not of Sanskrit).
- Support for Track B (remains **BLOCKED** independently).
- Any general/AGI claim.

A positive result would license exactly one sentence: *"Under model M and task set T, conditioning slot A was preferred over controls."* Nothing broader.

## 3. Arms

Six arms, one wrapper, conditioning slot is the **only** variable:

| Arm | Conditioning slot |
|---|---|
| **A** | Real resonance: Layer 2 synthesis of the key word's true-G2P varṇa process (frozen bridge `eb95226`). |
| **R** | Random resonance: fluent process sentence built from bridge values **not derived from the key word**. |
| **S** | Scrambled resonance: key-word varṇa structure with **permuted** pole associations. |
| **C** | Surface only: onset / vowel-count / final / consonant-position, **no associations**. |
| **X** | Neutral: user task as written, no symbolic orientation. |
| **D** | Dictionary-only: core sense + frozen synonym field, **no resonance**. |

Wrapper is fixed: `[soft orientation — does not override the task]\n{conditioning}\n\nTask:\n{task}`. Verified in the demo that only the middle slot differs and lengths are broadly matched (§11 enforces this).

## 4. Task types

Six generation task types, each represented by multiple prompts (§5):
1. Reflective paragraph
2. Gentle message
3. Metaphor generation
4. Explanation (neutral, expository)
5. Emotionally aligned response
6. Creative rewrite

Task type is a declared analysis factor: an effect that appears in **only one** task type is a kill (§10).

## 5. Prompt set (frozen before any run)

- **Frozen and versioned** before execution; hash recorded; no post-hoc additions, no substitutions.
- **Balanced across semantic domains** (emotion, abstract concept, concrete object, social relation, moral/ethical, sensory).
- **Includes both emotionally loaded and neutral/affect-flat words.**
- **Varied onset/coda structure** (voiced/voiceless onsets, vowel-initial, cluster codas, open syllables) so surface-form (C) can be separated from A.
- **Excludes the four demo words** used during development — `mercy`, `love`, `anger`, `peace` are **held out entirely** (development set only; no tuning, no inclusion) to prevent target-fitting.
- Every prompt must have a **constructible arm A** (true-G2P available, bridge coverage present) *before* freezing; words that force `[unresolved]` are declared and either excluded or carried as a separate transparency stratum — never silently dropped.

## 6. Models

- **≥ 2 distinct model families** (candidate set declared at freeze, e.g. one open-weight instruct model and one frontier instruct model). **No conclusion from a single model** — cross-model replication is a gate (§10: effect must not disappear across model/seed).
- **Model versions frozen** (exact IDs + revision hashes recorded).
- **Decoding parameters frozen** (temperature, top-p, max tokens, seed policy) and **identical across all arms** for a given item.
- **≥ 2 seeds per item** to test seed stability.

## 7. Outputs

- Exactly **one output per (prompt × task-instantiation × arm × model × seed)**. No regeneration, no best-of-N, no cherry-pick.
- Outputs **anonymized**; arm labels **hidden**; conditioning source **hidden from judges** except in a dedicated steerability sub-study that explicitly reveals *target direction only* (never arm identity).
- **No output may assert** ontology / Sanskrit truth / semantic-truth; a leak scanner (§11) flags any that do, and flagged items are reported, not silently removed.
- Output order **randomized** before judging.

## 8. Metrics

**Primary:**
- **Blinded human preference** (forced-choice and/or graded, predeclared).

**Secondary (all predeclared, all reported):**
- Relevance to task
- Coherence
- Emotional alignment (for the emotionally-aligned / gentle / reflective tasks)
- Novelty
- Controllability / steerability (does output move in the intended direction)
- Faithfulness / correctness (esp. for explanation task)
- Absence of unsupported claims (ontology / Sanskrit / semantic-truth leak rate)

Automated metrics may **supplement** but never **replace** the human primary.

## 9. Success criteria

For A to register any positive result, **A must beat X, D, R, S, and C** — not merely beat X.

**Co-primary comparisons (all five must be declared and all reported):**
- `A_vs_D`
- `A_vs_R`
- `A_vs_S`
- `A_vs_X`
- `A_vs_C`

**Threshold:** each co-primary requires the **CI lower bound > 0** (or an equivalent predeclared statistical threshold, e.g. a predefined effect size with multiple-comparison correction across the five co-primaries and across task types). Beating **only** X (the weakest control) is **not** success — it is the expected trivial outcome and maps to `NO_UTILITY` / `DICTIONARY_DOMINATES` depending on D.

## 10. Kill criteria (any one ⇒ negative label)

- A **loses to D** → `DICTIONARY_DOMINATES`.
- A **≈ R or A ≈ S** (no CI separation) → `RANDOM_OR_SCRAMBLED_MATCHES`.
- A **≈ C** → `SURFACE_STRUCTURE_EXPLAINS`.
- A **degrades correctness or faithfulness** (esp. explanation task) → `CORRECTNESS_DEGRADED`.
- Any arm-A output **asserts unsupported ontology / Sanskrit / semantic-truth** → hard fail, reported.
- Effect appears in **only one task type** → not a general utility; killed.
- Effect **disappears across model or seed** → not robust; killed.
- Outputs are **distinguishable by formatting/length** rather than content (judges can guess the arm from surface form) → confound, killed.

## 11. Blinding and leakage guards

- Judges see **no arm labels** and **no conditioning-source labels**.
- **Identical wrapper** across arms; **matched lengths** where possible; length distribution checked pre-judging and imbalance is a declared confound.
- **Leak scanner** for forbidden claims (ontology / Sanskrit-privilege / semantic-truth / "therefore means") over every output, pre-judging.
- **Randomized output order**; no two arms for the same item shown adjacently in a fixed pattern.
- **No dictionary answer-key visible** to judges (D's synonym field must not be exposed as a rubric).
- Judge pool declared; inter-rater agreement reported; a **calibration/attention-check** subset included.

## 12. Analysis plan

- **Predeclared comparisons only** (the five co-primaries + declared secondaries); anything else is exploratory and labeled as such.
- **Item-level and aggregate** reporting; per-task-type breakdown.
- **Confidence intervals** on every comparison; multiple-comparison correction stated in advance.
- **Report all six arms** and **all failures** — no arm omitted, no metric hidden.
- **No cherry-picking**, **no rerun-until-pass**: the frozen run is the run. A second run is a *new* prereg, reported alongside the first, never a replacement.

## 13. Expected prior (stated explicitly)

- **Informed-negative prior**, anchored by Track F `CORRECTNESS_DEGRADED`.
- **R and S are already observed to be fluent** in the no-model demo (any-injection confound is real, not hypothetical).
- **D dominance expected** — D is close to the answer key; `A_vs_D` is the hardest and least likely comparison for A to win.
- Prior PSE negatives (`NO_SIGNAL` under IAST and G2P) and Track G (`RANDOM_POLARITY_EXPLAINS`) both point the same way.
- **Positive result is unlikely but genuinely testable** — that combination is exactly why this is worth preregistering rather than asserting either way.

## 14. Decision labels (predeclared outcome space)

| Label | Meaning |
|---|---|
| `NO_UTILITY` | A does not beat controls (typically beats only X, or nothing). |
| `DICTIONARY_DOMINATES` | D ≥ A; lexical expansion explains any benefit. |
| `RANDOM_OR_SCRAMBLED_MATCHES` | R or S ≈ A; any-injection confound. |
| `SURFACE_STRUCTURE_EXPLAINS` | C ≈ A; phonetic surface, not the process, carries it. |
| `CORRECTNESS_DEGRADED` | A harms faithfulness/correctness (Track F pattern recurs). |
| `LIMITED_GENERATION_UTILITY` | A beats **all** of X/D/R/S/C on the co-primaries, robust across ≥2 models/seeds, no correctness loss, no leak — the *only* positive label, and still bounded to "prompt-conditioning utility under M and T," not meaning. |

## Pre-execution readiness gate

Execution may begin **only after** every item below is satisfied, in order, under separate explicit approval. Any item unmet ⇒ `NOT_READY`. Any change to a frozen item after the gate closes ⇒ `INVALID_POSTHOC` (the run is void; a new prereg is required).

- [ ] **Prompt set frozen and hashed** (§5) — content-addressed hash recorded; demo words `mercy/love/anger/peace` confirmed excluded.
- [ ] **Model IDs and versions frozen** (§6) — exact identifiers + revision hashes recorded; ≥ 2 model families.
- [ ] **Decoding parameters frozen** — temperature, top-p, max tokens, seed policy; identical across all arms per item.
- [ ] **Arm prompts generated and archived only after execution approval** — no arm text is produced or stored before the gate is approved; generation of A/R/S/C/X/D slots is itself gated.
- [ ] **Wrapper/length parity checked** — identical wrapper across arms; length distribution measured; imbalance declared as a confound before judging.
- [ ] **Leak scanner criteria frozen** (§11) — forbidden-claim patterns (ontology / Sanskrit-privilege / semantic-truth / "therefore means") fixed in advance.
- [ ] **Judge instructions frozen** — rubric, scales, and forced-choice format fixed; no answer-key exposure.
- [ ] **Randomization seed frozen** — output-order and any sampling seeds recorded before the run.
- [ ] **Analysis worksheet/script frozen** — predeclared comparisons, CIs, and multiple-comparison correction fixed before any output is seen.
- [ ] **No post-freeze edits** — otherwise `INVALID_POSTHOC`; no rerun-until-pass; a second run is a new, separately reported prereg.

## 15. Recommendation

**Remain `DOCS_ONLY`.** Do not freeze prompts/models, do not run a model, do not judge, do not write result files **until this prereg is explicitly approved for execution**. If approved, the first step is the **blind freeze** (§5 prompt set + §6 models + all tables/templates/decision rule + the Pre-execution readiness gate), committed *before* any generation; any post-freeze edit invalidates the run (`INVALID_POSTHOC`). The most probable pre-registered outcome, given the stated prior, is one of the negative labels in §14 — and that is an acceptable, publishable result.

---

**Guardrails (binding):** No ontology validation. No Sanskrit privilege. No semantic-truth claim. No Track G rescue. No Track B unblock. Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`). Track B remains **BLOCKED**. Prior PSE negatives remain valid. Track F prior remains `CORRECTNESS_DEGRADED`. No model call. No files (beyond this docs note). No code. No result artifacts.

**Structure, not validated meaning.**
