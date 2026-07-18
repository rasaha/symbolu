# DOCS_ONLY — TRACK B B0 FAILURE-MODE PREMORTEM — DRAFT ONLY — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only premortem. No commit of results, no code change, no model call, no generation, no scoring, no result files, no hashes computed. **Premortem only; nothing is frozen.** Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: B0 artifacts draft `c824a7a`; G2P audit `16266b4`; model/decode/seed policy `4c8122a`; arm-construction lock `916e00a`; D-arm dictionary table `bcb604e`; judge/randomization/leak lock `fae078d`; analysis-plan lock `031f609`; Track G negative `1fe5562`.

## 1. Scope and non-execution boundary

- **Docs-only premortem** — anticipates failure modes and maps each to a pre-freeze control / audit / kill label.
- **No model call · no generation · no scoring · no result files.**
- **No hash computation · no B0 freeze · no B1 approval · no Track B unblock.**
- `DRAFT_NOT_FROZEN`; freeze discipline (`INVALID_POSTHOC`) applies only after a future signed freeze.

## 2. Premortem principle

- Failures should be **anticipated before execution**, when controls can still be strengthened.
- **Controls may be strengthened before freeze** (e.g., make R/S/C/D *harder* for A).
- **A may NOT be tuned against observed model outputs** — no fitting A to win.
- **D/R/S/C/X may NOT be weakened** — controls stay strong.
- **After freeze, failures are reported, not patched** (any patch ⇒ `INVALID_POSTHOC`).

The premortem is adversarial toward A: its purpose is to make each null/negative outcome *easier* to detect, never to rescue A.

## 3. Failure-mode table

| Failure mode | Why plausible | Pre-freeze mitigation | Post-freeze allowed action | Kill label |
|---|---|---|---|---|
| **D dominates** | D is near the answer key; dictionary sense is directly on-topic. | Make D a **strong, fair** baseline (`bcb604e`); measure length parity; do **not** weaken D. | Report `A_vs_D` as-is. | `DICTIONARY_DOMINATES` |
| **R/S match A** | Random/scrambled process text reads fluent and evocative (any-injection confound, observed in the no-model demo). | Keep R/S **fluent and format-matched**; do not make them awkward; freeze R/S seeds. | Report `A_vs_R` / `A_vs_S` as-is. | `RANDOM_OR_SCRAMBLED_MATCHES` |
| **Surface explains** | Onset/coda/vowel-count alone may steer tone/rhythm. | Make C a **serious, format-matched** surface control; freeze C generator. | Report `A_vs_C` as-is. | `SURFACE_STRUCTURE_EXPLAINS` |
| **Correctness degrades** | A may add poetic style while reducing factual accuracy (Track F prior). | T4 explanation stratum + faithfulness/correctness rubric with hard flag. | Report degradation; correctness overrides style. | `CORRECTNESS_DEGRADED` |
| **Leakage** | Outputs/conditioning may surface ontology/Sanskrit/semantic-proof framing, or arm labels reach judges. | Leak scanner runs **before** judging; blinding rules (`fae078d`). | Report leak hits; quarantine. | `LEAKAGE_FAIL` |
| **Not robust** | Effect may exist for one model/seed/task only, or rest on low judge agreement. | ≥2 model families, ≥2 seeds, >1 task type; inter-rater agreement reported. | Report per-cell breakdown. | `NOT_ROBUST` |
| **Post-hoc contamination** | Temptation to edit/rerun/substitute after seeing unfavorable results. | Freeze everything + hash; declare no-rerun rule up front. | None — report the void. | `INVALID_POSTHOC` |
| **No signal** | A may simply fail, or beat only X. | Require A to beat **all** of D/R/S/C/X under corrected co-primaries. | Report null. | `NO_SIGNAL` |

## 4. D-dominates premortem

