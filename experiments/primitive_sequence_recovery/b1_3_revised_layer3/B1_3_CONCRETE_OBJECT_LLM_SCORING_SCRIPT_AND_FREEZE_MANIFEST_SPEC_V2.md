# B1.3 Concrete-Object LLM Judged-Modulation — Scoring-Script & Freeze-Manifest Spec (V2)

## 1. Scope and status

Specification only. **No final stimuli generated · no judge run · no scoring · no EVIDENCE_FREEZE · no positive
label earned · prior results unchanged.** Updates the scoring-script contract and freeze-manifest structure to
incorporate the near/mid/far deranged stratification (`DERANGED_STRATIFICATION_SPEC_READY`).
**Structure, not validated meaning.**

## 2. Why V2 is needed

The scoring contract must reflect the **deranged near/mid/far stratification**. The **single `R_deranged` arm
is obsolete**. The **primary endpoint changed to `A_real` vs `R_deranged_mid`**, and **near/far are required
diagnostics** (near = hard word-specificity test; far = easy category-only control). V1's single-deranged
scoring would misreport a stratified study.

## 3. Scoring input contract

**Input files:** a **stimulus file** (frozen rendered options + private truth-map) and a **judge output file**.
**Required columns:** `item_id` · `target_word` · `primary_or_secondary_or_diagnostic` · `object_family` ·
`comparison_id` · `arm_left` · `arm_right` · `deranged_stratum` (near/mid/far, when applicable, else null) ·
`selected_option` · `model_id` · `parse_status` · `invalid_flag` · `position_seed` · `generation_seed`.

## 4. Required comparisons

`A_real` vs **R_deranged_mid** · **R_deranged_far** · **R_deranged_near** · **R_scrambled** · **R_random** ·
**X_neutral** · **semantic_only_baseline**. Optional: `A_real` vs `R_semantic_near` / `R_varṇa_near` (only if
**not duplicative** of `R_deranged_near`).

## 5. Primary endpoint

**`A_real` win-rate vs `R_deranged_mid`** on the primary concrete-object set. Mid deranged is the practical
object-specificity test — not trivially far, not unfairly near.

## 6. Required success criteria

To earn a future `LLM_OBJECT_MODULATION_SIGNAL`:

- `A_real` beats `R_deranged_mid`.
- `A_real` beats `R_deranged_far`.
- `A_real` beats `R_scrambled`.
- `A_real` beats `R_random`.
- `A_real` beats `X_neutral`.
- `A_real` beats **or adds beyond** `semantic_only_baseline`.
- style / denotation / quality audits pass.
- result holds on the primary concrete-object set.
- not driven by secondary/diagnostic words.
- not driven by one model family.

## 7. Near-deranged interpretation

`A_real` vs `R_deranged_near` is **required reporting**. A **strong word-specific claim requires
`A_real > R_deranged_near`**. If `A_real` **fails near but beats mid/far**, label the result
**weaker/category-level or function-family signal** — **do not overclaim word-specificity** without near
success.

## 8. Far-only interpretation

If `A_real` beats **far only**, that is **weak/category-only** and cannot earn the full signal. If `A_real`
**fails far → STOP**. If the gradient is **flat or inverted**, flag as **red**.

## 9. Other required controls

`R_scrambled` tests **order/structure**; `R_random` tests **generic symbolic tags**; `X_neutral` tests whether
**modulation adds any value**; `semantic_only_baseline` tests whether **dictionary object-function semantics**
explain the result.

## 10. Semantic-only baseline gate

The `semantic_only_baseline` is **required**. **If it matches or beats `A_real`, the Symbol-U-specific claim
fails** — even if `A_real` beats deranged/random, **baseline parity means the result is ordinary object
semantics**, not varṇa modulation → decision `LLM_OBJECT_MODULATION_SEMANTIC_BASELINE_EXPLAINS`.

## 11. Draft threshold contract

- **Primary** `A_real` vs `R_deranged_mid`: **lower CI bound > 0.50**.
- `A_real` vs `R_deranged_far`: **lower CI bound > 0.50**.
- `A_real` **directionally > 0.50** against `R_scrambled`, `R_random`, `X_neutral`, `semantic_only_baseline`.
- **Near deranged** reported with CI and interpretation tier (strong vs category-limited).
- **Corrected significance** or a **preregistered CI rule**.
- **No single item-family dominance**; **no single model-family dominance**.
- **Semantic-only baseline must not match `A_real`**.

**Draft until an explicit EVIDENCE_FREEZE.**

## 12. Statistical methods

Forced-choice binary scoring · aggregate win-rate · confidence intervals · exact/binomial test where used ·
mixed-effects logistic model (item + judge random effects) if sample size/model count supports it ·
model-family and item-family stratified reporting · multiplicity correction across the required comparisons.

## 13. Invalid-response handling

Predeclared handling of: **parse failures · ties/refusals · malformed outputs · repeated-answer artifacts**. A
**maximum invalid rate** (draft: >10% of judgments in a comparison) → `LLM_OBJECT_MODULATION_INVALID_RUN` /
STOP. **No manual correction** unless predeclared.

