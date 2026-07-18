# B1.3 Concrete-Object LLM Judged-Modulation — Global Register-Polish

## 1. Scope and status

Pre-freeze stimulus polish only. **No evidence judge run · no scoring · no EVIDENCE_FREEZE · no positive label
earned · prior results unchanged.** Applies **one global reducer/fallback rule** so fallback tags obey the same
short plain-English register constraints as normal extraction, regenerates all stimuli (**v2**, versioned), and
reruns all audits plus three added scans. **Structure, not validated meaning.**

## 2. The issue (from the single-example walkthrough)

The `knife` walkthrough exposed `garrulous` (9 chars) in the mid-deranged option. Root cause: `tower`'s only
consonant varṇa `tta` has the gloss *"garrulous exaggeration beyond the warranted"*, which contains **no**
in-band (4–8 char) content word (garrulous 9, exaggeration 12, *beyond* is a banned function word, warranted 9).
The v1 reducer's last-resort fallback `return cand[0]` then emitted the **out-of-band** token `garrulous`. This
is a **global rule gap**, not a per-item defect.

## 3. The global rule change

The reducer now returns **only** an in-band (4–8) plain-English token **or `None`** — the **same rule in normal
extraction and in fallback**:

- prefer 4–6 char content words, else any 4–8 char token;
- **no** out-of-band fallback — when a gloss has no in-band content word, return `None`;
- `None` → the caller **backfills from the all-in-band global tag pool** (deterministic, seeded);
- ban Sanskrit/source-marker terms · ban target/synonym leakage · dedupe within option;
- applied **uniformly** to `A_real`, deranged (near/mid/far), scrambled, random, neutral, and the semantic
  baseline;
- **no per-item hand tuning.**

Because the deranged arms reuse a source word's `A_real`, fixing `A_real` propagates the fix to every arm.

## 4. Versioned artifacts (v1 preserved)

New v2 artifacts created; v1 kept as the previous draft:

- `b1_3_concrete_object_final_stimuli_draft_v2.jsonl` (sha256 `20f1ab61…04e9`)
- `b1_3_concrete_object_style_audit_report_v2.json` (sha256 `f2766631…f273a`)
- `b1_3_concrete_object_style_audit_report_v2.md`
- `b1_3_concrete_object_stimulus_generation_manifest_v2.json`

## 5. Regeneration

**371 records** = 53 primary objects × 7 comparisons, regenerated deterministically under seed
`b1_3_concrete_object_stimgen_v2`.

## 6. Audit results (all PASS)

| Audit | v2 result |
|---|---|
| Style-parity | PASS (mean \|char-len diff\| 1.87) |
| Style-tell | PASS (balanced accuracy 0.532 ≤ 0.55) |
| Denotation-leakage | PASS (0 repeats, 0 synonym leaks) |
| Quality-parity | PASS (0 empty/garbage/dup/Sanskrit) |
| Semantic-baseline | PASS (all 53; no varṇa; separated) |
| **Forbidden-token scan** | PASS (**0 Sanskrit, 0 over-band**) |
| **Duplicate-tag scan** | PASS (0 options with duplicates) |
| **Tag-length parity by arm** | PASS (per-arm mean spread 0.557 chars) |

## 7. `garrulous` and similar outliers — removed

Independent scan of the v2 JSONL: **0 over-band tokens across all 742 options; 0 occurrences of `garrulous`.**
`tower`'s A_real is now `['truth', 'giving', 'malice', 'spell']` (all in-band), so the `knife` mid-deranged
option no longer contains `garrulous`. Per-arm mean tag length now spans only 5.19–5.75 (max−min 0.557).

## 8. Impact on the freeze review

The freeze review previously hash-bound the **v1** stimuli + audit report. It must now bind the **v2** stimuli
(`20f1ab61…04e9`) and v2 audit report (`f2766631…f273a`) instead. This does **not** clear the other open freeze
blockers (final judge model list; re-review; operator EVIDENCE_FREEZE). The freeze review is **not** re-run here
(the task said not to proceed to freeze review yet).

## 9. Decision

```
DECISION: GLOBAL_REGISTER_POLISH_PASS_READY_FOR_FREEZE_REVIEW
```

The single global reducer/fallback rule change removed the over-band escape; all eight audits pass; v1 is
preserved. This is not `GLOBAL_REGISTER_POLISH_FAIL_NEEDS_REVISION` (all gates pass) and not
`GLOBAL_REGISTER_POLISH_NOT_FEASIBLE_CLOSE_LINE` (the fix is a clean global rule).

## 10. Final status block

```
document:                    B1.3 concrete-object GLOBAL REGISTER-POLISH (pre-freeze stimulus polish)
decision:                    GLOBAL_REGISTER_POLISH_PASS_READY_FOR_FREEZE_REVIEW
rule changed:                reducer returns in-band (4..8) token or None; NO out-of-band fallback; backfill from in-band pool
scope:                       global, uniform across all arms; no per-item hand tuning
garrulous / over-band:       ELIMINATED (0 over-band tokens, 0 garrulous across 742 options)
regenerated stimuli:         371 (v2); v1 preserved as previous draft
audits:                      style-parity / style-tell 0.532 / leakage / quality / semantic-baseline /
                             forbidden-token / duplicate / tag-length-parity — ALL PASS
ran LLM judges / scoring:     NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        re-bind v2 hashes, finalize judge model list, then freeze review (not yet)
```

**Structure, not validated meaning.** One global reducer/fallback rule now enforces the in-band register in both
normal extraction and fallback; the `garrulous` class is eliminated, all audits pass on the regenerated v2
stimuli, v1 is preserved, no judge was run, nothing was scored, prior nulls and closures stand, Track B remains
BLOCKED, and EVIDENCE_FREEZE is not declared.
