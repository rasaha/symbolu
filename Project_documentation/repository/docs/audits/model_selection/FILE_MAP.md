# Model Selection — File Map

Every Model Selection-related file, with LOC and role. Source LOC excludes the frozen replay tree.
Captured directly (`wc -l`) at commit `66066e99`.

## `execution_gate/` — production-shaped core (ExecutionGate + ModelPolicy + Registry)

| File | LOC | Role | Classification |
|---|---:|---|---|
| `gate.py` | 215 | `ExecutionGate.evaluate` — deterministic eligibility over 17 conditions with evidence/TTL/criticality; fail-closed aggregation | PRODUCT (eligibility core) |
| `policy.py` | 61 | `ModelPolicy.select` — utility `w_q·Q̂ − w_cost·cost − w_lat·lat` over eligible pool; deterministic id tie-break | PRODUCT (selection core) |
| `states.py` | 99 | `EligibilityState/Verdict/Criticality/EvidenceSource/Evidence/ConditionResult/EligibilityDecision` | PRODUCT (contract) |
| `model.py` | 58 | `Request/Candidate/Signal/GateConfig` dataclasses | PRODUCT (contract) |
| `registry.py` | 69 | `ExecutableRegistry/ModelRecord/ExecStatus` — evaluate gate over records | PRODUCT (registry port) |
| `reason_codes.py` | 63 | `ReasonCode` append-only taxonomy + `normalize_raw` | PRODUCT (contract) |
| `harness.py` | 141 | evaluation driver over scenarios | RESEARCH (eval harness) |
| `baselines.py` | 101 | comparison baselines | RESEARCH (eval baselines) |
| `scenarios.py` | 225 | synthetic scenario corpus | RESEARCH (eval data) |
| `common_io.py` | 6 | IO helper | SUPPORT |
| `__init__.py` | 1 | package docstring | SUPPORT |
| `tests/test_execution_gate.py` | 196 | 21 tests | TEST |
| `frozen/replay_v1/**` | 1158 | frozen artifact copies + `build_freeze.py`/`verify_frozen.py` (self-contained replay determinism guard; verifier PASS, aggregate `8b05b2da798a6222`) | FROZEN EVIDENCE |

## `model_selection_experiment/` — research/benchmark harness (contains the "scientific" route engine)

| File | LOC | Role | Classification |
|---|---:|---|---|
| `policy.py` | 242 | `route()` full pipeline: `resolve_constraints → hard_filter → fuse_quality → score → rank`; `_validate_advisory` | PRODUCT (selection engine, research-hosted) |
| `common.py` | 122 | version stamps, `weighted_caps`, deterministic hash noise, IO, `percentile` | SUPPORT (partly product: `weighted_caps`) |
| `baselines.py` | 156 | arms A–G (A fixed / B strongest / C cheapest-eligible / D static-rules / E benchmark-only / F,G policy) | RESEARCH (baselines) |
| `simulator.py` | 228 | ground-truth world + `telemetry_feed`/`advisory_feed`/`oracle`/`regret_for_choice` | RESEARCH (synthetic evidence + oracle) |
| `metrics.py` | 151 | `score_records`, `explanation_completeness`; reads `acceptable_quality_threshold` (measurement only) | RESEARCH (scoring) |
| `harness.py` | 202 | `run_all()` experiment driver | RESEARCH (driver) |
| `build_data.py` | 375 | emits versioned JSON data artifacts | RESEARCH (data gen) |
| `data/*.json` | — | `corpus_v1`, `ground_truth_v1`, `policy_v1`, `registry_v1` | RESEARCH DATA (synthetic corpus; declared registry facts) |
| `results/*.json` | — | `aggregate_metrics`, `decision_record*` | GENERATED EVIDENCE |
| `tests/test_policy.py` | 200 | 15 tests | TEST |

## `model_selection_pilot/` — real-provider shadow pilot (credential-blocked → runs stub)

