# CSR Supervised Observation Track — PRE-REGISTRATION

> **Status: DESIGN / PRE-REGISTRATION ONLY. Locked before any export or scoring code is written.** No
> runtime change; no Phase 1–3 logic change; no CSR_policy weight tuning; no wiring of
> `DerivedVrittiTrajectory` / `GunaQualityDiagnostic` into decisions; no canonical `p_v`; no canonical
> softmax-3D `p_g`; no hidden-risk control; no re-opening of Bhava claims; **no audit-derived label used
> as human truth.** This track exists because P-B (`PB_POLICY_NO_INCREMENTAL_VALUE`) was scored against
> `rubric_v2`, which shares detectors with the Phase 3 audit. The **only** legitimate way to re-open the
> policy question is against **independent human labels** — primarily `rewrite_needed`.

---

## 0. One line
Does the Phase 3 audit `needs_rewrite` gate predict **independent human** rewrite necessity — and do the
C×R×S / trajectory / Guna diagnostics add **incremental** value beyond it, against human labels (not
against `rubric_v2`)?

---

## 1. Deliverable 1 — Audit of current trace data

### Files inspected
| file | status | what it carries |
|---|---|---|
| `robustness_eval_v2.json` (pod `/workspace`, repo-root on pod) | **the dataset** (`production_valid=True`, rubric_v2) | `meta`, `backends[mistral]` (metrics/deltas/failures), `labels`, `traces[mistral]` = 110 items; each item: `id`, `category`, `answers{base,framed}` (model answer strings), `scores{base,framed}` (rubric_v2 fields + `reasons`) |
| `runs/csr_phase2b/robustness_stub.json` | same schema, **stub backend** (`production_valid=False`, rubric_v1) | used only to confirm the trace schema offline; **not** a labeling source |
| `scripts/.../eval_data/framed_answer_eval_v2_rubricv2.jsonl` | present (110 rows) | the prompts + **answer key**: `query`, `candidate_domains`, `expected_primary/secondary/rejected`, `must_include`, `may_include`, `must_not_include`, `false_claims`, `answer_type`, `ambiguity_type`, `category`, `notes` |
| `runs/csr_phase4_v3/*` | **absent** in this repo checkout (Phase 4 hidden-state collection lived on the pod; negative, closed) | n/a — not used here |
| `csr_policy_eval.json` / `.md` | on pod `/workspace` only | P-B output; **not** an input to this track (audit-derived) |

### What is available
- **Answers:** yes — model answer text for **both** `base` and `framed` arms (110 × 2 = **220 answers**).
- **Prompts / intended task:** yes — `query` (and `category`/`answer_type` for stratification) in the
  eval-data JSONL, joinable to traces by `id`.
- **C×R×S frame trace:** **not stored** in the robustness traces; `MATCH_primary` is **recomputable**
  offline from the answer + frame (as `csr_policy_eval.build_rows` already does). Deterministic, CPU.
- **Audit findings / `needs_rewrite`:** **not stored**; **recomputable** offline by running
  `answer_audit.py` on the stored answers. Deterministic, CPU. These become *predictors*, never labels.
- **Rubric_v2 scores:** stored per arm — **excluded from this track as ground truth** (the whole point).

### Usable fields (for predictors, recomputed offline — never shown to raters)
`id`, `arm`, `answers[arm]` (text), `query` (prompt), `category`/`answer_type`/`ambiguity_type` (strata),
+ recomputed `MATCH_primary`, audit `finding_types`/`needs_rewrite`, `DerivedVrittiTrajectory`,
`GunaQualityDiagnostic`.

### Fields that MUST be hidden from human raters (bias / leakage)
1. `expected_primary`, `expected_secondary`, `expected_rejected`, `candidate_domains`,
   `expected_secondary_true_senses` — **the answer key** (leaks the correct frame).
2. `must_include`, `may_include`, `must_not_include`, `false_claims` — graded constraints.
3. `scores{base,framed}` and `reasons` — the automated rubric_v2 verdict.
4. Phase 3 audit `finding_types` / `needs_rewrite`.
5. `MATCH_primary` / any C×R×S score; CSR_policy score; trajectory labels; Guna labels.
6. `arm` (`base`/`framed`) — hide if at all possible (prevents "framed must be better" priors).
7. `category` / `notes` if they hint at the intended answer (keep only as hidden strata keys).

