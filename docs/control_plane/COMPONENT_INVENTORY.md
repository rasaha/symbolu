# Control-Plane Component Inventory

*Phase 1. Read-only inventory of every control-plane component. Nothing is modified. Frozen
outcome-bearing artifacts are marked and left untouched.*

## Legend

Reuse: **UNCHANGED** (import/adapt as-is) · **ADAPTER** (wrap behind a clean interface) ·
**MISSING** (build new) · **FROZEN** (outcome-bearing; never modified).

## Components

### ExecutionGate — `execution_gate/`
- **Responsibility:** "can this provider-model-request tuple execute?" (reachability, auth,
  billing, quota, region, residency, provider approval, features, context, cost, latency,
  reliability).
- **Inputs:** `Candidate` (declared facts + signals with evidence), `Request`, `now`.
- **Outputs:** `EligibilityDecision` (state + reason codes + per-condition evidence).
- **State owned:** none persistent (pure fn); executable registry holds records.
- **Authority:** eligibility only. **Reason codes:** `execution_gate.reason_codes.ReasonCode`.
- **Versioning:** `policy_version` on each decision (`exec_gate_v1`).
- **Status:** mutable code; its **replay_v1 evaluation is FROZEN**. **Reuse: UNCHANGED (import).**
- **Overlap/coupling risk:** none — clean boundary; must not absorb model choice or governance.

### Executable Registry — `execution_gate/registry.py`
- **Responsibility:** declared→enumerated→authenticated→execution-verified→eligible lineage.
- **State owned:** model records + execution status/telemetry. **Reuse: UNCHANGED.**

### ModelPolicy — `execution_gate/policy.py`
- **Responsibility:** "among ELIGIBLE candidates, which model?" (utility over quality/cost/latency).
- **Inputs:** selectable `(record, decision)` list + quality prior. **Outputs:** `Selection`.
- **Authority:** selection only; never routes to an ineligible model. **Reuse: UNCHANGED.**
- **Note:** the *scientific* selection engine is the **FROZEN** Model Selection Policy V1/V2; this
  is the thin reference selector. Do not conflate.

### Model Selection Policy Engine — `model_selection_pilot/`, `model_selection_experiment/`
- **Responsibility:** the researched selection policy (F1/F2/G, hard-quality gate, governance).
- **Status:** **FROZEN** (V1/V2 artifacts, manifests, results). **Reuse: ADAPTER (read-only reference).**
- Not invoked on the live path here; cited as the authoritative selection design.

### Shadow-pilot harness — `execution_gate_shadow/`
- **Responsibility:** advisory shadow prediction/observation capture, safety guards, dry run.
- **Status:** protocol + dry-run results are outcome-bearing (**do not reinterpret**). **Reuse: ADAPTER.**

### ActionGate — `ACTIONGATE_*.md`, `agentic/enterprise_governance/`, `experiments/actiongate_*`
- **Responsibility:** "may this exact action execute?" (policy, identity, authority, scope, live safety).
- **Status:** research docs + experimental code; **FROZEN research artifacts**. No clean importable API.
- **Reuse: ADAPTER** — wrap the *concept* (allow/deny/approve/constrain/escalate/indeterminate)
  behind `ActionGovernanceAdapter`; do not merge or modify.

### TAP / Assertion Governance — `truth_assurance_pipeline/`
- **Responsibility:** "what may the system assert?" (evidence-grounded validation of material claims).
- **Status:** experimental pipeline (tap_e1..e7); **FROZEN evaluation artifacts**. No unified API.
- **Reuse: ADAPTER** — wrap the *concept* (approve/qualify/revise/reject/escalate) behind
  `AssertionGovernanceAdapter`; do not merge or modify.

### Enterprise policy representation — scattered (registry `enterprise_policy`, ActionGate ontologies)
- **Responsibility:** approved providers, residency, action policy, approval requirements.
- **Reuse: ADAPTER** — normalized into the **Request Envelope** `policy_context` (Phase 4). **MISSING** as a
  single canonical object → built here.

### Provider adapters — `execution_gate/provider.py` (real, inert), `model_selection_pilot/provider.py`
- **Responsibility:** "how is the selected model called?" **Reuse: ADAPTER** (mock on the integration path).

### Action adapters — none
- **Responsibility:** "how is an approved action executed?" **Status: MISSING** → mock only, never live.

### Retry/fallback — `execution_gate` baselines (attempt sequences), `model_selection_pilot/execute.py`
- **Responsibility:** fallback ordering. **Reuse: ADAPTER** — fallback must **re-enter** eligibility+policy
  (invariant), not bypass. **Overlap risk:** naive retry can bypass exclusions → orchestrator forbids it.

### Telemetry / evidence registry — `execution_gate_shadow/records.py`, `model_selection_pilot/telemetry.py`
- **Responsibility:** observed outcomes; feed registry (prospective only). **Reuse: ADAPTER** — append-only.

### Reason-code taxonomies — `execution_gate/reason_codes.py`; ActionGate/TAP prose codes
- **Reuse: ADAPTER via namespaces** (Phase 7: `EXEC.* MODEL.* ASSERT.* ACTION.* RUNTIME.* AUDIT.* POLICY.*`).
  **Do not merge** existing codes; wrap under namespaces.

### Audit records / decision records — `execution_gate_shadow` JSONL; `model_selection_pilot` decision records
- **Reuse: ADAPTER** — unified append-only **Decision Record** (Phase 6) with hash chaining. **MISSING** as canonical.

### Frozen manifests / versioning — `execution_gate/frozen/replay_v1/MANIFEST.json`, V1/V2 manifests
- **Status: FROZEN.** Verified by `verify_frozen.py`. **Reuse: UNCHANGED (reference only).**

## Overlaps and unsafe-coupling risks (flagged, resolved in AUTHORITY_MATRIX.md)

1. **Enterprise policy** is currently expressed in three places (registry `enterprise_policy`,
   ActionGate ontologies, ad-hoc request fields) → single canonical `policy_context` owner needed.
2. **Reason codes** overlap across components → namespace strategy, not merge.
3. **Fallback/retry** could bypass eligibility → invariant + orchestrator control needed.
4. **Cost/latency** appear in both ExecutionGate (constraint) and ModelPolicy (objective) → distinct roles
   (hard ceiling vs preference), single owner each.
5. **Telemetry → eligibility feedback** risks circularity → prospective-only registry updates.
