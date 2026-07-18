# B1.3 Concrete-Object LLM Judged-Modulation — Scoring-Script Implementation

## 1. Scope and status

Scoring-script implementation only. **No evidence judge run · no real judge outputs scored (synthetic fixtures
only) · no EVIDENCE_FREEZE · no positive label earned · prior results unchanged.** Implements the runnable
scorer required by the freeze review (`FREEZE_REVIEW_BLOCKED_NEEDS_SCORING_SCRIPT`), per scoring contract V2.
**Structure, not validated meaning.**

## 2. Files created

- `score_b1_3_concrete_object_llm.py` — the scorer (deterministic, no network, no judge calls).
- `test_score_b1_3_concrete_object_llm.py` — synthetic-fixture tests (10 tests, all six terminal labels + helpers).
- `b1_3_concrete_object_llm_scoring_script_manifest.json` — this implementation's manifest.

## 3. Scoring-script inputs

CLI flags: `--stimuli` (final stimuli JSONL) · `--judge-outputs` (judge outputs JSONL) · `--style-audit`
(style audit report JSON) · `--contract` (scoring contract JSON) · `--out-json` · `--out-md`. Input sha256
digests are computed and recorded in the report.

## 4. Judge-output fields (validated)

Required: `item_id`, `comparison_id`, `arm_left`, `arm_right`, `selected_option`. Supported/used:
`target_word`, `primary_or_secondary_or_diagnostic`, `object_family`, `model_id`, `parse_status`,
`invalid_flag`, `deranged_stratum`, `confidence` (optional), `option_left`/`option_right` (optional).

## 5. Selection handling

`selected_option` maps `A/left/l` → left and `B/right/r` → right (deterministic, documented). The winning arm
is read from `arm_left`/`arm_right`; A_real wins iff the selected side's arm is `A_real`. A judgment is counted
**invalid** (never silently repaired) when: a required field is missing · `invalid_flag` is true ·
`parse_status` ∈ {unparseable, refused, malformed, tie} · the selection is unmappable · or the pair contains no
`A_real` arm.

## 6. Required comparisons & primary endpoint

Seven comparisons scored: A_real vs R_deranged_mid / R_deranged_far / R_deranged_near / R_scrambled / R_random /
X_neutral / semantic_only_baseline. **Primary endpoint: A_real win-rate vs R_deranged_mid on the primary
concrete-object set.**

## 7. Statistical method (CI)

- **Wilson score interval** (primary threshold rule: lower bound > 0.50) and **exact Clopper-Pearson**
  interval (reported alongside), both implemented from scratch and **validated against reference values**
  (CP 8/10 → (0.4439, 0.9748); Wilson 8/10 → (0.4902, 0.9433); CP 0/10 → (0, 0.3085); CP 10/10 → (0.6915, 1)).
  Clopper-Pearson uses the regularized incomplete beta (Lentz continued fraction) inverted by bisection —
  `I_0.5(a,a)=0.5` verified.
- **p-values:** deterministic normal-approx two-sided binomial test vs p₀=0.5, used for ordering/reporting.

## 8. Multiple-comparison correction (Holm)

**Holm-Bonferroni** across the seven required comparisons, with enforced monotonicity of adjusted p-values.
The primary decision rule is CI-based (lower bound > 0.50); Holm-adjusted p-values are reported alongside.

## 9. Terminal-label rules (exactly one emitted)

Evaluated in order:
1. **INVALID_RUN** — no judgments · any required comparison missing · invalid rate > 10%.
2. **STYLE_CONFOUNDED** — any pre-judge audit (style-parity / style-tell / leakage / quality / semantic-baseline
   / overall) did not pass.
3. **SEMANTIC_BASELINE_EXPLAINS** — semantic_only_baseline matches or beats A_real (A_real not > 0.50 over
   baseline, or its lower CI ties the baseline).
4. **NULL** — A_real fails mid (lower CI ≤ 0.50) · fails far (lower CI ≤ 0.50) · fails any directional control
   (scrambled/random/neutral ≤ 0.50) · or a single model family dominates A_real wins.
5. **STRONG** — A_real beats near (lower CI > 0.50), mid, far, all controls, and the baseline.
6. **CATEGORY_LIMITED** — beats mid/far + controls + baseline but **not** near (no word-specificity claim).

## 10. Stratified reporting

The report emits: per-comparison win rates + Wilson & Clopper-Pearson CIs + Holm-adjusted p · primary-endpoint
result · near/mid/far gradient (with monotonicity flag) · model-family breakdown + dominance flag · item-family
(object-family) breakdown · secondary/diagnostic tier results (separately, never as primary) · invalid-rate
summary + breakdown · audit summary · threshold summary · warnings · input hashes.

## 11. Tests / fixtures (all pass)

`python3 test_score_b1_3_concrete_object_llm.py` → **10/10 pass**, covering: STRONG, CATEGORY_LIMITED (near
tie), SEMANTIC_BASELINE_EXPLAINS (baseline beats A_real), NULL (mid at chance), NULL (single-model-family
dominance), INVALID_RUN (invalid rate > 10%), INVALID_RUN (missing required comparison), STYLE_CONFOUNDED
(audit fail), selection mapping (A/B/left/right/garbage), and CI/Holm helper correctness. All fixtures are
**synthetic**; no real judge output exists or was scored.

## 12. No evidence scoring

The scorer was **not** run on real judge outputs — none exist. It ran only on fabricated fixtures to verify the
decision logic. The script itself earns no label; it computes one from data **after** an eventual EVIDENCE_FREEZE
and a real judge run.

## 13. Limitations

- Model-family dominance uses `model_id` as the family key; the final judge model list must supply meaningful
  family identifiers (a co-open blocker).
- p-values use a normal approximation (for Holm ordering); the **decision** rule is the CI lower-bound test, so
  small-n behavior is governed by the (exact-capable) interval, not the approximate p.
- The dominance fraction (0.60), invalid cap (0.10), and baseline-tie guard (0.45) are encoded from the
  finalized thresholds; changing them post-freeze spawns a new version.

## 14. Remaining blockers before EVIDENCE_FREEZE

- **Final judge model list** (pinned identifiers + temperature + run config), hash-bound — still OPEN.
- Re-bind all artifact hashes (including this scorer + tests) in an updated freeze manifest.
- Re-run the freeze review → operator confirmation → explicit EVIDENCE_FREEZE.
- Then the actual evidence judge run + real scoring.

## 15. Final status block

```
document:                    B1.3 concrete-object LLM SCORING-SCRIPT implementation
scorer:                      score_b1_3_concrete_object_llm.py (deterministic, no network, no judge calls)
tests:                       test_score_b1_3_concrete_object_llm.py — 10/10 PASS (all six terminal labels)
CI method:                   Wilson (decision) + exact Clopper-Pearson (reported); validated vs references
correction:                  Holm-Bonferroni across required comparisons
terminal labels:             STRONG / CATEGORY_LIMITED / NULL / STYLE_CONFOUNDED / SEMANTIC_BASELINE_EXPLAINS / INVALID_RUN
real judge outputs scored:   NO (synthetic fixtures only)
evidence judge run:          NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        finalize judge model list, re-bind hashes, re-review, operator EVIDENCE_FREEZE, then run
```

**Structure, not validated meaning.** The scorer is implemented and unit-tested on synthetic fixtures across all
six terminal labels; no evidence judge was run, no real outputs were scored, prior nulls and closures stand,
Track B remains BLOCKED, and EVIDENCE_FREEZE is not declared.
