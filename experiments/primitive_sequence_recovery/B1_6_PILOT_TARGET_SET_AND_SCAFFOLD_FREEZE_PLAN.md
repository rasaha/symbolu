# B1.6 — Pilot Target-Set & Scaffold-Freeze Plan

**Status:** Pilot design/freeze plan (docs-only). Freezes the *requirements* for a later B1.6 pilot — the target
set, the scaffold instantiation, and the randomized-control construction — so a pilot becomes executable later.
**No code, no generation run, no judging, no evidence freeze, no generated outputs.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

Subordinate to: `B1_6_SYMBOLU_GENERATIVE_UTILITY_PREREG.md` (`c1f5028`) and
`B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md` (`17a5ea0`).
Related: `B1_4B_PRIME_SCREENING_OPERATOR_COMMANDS_EXECUTED.md` (`880ad1a`, NULL),
`STAGE_A_PRIME_PHONEME_G2P_OPERATOR_LAYER_DESIGN.md`, `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.

---

## 1. Purpose

This document **freezes the design requirements** for a B1.6 pilot: how the pilot target set is chosen and
stratified, exactly what must be instantiated to turn the prompt-spec placeholders (`{TARGET_TEXT}`,
`{VARNA_SEQUENCE}`, `{VARNA_PROFILE_TABLE}`, `{CSR_STL_FRAME}`) into a runnable pilot, and how the randomized
control is constructed and frozen. **It does not run the pilot**, generate any text, judge anything, or declare
an evidence freeze. It makes a later pilot *executable* while performing none of it.

## 2. Relationship to prior B1.6 docs

Subordinate to **both**:

- `B1_6_SYMBOLU_GENERATIVE_UTILITY_PREREG.md` — the governing claim, arms, terminal labels, and thresholds.
- `B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md` — the frozen prompt templates, output format, judge
  rubric, blind packaging, and leakage/overclaim controls.

Where this document could appear to differ from either, **the prereg governs first, then the prompt/rubric
spec**. This plan adds no new arms, no new terminal labels, and no new claims — only the concrete freeze
procedure for a pilot target set and scaffold instantiation.

## 3. Pilot scope

- **20–30 target items** (frozen before generation).
- **5 active arms** (from the prompt spec §4):
  - `SYMBOLU_SCAFFOLD`
  - `PLAIN_PROMPT_BASELINE`
  - `GENERIC_STRUCTURED_PROMPT_BASELINE`
  - `RANDOMIZED_SYMBOLU_CONTROL`
  - `SEMANTIC_LLM_BASELINE`
- **Optional `SYMBOLIC_SYSTEM_BASELINE` disabled** (placeholder only; not run in the pilot).
- **Generations per item per arm:** **1** for a plumbing pilot; **2–3** only if run-to-run stability is wanted
  later (a separate decision, frozen before that run).
- **No terminal label / no utility claim** may be emitted from the pilot (prereg §15) — it validates plumbing,
  blinding, leakage scrubbing, and rubric discrimination only.

## 4. Target item stratification

Balanced coverage across these strata (roughly equal counts; abstract **and** concrete represented):

- **common concrete words** (everyday objects/actions);
- **abstract concepts** (qualities/ideas);
- **personal / name-like terms**;
- **symbolic / spiritual terms**;
- **brand / product-like terms**;
- **emotionally charged but non-clinical words**.

No single stratum may dominate; per-stratum results are reported separately so any utility is not confined to
one register (prereg §5).

## 5. Pilot target selection rules

- **No post-hoc replacement** of a target after any output is seen.
- **No target chosen because it is expected to favor Symbol-U** (no cherry-picking sonically "evocative" words).
- **Avoid highly obscure words** in the pilot (keep judgeability high).
- **Avoid medical, legal, financial, or other high-stakes advice targets** (no safety-sensitive interpretation).
- **No Sanskrit-only privilege** unless a stratum is *explicitly labelled* as such and analysed separately (no
  implicit Sanskrit advantage).
- **Include both easy and hard interpretive targets** across strata, so the rubric can discriminate.
- Targets must be **license-clear** and have documented provenance (prereg §6).

## 6. TOY_ONLY illustrative target table

**`TOY_ONLY` — illustrative candidates for discussion only. NOT the frozen pilot set. Not scored, not generated
from, not evidence. A real pilot set is frozen only by a separate operator declaration (§13).**

| item_id | target_text | target_type | category | neutral_context | forbidden_hints | notes |
|---|---|---|---|---|---|---|
| toy-01 | river | common_word | common concrete words | "A common noun." | no "intended" reading; no etymology if disallowed | easy |
| toy-02 | bridge | common_word | common concrete words | "A common noun." | none beyond the standard set | easy |
| toy-03 | lantern | common_word | common concrete words | "A common noun." | none | medium |
| toy-04 | balance | abstract_concept | abstract concepts | "An abstract quality." | no evaluative adjectives | medium |
| toy-05 | freedom | abstract_concept | abstract concepts | "An abstract quality." | no "intended" reading | hard |
| toy-06 | patience | abstract_concept | abstract concepts | "An abstract quality." | none | medium |
| toy-07 | threshold | abstract_concept | abstract concepts | "An abstract quality." | none | hard |
| toy-08 | Maya | name | personal/name-like terms | "A personal name." | no biography; no cultural gloss | medium |
| toy-09 | Rowan | name | personal/name-like terms | "A personal name." | no biography | medium |
| toy-10 | Ira | name | personal/name-like terms | "A personal name." | no biography | hard |
| toy-11 | Nova | name | personal/name-like terms | "A personal name." | no "star" gloss forced | easy |
| toy-12 | lotus | symbolic_term | symbolic/spiritual terms | "A symbolic term." | no doctrinal claim; no Sanskrit privilege | medium |
| toy-13 | dawn | symbolic_term | symbolic/spiritual terms | "A symbolic term." | none | easy |
| toy-14 | anchor | symbolic_term | symbolic/spiritual terms | "A symbolic term." | none | medium |
| toy-15 | mandala | symbolic_term | symbolic/spiritual terms | "A symbolic term." | no doctrinal/ontological claim | hard |
| toy-16 | Lumen | brand_product_term | brand/product-like terms | "A product/brand name." | no real-company claim | medium |
| toy-17 | Verba | brand_product_term | brand/product-like terms | "A product/brand name." | no real-company claim | medium |
| toy-18 | Solace | brand_product_term | brand/product-like terms | "A product/brand name." | no real-company claim | medium |
| toy-19 | Kite | brand_product_term | brand/product-like terms | "A product/brand name." | no real-company claim | easy |
| toy-20 | grief | emotionally_charged_word | emotionally charged (non-clinical) | "An emotion word." | non-clinical; no advice | hard |
| toy-21 | wonder | emotionally_charged_word | emotionally charged (non-clinical) | "An emotion word." | non-clinical | medium |
| toy-22 | longing | emotionally_charged_word | emotionally charged (non-clinical) | "An emotion word." | non-clinical | medium |
| toy-23 | courage | emotionally_charged_word | emotionally charged (non-clinical) | "An emotion word." | non-clinical | medium |
| toy-24 | ember | common_word | common concrete words | "A common noun." | none | medium |

*(24 illustrative rows, balanced across the six strata. `TOY_ONLY`: not frozen, not scored, not generated from,
not evidence. The final frozen pilot set — 20–30 items — is fixed only by operator declaration, §13.)*

## 7. Scaffold instantiation requirements

Before any generation, **each** target in the frozen set must have, recorded and hash-frozen:

- **`VARNA_SEQUENCE`** — the phoneme/varṇa decomposition of the normalized target (from the frozen Stage A /
  Stage A′ layer; no hand-editing).
- **`VARNA_PROFILE_TABLE`** — the per-varṇa structural profile/polarity rows for that sequence, drawn verbatim
  from the selected frozen source table (§8).
- **`CSR_STL_FRAME`** — the declared CSR/STL interpretive dimensions used as scaffold axes, from the frozen
  definition.
- **decomposition confidence / unsupported-segment note** — any grapheme/phoneme the frozen layer cannot
  decompose is flagged (not silently dropped); items with unsupported segments are excluded or labelled, never
  patched by hand.
- **normalized target text** — the exact normalized form fed to the decomposition (recorded alongside the raw
  `target_text`).
- **version/hash of the scaffold source tables** — the commit/hash of the Stage A / Stage A′ code and the
  profile/CSR-STL table used, so the instantiation is reproducible and auditable.

**No `{...}` placeholder may remain** at pilot time; an un-instantiated placeholder is a blocker (§14,
`..._BLOCKED_SCAFFOLD_UNINSTANTIATED`).

## 8. Allowed scaffold sources

- The Symbol-U scaffold content (`VARNA_SEQUENCE`, `VARNA_PROFILE_TABLE`, `CSR_STL_FRAME`) may come **only** from
  **frozen/versioned project sources** — the existing frozen Stage A / Stage A′ decomposition and the frozen
  profile/polarity and CSR/STL tables. **No external, ad-hoc, or newly-authored varṇa tables.**
- **If multiple candidate lexicons/tables exist, the selected one is documented** (name + hash) in the freeze
  record, and the choice is fixed before generation.
- **Do NOT invent or "improve" varṇa profiles/meanings during target preparation.** The profiles are structural
  propensities as already frozen; preparation copies them, it does not edit them.
- **No post-hoc editing** of scaffold content after any output is read.
- These sources are **not modified** by this plan (Stage A, Stage A′, scorer, B1.3, B1.4a, B1.4b, and lexicons
  are all untouched).

## 9. Randomized Symbol-U control construction

- **Same target sequence length** where possible (same number of scaffold rows), so length is not a giveaway.
- **Shuffled / relabelled varṇa profiles** — the sequence→profile assignment (and/or the profile rows) is
  permuted so the *specific* varṇa content is destroyed while the template, axes, and length are preserved.
- **Deterministic random seed** — the permutation is generated from a single frozen seed recorded in the freeze
  package (reproducible; no `Math.random`-style non-determinism).
- **No reveal** — the generator is given the randomized scaffold *as if it were a genuine scaffold* (no hint of
  randomization); the judge sees only the blinded output and cannot tell it was randomized.
- **Frozen before generation** — the seed, the permutation, and the resulting randomized scaffolds are fixed and
  hash-frozen **before** any generation runs (else `..._BLOCKED_RANDOMIZED_CONTROL_UNFROZEN`).

## 10. Plain and generic baseline parity

Confirmed for `PLAIN_PROMPT_BASELINE` and `GENERIC_STRUCTURED_PROMPT_BASELINE` (and enforced across all arms):

- **same output format** (Title / 120–180-word Interpretation / 2 bullets / 1-sentence Caution);
- **same token budget** / max tokens;
- **same target and `neutral_context`**;
- **no extra clues** to the Symbol-U arm (no target gloss, no "intended" reading);
- **no arm gets a privileged explanation length** — the 120–180-word bound is identical for every arm; the
  Symbol-U arm's scaffold lives in the *prompt*, not in extra output room.

## 11. Semantic LLM baseline

`SEMANTIC_LLM_BASELINE` may use:

- **ordinary conceptual / semantic knowledge** of the target;
- **broad cultural associations**;
- **optional etymology** — only when the item permits it *and* the model already knows it (no special research,
  no fabrication; unsure → say so);

and may **not** use any Symbol-U scaffold, varṇa sequence, profile table, or CSR/STL frame. Its purpose is to
set the bar: whether the Symbol-U scaffold adds anything **beyond** a strong ordinary semantic interpretation.
If it ties/beats Symbol-U → the prereg's `GENUTILITY_LLM_BASELINE_WINS`.

## 12. Blind packaging plan

- **Opaque arm IDs** — per-run codes with no arm name and no inferable mapping.
- **Randomized output order per item** — fixed by the frozen seed; position leaks nothing.
- **Target visible to the judge** — required so judges can rate specificity/non-genericity (prompt spec §13);
  identical across arms, leaks no arm identity.
- **No arm labels in output**; **no "Symbol-U" / "varṇa" / system names in the final text** (scrubbed; residual
  → void item).
- **Separate hidden metadata file** — the arm↔code map, seeds, scaffold hashes, and normalized-text records are
  kept **out of the judge package** and revealed only at analysis time.

## 13. Pilot evidence-freeze checklist

Before running the pilot, **all** must be true (and declared by the operator):

- [ ] **final target set frozen** (20–30 items, stratified, hashed);
- [ ] **scaffold values populated** for every target (§7; no residual placeholders);
- [ ] **randomized controls generated and frozen** (§9; seed + permutation recorded);
- [ ] **prompt templates frozen** (from the prompt/rubric spec, verbatim);
- [ ] **model / temperature / max-token settings frozen** (identical across arms);
- [ ] **random seeds frozen** (order randomization + control permutation);
- [ ] **judge rubric frozen** (1–7 dimensions + penalties, composite definition);
- [ ] **output packaging plan frozen** (opaque IDs, hidden metadata);
- [ ] **evidence-freeze declaration created by the operator** — the same gated discipline as B1.4b′.

**No generation runs until every box is checked and the operator declares the freeze.** This document checks
none of them (it is the plan, not the freeze).

## 14. Pilot run-blocked labels

- **`B1_6_PILOT_TARGET_SCAFFOLD_PLAN_READY`** — this plan is complete and internally consistent (the state of
  this document); a pilot still requires the §13 freeze before running.
- **`B1_6_PILOT_BLOCKED_TARGET_SET_UNFROZEN`** — no operator-declared frozen target set yet.
- **`B1_6_PILOT_BLOCKED_SCAFFOLD_UNINSTANTIATED`** — one or more `{...}` scaffold placeholders not populated.
- **`B1_6_PILOT_BLOCKED_RANDOMIZED_CONTROL_UNFROZEN`** — the randomized-control seed/permutation not frozen.
- **`B1_6_PILOT_BLOCKED_EVIDENCE_FREEZE_MISSING`** — the operator evidence-freeze declaration is absent.
- **`B1_6_PILOT_INVALID_LEAKAGE`** — a leakage/parity breach found (arm-identifying giveaway, unequal budget,
  system-name in output, post-hoc edit).

**Assigned label for this document: `B1_6_PILOT_TARGET_SCAFFOLD_PLAN_READY`** — plan complete; the actual pilot
remains `..._BLOCKED_TARGET_SET_UNFROZEN` / `..._BLOCKED_SCAFFOLD_UNINSTANTIATED` /
`..._BLOCKED_RANDOMIZED_CONTROL_UNFROZEN` / `..._BLOCKED_EVIDENCE_FREEZE_MISSING` until §13 is satisfied.

## 15. What this document does NOT do

- **No generation** — no text is produced by any arm.
- **No judging** — no output is rated.
- **No result** — no scores, no terminal label, no utility number.
- **No evidence freeze** — no freeze is declared; §13 is a checklist for a *future* operator step.
- **No claim of utility** — nothing here says Symbol-U helps.
- **No ontology or semantic-truth claim** — none, under any framing.

## 16. Relationship to prior negative results

- **B1.4b′ remains `NULL_RETURN_BOTTOM`.** This document does **not** erase, weaken, or reinterpret it.
- B1.4b′ was a **blind attribute-prediction** test; B1.6 tests a **different claim** — the **generative utility
  of a scaffold** under blinded rating. A B1.6 pilot outcome would say nothing about B1.4b′ and vice versa.

## 17. Guardrails

No `ONTOLOGICAL_SIGNAL`. No `L1_L2_L3_ATTRIBUTE_SIGNAL`. No Sanskrit privilege. No semantic-truth /
validated-meaning claim. No claim that sound objectively encodes meaning. No rescue of B1.4b′. No
reuse-as-positive of any prior null. Original B1.4b remains blocked. Track B remains blocked. **Structure, not
validated meaning.**

## 18. Validation checklist (docs-only)

- [x] **File is docs-only** — Markdown plan; no code.
- [x] **No target set frozen** unless explicitly marked — the §6 table is `TOY_ONLY`, not frozen; a real freeze
  needs a separate operator declaration (§13).
- [x] **No generated outputs** — none produced.
- [x] **No evidence freeze** — none declared.
- [x] **No prior artifacts modified** — B1.6 prereg/prompt-spec, B1.4b′ artifacts, Stage A, Stage A′, scorer,
  B1.3, B1.4a, B1.4b, and lexicons all untouched.
- [x] **No code modified** — none.

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_6_PILOT_TARGET_SET_AND_SCAFFOLD_FREEZE_PLAN.md`
- **Commit hash:** (recorded on commit below)
- **Readiness label:** `B1_6_PILOT_TARGET_SCAFFOLD_PLAN_READY` (a real pilot remains blocked until the §13
  freeze — target set, scaffold instantiation, randomized control, and operator evidence-freeze declaration —
  is completed).
- **Target/scaffold freeze-plan summary:** a 20–30-item pilot across six balanced strata (common concrete,
  abstract, name-like, symbolic/spiritual, brand/product, emotionally-charged non-clinical), selected under
  no-cherry-pick / no-Sanskrit-privilege / no-high-stakes rules; five active arms (Symbol-U scaffold, plain,
  generic-structured, randomized-Symbol-U, semantic-LLM), optional symbolic-system baseline disabled; per-target
  scaffold instantiation of `VARNA_SEQUENCE` / `VARNA_PROFILE_TABLE` / `CSR_STL_FRAME` drawn **only** from frozen
  versioned project sources (no invented profiles), with source hashes recorded; a deterministic, pre-frozen
  randomized control; strict baseline parity and blind packaging with a hidden metadata file; and a nine-item
  pre-run evidence-freeze checklist that gates any generation.
- **No generation run was performed.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**
- **This is not a semantic-decoding or ontology claim** — it plans a *generative-utility-of-a-scaffold* pilot
  only; no validated meaning, no Sanskrit privilege, no `ONTOLOGICAL_SIGNAL`.

> B1.6 pilot target/scaffold freeze plan drafted docs-only. No generation run. No evidence freeze. B1.4b′
> remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated
> meaning.
