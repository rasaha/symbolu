# B1.1 Sample-Word Render Dry Run (REAL G2P, structural, pre-refreeze)

## Status: `PASS_RENDER_DRY_RUN`

*Re-run with **real G2P** after the Śa de-Sanskritization fix (`artha` removed). This supersedes the prior
illustrative spelling-based dry run, which never routed the affected words to Śa and so missed the leak.*

## Scope and non-claims

Real-G2P structural preview of 8-arm construction for sample words, **before** re-freeze finalization. This
is **NOT** model generation, judging, or scoring, and is **NOT** evidence that B1.1 works or outperforms
B1/H2. No model / embedding / generation / scoring / judging. Does not modify B1, change the verdict
(`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). **Structure, not validated meaning.**

## Inputs & method

- **Word pool:** `COMMITTED_B1_POOL` (`b1_dry_run_harness.py` `PRIMARY_WORDS`); 8 sample words selected
  deterministically (seed 70101): **echo, envy, integrity, justice, music, ocean, shadow, silence**.
- **Arms:** A, D, S, R_same, R_deranged, R_domain, C, X. **Tasks:** T1, T3, T4, T6.
- **A uses REAL G2P->varṇa** (`varna_lens.phonemes_cmudict`), the frozen bridge pool, and the pinned
  composition policy (G1). D/C/X are lexicon-independent controls; R_domain uses the pinned bucket policy (G3).

## Leakage (real-G2P, model-facing)

- **Pool-level Sanskrit-label-token leakage (generic scan, all 68 bridges):** 0 — `NONE`
- **Per-render leakage (8 words × arms):** 0 — `NONE`
- **Śa/`artha` check:** removed from the conditioning path.
- **Weak controls:** 0 — `none`.

## Full prompt example (echo, arm A, T1)

```
Soft orientation, not a definition: forward-orientation held without attachment to the outcome — aspires and acts while releasing the grip on the result. Use this only as a gentle tonal/conceptual guide while following the task exactly.

Task:
Write a short reflective paragraph about echo.
```

## Final status
```
dry_run_status:        PASS_RENDER_DRY_RUN
g2p_mode:              REAL_G2P
generation_run:        NO
B1.1 frozen:           NO (re-freeze pending)
generation_authorized: NO
word_pool:             COMMITTED_B1_POOL (8 sampled, seed 70101)
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
```
`R_deranged` remains the crux. **Structure, not validated meaning.**
