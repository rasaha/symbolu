# DOCS_ONLY — TRACK B STAGE B0 READINESS PACKAGE — DOES NOT UNBLOCK TRACK B

*Docs-only readiness package. No commit of results, no code change, no model call, no generation, no scoring, no result files, no manifest/approval-gate change. Track B remains **BLOCKED**.*

Provenance: readiness audit `7d0c3552035ef860eae92be304da849757c73553` (recommendation `CREATE_TRACK_B_READINESS_PACKAGE — while Track B remains BLOCKED`).

---

## 1. Scope

- **Stage B0 only** — defines what must be *frozen*, not run.
- **Docs-only.** No execution, no model call, no scoring, no manifest transition.
- Builds **no** artifact that produces results; produces **no** evidence.
- **Track B remains BLOCKED**; `status NOT_READY`; `approval_status NOT_APPROVED`. This package does not change any of these.

## 2. Objective

Define the complete set of **frozen materials** that must exist, be blind-authored, and be content-hashed **before** a future Track B preregistered evaluation could even be *submitted for approval*. B0 is the "freeze the inputs" stage; it neither authorizes nor performs B1 execution.

## 3. Required frozen artifacts (freeze manifest)

Each item below must be authored blind, versioned, and **content-hashed** before B0 is declared frozen. No item may be edited after freeze (see `INVALID_POSTHOC`).

| # | Artifact | What it fixes |
|---|---|---|
| 1 | **Prompt set** | the exact task prompts (§4) |
| 2 | **Key-word list** | the words conditioning is derived from (§4) |
| 3 | **Held-out / development split** | dev/demo words (`mercy/love/anger/peace`, all fixture words) excluded from the eval set |
| 4 | **Model IDs + versions** | exact identifiers + revision hashes (§6) |
| 5 | **Decoding parameters** | temperature, top-p, max tokens (§6) |
| 6 | **Seed policy** | seed set + count; deterministic (§6) |
| 7 | **Arm construction rules A/R/S/C/X/D** | how each conditioning slot is built (§5) |
| 8 | **L1–L5 configuration** | exact commit/config of the pipeline used to build arms |
| 9 | **Vowel-mode policy** | `field_only` default; positional only as declared stratum (§10) |
| 10 | **Judge rubric** | scales, forced-choice format, definitions (§7) |
| 11 | **Leak-scanner criteria** | forbidden-claim patterns (§7) |
| 12 | **Randomization plan** | output-order + sampling seeds (§7) |
| 13 | **Analysis plan** | co-primaries, CIs, correction (§8) |
| 14 | **Failure / kill labels** | predeclared outcome space (§9) |
| 15 | **Approval record template** | who authorizes B1, when, on what hash |
| 16 | **Manifest transition checklist** | the gated steps to change any manifest field (§11) |

A single **B0 freeze manifest** records every artifact's content hash and the freeze timestamp. Absence of any item ⇒ B0 is `NOT_FROZEN`.

## 4. Prompt-set freeze rules

- **Blind-authored** — prompts and key-words authored without reference to which arm will "win."
- **Exclude dev/demo words** — `mercy`, `love`, `anger`, `peace` and all fixture words are held out (development only); no eval item may reuse them.
- **No post-hoc edits** — any change after freeze ⇒ `INVALID_POSTHOC`; a new B0 is required.
- **Content hash required** — the frozen prompt/key-word set is content-addressed; the hash is recorded in the B0 freeze manifest.
- **Semantic-domain balance** — spread across domains (emotion, abstract concept, concrete object, social relation, moral/ethical, sensory).
- **Vowel/consonant structural balance** — balanced word-initial vowels vs. consonants; varied onset/coda so surface-form (C) can be separated from A.
- **Privative `a-/an-` as a separate stratum** — negation-prefix items are a **declared stratum**, never silently mixed with non-prefixed items; analyzed separately.
- **Fixture-based items excluded from natural-run evidence** — any non-cmudict/fixture item is labeled and may not contribute to natural-run conclusions.

## 5. Arm construction freeze

All six arms share an **identical wrapper**; **only the single conditioning slot differs**. Frozen definitions:

| Arm | Conditioning slot (frozen) |
|---|---|
| **A** | real resonance — L2 synthesis of the key word's true-G2P varṇa process |
| **R** | random resonance — fluent process line from bridge values not derived from the key word |
| **S** | scrambled resonance — key-word structure with permuted pole associations |
| **C** | surface-only — onset/vowel-count/final/consonant-positions; no associations |
| **X** | neutral — task only, no symbolic orientation |
| **D** | dictionary-only — core sense + frozen synonym field; not resonance |

Wrapper, slot boundaries, and per-arm generators are frozen and hashed; length parity is measured pre-judging and any imbalance is declared as a confound.

