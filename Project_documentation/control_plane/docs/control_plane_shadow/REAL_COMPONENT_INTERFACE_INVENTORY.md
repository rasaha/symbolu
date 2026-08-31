# Real Component Interface Inventory

*Phase 1. Actual, verified interfaces of the real repository components to be wrapped by
shadow-pilot adapters. Every "real engine" entry below was executed read-only and confirmed
deterministic and network-free in this environment. No component was modified. Paths are
`file:line`.*

## Method

Each candidate was imported read-only and run on real fixtures. "Verified" means the engine
was invoked and produced the stated output shape/vocabulary deterministically (repeated
invocation identical). Live-call and real-action risks were traced to source.

## ExecutionGate — REAL, wrappable

- **Source:** `execution_gate/gate.py:47` `class ExecutionGate.evaluate(cand, req, now) -> EligibilityDecision`.
- **Input types:** `execution_gate.model.Candidate` (provider/model/family/region/caps/signals),
  `execution_gate.model.Request` (features_required, approved_providers, residency, budgets), `now: float`.
- **Output type:** `execution_gate.states.EligibilityDecision` — `state` ∈
  {ELIGIBLE, INELIGIBLE, CONDITIONALLY_ELIGIBLE, INDETERMINATE}, `reasons: [ReasonCode]`,
  `conditions`, `policy_version`, `evaluated_at`, `ttl_seconds`.
- **Hidden assumptions:** signals carry `Evidence` with TTL; `value is None` ⇒ UNKNOWN (never a pass).
- **State / side effects:** none (pure); reads nothing external. **Determinism:** yes.
  **Live-call risk:** none. **Real-action risk:** none.
- **Versioning:** `GateConfig.policy_version` (`exec_gate_v1`). **Frozen:** `execution_gate/frozen/replay_v1`
  (aggregate `8b05b2da798a6222`) — do not modify.
- **Reuse:** directly through adapter. **Integration blocker:** none.

## ModelPolicy — REAL, wrappable

- **Source:** `model_selection_experiment/policy.py:177`
  `route(task, registry, enterprise_policy, telemetry, policy, regime, advisory_by_model=None) -> dict`.
- **Input types:** `task` (task_id, task_class, required_caps, input_tokens_k, utility_weights,
  acceptable_quality_threshold, hard_constraints), `registry` (real `data/registry_v1.json`, 6 models),
  `enterprise_policy` (`approved_providers`), `policy` (real `data/policy_v1.json`), `regime` ("mature").
- **Output type:** full deterministic decision record — `eligible`, `eliminated[{model,reason,constraint,
  provenance}]`, `scored[{model,predicted_quality,utility,components,est_cost,est_latency_ms,evidence}]`,
  `selected`, `fallback_chain`, `abstained`, `abstain_reason`, `policy_version`, `registry_version`.
- **Hidden assumptions:** `enterprise_policy["approved_providers"]` required; providers are
  {vendor_alpha…omega, internal}. Advisory (arm G) fields are validated (`_validate_advisory`).
- **State / side effects:** none. **Determinism:** yes (tie-break by model id). **Live-call risk:** none.
- **Versioning:** `policy_v1` / `registry_v1`. **Frozen:** `model_selection_experiment/results/*.json`,
  `model_selection_pilot/results/*.json` — do not modify (code import is fine).
- **Reuse:** directly through adapter. **Semantic note:** richer than `execution_gate.policy.select`
  used in the prior mock track; this is the authoritative ModelPolicy for the shadow pilot.

## TAP / Assertion Governance — REAL engine, **documented semantic gap**

- **Best real engine:** `truth_assurance_pipeline/tap_e4_governance_truth/applicability.py:144`
  `class GovernanceTruthLayer.resolve(intent, retrieval, relationship, situation) -> GovernanceRecord`
  (canonical alias: `tap_e4_governance_resolution.GovernanceResolver`; config `F` = full engine).
- **Input types:** three upstream records (`IntentRecord`, `RetrievalRecord`, `RelationshipRecord`) +
  `Situation` (jurisdiction/role/environment/date/contract/product/business_unit). Valid records are
  built read-only via `tap_e4_governance_truth.corpus.cases` (`cases_for_split`, `build_retrieval_record`,
  `build_relationship_record`) and `harness._intent`.
- **Output type:** `GovernanceRecord` — `governing_authorities[GoverningDecision{status,...}]`,
  `governance_conflicts`, `governance_gaps`, 8-axis `confidence_vector` with `band()`, full `provenance`.
  Disposition vocabulary (`schema.py:24` `GovStatus`): GOVERNING, GOVERNING_WITH_EXCEPTION, CONFLICTED,
  NO_GOVERNING_AUTHORITY, INSUFFICIENT_BASIS, UNRESOLVED. **Verified distribution** over dev cases:
  GOVERNING×12, GOVERNING_WITH_EXCEPTION×1, CONFLICTED×1, NO_GOVERNING_AUTHORITY×1.
