# §15.14 Implementation §0.X — Authorization Record

## Status

**EFFECTIVE** as of this commit. This document records the §0.8-binding
authorization to write `scripts/probe_framing_15_14.py` per the §15.14
spec Chunk 5 implementation chunk plan.

## Authorization scope

The user (annotator `rasaha-2026-04-30`) explicitly authorized the §15.14
implementation phase after `--strict` validator exit 0 confirmed that all
upstream gates have cleared.

This authorization is the parallel to §15.13's implementation §0.X (commits
`c82c893..3e718fa` on the §15.13 branch). It permits writing the
implementation script and running the experiment on runpod; it does NOT
permit any modification to the spec, the amendment, the calibration labels,
the sealed thresholds, the cascade structure, or any §13/§14/§15.x verdict.

## Pinned SHAs

```
final_stimulus_sha       = e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7
calibration_labels_sha   = e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c
```

These two SHAs are the canonical-form SHA-256 digests of the two locked
input artifacts the implementation script will consume:

- `final_stimulus_sha` → `docs/experiments/sticky_framing_15_14_stimuli.json`
- `calibration_labels_sha` → `docs/experiments/sticky_framing_15_14_calibration_labels.json`

Both values were emitted by `scripts/validate_framing_15_14_stimuli.py`
under `--strict` mode against the labels artifact at
`labels_artifact_commit = 4ba0c27d`.

## Authorization metadata