## 6. Model / decode freeze

- **≥ 2 distinct model families** (no single-model conclusion).
- **Exact model IDs** + **revision hashes** where obtainable.
- **Decoding frozen**: temperature, top-p, max tokens — identical across all arms per item.
- **Seed count**: ≥ 2 seeds per item; seeds recorded.
- **No rerun-until-pass**: the frozen run is the run; a second run is a new, separately-reported prereg — never a replacement.

## 7. Judging / blinding freeze

- **Arm labels hidden** from judges; **conditioning source hidden** (except a dedicated steerability sub-study revealing target *direction* only, never arm identity).
- **Output order randomized** (seed recorded); no fixed adjacency of an item's arms.
- **Judge instructions frozen** (rubric, scales, forced-choice); no post-hoc rubric edits.
- **No dictionary answer-key exposed** — D's synonym field must not appear as a judging rubric.
- **Inter-rater agreement reported**; judge pool declared.
- **Attention/calibration checks** included; failed-check judges handled by a pre-declared rule.
- **Leak scanner** run over every output pre-judging for ontology / Sanskrit-privilege / semantic-truth / "therefore means" phrasing (→ `LEAKAGE_FAIL`).

## 8. Analysis freeze

- **Co-primary comparisons:** `A_vs_D`, `A_vs_R`, `A_vs_S`, `A_vs_X`, `A_vs_C` — all declared, all reported.
- **Confidence intervals** on every comparison; threshold = CI-lower-bound > 0 (or equivalent predeclared effect size).
- **Multiple-comparison correction** across the five co-primaries and across task types, stated in advance.
- **All arms reported**; **all failures reported**; per-task-type and per-stratum (incl. the `a-/an-` stratum) breakdown.
- **No cherry-picking**; exploratory analyses labeled as such and separated from the predeclared set.

## 9. Kill labels (predeclared; any ⇒ Track B stays BLOCKED)

`NO_SIGNAL` · `DICTIONARY_DOMINATES` · `RANDOM_OR_SCRAMBLED_MATCHES` · `SURFACE_STRUCTURE_EXPLAINS` · `CORRECTNESS_DEGRADED` · `INVALID_POSTHOC` · `LEAKAGE_FAIL` · `NOT_ROBUST` (effect appears in only one model/seed/task type).

The only non-kill outcome is: **A beats all of D/R/S/C/X on every co-primary, CI-lower-bound > 0, robust across ≥2 models/seeds and task types, no correctness degradation, no leakage** — and even then the claim is bounded to "prompt-conditioning utility under M and T," not meaning.

## 10. Vowel positional polarity policy

- **Default `field_only`** for the primary evaluation.
- **`positional_polarity` is an experimental opt-in**, **not default**.
- If used at all, it must be a **declared stratum or ablation** with its own predeclared comparison — never silently mixed into the primary arms.
- **Fixture examples are not natural evidence** and are excluded from natural-run conclusions.
- **English `EY`→`e` G2P caveat disclosed**: written `a-` prefixes map via cmudict to ARPAbet `EY` (varṇa `e`), not Sanskrit short `a`; no spelling-to-meaning claim is permitted.

## 11. Track B transition gate

**Stage B0 does not unblock Track B.** Track B can move only after, in order:
1. **B0 package frozen** (all §3 artifacts hashed; freeze manifest complete).
2. **Separate approval** — an independent, logged authorization to execute.
3. **B1 execution** — frozen A/R/S/C/X/D generation, no edits.
4. **B2 independent analysis** — predeclared comparisons, CIs, correction.
5. **B3 blocker review** — adjudication against §4 conditions and §9 kill labels.
6. **B4 explicit manifest transition** — a status change is *considered*, requires an independent approval record and the manifest transition checklist; never automatic.

At no point in B0 do `track_b_status`, `status`, or `approval_status` change.

## 12. Required next decision

**`FREEZE_B0_PACKAGE — while Track B remains BLOCKED`.**

Freezing the B0 materials (blind, hashed, held-out) is the disciplined next step; it advances readiness **without** model call, scoring, caveat-weakening, or gate change. It explicitly does **not** unblock Track B and does **not** authorize B1. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome is one of the §9 kill labels — an acceptable result.

## 13. Guardrails

- No ontology validation.
- No Sanskrit privilege.
- No semantic-truth claim.
- No Track G rescue.
- No Track B unblock.
- Track G negative preserved: `1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`.
- Track B remains **BLOCKED**.
- Prior PSE negatives remain valid.
- Track F prior remains `CORRECTNESS_DEGRADED`.
- Frozen manifest remains `NOT_READY`.

---

**Structure, not validated meaning.**