- **D is expected to be strong** — it is close to the answer key, and `A_vs_D` is the hardest co-primary.
- **A losing to D is a valid, expected failure**, not a bug to fix.
- **Do not weaken D.** The only permitted adjustment is **length parity** (so arms aren't guessable by length) — **never** semantic weakening, truncation of D's sense, or thinning its synonym field.
- Trigger: `DICTIONARY_DOMINATES` (D ≥ A, or A fails to beat D under corrected `A_vs_D`).

## 5. R/S confound premortem

- **Random/scrambled symbolic text may sound fluent** and even land on-theme by chance (observed).
- **R/S must remain strong controls** — same template, same fluency, frozen seeds.
- **Do not make R/S awkward, ungrammatical, or shorter** to help A.
- If R/S match A, the **correct result is `RANDOM_OR_SCRAMBLED_MATCHES`** — reported, not rescued.

## 6. Surface-only confound premortem

- **Phoneme/onset/coda features may be enough** to steer style/rhythm without any varṇa semantics.
- **C must be serious and format-matched** — a genuine surface control, not a strawman.
- If C matches A → `SURFACE_STRUCTURE_EXPLAINS` (the phonetic surface, not the process, carries any effect).

## 7. Correctness-degradation premortem

- **A may improve poetic style but reduce factual accuracy.**
- **Explanation tasks (T4) must detect this** via the faithfulness/correctness dimension with a hard flag.
- **Correctness loss overrides style preference** — a style win that costs correctness is not a utility win.
- Trigger: `CORRECTNESS_DEGRADED` (directly guards the Track F prior).

## 8. Leakage premortem

- **Outputs or conditioning may leak** ontology / Sanskrit / semantic-proof framing; or arm/source labels may reach judges.
- **The leak scanner must run before judging** over every output and conditioning slot (`fae078d` §8).
- **Isolated hits** are flagged/quarantined; **systematic leakage triggers `LEAKAGE_FAIL`**.

## 9. Robustness premortem

- **A result confined to one model/seed/task is not enough.**
- Require **≥ 2 model families, ≥ 2 seeds, > 1 task type**.
- **Low judge agreement** may also trigger a caution label or `NOT_ROBUST`.
- Per-model / per-seed / per-task and per-stratum breakdowns are reported (the privative stratum cannot rescue a failed primary).

## 10. Post-hoc contamination premortem

After freeze, **none** of the following is permitted (each ⇒ `INVALID_POSTHOC`):
- post-freeze edits to any frozen artifact;
- rerun-until-pass;
- word substitution after seeing results;
- bridge/lexicon rewrite after seeing failures;
- prompt/wrapper tweaking after outputs;
- decode/seed changes after outputs;
- silent exclusion of unfavorable items/judges.

The only permitted rerun is the documented pre-output infrastructure-failure case (`4c8122a` §7), logged.

## 11. What can be changed before freeze

- Strengthening any control (make R/S more fluent, C more serious, D fairer within its true sense).
- Length-parity adjustments across arms.
- Finalizing all `TBD_AT_FREEZE` fields (models, decode, seeds, tie/both-bad, CI method, correction, clustering, robustness thresholds, judge count, attention/tie rules).
- Adding leak-scanner terms; refining blinding and randomization config.
- Adding/removing eval words **only** on structural grounds (G2P resolvability, balance) — **not** based on any A outcome (no outputs exist yet).

## 12. What cannot be changed after freeze

- Prompt set, key-word list, held-out split.
- Model IDs/revisions, decode params, seed list.
- Wrapper, arm generators, R/S seeds, D-anchor table.
- Judge rubric, blinding rules, leak-scanner terms, randomization seed/config.
- Analysis plan (co-primaries, CI method, correction, clustering, thresholds, tie/missing-data rules), kill-label triggers, reporting template.

Any change to the above after freeze voids the run (`INVALID_POSTHOC`); a new B0 with new hashes is required.

## 13. Current status

- `FAILURE_MODE_PREMORTEM_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 14. Recommendation

**`PERSIST_FAILURE_MODE_PREMORTEM_DRAFT`.**

The premortem maps every anticipated failure to a pre-freeze control and a kill label, strengthens (never weakens) the controls, and forbids tuning A — but it is a planning document, not a freeze, and it references artifacts that remain `DRAFT_NOT_FROZEN` with open `TBD_AT_FREEZE` fields and no hashes. Therefore **do not `FREEZE_B0_NOW`** and **do not `REQUEST_B1_APPROVAL`** (both gated behind a completed, signed B0 freeze plus a separate independent approval). Recommended path: persist docs-only. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome remains a §3 kill label — which the premortem is explicitly designed to detect, not avoid.

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

**The premortem detects likely failure modes; it does not tune A, weaken controls, or rescue failures after execution.**

**Structure, not validated meaning.**
