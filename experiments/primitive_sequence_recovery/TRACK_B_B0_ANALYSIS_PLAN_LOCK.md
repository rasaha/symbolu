# DOCS_ONLY — TRACK B B0 ANALYSIS PLAN LOCK — DRAFT ONLY — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only analysis-plan draft. No commit of results, no code change, no model call, no generation, no scoring, no result files, no hashes computed. **All specifics are draft; nothing is frozen.** Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: B0 artifacts draft `c824a7a`; G2P audit `16266b4`; model/decode/seed policy `4c8122a`; arm-construction lock `916e00a`; D-arm dictionary table `bcb604e`; judge/randomization/leak lock `fae078d`; B1 approval request `7569210`; Track G negative `1fe5562`.

## 1. Scope and non-execution boundary

- **Docs-only analysis-plan draft** — defines how judgments will be analyzed at a future run; it does not analyze anything.
- **No model call · no generation · no scoring · no result files.**
- **No hash computation · no B0 freeze · no B1 approval · no Track B unblock.**
- `DRAFT_NOT_FROZEN`; freeze discipline (`INVALID_POSTHOC`) applies only after a future signed freeze.

## 2. Analysis goal

- Evaluate **generation-conditioning utility only** — *not* semantic truth, *not* ontology, *not* Sanskrit privilege, *not* a Track G rescue, and **not, by itself, a Track B unblock**.
- **Central question:** does **A beat D/R/S/C/X** under the frozen setup?

## 3. Co-primary comparisons (locked set)

`A_vs_D` · `A_vs_R` · `A_vs_S` · `A_vs_X` · `A_vs_C`.
- **All five must be reported**; **no comparison may be dropped**.
- **A positive result requires A to beat all five.**
- **Beating only X is not success** (X is the weakest control).
- **D is the strongest baseline** (near answer key) and is treated as a **co-primary**, not a footnote.

## 4. Primary outcome definition

Primary outcome = **blinded pairwise preference** from human judges (`fae078d` §5).

Draft scoring rule:
- A win = **1**
- control win = **0**
- tie / no preference = **0.5** *(unless changed before freeze)*
- both bad = **0.5 or excluded** *(must be finalized before freeze)*

**Tie / both-bad handling is `TBD_AT_FREEZE`** until finalized.

## 5. Confidence-interval rule

- Estimate, per co-primary, the **pairwise win rate** (or mean preference-difference score).
- **Report a CI for each** co-primary.
- Positive co-primary requires **CI lower bound > 0.5** (win rate) **or > 0** (difference score).
- **Exact CI method `TBD_AT_FREEZE`.** Candidates: **bootstrap CI over item-level clustered units** (primary candidate); **mixed-effects logistic model** (secondary); **paired bootstrap by item/model/seed/task**.

## 6. Multiple-comparison correction

- Correction applied **across the five co-primaries**.
- Candidate method: **Holm-Bonferroni** or **Benjamini-Hochberg**; **exact method `TBD_AT_FREEZE`**.
- Success requires the **corrected** significance / corrected CI threshold to hold.
- **Exploratory analyses separated and labeled** (never mixed into the corrected co-primary set).

## 7. Unit of analysis (draft hierarchy)

- **item** = key word × task (T1–T6)
- **generated output** = item × arm × model × seed
- **judgment** = pairwise comparison × judge
- **Clustering by item** (and possibly judge); repeated judgments are **not** treated as independent without adjustment.
- Exact clustering/mixed-effects specification `TBD_AT_FREEZE`.

## 8. Robustness requirements

A positive result requires **all** of:
- A beats **all** controls in aggregate (§3);
- effect **not confined to one model**;
- effect **not confined to one seed**;
- effect **not confined to one task type**;
- **no correctness degradation** (T4 hard flag);
- **no systematic leakage**;
- **no low-agreement judge collapse**.

If the effect is driven by **only one** model/seed/task, or rests on low inter-rater agreement → `NOT_ROBUST`.

## 9. Per-stratum reporting

Report **separately**:
- **primary 20-word natural set**;
- **privative `a-/an-` stratum**;
- **fixture-ablation** (if ever run).