### Missing fields (gaps)
- No stored C×R×S trace or audit trace in the file → recompute offline (deterministic; not a blocker).
- **No human labels at all** — this track creates them.
- No human-written reference/gold answer (we judge acceptability of the model answer directly, which is
  what we want; not a blocker).

### Recommended labeling sample size
- **Label all 220 answers** (110 items × 2 arms). The set is small enough that subsampling only costs
  power; the P-B run already showed ~78/220 *rubric* positives, so human-positive count should be in a
  usable range but is **unknown until labeled** (a power risk — see §9 risks).
- **Dual-rate** a randomly chosen **≥ 60-answer overlap subset** (≈ 27%) for inter-rater agreement
  (Cohen κ on binary labels; Spearman on the 1–5 scales). Expand to full dual-rating if budget allows.
- Pre-register a **minimum-positives stop**: if fewer than **20** `rewrite_needed=yes` human labels land,
  the evaluation is `SO_INSUFFICIENT_LABEL_POWER` (report descriptively, do not force a comparison).

**Conclusion (sufficiency): the existing `robustness_eval_v2.json` + eval-data JSONL are sufficient to
build a clean, de-biased human-labeling packet** — answers and prompts exist for both arms, and every
automated predictor is recomputable offline. No new model collection is required to start.

---

## 2. Deliverable 2 — Supervised observation label schema (plain observable labels)

Raters label **observable answer quality**, never interpretive constructs. **No** "Bhava / Guna / Vritti /
Sattva / Rajas / Tamas" labels — those remain *after-the-fact* mappings the analyst applies, never asked
of humans.

**Primary label**
- `rewrite_needed`: yes / no

**Secondary labels**
- `answer_acceptable`: yes / no
- `primary_frame_correct`: yes / no
- `rejected_domain_leak`: yes / no
- `secondary_overpromoted`: yes / no
- `generic_low_signal`: yes / no
- `clear_and_useful_1to5`: 1–5
- `factual_or_grounded_1to5`: 1–5
- `overconfident_or_overstated`: yes / no
- `frame_label_parroting`: yes / no
- `needs_clarification`: yes / no

**Optional**
- `short_reason`: free text (≤ 1 sentence)

All labels default `null` (unlabeled). Booleans are `"yes"`/`"no"`/`null`; scales are integers 1–5 or
`null`.

---

## 3. Deliverable 3 — Human labeling packet format

One rater-facing row per **(item, arm)**, arm hidden. JSONL (canonical) + a flattened CSV template for
spreadsheet raters. **Rows include only** what a user judging the answer would see:

```json
{
  "item_id": "ord_001__a",          // opaque id; arm encoded only in a SEPARATE private keymap
  "prompt": "What domain best frames the role of a doctor?",
  "answer": "<model answer text>",
  "intended_task": "Answer the user's question directly and usefully.",
  "rubric_hint": "Judge the answer as a user would; see rater instructions.",
  "human_labels": {
    "rewrite_needed": null,
    "answer_acceptable": null,
    "primary_frame_correct": null,
    "rejected_domain_leak": null,
    "secondary_overpromoted": null,
    "generic_low_signal": null,
    "clear_and_useful_1to5": null,
    "factual_or_grounded_1to5": null,
    "overconfident_or_overstated": null,
    "frame_label_parroting": null,
    "needs_clarification": null,
    "short_reason": null
  }
}
```

**Each row EXCLUDES** (enforced by the exporter, asserted in tests): audit findings; `needs_rewrite`
output; C×R×S / `MATCH` scores; CSR_policy score; trajectory labels; Guna labels; the rubric_v2 scores
and `reasons`; the **answer key** (`expected_*`, `must_*`, `false_claims`, `candidate_domains`); the
`arm` label; `category`/`notes` if leaky.

- **`intended_task`**: a neutral restatement so raters know what "good" means **without** seeing the
  expected domain. Default to a generic instruction; only include `candidate_domains` or an expected
  partition **never** (that is the answer key). If a minimal frame description is unavoidable for a
  given item, it must be a paraphrase of the *user's* need, reviewed to ensure it does not reveal the
  correct primary/rejected domains.
