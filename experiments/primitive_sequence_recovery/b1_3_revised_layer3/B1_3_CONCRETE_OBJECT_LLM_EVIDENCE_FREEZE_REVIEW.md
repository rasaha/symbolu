# B1.3 Concrete-Object LLM Judged-Modulation — EVIDENCE_FREEZE Readiness Review

## 1. Scope and status

Freeze-review only. **No evidence judge run · no scoring · no signal claim · EVIDENCE_FREEZE NOT automatically
declared · prior results unchanged.** Reviews whether the concrete-object LLM judged-modulation study is ready
for an explicit, operator-confirmed EVIDENCE_FREEZE by binding the final stimuli, audits, generation rules,
deranged map, scoring contract, judge protocol, and thresholds. **Structure, not validated meaning.**

## 2. Artifacts reviewed (hash-bound)

sha256 at review time (bind these exact versions at freeze):

| sha256 | artifact |
|---|---|
| `c8cf24c4…bf01e` | b1_3_concrete_object_final_primary_wordlist.json |
| `123a86aa…1eda` | b1_3_concrete_object_deranged_source_map.json |
| `59b09eb8…ae44` | b1_3_concrete_object_generation_template_spec.json |
| `f4a52635…7d22` | b1_3_concrete_object_arm_construction_spec.json |
| `3f88056b…ffa1` | b1_3_concrete_object_semantic_baseline_spec.json |
| `abf19f6b…7731` | b1_3_concrete_object_llm_freeze_manifest_draft_v2.json |
| `48beaf88…bbbf` | b1_3_concrete_object_final_stimuli_draft.jsonl |
| `fe3a04a1…b4f8` | b1_3_concrete_object_style_audit_report.json |
| `99c41f64…6890` | b1_3_concrete_object_style_audit_report.md |
| `16aec929…82e9` | b1_3_concrete_object_stimulus_generation_manifest.json |
| `8f49f26e…4a16f` | b1_3_concrete_object_llm_judge_spec.json |
| `b55bc91f…4b25` | b1_3_concrete_object_llm_scoring_contract_v2.json |
| `156008bc…275c` | b1_3_concrete_object_llm_style_audit_protocol_draft.json |
| `dcaafe22…eadc1` | b1_3_concrete_object_deranged_stratification_spec.json |
| `9a986083…3a89` | b1_3_concrete_object_final_screen_manifest.json |

Full digests are recorded in `b1_3_concrete_object_llm_freeze_review_manifest.json`.

## 3. Study object

Dictionary meaning **fixes** the object. Varṇa/vṛtti supplies **modulation tags**, not a definition. Blinded
LLM judges compare which option **better fits the object-function without changing denotation** — testing the
real varṇa modulation against near/mid/far-deranged, scrambled, random, neutral, and a dictionary-derived
semantic-only baseline.

## 4. Final stimulus status

Confirmed: **371 records · 53 primary objects · 7 comparisons each** — A_real vs R_deranged_mid /
R_deranged_far / R_deranged_near / R_scrambled / R_random / X_neutral / semantic_only_baseline. **No evidence
judging yet.**

## 5. Audit status

Style-parity **PASS** · style-tell **PASS (balanced accuracy 0.378 ≤ 0.55)** · denotation-leakage **PASS** ·
quality-parity **PASS** · semantic-baseline **PASS** · near/mid/far sanity pass **ACCEPTED
(MAP_ACCEPTED_NO_REPLACEMENTS)**. All fixes during generation were **global template-level** (anti-leak,
no-Sanskrit/dedupe, shared-register, content-word preference); **no per-item rescue**.

## 6. Remaining blockers (assessment)

| Blocker | Status |
|---|---|
| Final judge model list | **OPEN** — not finalized (see §7) |
| Final judge prompt | **RESOLVED (drafted, frozen-ready)** — §8 |
| Final scoring-script implementation | **OPEN** — only the contract spec exists; no runnable scorer |
| Final thresholds | **RESOLVED (promoted to final)** — §9 |
| Final hash binding | **RESOLVED at review** — §2 (re-bind at freeze) |
| Explicit operator EVIDENCE_FREEZE declaration | **OPEN** — required, must be a separate operator step |

Two technical blockers remain open (**judge model list**, **scoring-script implementation**), so the study is
**not** yet at the "await operator confirmation" stage.

## 7. Judge model list proposal

Proposed panel (to be finalized): **≥2 distinct model families** for cross-family robustness; **deterministic /
low temperature** (recorded); **identical fixed prompt** across all models; **no chain-of-thought required**;
short rationale **optional, diagnostic-only**; position-balanced; item-order randomized; arm-labels blinded.
**Exact model identifiers cannot be responsibly finalized inside this preparation environment** (availability
and versioning must be pinned at run configuration), so this is marked an **OPEN blocker**, not resolved.

## 8. Final judge prompt (frozen-ready)

```
Object: {target_word}
Dictionary meaning: {dictionary_anchor}
Context: {neutral_context}

Option A: {option_left}
Option B: {option_right}

Question: Given the dictionary meaning of the object, which option gives a more fitting inner
tendency or field around this object without changing what it is?

Answer with exactly one letter: A or B.
Optionally, on a second line, give a confidence from 1 (guess) to 5 (certain).
```

