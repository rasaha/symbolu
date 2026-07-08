# B1.3 Concrete-Object Stimuli — Pre-Judge Style/Denotation/Quality Audit Report

**Status:** AUDIT_COMPLETE_PRE_FREEZE · **evidence judge run:** NO · **scoring:** NO · **EVIDENCE_FREEZE:**
NOT declared · **generation seed:** `b1_3_concrete_object_stimgen_v1`. **Structure, not validated meaning.**

These are **mechanical** audits (format/lexical), not the evidence judge task (which judges object-function
fit). No positive label is earned. Prior results unchanged.

## Stimuli generated

- **371 draft comparison records** = **53 primary concrete objects × 7 required comparisons**.
- Fixed 4-tag template, identical across all arms; deterministic, sha256-seeded; no per-item hand-polishing.
- Comparisons: A_real vs **R_deranged_mid / R_deranged_far / R_deranged_near / R_scrambled / R_random /
  X_neutral / semantic_only_baseline**.

## Audit results (all PASS)

| Audit | Result | Key metric |
|---|---|---|
| **Style-parity** | PASS | all options 4 tags (742/742); mean \|char-len diff\| = 2.11; mean \|tag-len diff\| = 0.53; identical template |
| **Style-tell** | PASS | balanced accuracy **0.378 ≤ 0.55** (A_real not identifiable from format features) |
| **Denotation-leakage** | PASS | 0 options repeat the target word; 0 options use a WordNet synonym of the target |
| **Quality-parity** | PASS | 0 empty/garbage tags; 0 within-option duplicates; 0 Sanskrit/varṇa tokens |
| **Semantic-baseline** | PASS | present for all 53; same 4-tag format; no varṇa input; separated from X_neutral; not used as A_real/control |
| **Near/mid/far map sanity** | MAP ACCEPTED | 0 obvious mislabels; 0 replacements; family separation 53/53 |

## Style-tell detail

Method: mechanical leave-one-out nearest-centroid on **format features only** (`char_len`, `mean_tag_len`) —
**not** content or fit — evaluated over **distinct** rendered options (each A_real option is identical across a
word's 7 comparisons; counting it 7× would bias the centroid). Balanced accuracy **0.378** (tpr 0.308, tnr
0.448), well under the 0.55 draft threshold: A_real cannot be picked out by surface style.

## Global revisions applied to reach parity (no per-item rescue)

All fixes are **global template-level rules** applied uniformly to every arm; no per-item hand-tuning:

1. **Anti-leak rule** — a tag may not equal the target or any WordNet synonym of it (fixed the only 2 initial
   leaks: branch→limb, rock→stone in the semantic baseline).
2. **No-Sanskrit rule** — banned Sanskrit/varṇa tokens (e.g. *rajasic*, *sattvic*) skipped in gloss reduction.
3. **Within-option dedupe** — each arm's 4 tags are distinct.
4. **Shared-register normalization** — gloss reduction and dictionary/neutral extraction prefer short plain
   tokens (4–6 chars, hyphen-split), converging every arm to one register (per-arm mean tag length 5.29–5.75)
   so no arm reads systematically longer/richer.
5. **Content-word preference** — function/deictic tokens skipped so tags are contentful.

## Near/mid/far map sanity pass (non-outcome)

Non-outcome pass over the frozen deranged source map — **no** inspection of generated tags or expected judge
outcomes. Family separation is perfect (near same-family 53/53; mid & far different-family 53/53); aggregate
similarity gradient monotone (near 0.597 > mid 0.510 > far 0.362; mid ≥ far 53/53). **0 obvious mislabels, 0
replacements.** Documented caveat: 13/53 targets have a same-family near source with lower Wu-Palmer than the
cross-family mid (near is defined by same-family membership — the hard specificity criterion — not raw WuP).
Result: **MAP_ACCEPTED_NO_REPLACEMENTS.**

## Decision

```
DECISION: STIMULI_AND_STYLE_AUDIT_PASS_READY_FOR_FREEZE_REVIEW
```

All draft stimuli generated and all pre-judge audits pass. **No evidence judge run · no scoring · no
EVIDENCE_FREEZE · no positive label earned.** Next gate: `B1_3_CONCRETE_OBJECT_LLM_EVIDENCE_FREEZE_REVIEW`.
