# Causal and advancement gates

Machine-readable: `experiments/bindingslots_persistence/classifier.json`. All frozen formation and
causal-collapse logic is inherited unchanged from `classify_stage_b.py` (sha256 `3ca1e75f…`).

## CLEAN_STABLE (per seed, at step 1200)

All must hold vs the **same-seed** A+: needle@d96 passes the frozen formation rule; correct-slot
probability ≥ 0.50; correct-slot rank ≤ 5; address margin ≥ 3.0; **slots-off collapses**;
**randomized-addressing collapses**; quality passes; d16 + d220 pass. Same-seed causal threshold:
`post_ablation ≤ max(A+_same_seed + 0.03, 0.05)` — A+ is never a pinned/pooled/assumed value.

## Retention categories

`NEVER_FORMED`, `FORMED_THEN_COLLAPSED`, `FORMED_AND_RETAINED_BUT_CAUSALLY_UNCLEAN`,
`FORMED_AND_CLEAN_BUT_ROUTING_METRICS_DECAYED`, `CLEAN_STABLE`, `QUALITY_FAILED`, `INTEGRITY_FAILED` —
distinguishing **proxy retained** vs **function retained** vs **causal dependence retained**.

## Arm advancement

`clean_stable_count ≥ 4/5` **AND** `> R0 clean_stable_count` **AND** all mandatory quality/integrity
gates pass. Raw 5/5 needle cannot compensate for low prob / poor rank / weak margin / non-collapse /
quality or distance failure. Causal results are **never averaged**; one causally-unclean forming seed
is a failed seed. No candidate is selected on means alone.