| Field | Pinned value |
|---|---|
| `final_stimulus_sha` | `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| `calibration_labels_sha` | `e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c` |
| Annotator ID | `rasaha-2026-04-30` |
| Labels artifact commit | `4ba0c27d` on `claude/sticky-framing-spec-r6U1j` |
| §15.14 spec source | `docs/design/15_14_STICKY_FRAMING_DESIGN_SPEC.md` (current branch state) |
| §15.14-A1 amendment | EFFECTIVE (per spec amendment block, sign-off recorded in commit `8ba407f`) |
| Implementation script path | `scripts/probe_framing_15_14.py` |

## Sealed §0.8 thresholds — preserved unchanged

Confirmed in the authorization request and verified against the spec's
Sealed §0.8-binding decisions table (Chunk 6) plus the §15.14-A1
amendment block:

- **Severity rubric (3-level):** 0 = IGNORED / 1 = MENTIONED / 2 = STRUCTURED — unchanged.
- **`BINARY_LABEL_THRESHOLD`:** `y = 1 iff severity ≥ 1` — unchanged.
- **`KAPPA_GATE_THRESHOLD`:** 0.6 (inclusive) — unchanged.
- **`DIRECTION_GATE_THRESHOLD`:** 0.5 (strict) — unchanged.
- **`PARTIAL_AUC_THRESHOLD`:** 0.66 (inclusive) — unchanged.
- **`STRONG_AUC_THRESHOLD`:** 0.75 (inclusive) — unchanged.
- **`STRONG_DELTA_AUC_THRESHOLD`:** 0.05 (inclusive, vs chance, vs R_topic_to_framing, vs R_recency) — unchanged.
- **Cascade structure:** 4-step (direction gate → STRONG → PARTIAL → default NO_MATERIAL), 2-comparator strict-margin requirement — unchanged.
- **Class-3 firewall:** 52 patterns (44 inherited + 8 §15.14-specific) — unchanged.
- **Source enum scoping (per §15.14-A1):**
  - `main_chains` source enum: `{"truthfulqa_mc", "humaneval"}` — unchanged.
  - `calibration_chains` source enum: `{"truthfulqa_mc", "humaneval"}` — unchanged.
  - `frame_positive_chains` source enum: `{"truthfulqa_mc", "humaneval", "synthetic_frame_positive_v1"}` — effective under §15.14-A1.

## Implementation chunk plan (per §15.14 spec Chunk 5)

| Chunk | Content | Approx. size |
|---|---|---|
| **I-1** | Module docstring (embedded §0.8 declaration), pinned constants block, frozen judge prompt as a frozen string constant, 9 dataclasses (`FramingPoolItem`, `ChainQuestion`, `StimulusChain`, `ChainExtraction`, `EvaluationRow`, `FramingFeatures`, `FramingProbeResult`, `FramingCascadeVerdict`, `FramingAuditOutputs`), 12 self-test cascade boundary cases. | ~450 lines |
| **I-2** | `SchemaMismatchError`, stimulus JSON validator + topical-disjointness re-check, HF dataset loaders, Pass A iterative K-turn extraction (`s_t`, `f_1`, `a_prev`), Pass B standalone extraction (`q_t`), `.npz` cache I/O. | ~500 lines |
| **I-3** | Judge loader (Qwen-72B with Qwen-7B fallback), Pass C severity protocol with retry/JSON-parse handling, Pass D κ ≥ 0.6 gate, feature computation (R_framing, R_topic_to_framing, R_recency), cascade classifier, selective-prediction κ@α (disclosure-only). | ~450 lines |
| **I-4a** | `scan_for_forbidden_patterns` (case-insensitive non-§; literal §-anchored), `enforce_firewall_or_exit` (exits 4 with diagnostic). | ~60 lines |
| **I-4b** | Self-test gate: `_self_test_cascade` (12 cases), `_self_test_cosine_invariants`, `_self_test_firewall` (52-pattern coverage + clean negative), `_self_test_topical_disjointness`. | ~200 lines |
| **I-4c** | JSON output writer with full `schema_version "15.14"` payload (alphabetical `sort_keys=True`). | ~150 lines |
| **I-4d** | Markdown rendering (8 sections per spec), firewall-scanned writer. | ~300 lines |
| **I-5** | CLI: `--self-test` / `--collect` / `--annotate` / `--probe` / default; `main(argv)` orchestration. | ~300 lines |

**Total:** ~2410 lines across 8 implementation commits.

## Exit codes (per spec Chunk 5, pinned)

```
0  success
2  CLI / argument error (handled by argparse)
3  SELF_TEST_FAILED
4  INTERPRETATION_VIOLATION
5  SCHEMA_MISMATCH (stimulus JSON, labels JSON, or cache)
6  EXTRACTION_FAILED (torch / transformers stack)
7  PROBE_FAILED (sklearn / NaN in features)
8  STIMULUS_INVALID (topical-disjointness violated, framing span out of range, source enum violated)
9  ANNOTATION_FAILED (judge κ < 0.6 OR judge JSON-parse failure rate > 5%)
```

## CLI surface (per spec Chunk 5, pinned)

```
--self-test            run gate only (12 cascade + cosine invariants + 52-pattern firewall + disjointness)
--collect              load stimulus JSON + labels JSON; run Pass A (multi-turn) + Pass B (standalone) for all chains; write extraction cache
--annotate             load extraction cache + run Pass C (LLM-judge severity) + Pass D (κ self-test gate); write annotated cache
--probe                load annotated cache + compute features + cascade + write JSON+MD outputs
(default)              self-test → collect → annotate → probe → write
--stimulus-json        override default stimulus-JSON path
--labels-json          override default labels-JSON path
--cache-path           override default extraction cache path
--annotated-cache-path override default annotated cache path
--json-out             override default JSON output path
--md-out               override default markdown output path
--force-collect        force re-collection even if cache exists
--force-annotate       force re-annotation even if annotated cache exists
--judge-fallback       explicitly force the Qwen-7B fallback judge
```

## What this authorization explicitly does NOT permit

Per the user's authorization message:

- Does NOT alter the spec (`docs/design/15_14_STICKY_FRAMING_DESIGN_SPEC.md`).
- Does NOT alter §15.14-A1 (the source-enum amendment).
- Does NOT alter the calibration labels artifact.
- Does NOT alter any sealed §0.8 threshold.
- Does NOT alter the severity rubric.
- Does NOT alter `BINARY_LABEL_THRESHOLD`.
- Does NOT alter `KAPPA_GATE_THRESHOLD`.
- Does NOT alter `DIRECTION_GATE_THRESHOLD`.
- Does NOT alter `PARTIAL_AUC_THRESHOLD` or `STRONG_AUC_THRESHOLD`.
- Does NOT alter cascade structure or comparator margins.
- Does NOT alter any §13/§14/§15.x verdict-of-record.
- Does NOT add post-hoc sign-flip rescue.
- Does NOT anticipate or interpret the verdict before the full run.

## Branch state at authorization

```
READY_FOR_IMPLEMENTATION_§0.X_AUTHORIZATION
            ↓ (this commit)
IMPLEMENTATION_§0.X_AUTHORIZED → IMPLEMENTATION_IN_PROGRESS_I-1
```

## Provenance

- Spec sealed at `docs/design/15_14_STICKY_FRAMING_DESIGN_SPEC.md` (most recent EFFECTIVE-flip commit `8ba407f`).
- Stimulus JSON + amendment + frame-positive curation: see C-1..C-7 commits + `8ba407f` (EFFECTIVE).
- Labels artifact split + validator infrastructure: C-8a..C-8e (commits `1322bab`..`b3e848a`).
- Calibration response collection script (`scripts/collect_calibration_responses_15_14.py`): commits `2ca7896` + `d72f299` (fix).
- Calibration responses artifact: commit `fd610995` (Qwen-7B inference run on runpod, runpod_id `47fe791df9a7`).
- Annotation infrastructure (review markdown, JSON template, interactive CLI): commits `110da66`, `dbd1e60`, `c51743b`.
- Calibration labels artifact (50/50 human-annotated by `rasaha-2026-04-30`): commit `4ba0c27d`.
- Validator `--strict` exit 0 confirmation: emitted SHAs above.

## Next chunk

Implementation chunk **I-1** lands as the next commit on this branch.
