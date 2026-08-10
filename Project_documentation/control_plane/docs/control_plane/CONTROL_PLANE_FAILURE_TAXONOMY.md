# Control-Plane Failure & Conflict Taxonomy

*Phase 7. Failures specific to the **integrated** system — distinct from any single
component's internal reason codes. Existing component codes are NOT merged; they are
wrapped under namespaces. Source of truth: `control_plane/failure_codes.py`
(`Failure` enum + `FAILURE_META`); this table is generated from it and must match.*

## Namespace strategy

Each existing component keeps its own vocabulary; the control plane reaches them only
through a namespace prefix, so provenance is never lost and no two components collide:

| Namespace | Owner domain | Example |
|---|---|---|
| `EXEC.*` | Execution eligibility (ExecutionGate) | `EXEC.NO_ELIGIBLE_MODEL` |
| `MODEL.*` | Model selection (ModelPolicy) | `MODEL.SELECTED_MODEL_NOT_ELIGIBLE` |
| `ASSERT.*` | Assertion governance (TAP) | `ASSERT.ASSERTION_REJECTED` |
| `ACTION.*` | Action governance (ActionGate) | `ACTION.ACTION_DENIED` |
| `RUNTIME.*` | Provider/action execution & runtime | `RUNTIME.PROVIDER_EXECUTION_FAILED` |
| `AUDIT.*` | Audit / telemetry integrity | `AUDIT.AUDIT_CHAIN_BROKEN` |
| `POLICY.*` | Policy / version / contract | `POLICY.POLICY_VERSION_MISMATCH` |

A component's raw reason code is carried inside the namespaced code's evidence, never
re-emitted bare. Only `ProviderAdapter` may read raw provider errors and it normalizes
them to `RUNTIME.*` (invariant 14); a raw provider error crossing any other boundary is
itself a failure: `AUDIT.RAW_PROVIDER_ERROR_LEAKED`.

## Failure map

owning = component accountable for handling it · originating = where it arises ·
recover = trace can recover (vs terminal) · retry = retry-eligible · escalate =
requires escalation/human path. **Every** control-plane failure is fail-closed.

| Code | Owning | Originating | Severity | Recover | Retry | Escalate | Fail-mode |
|---|---|---|---|---|---|---|---|
| `RUNTIME.UPSTREAM_EXCLUSION_BYPASSED` | Orchestrator | any | critical | no | no | yes | fail-closed |
| `EXEC.NO_ELIGIBLE_MODEL` | ExecutionGate | ExecutionGate | high | yes | no | no | fail-closed |
| `POLICY.POLICY_VERSION_MISMATCH` | PolicyContext | any | high | yes | no | no | fail-closed |
| `POLICY.REGISTRY_VERSION_MISMATCH` | PolicyContext | any | high | yes | no | no | fail-closed |
| `POLICY.CONTRACT_VERSION_UNSUPPORTED` | Orchestrator | any | high | no | no | no | fail-closed |
| `EXEC.STALE_ELIGIBILITY_EVIDENCE` | ExecutionGate | ExecutionGate | medium | yes | yes | no | fail-closed |
| `MODEL.INVALID_SELECTION_INPUT` | ModelPolicy | ExecutionGate | high | no | no | no | fail-closed |
| `MODEL.SELECTED_MODEL_NOT_ELIGIBLE` | Orchestrator | ModelPolicy | critical | yes | no | yes | fail-closed |
| `RUNTIME.PROVIDER_EXECUTION_FAILED` | ProviderAdapter | Provider | medium | yes | yes | no | fail-closed |
| `ASSERT.ASSERTION_REJECTED` | Assertion | Assertion | high | no | no | yes | fail-closed |
| `ASSERT.ASSERTION_CONSTRAINED` | Assertion | Assertion | medium | yes | no | no | fail-closed |
| `ASSERT.ASSERTION_ESCALATED` | Assertion | Assertion | medium | yes | no | yes | fail-closed |
| `ACTION.ACTION_PROPOSAL_INVALID` | ActionProposalLayer | ActionProposalLayer | medium | no | no | no | fail-closed |
| `ACTION.ACTION_DENIED` | ActionGate | ActionGate | high | no | no | yes | fail-closed |
| `ACTION.ACTION_CONSTRAINED` | ActionGate | ActionGate | medium | yes | no | no | fail-closed |
| `ACTION.ACTION_APPROVAL_REQUIRED` | ActionGate | ActionGate | high | yes | no | yes | fail-closed |
| `RUNTIME.ACTION_EXECUTION_FAILED` | ActionAdapter | ActionAdapter | high | yes | yes | yes | fail-closed |
| `AUDIT.TELEMETRY_WRITE_FAILED` | Telemetry | Telemetry | medium | yes | yes | no | fail-closed |
| `AUDIT.AUDIT_CHAIN_BROKEN` | Audit | Audit | critical | no | no | yes | fail-closed |
| `ACTION.HUMAN_AUTHORITY_UNRESOLVED` | ActionGate | Human | high | yes | no | yes | fail-closed |
| `POLICY.POLICY_CONFLICT` | PolicyContext | any | high | no | no | yes | fail-closed |
| `RUNTIME.GOVERNANCE_COMPONENT_UNAVAILABLE` | Orchestrator | Assertion\|ActionGate | high | yes | no | yes | fail-closed |
| `AUDIT.UNAUTHORIZED_OVERRIDE` | Audit | any | critical | no | no | yes | fail-closed |
| `AUDIT.RAW_PROVIDER_ERROR_LEAKED` | Orchestrator | ProviderAdapter | high | no | no | yes | fail-closed |
| `POLICY.DATA_FLOW_NOT_APPROVED` | PolicyContext | any | critical | no | no | yes | fail-closed |
| `POLICY.REPLAY_VERSION_MISMATCH` | ReplayEngine | ReplayEngine | medium | no | no | no | fail-closed |
| `AUDIT.TRACE_INCOMPLETE` | Audit | Orchestrator | high | no | no | yes | fail-closed |
| `RUNTIME.CIRCULAR_DEPENDENCY_DETECTED` | Orchestrator | Telemetry | critical | no | no | yes | fail-closed |

## Recoverable vs terminal

- **Recoverable** failures permit a *bounded* re-entry: `EXEC.STALE_ELIGIBILITY_EVIDENCE`
  and `RUNTIME.PROVIDER_EXECUTION_FAILED` re-enter eligibility+policy (invariant 19); they
  never silently retry in place. Recovery is capped, and each attempt is its own audited
  decision.
- **Terminal** failures end the trace with an audited outcome and no execution.
  `MODEL.SELECTED_MODEL_NOT_ELIGIBLE`, `RUNTIME.UPSTREAM_EXCLUSION_BYPASSED`, and
  `AUDIT.*` integrity failures are terminal *and* escalate — they signal an integration
  defect, not an ordinary rejection.

## Distinctions that this taxonomy protects

- **Assertion vs action.** `ASSERT.ASSERTION_REJECTED` (may-state) is separate from
  `ACTION.ACTION_DENIED` (may-do). A rejected assertion never produces an action; an
  approved assertion never implies an approved action (invariants 4, 5, 17).
- **Eligibility vs selection.** `EXEC.NO_ELIGIBLE_MODEL` (nothing *can* run) is separate
  from `MODEL.SELECTED_MODEL_NOT_ELIGIBLE` (selection escaped the eligible set — an
  integration bug, invariant 1).
- **Execution vs governance.** `RUNTIME.PROVIDER_EXECUTION_FAILED` (technical) never
  substitutes for a governance verdict; a technically-successful call can still fail
  assertion governance (invariant 4).
