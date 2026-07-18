# B1.1 Pre-Freeze Adversarial Audit (REAL G2P)

## Status: `PASS_PREFREEZE_AUDIT`

Read-only adversarial audit of the B1.1 artifact set before **re-freeze** finalization, using **real
G2P** routing and a **generic** Sanskrit-source-label leak scan (the prior audit used a hardcoded term
list and missed `artha`). **Audit only** — no artifact modified. No model / embedding / generation /
scoring / judging. Does not modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock
Track B (**BLOCKED**). **Structure, not validated meaning.**

## Check summary
- **1_leakage_generic**: PASS
- **1b_real_g2p_conditioning**: PASS
- **2_forbidden_framing**: PASS
- **3_control_strength**: PASS
- **4_freeze_status**: PASS
- **5_hash_staleness**: PASS
- **6_judge_panel**: PASS
- **7_prereg_consistency**: PASS
- **8_dry_run_realg2p**: PASS

## Blockers (0)
_none_

## Warnings / expected caveats (6)
- expected caveat: embedding gate remains BLOCKED_DEPENDENCY_UNAVAILABLE (owed)
- expected caveat: fallback qualification required (FALLBACK_QUALIFIED)
- expected caveat: local lexical audit is surface-only (not semantic)
- expected caveat: Meta-Llama-3-8B ACCEPT_WITH_CAVEAT
- expected caveat: positive limited to LIMITED_GENERATION_UTILITY; R_deranged is the crux
- expected caveat: 'artha' retained ONLY in non-rendered provenance metadata (sanskrit_label/source_note)

## Detail
- **Leakage (generic, all 68 bridges):** sanskrit-label tokens=0,
  IAST=0, varṇa-names=0,
  arm-labels=0, filled-template-meta=False.
- **Real-G2P conditioning:** render-only `PASS_RENDER_ONLY`, leak_total=0 over
  200 cores.
- **Control strength:** weak controls (real G2P)=none; G3 r_domain policy pinned=b1_1_r_domain_assignments.json (persisted per-word native/mismatched buckets; deterministically reproducible from this frozen policy + frozen seeds + frozen word pool).
- **Freeze status:** gen_authorized true in=none; final manifest exists=False;
  run outputs=none.
- **Hash/staleness:** draft manifest current=True; stale=none.
- **Prereg consistency:** all pass.
- **Dry-run (REAL G2P):** PASS_RENDER_DRY_RUN, leakage clean=True.

## Final status
```
audit_status:          PASS_PREFREEZE_AUDIT
g2p_mode:              REAL_G2P
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
Embedding gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (owed) · FALLBACK_QUALIFIED
Artifacts modified:    NONE
Final manifest:        NOT created (re-freeze finalization is the next step)
B1.1 frozen:           NO
Generation authorized: NO
```
`R_deranged` remains the crux. **Structure, not validated meaning.**
