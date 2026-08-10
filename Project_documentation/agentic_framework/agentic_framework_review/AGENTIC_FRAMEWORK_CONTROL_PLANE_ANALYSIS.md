# Agentic Framework vs AI Control Plane — Comparative Analysis (Part 2)

**Reference architecture:** ACP V2.2 (the "AI Control Plane"), as frozen in `Project_documentation/control_plane/acp/ACP_V2_2_PREREGISTRATION.md`, `Project_documentation/control_plane/acp/AI_CONTROL_PLANE_ARCHITECTURE.md`, `Project_documentation/control_plane/acp/RESPONSIBILITY_MATRIX.md`, `Project_documentation/control_plane/acp/ACP_ACTIONGATE_BOUNDARY.md`.
**Subject:** the Agentic Framework as decomposed in `AGENTIC_FRAMEWORK_ARCHITECTURE_AUDIT.md`.

Labels: `FACT` / `INTERPRETATION` / `RECOMMENDATION` / `SPECULATION`.

---

## 1. What "AI Control Plane" means in *this* repo (not the generic industry term)

**FACT.** In this codebase the "AI Control Plane" is a **specific, narrow, deterministic, shadow-only** composition of three independent layers over one identity-bound action (`Project_documentation/control_plane/acp/AI_CONTROL_PLANE_ARCHITECTURE.md`, `Project_documentation/control_plane/acp/RESPONSIBILITY_MATRIX.md`):

```
Original Context
  → Context Minimization (REAL)   — owns RELEVANCE ("what to SEE")
  → LLM reader stage              — owns PROPOSAL ("what to PROPOSE")
  → ActionGate (REAL)             — owns AUTHORIZATION ("MAY it be done?")
  → ACP (REAL)                    — owns OPERATIONAL SAFETY ("is it SAFE now?")
  → Composition (8 classes)       — links verdicts, never overrides
```

**FACT — defining properties** (from the ACP corpus):
- **Deterministic, non-compensatory, fail-closed.** "No probabilistic authorization. `ActionDecision` is a closed enum; no scalar 'allow score' exists" (`Project_documentation/control_plane/acp/ACP_INTERFACE_CONTRACTS.md`). "Same inputs → same decision, bit-for-bit" (`Project_documentation/control_plane/acp/ACP_ARCHITECTURE.md` A2).
- **Disjoint ownership, zero duplication.** "relevance ⟂ proposal ⟂ authorization ⟂ operational safety"; "duplicated-logic count 0, ownership violations 0" (`Project_documentation/control_plane/acp/RESPONSIBILITY_MATRIX.md`).
- **Cross-domain.** The frozen ACP decision core (SHA-256 `8f8660e2…`) runs byte-for-byte unchanged over both robot actions and Kubernetes operations (`Project_documentation/control_plane/acp/ACP_V1_FREEZE.md`, `symbolu_robotics/autonomous_control_plane/cloud/adapter.py`).
- **Not an executor / planner / agent runtime.** "it does not do the work, it decides and authorizes what work is allowed to happen" (`Project_documentation/control_plane/acp/ACP_ARCHITECTURE.md`).
- **Shadow-only, non-authoritative today.** Everything beyond V1 design is shadow (`Project_documentation/control_plane/acp/ACP_V2_2_PREREGISTRATION.md`).

**FACT — the ACP corpus contains ZERO references to the Agentic Framework** (case-insensitive scan of all 57 `acp/` files). Symmetrically, **no Agentic Framework doc references ACP, ActionGate, or Context Minimization by name.** The two bodies of work are architecturally disjoint in their own documentation; the only stated linkage is portfolio-level ("part of a broader SymbolU / Conscious Generation portfolio … each brief describes a distinct product boundary," `AGENTIC_FRAMEWORK_VC_BRIEF.md`).

**INTERPRETATION.** This is the crux. The repo's "AI Control Plane" is *the deterministic authorization+safety substrate beneath an agent*. The Agentic Framework is *the probabilistic agent that produces the proposal that flows into that substrate*. In ACP's own pipeline diagram, the Agentic Framework's natural seat is the **"LLM reader → Proposed Action"** box — the proposer — **not** any of the governance layers.

---

## 2. Mapping the task's governance taxonomy onto the repo

The task asks whether each module is primarily Context Governance / Execution Governance / Operational Governance / Planning / Scheduling / Memory / Reasoning / Coordination / Infrastructure / Telemetry / Policy / Optimization / Human approval / State management / Lifecycle management.

**FACT — the three "governances" already have owners in the repo**, and none of them is the Agentic Framework:

| Governance tier | Owner in the repo | Nature |
|---|---|---|
| **Context Governance** ("what the model may read") | **Context Minimization** (`experiments/actiongate_context_ablation/`) | Deterministic, authorization-preserving compression |
| **Execution Governance** ("may this exact action execute, once") | **ActionGate** (`cyber_security/action_gate_reference/`) | Deterministic pre-commit authorization; mints a single-use token |
| **Operational Governance** ("is it safe against live state now") | **ACP proper** (frozen core + `cloud_controller`) | Deterministic operational-safety evaluator; shadow-only |

