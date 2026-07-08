# B1.3 Concrete-Object LLM Judged-Modulation — Final Stimulus Generation & Style Audit

## 1. Scope and status

Final **draft** stimulus generation + pre-judge audits only. **No evidence judge run · no scoring · no
EVIDENCE_FREEZE · no positive label earned · prior results unchanged.** The evidence judge task
(object-function fit) is **not** run here; the style-tell audit is a **mechanical format classifier**, which is
the required pre-judge gate. **Structure, not validated meaning.**

## 2. Inputs used

Final primary wordlist (`b1_3_concrete_object_final_primary_wordlist.json`, 53 targets) · near/mid/far deranged
source map (`b1_3_concrete_object_deranged_source_map.json`) · generation template spec · arm-construction
spec · semantic-baseline spec · scoring/freeze manifest V2 · frozen bridge pool
(`b1_2_varna_bridge_pool.json`) as varṇa-tag source · varṇa pipeline (`varna_lens` G2P→varṇa +
`ArmBuilder`) · WordNet (semantic baseline + synonym leak filter) · deterministic seed
`b1_3_concrete_object_stimgen_v1` (sha256, no random).

## 3. Stimulus generation method

Generated **371 records** = **53 targets × 7 required comparisons**: A_real vs R_deranged_mid /
R_deranged_far / R_deranged_near / R_scrambled / R_random / X_neutral / semantic_only_baseline. Each record
carries `item_id` · `target_word` · `primary_or_secondary_or_diagnostic` · `object_family` ·
`dictionary_anchor` · `neutral_context` · `comparison_id` · `arm_left` · `arm_right` · `option_left` ·
`option_right` · `deranged_stratum` · `position_seed` · `generation_seed` · `source_metadata`. Field tags are
derived deterministically from varṇa pole glosses (A_real/deranged/scrambled/random), the frozen tag pool
(random), fixed fillers (X_neutral), or the dictionary anchor/WordNet (semantic baseline) — **no per-item
hand-polishing**.

## 4. Rendering constraints (verified)

Exact 4-tag template `"Within the fixed meaning, this object is modulated by {t1}, {t2}, {t3}, and {t4}."` ·
four tags per option (742/742) · tags short single tokens · identical syntax/punctuation · no visible arm
labels · **no Sanskrit/varṇa terminology** · **no target-word repetition** · **no dictionary-definition
restatement** · **no per-item hand-polishing.** Global normalization rules (anti-leak, no-Sanskrit, dedupe,
shared-register, content-word preference) were applied **uniformly to every arm**, never per item.

## 5. Style-parity audit — PASS

All options 4 tags; **mean |char-length diff| = 2.11** (max 10); mean |tag-length diff| = 0.53; identical
template/syntax; per-arm mean tag length converged to **5.29–5.75** (no arm reads systematically longer/richer).

## 6. Style-tell audit — PASS

Mechanical leave-one-out nearest-centroid on **format features only** (`char_len`, `mean_tag_len`; not
content/fit), over **distinct** rendered options. **Balanced accuracy 0.378 ≤ 0.55** (tpr 0.308, tnr 0.448):
A_real cannot be identified by surface style. (An earlier draft hit 0.57 when the varṇa arms read longer than
the dictionary/neutral arms; fixed **globally** by converging all arms to a short shared register — no per-item
rescue.)

## 7. Denotation-leakage audit — PASS

0 options repeat the target word; 0 options use a WordNet synonym of the target. (The only two initial leaks —
branch→limb, rock→stone in the semantic baseline — were removed by a **global** anti-leak rule filtering any
target-synonym tag from every arm.)

## 8. Quality-parity audit — PASS

0 empty/garbage tags; **0 within-option duplicates**; **0 Sanskrit/varṇa tokens**; all render OK; controls are
plausible (no nonsense/degraded arms); no A_real fluency advantage; semantic baseline uses the identical
4-tag format.

## 9. Semantic-baseline audit — PASS

Present for all 53 primary items; same 4-tag format; **no varṇa input** (dictionary anchor + WordNet only);
**clearly separated from X_neutral** (dictionary-derived content vs content-free filler); **not** used as
A_real or any control arm.

## 10. Near/mid/far map sanity pass — MAP ACCEPTED

Non-outcome pass over the frozen deranged map; **no** inspection of generated tags or expected judge outcomes.
Family separation perfect (near same-family 53/53; mid & far different-family 53/53); aggregate gradient
monotone (near 0.597 > mid 0.510 > far 0.362; mid ≥ far 53/53). **0 obvious mislabels, 0 replacements.**
Documented caveat: 13/53 targets have a same-family near source with lower Wu-Palmer than the cross-family mid
(near is defined by same-family membership — the hard specificity criterion — not raw WuP). Result:
**MAP_ACCEPTED_NO_REPLACEMENTS.**

## 11. Audit decision

```
DECISION: STIMULI_AND_STYLE_AUDIT_PASS_READY_FOR_FREEZE_REVIEW
```

All 371 draft stimuli generated and **all five audits + the map sanity pass PASS**. This is not
`STIMULI_STYLE_AUDIT_FAIL_NEEDS_GLOBAL_REVISION` (all gates pass after the global fixes) and not
`STIMULI_GENERATION_NOT_VALID_CLOSE_LINE` (generation is deterministic and valid).

## 12. If audit passes — next gate

`B1_3_CONCRETE_OBJECT_LLM_EVIDENCE_FREEZE_REVIEW` (bind final stimuli + all artifacts, finalize judge model
list, scoring script, and thresholds, then the explicit EVIDENCE_FREEZE decision before any evidence judge run).

## 13. If audit fails — protocol (not triggered)

Only **global template-level** revision is allowed; **no per-item hand rescue**; regenerate all affected
stimuli; rerun audits. (This path was exercised three times during this step — anti-leak, no-Sanskrit/dedupe,
and shared-register normalization — each a global fix followed by a full re-audit, until all gates passed.)

## 14. Final status block

```
document:                    B1.3 concrete-object FINAL STIMULUS GENERATION & STYLE AUDIT (pre-freeze prep)
decision:                    STIMULI_AND_STYLE_AUDIT_PASS_READY_FOR_FREEZE_REVIEW
draft stimuli generated:     YES — 371 records (53 targets × 7 comparisons), deterministic, seeded
style-parity:                PASS (mean |char-len diff| 2.11; all 4 tags)
style-tell:                  PASS (balanced accuracy 0.378 ≤ 0.55; format features only)
denotation-leakage:          PASS (0 target repeats; 0 synonym leaks)
quality-parity:              PASS (0 empty/garbage/dup/Sanskrit)
semantic-baseline:           PASS (all 53; no varṇa; separated from X_neutral)
near/mid/far map sanity:     MAP_ACCEPTED_NO_REPLACEMENTS
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
next gate:                    B1_3_CONCRETE_OBJECT_LLM_EVIDENCE_FREEZE_REVIEW
```

**Structure, not validated meaning.** 371 draft stimuli were generated deterministically and passed all
pre-judge style/denotation/quality audits and the map sanity pass; no evidence judge was run, nothing was
scored, prior nulls and closures stand, Track B remains BLOCKED, and EVIDENCE_FREEZE is not declared.
