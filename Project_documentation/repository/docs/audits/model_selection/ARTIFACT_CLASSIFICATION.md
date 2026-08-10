# Model Selection — Artifact Classification

Classifies every Model Selection artifact as **reusable product logic**, **research/benchmark
evaluation**, **contract**, **generated evidence**, or **runtime/provider execution**. This is the axis
that determines what could migrate into a canonical capability vs what stays behind as research.

## Legend
- **PRODUCT** — deterministic decision logic that a productized capability would keep.
- **CONTRACT** — public data types / enums / reason codes (a subset of PRODUCT, serialization-sensitive).
- **RESEARCH** — benchmark/ablation/simulation harness, oracle, baselines, synthetic corpora, drivers.
- **EXECUTION** — provider invocation / counterfactual runner (not selection).
- **EVIDENCE** — generated result JSON / frozen replay artifacts.
- **SUPPORT** — IO/version helpers.

## `execution_gate/`

| Artifact | Class | Reasoning |
|---|---|---|
| `gate.py` (`ExecutionGate.evaluate`, `_aggregate`) | PRODUCT | deterministic eligibility; the reusable "can execute" core |
| `policy.py` (`ModelPolicy.select`, `PolicyWeights`, `Selection`) | PRODUCT | deterministic selection over eligible pool |
| `states.py`, `model.py`, `reason_codes.py` | CONTRACT | public types, enums, append-only reason codes; `to_dict()` serialization |
| `registry.py` (`ExecutableRegistry`, `ModelRecord`, `ExecStatus`) | PRODUCT (port) | provider-metadata registry + gate driver |
| `harness.py`, `baselines.py`, `scenarios.py` | RESEARCH | scenario evaluation + comparison baselines |
| `frozen/replay_v1/**` | EVIDENCE | self-contained replay determinism guard (verifier PASS) |

## `model_selection_experiment/`

| Artifact | Class | Reasoning |
|---|---|---|
| `policy.py` (`route`, `hard_filter`, `resolve_constraints`, `fuse_quality`, `score`) | PRODUCT | the "scientific" selection engine; reads only registry/telemetry/policy/advisory, never ground truth |
| `common.py::weighted_caps` | PRODUCT | shared quality primitive |
| `common.py` (IO, versions, hash noise) | SUPPORT | experiment scaffolding |
| `baselines.py` (arms A–G) | RESEARCH | comparison arms (A fixed / B strongest / C cheapest / D static-rules / E benchmark-only); F,G wrap `route` |
| `simulator.py` (`true_*`, `telemetry_feed`, `advisory_feed`, `oracle`, `regret_for_choice`) | RESEARCH | synthetic ground-truth world + evidence generators; only module that reads ground truth |
| `metrics.py` | RESEARCH | scores records vs ground truth |
| `harness.py`, `build_data.py` | RESEARCH | experiment driver + data generator |
| `data/*.json`, `results/*.json` | EVIDENCE | synthetic corpus, declared registry facts, generated decision records |

## `model_selection_pilot/`

| Artifact | Class | Reasoning |
|---|---|---|
| `policy.py` (`route` F1/F2/G, `hard_and_technical_filter`, `predict_quality`) | PRODUCT (forked copy) | selection engine variant; adds soft/hard quality modes + reliability gate |
| `costguard.py`, `advisory.py` | PRODUCT-ADJACENT | spend cap + bounded self-assessment gate (reusable guards) |
| `provider.py` (`Anthropic/OpenAI/Bedrock/Stub` adapters, `resolve_adapters`) | EXECUTION | provider invocation; **credential-blocked → runs Stub**; NOT selection |
| `execute.py` (`run_counterfactual`, `technically_eligible`) | RESEARCH/EXECUTION | runs every eligible model on every task to build outcome store |
| `scoring.py` | RESEARCH | per-task-class outcome graders (rule-based; not selection, not LLM judge) |
| `telemetry.py` | RESEARCH | regime-gated evidence snapshots from outcomes |
| `arms.py`, `metrics.py`, `harness.py` | RESEARCH | baselines + scoring + driver |
| `registry.py`, `build_corpus.py`, `data/*` , `results/**` | EVIDENCE/DATA | 5 real models (stamped not-live-verified); synthetic corpus; generated results |

## `model_selection_reconciliation/`

| Artifact | Class | Reasoning |
|---|---|---|
| `variants.py` (`route_A/B/C`, `route_variant`) | PRODUCT | selectable policy variants over the experiment engine (A verbatim; B hard floor+min cost; C lexicographic) |
| `evaluation.py` | RESEARCH | A/B/C evaluation over the frozen simulator/metrics; threshold + regime sweep |
| `results/reconciliation_eval_v1.json` | EVIDENCE | full grid |

## `governed_inference_pilot/adapters/` (same-capability, outside the four dirs)

| Artifact | Class | Reasoning |
|---|---|---|
| `execution_gate.py` | PRODUCT (re-host) | eligibility over frozen `execution_gate.gate` |
| `model_policy.py` | PRODUCT (re-host) | selection `argmin cost s.t. quality ≥ q_min` (reconciliation objective) |

## Roll-up

| Class | Where it dominates |
|---|---|
| PRODUCT / CONTRACT | `execution_gate/{gate,policy,states,model,registry,reason_codes}.py`; `model_selection_experiment/policy.py` (+`weighted_caps`); `model_selection_pilot/policy.py` (fork); `model_selection_reconciliation/variants.py`; `governed_inference_pilot/adapters/*` |
| RESEARCH | the *majority* of `model_selection_experiment/`, `model_selection_pilot/`, and all of `model_selection_reconciliation/evaluation.py`, plus `execution_gate/{harness,baselines,scenarios}.py` |
| EXECUTION | `model_selection_pilot/{provider,execute}.py` (blocked) |

**Key finding:** genuine reusable product logic (a deterministic two-stage eligibility+selection core)
is real and coherent, but it is (a) **interleaved with** substantial research/benchmark evaluation code
inside every directory, and (b) **duplicated** across four-to-five directories. Extracting the product
core from the research evaluation is the pre-condition for any canonical migration.
