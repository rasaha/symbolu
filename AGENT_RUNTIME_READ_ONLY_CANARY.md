# Agent Runtime — Read-Only Canary (Deliverable 4)

A narrowly scoped canary limited to TRUSTED read-only tools. Grounded in
`agent_runtime_migration/canary/`.

Labels: `FACT` (implemented/tested).

## Scope (§6)
`FACT`. The canary registry (`ReadOnlyRegistry`) **refuses** to register anything that is not a
policy-permitted `LOCAL_READ_ONLY` tool. Permitted tools: repository search, document retrieval,
deterministic parsing, metadata inspection — no write/delete/execute/privileged tool. Consequential
tools are **not** in the canary; they remain shadow-only through CER → ActionGate → ACP elsewhere.

## Requirements — all met
| Requirement | How | Test |
|---|---|---|
| Risk class from the trusted registry | `ReadOnlyRegistry` sets `LOCAL_READ_ONLY`; rejects governed | `test_canary_refuses_governed_tool` |
| No write/delete/execute/privileged tool | governed tool registration raises `ToolPolicyError` | `test_canary_cannot_invoke_write_handler` |
| Kill switch | `KillSwitch.engage()` cancels the run | `test_canary_kill_switch` |
| Bounded runtime | step budget + iteration cap | `test_canary_budget_bound` |
| Cancellation | cancellation token honored | `test_canary_kill_switch` |
| Full trace | `RunTrace` with OBSERVED events | `test_canary_runs_read_only_task` |
| Observation return | observations recorded to memory | `test_canary_runs_read_only_task` |
| Fallback to legacy runtime | explicit `legacy_fallback` callable | `test_canary_explicit_fallback_only` |
| No SILENT fallback after failure | fallback only when `allow_fallback=True`, and audited | `test_canary_explicit_fallback_only` |

## Fallback semantics (§6)
`FACT`. On a new-runtime exception the canary does **not** silently fall back. Without
`allow_fallback`, it returns `status="error"` and the legacy runtime is **not** called. With
`allow_fallback=True` and a `legacy_fallback` provided, it calls the legacy runtime **explicitly** and
records an auditable `fallback_reason` (the new-runtime error). Fallback is always explicit and logged.

## Result
`FACT`. Read-only task success, kill-switch stop, budget stop, cancellation, and explicit/no-silent
fallback all pass (7 canary/parity tests). Unauthorized-handler invocations: **0** (governed tools
cannot be registered in the canary). This supports `READY_FOR_READ_ONLY_CANARY` (read-only scope,
consequential tools shadow-only).
