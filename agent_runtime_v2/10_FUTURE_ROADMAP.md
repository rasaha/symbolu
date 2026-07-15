# Deliverable 10 — Future Roadmap (2–3 years)

A design-stage roadmap for the Agent Runtime, split into three tracks: **Core Runtime**, **AI Control Plane integration**, and **AI Infrastructure integration**. This is a plan, not a commitment; no implementation is part of this milestone.

Labels: `FACT` (current state) / `RECOMMENDATION` (planned work). Sequencing rationale follows the prior review's principle: *depth before breadth, honesty before architecture, delegate before duplicate.*

---

## 0. Starting point (FACT)

- Runtime is a late-prototype single-agent, plan-then-execute loop; single CLI entry point; no CI gate; in-memory trace; two disconnected governance stacks; falsified CG signal apparatus (all FACT from the prior review).
- The Control Plane (ActionGate/ACP/Context-Min) exists as real-but-shadow, cross-domain, deterministic (FACT).
- No integration seam between runtime and Control Plane exists yet (FACT).

---

## Track A — Core Runtime

| Horizon | Work (RECOMMENDATION) | Unlocks |
|---|---|---|
| **0–3 mo** | Truth-in-labeling: retract "replayable/hard-cost/streaming/CI-passing/CG-moat" claims; add a real CI gate; fix cross-test state pollution | A trustworthy baseline to build on |
| **3–6 mo** | Consolidate internal duplication: merge World A + World B into one pre-screen; single safety-threshold source; delete the P52 schema facade; demote JEPA/trust/signal-adapters to advisory; remove CG governance | One coherent runtime; no self-duplication |
| **6–9 mo** | **Durable run store + checkpointing** (replaces the overstated trace); resumable long-running tasks | Reliable long-running agents; honest "replay" |
| **9–12 mo** | **Observability export** (OTel); durable reasoning-trace record | Enterprise-grade debuggability |
| **12–18 mo** | **Agent identity + registry + capability registry** | Prereq for multi-agent + meaningful Control-Plane binding |
| **18–30 mo** | **Multi-agent coordination (Layer 1)** then **hierarchical (Layer 2)** — recursion over the single-agent pipeline | Multi-role enterprise workflows (support, IT-ops) |
| **Throughout** | Wire `reasoning_workflows` into the loop; formalize retry/backoff; finish memory retention (M3); fix `proactive_scheduler` dead wiring; `coherence_tracker.factual_alignment` | Close the "exists but unwired" debt |

## Track B — AI Control Plane integration

| Horizon | Work (RECOMMENDATION) | Depends on |
|---|---|---|
| **3–6 mo** | Define the **Execution Proposal** boundary object + evidence schema (Deliverable 1 §4) | Track A consolidation |
| **6–9 mo** | **`ActionGateClient`** (opt-in, default OFF): submit proposal + evidence → verdict + token; execute only with token; emit risk/raw-entropy as scrutiny-only evidence | Proposal schema; ActionGate transport |
| **9–12 mo** | **Verdict-branch handling** in the loop (DENY/HOLD/ESCALATE/REQUEST_MORE_EVIDENCE/SIMULATE_AND_RETRY) driving reflection/self-correction (Deliverable 3 §4) | ActionGateClient |
| **9–12 mo** | **`ContextMinimizationClient`** (opt-in): optional pre-read compression | CM transport |
| **12–15 mo** | **Approval-authority binding**: runtime routes UX; ActionGate owns the quorum decision | Identity work |
| **15–24 mo** | **Runtime-agnostic Control-Plane interface**: publish the seam so ActionGate/ACP can govern *any* agent framework (Deliverable 9 §4.5) | Stable seam |
| **24–36 mo** | **Domain adapters for ACP** beyond cloud/robotics (finance/healthcare/support operational-safety) | ACP core is cross-domain by design (FACT) |

**FACT constraint honored:** every Track-B item is a *client in the runtime calling the Control Plane*; none modifies ActionGate/ACP/Context-Min. If a network transport doesn't exist yet (FACT: ActionGate transport is in-process/planned), the client targets the in-process reference until a transport ships. Because evidence can only *raise* scrutiny, opting in is monotonically safe.

## Track C — AI Infrastructure integration

| Horizon | Work (RECOMMENDATION) | Rationale |
|---|---|---|
| **6–12 mo** | **KVPro** under the runtime's model calls (drop-in vLLM backend path, FACT) | Cut serving cost for reasoning-heavy loops (many LLM calls per task) |
| **9–15 mo** | **Hybrid LLM** as a first-class long-context model option in `llm_adapters` | Better long-context reasoning for IT-ops/healthcare workflows |
| **12–18 mo** | **CG LLM** as an optional generation-control + answer-audit layer (advisory, not governance) | Frame control + audit for regulated domains; the 32-D signal is *evidence*, not a gate (FACT: falsified as governance) |
| **15–24 mo** | **Cloud Scaling Controller** scales the runtime's own serving fleet — itself governed by ACP (FACT: ACP already consumes `cloud_controller`) | Closed loop: the platform scales and governs itself |

---

## Roadmap on one timeline

```
        0────3────6────9────12───15───18───24────────30────────36 (months)
Core    │truth│dedup│durable│OTel │identity/registry│  multi-agent → hierarchical
CtrlP   │           │proposal│AGClient│verdicts│CMClient│approval│runtime-agnostic│domain adapters
Infra   │                    │KVPro   │HybridLLM │CG LLM  │CSC self-scaling
```

---

## Sequencing rationale (INTERPRETATION)

1. **Track A leads.** You cannot integrate a Control Plane from a runtime that duplicates governance internally and overstates its own capabilities. Consolidation + honesty first.
2. **Track B is the strategic core.** The integration seam is where Ugence's differentiation lives (Deliverable 9). It starts as soon as the proposal schema is stable and stays opt-in/monotonically-safe throughout.
3. **Track C is opportunistic.** Infrastructure integration improves economics but is not on the critical path to the differentiated product; it lands as each sibling matures.
4. **Multi-agent is deliberately late.** It is the biggest competitive gap (Deliverable 9) but the highest-risk build; it is gated on durability + identity + Control-Plane integration so breadth never precedes depth.

**RECOMMENDATION — the north star.** In 2–3 years the Agent Runtime is a durable, observable, multi-agent-capable runtime whose every consequential action is authorized by ActionGate and safety-checked by ACP — and whose Control-Plane seam is open enough that Ugence can govern *any* agent framework, not just its own. The moat is the governed boundary, not the runtime features.
