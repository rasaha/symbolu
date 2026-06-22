# RESULTS — Supervised Observation: audit gate vs independent human `rewrite_needed`

> **Status: AWAITING HUMAN LABELS — skeleton only.** Pre-registration:
> `docs/CSR_SUPERVISED_OBSERVATION_PREREG.md`. Fill the bracketed `[…]` cells from the real evaluator run
> (`eval_supervised_observation.py` on `--labels <filled>`), then write the verdict + close-out. Do **not**
> populate this from synthetic labels (`*_SYNTHETIC*`) or from rubric_v2 — that violates the pre-reg.

## 1. Run (fill on first real run)
- **Labels:** `[supervised_observation_labels_filled.csv  | rater1.csv,rater2.csv]`  · raters: `[1|2]`
- **Trace:** `robustness_eval_v2.json` (`production_valid=True`, real Mistral; base primary 0.609 / framed 0.736)
- **Command:**
  ```bash
  python scripts/cg_wrapper_ablation/csr_match_filter/eval_supervised_observation.py \
    --labels [LABELS] --keymap supervised_observation_private_keymap.json \
    --traces robustness_eval_v2.json \
    --eval-data scripts/cg_wrapper_ablation/csr_match_filter/eval_data/framed_answer_eval_v2_rubricv2.jsonl \
    --out supervised_observation_eval.json --report supervised_observation_eval.md
  ```
- **Outputs:** `supervised_observation_eval.json` + `.md` (pod `/workspace`).
- **Rows:** `[n]`  ·  **human rewrite_needed=yes:** `[n_pos]`  ·  **single_rater_descriptive_only:** `[true|false]`
- **MATCH available (sets C/F use inv_match):** `[true|false]`

## 2. Label power & rater agreement (gate preconditions)
| check | value | threshold | pass? |
|---|---|---|---|
| positives (`rewrite_needed=yes`) | `[n_pos]` | ≥ 20 | `[ ]` |
| Cohen κ — `rewrite_needed` | `[κ]` | ≥ 0.40 | `[ ]` |
| Cohen κ — other binary labels | `[…]` | (report) | — |
| Spearman — `clear_and_useful_1to5` | `[ρ]` | (report) | — |
| Spearman — `factual_or_grounded_1to5` | `[ρ]` | (report) | — |

(If `n_pos < 20` → `SO_INSUFFICIENT_LABEL_POWER`. If two raters and κ < 0.40 → `SO_INSUFFICIENT_RATER_AGREEMENT`. Both are terminal.)

## 3. Predictor comparison vs human `rewrite_needed`
| set | predictors | F1 | precision | recall | false_rw | missed_rw | ΔF1 vs gate | CI | overlap |
|---|---|---|---|---|---|---|---|---|---|
| **A** baseline (`needs_rewrite`) | Phase 3 gate | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | — | — | — |
| **B** audit fields | audit_severity | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[lo,hi]` | `[ok]` |
| **C** audit + C×R×S | B + (1−MATCH) | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[lo,hi]` | `[ok]` |
| **D** audit + trajectory | B + traj_drift | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[lo,hi]` | `[ok]` |
| **E** audit + Guna | B + guna_quality | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[lo,hi]` | `[ok]` |
| **F** all diagnostics | B + match + traj + guna | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[ ]` | `[lo,hi]` | `[ok]` |

- **Best set:** `[…]`  ·  **confusion (best):** tp `[ ]` fp `[ ]` fn `[ ]` tn `[ ]`
- **Disjoint partition held (overlap_map):** `[yes/no]` — `audit_severity` / `traj_drift` / `guna_quality` / `inv_match` consume non-overlapping findings.

## 4. Secondary target — `answer_acceptable` & 1–5 scales
- `answer_acceptable` accuracy/F1 of best set: `[…]`
- mean `clear_and_useful_1to5`: `[…]`  ·  mean `factual_or_grounded_1to5`: `[…]`
- correlation of predictors with the two scales: `[…]`

## 5. Success gate (§5.7 — ALL required for `SO_DIAGNOSTICS_ADD_SIGNAL`)
1. ΔF1 ≥ +0.05 vs gate — `[ ]`
2. bootstrap CI lower bound > 0 — `[ ]`
3. missed-rewrite rate ≤ baseline — `[ ]`
4. false-rewrite rate ≤ baseline + 0.02 — `[ ]`
5. improvement not overlap/repackaging (disjoint partition holds; genuine new catches) — `[ ]`
6. ≥ 2 raters with adequate agreement — `[ ]`

## 6. DECISION
`[ SO_AUDIT_GATE_VALIDATED | SO_DIAGNOSTICS_ADD_SIGNAL | SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE |
   SO_AUDIT_GATE_FAILS_HUMAN_LABELS | SO_INSUFFICIENT_RATER_AGREEMENT | SO_INSUFFICIENT_LABEL_POWER |
   SO_TERM_OVERLAP_INVALID ]`

**Reasoning:** `[…]`

## 7. Close-out (apply the matching branch; delete the others)
- **`SO_DIAGNOSTICS_ADD_SIGNAL`** — a diagnostic family beats the gate against *human* labels. This is the
  one outcome that re-opens a runtime-policy question — but **not here**: open a **new** pre-registration
  for a runtime policy (with the §5.7-passing set, held-out validation, and a pinned baseline). No runtime
  change is made on the strength of this evaluation alone.
- **`SO_AUDIT_GATE_VALIDATED` / `SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE`** — the gate tracks human judgement
  and diagnostics add nothing clearing §5.7. **Kill criterion:** keep C×R×S + Phase 3 `needs_rewrite` as
  the product; trajectory/Guna stay **diagnostic-only**; build no runtime policy. Done.
- **`SO_AUDIT_GATE_FAILS_HUMAN_LABELS`** — the gate itself diverges from human judgement. Do **not** patch
  post-hoc; open a **new** audit-improvement pre-registration. The current product stands until then.
- **`SO_INSUFFICIENT_RATER_AGREEMENT` / `SO_INSUFFICIENT_LABEL_POWER`** — labels can't decide. Collect more
  positives / more raters under the same pre-reg; do not over-read the thin signal. No change.
- **`SO_TERM_OVERLAP_INVALID`** — a winning improvement was driven by a double-counted feature. The result
  is invalid; redefine disjoint families in a new pre-reg. No change.

No runtime behavior, Phase 1–3 logic, or CSR_policy weights change as a result of this track unless a
*separate* pre-registration (triggered only by `SO_DIAGNOSTICS_ADD_SIGNAL`) is approved and passes.
