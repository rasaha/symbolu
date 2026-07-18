# B1.3 Concrete-Object Stimuli (v3-authoritative) — Pre-Judge Audit Report

**Status:** AUDIT_COMPLETE_PRE_FREEZE · **version:** 3 (authoritative-sourced) · **generation seed:**
`b1_3_concrete_object_stimgen_v3_authoritative` · **evidence judge run:** NO · **scoring:** NO ·
**EVIDENCE_FREEZE:** NOT declared. Built on the **authoritative** varṇa lexicon (via
`b1_3_authoritative_varna_bridge_pool.json`); v2 preserved. **Structure, not validated meaning.**

## Source

`b1_3_authoritative_varna_bridge_pool.json` ← `varna_lens/lexicon_authoritative_varna.json` (AUTHORITATIVE,
*Sanskrit_letters_full.docx*). Pole direction preserved by construction (binding_state→binding_bridge,
liberating_state→liberating_bridge); local rewrite = Sanskrit-label parentheticals stripped only.

## Mechanical audits (all PASS)

| Audit | Result | Metric |
|---|---|---|
| Style-parity | PASS | all options 4 tags; mean \|char-len diff\| 2.58 |
| Style-tell | PASS | balanced accuracy **0.529 ≤ 0.55** |
| Denotation-leakage | PASS | 0 target repeats; 0 synonym leaks |
| Quality-parity | PASS | 0 empty/garbage/dup/Sanskrit |
| Semantic-baseline | PASS | present for all 53; same format; no varṇa; separated from X_neutral |
| Forbidden-token scan | PASS | 0 Sanskrit, 0 over-band tokens |
| Duplicate-tag scan | PASS | 0 options with duplicates |
| Tag-length parity by arm | PASS | per-arm mean spread 0.637 |

## Source/provenance audit (all PASS)

34 keys covered · 0 pole flips (provenance intact) · all 53 objects route through authoritative entries ·
controls present per object · no leakage · no arm-label exposure in options · judge-facing vs answer fields
separable (blinding supported) · **no four-sphere integration** · 371 records = 53 × 7.

## Effect of the source correction (illustrative)

Authoritative glosses now drive the tags — e.g. `knife` A_real = `envy, fear, others, release`
(nna=Envy, pha=Fear) vs v2's `sting, flight, spell, stands`; drifted varṇas corrected (`sa`→escapist-withdrawal,
`va`→dharma/sustaining-order, `ha`→darkness). Tags changed; the **design, controls, and audit outcomes did
not**.

## Decision

```
DECISION: V3_AUTHORITATIVE_AUDIT_PASS
```

All mechanical audits and the source/provenance audit pass on the authoritative-sourced v3 stimuli; v2 preserved;
no model call; no scoring; no EVIDENCE_FREEZE.
