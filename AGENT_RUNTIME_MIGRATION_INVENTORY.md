# Agent Runtime Migration — Inventory (Deliverable 1)

Inventory of the legacy `agentic/agentic_framework/` (45 modules) produced **before** any migration
code was written. Classification is grounded in direct reads; the machine-readable form is
`agent_runtime_migration_inventory.json`.

Labels: `FACT` (read from source).

## Classification key
`REUSE_UNCHANGED` · `REUSE_WITH_WRAPPER` · `PORT_WITH_CHANGES` · `REIMPLEMENT_FROM_CONTRACT` may enter
the migration package. `EXCLUDE_DUPLICATE_GOVERNANCE` · `EXCLUDE_RESEARCH_ONLY` · `OTHER` may not.

## The legacy execution path (why a clean rebuild, not a copy)
`FACT`. `AgenticLLMWrapper.run` (agent.py:384) decomposes the goal, then `_execute_actions`
(agent.py:1763) filters actions by a SafetyGate allow-list and routes each through
`_dispatch_via_mcp` → `SafeMCPGateway`, which returns `GatewayDecision.ALLOWED/BLOCKED` — a
**runtime-owned authorization**. That decision, plus approval enforcement, confidence gating, and the
governance service, is exactly what the frozen boundary moves to ActionGate/ACP. So `agent.py` is
`REIMPLEMENT_FROM_CONTRACT` (rebuild the loop as a proposer), not a copy.

## What enters the migration package
| Module | Subsystem | Class | New responsibility |
|---|---|---|---|
| `goal_decomposition.py` | goals + decomposition | REIMPLEMENT | `contracts.Goal` / `planning.decomposition` |
| `agent.py` (loop) | runtime loop | REIMPLEMENT | `runtime.runtime` proposer loop |
| `agent_builder.py` | factory | REIMPLEMENT | `build_runtime()` |
| `memory_store.py` | memory | REIMPLEMENT | `memory.working` / `memory.episodic` |
| `reflective_loop.py` | reflection | REIMPLEMENT | `reasoning.reflection` |
| `reasoning_workflows.py` | reasoning + workflow | PORT | `reasoning.reasoner` / `workflow` (no governance) |
| `tool_discovery.py` + `mcp_gateway.ToolRiskLevel` | tool registry | PORT/REIMPLEMENT | `tools.registry` with **trusted** risk class |
| `cancellation.py` | cancellation | REUSE_WITH_WRAPPER | `runtime.cancellation` |
| `token_budget.py` | budgets | REUSE_WITH_WRAPPER | `runtime.budget` (advisory) |
| `tracing.py` / `streaming_events.py` / `trace_viewer.py` | tracing | PORT | `tracing.events` / `trace` / `sink` |
| `structured_output.py` | reasoning | PORT | optional structured parsing |
| `proactive_scheduler.py` | workflow | PORT | `workflow.scheduler` |
| `llm_adapters.py` (`BaseLLMAdapter`, `MockLLMAdapter`, OpenAI/Anthropic) | adapter | PORT | `contracts`/adapter interface (**exclude CG variants**) |
| `validate.py` | proposal validation | PORT | `proposal` completeness checks (never authorization) |
| `memory_retention.py` | memory | PORT | memory policy |
| `request_enrichment.py` | reasoning (advisory) | PORT | advisory proposal evidence |

New, with no legacy source: **`proposal.cer_builder`** (native CER over the frozen `cer_v0_3`),
**`control_plane` client + governed executor** (narrow boundary to the frozen control plane).

## What must NOT enter
`FACT`.
- **Authoritative allow/deny:** `mcp_gateway.py` (SafeMCPGateway `GatewayDecision`),
  `safety_contract.py` (SafetyGate `eligible`), `confidence_gate.py`, `governance_service.py`,
  `governance_adapter.py`, `governance_api.py`, `governance_models.py` — **EXCLUDE_DUPLICATE_GOVERNANCE**.
  (SafeMCPGateway's *risk taxonomy* is reimplemented cleanly as data in `tools.registry`; its
  *decision* is dropped.)
- **Approval enforcement:** `approval.py`, `approval_workflow.py`, `approval_coverage.py` — approvals
  bind in ActionGate now. The runtime only *requests* human input.
- **Policy enforcement / replay:** `policy_bundle.py`, `policy_replay.py`, `domain_policy.py`,
  `adaptive_policy.py`, `duration_policy.py` — **EXCLUDE_DUPLICATE_GOVERNANCE**.
- **Research-only signal governance:** `jepa_governance.py`, `cg_tool_dispatcher.py`,
  `sovereign_bridge.py`, `coherence_tracker.py`, `signal_config.py`, `shadow_ai.py`,
  `inference_mistral.py`, `olm_bridge.py`, `local_critic.py`, `benchmark_critics.py` —
  **EXCLUDE_RESEARCH_ONLY**. A forbidden-import test enforces their absence from the production runtime.
- **Not runtime code:** `examples.py`, `adaptive_prompts.py` — **OTHER** (not migrated this milestone).

## Active/valid implementation per required subsystem
See `agent_runtime_migration_inventory.json → active_valid_per_subsystem`. Every subsystem the
milestone lists (goals, planning, decomposition, reasoning, memory, reflection, workflow, tool
registry, tool selection, retries, cancellation, budgets, human interaction, observations,
trace/events, adapter abstraction, CER generation) has an identified source and a migration class;
CER generation is **new/native** over the frozen contract.

## Migration confidence
- **High:** contracts, CER builder, control-plane client, governed executor, memory, tracing,
  cancellation, budget, tool registry (clean rebuilds against a frozen contract).
- **Medium:** planning/decomposition and reflection (behaviorally reimplemented; validated by the
  scenario suite in Commit F).
- **Excluded with high confidence:** all governance-authority and research-only modules (they
  contradict the frozen boundary by construction).
