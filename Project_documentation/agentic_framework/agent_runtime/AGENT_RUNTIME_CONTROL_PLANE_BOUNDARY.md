# Agent Runtime — AI Control Plane Boundary (Deliverable 5)

The narrow interface between the Agent Runtime (proposer) and the frozen AI Control Plane
(governor). Grounded in `agent_runtime_migration/control_plane/` and `proposal/`.

Labels: `FACT` (implemented/tested).

## 1. What the runtime submits
`FACT`. A **CER**, built natively by `proposal/cer_builder.build_cer` over the **frozen** `cer_v0_3`
contract. The builder fails closed on an incomplete/invalid CER before submission. Runtime
provenance is carried in `provenance` and is **excluded from the CER action identity** (v2 profile).
Supported profiles are exactly the frozen ones: `kubernetes.scale.v1`, `kubernetes.rollout.v1`,
`database.mutation.v1`.

## 2. What the control plane returns (structured, separated)
`FACT`. `ControlPlaneClient.submit` returns a `GovernanceDecision` with **separated** fields:
- `actiongate_authorization` — ActionGate outcome (ALLOW / ALLOW_WITH_CONSTRAINTS / DENY / …);
- `acp_operational_safety` — ACP recommendation/decision;
- `composed_eligibility` — PROCEED / BLOCKED_BY_AUTHORIZATION / PENDING_AUTHORIZATION / HELD_BY_ACP;
- `eligible` + `execution_reference` — the reference is present **only** when eligible;
- `required_next_step` — execute / replan_or_stop / provide_evidence_or_request_human / wait_or_reobserve / stop;
- `reason_codes`, `trace_ref`.

It is a thin wrapper over `cer_v0_3.control_plane.run_control_plane` — no policy, no re-decision.

## 3. What the runtime MAY do
`FACT`. Replan, request evidence, request human input, wait/reobserve, stop, or reflect — driven by
`required_next_step` (`control_plane/decision_adapter.py`, pure interpretation of the frozen outcome
set).

## 4. What the runtime MAY NOT do (enforced)
`FACT`. Override ActionGate or ACP; treat an ACP hold as authorization; treat an ActionGate allow as
operational safety; mint an execution token; or execute around the governed executor. Guards:
- `ControlPlaneClient.ensure_not_self_authorized` rejects an "eligible" decision lacking a
  control-plane execution reference.
- `ExecutionReceipt.permits_execution` is true **only** for `PROCEED` **and** a present
  `execution_reference`.
- `proposal/identity_bridge.assert_binding` fails closed if a CER is modified after a decision
  (a modified action invalidates a prior decision — tested).

## 5. Risk-tiered execution paths
`FACT` (paths defined here; enforcement wired in Commit D's governed executor + tool registry).
- **Governed consequential** (`RiskClass.GOVERNED_CONSEQUENTIAL`): Kubernetes mutation, database
  mutation, financial/write/delete, privileged. **Must** pass CER → AI Control Plane → governed
  executor. The `Action` contract requires a CER profile for this class.
- **Low-risk local/read-only** (`RiskClass.LOCAL_READ_ONLY`): formatting, deterministic parsing,
  read-only retrieval where policy explicitly permits. May run on a local fast path with no CER.
  The **risk class comes from the trusted tool registry / policy — never from the model** (the
  `Action.risk_class` field is a `RiskClass`, set by the registry, not parsed from model output).

### Fast paths that remain local — and why they do not bypass governance
`FACT`. A local fast path is permitted **only** for tools the trusted registry classifies
`LOCAL_READ_ONLY` and that perform **no consequential actuation** (no external write/delete, no
privileged effect, no state mutation). They touch nothing an enterprise needs to authorize, so
running them locally is not a governance bypass. Any tool that actuates is `GOVERNED_CONSEQUENTIAL`
by registry classification and cannot use the fast path. The model cannot reclassify a tool.

## 6. Determinism
`FACT`. The client is deterministic — the caller supplies `now`; no wall clock, no randomness. Tested
across PROCEED / DENY / HELD_BY_ACP / PENDING outcomes against the real frozen control plane.
