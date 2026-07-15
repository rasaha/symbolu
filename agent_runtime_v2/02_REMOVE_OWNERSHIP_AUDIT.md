# Deliverable 2 — Remove Ownership Audit

Every Agentic Framework subsystem classified for Agent Runtime V2:
**KEEP** · **MOVE TO ACTIONGATE** · **MOVE TO ACP** · **MOVE TO CONTEXT MINIMIZATION** · **DELETE** · **REDESIGN**.

"MOVE TO X" means *the responsibility belongs to X; the runtime stops owning it and instead consumes X.* Because the milestone forbids duplicating anything ActionGate/ACP/Context-Min already provide, "MOVE" usually means **delete the framework's copy and call the Control Plane** — not port code into it.

Labels: `FACT` (module behavior verified in the prior review's source reads) / `RECOMMENDATION` / `INTERPRETATION`. Line references are from the source reads in `agentic_framework_review/AGENTIC_FRAMEWORK_ARCHITECTURE_AUDIT.md`.

---

## 1. Core runtime (World A) — the proposer

| Subsystem | FACT (what it does) | Verdict | Justification |
|---|---|---|---|
| `agent.py` (`AgenticLLMWrapper`) | Per-turn orchestration loop | **KEEP** | The runtime's core. RECOMMENDATION: make budget/deadline/approval uniform across `run()` and `run_stream()` (today enforced only on streaming). |
| `agent_builder.py`, `cg_tool_dispatcher.py` | Assembly + tool-call routing | **KEEP + REDESIGN** | Keep as composition front doors; REDESIGN default from `MockMCPClient` to a real transport or a loud mock banner. |
| `goal_decomposition.py` | Intent → plan | **KEEP** | Pure proposer function; ACP explicitly "consumes a planner." |
| `reasoning_workflows.py` | 7 reasoning patterns | **KEEP + REDESIGN** | FACT: standalone (only `adaptive_prompts` imports it). REDESIGN: wire into the loop as selectable strategies or mark experimental. |
| `adaptive_prompts.py` | Complexity → prompt depth | **KEEP** | Proposer reasoning. |
| `reflective_loop.py`, `local_critic.py`, `benchmark_critics.py` | Critique/revise + cost-aware critic routing | **KEEP** | Differentiated reasoning value. |
| `memory_store.py`, `memory_retention.py` | External memory + retention | **KEEP + REDESIGN** | Finish the deferred "M3" retention wiring (FACT: `last_accessed_at` unused). |
| `coherence_tracker.py` | 7 coherence metrics | **KEEP + REDESIGN** | FACT: `factual_alignment` hardcoded 0.7 weighted into every score → REDESIGN to compute it or drop the constant. |
| `llm_adapters.py`, `inference_mistral.py`, `structured_output.py`, `streaming_events.py`, `cancellation.py`, `tool_discovery.py`, `token_budget.py`, `duration_policy.py` | Runtime plumbing | **KEEP** | Standard runtime infra. REDESIGN token_budget cost path (FACT: cost caps inert). |
| `tracing.py`, `trace_viewer.py` | Event → trace summary | **KEEP + REDESIGN** | FACT: "replayable" overstated; analytics rollup only. REDESIGN into a real durable/replayable run record + OTel export. |
| `proactive_scheduler.py` | Cron/interval autonomous execution | **KEEP + REDESIGN** | FACT: nothing imports it; stored `confidence_gate` never called. REDESIGN: fix dead wiring; keep as opt-in long-running-task driver. |

## 2. The tool-authorization path — the biggest overlap

| Subsystem | FACT | Verdict | Justification |
|---|---|---|---|
| `mcp_gateway.SafeMCPGateway` — **final ALLOW/BLOCK authority + escalation + execute + audit** | Threshold/risk-score authorization; mints no token; brokers no credential; default mock client | **REDESIGN (split)** | Split: **KEEP** risk classification + escalation UX + (dev-only) local execution; **MOVE TO ACTIONGATE** the final authorization, credential brokering, token minting, and tamper-evident audit. The kept part emits ActionGate *evidence*. |
| `ToolRiskClassifier`, `ToolSpec`, `ToolPermission` | 5-level risk taxonomy (AUROC 0.82) | **KEEP** | Genuine asset; becomes ActionGate evidence + runtime tool-selection input. |
| Gateway hard-deny / forbidden-capability block | Deterministic block list | **MOVE TO ACTIONGATE** | Hard forbidden-capability enforcement is ActionGate's signed-policy job (FORBID operator). Runtime keeps a *soft* pre-filter only. |

## 3. World B — the standalone governance service

| Subsystem | FACT | Verdict | Justification |
|---|---|---|---|
| `governance_service.GovernanceService` | Decision-only `/authorize`→ALLOW/DENY/DEFER; **not called by the agent** | **MOVE TO ACTIONGATE (as evidence) + DELETE the authority** | It re-implements ActionGate's decision at a softer tier. RECOMMENDATION: keep its *risk/uncertainty aggregation* as the runtime's evidence emitter; delete its role as an independent PDP. |
| `governance_api.py` (FastAPI `/authorize`) | Network authorization surface | **REDESIGN** | Reposition as the runtime's **pre-authorization / evidence** API (advisory), not an authorization authority; add auth/TLS (FACT: none today). |
| `governance_models.py` | Schemas; `counterfactual` never populated; `tenant_id/org_id/dry_run` unused | **KEEP + REDESIGN** | Keep the request/response schema; delete never-populated fields or implement them. |
| `governance_adapter.py` | Re-export of an external, incompatible P52 schema | **DELETE** | FACT: a second, un-audited schema family. Consolidate to one. |
| `jepa_governance.py` | Deterministic heuristic "regime" override, stricter-only; "NOT a trajectory predictor" | **REDESIGN → advisory, or DELETE** | FACT: framework's own trust docs say "demote JEPA to advisory/off; it re-encodes tool risk." At most an advisory signal; never blocking. |
| `safety_contract.py` (`SafetyGate`) | 6 fail-closed preconditions; thresholds hardcoded, duplicated vs `policy_bundle` | **KEEP + REDESIGN** | Keep as a *turn-level soft pre-gate* (a runtime sanity check before proposing). REDESIGN to source thresholds from one place. Hard action-authorization still goes to ActionGate. |
| `policy_bundle.py` | Versioned scoped policy | **KEEP (behavior scope only)** | Keep for *agent-behavior* policy; the *action-authorization* policy belongs to ActionGate. RECOMMENDATION: rename/namespace to prevent confusion with ActionGate's signed policy. |
| `domain_policy.py`, `adaptive_policy.py`, `signal_config.py` | Domain profiles / session tuning / signal config | **KEEP** | Legitimate agent-behavior policy + runtime adaptation. REDESIGN: fix the latent no-op rule (severity-0 ALLOW); relabel "SCC gradient descent" (fixed constants, not learned). |
| `policy_replay.py`, `policy_simulation.py` | What-if replay/simulation | **KEEP** | Useful offline runtime tooling; non-mutating. |
| `approval.py` / `approval_workflow.py` / `approval_coverage.py` | Ephemeral + durable approval + coverage report | **KEEP routing / MOVE TO ACTIONGATE authority** | Keep approval *UX and record*; the authoritative quorum decision binds to ActionGate's `ESCALATE_TO_HUMAN`. FACT: durable store never executes/resumes anyway. |

## 4. Signal apparatus

| Subsystem | FACT | Verdict | Justification |
|---|---|---|---|
| `raw_entropy_adapter`, `confidence_risk_gap` | Validated uncertainty (AUROC 0.857) | **KEEP** | The one empirically-supported signal; runtime evidence. |
| `signal_adapters/*` (other ~17) | Bounded stricter-only penalties; inert by default; some dead-wired | **REDESIGN → advisory / DELETE dead ones** | FACT: `rollback_adapter` post-action loop missing; `readiness_adapter` cooldown stub; `counterfactual_bridge` replay-only. Keep real ones as advisory signals; delete dead wiring. |
| `sovereign_bridge.py`, `olm_bridge.py` | Tensor/ontology → signals; enforce nothing | **REDESIGN → advisory** | Optional signal producers for CG-capable models; never blocking. |
| `trust/*` | Deterministic shadow-gated trust layer; flip not taken | **REDESIGN (decide flip) / DELETE** | RECOMMENDATION: either commit the flip (and reconcile with ActionGate as the runtime's soft evidence tree) or retire it. Perpetual shadow is debt. |
| **CG sovereign-state governance** | AUROC 0.457 (anti-predictive), default OFF, founder notes "kill" | **DELETE (as governance)** | FACT: falsified. May survive as CG-LLM research, not as runtime governance. |

## 5. Sibling policy layer (`agentic/policy/`)

| Subsystem | FACT | Verdict | Justification |
|---|---|---|---|
| `policy_control_plane.py` | Read-only, zero-LLM per-domain policy state + health + tenant hooks | **KEEP + REDESIGN (rename)** | The framework's most control-plane-shaped module — but it governs *agent behavior*, not actions. Rename to "agent behavior policy surface" to avoid colliding with the real AI Control Plane. |
| `policy_engine.py`, `policy_service.py`, `policy_lifecycle.py`, `policy_simulation.py` | Behavior-policy computation/lifecycle | **KEEP** | Legitimate runtime policy backend. |

---

## 6. Audit rollup

| Verdict | Count (approx) | Representative subsystems |
|---|---|---|
| **KEEP** | ~24 | agent loop, goal_decomposition, reflective_loop, reasoning_workflows, memory_store, llm_adapters, policy_bundle, domain_policy, policy_replay, ToolRiskClassifier, raw_entropy/confidence_risk_gap, approval (routing) |
| **REDESIGN** | ~11 | mcp_gateway (split), governance_api (→pre-auth), governance_models, safety_contract (threshold source), tracing (durable/OTel), proactive_scheduler (fix wiring), coherence_tracker (factual_alignment), signal_adapters (→advisory), trust (flip decision), sovereign/olm bridges, policy_control_plane (rename) |
| **MOVE TO ACTIONGATE** | ~5 concerns | final authorization, credential brokering, token minting, approver-quorum authority, hard forbidden-capability enforcement, tamper-evident authorization audit |
| **MOVE TO ACP** | 0 code / concerns delegated | operational safety, live-state action selection, infra rollback (the runtime never had these — nothing to move, only *not to build*) |
| **MOVE TO CONTEXT MINIMIZATION** | 0 code / concern delegated | context relevance/compression (runtime never had it; consume it optionally) |
| **DELETE** | ~3 | `governance_adapter` (P52 facade), CG sovereign-state governance, dead-wired signal adapters |

**INTERPRETATION.** The dominant verdict is **KEEP** — because the runtime's real value (reasoning, memory, planning, risk pre-screen, policy simulation) is legitimately runtime-owned. The second theme is **REDESIGN**, concentrated entirely in the *authorization-shaped* modules that must demote to advisory/evidence. **MOVE TO ACP / CONTEXT MINIMIZATION is empty of code** — a `FACT`-level confirmation that the runtime never actually owned operational safety or context governance; it only must avoid *building* them. The only real deletions are a falsified signal and a duplicate schema. This is a clean, low-risk removal path.
