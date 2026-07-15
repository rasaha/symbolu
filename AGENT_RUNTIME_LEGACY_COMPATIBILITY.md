# Agent Runtime — Legacy Compatibility (Deliverable 6)

The additive compatibility layer (`agent_runtime_migration/compatibility/`) lets existing
`agentic/agentic_framework` callers move onto the migration runtime without a rewrite of their
*proposal* code — while **removing** the runtime's old governance authority.

Labels: `FACT` (implemented/tested).

## Design: duck-typed, no legacy import
`FACT`. The compatibility layer **does not import** `agentic.agentic_framework` (its package
`__init__` pulls research-signal code — `coherence_tracker`, `sovereign_bridge`). It accepts
legacy-*shaped* objects (attributes or dict keys: `purpose`, `purpose_type`, `actions`, and per
action `action_id`/`action_type`/`parameters`) and converts them to the new `Goal`/`Action`
contracts. The forbidden-import test proves no legacy/research module is loaded when the migration
package is imported.

## Supported legacy APIs
`FACT`.
- **Legacy `GoalState`/`ActionItem` shapes** → `compatibility.to_goal(...)` / `to_action(...)`
  (new `Goal` carrying a plan of `Action`s). Emits `AgentRuntimeDeprecationWarning`.
- **Local read-only action types** (formatting, parsing, read-only retrieval) → `LOCAL_READ_ONLY`
  actions that run the policy-permitted fast path.
- **Governed action types** (`kubernetes.scale`, `kubernetes.rollout`, `database.mutation`) →
  `GOVERNED_CONSEQUENTIAL` actions routed through **CER → AI Control Plane → governed executor**,
  provided the legacy action carries the CER envelope sections in its `parameters`.
- **Mock adapters / any `.call(prompt)->str` adapter** → supported by duck typing (no adapter
  rewrite needed to evaluate).

## Unsupported legacy APIs (fail explicitly, never silently)
`FACT`.
- **All legacy governance authority** — `SafetyGate`, `SafeMCPGateway`, `GovernanceService`,
  `ConfidenceGate`, `ApprovalController`/`ApprovalStore`, `GatewayDecision`, `policy_control_plane`.
  `compatibility.get_legacy(name)` **refuses** them with a `GovernanceBoundaryError` pointing to the
  AI Control Plane. They are *not* re-exposed.
- **A governed legacy action missing CER envelope sections** — conversion raises `ContractError`
  ("cannot be migrated: missing actuation/authority/state_binding/policy_ref"). Legacy governed
  actions must be re-expressed as CERs; they are never silently executed.
- **Research-signal governance paths** (CG/JEPA/vritti/sovereign/confidence gating as authority) —
  not migrated; absent from the production package (forbidden-import test).

## Semantic differences (important)
`FACT`.
- **Governance moved out of the runtime.** The legacy runtime returned its own `ALLOWED/BLOCKED`
  (SafeMCPGateway) and `eligible` (SafetyGate). The migration runtime returns **no** authoritative
  allow/deny; eligibility comes only from the AI Control Plane. A legacy caller that inspected the
  gateway decision now inspects the `GovernanceDecision` from `ControlPlaneClient`.
- **Approvals are the control plane's.** Legacy per-action approval enforcement is replaced by the
  runtime *requesting* human input and the control plane *binding* approvals to the action hash.
- **Uncertainty is advisory only.** Confidence/entropy signals may raise scrutiny; they never gate.

## Deprecation timeline & removal criteria
`INTERPRETATION` (recommended; not executed this milestone — the legacy package is untouched).
- **Now:** legacy package remains the rollback source; compatibility layer emits deprecation warnings.
- **Phase 1:** new integrations use `agent_runtime_migration` directly; compatibility used only for
  in-flight legacy callers.
- **Phase 2 (removal criteria, all required):** (a) all in-flight callers migrated to the new
  contracts; (b) the migration scenario suite passes for every migrated workflow; (c) the governance
  boundary tests are green in CI; (d) a rollback has not been needed for a full release cycle. Only
  then is the legacy `agentic/agentic_framework` package a candidate for archival — behind a separate,
  reviewed change, never in this milestone.

## Rollback
`FACT`. The legacy package is **untouched**. Reverting to it requires no data migration; the
compatibility layer is additive and can be removed independently.