## 14. Style-audit gate contract

Before any evidence judge run: **style-parity · style-tell · denotation-leakage · quality-parity** audits must
**all pass**. If any fail → **no evidence run**. **Global template-level fixes only; no per-item rescue.** A
run whose style-tell fails post-hoc → `LLM_OBJECT_MODULATION_STYLE_CONFOUNDED`.

## 15. Output-report contract

The final scoring script emits: **overall decision label** · **per-comparison win rates** · **confidence
intervals** · **p-values (if used)** · **near/mid/far gradient report** · **model-family breakdown** ·
**item-family breakdown** · **primary-only result** · **secondary/diagnostic result (separately)** ·
**invalid-rate summary** · **audit pass/fail summary** · **threshold pass/fail summary**.

## 16. Possible future scoring decisions

- `LLM_OBJECT_MODULATION_SIGNAL_EARNED_STRONG` — beats near, mid, far + all controls + baseline; audits pass.
- `LLM_OBJECT_MODULATION_SIGNAL_EARNED_CATEGORY_LIMITED` — beats mid and far (+ controls + baseline) but not
  near; word-specificity **not** claimed.
- `LLM_OBJECT_MODULATION_NULL` — `A_real ≈` controls; no advantage.
- `LLM_OBJECT_MODULATION_STYLE_CONFOUNDED` — style-tell/quality/leakage audit fails; win uninterpretable.
- `LLM_OBJECT_MODULATION_SEMANTIC_BASELINE_EXPLAINS` — semantic baseline matches/beats `A_real`.
- `LLM_OBJECT_MODULATION_INVALID_RUN` — invalid rate over threshold / broken run.

## 17. Evidence-freeze manifest draft V2

`b1_3_concrete_object_llm_freeze_manifest_draft_v2.json` includes: `evidence_freeze_declared: false` ·
`hypothesis` · `allowed_future_labels` · `wordlist_artifacts` · `deranged_stratification_artifacts` ·
`generation_artifacts` · `style_audit_artifacts` · `scoring_contract` · `judge_model_list_status` ·
`thresholds_status` · `semantic_baseline_status` · `prior_results_preserved` · `missing_blockers` ·
`hash_binding_status`.

## 18. Hash-binding requirements

At the actual freeze, bind: **final word list · final near/mid/far deranged source map · final generation
template · final arm-construction spec · final semantic-baseline spec · final stimuli · final style-audit
result · final judge model list · final judge prompt · final scoring script · final thresholds · final
manifest.** No mutation after binding.

## 19. Remaining blockers after this spec

Final screened primary object list · final deranged near/mid/far source map · actual final stimulus generation ·
actual style-audit execution/result · final judge model list · final scoring-script implementation · final
thresholds · manifest hash binding · explicit EVIDENCE_FREEZE declaration · **actual judge run**.

## 20. Decision

```
DECISION: SCORING_FREEZE_MANIFEST_SPEC_V2_READY
```

The scoring input contract, required comparisons, mid-primary endpoint, near/far interpretation tiers,
semantic-baseline gate, draft thresholds, statistical methods, invalid handling, style-audit gate, output
report, the six future scoring-decision labels, and the V2 freeze-manifest structure are specified and
consistent with the stratified design. This is not `SCORING_FREEZE_MANIFEST_V2_HIGH_RISK_NEEDS_REVISION` (the
contract is complete and gated) and not `LLM_OBJECT_MODULATION_NOT_FREEZEABLE_CLOSE_LINE` (the study is
freezeable once the listed blockers are resolved). Thresholds remain draft until an explicit EVIDENCE_FREEZE.

## 21. Final status block

```
document:                    B1.3 concrete-object LLM SCORING-SCRIPT & FREEZE-MANIFEST spec V2 (specification only)
decision:                    SCORING_FREEZE_MANIFEST_SPEC_V2_READY
change:                      scoring/manifest updated for near/mid/far deranged strata; single R_deranged obsolete
primary endpoint:            A_real win-rate vs R_deranged_mid on primary concrete objects
required comparisons:        A_real vs mid / far / near / R_scrambled / R_random / X_neutral / semantic_baseline
future scoring decisions:    STRONG / CATEGORY_LIMITED / NULL / STYLE_CONFOUNDED / SEMANTIC_BASELINE_EXPLAINS / INVALID_RUN
semantic-baseline gate:      if baseline matches/beats A_real -> SEMANTIC_BASELINE_EXPLAINS (claim fails)
draft thresholds:            mid lower CI > 0.50; far lower CI > 0.50; directional vs other controls; near = tiered report
final stimuli generated:     NO
ran LLM judges / scoring:     NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        screen final list, freeze deranged source map, generate stimuli, run style audit, implement scorer
```

**Structure, not validated meaning.** The scoring contract and freeze-manifest structure are updated for the
near/mid/far deranged stratification; no final stimuli were generated, no judges were run, nothing was scored,
prior nulls and closures stand, Track B remains BLOCKED, and EVIDENCE_FREEZE is not declared.
