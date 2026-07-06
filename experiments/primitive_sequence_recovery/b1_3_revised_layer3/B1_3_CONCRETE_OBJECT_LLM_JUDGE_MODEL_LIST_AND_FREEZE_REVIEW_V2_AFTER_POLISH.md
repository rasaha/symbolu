# B1.3 Concrete-Object LLM Judged-Modulation — Judge Model List & Freeze Review V2 (after polish)

## 1. Scope and status

Freeze-readiness review only. **No judge run · no real scoring · no EVIDENCE_FREEZE · no positive label
earned · prior results unchanged.** Finalizes the judge model list/run configuration and re-runs the freeze
readiness review against the **v2 globally-polished** concrete-object stimuli and audits.
**Structure, not validated meaning.**

## 2. v2 artifact selection

The freeze review uses the **v2 polished stimuli**, not v1. **v1 artifacts are preserved as historical draft
artifacts and are NOT bound as active freeze inputs.** v2 supersedes v1 for any future EVIDENCE_FREEZE. Active
v2 inputs:

- `b1_3_concrete_object_final_stimuli_draft_v2.jsonl`
- `b1_3_concrete_object_style_audit_report_v2.json`
- `b1_3_concrete_object_style_audit_report_v2.md`
- `b1_3_concrete_object_stimulus_generation_manifest_v2.json`

(v1 `…_final_stimuli_draft.jsonl` / `…_style_audit_report.json` are listed in the manifest as **historical
reference only**.)

## 3. v2 audit summary

371 stimuli · 53 objects × 7 comparisons. **All eight gates PASS:** style-parity (mean |char-len diff| 1.87) ·
style-tell (**0.532 ≤ 0.55**) · denotation-leakage · quality-parity · semantic-baseline · **forbidden-token
scan (0 Sanskrit, 0 over-band)** · **duplicate-tag scan** · **tag-length parity by arm (spread 0.557)**. **0
over-band tokens; `garrulous` eliminated.** All fixes were global template-level rules — **no per-item rescue**.

## 4. Judge model list

Exact runtime model availability cannot be guaranteed inside this preparation environment, so a **constrained
model-family policy** is fixed here and the **operator pins exact runtime model identifiers + versions at the
freeze/run step** (they become part of the frozen record). Policy (`b1_3_concrete_object_llm_judge_model_config_v2.json`):

- **min 2, target 3 families.** Slots: `frontier_A` (top-tier frontier judge), `frontier_B` (same-vendor,
  version-distinct), `cross_vendor_C` (**different vendor**, recommended, for cross-vendor robustness).
- **deterministic / low temperature** (0.0, or lowest permitted, recorded) · **identical prompt** · **identical
  output schema** · **no chain-of-thought required** · **optional confidence 1–5** · **fixed retry/invalid
  policy** (≤2 retries on transport/empty only; unparseable → invalid, never hand-repaired).
- A result carried by a **single family** is down-weighted by the scorer's no-single-model-family-dominance
  rule.

(Exact model identifiers are intentionally not hard-coded; this keeps the config vendor-agnostic and lets the
operator record the pinned IDs in the frozen run log.)

## 5. Judge prompt (final)

```
Object: {target_word}
Dictionary meaning: {dictionary_anchor}
Context: {neutral_context}

Option A: {option_left}
Option B: {option_right}

Question: Given the dictionary meaning of the object, which option gives a more fitting inner
tendency or field around this object without changing what it is?

Answer with exactly one letter: A or B. Optionally, on a second line, confidence 1-5.
```

Forced A/B · optional confidence 1–5 · **no** spiritual/poetic/Sanskritic/"defines the object" wording · **no**
arm labels shown to the model.

## 6. Run configuration

`temperature` 0.0 (lowest permitted, recorded) · `top_p` 1.0 · `max_output_tokens` 16 · **system prompt**
"careful annotator, single letter only, no explanation" · **user prompt template** as §5 · **output JSON
schema** echoing item/comparison/target/tier/family + `model_id` + `selected_option` + `confidence` +
`parse_status` + `invalid_flag` (arm_left/arm_right echoed for scoring but **hidden from the model**) ·
**retries** ≤2 on transport/empty, no prompt change · **invalid handling** never hand-repaired, counts toward
the 10% cap · **model ordering** every item judged by every pinned model, results reported per `model_id` ·
**position balancing** already baked into the stimuli via `position_seed` · **no access to hidden arm labels**.

## 7. Hash-bound active artifacts

sha256 recorded in `b1_3_concrete_object_llm_freeze_review_manifest_v2_after_polish.json`:

