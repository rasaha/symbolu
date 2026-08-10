# Deliverable 5 — Multi-Agent Readiness

Should Agent Runtime V2 remain single-agent, become multi-agent capable, or be hierarchical? Recommendation with an architecture, grounded in what exists today.

Labels: `FACT` / `INTERPRETATION` / `RECOMMENDATION` / `SPECULATION`.

---

## 1. Where the runtime is today

**FACT.** The current framework is strictly single-agent by design:
- `agentic/agentic_framework/README.md`: "Not a multi-agent platform. Governs a single agent's execution path. No agent-to-agent handoffs or orchestration."
- `FRAMEWORK_STATUS.md`: multi-agent orchestration is "Intentionally deferred… Out of scope."
- No agent registry, no agent identity, no capability registry (confirmed absent in the prior review).
- The independent readiness audit: "a single-generation, plan-then-execute loop, not a multi-step agent."

**INTERPRETATION.** The runtime is not even a mature *single-agent multi-step* loop yet (it is closer to plan-then-execute). Jumping to multi-agent before the single-agent loop is durable and observable would repeat the framework's historical pattern of building breadth over depth (the falsified signal apparatus).

---

## 2. The three options

| Option | What it means | Fit for this runtime |
|---|---|---|
| **Single-agent (stay)** | One agent, one execution path | FACT: matches today; but forecloses the enterprise workflows in Deliverable 8 (IT ops, support triage) that are inherently multi-role |
| **Multi-agent capable** | Multiple cooperating agents, peer handoff, shared/scoped memory | Natural next step; the enterprise use cases need it |
| **Hierarchical** | An orchestrator agent decomposes and delegates to sub-agents, recursively | The most powerful; also the most complex; premature until identity/registry/coordination exist |

---

## 3. Recommendation

**RECOMMENDATION — build toward *hierarchical-capable*, in three staged layers, but ship *single-agent-first with multi-agent seams*.**

The runtime should be architected so multi-agent and hierarchical are *configurations of the same primitives*, not separate products:

```
Layer 0  SINGLE AGENT (harden first)
         one AgenticLLMWrapper, durable loop, checkpointing, observability, Control-Plane integration

Layer 1  MULTI-AGENT CAPABLE (add coordination primitives)
         agent identity + registry + capability registry
         peer handoff (pass goal + scoped memory to another agent)
         shared memory with per-agent scoping

Layer 2  HIERARCHICAL (compose Layer 1)
         an orchestrator agent = an agent whose "tools" are other agents
         recursive decomposition: a sub-goal is dispatched to a sub-agent
         each sub-agent runs the SAME pipeline, proposes to the SAME Control Plane
```

**INTERPRETATION — why hierarchy is "just composition."** A hierarchical orchestrator is an agent whose action space includes "invoke sub-agent X on sub-goal Y." That invocation is itself a runtime step and, if it triggers a consequential action, flows through the Control Plane like any other. So hierarchy needs **no new governance** — it reuses the single-agent pipeline recursively. This is the key architectural insight that keeps multi-agent from re-introducing a governance layer.

---

## 4. How multi-agent interacts with the AI Control Plane (no new ownership)

**RECOMMENDATION — the invariants that keep multi-agent clean:**

1. **Every agent has a distinct principal.** Each sub-agent's Execution Proposals carry its own `agent_principal` (FACT: ActionGate binds identity per action; multiple agents = multiple principals, no change to ActionGate).
2. **Authority is never delegated between agents.** A parent agent cannot pass a token to a child; each agent re-proposes and gets its own token. This prevents privilege escalation via delegation — the exact concern ActionGate's single-use nonce + SoD already guard (FACT: `acp/ACP_ACTIONGATE_BOUNDARY.md`).
3. **Coordination is a runtime concern; authorization is per-action.** Handoff, shared memory, and orchestration live entirely in the runtime. The Control Plane still sees only a stream of identity-bound proposals — it does not know or care whether one agent or ten produced them.
4. **Shared memory is scoped, not global.** Memory sharing is a runtime capability with per-agent read/write scopes; it never bypasses Context Minimization for what any single agent's model reads.

**INTERPRETATION.** Multi-agent multiplies the *number of proposers* but does not change the *ownership boundary*. This is why the runtime can safely grow to hierarchical without ever encroaching on ActionGate/ACP.

---

## 5. Prerequisites (gating the sequence)

**RECOMMENDATION — do not start Layer 1 until Layer 0 is real:**

| Prerequisite | Why it gates multi-agent | Source (FACT) |
|---|---|---|
| Durable run store + checkpointing | Multiple long-running agents need resumable state | absent today (trace is analytics-only) |
| Agent identity | Coordination is meaningless without distinct principals | absent today |
| Observability export | Debugging N agents by in-memory trace is infeasible | in-memory only today |
| Control-Plane integration (ActionGate client) | Each agent must propose→authorize→execute correctly *alone* before doing it in concert | not wired today |

**SPECULATION (labeled).** If the enterprise traction is strongest in a domain that is inherently multi-role (e.g., IT-ops runbooks with a diagnoser + a remediator + an approver-liaison), Layer 1 could be pulled forward — but only after Layer 0's durability and Control-Plane integration are proven, because a flaky single agent multiplied N times is N times as flaky.

---

## 6. Summary

- **Stay single-agent-first**, but architect every primitive (identity, memory, proposal) so multi-agent is a configuration.
- **Target hierarchical-capable**, achieved by recursion over the single-agent pipeline — no new governance.
- **The Control Plane is unaffected**: more agents = more identity-bound proposals; authority is per-action and never delegated.
- **Gate the expansion** on Layer 0 durability + Control-Plane integration; do not build breadth before depth.
