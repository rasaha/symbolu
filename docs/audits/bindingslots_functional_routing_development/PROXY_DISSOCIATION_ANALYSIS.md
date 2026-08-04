# Proxy-dissociation analysis

The confirmatory phase (PR #1324) motivates this development phase. The alignment scaffold maximizes
**aggregate write-read overlap**, but the committed trajectories show overlap dissociates from
functional, causally-address-dependent retrieval. Reproduced mechanically by
`validate_known_signatures.py` (5/0) on the committed CR1 seeds 13–17:

| seed | needle@1200 | correct-slot prob | rank of written slot | address margin | aggregate overlap | outcome |
|---|---|---|---|---|---|---|
| 15 | 1.00 | 0.95 | 0.6 | 10.9 | 0.84 | clean + retained |
| 17 | 1.00 | 0.74 | 4.8 | 9.3 | 0.55 | clean + retained |
| 16 | 1.00 | **0.21** | **14.1** | **0.9** | **0.15** | **impure** (rand-addr 0.45) |
| 13 | **0.00** | 0.88 | 3.1 | 9.9 | 0.70 | **collapsed** |
| 14 | **0.00** | 0.82 | 1.8 | 6.7 | 0.72 | **collapsed** |

## Two distinct dissociations

1. **Purity (seed 16).** Retrieval succeeds (needle 1.0) with *low* correct-slot probability (0.21),
   *poor* written-slot rank (14), and *weak* margin (0.9). The read does not attend to the written
   slot; retrieval survives address randomization (0.45). → an **addressing-specificity** failure that
   **O1/O2 directly target**.

2. **Retention (seeds 13/14).** Endpoint retrieval is 0, yet at step 1200 the *addressing* metrics are
   **clean** (prob 0.82–0.88, rank 1.8–3.1, margin 6.7–9.9) and aggregate overlap is retained
   (~0.70). The circuit still *addresses* the right slot but no longer *retrieves the value*. → the
   collapse is **downstream of addressing** (value-recovery / decoding), **not** a routing failure.

## Prediction for this phase (to be tested, not assumed)

- **O1/O2** (address-specific objectives) should improve **purity** (seed-16-type), because they
  penalize exactly the low prob / poor rank / weak margin signature.
- **O1/O2 are *not* expected to fix seed-13/14-type collapse**, because addressing was already clean
  there — the collapse is a value/decoding retention failure.
- **H3** (gradual handoff) targets the distribution-shift retention failure and is the arm most
  plausibly relevant to 13/14-type collapse in this focused screen. (A functional teacher / residual
  — H2/O1R — is the more direct value-retention lever but is **deferred**.)

This makes the Stage-1 screen genuinely informative: it can dissociate "purity fixed" from "retention
fixed," and the phase is preregistered to report both rather than collapse them into one number.

Mechanistic statements are conservative: single-trajectory reads on 2–5 seeds; treat "collapse is a
value-recovery failure" as a strong hypothesis the Stage-1 value-recovery trajectories will test.
