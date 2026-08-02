# Model Selection — Capability Boundary, Authority, Evidence, Duplication, Packaging & Migration-Readiness Audit

*Audit-only phase. No source moved, no canonical package created, no public API changed, no
model-selection behavior/routing/scoring altered, no Governance Contracts / Hybrid LLM / AI Control Plane
touched, no API snapshot or platform freeze re-baselined. Every claim is traceable to a repository source;
the live repository is the source of truth, historical reports are evidence only.*

Companion deliverables in `docs/audits/model_selection/`: `BASELINE.md`, `baseline_manifest.json`,
`test_manifest.txt`, `FILE_MAP.md`, `IMPORT_GRAPH.md`, `PUBLIC_API_AND_CONSUMER_MAP.md`,
`ARTIFACT_CLASSIFICATION.md`, `AUTHORITY_AND_OUTPUT_CLASSIFICATION.md`,
`ELIGIBILITY_SCORING_ROUTING_EXECUTION_MATRIX.md`, `CONTRACT_OWNERSHIP_MATRIX.md`,
`DUPLICATION_MATRIX.md`, `EVIDENCE_AND_SCORING_ASSESSMENT.md`,
`HYBRID_LLM_AND_CONTROL_PLANE_BOUNDARY.md`, `PACKAGING_AND_FREEZE_IMPACT.md`,
`MIGRATION_READINESS_RECOMMENDATION.md`.

---

## 1. Executive verdict

**Model Selection is a coherent, bounded, dependency-clean capability that is not yet packaged as one
thing.** It is a two-stage policy — **ExecutionGate** (deterministic, fail-closed eligibility: "can this
approved model execute this request?") followed by **ModelPolicy** (advisory, policy-bounded selection:
"which eligible model should?"). Its output is a recommendation/policy-bounded choice, never an
authorization or an execution. It is cleanly separated from Hybrid LLM, the AI Control Plane, the Optional
Orchestrator, and provider execution, which only *consume* it. Its dependency direction is correct and it
is **not** part of the platform freeze.

The one structural obstacle to a canonical migration is **fragmentation + duplication**: the same
two-stage core is implemented four-to-five times (`execution_gate/`, `model_selection_experiment/`,
`model_selection_pilot/`, `model_selection_reconciliation/`, and `governed_inference_pilot/adapters/`) and
is interleaved with research/benchmark evaluation in every directory (and provider execution in the
pilot). All quantitative evidence is **synthetic and optimistically biased**; the real-provider pilot is
**credential-blocked**. Semantics are fully reproducible.

**Migration-readiness verdict:** *READY — separate Model Selection product logic from research evaluation.*

## 2. Current implementation map

| Layer | Where | Nature |
|---|---|---|
| Eligibility ("can execute") | `execution_gate/gate.py` (17 conditions, evidence+TTL+criticality, fail-closed) | production-shaped, deterministic |
| Selection ("should execute") | `execution_gate/policy.py::select`; `model_selection_experiment/policy.py::route`; `model_selection_pilot/policy.py::route`; `model_selection_reconciliation/variants.py` | advisory, policy-bounded (four copies) |
| Registry / port | `execution_gate/registry.py` (`ExecutableRegistry`) | governed candidate-metadata port |
| Contracts | `execution_gate/{states,model,reason_codes}.py` | enums, records, append-only reason codes |
| Research evaluation | experiment `simulator/metrics/baselines/harness`; pilot `arms/metrics/harness/scoring/execute`; reconciliation `evaluation.py`; `execution_gate/{harness,baselines,scenarios}.py` | benchmark/ablation/oracle |
| Provider execution | `model_selection_pilot/provider.py` + `execute.py` | credential-blocked → Stub |
| Consumers | `control_plane/adapters.py`, `control_plane_shadow/adapters/*`, `execution_gate_shadow/*`, `governed_inference_pilot/adapters/*` | depend on MSP |

Design docs: `ADR_MODEL_SELECTION_POLICY_PLACEMENT.md`, `MODEL_SELECTION_POLICY_ENGINE_SPEC.md`,
`MODEL_SELECTION_POLICY_OBJECTIVE_RECONCILIATION.md`, `MODEL_SELECTION_POLICY_VC_BRIEF.md`,
`docs/execution_eligibility/*` (16 docs). Sizes: source ≈ 4,636 LOC (non-frozen), tests ≈ 724 LOC, 85
tests (all pass).

## 3. Exact capability boundary

**Owns:** candidate eligibility (hard constraints), constraint evaluation, deterministic disqualification,
policy-weighted scoring, ranking, recommendation, selection explanation + evidence references,
cost/latency/quality trade-off, privacy/jurisdiction/capability matching, escalation when no candidate
qualifies (`NO_ELIGIBLE_MODEL`), audit-friendly deterministic selection records.

