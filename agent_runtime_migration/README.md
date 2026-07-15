# Agent Runtime (migration package)

**Specialized AI System · proposer, not governor.** A new, additive runtime built to the frozen
architectural boundary:

> The runtime converts a goal and observations into a **governed execution request (CER)**, submits
> it to the **AI Control Plane**, and consumes the execution result to continue reasoning. It never
> makes its own authoritative allow/deny decision.

## Ownership boundary (frozen)
| Agent Runtime owns | AI Control Plane owns (frozen, not in this package) |
|---|---|
| planning, decomposition, reasoning, memory, reflection | authorization (ActionGate) |
| workflow orchestration, tool selection, retries, cancellation | operational safety (ACP) |
| human interaction, observation processing | execution eligibility, replay protection, exact-action binding |
| **native CER generation** | approvals, policy enforcement, commit-time validation |

CER is the boundary. This package imports the **frozen** CER (`cer_v0_3`) and control plane
(`cer_v0_3.control_plane`) — it does not reimplement or modify them.

## The loop
```
Goal → Plan → Select action → Build CER → Submit to AI Control Plane
     → Receive governance result → (if eligible) governed executor runs the tool
     → Receive execution observation → Update memory → Reflect
     → Continue / stop / replan / request human input
```

## Layout
```
contracts/     typed Goal / Plan / Action / Observation / Result / errors
runtime/       lifecycle, state, cancellation, retry, budget, the loop
planning/      planner, decomposition, policies
reasoning/     reasoner, reflection, uncertainty (advisory only)
memory/        working + episodic memory, persistence interface
tools/         registry, selection, invocation, local_tool_policy (trusted risk class)
workflow/      workflow, step, scheduler, checkpoint
proposal/      cer_builder, cer_adapter, proposal_evidence, identity_bridge  (native CER)
control_plane/ client, governed_executor, decision_adapter, execution_receipt  (narrow boundary)
observation/   adapter, result_ingestion, memory_update
tracing/       events, trace, sink
compatibility/ legacy_adapter, legacy_imports, warnings  (additive shim; no duplicate authority)
tests/         unit / integration / compatibility / forbidden-import
benchmark/     deterministic old-vs-new scenario suite
```

## Non-goals (hard constraints)
- No authoritative allow/deny inside the runtime.
- No duplicate ActionGate/ACP logic; no execution-token minting; no commit-time validation.
- No research-only signal imports (CG / JEPA / vritti / sovereign / entropy governance).
- No direct tool execution around the governed executor in governed mode.
- The legacy `agentic/agentic_framework/` package is untouched and remains the rollback source.

## Status
Migration build in progress. Public API exports only validated modules; placeholders are marked
`NOT_EXPORTED` / `NOT_FOR_PRODUCTION` and are not re-exported from package `__init__`.
