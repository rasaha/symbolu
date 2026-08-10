# Deliverable 1 — Runtime Responsibility Matrix

**Milestone:** Agent Runtime V2 — design only. No production code, no refactoring, no implementation.
**Premise (given):** the AI Control Plane (Context Minimization + ActionGate + ACP) already owns governance. The Agentic Framework becomes a **pure Agent Runtime**: the layer responsible only for *intelligence generation* and *workflow execution*.

Labels: `FACT` (verifiable in the repo, cited) / `INTERPRETATION` / `RECOMMENDATION`.

This document is grounded in the prior review (`agentic_framework_review/`) and the source it cites. It defines exactly what the runtime owns and what it must never own.

---

## 1. The one-sentence contract

**RECOMMENDATION.** *The Agent Runtime decides **what to attempt, how to reason about it, and how confident it is** — and executes only what the AI Control Plane authorizes. It never mints authority, never judges operational safety, never enforces deterministic policy, and never governs context relevance.*

This mirrors the ACP pipeline's own ownership split — "relevance ⟂ proposal ⟂ authorization ⟂ operational safety" (`FACT`, `Project_documentation/control_plane/acp/RESPONSIBILITY_MATRIX.md`) — and makes the runtime the explicit, sole owner of **proposal** (the "LLM reader → Proposed Action" box in `Project_documentation/control_plane/acp/AI_CONTROL_PLANE_ARCHITECTURE.md`).

---

## 2. What the Runtime OWNS

Grouped by the two responsibilities the runtime is allowed to have: **intelligence generation** and **workflow execution**. Each row cites the existing module that already provides it (or notes it as a V2 gap).

### 2.1 Intelligence generation

| Responsibility | Owns | Existing module (FACT) | Nature |
|---|---|---|---|
| **Goal management / intake** | Accept a user/system goal, track goal state, decide completion | `goal_decomposition.GoalState` | Probabilistic (LLM) + deterministic tracking |
| **Task decomposition** | Break a goal into ordered `ActionItem`s with dependencies | `goal_decomposition.decompose_goal` (`agent.py:1729`) | LLM-driven, rule fallback |
| **Planning** | Sequence steps, resolve dependencies, choose strategy/agency level | `goal_decomposition`, `agent.py` loop | Probabilistic |
| **Reasoning** | Multi-step reasoning patterns (chain/tree/debate/map-reduce/Socratic/metacognitive) | `reasoning_workflows.py`, `adaptive_prompts.py` | Probabilistic |
| **Reflection / self-correction** | generate → critique → revise until quality threshold | `reflective_loop.py`, `local_critic.py` | Probabilistic + heuristic critic |
| **Uncertainty estimation** | Raw-entropy + confidence-risk-gap + risk classification | `raw_entropy_adapter`, `confidence_risk_gap`, `ToolRiskClassifier` | Probabilistic signals (FACT: AUROC 0.857 / 0.82) |
| **Tool selection** | Decide *which* tool best fits a step (from the catalog) | `tool_discovery.ToolCatalog`, `action_type_to_tool` | Probabilistic selection — **selection only, not authorization** |
| **Structured output** | Constrain generation to a schema and validate | `structured_output.py` | Deterministic validation |

### 2.2 Workflow execution

| Responsibility | Owns | Existing module (FACT) | Nature |
|---|---|---|---|
| **Workflow orchestration** | Drive the per-step loop; sequence proposal → execution → observation → reflection | `agent.py` (`run`/`run_stream`) | Deterministic control |
| **Execution proposal construction** | Assemble `(proposed_action, agent_identity, risk/uncertainty evidence)` for the Control Plane | *V2 seam* (from `mcp_gateway` pre-screen) | Deterministic packaging |
| **Observation ingestion** | Feed authorized tool results back into reasoning/memory | `agent.py` action loop | Deterministic |
| **Retries / backoff** | Retry the runtime's own steps (reasoning, proposal, tool-result handling) | `proactive_scheduler` retry logic (partial) | Deterministic |
| **Long-running task management** | Durable run state, checkpoints, resume | *V2 gap* (trace is analytics-only today, FACT: readiness audit) | Deterministic |
| **Retry/cancellation/budget of runtime work** | Cooperative cancellation, token/time budgets on runtime steps | `cancellation.py`, `token_budget.py`, `duration_policy.py` | Deterministic |
| **Human interaction (UX/routing)** | Surface approvals/questions to a human, collect responses, route them | `approval.py` (ephemeral), `approval_workflow.py` (durable record) | Deterministic — **routing only, not authoritative sign-off** |
| **Memory** | Working + episodic memory, retrieval, retention/TTL | `memory_store.py`, `memory_retention.py` | Deterministic (pluggable embeddings) |
| **Agent-behavior policy** | Interaction mode, revision budget, response style, domain profile | `policy_bundle.py`, `domain_policy.py`, `adaptive_policy.py` | Deterministic — **behavior, not action-authorization** |
| **Agent identity / registry / lifecycle** | Assert the agent principal; register agents & capabilities; manage lifecycle | *V2 gap* (FACT: none today — `README.md` "no agent registry") | Deterministic |
| **Runtime observability** | Reasoning trace, telemetry, OTel export | `tracing.py`, `trace_viewer.py` (+ *V2 export gap*) | Deterministic |

**INTERPRETATION.** Every "owns" row is either an existing framework strength or an agent-runtime capability gap (identity/registry/lifecycle/checkpointing/observability-export). None of them is a governance concern. This is the correct center of gravity for a runtime.

---

## 3. What the Runtime must NOT own

