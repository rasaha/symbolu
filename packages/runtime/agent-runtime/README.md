# Ugence Agent Runtime (`ugence-agent-runtime`)

A **domain-neutral coordination runtime** for agent and workflow execution.

The Agent Runtime drives task and workflow lifecycle, invokes providers/tools, and
applies retry, timeout, cancellation, checkpointing, and durable recovery. Before any
*consequential* transition it asks an external, neutral **governance boundary** whether
the transition may proceed, and it obeys the answer.

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
pip install dist/ugence_agent_runtime-0.1.0-py3-none-any.whl
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
| `CLEAR` | continue — invoke the provider |
| `HOLD` | task `WAITING`, workflow `WAITING` (no provider call, no authority) |
| `BLOCK` | task `FAILED`, workflow `FAILED` (no provider call) |
| `ESCALATE` | task `WAITING`, workflow `PAUSED` (external resolution required) |

The default hook is a neutral no-op (always `CLEAR`); concrete Ugence governance
adapters live in **separate, optional** packages and are never required to import the
core.

## Documentation

See [`docs/`](docs/) — overview, package boundary, public API, state model, provider
interface, persistence, recovery, governance integration, compatibility, security,
limitations, and H22 readiness. Machine-readable contracts are in
[`artifacts/`](artifacts/).

## Status

`0.1.0` — first independent distribution. Single-workflow coordination only.
**Multi-workflow orchestration (H22) is a later feature phase and is not implemented
here.**
