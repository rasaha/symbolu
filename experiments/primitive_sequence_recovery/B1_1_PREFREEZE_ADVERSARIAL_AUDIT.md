# B1.1 Pre-Freeze Adversarial Audit

## Status: `PASS_PREFREEZE_AUDIT`

Read-only adversarial audit of the B1.1 artifact set before final freeze. **Audit only** — no artifact
modified. No model / embedding / generation / scoring / judging. Does not modify B1, change the verdict
(`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology / Sanskrit privilege /
semantic-truth claim. **Structure, not validated meaning.**

## Check summary
- **1_leakage**: PASS
- **2_forbidden_framing**: PASS
- **3_control_strength**: PASS
- **4_freeze_status**: PASS
- **5_hash_staleness**: PASS
- **6_judge_panel**: PASS
- **7_prereg_consistency**: PASS
- **8_dry_run_consistency**: PASS

## Blockers (0)
_none_

## Warnings / expected caveats (5)
- expected caveat: embedding gate remains BLOCKED_DEPENDENCY_UNAVAILABLE (owed)
- expected caveat: fallback qualification required (FALLBACK_QUALIFIED)
- expected caveat: local lexical audit is surface-only (not semantic)
- expected caveat: Meta-Llama-3-8B ACCEPT_WITH_CAVEAT
- expected caveat: positive limited to LIMITED_GENERATION_UTILITY; R_deranged is the crux

## Detail
- **Leakage (model-facing):** proper Sanskrit nouns=0, IAST=0, meta-terms=0, arm-labels=0, filled-template meta=False.
- **Forbidden framing / claims:** framing hits=0; un-negated claim lines=0 (claim terms in prereg/configs are all negated: "cannot prove", "no …", "not …").
- **Control strength:** arm rules present=['no_target_self', 'same_pool', 'deranged_real_mapping_from_other_word', 'domain_mismatch', 'style_length_normalization']; weak controls=none; R_domain policy present=True.
- **Freeze status:** generation_authorized true in=none; final manifest exists=False; run outputs=none.
- **Hash/staleness:** draft manifest current=True; stale=none.
- **Judge panel:** Meta-Llama-3-8B=WARNING_ACCEPTANCE_REQUIRED; ACCEPT_WITH_CAVEAT recorded in manifest; strict parser + replacement policy + no post-hoc selection.
- **Prereg consistency:** all pass.
- **Dry-run:** PASS_RENDER_DRY_RUN, generation_run=False, leakage clean=True.

## Final status
```
audit_status:          PASS_PREFREEZE_AUDIT
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
Embedding gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (owed) · FALLBACK_QUALIFIED
Artifacts modified:    NONE
Final manifest:        NOT created
B1.1 frozen:           NO
Generation authorized: NO
```
`R_deranged` remains the crux. **Structure, not validated meaning.**
