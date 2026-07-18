# B1.5 — Three-Clue Word Recovery — Pre-Registration

**Status:** Pre-registration (docs-only). A **new, separate track** — not a continuation or rescue of B1.4b′.
No code, no dataset (beyond one `TOY_ONLY` illustration), no run.
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`. Original B1.4b remains blocked. Track B remains blocked. Structure, not
validated meaning.**

Related: `B1_4B_PRIME_SCREENING_OPERATOR_COMMANDS_EXECUTED.md` (`880ad1a`, NULL),
`B1_4B_PRIME_WORD_IDENTITY_BLINDING_CLARIFICATION.md` (`6edf3ea`), `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`,
`VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md`.

---

## 1. Purpose

This is a **different task** from B1.4b′:

- **B1.4b′** asked: *do phoneme/operator (Stage A′ → F-3) structural features **predict** a concept's McRae
  object-attribute vector, without lexical identity?* Answer, on record: **`NULL_RETURN_BOTTOM`** (all arms at
  chance). **That result stands.**
- **B1.5** asks a narrower, different question: *given three semantic **clue words**, can a scoring method
  **rank/recover** the intended target word from a candidate set — better than chance and better than
  structure-scrambled controls?*

These are not the same claim. B1.5 is a **task-utility ranking** test, not an attribute-prediction test. Drafting
B1.5 does **not** erase, weaken, or reinterpret the B1.4b′ null (§14).

## 2. Hypothesis

**H1 (narrow, candidate):** a Symbol-U / varṇa / Stage A′ / F-3 scoring method can rank the intended target
word given a three-word semantic clue triad **above chance** and **above structure-scrambled/random controls**.

**H0 (null, expected default given priors):** Symbol-U triad scoring does no better than random/shuffled
controls, and any apparent ranking utility is explained by an ordinary **semantic-embedding** baseline (the task
is semantic) or by phonology/length/frequency.

The burden is entirely on the Symbol-U arm to beat **all** controls (§7, §10).

## 3. What this experiment CAN prove

- **Task-specific ranking utility** under a constrained word-recovery setup: whether the Symbol-U scoring, as an
  operational procedure, ranks the right target above chance and above its own scrambles — a statement about
  *utility on this task*, nothing more.

## 4. What this experiment CANNOT prove

It cannot prove: an ontology; Sanskrit semantic truth; universal word meaning; `ONTOLOGICAL_SIGNAL`; that
B1.4b′ was wrong; or that word-identity leakage is acceptable. A win here would be **task utility**, explicitly
**not** validated meaning. If a semantic embedding wins, the task is simply semantic and Symbol-U adds nothing
(`TRIAD_COLLAPSES_TO_SEMANTIC_EMBEDDING`).

## 5. Dataset design

Small initial dataset, **frozen before any scoring**:

- **Fields per item:** `target` (one word), `clues` (exactly three semantic clue words), `candidate_set`
  (target + matched distractors), optional `category`, `source`, `clue_origin`.
- **`clue_origin`** must be recorded per item: `human_written` / `dataset_derived` / `llm_generated` — and the
  Symbol-U arm may **never** see any LLM rationale (§8).
- **Source / provenance:** documented per item; license-clear. Human-written or derived from an existing
  license-clear association/feature norm are preferred over unconstrained LLM generation (LLM-generated clues
  are permitted only if labelled and never accompanied by LLM explanations to the scorer).
- **Freeze:** the dataset, candidate sets, and all fields are hash-frozen **before** any arm is scored. No
  post-hoc edits (§8).

**TOY_ONLY illustration (not a dataset; format only, not for scoring):**

| target | clues | candidate_set (target + distractors) | clue_origin |
|---|---|---|---|
| mother | nurture, care, protection | mother, stone, knife, river, market, thunder | TOY_ONLY |

*(Illustrative format only. Marked `TOY_ONLY`. Not frozen, not scored, not evidence.)*

## 6. Candidate construction

- **One correct target** per item; all other candidates are **distractors**.
- **Candidate-set size:** pre-registered per run — one of **{10, 20, 50, 100}** (chance = 1/size). Larger sets
  give a stronger test.
- **Matched distractors:** matched to the target for **frequency, length, concreteness, and category** where
  possible, so ranking cannot be won on those nuisance dimensions.
- **No trivial clue↔target spelling/phoneme overlap** — a clue may not share the target's spelling or be a
  near-orthographic/phonetic twin (would let phonology or string matching win trivially); such items are
  excluded or explicitly labelled easy cases.
- **No direct near-synonym clues** unless the item is explicitly labelled an *easy case* and analysed
  separately.

## 7. Arms

All arms rank the **same candidate set** for the **same triad**; identical items/folds; matched scoring
protocol. The **answer word is never given to any arm except as one candidate among the distractors** (§8).

- **A. `SYMBOLU_TRIAD_SCORE`** — the candidate: score each candidate word against the three clues using a
  Symbol-U / varṇa / Stage A′ / F-3 structural scoring (e.g. structural distance between candidate and clue
  representations). **Sees only sound-structure-derived features**, never dictionary definitions or LLM
  rationale.
- **B. `SEMANTIC_EMBEDDING_BASELINE`** — ordinary semantic / LLM **embedding** similarity between candidates and
  clues. **The main benchmark**, because the task is semantic; Symbol-U must at least match it to claim unique
  utility.
- **C. `WORD_ID_OR_LEXICAL_UPPER_BOUND`** *(optional)* — a lexical/semantic **lookup** upper bound (e.g. gloss
  or association-norm overlap). **Clearly marked NOT Symbol-U evidence**; a ceiling/denominator only; cannot
  emit a Symbol-U positive.
- **D. `SHUFFLED_VARNA_CONTROL`** — the Symbol-U arm with **shuffled/relabelled** varṇa/operator mapping (same
  candidates, structure destroyed). Tests whether the real structure matters.
- **E. `RANDOM_CANDIDATE_CONTROL`** — random ranking (chance).
- **F. `LENGTH_FREQUENCY_CONTROL`** — rank by length/frequency only.
- **G. `PHONOLOGY_ONLY_BASELINE`** — plain phoneme/phonology features (no Symbol-U F-3), to separate "sound" from
  "Symbol-U structure".

## 8. Leakage rules (strict; a breach → `TRIAD_INVALID_LEAKAGE`)

Strictly forbidden:

- giving the **answer word to the scorer** except as one candidate among the distractors;
- using **dictionary definitions** of candidate words inside the Symbol-U arm;
- using any **LLM explanation** of why the clues match the target inside the Symbol-U arm;
- **post-hoc editing of clues/candidates** after seeing any results;
- **near-synonym clues** too close to the target, unless the item is explicitly labelled an easy case;
- letting the Symbol-U arm see arm identity, the correct answer, or another arm's ranking.

## 9. Scoring metrics

Per arm, over the frozen items:

- **top-1 accuracy**, **top-5 accuracy**;
- **mean reciprocal rank (MRR)**;
- **median rank**;
- **accuracy over random** (accuracy − chance, with chance = 1/candidate-set-size);
- **bootstrap confidence intervals** on every metric;
- **per-arm deltas** vs random / shuffled / phonology / length-frequency / semantic-embedding;
- **multiple-comparison correction** (Holm) across the control-contrast family.

## 10. Terminal labels

- **`TRIAD_SYMBOLU_BEATS_CONTROLS`** — Symbol-U beats **all** of: random, shuffled, phonology-only,
  length/frequency, **and** semantic-embedding, under the pre-registered thresholds.
- **`TRIAD_COLLAPSES_TO_SEMANTIC_EMBEDDING`** — the embedding baseline matches/beats Symbol-U (task is just
  semantic).
- **`TRIAD_COLLAPSES_TO_PHONOLOGY`** — phonology-only matches/beats Symbol-U.
- **`TRIAD_SHUFFLE_EXPLAINS`** — the shuffled-varṇa control matches/beats Symbol-U (structure irrelevant).
- **`TRIAD_LENGTH_FREQUENCY_EXPLAINS`** — length/frequency matches/beats Symbol-U.
- **`TRIAD_NULL_RETURN_BOTTOM`** — no arm beats chance.
- **`TRIAD_INCONCLUSIVE`** — no clean resolution.
- **`TRIAD_INVALID_LEAKAGE`** — a leakage rule (§8) was breached.

**Hard rule:** `TRIAD_SYMBOLU_BEATS_CONTROLS` may be emitted **only** if `SYMBOLU_TRIAD_SCORE` beats **random,
shuffled, phonology, length/frequency, AND semantic-embedding** by the pre-registered margins. Beating some but
not all → the corresponding collapse/explains label. **No `ONTOLOGICAL_SIGNAL` under any label.**

## 11. Thresholds (conservative, pre-registered)

- **Statistically above random** — accuracy CI lower bound > chance (1/set-size), with correction.
- **Meaningful effect over shuffled** — a pre-declared minimum Δ(MRR) over `SHUFFLED_VARNA_CONTROL`
  (e.g. ≥ a fixed margin), not just significant.
- **Non-trivial improvement over phonology-only** — Symbol-U must beat `PHONOLOGY_ONLY_BASELINE` by a
  pre-declared margin (else the "structure" is just sound).
- **Not worse than semantic embedding** to claim unique utility — if `SEMANTIC_EMBEDDING_BASELINE` ties/wins →
  `TRIAD_COLLAPSES_TO_SEMANTIC_EMBEDDING` (the task is semantic, Symbol-U adds nothing).
- All margins, the metric, the candidate-set size, and the primary endpoint are frozen before any data is seen.

## 12. Pilot plan (tiny; no claim)

- **20–50 items**, plumbing + leakage-control validation only.
- **No terminal label / no claim** may be emitted from the pilot; it verifies the harness runs, arms rank the
  same candidates, leakage scans pass, and metrics compute.
- A synthetic positive control (a planted-structure toy) should confirm the harness *can* detect a triad signal
  when one exists — so a real null is informative, not a dead pipeline.

## 13. Full run plan

Before any evidence run: **freeze** the dataset, the candidate sets, the scoring code (all arms), the metrics,
and the thresholds; then an **operator EVIDENCE_FREEZE declaration** — exactly the gated discipline used for
B1.4b′. No run without the freeze declaration. Report the terminal label as-is.

## 14. Relationship to B1.4b′

- **B1.4b′ remains `NULL_RETURN_BOTTOM`.** This document does **not** erase, weaken, or reinterpret it.
- **Different task, different claim:** B1.4b′ = attribute-vector *prediction* from sound-structure; B1.5 =
  target-word *ranking* from a semantic triad. A B1.5 outcome — positive or null — says nothing about the
  B1.4b′ result and vice versa.
- B1.5 is a **separate track**; it does not reuse or modify B1.4b′ artifacts.

## 15. Guardrails

No `ONTOLOGICAL_SIGNAL`. No Sanskrit privilege. No semantic-truth / validated-meaning claim. No rescue of
Track B. No reuse-as-positive of any prior null. Original B1.4b remains blocked. Track B remains blocked.
**Structure, not validated meaning.**

---

## Next gate

Docs-only pre-registration only. Next step (separate approval) would be a **tiny pilot harness**,
synthetic-tested, with the leakage scans and a synthetic positive control — **not** a real run. No dataset is
built and no code is written by this document.

> Three-clue word recovery prereg drafted docs-only. No experiment run. B1.4b′ remains NULL_RETURN_BOTTOM.
> Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
