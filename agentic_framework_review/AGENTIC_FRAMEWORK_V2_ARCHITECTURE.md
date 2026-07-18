# Agentic Framework V2 — Capability Gaps, ACP Boundary & Future Architecture (Parts 5, 7, 8)

Assumes ACP, ActionGate, and Context Minimization already exist as the deterministic control-plane substrate. Redesigns the Agentic Framework so it fits *above* that substrate without duplicating it.

Labels: `FACT` / `INTERPRETATION` / `RECOMMENDATION` / `SPECULATION`.

---

## Part 5 — Missing control-plane capabilities

For each mature-control-plane capability: **Already exists / Partially exists / Should exist (in AF) / Should exist (elsewhere) / Should never exist in AF** — with the reason. The key move: many capabilities that a naive "grow AF into a control plane" plan would *build in AF* **already exist in ACP/ActionGate** and should be *delegated to*, not rebuilt.

| Capability | Status in AF (FACT) | Verdict | Why |
|---|---|---|---|
| **Policy engine** | Exists: `policy_bundle`, `domain_policy`, `policy_engine` (agent-behavior); ActionGate owns action-policy | **Partially / split** | Agent-behavior policy in AF; action-authorization policy in ActionGate. Two scopes, one word. |
| **Workflow governance** | Partial: `reasoning_workflows` (standalone), `agent.py` loop invariant | **Should exist (AF)** | Legitimate proposer concern; finish wiring. |
| **Agent lifecycle** | Absent | **Should exist (AF-V2)** if it becomes multi-agent; else N/A | FACT: single agent, no lifecycle. Prereq for any orchestration story. |
| **Multi-agent coordination** | Absent (explicitly out of scope, README) | **Should exist (AF-V2)** | The single biggest capability gap for a "platform" claim; deliberately deferred today. |
| **Budget governance** | Exists: `token_budget` (token caps real; cost caps inert) | **Should exist (AF) — fix** | Wire adapter cost or drop the cost guarantee. |
| **Human approval routing** | Exists: `approval`, `approval_workflow` | **Should exist (AF); authority → ActionGate** | Routing/UX in AF; quorum authority in ActionGate. |
| **Escalation** | Exists: `confidence_gate` escalation, gateway ESCALATE | **Should exist (AF)** | Core proposer-side control. |
| **Retry policy** | Partial: `proactive_scheduler` retries | **Should exist (AF)** | Agent execution concern. |
| **Execution state** | Partial: goal/turn state | **Should exist (AF)** | Agent state. |
| **Checkpointing** | Absent (trace is analytics rollup, not replay) | **Should exist (AF-V2)** | Prereq for durable long-running agents; currently overstated. |
| **Compensation** | Absent (`rollback_adapter` post-action loop unwired) | **Should exist (AF-V2) or delegate** | FACT: snapshots captured, never used. |
| **Rollback** | Partial/unwired | **Delegate to ACP (operational) / build agent-state rollback (AF)** | Infra rollback is ACP's; agent-state rollback is AF's. |
| **Agent registry** | Absent | **Should exist (AF-V2)** | Prereq for multi-agent. |
| **Capability registry** | Absent | **Should exist (AF-V2)** | Pairs with agent registry. |
| **Tool registry** | Exists: gateway registry, `ToolSpec`, `ToolCatalog` | **Already exists (AF)** | Keep. |
| **Tool permissions** | Exists: `ToolRiskClassifier`, `ToolPermission` | **Already exists (AF); hard-enforce via ActionGate** | Risk taxonomy = evidence; hard permission = ActionGate. |
| **Agent identity** | Absent | **Should exist (AF-V2)** | Required to bind actions to an accountable agent principal; ActionGate already binds *caller* identity — AF must supply the *agent* principal. |
| **Execution quotas** | Partial: budget | **Should exist (AF)** | Extend budget → quotas. |
| **Execution priorities** | Absent | **Should exist (AF-V2)** | Scheduling concern once multi-agent. |
| **Rate limiting** | Facade: `rate_limiter` UNUSED; `policy_engine_adapter` rate-limit | **Should exist (AF) — activate** | FACT: present but dormant. |
| **Scheduling** | Exists: `proactive_scheduler` (poll-based, unimported) | **Already exists (AF) — wire** | Keep, fix dead integration. |
| **Observability** | Partial: in-memory `tracing`, no OTel | **Should exist (AF) — export** | FACT: no external export; must integrate a real observability plane. |
| **Audit** | Exists: `AuditEntry`, `governance_audit_store` (not durable in World A) | **Split: reasoning audit (AF) / decision audit (ActionGate)** | ActionGate already has tamper-evident hash-chained audit. |
| **Decision trace** | Exists but analytics rollup, not causal-replayable | **Should exist (AF) — or use ACP's** | FACT: ACP has a real hash-chained `DecisionTrace`. Reuse the pattern rather than overclaim replay. |
| **Policy simulation** | Exists: `policy_simulation`, `policy_replay` | **Already exists (AF)** | Genuine strength; keep. |
| **Dry run** | Partial: fields accepted, not implemented; `shadow_ai` is a different concept | **Should exist (AF) / delegate to ACP shadow** | ACP is entirely shadow-capable; reuse. |
| **Risk scoring** | Exists: `ToolRiskClassifier` (AUROC 0.82), raw-entropy (0.857) | **Already exists (AF)** | The framework's best asset; keep as evidence. |
| **Runtime adaptation** | Exists: `adaptive_policy` | **Already exists (AF)** | Keep (relabel honestly). |
| **Safety envelopes** | Partial: `safety_contract`; `safety_bounds` DORMANT | **Should exist (AF) — activate** | FACT: dormant primitive. |
| **Context routing** | Partial: `request_enrichment` | **Should exist (AF)** | Keep; compose with Context Minimization. |
| **Context ownership** | N/A | **Delegate to Context Minimization** | Not AF's. |
| **Agent ownership** | Absent | **Should exist (AF-V2)** | Pairs with agent identity/registry. |
| **Versioning** | Partial: `policy_bundle` versioned; product versioning incoherent | **Should exist (AF) — fix** | FACT: v1.4→v6.2 across docs. |
| **Plugin architecture** | Partial: adapter/critic/tool Protocols | **Already exists (AF) — formalize** | Good bones; make it a first-class extension SDK. |
| **Control APIs** | Exists: `governance_api` FastAPI (minimal) | **Should exist (AF) — harden** | Add auth/TLS; reposition as pre-authorization API. |
| **Control SDK** | Exists: the library itself | **Already exists (AF)** | The Python library *is* the SDK. |