- **Arm handling**: a **private** `keymap.json` (analyst-only) maps `item_id` → `(real_id, arm)`. The
  rater file carries neither. Order is shuffled with a fixed pre-registered seed so arm is not inferable
  from position.
- **Optional `rubric_instruction`**: a pointer to the rater-instructions doc, not per-row guidance.

---

## 4. Deliverable 4 — Rater instructions (draft)

> **What you are doing.** You see a user's question and one answer. Judge **the answer**, not the model,
> the prompt, or any system. Imagine you are the user who asked the question.
>
> 1. **`rewrite_needed = yes`** if a reasonable user would need this answer **rewritten before they could
>    use it** (wrong, misleading, off-topic, or too vague to act on). `no` if it is usable as-is.
> 2. **`answer_acceptable = yes`** if the answer is usable as-is (the natural complement of `rewrite_needed`,
>    but judge it independently — do not just mirror).
> 3. **`primary_frame_correct = no`** if the answer addresses the **wrong meaning / domain** of the
>    question (answers a different sense than the user intended).
> 4. **`rejected_domain_leak = yes`** if it pulls in an **unrelated or wrong domain** that does not belong.
> 5. **`secondary_overpromoted = yes`** if a **minor / secondary** meaning is treated as the **main**
>    answer.
> 6. **`generic_low_signal = yes`** if it is **vague, padded, or mostly filler** — true but useless.
> 7. **`overconfident_or_overstated = yes`** if it asserts more certainty/scope than warranted.
> 8. **`frame_label_parroting = yes`** if it **talks about "frames / domains / categories"** instead of
>    just answering the question naturally.
> 9. **`needs_clarification = yes`** if the question is genuinely ambiguous and the answer should have
>    asked back instead of guessing.
> 10. **`clear_and_useful_1to5`** and **`factual_or_grounded_1to5`**: 1 = very poor, 5 = excellent.
> 11. **`short_reason`**: one short phrase, optional.
>
> **Do not** try to guess what the system "intended," what an arm/condition is, or any internal label.
> There are no "Bhava/Guna/Vritti" judgments — just answer quality. When unsure, use your judgment as the
> end user and leave a `short_reason`.

- **Raters:** prefer **two independent raters**; resolve nothing during labeling (disagreement is data).
- **Agreement tracking (pre-registered):** Cohen **κ** for each binary label; **Spearman** (and Pearson)
  for each 1–5 scale, on the dual-rated overlap subset. Report per-label κ; flag any primary-label
  κ < 0.4 as `SO_INSUFFICIENT_RATER_AGREEMENT` (see §8).
- **Adjudication:** for the primary `rewrite_needed`, disagreements on dual-rated rows are adjudicated by
  a pre-named tie-breaker **or** treated as "uncertain" and excluded from the primary comparison (choice
  fixed **before** seeing labels; default = majority/adjudicator, recorded in the run).

---

## 5. Deliverable 5 — Pre-registration of the supervised evaluation

### 5.1 Objective
Test whether the automated CSR / Phase 3 audit diagnostics predict **independent human rewrite
necessity** and **answer acceptability**, and whether the C×R×S / trajectory / Guna diagnostics add
incremental value **beyond the existing audit gate**.

### 5.2 Primary target
`human_rewrite_needed` (the human primary label, after adjudication).
**Secondary target:** `human_answer_acceptable` (+ correlation with the two 1–5 scales).

### 5.3 Primary baseline (the bar to beat — exact, not weakened)
The **Phase 3 audit `needs_rewrite` gate exactly as implemented** (`answer_audit.should_rewrite`;
narrow: critical `rejected_domain_promoted` / `phoneme_overreach_claim`), recomputed on the stored
answers. No modification to the auditor.

### 5.4 Candidate predictors
**Allowed:** Phase 3 audit fields (`finding_types`, severities); C×R×S `MATCH`/frame trace
(`1 − MATCH_primary`); `DerivedVrittiTrajectory` diagnostics; `GunaQualityDiagnostic` diagnostics. All
deterministic, recomputed offline, over the **non-overlap partition** carried over from P-B
(`trajectory_drift` / `audit_severity` / `guna_quality` / `1−MATCH` — disjoint; an overlap map is
emitted, else `SO_TERM_OVERLAP_INVALID`).

