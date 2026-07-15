# Deliverable 4 — Runtime Capabilities

The capability set of Agent Runtime V2, each mapped to what exists today, what its V2 form is, and whether it is a gap. "Exists" claims are `FACT` from the prior review's source reads; targets are `RECOMMENDATION`.

Design rule enforced throughout: **a capability that is really a governance concern is delegated, not built.** Only runtime capabilities appear here.

---

## 1. Capability catalog

| Capability | Today (FACT) | V2 form (RECOMMENDATION) | Status |
|---|---|---|---|
| **Planning** | `goal_decomposition.decompose_goal` — LLM plan with rule fallback | Add plan revision on `DENY`/`HOLD` verdicts; explicit dependency DAG | **Exists — extend** |
| **Task decomposition** | Ordered `ActionItem`s with deps, 12-D ontology mapping | Recursive/hierarchical decomposition for sub-goals | **Exists — extend** |
| **Reasoning** | 7 workflow patterns (`reasoning_workflows`) + adaptive prompt depth | Wire workflows into the loop as selectable strategies (FACT: today standalone) | **Exists — wire** |
| **Reflection / self-correction** | `reflective_loop` critique/revise to a quality threshold (0.85) | Add *post-action* reflection driven by Control-Plane verdicts + observations | **Exists — extend** |
| **Tool orchestration** | `mcp_gateway` dispatch + `ToolCatalog` discovery | Multi-tool step plans; tool selection separated from authorization | **Exists — redesign** |
| **Tool selection** | `action_type_to_tool` + risk-aware selection | Selection uses risk taxonomy as an input; authorization delegated | **Exists** |
| **Workflow execution** | `agent.py` per-turn loop with pinned action ordering | Durable, resumable multi-step workflow engine | **Exists — extend to durable** |
| **Memory** | `memory_store` (working + episodic, cosine/recency retrieval) + retention | Finish retention wiring (M3); add semantic + summary tiers | **Exists — finish** |
| **Long-running tasks** | `proactive_scheduler` (cron/interval, poll-based; unimported) | Durable run state + checkpoint/resume; scheduler wired to the loop | **Partial — build durability** |
| **Retries / backoff** | `proactive_scheduler` retries; per-step timeouts | First-class retry policy per step + verdict-aware backoff (HOLD→retry later) | **Partial — formalize** |
| **Human interaction** | `approval` (ephemeral) + `approval_workflow` (durable record) | Interaction as UX/routing; authority binds to ActionGate quorum | **Exists — reposition** |
| **Uncertainty / risk pre-screen** | `raw_entropy` (AUROC 0.857), `confidence_risk_gap`, `ToolRiskClassifier` (AUROC 0.82) | Packaged as ActionGate evidence | **Exists — strong** |
| **Structured output** | `structured_output` schema-validate | Keep; add streaming structured output | **Exists** |
| **Runtime adaptation** | `adaptive_policy` per-session tuning | Keep (relabel "gradients" honestly) | **Exists** |
| **Policy simulation / what-if** | `policy_replay`, `policy_simulation` | Keep; extend to proposal-level dry-run | **Exists** |
| **Observability** | `tracing` in-memory, `trace_viewer` | OTel export; durable, replayable run record | **Partial — export gap** |
| **Agent-behavior policy** | `policy_bundle`, `domain_policy` | Keep, namespaced away from action-authorization policy | **Exists** |

---

## 2. Missing capabilities (V2 gaps — none are governance)

**FACT.** The prior review confirmed these are absent (`README.md`: "no agent-to-agent handoff, orchestration graph, or agent registry"; trace is analytics-only). **RECOMMENDATION.** Build them — they are what separate a single-agent library from an agent-runtime platform, and every one is a *runtime* concern, not a Control-Plane concern.

| Missing capability | Why it matters | Why it belongs to the runtime (not the Control Plane) |
|---|---|---|
| **Agent identity (principal)** | ActionGate binds *caller* identity but needs the *agent* principal supplied | The runtime is what instantiates and runs the agent; only it can assert who is acting. It feeds this into the Execution Proposal. |
| **Agent registry** | Discover/instantiate agents by role/capability | Runtime composition concern; the Control Plane authorizes actions, not agent existence |
| **Capability registry** | Map agents ↔ tools/skills they can use | Pairs with agent registry; informs tool selection (runtime), not authorization (ActionGate still gates each call) |
| **Lifecycle management** | Create/pause/resume/retire long-running agents | Runtime process/state concern |
| **Checkpointing** | Resume a long task after a crash without re-planning | Runtime state durability; replaces the overstated "replayable trace" |
| **Durable run store** | Persist goal/plan/step state | Runtime state; distinct from ActionGate's authorization audit |
| **Observability export** | Ship traces to OTel/enterprise observability | Runtime telemetry; distinct from ActionGate's tamper-evident *decision* audit |
| **Multi-agent coordination** | Handoff, shared/scoped memory, sub-agent spawning | Runtime orchestration; see Deliverable 5 |
| **Compensation (saga) at the plan level** | Undo a *sequence* of authorized steps when a later step fails | Runtime workflow concern — note: *infra* rollback of a single action is ACP's; *plan-level* compensation across steps is the runtime's |

**INTERPRETATION — the compensation boundary (subtle, important).** ACP owns "rollback-available now" for a *single infrastructure action* (FACT: `acp/ACP_ACTIONGATE_BOUNDARY.md`). But undoing a *multi-step workflow* (e.g., "step 3 failed, so semantically reverse steps 1–2") is a reasoning/plan concern the Control Plane cannot own — it has no notion of the runtime's plan. So the runtime owns **saga-style compensation across steps**, implemented by *proposing compensating actions back through the Control Plane* (each of which ActionGate/ACP authorize independently). The runtime never executes an un-authorized rollback.

---

## 3. Capability layering

```
INTELLIGENCE GENERATION            WORKFLOW EXECUTION              PLATFORM (V2 gaps)
─────────────────────────          ───────────────────────        ─────────────────────
planning / decomposition           workflow orchestration         agent identity + registry
reasoning (7 patterns)             tool orchestration             capability registry
reflection / self-correction       retries / backoff              lifecycle management
uncertainty estimation             observation ingestion          checkpointing / durable store
tool selection                     human interaction (UX)         observability export
structured output                  execution proposal             multi-agent coordination
runtime adaptation                 memory read/update             plan-level compensation
agent-behavior policy              long-running task loop
```

**RECOMMENDATION — priority order for the gaps:** (1) durable run store + checkpointing (unlocks reliable long-running tasks and honest "replay"); (2) observability export (enterprise table-stakes); (3) agent identity (required for the Control-Plane binding to be meaningful); (4) agent/capability registry; (5) multi-agent coordination. Rationale: 1–3 harden the *existing* single-agent runtime and are prerequisites for the Control-Plane integration to be trustworthy; 4–5 are the expansion into multi-agent (Deliverable 5). None competes with ActionGate/ACP/Context-Min.