- **Determinism:** yes (`CREATED_AT = "N/A (deterministic run)"`). **Live-call risk:** none in E4.
  **Real-action risk:** none.
- **⚠ SEMANTIC GAP (integration blocker, mitigated):** E4 decides *which documented authority governs a
  situation*, NOT *whether a model's claim may be asserted*. Its README explicitly separates it from
  assertion/action governance. Using it as the assertion-governance boundary is a **semantic
  approximation**; the `GovStatus → {ALLOW,QUALIFY,REJECT,ESCALATE,INDETERMINATE}` mapping is
  **authored in the adapter** and must be labeled as such. **Do NOT claim production TAP integration.**
- **Avoid:** `tap_e1_1_realmodel/model_client.py:77 AnthropicModelClient` — **real Anthropic API** if
  `ANTHROPIC_API_KEY` present (live-call risk HIGH). `symbolu_bcvf_llm/trust` — token decoder, unrelated.
- **Frozen:** each stage's `experiments/{experiment_lock,preregistration,results_*}.json`, and the E4
  `frozen_components_hash()` over the engine sources — do not modify engine files.

## ActionGate — REAL, wrappable, clean semantic match

- **Source:** `cyber_security/action_gate_reference/action_gate_ref/gate.py:146`
  `evaluate(envelope, signed_policy, *, evidence=None, approvals=None, now, used_nonces=(), ...) -> dict`.
- **Input types:** 24-field canonical action **envelope** (operation, target_resource, arguments,
  reversibility, credential_scope, delegation_chain, attestation), signed **policy bundle**, evidence
  list, approvals list. Valid inputs built read-only via `action_gate_reference/tests/helpers.py`
  (`env_for`, `signed_policy`, `approval_for`, `ev_backup`, `ev_signed_artifact`, `with_attestation`).
- **Output type:** dict — `outcome` ∈ {ALLOW, ALLOW_WITH_CONSTRAINTS, SIMULATE_AND_RETRY,
  REQUEST_MORE_EVIDENCE, ESCALATE_TO_HUMAN, DENY}, `dispositive_rules`, `applied_constraints`,
  `action_hash`, `policy_hash`, `state_trace`, `terminal` ∈ {COMMITTED,DENIED,ESCALATED,AUDIT_LOGGED},
  `reason`. **Verified**: bare ops → {DEPLOY:REQUEST_MORE_EVIDENCE, DB_DELETE:DENY, SECRET_READ:
  ESCALATE_TO_HUMAN, KEY_ROTATE:ESCALATE_TO_HUMAN, NET_EXPOSE:DENY, EXTERNAL_COMMS:DENY,
  CLOUD_SPEND_INCREASE:DENY}; KEY_ROTATE + attestation + dual approval + evidence → ALLOW.
  Deterministic; `action_hash` stable.
- **Determinism:** pure function. **Live-call risk:** none. **Real-action risk:** none (decision-only).
- **Versioning:** signed policy `policy_hash`; envelope `schema_version` "1.0.0". **Frozen:**
  `fixtures/conformance_vectors.json`, `fixtures/transitions.json`, `real_world_validation/
  real_world_results.json` — do not modify.
- **⚠ AVOID (real side effects):** `action_gateway_k8s/kubeclient.py` (real kube-apiserver HTTPS
  apply/delete), `action_gateway_isolated/gateway_core.py` (real `broker.execute`), the MCP server, and
  `action_gateway.Gateway.execute_action` (runs adapters; defaults to RealClock). These are **never**
  invoked by the shadow pilot.

## Provider execution & Action execution — NO real component used

- **Provider execution:** no live provider call is made (task constraint). Provider outcomes come from
  synthetic fixtures / recorded failure artifacts only → **replay/mock**, never TIER ≥5 here.
- **Action execution:** **prohibited.** No real action adapter is invoked. In shadow mode the action
  adapter is simulated (records "would execute", never executes).

## Telemetry / Audit — reuse prior track

- `control_plane/decisions.py` (append-only hash-chained `AuditLog`), `control_plane/telemetry.py`
  (prospective `RegistryUpdater`). Unit-tested; reused unchanged through a thin shadow audit adapter.

## Summary table

| Boundary | Real engine | Executable? | Determinism | Live-call | Real-action | Reuse | Blocker |
|---|---|---|---|---|---|---|---|
| ExecutionGate | `execution_gate.gate` | yes | yes | none | none | adapter | none |
| ModelPolicy | `model_selection_experiment.policy.route` | yes | yes | none | none | adapter | none |
| TAP/assertion | `tap_e4…GovernanceResolver` | yes | yes | none (E4) | none | adapter | **semantic gap** |
| ActionGate | `action_gate_ref.gate.evaluate` | yes | yes | none | none | adapter | none |
| Provider exec | — | — | replay | avoided | avoided | replay adapter | no live calls |
| Action exec | — | — | simulated | avoided | **avoided** | sim adapter | no real actions |
| Telemetry/Audit | `control_plane.*` | yes | yes | none | none | reuse | none |
