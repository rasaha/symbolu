# Product Positioning (Parts 6 & 9)

Where the Agentic Framework belongs, what it should evolve into, and what it should be called.

Labels: `FACT` / `INTERPRETATION` / `RECOMMENDATION` / `SPECULATION`.

---

## 0. A required correction about the taxonomy in the question

**FACT.** The task asks us to place the Agentic Framework among three product families — *Specialized AI Systems*, *AI Control Plane*, *AI Infrastructure*. Two of these three labels are **not** how the repo currently organizes itself:
- The current authoritative framing (`docs/UGENCE_PITCHBOOK.md`) is **"AI Infrastructure Platform | Five Composing Modules + Two Standalone Verticals."** The Agentic Framework is module #3.
- **"AI Control Plane"** appears **only** in the internal `acp/` docs describing the Context-Min + ActionGate + ACP composition — it is *not* a pitchbook product category.
- **"Specialized AI Systems"** appears **nowhere** in the repo (repo-wide grep: no matches). The closest concept is "two standalone verticals" (PSE, Robotics).

**INTERPRETATION.** The three-family taxonomy is a *proposed* portfolio structure, not an established one. That is fine — this milestone is partly about deciding that structure. But the conclusion must be labeled as a recommendation about a hypothesized taxonomy, not a description of the repo as-is. I answer the question within the proposed taxonomy while flagging where it diverges from current documents.

---

## Part 6 — What should the Agentic Framework evolve into?

Candidate categories offered by the task: Agent Runtime · Agent Operating System · Agent Orchestrator · Agent Governance Layer · AI Control Plane Runtime · Workflow Engine · Execution Coordinator.

### Evidence-based elimination

| Candidate | Verdict | Why (FACT-anchored) |
|---|---|---|
| **AI Control Plane Runtime** | **Reject** | FACT: the repo already has an AI Control Plane (deterministic, fail-closed, cross-domain, ActionGate+ACP+Context-Min). The framework is probabilistic, threshold-based, single-agent, and its authorization parts *duplicate* that plane at a softer tier. Reclassifying it here creates the exact duplicated ownership ACP forbids. |
| **Agent Governance Layer** | **Reject (as the primary identity)** | FACT: the framework's governance is "recommends but doesn't enforce," its signal moat is falsified/off, its two PDPs don't agree, and hard authorization belongs to ActionGate. Governance is a *feature it emits as evidence*, not its center of gravity. Also collides with ACP's governance identity. |
| **Agent Operating System** | **Reject (overclaim)** | FACT: no multi-agent, no agent registry, no agent identity, no lifecycle, no scheduling daemon. An "OS" claim is years and several missing subsystems away. |
| **Workflow Engine** | **Reject** | FACT: `reasoning_workflows` is standalone and unwired into the loop; there is no durable workflow state, no checkpointing, no compensation. It is not a workflow engine. |
| **Execution Coordinator** | **Partial** | FACT: it does coordinate a single agent's execution loop — but "coordinator" understates the reasoning value and overstates the multi-agent capability (none). |
| **Agent Orchestrator** | **Partial (aspirational)** | FACT: single-agent only today; "orchestrator" implies multi-agent, which is the V2 gap. Valid *target* if multi-agent coordination is built. |
| **Agent Runtime** | **Accept (primary)** | FACT: matches the shipped reality precisely — a code-first runtime that wraps an LLM with goal decomposition, reflection, memory, safety pre-gate, tool dispatch, and runtime primitives, governing a single agent's execution path. Its own docs converge on "governed runtime." |

### Recommendation (Part 6)

**RECOMMENDATION.** The Agentic Framework is, and should be positioned as, an **Agent Runtime** — specifically a *governed, model-agnostic agent runtime that produces control-plane-ready proposals*. Its evolution target is an **Agent Runtime → (optionally) Agent Orchestrator** once multi-agent coordination, agent identity, and a registry exist (Part 5). It should **not** evolve into an AI Control Plane, an Agent OS, or a Workflow Engine — the first duplicates ACP, the other two overclaim by several missing subsystems.

**Technical support.** The framework's differentiated, defensible assets are all *runtime/proposer* assets: goal decomposition, reflective self-revision, cost-aware local critics, a 5-level tool-risk taxonomy (AUROC 0.82), raw-entropy uncertainty (AUROC 0.857), and an adaptive per-session policy. None of these are control-plane assets; all of them make a *better agent*. The framework's weakest, most-contested claims (CG signal moat, replayable trace, hard cost caps, blocking JEPA) are exactly the ones that were reaching toward "control plane / governance layer" — and they are the ones the evidence retracts.