**Does not own:** model execution, provider invocation, retry, load balancing, request scheduling,
workflow orchestration, business-decision authority (Decision Authority), exact-action authorization
(ActionGate), operational clearance (ACP), assertion truth (TAP), provider *implementation* registration
(Governance Provider Framework), secrets, billing, application workflow, training, prompt optimization,
Hybrid-LLM handover, LLM steering. All confirmed absent from the selection path (`AUTHORITY_…`,
`ELIGIBILITY_…`, `HYBRID_LLM_…` companions).

The candidate definition — *"evaluate which already-approved model/provider best satisfies declared policy
and operational constraints for a request"* — **holds against the code.**

## 4. Authority classification

`POLICY_BOUNDED_SELECTION` with a deterministic `ADVISORY_RANKING` core. The eligibility gate is binding
in the safe (exclusionary) direction only; the selection is advisory and bypassable. It **recommends and
selects**; it does **not authorize or execute**. It chooses only from the ExecutionGate-eligible,
enterprise-approved set (the "one invariant" of `EXECUTIONGATE_MODELPOLICY_CONTRACT.md`). Override owners:
enterprise policy (hard constraints, constraint supremacy), the consumer/orchestrator (may ignore or
supply a pre-authorized model), and ExecutionGate (bounds the selectable set). See
`AUTHORITY_AND_OUTPUT_CLASSIFICATION.md`.

## 5. Advisory vs binding output

Empty eligible pool → `abstained` / `NO_ELIGIBLE_MODEL` (fail-fast, safe), not an unsafe fallback.
Selection reason strings are advisory; `control_plane_shadow` re-checks the pick and emits
`MODEL.SELECTED_MODEL_NOT_ELIGIBLE` rather than trusting it. Even the opt-in sufficiency mode is a
*predicted*, not *guaranteed*, floor.

## 6. Eligibility model

Hard, fail-closed constraints with evidence and TTL: provider reachable/authenticated, credential
validity, billing, quota, model availability, **approved-provider allowlist (CRITICAL_GOV)**, region /
**data-residency (CRITICAL_GOV)**, required features (tools/structured), context window, **hard cost
ceiling**, **hard latency SLA**, reliability floor / provider-degraded. Missing/stale critical evidence →
UNKNOWN → INDETERMINATE or fail-closed (never a silent pass). Aggregation precedence is fixed and
replayable (`gate.py::_aggregate`).

## 7. Scoring & ranking model

`utility = w_q·Q̂ − w_cost·(cost/cost_ref) − w_lat·(latency/lat_ref)`, `argmax`, deterministic id
tie-break; cost/latency normalized over the eligible set. `Q̂` is a confidence-weighted fusion of
provider-declared, benchmark-measured, runtime-telemetry, and (opt-in) advisory evidence. Fully
deterministic (hash-based noise, `now` injected). **Documented divergence:** the quality threshold is a
*soft* target in the default policy (read by `metrics.py`, not `policy.py`); the opt-in Policy B enforces a
*predicted* floor. Constraint supremacy holds for all *hard* constraints. See
`EVIDENCE_AND_SCORING_ASSESSMENT.md`.

## 8. Routing & execution separation

Eligibility ↔ scoring are architecturally separated and test-covered. **Routing does not exist** in any
production path. **Execution** exists only as the credential-blocked pilot (`provider.py`/`execute.py`),
co-located in `model_selection_pilot/` as a research harness. No retry, failover, or load balancing is
implemented (`fallback_chain` is a ranked ordering, never executed; `retries` field is always 0). See
`ELIGIBILITY_SCORING_ROUTING_EXECUTION_MATRIX.md`.

## 9. Hybrid LLM boundary

Clean. `symbolu/hybrid/router.py` (SemanticRouter), `symbolu/providers/*_router.py`,
`experiments/.../reasoning_router.py`, and `agentic/hybrid_handover/` are Hybrid LLM (internal
specialized-model routing / local-frontier handover) — none performs governed provider eligibility, and no
Model Selection code performs handover, egress minimization, context filtering, or runtime orchestration.
Terminology audit pins Model Selection = #8, distinct from Hybrid LLM = #9.

## 10. AI Control Plane & Orchestrator boundary

Clean and correctly directed. `control_plane/orchestrator.py` "holds NO decision authority"; it and
`control_plane_shadow` **consume** MSP via adapters. `PolicyContext`/RequestNormalizer are upstream
envelopes that *feed* MSP without owning selection. MSP imports none of them and stays bypassable.
`ai_control_plane_v3/` is docs-only; `cloud_controller/` is infra autoscaling. No improper coupling.

