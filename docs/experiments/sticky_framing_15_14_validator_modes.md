# §15.14 stimulus validator — mode matrix

`scripts/validate_framing_15_14_stimuli.py` exposes five validation
modes covering the curation lifecycle from incremental development
through final implementation-§0.X gating. This document records the
expected exit code and behavior of each mode at the post-C-8 state
on branch `claude/sticky-framing-spec-r6U1j`.

The post-C-8 state is:

- frame_positive_chains: 20/20 hand-authored, status FINAL,
  source `synthetic_frame_positive_v1` (effective under §15.14-A1).
- calibration_chains: 10 chains × 5 turns = 50 rows, structure only,
  labels live in the separate artifact at
  `docs/experiments/sticky_framing_15_14_calibration_labels.json`
  which is currently an `EMPTY_STUB` with 0 labels filled.
- Sealed §0.8 thresholds (BINARY_LABEL_THRESHOLD,
  KAPPA_GATE_THRESHOLD, DIRECTION_GATE_THRESHOLD,
  PARTIAL_AUC_THRESHOLD, STRONG_AUC_THRESHOLD) unchanged.

## Mode matrix

| # | Invocation | Exit | Diagnostic |
|---|---|---|---|
| 1 | `validate ... ` (default) | 0 | STRUCTURAL OK; PRE-LOCK. Reports stimulus SHA. |
| 2 | `validate ... --require-frame-positive-final` | 0 | STRUCTURAL OK; PRE-LOCK. FP=FINAL satisfied. |
| 3 | `validate ... --require-calibration-labels` | 8 | `--require-calibration-labels was specified without --calibration-labels-json. Labels live in the separate artifact at docs/experiments/sticky_framing_15_14_calibration_labels.json and must be supplied to be merged at validation time.` |
| 4 | `validate ... --require-calibration-labels --calibration-labels-json <incomplete file with 3 labels>` | 8 | `calibration labels: only 3/50 filled in the supplied artifact and --require-calibration-labels was specified` |
| 5 | `validate ... --strict --calibration-labels-json <empty stub>` | 8 | `calibration labels: only 0/50 filled in the supplied artifact and --require-calibration-labels was specified` |

## Implementation §0.X gating

The implementation §0.X for §15.14 (`scripts/probe_framing_15_14.py`,
not yet authorized) must run mode 5 (`--strict`) and require exit 0
before proceeding to `--collect / --annotate / --probe`. Mode 5
becomes exit 0 only when:

- Frame-positive curation is FINAL (already true post-C-7e).
- The labels artifact has all 50 calibration severity labels filled,
  validated per row, and pinned to the current stimulus SHA via the
  artifact's `stimulus_sha256` field (still PENDING — requires the
  human-annotation pass per `_annotation_procedure` in the stimulus
  JSON).

When mode 5 succeeds, the validator emits two pinnable SHAs:

```
final_stimulus_sha       = <stimulus canonical SHA>
calibration_labels_sha   = <labels canonical SHA>
```

Both must be recorded in the implementation §0.X commit metadata
alongside the §15.14 spec amendment §15.14-A1 EFFECTIVE reference.

## Reference: historical SHAs

| Milestone | Stimulus SHA |
|---|---|
| post-C-6 (structural curation; FP placeholder; cal labels in-JSON) | `3e00a9a21e8c28cc5faf0327dd246ea8a0811209456be9229dc773ce765e049c` |
| post-C-7e (FP FINAL via synthetic_frame_positive_v1; cal labels in-JSON nulls) | `fd71242b84c575a089c3ab0594641d6e342480be06bd274cb1c1089f40b411ac` |
| post-C-8a (labels split out of stimulus JSON) | `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| post-C-8 (current; same canonical content as post-C-8a; FP=FINAL; cal=PENDING) | `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| FINAL (mode 5 = exit 0) | computed live by validator; pinned in implementation §0.X |

The `_post_c8_pre_calibration_sha` is `e56cfe8c…`. The
`_final_stimulus_sha` field in the stimulus JSON is `null` until
`--strict` passes.