Forced choice A/B only · optional confidence 1–5 · **no** spiritual/deeper/poetic/Sanskritic wording · **no**
arm labels · anchor identical across arms.

## 9. Final thresholds (promoted from draft)

- **Primary** A_real vs R_deranged_mid: **lower CI bound > 0.50**.
- A_real vs R_deranged_far: **lower CI bound > 0.50**.
- A_real **directionally > 0.50** vs R_scrambled, R_random, X_neutral, semantic_only_baseline.
- **semantic baseline must not match or beat A_real** (else `…SEMANTIC_BASELINE_EXPLAINS`).
- **Near deranged** reported as the **hard specificity test**: strong form requires A_real > R_deranged_near;
  passing mid/far but not near ⇒ **category-limited** (no word-specificity claim).
- **No single model-family dominance**; **no diagnostic/secondary contamination** of the primary result.
- Multiplicity correction (Holm) across the required comparisons; invalid-rate cap (draft 10%) → invalid run.

These are promoted to **final for freeze** (they will be hash-bound); they were not changed to fit any result
(no results exist).

## 10. Scoring-script readiness

**No runnable scoring script exists** — only the scoring **contract** (`…llm_scoring_contract_v2.json`). A
deterministic scorer must be implemented that consumes the stimuli + judge-output files and emits, as its
terminal decision, exactly one of:

`LLM_OBJECT_MODULATION_SIGNAL_EARNED_STRONG` · `LLM_OBJECT_MODULATION_SIGNAL_EARNED_CATEGORY_LIMITED` ·
`LLM_OBJECT_MODULATION_NULL` · `LLM_OBJECT_MODULATION_STYLE_CONFOUNDED` ·
`LLM_OBJECT_MODULATION_SEMANTIC_BASELINE_EXPLAINS` · `LLM_OBJECT_MODULATION_INVALID_RUN`

plus per-comparison win rates + CIs, the near/mid/far gradient, model-family and item-family breakdowns, and
audit/threshold pass-fail summaries. **This is an OPEN blocker.**

## 11. Freeze decision

```
DECISION: FREEZE_REVIEW_BLOCKED_NEEDS_SCORING_SCRIPT
```

The stimuli, audits, deranged map, generation rules, judge prompt, and thresholds are ready and hash-bound, but
**no runnable scoring script exists**, so the study cannot be frozen for a run whose analysis is pre-committed.
(The **judge model list** is a co-open blocker per §7; it is called out explicitly here even though the single
decision label names the scoring script as the primary gating artifact. Thresholds and prompt are resolved.)
This is not `FREEZE_REVIEW_READY_AWAITING_OPERATOR_CONFIRMATION` (technical blockers remain) and not
`FREEZE_REVIEW_FAIL_RETURN_TO_GLOBAL_REVISION` (the stimuli/audits are valid — no revision needed).

## 12. If ready (not yet)

When the scoring script and judge model list are resolved and re-bound, the review would move to
`FREEZE_REVIEW_READY_AWAITING_OPERATOR_CONFIRMATION`. **EVIDENCE_FREEZE is NOT declared inside any review**; it
requires a separate explicit operator step: *"Declare EVIDENCE_FREEZE for the B1.3 concrete-object LLM
judged-modulation study."* After freeze, **no changes** to stimuli, thresholds, prompts, or scoring rules —
post-freeze changes spawn a new version and cannot retro-rescue a run.

## 13. If blocked (current) — artifacts to create before freeze

1. **Runnable scoring script** implementing `…llm_scoring_contract_v2.json` and emitting the six terminal
   labels + the full report contract.
2. **Final judge model list** (pinned model identifiers + temperature + run config), hash-bound.
3. Re-bind all artifact hashes (including the two new ones) in an updated freeze manifest.
4. Then re-run this freeze review → operator confirmation → EVIDENCE_FREEZE.

## 14. Final status block

```
document:                    B1.3 concrete-object LLM EVIDENCE_FREEZE readiness REVIEW (review only)
decision:                    FREEZE_REVIEW_BLOCKED_NEEDS_SCORING_SCRIPT
stimuli:                     371 records / 53 objects / 7 comparisons — generated, audited, hash-bound
audits:                      style-parity / style-tell(0.378) / leakage / quality / semantic-baseline PASS; map accepted
resolved for freeze:         judge prompt; final thresholds; artifact hash binding (this review)
open blockers:               scoring-script implementation; final judge model list; operator EVIDENCE_FREEZE
evidence judge run:          NO
scoring run:                 NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        implement scoring script + finalize judge model list, re-bind, re-review
```

**Structure, not validated meaning.** The stimuli, audits, deranged map, generation rules, judge prompt, and
thresholds are ready and hash-bound, but the scoring script and judge model list remain open, so the study is
**not** frozen; no evidence judge was run, nothing was scored, prior nulls and closures stand, Track B remains
BLOCKED, and EVIDENCE_FREEZE is not declared.