## 11. Contract ownership

Every Model Selection record (`Request`, `Candidate`, `Signal`, `GateConfig`, `Evidence`,
`EligibilityState/Decision`, `Verdict`, `Criticality`, `ReasonCode`, `ModelRecord`/`ExecStatus`,
`PolicyWeights`/`Selection`, `ConstraintSet`, decision record, score breakdown, `NO_ELIGIBLE_MODEL`)
belongs to the **Model Selection capability**. **None** meets the bar for Governance Contracts today
(capability-specific; they flow downward to consumers, not shared at a lower layer). Governance Contracts
is not modified in this phase. See `CONTRACT_OWNERSHIP_MATRIX.md`.

## 12. Duplication findings

The two-stage core is implemented **4–5×** by copy (only `reconciliation→experiment` is an import edge),
with duplicated hard-filter 4-tuples, utility formula, decision-record schema, advisory guard, quality
fusion, cost/latency estimators, and registries. Pattern-only neighbors with a *different object*
(`provider_heterogeneity_validation/selection/resolve.py`, Hybrid routers, `trading2` model_selector, MoE
expert routers) must **not** be consolidated in. See `DUPLICATION_MATRIX.md`.

## 13. Evidence quality

Hard constraints derive from STATIC_POLICY / CUSTOMER_CONFIGURATION / PROVIDER_DECLARATION (deterministic).
The three "measured" quality signals (benchmark, telemetry, advisory) are **SYNTHETIC** in every current
corpus (simulator/stub-generated); the advisory signal is a MODEL_GENERATED_ESTIMATE weighted low. `Q̂` is
optimistically biased (|Q̂−true| 0.035→0.058; dangerous optimistic miscalibration 0.041→0.090). No
calibrated variance/LCB. **No real-provider evidence** (credential-blocked). Semantics are fully
reproducible. See `EVIDENCE_AND_SCORING_ASSESSMENT.md`.

## 14. Public API

No package defines `__all__`; the de-facto surface is `execution_gate.*` (4 consumer trees),
`model_selection_experiment.policy.route` (1 consumer), and the consumer-less pilot/reconciliation
surfaces. Serialization-sensitive: the `execution_gate` enums/records/`to_dict` and append-only
`ReasonCode`. See `PUBLIC_API_AND_CONSUMER_MAP.md`.

## 15. Dependency direction

Correct. `execution_gate` and `model_selection_experiment` import nothing external; consumers depend on
them; no inversion. `ExecutableRegistry` already serves as the provider-metadata port. See `IMPORT_GRAPH.md`.

## 16. Packaging readiness

Dependency-wise, ready (dependency-free leaf, no inversions). Structurally, **not a lift-and-shift**:
consolidation + product/research separation is required first. Proposed future target (not created):
`packages/capabilities/model-selection/`, `ugence_model_selection`, `ugence-model-selection`. See
`PACKAGING_AND_FREEZE_IMPACT.md`.

## 17. Freeze / API impact

**Zero platform-freeze / public-API-snapshot impact** — Model Selection is not a frozen core tree, has no
platform API snapshot, and no component-version entry (`platform_freeze/version.py`). The only freeze
obligation is to carry `execution_gate/frozen/replay_v1` (aggregate `8b05b2da798a6222`, verifier PASS)
along and keep it byte-identical. This is a lower-risk migration than the prior governance migrations.

## 18. Consumer impact

`execution_gate.*`: moderate (4 consumers; canonical import + legacy shim preserves them).
`model_selection_experiment.route`: low (1 adapter). `model_selection_pilot`, `model_selection_reconciliation`:
none (no consumers). No consumer relies on a platform freeze snapshot of MSP (there is none).

## 19. Risks

Duplication I/O-shape and numeric drift (mitigate with a behavior-equivalence harness); synthetic/optimistic
evidence over-claimed (keep wording discipline; pilot blocked); soft quality floor shipped as a guarantee
(opt-in *predicted* mode only); migrating pilot execution into the package (leave it behind). Full register
in `MIGRATION_READINESS_RECOMMENDATION.md`.

## 20. Exact next phase

1. Define canonical product core (`execution_gate` eligibility+selection+contracts + experiment quality
   fusion + reconciliation opt-in mode). 2. Build a byte-identical behavior-equivalence harness across all
   copies. 3. Separate research evaluation and provider execution out. 4. Resolve the soft-vs-hard quality
   floor as an explicit *predicted* opt-in mode. 5. Then migrate to
   `packages/capabilities/model-selection/`, carrying the replay freeze. **None executed in this phase.**

---

## Migration-readiness verdict

**READY — separate Model Selection product logic from research evaluation**
