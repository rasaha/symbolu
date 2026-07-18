# Part 4 — Ownership Boundary

The definitive three-tier ownership matrix for a runtime-agnostic platform: **Runtime** owns intelligence + execution, **Control Plane** owns governance, **Infrastructure** owns efficiency + scale. Every responsibility has exactly one owner. No overlap. (Canonical portfolio taxonomy: `UGENCE_PLATFORM_OVERVIEW.md`.)

Labels: `FACT` (repo evidence) · `RECOMMENDATION`. This extends `../agent_runtime_v2/06_RUNTIME_VS_CONTROL_PLANE_OWNERSHIP.md` to the runtime-agnostic case (any runtime, not only Ugence's).

---

## 1. The three-tier matrix

| # | Responsibility | Sole owner | Evidence / rationale |
|---|---|---|---|
| 1 | Goal intake, decomposition, planning | **Runtime** | any runtime; ACP "consumes a planner" (FACT) |
| 2 | Reasoning, reflection, self-correction | **Runtime** | runtime-internal; Control Plane never reads it (FACT: grep clean) |
| 3 | Memory (working/episodic) | **Runtime** | runtime-internal |
| 4 | Tool **selection** | **Runtime** | which tool to attempt |
| 5 | Uncertainty / risk **estimation** | **Runtime** | emitted as scrutiny-only evidence (FACT: ActionGate evidence contract) |
| 6 | Execution proposal construction (via adapter) | **Runtime + Adapter** | the adapter normalizes; the runtime originates |
| 7 | Workflow orchestration, retries, long-running state | **Runtime** | runtime-internal |
| 8 | Multi-agent coordination | **Runtime** | more principals, same boundary (Part 8) |
| 9 | Human interaction (UX / routing) | **Runtime** | routing only |
| 10 | Agent identity assertion (the principal) | **Runtime** | the runtime knows who is acting; ActionGate binds it |
| 11 | **Context relevance / compression** | **Control Plane (Context Minimization)** — *optional, ActionGate-coupled* | FACT: coupled to ActionGate oracle (`compressor.py:36–58`); optional layer |
| 12 | **Authorization** — may this exact action execute, once? | **Control Plane (ActionGate)** | FACT: 6-outcome verdict, sole authority (`gate.py`) |
| 13 | Deterministic hard-policy enforcement | **Control Plane (ActionGate)** | FACT: enterprise-signed policy (`policy.py`) |
| 14 | Token minting / credential brokering | **Control Plane (ActionGate)** | FACT: single-use token + broker |
| 15 | Approver-quorum authority (four-eyes) | **Control Plane (ActionGate)** | FACT: approvals bound to action_hash |
| 16 | Tamper-evident authorization audit | **Control Plane (ActionGate)** | FACT: hash-chained audit |
| 17 | **Operational safety** — safe against live state now? | **Control Plane (ACP)** | FACT: readiness/blast/capacity/freeze |
| 18 | Live-state action selection over admissible set | **Control Plane (ACP)** | FACT: `filter_admissible` + selector |
| 19 | Verdict composition / eligibility | **Control Plane (Composition)** | FACT: `composition.py`, 8 classes |
| 20 | World-state modeling per domain | **Control Plane (ACP domain adapter)** | FACT: `WorldStateProvider` (`interfaces.py:24–36`) |
| 21 | Infrastructure rollback (single action) | **Control Plane (ACP)** | FACT: rollback-availability gating |
| 22 | Model inference (long-context / semantic control) | **Specialized** (Hybrid LLM, LLM Steering Controller) | model substrate |
| 23 | KV-cache efficiency | **Infrastructure (KVPro)** | FACT: drop-in vLLM path |
| 24 | Serving autoscaling (safety-gated) | **Infrastructure (Cloud Scaling Controller)** — itself governed by ACP | FACT: ACP consumes `cloud_controller` |
| 25 | Reasoning trace / runtime telemetry export | **Runtime** | distinct from ActionGate's decision audit |

---

## 2. The one-line boundary

> **Runtime** decides *what to attempt and how to reason.*
> **Control Plane** decides *what may read, what is authorized, and what is operationally safe.*
> **Infrastructure** decides *how cheaply and at what scale it all runs.*
> Nothing decides anything twice.

---

## 3. The three contested boundaries (resolved for the runtime-agnostic case)

**FACT-anchored — these are where a naive design would overlap:**

1. **Risk/safety.** The runtime's risk score is *evidence that can only raise scrutiny*; the hard gate is ActionGate (authorization) + ACP (operational). Cut line: the runtime never renders the final ALLOW/BLOCK. (FACT: ActionGate evidence "can only raise scrutiny," `ACTIONGATE_VC_BRIEF.md`.)
2. **Context.** The runtime *assembles* its context; Context Minimization *optionally* compresses it against the ActionGate decision. Cut line: context relevance-for-authorization is the Control Plane's; context assembly is the runtime's. (FACT: Context Min is ActionGate-coupled, `compressor.py:36–58`.)
3. **Identity.** The runtime *asserts* the principal; ActionGate *binds* it to the exact action; ACP *re-binds* the same identity for operational safety. Cut line: the runtime names who is acting; the Control Plane makes that identity authoritative and non-replayable. (FACT: single-use nonce, action-bound approvals.)

---

## 4. Why this matrix survives multiple runtimes

**RECOMMENDATION / INTERPRETATION.** The matrix is runtime-*count*-invariant: adding runtimes (or agents within a runtime) only adds rows-1..10 producers. Rows 11–21 (the Control Plane) are unchanged because they consume only the canonical proposal + domain world-state + enterprise policy — none of which scales with the number or type of runtimes. This is the structural reason a *shared* Control Plane across many runtimes (Part 8) does not create overlap: the owners of governance responsibilities never multiply.
