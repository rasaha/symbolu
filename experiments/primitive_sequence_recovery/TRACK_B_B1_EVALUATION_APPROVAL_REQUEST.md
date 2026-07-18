# DOCS_ONLY — H2 B1 REAL-LLM EVALUATION APPROVAL REQUEST — NOT APPROVED — DOES NOT UNBLOCK TRACK B

*Docs-only approval-request document. No commit of results, no code change, no model call, no generation, no scoring, no result files, no manifest/approval-gate change. Track B remains **BLOCKED**; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: readiness audit `7d0c355`; Stage B0 readiness package `68e04cd`; B0 freeze manifest template `6fce2e9`; research-validation wrap-up `5014173`; Track G negative `1fe5562`.

**Framing (binding):** this requests approval for an **H2 generation-conditioning *utility* evaluation** only — *not* semantic proof, *not* ontology, *not* Sanskrit privilege, *not* a Track G rescue, and **not, by itself, a Track B unblock**. Null / informed-negative prior. Approving B1 authorizes a single frozen run; it does **not** move any manifest field (that is B4).

---

## 1. Evaluation question

Under a **frozen** model/task/prompt set, does **real symbolic-resonance conditioning (A)** improve blinded human preference / quality / steerability compared with **dictionary-only (D)**, **random (R)**, **scrambled (S)**, **surface-only (C)**, and **neutral (X)** — all sharing an identical wrapper and differing only in the single conditioning slot? The claim under test is bounded to "prompt-conditioning utility of a specific pipeline under specific models and tasks," never to meaning.

## 2. Required B0 freeze artifacts (all must be hashed before B1)

B1 cannot proceed until the B0 freeze manifest (`6fce2e9` template) is **fully populated with real content hashes** and signed. Required: prompt set · key-word list · held-out/dev split · model IDs+versions · decoding params · seed policy · arm-construction rules (A/R/S/C/X/D) · L1–L5 pipeline commit SHA · vowel-mode policy · judge rubric · leak-scanner criteria · randomization plan · analysis plan · kill-label set · approval-record · manifest-transition checklist. Any missing hash ⇒ B0 `NOT_FROZEN` ⇒ **B1 request is invalid**.

## 3. Proposed model set

- **≥ 2 distinct model families** (no single-model conclusion). Candidate example: one open-weight instruct model + one frontier instruct model — **exact IDs and revision hashes recorded at freeze**.
- Model versions **frozen**; no swaps after freeze (else `INVALID_POSTHOC`).

## 4. Prompt / task set requirements

- **Blind-authored**, content-hashed, frozen before any run.
- **Dev/demo words held out** (`mercy/love/anger/peace` + all fixture words excluded from the eval set).
- **Task types** (each multiply represented): reflective paragraph · gentle message · metaphor · explanation (faithfulness-sensitive) · emotionally-aligned response · creative rewrite.
- **Semantic-domain balance** and **vowel/consonant onset/coda balance**.
- **Privative `a-/an-` items as a declared stratum** (analyzed separately; `EY`→`e` G2P caveat attached).
- **Fixture-based items excluded** from natural-run conclusions.

## 5. Arm construction A/R/S/C/X/D

Identical wrapper; **only the conditioning slot varies**:

| Arm | Conditioning slot |
|---|---|
| **A** | real resonance — L2 synthesis of the key word's true-G2P varṇa process |
| **R** | random resonance — fluent process line from bridge values not derived from the key word |
| **S** | scrambled resonance — key-word structure with permuted pole associations |
| **C** | surface-only — onset / vowel-count / final / consonant-positions; no associations |
| **X** | neutral — task only |
| **D** | dictionary-only — core sense + frozen synonym field; not resonance |

Wrapper + per-arm generators frozen and hashed; length parity measured pre-judging (imbalance declared as a confound).

## 6. Decoding parameters

Frozen and **identical across all arms per item**: temperature, top-p, max tokens. Seed policy frozen; **≥ 2 seeds per item**. **No rerun-until-pass** — the frozen run is the run.

## 7. Randomization and blinding

- Judges blind to arm labels and conditioning source (a steerability sub-study may reveal target *direction* only, never arm identity).
- Output order randomized (seed recorded); no fixed arm adjacency per item.
- **Leak scanner** over every output pre-judging for ontology / Sanskrit-privilege / semantic-truth / "therefore means" phrasing (→ `LEAKAGE_FAIL`).
- **No dictionary answer-key** exposed to judges.

## 8. Output storage rules