**Forbidden:** answer-text embeddings (unless separately pre-registered); hidden states; canonical
`p_v`; canonical softmax-3D `p_g`; Bhava labels; rubric_v2 / any audit-derived label as ground truth;
human labels leaking into both train and test of the same fold.

### 5.5 Comparisons (nested; each adds one diagnostic family)
| id | predictor set |
|---|---|
| **A** | Phase 3 `needs_rewrite` gate (baseline) |
| **B** | Phase 3 audit fields (finding-type indicators + severity) |
| **C** | B + C×R×S `MATCH`/frame trace (`1−MATCH_primary`) |
| **D** | B + `DerivedVrittiTrajectory` |
| **E** | B + `GunaQualityDiagnostic` |
| **F** | B + C×R×S + trajectory + Guna (all diagnostics) |

Each learned set (B–F) is fit by **grouped-by-item CV** on a coarse pre-registered grid (same discipline
as P-B: `w ∈ {0, 0.5, 1}`, `τ` swept; metric reported on held-out folds only; no free post-hoc tuning).
Groups = `item_id` so the two arms of an item never split across train/test.

### 5.6 Metrics
For **`human_rewrite_needed`**: precision · recall · **F1** (primary) · false-rewrite rate ·
missed-rewrite rate · **ΔF1 vs baseline with grouped bootstrap CI** · per-class recall
(frame / rejected-leak / secondary / generic) · term-contribution table.
For **`human_answer_acceptable`**: accuracy / F1; correlation of predictors with
`clear_and_useful_1to5` and `factual_or_grounded_1to5` (Spearman).
Reported within-arm and pooled; plus **inter-rater κ / Spearman** from §4.

### 5.7 Success gate (a candidate B–F beats the audit gate only if ALL hold)
1. **ΔF1 ≥ +0.05** vs the Phase 3 gate on `human_rewrite_needed`;
2. grouped-bootstrap **CI lower bound > 0**;
3. **missed-rewrite (and missed-critical) rate does not worsen** (≤ baseline);
4. **false-rewrite rate ≤ baseline + 0.02**;
5. improvement is **not explained by term overlap / repackaging** (non-overlap partition holds; decision
   agreement with baseline < 0.97 where it improves, i.e. genuine new catches);
6. enough adjudicated positives + adequate rater agreement (else §8 power/agreement labels).

### 5.8 Decision labels
- `SO_AUDIT_GATE_VALIDATED` — Phase 3 `needs_rewrite` tracks human `rewrite_needed` well **and** no
  diagnostic set B–F clears §5.7. (The current product is the right product.)
- `SO_DIAGNOSTICS_ADD_SIGNAL` — at least one of B–F clears **all** of §5.7. (Then, and only then, a
  *new* pre-registration may consider a runtime policy — this track does **not** build one.)
- `SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE` — gate is fine but B–F add nothing clearing §5.7.
- `SO_AUDIT_GATE_FAILS_HUMAN_LABELS` — the Phase 3 gate itself predicts human labels poorly (e.g. low
  F1 / high missed-rewrite vs humans). Do **not** patch post-hoc; open a **new** audit-improvement
  pre-registration.
- `SO_INSUFFICIENT_RATER_AGREEMENT` — primary-label κ below threshold (default κ < 0.4); labels not
  trustworthy enough to decide.
- `SO_INSUFFICIENT_LABEL_POWER` — too few adjudicated positives (< 20 `rewrite_needed=yes`).
- `SO_TERM_OVERLAP_INVALID` — the disjoint partition cannot be maintained / overlap drives a result.

### 5.9 Kill criterion
- If diagnostics do **not** beat the Phase 3 gate on **human** labels → keep them **diagnostic-only**,
  build **no** runtime policy. (Consistent with the P-B close-out.)
- If the Phase 3 gate **itself** fails against human labels → do **not** patch post-hoc; create a new
  pre-registration for audit improvement.
- Anything other than `SO_DIAGNOSTICS_ADD_SIGNAL` → no runtime change of any kind. No re-tuning; a new
  attempt is a new pre-registration.