Rules:
- **The privative stratum cannot rescue a failed primary result.**
- **Fixture-ablation cannot support natural-run claims.**
- The **`EY`→`e` caveat is repeated** for the privative stratum (written `a-` → ARPAbet `EY` → varṇa `e` for `amoral`/`asymmetry`; not Sanskrit `a`; no spelling-to-meaning claim).

## 10. Secondary outcomes

relevance · coherence · emotional alignment · novelty · controllability/steerability · faithfulness/correctness · unsupported-claim risk · overall quality.
- **Secondary outcomes cannot override failed co-primaries.**
- **Secondary wins are exploratory** unless predeclared otherwise.

## 11. Kill-label application (triggers)

| Label | Trigger condition |
|---|---|
| `DICTIONARY_DOMINATES` | D ≥ A, or A fails to beat D on `A_vs_D` (corrected). |
| `RANDOM_OR_SCRAMBLED_MATCHES` | R or S matches/beats A (`A_vs_R` or `A_vs_S` not cleared). |
| `SURFACE_STRUCTURE_EXPLAINS` | C matches/beats A (`A_vs_C` not cleared). |
| `NO_SIGNAL` | A fails broadly, or beats **only** X. |
| `CORRECTNESS_DEGRADED` | A improves style but worsens correctness (T4 hard flag). |
| `LEAKAGE_FAIL` | systematic leakage, or arm/source labels exposed to judges. |
| `INVALID_POSTHOC` | any post-freeze edit, reorder, or rerun-until-pass. |
| `NOT_ROBUST` | result depends on one model/seed/task, or low judge agreement. |

**Any one kill label ⇒ Track B stays BLOCKED.**

## 12. Success label (only non-kill positive)

`LIMITED_GENERATION_UTILITY`.
Trigger — **all** of:
- A beats D/R/S/C/X under the **corrected co-primary** criteria;
- robust across **≥ 2 model families**;
- robust across **seeds** and **> 1 task type**;
- **no correctness degradation**;
- **no leakage**;
- **no `INVALID_POSTHOC` event**.

Even this label means only: **"Under frozen models M and task set T, A showed bounded prompt-conditioning utility."** It does **not** prove semantic truth, ontology, Sanskrit privilege, or unblock Track B by itself.

## 13. Missing-data and failure handling

- Failed model/API calls handled **only** per the infrastructure-failure rule (`4c8122a` §7); **no post-output reruns**.
- Missing judgments handled by a **predeclared rule** (`TBD_AT_FREEZE`).
- **Judge exclusions only** by the frozen attention-check rule (`fae078d` §10); no discretionary removal.
- **All missingness reported.**

## 14. Reporting requirements

Report **all**: arms · co-primaries · secondary metrics · failures · excluded outputs/judgments · leak hits · post-hoc/exploratory analyses (labeled as such). No cherry-picking; no silent exclusions.

## 15. Freeze requirements (finalize before B0 freeze)

- [ ] Tie handling.
- [ ] Both-bad handling.
- [ ] CI method.
- [ ] Multiple-comparison correction method.
- [ ] Clustering / unit-of-analysis method.
- [ ] Robustness thresholds.
- [ ] Missing-data handling.
- [ ] Judge-exclusion rule.
- [ ] Kill-label trigger wording.
- [ ] Reporting template.
- [ ] Analysis script/config hash (if any).

Until every box is final and hashed into the B0 manifest, this document stays `DRAFT_NOT_FROZEN`.

## 16. Current status

- `ANALYSIS_PLAN_LOCK_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 17. Recommendation

**`PERSIST_ANALYSIS_PLAN_LOCK_DRAFT`.**

The analysis plan is coherent and coverage-complete as a draft, but several methodological choices remain `TBD_AT_FREEZE` (tie/both-bad handling, CI method, correction method, clustering specification, robustness thresholds, missing-data rule), no content is hashed, and no artifact is finalized into a standalone frozen file. Therefore **do not `FREEZE_B0_NOW`** (multiple §15 boxes open) and **do not `REQUEST_B1_APPROVAL`** (gated behind a completed, signed B0 freeze). `REVISE_ANALYSIS_PLAN_BEFORE_FREEZE` is the fallback if review finds a methodological gap. Recommended path: persist docs-only; finalizing the TBD methods + hashing remain a separate, explicitly-approved step. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome remains a §11 kill label.

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