| File | LOC | Role | Classification |
|---|---:|---|---|
| `policy.py` | 248 | fork of two-stage: `hard_and_technical_filter` + `route` with F1/F2/G modes, reliability gate, thin-evidence leniency | PRODUCT (selection engine, forked copy) |
| `provider.py` | 356 | `Anthropic/OpenAI/Bedrock/Stub` adapters (urllib/boto3); keys from env only; `resolve_adapters` | RESEARCH/RUNTIME (provider EXECUTION — blocked) |
| `execute.py` | 80 | `run_counterfactual` — runs every eligible model on every task to build outcome store | RESEARCH (counterfactual execution) |
| `costguard.py` | 59 | `CostGuard` spend cap + `dry_run` pre-flight cost | PRODUCT-ADJACENT (spend guard) |
| `telemetry.py` | 60 | regime-gated prior snapshots (cold/partial/mature) from outcomes | RESEARCH (evidence gen) |
| `advisory.py` | 59 | bounded cold-start self-assessment gate (`ALLOWED`/`FORBIDDEN` fields, `SelfAssessmentViolation`) | PRODUCT-ADJACENT (advisory guard) |
| `scoring.py` | 136 | per-task-class **outcome graders** (NOT the selection formula) | RESEARCH (outcome scoring) |
| `arms.py` | 88 | baselines A–E | RESEARCH (baselines) |
| `metrics.py` | 178 | `score_arm`, `commercial_vs_baseline` | RESEARCH (scoring) |
| `harness.py` | 209 | `run()` pilot driver | RESEARCH (driver) |
| `registry.py` | 127 | `build()` — 5 real models, stamped `published-docs-not-live-verified` | RESEARCH DATA (declared registry) |
| `build_corpus.py` | 200 | synthetic corpus generator (no real PII) | RESEARCH (data gen) |
| `common.py` | 76 | helpers | SUPPORT |
| `data/*.json` | — | `registry`, `corpus_dev`, `corpus_shadow` | RESEARCH DATA |
| `results/**` | — | aggregate/decision/normalized/raw | GENERATED EVIDENCE |
| `tests/test_pilot.py` | 201 | 17 tests | TEST |

## `model_selection_reconciliation/` — objective reconciliation (Policy A/B/C)

| File | LOC | Role | Classification |
|---|---:|---|---|
| `variants.py` | 130 | `route_A` (verbatim baseline) / `route_B` (hard floor + min cost) / `route_C` (lexicographic); imports experiment read-only | PRODUCT (policy variants) |
| `evaluation.py` | 141 | `run_evaluation` — A/B/C on the frozen simulator/metrics; threshold + regime sweep | RESEARCH (evaluation) |
| `results/reconciliation_eval_v1.json` | — | full grid result | GENERATED EVIDENCE |
| `tests/test_variants.py` | 127 | 9 tests | TEST |

## Same-capability, outside the four dirs

| File | Role |
|---|---|
| `governed_inference_pilot/adapters/execution_gate.py` | adapter over the FROZEN `execution_gate.gate` (eligibility) |
| `governed_inference_pilot/adapters/model_policy.py` | re-implements selection `argmin cost s.t. quality ≥ q_min` (reconciliation objective) |

## Documentation & specs (evidence, not code)

- Root: `ADR_MODEL_SELECTION_POLICY_PLACEMENT.md`, `MODEL_SELECTION_POLICY_ENGINE_SPEC.md`,
  `MODEL_SELECTION_POLICY_OBJECTIVE_RECONCILIATION.md`, `MODEL_SELECTION_POLICY_VC_BRIEF.md`
- `docs/execution_eligibility/` — 16 docs incl. `EXECUTION_ELIGIBILITY_SPEC.md`,
  `EXECUTIONGATE_MODELPOLICY_CONTRACT.md`, `EXECUTABLE_REGISTRY_SCHEMA.md`, `REASON_CODE_TAXONOMY.md`,
  `LIVE_SHADOW_GO_NO_GO.md`, `LIMITATIONS_AND_FALSIFICATION.md`
- Per-dir: `ARCHITECTURE_NOTE.md`, `FALSIFICATION_ASSESSMENT.md` (experiment); `PILOT_STATUS.md`,
  `RECOMMENDATION.md`, `V2_VIABILITY_REPORT.md` (pilot)
- Architecture: `UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md` (Model Selection = capability #8,
  distinct from Hybrid LLM #9), `UGENCE_MODULARITY_AND_PACKAGING_AUDIT.md`