### 5.10 Honest prior
The audit + rubric were co-designed, so the gate is *expected* to track human labels at least moderately
(`SO_AUDIT_GATE_VALIDATED` or `SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE` are the most likely outcomes). The
genuinely new degrees of freedom are (a) the `1−MATCH` term and (b) the freedom to flag *non-critical*
residuals the narrow gate ignores — the same two that failed against rubric_v2 in P-B; whether they help
against **human** labels is the open question. A clean negative is fully accepted and ends the policy
question for good (absent a new pre-reg). We may **also** learn the gate itself diverges from humans —
that is a valuable, separately-actionable finding, not a failure of this design.

---

## 6. Deliverable 6 — Implementation plan (proposed; NOT implemented here)

| file | role |
|---|---|
| `scripts/cg_wrapper_ablation/csr_match_filter/export_supervised_observation_packet.py` | join `robustness_eval_v2.json` × eval-data by `id`; emit de-biased `supervised_observation_packet.jsonl` + `supervised_observation_labels_template.csv` + private `keymap.json`; **assert** every hidden field is absent from rater rows; fixed shuffle seed |
| `scripts/cg_wrapper_ablation/csr_match_filter/eval_supervised_observation.py` | read labels + recompute predictors offline (audit, MATCH, trajectory, Guna); run comparisons A–F with grouped-by-item CV, grouped bootstrap CI, κ/Spearman; emit `supervised_observation_eval.json` + `.md` + a decision label from §5.8 |
| `tests/test_supervised_observation_export.py` | CPU: assert no hidden/answer-key/arm field leaks into rater rows; keymap round-trips; shuffle deterministic |
| `tests/test_supervised_observation_eval.py` | CPU on synthetic labeled rows: metric math, non-overlap partition, every §5.8 decision label, power/agreement gates |

**Expected outputs:** `supervised_observation_packet.jsonl`, `supervised_observation_labels_template.csv`,
`supervised_observation_eval.json`, `supervised_observation_eval.md`.

**Build order (when authorized):** exporter + its test first (it produces the human packet; needs no
labels) → collect human labels → evaluator + its test. The exporter can be built and tested on the
existing traces immediately; the evaluator is testable on synthetic labels before any human labeling
finishes.

---

## 7. Risks & ambiguities (stated up front)
- **Label power:** human `rewrite_needed=yes` count is unknown until labeling; 220 rows is small. The
  `SO_INSUFFICIENT_LABEL_POWER` floor (≥ 20 positives) guards against over-reading a thin signal.
- **Rater agreement:** "rewrite necessity" is subjective; κ may be low. Dual-rating + the
  `SO_INSUFFICIENT_RATER_AGREEMENT` gate (κ ≥ 0.4) guard this. Tight, example-anchored instructions
  reduce variance.
- **`intended_task` leakage:** restating the task without revealing the expected domain is delicate.
  Mitigation: default to a generic instruction; never include `expected_*`/`candidate_domains`; review
  any per-item paraphrase for answer-key leakage before release.
- **Arm de-identification:** framed answers may be stylistically recognizable ("the primary frame
  is…") — that is itself a `frame_label_parroting` signal we *want* raters to catch, but it could bias
  arm inference. We hide the arm label and shuffle; we do not claim arms are perfectly blinded.
- **Predictor recomputation drift:** audit/MATCH must be recomputed exactly as runtime computes them;
  the evaluator reuses the production `answer_audit.py` / frame code (no re-implementation) to avoid
  drift.
- **Single-rater fallback:** if only one rater is available, agreement is unverifiable → results carry a
  `single_rater` caveat and cannot reach `SO_DIAGNOSTICS_ADD_SIGNAL` (downgraded to descriptive).

---

## 8. Recommendation
**Proceed to doc-only pre-registration now (this file), then build the export packet** on the existing
`robustness_eval_v2.json` — the traces are **sufficient** to produce a clean, de-biased human-labeling
packet without any new model collection. Defer the evaluator until human labels exist (it is testable on
synthetic labels meanwhile). Do **not** collect new traces first — the current 220 answers (both arms,
real-Mistral, `production_valid=True`) are an adequate and already-validated starting set; only revisit
collection if human positives fall below the power floor.

No runtime behavior is changed by this track. No Guna/Vritti/Bhava validity is claimed from it; those
remain interpretive, after-the-fact mappings.