**INTERPRETATION.** The Agentic Framework does not primarily own any of these three tiers. It *touches* all three in weak, app-level form — but the authoritative owners already exist as separate, deterministic subsystems.

---

## 3. Component-by-component classification

For each Agentic Framework component: its primary category, and **why**, with the ACP-side analogue it maps to (or the fact that it has none).

### 3.1 World A — the agent runtime (proposer)

| AF component | Primary category | ACP analogue | Why (evidence) |
|---|---|---|---|
| `agent.py` orchestrator | **Coordination / Reasoning (proposer)** | The **LLM reader → proposal** box | FACT: it runs the LLM, decomposes goals, reflects, and *proposes* actions. It is the thing upstream of the control plane, not a governance layer. |
| `goal_decomposition.py` | **Planning** | None in ACP (ACP "consumes a planner," `ACP_ARCHITECTURE.md` §7) | FACT: LLM-driven intent→actions. ACP explicitly is *not* a planner. |
| `reasoning_workflows.py`, `adaptive_prompts.py` | **Reasoning** | None | FACT: LLM reasoning patterns; probabilistic; no ACP counterpart. |
| `reflective_loop.py`, `local_critic.py`, `benchmark_critics.py` | **Reasoning / Optimization** | None | FACT: quality-critic revision; probabilistic or heuristic. |
| `memory_store.py`, `memory_retention.py` | **Memory / State management** | None (ACP is stateless per tick; world-state is injected) | FACT: append-only conversational memory. |
| `coherence_tracker.py` | **Telemetry (observation-only)** | ACP `DecisionTrace` (but ACP's is causal/hash-chained) | FACT: 7 shallow proxies, observation-only, `factual_alignment` hardcoded. |
| `llm_adapters.py`, `inference_mistral.py` | **Infrastructure (model I/O)** | None | FACT: provider SDK plumbing. |
| `structured_output.py`, `streaming_events.py`, `cancellation.py`, `tool_discovery.py` | **Infrastructure** | None | FACT: runtime plumbing. |
| `proactive_scheduler.py` | **Scheduling** | None (ACP is per-tick, externally driven) | FACT: cron/interval; poll-based; unimported. |

### 3.2 The tool-authorization path (the control-plane-shaped part of World A)

| AF component | Primary category | ACP analogue | Why (evidence) |
|---|---|---|---|
| `mcp_gateway.py` (`SafeMCPGateway`) | **Execution Governance (soft) + Authorization** | **ActionGate** | FACT: risk-classify → confidence gate → escalate → execute → audit is a soft, probabilistically-informed analogue of ActionGate's `canonicalize→decide→bind→execute→audit`. But it decides by *threshold*, mints no token, brokers no credential, defaults to a mock client. **This is the clearest conceptual overlap with the control plane.** |
| `ToolRiskClassifier`, `ToolSpec`, `ToolPermission` | **Policy / Tool permissions** | ActionGate operation taxonomy + policy operators | FACT: 5-level risk taxonomy (AUROC ≈0.82) with min-confidence per level. |
| `cg_tool_dispatcher.py` | **Coordination (routing)** | None | FACT: enrich-and-forward. |

### 3.3 World B — the governance decision service (control-plane-shaped, standalone)

| AF component | Primary category | ACP analogue | Why (evidence) |
|---|---|---|---|
| `governance_service.py` (`GovernanceService`) | **Execution Governance / Authorization (PDP)** | **ActionGate** (authorization) | FACT: decision-only `authorize()→ALLOW/DENY/DEFER` over a tool action; deterministic; no LLM; no execution. This is *structurally a policy decision point* — the same job ActionGate does, one tier softer and probabilistically-informed. |
| `governance_api.py` | **Infrastructure (Control API)** | ACP interface contracts / brokers | FACT: FastAPI `/authorize`. The only network control surface in the framework. |
| `jepa_governance.py` | **Policy (advisory)** | None (ACP forbids scalar scoring) | FACT: deterministic heuristic; stricter-only; falsified-adjacent (its inputs are approximated from confidence scalars). |
| `domain_policy.py`, `policy_bundle.py`, `adaptive_policy.py`, `signal_config.py` | **Policy** | ActionGate *signed policy bundle* | FACT: versioned/scoped policy model, fail-closed. Direct conceptual analogue to ActionGate's signed policy — but softer and not token-binding. |
| `safety_contract.py` | **Execution Governance (turn-level pre-gate)** | ActionGate hard invariants (weakly) | FACT: 6 fail-closed preconditions; not wired to `policy_bundle`. |
| `approval.py`, `approval_workflow.py`, `approval_coverage.py` | **Human approval** | ActionGate `ESCALATE_TO_HUMAN` + Cloud Controller approval lifecycle | FACT: ephemeral + durable approval; **no resume/execute**. |
| `policy_replay.py` | **Policy simulation** | ACP deterministic replay | FACT: "what-would-this-policy-do" over audit records. |
| `agentic/policy/policy_control_plane.py` (sibling) | **Operational Governance (read-only)** | ACP runtime governor / decision ledger surface | FACT: "Policy Control Plane — zero-LLM, read-only" per-domain policy state + health signals + tenant hooks. **The framework's own most control-plane-shaped module.** |

### 3.4 The signal apparatus (advisory, mostly dormant)

| AF component | Primary category | ACP analogue | Why (evidence) |
|---|---|---|---|
| `signal_adapters/*` | **Telemetry → advisory Policy input** | ACP predictor-reliability *evidence* (conceptually) | FACT: bounded stricter-only penalties (≤0.20 aggregate), inert by default. |
| `sovereign_bridge.py`, `olm_bridge.py` | **Telemetry (translation)** | None | FACT: tensor/ontology → signals; enforce nothing. |
| `trust/*` | **Governance (shadow, not flipped)** | ACP evidence-status model | FACT: deterministic weakest-link tree; shadow/canary-gated; changes no production outcome. |
| `raw_entropy_adapter`, `confidence_risk_gap` | **Telemetry (validated)** | None | FACT: the one empirically-supported signal (raw-entropy AUROC 0.857). |
| CG sovereign-state governance | **(falsified — should disappear)** | None | FACT: `signal_config` AUROC 0.457, anti-predictive; default OFF; founder notes say "kill." |

---

## 4. Determinism & layer alignment — the decisive mismatch

**FACT.** ACP's foundational axiom is that the control plane is **deterministic and non-compensatory** — "no probabilistic scoring where a deterministic decision exists" (`Project_documentation/control_plane/acp/ACP_ARCHITECTURE.md` A2). ActionGate is stdlib-only, "no AI" (`gate.py` header). Context Minimization's *safety property* is deterministic (a trainable detector's misses are caught by a deterministic fail-closed check).

**FACT.** The Agentic Framework's authorization decisions are **confidence-threshold and risk-score based** — exactly the "scalar allow score" ACP forbids. `mcp_gateway` computes `effective_confidence = gate + jepa_adj − raw_entropy_penalty − cg_entropy_penalty` and compares to thresholds (`mcp_gateway.py:1356–1362`). `governance_service` returns ALLOW/DENY/DEFER from aggregated soft signals.

**INTERPRETATION.** This is not a defect — it is a *layer difference*. Probabilistic, confidence-weighted judgment is exactly what you want in the **proposer/pre-screen** tier (deciding what to attempt and how hard to think). Deterministic, non-compensatory authorization is exactly what you want in the **actuation** tier (deciding whether the attempt may execute). The Agentic Framework is built for the first; ACP/ActionGate for the second. **They are complementary tiers of one stack, not competing versions of the same layer.**

---

## 5. Runtime vs design-time alignment

**FACT.** ACP is a runtime, per-tick decision plane (currently shadow). The Agentic Framework's World A is a runtime agent loop; World B is a runtime PDP; the policy/replay/simulation modules are design-time/offline. Both sides are "runtime-shaped." No mismatch here.

---

## 6. Category verdict per area (summary)

| Task category | Primarily owned in AF by | Should it be AF's to own? |
|---|---|---|
| Context Governance | (weakly) `memory_store`/`request_enrichment` | **No** — Context Minimization owns it |
| Execution Governance | `mcp_gateway` (A), `governance_service` (B), `safety_contract` | **No, not authoritatively** — ActionGate owns hard authorization; AF should *pre-screen and feed evidence* |
| Operational Governance | `policy_control_plane` (read-only), `duration_policy` | **No** — ACP owns it |
| Planning | `goal_decomposition`, `adaptive_prompts` | **Yes** — proposer tier |
| Scheduling | `proactive_scheduler`, `duration_policy` | **Yes** (agent-side) |
| Memory | `memory_store` | **Yes** |
| Reasoning | reflective/critic/reasoning modules | **Yes** — this is the core value |
| Coordination | `agent.py`, dispatcher | **Yes** (single-agent today) |
| Infrastructure | adapters, events, API | **Yes** (runtime) |
| Telemetry | `tracing`, coherence, adapters | **Yes**, but should export to a real observability plane |
| Policy | `policy_bundle`, `domain_policy` | **Partly** — agent-behavior policy yes; action-authorization policy belongs with ActionGate |
| Optimization | `adaptive_policy`, critic router | **Yes** |
| Human approval | `approval*` | **Shared** — routing yes; authoritative sign-off binds to ActionGate |
| State management | memory/approval store | **Yes** (agent state) |
| Lifecycle management | *absent* | **Should exist** if it becomes a multi-agent runtime (see Part 5) |

**INTERPRETATION → conclusion of Part 2.** Measured against ACP V2.2, the Agentic Framework is **primarily a proposer/reasoning/coordination runtime (Planning + Reasoning + Coordination + Memory + agent-side Telemetry)** with a **bolted-on, non-authoritative Execution-Governance backend (World B + `mcp_gateway`)** that *duplicates ActionGate's concern at a softer tier*. It is not, in its center of gravity, a control plane. The next document (Responsibility Matrix) turns this into per-module keep/move/merge/disappear recommendations, and Part 4 quantifies the duplication.
