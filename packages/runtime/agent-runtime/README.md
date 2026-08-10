# Ugence Agent Runtime (`ugence-agent-runtime`)

A **domain-neutral execution-coordination kernel** for agent and workflow execution.

> **Scope note.** This is a *newly created coordination kernel*, not a relocation of the
> legacy `agent_runtime_migration` proposer (which owns planning, reasoning, and memory
> and remains a separate, coexisting package). The kernel intentionally excludes agent
> planning/reasoning/memory. See
> [`docs/AGENT_RUNTIME_POST_MERGE_FIDELITY_AUDIT.md`](docs/AGENT_RUNTIME_POST_MERGE_FIDELITY_AUDIT.md).
>
> **Maturity:** `IMPLEMENTED_AND_OFFLINE_VERIFIED` (plus a scoped CI job). Not
> live-verified, pilot-validated, enforcement-ready, or production-ready.

The kernel drives task and workflow lifecycle, invokes providers/tools, and applies
retry, timeout, cancellation, checkpointing, and durable recovery. Before any
*consequential* transition it constructs an immutable proposal and asks an external,
neutral **governance boundary** whether that exact proposal may proceed — and it obeys
the answer. **With no governance adapter configured, consequential transitions fail
closed.**

> **The runtime coordinates execution. It never creates governance authority, authors
> policy, authorizes actions, or mints execution clearance.**

```
applications / products
        ↓
optional integration adapters (providers, concrete governance)
        ↓
ugence-agent-runtime           ← this package (stdlib-only, neutral)
        ↓
neutral contracts and utilities
```

## What it is / is not

| Owns (coordination) | Does **not** own |
| --- | --- |
| task & workflow lifecycle, step coordination | policy authorship, binding decisions |
| provider/tool invocation interfaces | ActionGate authorization, Action Clearance |
| retry / timeout / cancellation | assertion governance, evidence admissibility |
| checkpoints & durable recovery | GitHub / financial / healthcare specifics |
| runtime events, tracing, correlation | a particular LLM provider or agent framework |
| the neutral governance-integration boundary | one persistence backend, one governance impl |

## Install

```bash
python -m build packages/runtime/agent-runtime
pip install dist/ugence_agent_runtime-0.2.0-py3-none-any.whl
```

The core has **no third-party dependencies** — it is stdlib-only. Importing it is
side-effect free (no sockets, no threads, no credentials, no scheduler, no recovery).

## Quick start

```python
from ugence_agent_runtime.api import (
    create_runtime, AgentRuntimeConfig, WorkflowDefinition, TaskDefinition,
)
from ugence_agent_runtime.providers.interfaces import ToolResult

class EchoProvider:
    provider_id, version = "echo", "1.0.0"
    def execute(self, invocation):
        return ToolResult(provider_id="echo", operation=invocation.operation,
                          ok=True, output=invocation.arguments)

rt = create_runtime(AgentRuntimeConfig())
rt.config.provider_registry.register(EchoProvider())

wf = WorkflowDefinition(workflow_id="hello", tasks=(
    TaskDefinition(task_id="t1", operation="echo", provider_id="echo",
                   arguments={"msg": "hi"}, consequential=False),
))
inst = rt.start_workflow(wf)
print(inst.status.value)            # COMPLETED
```

## Governance boundary

The runtime asks an injected `GovernanceHook` and maps the disposition — never
broadening it:

| Disposition | Runtime behavior |
| --- | --- |
| `CLEAR` | continue — **only if** the result is bound to the exact proposal (fingerprint + reference, not expired); otherwise fail closed |
| `HOLD` | task `WAITING`, workflow `WAITING` (no provider call, no authority) |
| `BLOCK` | task `FAILED`, workflow `FAILED` (no provider call) |
| `ESCALATE` | task `WAITING`, workflow `PAUSED` (external resolution required) |

The **default** hook (`UnconfiguredGovernanceHook`) **fails closed** — it BLOCKs every
consequential transition with reason `GOVERNANCE_NOT_CONFIGURED`. An always-CLEAR hook
(`AllowAllGovernanceHook`) exists only as an explicit, opt-in, documented-unsafe testing
helper and is never a default. Concrete Ugence governance adapters live in **separate,
optional** packages and are never required to import the core.

## Canonical execution state

The runtime is the **canonical owner of execution-trajectory identity**. For each task
it derives an immutable, versioned, integrity-protected `CanonicalExecutionState`
snapshot — workflow/task identity, correlation/causation, agent/plan lineage
*references*, runtime status, the active `TransitionProposal` fingerprint, external
authority *references* governance produced, artifact lineage *references*, and a SHA-256
`state_digest`. It records the trajectory; it never authors policy, mints authority,
selects agents, or duplicates the proposal's action payload. Read it with
`runtime.execution_state(instance_id, task_id)`. See
[`docs/AGENT_RUNTIME_CANONICAL_EXECUTION_STATE.md`](docs/AGENT_RUNTIME_CANONICAL_EXECUTION_STATE.md).

> Agents may hold independent reasoning contexts, but consequential execution has **one**
> canonical authoritative execution state — owned by the runtime, not the agent brain and
> not the authority engine.

## Documentation

See [`docs/`](docs/) — overview, package boundary, public API, state model, canonical
execution state, provider interface, persistence, recovery, governance integration,
compatibility, security, limitations, and H22 readiness. Machine-readable contracts are
in [`artifacts/`](artifacts/).

## Status

`0.2.0` — adds canonical execution state (deterministic, versioned, integrity-protected,
runtime-owned execution-trajectory identity; additive public API + a `checkpoint_version`
boundary for execution-state lineage) on top of the first independent distribution, the
post-merge governance-safety correction (0.1.1), and exact-action contract hardening
(0.1.2). No change to exact-action fingerprint semantics, governance ownership, or the
digest semantics of existing checkpoints. Single-workflow coordination only. Maturity:
`IMPLEMENTED_AND_LOCALLY_OFFLINE_VERIFIED` (promoted to `IMPLEMENTED_AND_CI_VERIFIED` once
the scoped GitHub Actions run is observed passing). **Multi-workflow orchestration (H22)
is a later feature phase, not implemented here.**