Each row names the sole owner in the AI Control Plane, with the evidence that the owner already provides it — so the runtime must **delegate, not duplicate**.

| Responsibility the runtime must NOT own | Sole owner | Evidence the owner already has it (FACT) |
|---|---|---|
| **Authorization** — "may this exact action execute, once?" | **ActionGate** | "grants authority to one exact action, once, only after policy, evidence, state, approval… are satisfied" (`ACTIONGATE_VC_BRIEF.md`); 6-outcome verdict + signed token (`action_gate_ref/gate.py`) |
| **Token minting / execution grant** | **ActionGate** | mints single-use execution token on ALLOW (`action_gateway/README.md`) |
| **Credential brokering** | **ActionGate** | single-use scoped credential the agent never holds (`broker.py`, real ServiceAccount/TokenRequest in K8s) |
| **Approver quorum / four-eyes authority** | **ActionGate** | `ESCALATE_TO_HUMAN` + approvals bound to action_hash + policy_hash (`gate.py`) |
| **Deterministic hard-policy enforcement** | **ActionGate** | signed policy bundle of hard invariants (REQUIRE/FORBID/MAX_SCOPE/MAX_BLAST_RADIUS…) (`gate.py`) |
| **Operational safety** — "is it safe against live state now?" | **ACP** | readiness/cooldown/blast-radius/capacity/freeze/rollback (`Project_documentation/control_plane/acp/ACP_ACTIONGATE_BOUNDARY.md`, real `ReadinessChecker`/`SafetyBounds`) |
| **Live-state action selection over admissible candidates** | **ACP** | `filter_admissible` + `LexicographicActionSelector`, non-compensatory (`Project_documentation/control_plane/acp/ACP_V1_FREEZE.md`) |
| **Infrastructure rollback** | **ACP** | rollback-availability gating + `cloud_controller` rollback watch |
| **Context governance** — "what may the model read?" | **Context Minimization** | authorization-preserving deterministic compression, fail-closed span preservation (`CONTEXT_MINIMIZATION_VC_BRIEF.md`) |
| **Tamper-evident authorization audit** | **ActionGate** | hash-chained audit record (`audit.py`) |

**FACT — why this matters.** The prior review found the framework *already* duplicates several of these at a softer tier: two soft authorization PDPs (`mcp_gateway` in World A, `GovernanceService` in World B), a `policy_bundle` that mirrors ActionGate's policy concept, and an `approval_workflow` that shadows ActionGate's quorum. V2's central discipline is to **stop owning all of the "must not own" rows** and re-emit the useful parts (risk/uncertainty) as ActionGate *evidence*.

**FACT — the integration is already natural.** ActionGate "accept[s] optional evidence [that] can only *raise* scrutiny… never *lower* a hard invariant" (`ACTIONGATE_VC_BRIEF.md`). The runtime's risk score, raw-entropy, and confidence-risk-gap map onto that evidence slot with **no new Control-Plane concept required**, and the composition is monotonically safe (opting in can never make an agent more permissive).

---

## 4. The boundary object: the Execution Proposal

**RECOMMENDATION.** The runtime's output to the Control Plane is a single typed object — the **Execution Proposal** — and this is the *only* thing that crosses the boundary:

```
ExecutionProposal {
  agent_principal        // who is acting (runtime-owned identity)
  proposed_action        // canonical action the runtime wants to take
  selected_tool          // runtime's tool selection (advisory)
  reasoning_ref          // pointer to the reasoning trace (runtime-owned)
  evidence {             // scrutiny-only, per ActionGate's evidence contract
    risk_level           // ToolRiskClassifier (AUROC 0.82)
    raw_entropy          // uncertainty (AUROC 0.857)
    confidence_risk_gap  // "confidently uncertain" flag
  }
}
```

The Control Plane returns a verdict + (on ALLOW) a single-use token; the runtime executes **only** with that token. `FACT`: this matches ActionGate's `submit_action → evaluate_action → execute_action` shape (`action_gateway/README.md`) and ACP's identity-bound composition (`Project_documentation/control_plane/acp/ACP_V2_2_PREREGISTRATION.md` §4).

---

## 5. Summary table — owns / does-not-own

| Category | Runtime owns? | Owner if not runtime |
|---|---|---|
| Goal management, decomposition, planning | ✅ | — |
| Reasoning, reflection, self-correction | ✅ | — |
| Tool **selection** | ✅ | — |
| Tool **authorization** | ❌ | ActionGate |
| Memory (working/episodic/retention) | ✅ | — |
| Workflow execution / orchestration | ✅ | — |
| Execution proposal + evidence | ✅ | — |
| Retries/backoff of runtime steps | ✅ | — |
| Long-running task state / checkpointing | ✅ (V2 gap) | — |
| Human interaction (UX/routing) | ✅ | — |
| Human approval **authority** (quorum) | ❌ | ActionGate |
| Agent identity / registry / lifecycle | ✅ (V2 gap) | — |
| Agent-behavior policy | ✅ | — |
| Deterministic action-authorization policy | ❌ | ActionGate |
| Operational safety / readiness | ❌ | ACP |
| Infrastructure rollback | ❌ | ACP |
| Context relevance / compression | ❌ | Context Minimization |
| Reasoning trace / runtime telemetry | ✅ | — |
| Tamper-evident authorization audit | ❌ | ActionGate |

The cross-system, no-overlap version of this table is Deliverable 6 (`06_RUNTIME_VS_CONTROL_PLANE_OWNERSHIP.md`). The per-subsystem KEEP/MOVE/DELETE/REDESIGN classification is Deliverable 2 (`02_REMOVE_OWNERSHIP_AUDIT.md`).
