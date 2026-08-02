# Code Governance MVP 1F — Implementation

> **Read-only, non-enforcing, execution disabled.** MVP 1F is primarily an
> *operational validation* phase. It adds the product-owned tooling to run the MVP
> 1E pilot operator against a tightly bounded environment, collect honest reviewer
> feedback, measure whether Ugence catches governance conditions beyond ordinary CI,
> analyze policy/source problems, and produce an **evidence-based enforcement-
> readiness verdict** — without changing what the product may do.
>
> There is still no GitHub write path, no `reserve_once`, no consumption ledger, no
> execution provider, no `ProviderKind`, and no external database.
> `execution_status()` returns `DISABLED` in every mode.

## The validation pipeline

```
bounded pilot configuration
  -> real read-only GitHub metadata           (via the 1E operator; live is opt-in)
  -> clearly classified enterprise/supplied signals
  -> existing Code Governance workflow
  -> Action Clearance shadow evaluation        (unchanged AC public API)
  -> CLEAR / HOLD / BLOCK / ESCALATE
  -> human reviewer assessment                 (curated annotations)
  -> categorized disagreement + outcome analysis
  -> verified pilot evidence pack
  -> enforcement-readiness verdict
  -> EXECUTION_DISABLED
```

## What 1F adds (`pilot_study/`)

| Module | Responsibility |
|---|---|
| `vocab.py` | evidence classes, cohorts, reviewer/outcome/root-cause/value/verdict vocabularies |
| `manifest.py` | immutable `PilotStudyManifest` (fails closed), pre-pilot freeze, amendments |
| `candidates.py` | deterministic `select_pilot_candidates` (no org-wide scan) + selection record |
| `annotation.py` | append-only `PilotEvaluationAnnotation` (exact-revision bound, blinding, unique-value evidence) |
| `analysis.py` | `analyze_pilot_results` — separated metrics, live vs non-live kept distinct, no unsupported stats |
| `calibration.py` | `PilotCalibrationRecommendation` (never applied) + offline `replay_pilot_policy` |
| `adverse.py` | `collect_adverse_cases` — individually reviewable, never hidden in aggregates |
| `checkpoints.py` | `PilotCheckpointRecord` + continue/pause/stop classification |
| `readiness.py` | `assess_enforcement_readiness` — deterministic verdict, never enables execution |
| `evidence_pack.py` | build/verify a deterministic, offline-verifiable, credential-free evidence pack |
| `security.py` | pre/post-run security + integrity + manifest-freeze verification |
| `persistence.py` | durable study records under a `study:<pilot_id>` lineage |

The study **reuses** the 1D adapters, the 1E operator, Action Clearance, durable
persistence, the pilot lifecycle, and reporting — it rebuilds none of them.

## Evidence-class honesty

Every evaluation and metric identifies its evidence class. Synthetic and
supplied-snapshot results are **never** aggregated into a metric presented as live
enterprise performance: `analyze_pilot_results` keeps `clearance_distribution_live`
(over `LIVE_GITHUB_METADATA` / `LIVE_ENTERPRISE_SIGNAL` only) strictly separate from
`clearance_distribution_non_live`. Supplied snapshots are counted under
`supplied_snapshot_dependence`, never as live signals.

## No unsupported statistics

No precision/recall/false-positive-rate/accuracy is produced — there is no
ground-truth protocol. Reviewer-derived outputs are reported as a
**reviewer-disagreement rate**, **possible** unnecessary/missed intervention
counts, incremental-value case counts, and unresolved counts, always with
numerator/denominator/missing. Small-sample discipline is preserved.

## Calibration never changes policy

`generate_calibration_recommendations` groups recurring disagreements by root cause
into *proposals* bound to supporting evaluations; each requires a new pilot
revision to validate and is never applied. `replay_pilot_policy` re-scores
completed evaluations against a policy candidate using **persisted facts only**,
makes no external call, never overwrites originals, and is always labelled
`HISTORICAL_REPLAY`.

## Enforcement-readiness verdict

`assess_enforcement_readiness` is a deterministic decision framework (no single
numeric score). Safety/integrity failures dominate → `SAFETY_OR_INTEGRITY_BLOCKED`;
no live evidence → `INSUFFICIENT_LIVE_EVIDENCE`; unresolved possible-false-CLEAR or
recurring policy defects → `PILOT_CALIBRATION_REQUIRED`; no demonstrated
incremental value → `PRODUCT_VALUE_NOT_PROVEN`; otherwise
`READY_FOR_ENFORCEMENT_DESIGN`. **No verdict enables execution.**

## Live vs offline (no fabricated evidence)

The offline demo (`examples/pilot_study_demo.py`) runs the complete analysis + report
flow with supplied snapshots, synthetic controls, historical replay, and mock
reviewer annotations. Because no live evaluations occur, it honestly reports
`LIVE_PILOT_NOT_RUN` and `INSUFFICIENT_LIVE_EVIDENCE`. A live pilot runs only when
`UGENCE_CODE_GOVERNANCE_LIVE_PILOT=1` plus an explicit manifest, tenant, allowlists,
store path, read-only credential reference, reviewer protocol, and evaluation bound
are supplied. This build is **IMPLEMENTED_AND_OFFLINE_VERIFIED**; it is not a live
pilot and no live results are fabricated.

## Validation

- `pytest products/code-governance` → full suite green (1A–1F) with 82 new 1F tests
  + the offline study demo.
- Version bumped to **0.5.0 / MVP phase 1F**; `cg-pilot study-validate` /
  `evidence-pack-verify` CLI added; wheel builds; clean install imports; Action
  Clearance unchanged; platform freeze digest unchanged.
- Machine-readable companions in `docs/`: `pilot_study_manifest_schema.json`,
  `pilot_evidence_classes.json`, `pilot_cohorts.json`, `pilot_reviewer_protocol.json`,
  `pilot_annotation_schema.json`, `pilot_checkpoint_schema.json`,
  `pilot_adverse_case_schema.json`, `pilot_calibration_schema.json`,
  `pilot_readiness_verdicts.json`, `pilot_1f_acceptance_scenarios.json`,
  `public_api.json`.

See `CODE_GOVERNANCE_ENFORCEMENT_READINESS.md`, `CODE_GOVERNANCE_MVP_1F_LIMITATIONS.md`,
and `CODE_GOVERNANCE_NEXT_PHASES.md`.