**INTERPRETATION.** The gap analysis splits cleanly into three buckets:
1. **Already strong (keep):** tool registry/permissions, risk scoring, policy simulation, runtime adaptation, plugin bones, control SDK. These are *proposer/agent-runtime* capabilities — exactly where AF should be strong.
2. **Delegate, don't build:** hard action-authorization, credential brokering, approver-quorum authority, operational-safety, infra rollback, context compression, tamper-evident decision audit. **All already exist in ActionGate/ACP/Context Minimization.** Building them in AF is the duplication trap.
3. **Genuinely missing for a platform (build in AF-V2):** agent identity, agent/capability registry, multi-agent coordination, lifecycle, checkpointing, real observability export. These are what separate "a single-agent library" from "an agent runtime platform" — and none of them are control-plane responsibilities; they are *agent-runtime* responsibilities.

**FACT-anchored conclusion for Part 5:** the framework does **not** need to become a control plane to mature. It needs to (a) delegate its authorization-shaped parts to the existing control plane, and (b) build the *agent-runtime* capabilities (identity, registry, coordination, lifecycle, checkpointing, observability) it currently lacks.

---

## Part 7 — The strict ACP ↔ Agentic Framework boundary

**FACT (from ACP's own boundary docs).** ACP already draws hard internal boundaries: Context Minimization ⟂ ActionGate ⟂ ACP, "duplicated-logic 0, ownership violations 0" (`acp/RESPONSIBILITY_MATRIX.md`). The Agentic Framework must slot into this *without adding a fifth overlapping owner*.

### The boundary

```
┌──────────────────────────────────────────────────────────────┐
│  AGENTIC FRAMEWORK  (proposer / agent runtime — PROBABILISTIC) │
│  owns:                                                         │
│   • goal decomposition, planning, reasoning, reflection        │
│   • agent identity, registry, lifecycle, coordination (V2)     │
│   • memory, agent-behavior policy, scheduling                  │
│   • risk pre-screen + uncertainty scoring  ── emitted as ─┐    │
│   • reasoning trace + observability export                │    │
└───────────────────────────────────────────────────────────┼───┘
                                                            │ evidence
                     proposes an action  +  evidence         ▼
┌──────────────────────────────────────────────────────────────┐
│  AI CONTROL PLANE  (governor — DETERMINISTIC, fail-closed)     │
│   Context Minimization → owns what may be READ                 │
│   ActionGate           → owns AUTHORIZATION (token, credential,│
│                          quorum, hard policy, tamper audit)    │
│   ACP                  → owns OPERATIONAL SAFETY (live state)   │
│   Composition          → links verdicts                        │
└──────────────────────────────────────────────────────────────┘
```

### What each side owns (no duplicated ownership)

| Concern | Agentic Framework | AI Control Plane (ACP stack) |
|---|---|---|
| What to read | assemble context | **Context Minimization** compresses it |
| What to propose | **owns** (LLM planning/reasoning) | consumes the proposal |
| Whether authorized | produces *risk/uncertainty evidence* | **ActionGate** decides (sole authority) |
| Whether operationally safe | — | **ACP** decides (sole authority) |
| Human approval | routes/UX | **ActionGate** binds the authoritative quorum |
| Credentials | never holds | **ActionGate** brokers single-use |
| Decision audit | reasoning trace | **ActionGate** tamper-evident record |
| Agent identity/registry | **owns** | consumes the agent principal |
| Operational rollback | — | **ACP** |
| Agent-state rollback/checkpoint | **owns** | — |

**RECOMMENDATION (the one-line contract).** *The Agentic Framework decides **what to attempt and how confident it is**; the AI Control Plane decides **whether the attempt may execute and is safe**. The framework never mints authority; the control plane never reasons.* This mirrors ACP's own "propose ⟂ authorize ⟂ operational-safety" split and adds the framework as the explicit owner of "propose."

**FACT — this integration is natural for ActionGate specifically:** ActionGate already accepts *optional evidence* that "can only raise scrutiny … never lower a hard invariant" (`ACTIONGATE_VC_BRIEF.md`). The framework's risk score + raw-entropy + confidence-risk-gap map directly onto that evidence slot. No new ActionGate concept is required.

---

## Part 8 — Agentic Framework V2 (future architecture)

### Design principles
1. **Proposer, not governor.** The framework is the probabilistic agent tier; authority lives in the control plane.
2. **One pre-screen path.** Collapse World A `mcp_gateway` and World B `GovernanceService` into a single agent-side pre-authorization component that emits ActionGate evidence.
3. **Advisory signals, not blocking heuristics.** JEPA/sovereign/trust/CG demote to advisory; only ActionGate/ACP block.
4. **Honest naming.** Retire falsified CG governance; relabel "gradient descent"/"replayable"/"streaming"/"cost caps" to what they actually are.
5. **Build the agent-runtime gaps** (identity, registry, coordination, lifecycle, checkpointing, observability export) — not control-plane gaps.

### V2 module map

```
Agentic Framework V2
├── runtime/                     (was: agent.py, builders, dispatcher)
│    ├── agent loop  (uniform budget/deadline/approval on ALL paths)
│    ├── agent identity + registry            ← NEW (V2)
│    ├── capability registry                  ← NEW (V2)
│    ├── multi-agent coordination (opt-in)    ← NEW (V2)
│    └── lifecycle + checkpointing            ← NEW (V2)
├── reasoning/                   (KEEP: goal_decomposition, reflective_loop,
│    │                                  reasoning_workflows, adaptive_prompts,
│    │                                  local_critic, coherence_tracker)
│    └── optional generation-control plug-in → CSR Steering Controller
├── memory/                      (KEEP: memory_store, retention; finish M3)
├── policy/                      (KEEP: agent-BEHAVIOR policy only —
│    │                                  policy_bundle, domain_policy, adaptive_policy,
│    │                                  policy_simulation, policy_replay,
│    │                                  policy_control_plane → renamed)
├── prescreen/                   (MERGED World A+B: risk classify + confidence +
│    │                                  uncertainty → ActionGate EVIDENCE)
│    ├── ToolRiskClassifier      (KEEP)
│    ├── raw_entropy / confidence_risk_gap (KEEP — validated)
│    └── evidence emitter → ActionGate         ← NEW integration seam
├── approval/                    (KEEP routing; authority binds to ActionGate)
├── observability/               (tracing + trace_viewer; ADD OTel export) ← NEW export
├── adapters/                    (KEEP llm_adapters; CSR/ContextMin/ActionGate clients) ← NEW clients
└── advisory-signals/            (DEMOTED: jepa, sovereign_bridge, olm_bridge,
                                        signal_adapters, trust/ — signal-only, non-blocking)
        └── CG sovereign-state governance → REMOVED
```

### Control-plane integration seams (new in V2)
- **ContextMinimizationClient** — optional pre-read compression before the LLM reads.
- **ActionGateClient** — submit proposed action + evidence; receive the 6-outcome verdict + token; the framework executes *only* with a minted token.
- **ACP is reached through ActionGate composition** (the framework does not call ACP directly; ACP evaluates the same identity-bound action downstream, per `acp/ACP_ACTIONGATE_BOUNDARY.md`).

### What can be reused unchanged (FACT-grounded)
- **Entire reasoning tier** — goal decomposition, reflective loop, reasoning workflows, adaptive prompts, local critics: unchanged. This is the differentiated value and touches no control-plane concern.
- **Memory** — `memory_store`/`retention`: unchanged (finish the pending M3 wiring).
- **Agent-behavior policy** — `policy_bundle`, `domain_policy`, `adaptive_policy`, `policy_simulation`, `policy_replay`: unchanged; only their *scope* is clarified (behavior, not action-authorization).
- **Tool registry + risk taxonomy** — `ToolSpec`, `ToolCatalog`, `ToolRiskClassifier`: unchanged; the *output* is re-routed to ActionGate as evidence instead of being the final authority.
- **Validated signals** — `raw_entropy_adapter`, `confidence_risk_gap`: unchanged (demoted to advisory/evidence, which they effectively already are).
- **Runtime plumbing** — streaming events, cancellation, structured output, tracing scaffolding: unchanged (add OTel export).
- **The FastAPI control surface** — `governance_api`: reused as the *pre-authorization* API (add auth/TLS; relabel advisory).

### What changes (FACT-grounded)
- **`GovernanceService` (World B)** — from standalone authority → agent-side evidence producer, merged with `mcp_gateway`'s pre-screen. It stops being a second PDP.
- **`mcp_gateway` final-authorization** — the ALLOW/BLOCK *authority* moves to ActionGate; the gateway keeps risk classification, escalation UX, and (dev-only) local execution.
- **`jepa_governance`, `trust/`, `sovereign_bridge`, `olm_bridge`, signal_adapters** — demoted to non-blocking advisory.
- **CG sovereign-state governance** — removed from the governance path (falsified).
- **`governance_adapter` (external P52 facade)** — removed; one schema family.

**INTERPRETATION.** V2 is *less* than V1 in governance surface and *more* in agent-runtime capability. It deletes the duplicated soft-control-plane and invests the freed complexity budget into the things that actually make an agent runtime valuable at scale: identity, registry, coordination, lifecycle, and real observability. The migration path and compatibility guarantees are in `MIGRATION_ROADMAP.md`.