---

## Part 9 — Placement in the three product families, and naming

### 9.1 Where it belongs

**FACT — the three tiers as they actually exist in the repo:**
- **AI Infrastructure** = the substrate modules (KV Pro, Cloud Scaling Controller) — compute/memory/scaling plumbing.
- **AI Control Plane** = the deterministic governor stack (Context Minimization + ActionGate + ACP) — authorize/operational-safety.
- **Specialized AI Systems** (proposed) = the standalone verticals + applied runtimes (PSE naming vertical, Autonomous Robotics, and — by this analysis — the Agent Runtime).

**RECOMMENDATION.** Place the Agentic Framework in **Specialized AI Systems**, as the **Agent Runtime** product — the applied, probabilistic, model-agnostic system that *sits above and feeds* the AI Control Plane. It is not infrastructure (it is not compute/memory plumbing) and it is not the control plane (it does not hold authority). It is a specialized applied AI system: a governed agent.

**The split the evidence forces (answering the headline question — option 4).** The current "Agentic Framework" should be **split into two products across two families**:
1. **Agent Runtime** → *Specialized AI Systems*. The proposer: reasoning, planning, reflection, memory, agent-behavior policy, risk pre-screen. (World A + the reasoning/memory/policy modules + the merged pre-screen.)
2. **The agent-action authorization concern** (World B `GovernanceService`, the gateway's final-authz, approver authority) → **merge into the AI Control Plane (ActionGate)** as evidence-fed authorization, not a separate product. It does not become a third product; it *disappears into ActionGate*.
3. The **falsified CG/sovereign governance** → retired (not a product).

So: not "one product reclassified," but "**one product split, with its control-plane-shaped half folded into the existing control plane and its reasoning half standing up as the Agent Runtime.**"

### 9.2 Naming (avoid generic buzzwords)

**FACT — the naming problem is real and documented:** the product is variously "Agentic Framework," "Sentinel," and shipped under "Ugence Labs"/"Ugence Labs"; the word "control plane" is used in *four* unrelated places (ACP, the framework's `policy_control_plane`, CSR's "vendor-agnostic control plane," the Cloud Controller). "Agentic Framework" is itself a generic industry term (every vendor has one).

**RECOMMENDATION — names for the Agent Runtime product** (avoiding "framework," "platform," "AI," "agentic," "control plane"):

| Candidate | Rationale | Caution |
|---|---|---|
| **Proposer** (or **Ugence Proposer**) | Names its exact role in the control-plane pipeline — it produces authorized-*able* proposals. Ties directly to ACP's "proposal" ownership. | Understated; may read as internal jargon. |
| **Deliberator** | Captures the reflective/goal-decomposition/critic reasoning loop that is the differentiated value. | Slightly abstract. |
| **Sentinel Runtime** | Reuses the existing internal "Sentinel" brand; "Runtime" is honest about the category. | "Sentinel" leans governance/security, the retracted moat — could mislead. |
| **Cognition Runtime** | Names the reasoning tier plainly. | "Cognition" risks the same overclaim as the CG apparatus. |

**Primary recommendation:** **"Proposer"** as the architectural role name and **"Ugence Agent Runtime (codename Sentinel)"** as the product name — the former makes the control-plane boundary self-documenting; the latter is honest about the category and preserves brand continuity.

**RECOMMENDATION — fix the "control plane" collision:** reserve **"AI Control Plane"** exclusively for the ACP stack (Context-Min + ActionGate + ACP). Rename the framework's internal `policy_control_plane.py` surface to **"agent policy console"** or **"behavior policy surface"** so it does not read as a competing control plane. Rename CSR's "vendor-agnostic control plane" phrasing to "generation control layer." One term, one owner.

### 9.3 Portfolio picture (recommended)

```
Ugence Labs
├── Specialized AI Systems     — Hybrid LLM · LLM Steering Controller · Agent Runtime · Autonomous Runtime
├── AI Control Plane           — Context Minimization · ActionGate · ACP   (deterministic governor)
└── AI Infrastructure          — KV Pro · Cloud Scaling Controller
                                  (PSE naming remains a standalone vertical; canonical taxonomy: UGENCE_PLATFORM_OVERVIEW.md)
```

**INTERPRETATION.** In this picture the story is clean and non-overlapping: *Infrastructure* makes AI cheap and fast; the *Control Plane* makes AI actions safe and authorized; *Specialized Systems* (including the Agent Runtime) do the actual applied work and *feed* the control plane. The Agent Runtime's tagline writes itself without buzzwords: **"the agent that proposes; the control plane disposes."**
