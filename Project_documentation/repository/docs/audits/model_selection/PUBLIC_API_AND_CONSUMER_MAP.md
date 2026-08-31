# Model Selection — Public API & Consumer Map

Captured directly at commit `66066e99`. None of the Model Selection packages defines `__all__`; the
"public API" is the set of module-level classes/functions consumers actually import. There is **no**
platform public-API snapshot for any of them (they are not frozen core trees).

## 1. `execution_gate` — the de-facto product surface (has real consumers)

| Symbol | Kind | Signature (as-is) | Notes |
|---|---|---|---|
| `ExecutionGate` | class | `ExecutionGate(config: GateConfig=None)`; `.evaluate(cand, req, now) -> EligibilityDecision` | eligibility engine |
| `ModelPolicy.select` | function | `select(selectable, req, quality_of, weights=None) -> Selection` (`execution_gate/policy.py`) | selection over eligible pool |
| `PolicyWeights` | dataclass | `quality=1.0, cost=0.5, latency=0.35, conditional_penalty=0.15` | serialization-sensitive |
| `Selection` | dataclass | `selected: Optional[ModelRecord]; ranked; abstained: bool; reason: str` | selection output record |
| `ExecutableRegistry` | class | `.upsert(rec)`, `.evaluate(req, now) -> (selectable, excluded)` | provider-metadata port |
| `ModelRecord` | dataclass | `internal_id, candidate, exec_status, …, observed_latency_ms, observed_reliability, evidence_ttl_s, enabled` | serialization-sensitive |
| `ExecStatus` | enum | `DECLARED/ENUMERATED/AUTHENTICATED/EXECUTION_VERIFIED/DISABLED` | serialization-sensitive |
| `Request` | dataclass | `request_id, context_tokens, features_required, approved_providers, region_allowed, residency_required, latency_limit_ms, cost_cap_usd, est_output_tokens` | input contract |
| `Candidate` | dataclass | `provider, model_id, family, developer, region, context_limit, structured_output, tool_use, price_in/out_per_mtok, signals` | input contract |
| `Signal` | dataclass | `value, evidence, reason_hint` | input contract |
| `GateConfig` | dataclass | `allow_conditional, require_billing, reliability_floor, default_latency_limit_ms, indeterminate_on_unknown, policy_version` | config contract |
| `EligibilityState` | enum | `ELIGIBLE/INELIGIBLE/CONDITIONALLY_ELIGIBLE/INDETERMINATE` | serialization-sensitive |
| `Verdict` | enum | `PASS/FAIL/UNKNOWN` | serialization-sensitive |
| `Criticality` | enum | `CRITICAL_GOV/CRITICAL_OP/OPERATIONAL` | serialization-sensitive |
| `Evidence`, `EvidenceSource`, `ConditionResult`, `EligibilityDecision` | dataclass/enum | see `states.py`; `EligibilityDecision.to_dict()` is a stable serialization | serialization-sensitive; `.selectable` property gates selection |
| `ReasonCode` | enum | append-only taxonomy (24 codes) + `normalize_raw(signal)` | serialization-sensitive; **append-only invariant** |

**Consumers:** `control_plane/adapters.py`, `control_plane_shadow/adapters/execution_gate_adapter.py`,
`execution_gate_shadow/*`, `governed_inference_pilot/adapters/execution_gate.py`.

## 2. `model_selection_experiment` — research engine with one consumer

| Symbol | Kind | Signature |
|---|---|---|
| `policy.route` | function | `route(task, registry, enterprise_policy, telemetry, policy, regime, advisory_by_model=None) -> dict` (decision record) |
| `policy.hard_filter` | function | `hard_filter(model, task, cs) -> (ok, reason, constraint, provenance)` |
| `policy.resolve_constraints` | function | `resolve_constraints(task, enterprise_policy) -> ConstraintSet(dict)` |
| `policy.fuse_quality` | function | `fuse_quality(model, task, telemetry, policy, advisory) -> {predicted_quality, evidence}` |
| `policy.score` | function | `score(model, task, predicted_q, cost_ref, lat_ref) -> {utility, components, est_cost, est_latency_ms}` |
| `policy.SelfAssessmentViolation` | exception | raised when advisory supplies a forbidden field |
| `common.weighted_caps`, `common.POLICY_VERSION`, `common.REGISTRY_VERSION` | helper/const | shared quality primitive + version stamps |
| `baselines.ARMS`, `simulator.*`, `metrics.score_records`, `harness.run_all` | research | evaluation apparatus only |

**Consumer:** `control_plane_shadow/adapters/model_policy_adapter.py` (wraps `route` on `policy_v1`/`registry_v1`).

## 3. `model_selection_pilot` — forked engine, **no external consumers**

Bare `__init__.py` (no exports). De-facto surface: `harness.run()/print_summary()`,
`policy.route(task, registry, telemetry, regime, mode, advisory_map=None)`,
`policy.hard_and_technical_filter`, `policy.predict_quality`, `provider.resolve_adapters` + adapter
classes (`Anthropic/OpenAI/Bedrock/Stub`), `execute.run_counterfactual/technically_eligible`,
`costguard.CostGuard/dry_run`, `advisory.validate/synth_advisory`, `scoring.score`,
`telemetry.build_snapshots`, `metrics.score_arm/commercial_vs_baseline`. **No module imports it.**

## 4. `model_selection_reconciliation` — variants, **no external consumers**

`variants.route_A/route_B/route_C`, `variants.route_variant(variant, …, q_min=…)`,
`evaluation.run_evaluation/reproducible`. Imports `model_selection_experiment` read-only. **No module imports it.**

## 5. Same-capability re-host

`governed_inference_pilot/adapters/execution_gate.py` (eligibility over frozen `execution_gate.gate`)
and `governed_inference_pilot/adapters/model_policy.py` (selection `argmin cost s.t. quality ≥ q_min`).

## 6. Consumer-impact summary for a future migration

| Surface | Consumers | Migration blast radius |
|---|---|---|
| `execution_gate.*` | 4 consumer trees | **Moderate** — a canonical import path + a legacy shim would preserve all 4; contracts (`states`, `model`, `reason_codes`) are the serialization-sensitive part |
| `model_selection_experiment.policy.route` | 1 consumer (`control_plane_shadow`) | **Low** — single adapter to repoint |
| `model_selection_pilot.*` | 0 | **None** (self-contained) |
| `model_selection_reconciliation.*` | 0 | **None** (depends only on experiment) |

No consumer relies on a platform freeze snapshot of Model Selection (there is none), so no API-snapshot
re-baseline is implicated.