- One output per (prompt × arm × model × seed); **no best-of-N**, no cherry-pick.
- Outputs anonymized, arm-delabeled, stored against the frozen manifest hash.
- Raw outputs retained for audit; **no scoring fields written into raw output files**.
- Storage occurs **only after B1 approval**; nothing is written in this draft.

## 9. Human judging plan

- Predeclared rubric + forced-choice and/or graded scales, frozen.
- Judge pool declared; **inter-rater agreement reported**; **attention/calibration checks** included with a pre-declared handling rule.
- Primary metric: **blinded human preference**. Secondary (all predeclared, all reported): relevance, coherence, emotional alignment, novelty, controllability/steerability, faithfulness/correctness, unsupported-claim leak rate.

## 10. Analysis plan

- **Co-primary comparisons:** `A_vs_D`, `A_vs_R`, `A_vs_S`, `A_vs_X`, `A_vs_C` — all declared, all reported.
- **Confidence intervals** on every comparison; **multiple-comparison correction** across the five co-primaries and task types, stated in advance.
- **All arms and all failures reported**; per-task-type and per-stratum (incl. `a-/an-`) breakdown; robustness across model/seed/task type.
- Exploratory analyses labeled and separated; **no cherry-picking, no rerun-until-pass**.

## 11. Success criteria

For any positive result, **A must beat D, R, S, C, and X** — not merely X:
- `A_vs_D` > 0, `A_vs_R` > 0, `A_vs_S` > 0, `A_vs_X` > 0, `A_vs_C` > 0, each by **CI-lower-bound > 0** (or the predeclared effect-size threshold, multiple-comparison corrected);
- **robust** across ≥2 models, ≥2 seeds, and >1 task type;
- **no correctness/faithfulness degradation**;
- **no leakage**.
Beating only X ⇒ not success (maps to `NO_SIGNAL`/`DICTIONARY_DOMINATES`). The single non-kill label is `LIMITED_GENERATION_UTILITY`, still bounded to "utility under M and T."

## 12. Kill criteria (any ⇒ Track B stays BLOCKED)

`NO_SIGNAL` · `DICTIONARY_DOMINATES` (D ≥ A) · `RANDOM_OR_SCRAMBLED_MATCHES` (R or S ≈ A) · `SURFACE_STRUCTURE_EXPLAINS` (C ≈ A) · `CORRECTNESS_DEGRADED` · `LEAKAGE_FAIL` · `NOT_ROBUST` (effect in only one model/seed/task type) · `INVALID_POSTHOC` (any post-freeze edit).

## 13. What the run can prove (at most)

- A **preference/quality/steerability difference** between arm A and the controls, **under the frozen models and task set** — i.e., **architecture-bound prompt-conditioning utility**. Nothing broader; a positive result licenses one sentence: "under model M and task set T, conditioning slot A was preferred over controls."

## 14. What the run cannot prove

- That varṇas/phonemes encode meaning; semantic truth; ontology; Sanskrit privilege (natural runs key off English `EY`→`e`); Track B support in general; any AGI/universal claim; and it does **not** by itself unblock Track B (that requires B2/B3/B4 + independent approval + manifest-transition protocol).

## 15. Approval-gate checklist (all must be TRUE before B1 executes)

- [ ] B0 freeze manifest **fully populated with real hashes** and signed (`frozen: true`).
- [ ] Prompt/key-word set frozen, hashed, dev/demo held out.
- [ ] ≥2 model families with IDs+revision hashes frozen.
- [ ] Decoding params + seed policy frozen (≥2 seeds/item).
- [ ] Arm generators + wrapper frozen; single-slot-varies attested.
- [ ] Judge rubric, leak-scanner, randomization plan, analysis plan frozen.
- [ ] Kill labels predeclared.
- [ ] **Separate, independent, logged approval** recorded against the exact frozen manifest hash.
- [ ] Manifest-transition checklist acknowledged (transition is B4, not B1).

Until every box is checked, `approval_status` stays `NOT_APPROVED` and no model runs.

## 16. Final recommendation

**`FREEZE_B0_FIRST`** — then, and only then, **`REQUEST_B1_APPROVAL_AFTER_B0_FREEZE`**.

B0 is **not yet frozen** (freeze manifest is a template with `<UNFROZEN>` placeholders). Per the approval gate, **immediate model execution is not recommended** and is not authorized. The disciplined path is: author + hash the B0 artifacts → sign the freeze manifest → submit the B1 approval request against that frozen hash → obtain separate independent approval → only then run. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable outcome remains one of the §12 kill labels — an acceptable result.

## Guardrails

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
- Approval status remains `NOT_APPROVED`.

---

**Structure, not validated meaning.**