| sha256 | artifact |
|---|---|
| `c8cf24c4…` | final_primary_wordlist.json |
| `123a86aa…` | deranged_source_map.json |
| `59b09eb8…` | generation_template_spec.json |
| `f4a52635…` | arm_construction_spec.json |
| `3f88056b…` | semantic_baseline_spec.json |
| `dcaafe22…` | deranged_stratification_spec.json |
| `b55bc91f…` | llm_scoring_contract_v2.json |
| `156008bc…` | llm_style_audit_protocol_draft.json |
| `8f49f26e…` | llm_judge_spec.json |
| `dbdf6f4b…` | score_b1_3_concrete_object_llm.py |
| `6b9fc03a…` | test_score_b1_3_concrete_object_llm.py |
| `d15f7da3…` | llm_scoring_script_manifest.json |
| `20f1ab61…` | **final_stimuli_draft_v2.jsonl** |
| `f2766631…` | **style_audit_report_v2.json** |
| `1b9fc85c…` | **style_audit_report_v2.md** |
| `559c9213…` | **stimulus_generation_manifest_v2.json** |
| `ee504033…` | **llm_judge_model_config_v2.json** |

The freeze-review manifest's **own** sha256 is bound by the operator at the freeze step (pending self-hash).

## 8. Freeze-readiness assessment

| Item | Status |
|---|---|
| v2 stimuli ready | **YES** |
| v2 audits passed | **YES** (all 8) |
| scorer implemented + tested | **YES** (10/10) |
| thresholds final | **YES** |
| judge prompt final | **YES** |
| judge model list/config final | **POLICY final**; operator pins exact runtime IDs (sanctioned fallback) |
| hashes bound | **YES** (17 active artifacts) |
| operator EVIDENCE_FREEZE | **STILL REQUIRED** (separate explicit step) |

## 9. Decision

```
DECISION: FREEZE_REVIEW_V2_AFTER_POLISH_READY_AWAITING_OPERATOR_CONFIRMATION
```

v2 stimuli and audits are ready, the scorer is implemented and tested, thresholds and prompt are final, the
judge model-family policy + run config are fixed, and all 17 active artifacts are hash-bound. The only remaining
steps are genuinely the operator's: **pin the exact runtime model identifiers and declare EVIDENCE_FREEZE.**
This is not `…BLOCKED_NEEDS_MODEL_IDS` (the config sanctions operator ID-pinning as the final step, not a
missing artifact), not `…BLOCKED_NEEDS_HASH_REBIND` (hashes are bound to v2), and not
`…FAIL_RETURN_TO_REVISION` (all audits pass).

## 10. If ready — operator next step

The next step is a **separate explicit operator instruction**:
> *"Declare EVIDENCE_FREEZE for the B1.3 concrete-object LLM judged-modulation study using the v2 polished
> stimuli"* — pinning the exact runtime model identifiers.

**No artifact may change after freeze except via a new versioned study.** EVIDENCE_FREEZE is **not** declared in
this review.

## 11. If blocked — (not the current state)

Would list: missing pinned runtime IDs treated as a hard blocker, or any hash mismatch requiring rebind. Neither
applies: the config sanctions operator ID-pinning at freeze, and hashes are bound to v2.

## 12. Final status block

```
document:                    B1.3 concrete-object JUDGE MODEL LIST & FREEZE REVIEW V2 (after polish; review only)
decision:                    FREEZE_REVIEW_V2_AFTER_POLISH_READY_AWAITING_OPERATOR_CONFIRMATION
active freeze inputs:        v2 polished stimuli + v2 audits (v1 preserved as historical only)
v2 audits:                   all 8 PASS; style-tell 0.532; 0 over-band; garrulous eliminated
judge model config:          constrained family policy (>=2, target 3, cross-vendor recommended); temp 0.0; blinded; forced A/B
judge prompt:                FINAL
hashes bound:                17 active artifacts (manifest self-hash pending at operator freeze)
evidence judge run:          NO
real scoring:                NO
EVIDENCE_FREEZE:             NOT declared (separate operator step required)
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        operator pins runtime model IDs + declares EVIDENCE_FREEZE (v2), then judge run + scoring
```

**Structure, not validated meaning.** The judge model-family policy and run configuration are finalized and the
freeze review is re-run against the v2 polished stimuli with all 17 active artifacts hash-bound; no judge was
run, nothing was scored, prior nulls and closures stand, Track B remains BLOCKED, and EVIDENCE_FREEZE is not
declared — awaiting a separate explicit operator confirmation.
