# Agent Runtime — Direct-Execution Bypass Audit (Deliverable 5)

Audit of every path in the new runtime for a way to execute a **governed consequential** tool
outside `GovernedExecutor`. Conclusion: **no bypass exists**; every governed tool call goes through
the governed executor, which runs the tool only on a control-plane execution reference.

Labels: `FACT` (code-audited + tested).

## Audit surface (§7)
| Path | Finding | Why it cannot bypass | Evidence |
|---|---|---|---|
| **Direct handler calls** | Tool handlers live in `ToolRegistry.RegisteredTool.handler` and are invoked only by `tools.invocation.invoke_local`, which is called **only** inside `GovernedExecutor`. The runtime loop holds an `ActionExecutor` (the governed executor), never the handlers. | The loop has no reference to a handler; it can only call `executor.execute(action)`. | `test_tools_and_execution` (governed DENY/HOLD/PENDING → tool unrun) |
| **Workflow callbacks** | `WorkflowScheduler.run` executes each step via the injected executor (`executor.execute`). | Same governed executor; no direct handler path. | `test_workflow_scheduler_orders_and_checkpoints` |
| **Compatibility adapters** | `compatibility.legacy_adapter` only converts legacy shapes to `Action`s; it never executes and holds no handler. Governed legacy actions become `GOVERNED_CONSEQUENTIAL` routed through CER. | Conversion ≠ execution; execution still requires the governed executor. | `test_compatibility` |
| **Retry handlers** | A `RETRY` re-invokes `executor.execute(action)` (bounded by `ResolutionBudget`); an optional refresh hook only rebuilds the *action* (new CER identity). | Retry re-enters the governed executor; it never calls a handler directly. | `test_execution_failure_retry_within_budget_then_succeeds`, `test_iteration_cap_prevents_runaway` |
| **Reflection actions** | `Reflector`/`ModelReasoner` produce a decision + advisory text; they never touch tools. | No execution surface. | `test_runtime_core` |
| **Local tool paths** | The fast path runs a tool only if the **trusted registry** marks it `LOCAL_READ_ONLY` **and** `fast_path_permitted`; a governed tool mis-declared local fails closed. | `resolve()` fails closed on risk-class disagreement; the registry (not the model) wins. | `test_model_cannot_reclassify_governed_tool_as_local`, `test_inv13_write_capable_governed_tool_cannot_take_fast_path` |
| **Exception fallbacks** | On a tool exception the governed executor returns a `failed` `ExecutionResult` (`executed=False`); there is no silent alternate execution and no fallback handler. | Failure is observed, not routed around. | `test_execution_failure_*` |
| **Model output** | Model-proposed `risk`/`authorized`/`eligible`/`execution_reference` fields are ignored; risk class comes from the registry; eligibility from the control plane. | The model cannot self-classify or self-authorize. | `test_inv1_*`, `test_inv2_*` |

## Structural guarantee
`FACT`. The governed executor runs a governed tool only when `decision.eligible` **and**
`decision.execution_reference` are present, and only after re-asserting exact-action binding
(`assert_binding` + `decision.cer_digest == proposed identity`). `ControlPlaneClient.
ensure_not_self_authorized` rejects an "eligible" decision lacking a control-plane reference. There
is no code path where a `GOVERNED_CONSEQUENTIAL` tool handler is invoked outside `GovernedExecutor`.

## Result
`FACT`. Governance-boundary violations across the security + benchmark suites: **0**. Bypass attempts
(governed-as-local reclassification, model self-authorization, direct handler access) are all blocked
and tested. No governed consequential tool can execute outside `GovernedExecutor`.
