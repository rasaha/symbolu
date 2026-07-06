# B1.3 Concrete-Object Stimuli (v2) — Pre-Judge Audit Report after Global Register-Polish

**Status:** AUDIT_COMPLETE_PRE_FREEZE · **version:** 2 · **generation seed:** `b1_3_concrete_object_stimgen_v2` ·
**evidence judge run:** NO · **scoring:** NO · **EVIDENCE_FREEZE:** NOT declared. Supersedes the v1 stimuli
(preserved). **Structure, not validated meaning.**

## Global register-polish applied

The gloss reducer now returns **only** an in-band (4–8 char) plain-English token **or `None`** — the **same
rule for normal extraction and fallback**. There is **no** out-of-band fallback: when a gloss has no in-band
content word, the reducer returns `None` and the caller backfills from the **all-in-band global tag pool**.
Applied **uniformly** to A_real, deranged (near/mid/far), scrambled, random, neutral, and the semantic
baseline. This is a single global rule change — **no per-item hand tuning**. It eliminates `garrulous` (from
`tower`'s gloss "garrulous exaggeration beyond the warranted", which had no in-band token) and any other
over-band fallback.

## Audit results (all PASS)

| Audit | Result | Key metric |
|---|---|---|
| **Style-parity** | PASS | all options 4 tags; mean \|char-len diff\| = 1.87 |
| **Style-tell** | PASS | balanced accuracy **0.532 ≤ 0.55** |
| **Denotation-leakage** | PASS | 0 target repeats; 0 synonym leaks |
| **Quality-parity** | PASS | 0 empty/garbage/dup/Sanskrit |
| **Semantic-baseline** | PASS | present for all 53; same format; no varṇa; separated from X_neutral |
| **Forbidden-token scan** | PASS | **0 Sanskrit tokens; 0 over-band tokens** (garrulous class eliminated) |
| **Duplicate-tag scan** | PASS | 0 options with duplicate tags |
| **Tag-length parity by arm** | PASS | per-arm mean tag length spread (max−min) = **0.557** chars |

## Per-arm mean tag length

`A_real` 5.29 · `R_deranged_mid` 5.37 · `R_deranged_far` 5.19 · `R_deranged_near` 5.29 · `R_scrambled` 5.29 ·
`R_random` 5.37 · `X_neutral` 5.75 · `semantic_only_baseline` 5.64. All within 0.56 chars — no arm reads
systematically longer/richer.

## garrulous verification

Independent scan of the v2 JSONL: **0 over-band tokens across all 742 options; 0 occurrences of `garrulous`.**
`tower`'s A_real is now `['truth', 'giving', 'malice', 'spell']` (all in-band), so `knife`'s mid-deranged option
no longer contains `garrulous`.

## Decision

```
DECISION: GLOBAL_REGISTER_POLISH_PASS_READY_FOR_FREEZE_REVIEW
```

The single global reducer/fallback rule change removed the over-band escape and all eight audits pass. **No
evidence judge run · no scoring · no EVIDENCE_FREEZE.** v1 artifacts preserved as the previous draft.
