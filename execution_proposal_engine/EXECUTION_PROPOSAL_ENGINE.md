# The Agent Runtime as an Execution Proposal Engine — Falsification & Verdict

**Milestone:** design-first, evidence-first. No code, no production changes, no marketing.
**Main question:** can the Agent Runtime evolve into a *pure Execution Proposal Engine* — owning reasoning, planning, decomposition, tool selection, memory, reflection, uncertainty estimation, and proposal generation, while authorization, operational safety, deployment decisions, and governance permanently leave it?
**Method:** attempt to **disprove** the architecture first. If it survives, strengthen it with concrete corrections rather than agreeing.

Labels on every substantive claim: `FACT` · `INTERPRETATION` · `RECOMMENDATION` · `SPECULATION` · `EXTERNAL KNOWLEDGE`.
Evidence base: the three prior milestones committed on this branch (`../agentic_framework_review/`, `../agent_runtime_v2/`, `../ai_control_plane_v3/`) and the source they cite. The vendor-neutral schema is in `EXECUTION_PROPOSAL_SCHEMA.md`.

---

## 0. Falsification first — five attempts to disprove the architecture

I tried to break the "pure Execution Proposal Engine" thesis five ways before rendering a verdict. Two attempts succeeded *partially* and force corrections; three failed (the architecture held).

### F1 — The one-way pipeline is wrong: execution results return to the runtime → **PARTIAL DISPROOF (forces a correction)**
**Claim under test:** "Everything after the Execution Proposal belongs to the AI Control Plane."
**FACT.** The runtime's actual loop does not end at the proposal. `agent.py` runs `…7. Execute actions → 8. Update Memory → 9. Check for intervention` (`agentic/agentic_framework/agent.py:490–514`), and the Agent Runtime V2 pipeline is explicitly `…propose → [Control Plane] → execute → 11. Observation → 12. Reflection → 13. Memory update → 14. next step` (`../agent_runtime_v2/03_RUNTIME_PIPELINE_V2.md`).
**INTERPRETATION.** The proposal boundary is real, but it is **not a terminus** — it is a *segment*. The Control Plane owns `authorize → execute`; the **execution result returns to the runtime**, which owns observation, reflection, and memory update. The stated linear diagram (`… → Execution Token → Infrastructure`, full stop) omits the return arrow.
**Correction (mandatory):** the runtime is a **Proposal-and-Observation *loop* engine**, not a one-way proposal emitter. "Everything after the proposal belongs to the Control Plane" is false; the correct statement is "the *authorize-and-execute segment* belongs to the Control Plane; the *observe-and-reflect return* belongs to the runtime."

### F2 — High-frequency low-risk actions make per-action governance impractical → **PARTIAL DISPROOF (forces a correction)**
**Claim under test:** every action becomes an Execution Proposal routed through Context-Min → ActionGate → ACP.
**EXTERNAL KNOWLEDGE.** Real runtimes (Claude Code, coding agents) issue many rapid, read-only, low-consequence tool calls (file reads, greps, list-dirs). Routing each through a full deterministic governance round-trip adds latency and cost that would break interactive use.
**FACT.** ActionGate already has a risk taxonomy where `READ_ONLY` is the lowest tier (`ToolRiskClassifier`, prior review), and its outcome set includes non-escalating ALLOW. So tiering is expressible.
**INTERPRETATION.** The architecture is not disproven, but "pure" cannot mean "every action pays full governance latency." It requires a **risk-tiered fast path**: low-consequence actions get a cheap local authorization (or a cached policy grant) while consequential actions get the full round-trip.
**Correction (mandatory):** the Execution Proposal boundary is **universal in principle but risk-tiered in practice** — the *classification* of an action's consequence is a runtime pre-screen (evidence), and the Control Plane offers a proportional path. Without this, the architecture is correct but unusably slow for interactive runtimes.

### F3 — Tool selection secretly requires governance knowledge → **FAILED (architecture holds)**
**Claim under test:** the runtime can own "tool selection" without owning "authorization."
**Attempted disproof:** to select a tool well, the runtime must know which tools it is *allowed* to use — so tool selection and authorization are coupled, and the runtime can't cleanly shed authorization.
**FACT + INTERPRETATION.** They are distinct. The runtime *modeling* policy to propose efficiently (avoid proposing doomed actions) is not the same as *deciding* authorization. The runtime can be wrong; ActionGate is authoritative and non-compensatory (`gate.py`). A policy-aware pre-screen is *evidence* that "can only raise scrutiny" (`ACTIONGATE_VC_BRIEF.md`), never a grant. **The coupling is advisory, not authoritative — the boundary survives.**

### F4 — Reasoning depends on the world, which only the Control Plane sees → **FAILED (architecture holds)**
**Claim under test:** to reason/plan, the runtime needs live world-state (readiness, capacity), which ACP owns — so reasoning can't be cleanly separated from operational safety.
**FACT.** ACP obtains world-state from a domain `WorldStateProvider`, *not* from the runtime (`symbolu_robotics/autonomous_control_plane/interfaces.py:24–36`). The runtime reasons over its *own* observations; ACP checks operational safety over *live* state at commit. These are two different reads of the world at two different times. The runtime proposing against stale beliefs and ACP holding on fresh state is the *designed* behavior (the `ag_allows_acp_holds` case, `../ai_control_plane_v3/`), not a coupling. **Boundary survives.**

### F5 — Memory/state makes "engine" the wrong word → **FAILED (minor framing note)**
**Claim under test:** a "pure Execution Proposal Engine" implies a stateless function; but the runtime is stateful (memory, goal state, coherence across turns).
**FACT.** The runtime is stateful (`memory_store`, `GoalState`, coherence tracked across turns; `agent.py`). **INTERPRETATION.** This does not disprove the architecture — it refines the noun. The runtime is a **stateful proposer**, and its state (memory, plan, reflection) is exactly what MUST stay in the runtime (Deliverable 3). "Engine" is fine as long as it is understood as a stateful, looping engine, not a pure function. Minor framing note, not a disproof.

**Net of the falsification pass:** the core thesis — *the runtime sheds authorization, operational safety, deployment, and governance, keeping reasoning/planning/decomposition/tool-selection/memory/reflection/uncertainty/proposal* — **survived**. Two real corrections emerged (the return path F1; risk-tiering F2). Neither breaks the boundary; both sharpen it.

---

## Deliverable 1 — Architecture verdict

# `SUPPORTED`

**Not `STRONGLY_SUPPORTED`**, because (a) the architecture as *stated* is a one-way pipeline that omits the observation return path (F1) and the risk-tiered fast path (F2) — both mandatory corrections; and (b) `FACT`: no non-Ugence runtime has been demonstrated end-to-end, and the Control Plane is shadow-only/pre-transport (carried from `../ai_control_plane_v3/`). With the two corrections applied and one empirical demonstration, it would be strong.

**Not `PARTIALLY_SUPPORTED` or `REJECT`**, because the load-bearing claim was directly tested against the code and holds: the runtime *can* shed authorization, operational safety, and governance cleanly, because `FACT` the Control Plane consumes only the action (never the runtime's prompt/reasoning/memory/model) — proven by the input-contract audits in `../ai_control_plane_v3/02_RUNTIME_INDEPENDENCE_AUDIT.md`. The four things the runtime gives up genuinely leave; the eight it keeps genuinely stay.

**Why SUPPORTED is the honest call.** The thesis is architecturally sound and evidence-backed, but the milestone's own framing over-simplifies it in two ways that would cause real engineering failures if shipped literally (a runtime that can't observe results is useless; a runtime that pays full governance latency per file-read is unusable). A verdict of STRONGLY would be agreeing with an imprecise diagram; a verdict below SUPPORTED would ignore that the falsification failed. `SUPPORTED, with two mandatory corrections` is the precise answer.

---

## Deliverable 2 — Execution Proposal specification

See `EXECUTION_PROPOSAL_SCHEMA.md`. Summary: a vendor-neutral object whose MANDATORY fields (`principal`, `action{tool,operation,targets,arguments,reversibility}`, `authority`, `policy_ref`) are exactly what ActionGate's predicates read (`FACT`: `gate.py:46–234`) and are producible by any action-taking runtime; whose `evidence` (incl. the runtime's uncertainty score) is OPTIONAL and scrutiny-only; whose `context_bundle` is OPTIONAL and pipeline-specific (Context-Min is ActionGate-coupled, `FACT`); and whose `provenance` (runtime/model/objective) is recorded but **excluded from the identity digest** so the same action from any runtime yields the same verdict. Fields that must **never** exist: prompt, reasoning trace, memory state, planning graph, model internals.

---

## Deliverable 3 — Runtime responsibility

### Stays in the runtime (and WHY)

| Owned | Why it must stay (FACT/INTERPRETATION) |
|---|---|
| **Reasoning** | Probabilistic intelligence generation; the Control Plane is deterministic and reads none of it (`FACT`: grep-clean decision paths). It cannot live anywhere else. |
| **Planning / decomposition** | ACP "consumes a planner, is not one" (`FACT`: `acp/ACP_ARCHITECTURE.md`). Planning is the runtime's core value. |
| **Tool selection** | *Which* tool to attempt is a reasoning act; *whether* it's allowed is ActionGate's. F3 confirmed the split is clean. |
| **Memory** | Stateful across turns (`FACT`: `memory_store`, `agent.py`); the Control Plane is stateless-per-call. Memory has no other home. |
| **Reflection / self-correction** | Consumes execution *observations* (F1) to re-plan; inherently post-execution runtime work. |
| **Uncertainty estimation** | The runtime's differentiated asset (raw-entropy AUROC 0.857; `FACT`, prior review). Emitted as *evidence*, but computed in the runtime. |
| **Proposal generation** | The runtime's output artifact; the boundary object it produces. |
| **Observation ingestion** | The return path (F1): execution results flow back to the runtime to continue the loop. |
| **Agent identity assertion** | The runtime knows *who* is acting; it asserts the principal (the Control Plane binds it). |
| **Agent-behavior policy** | Interaction mode, revision budget, style — *behavior*, not action-authorization (`FACT`: distinct from ActionGate's signed policy). |

### Permanently leaves the runtime (and WHY)

| Leaves → owner | Why it must leave (FACT) |
|---|---|
| **Authorization** → ActionGate | A boundary the agent controls is not a boundary; deterministic, credential-controlling authorization must be external (`FACT`: `ACTIONGATE_VC_BRIEF.md:39–41`). |
| **Operational safety** → ACP | Requires a live domain world-model the runtime doesn't have; must be a separate key that also passes (`FACT`: ACP `ReadinessChecker`). |
| **Deployment decisions** → ActionGate/ACP + Infrastructure | Whether/where an action actually commits is authorization + operational + infra, not reasoning. |
| **Governance / policy enforcement** → ActionGate | Enterprise-signed, out-of-band, non-compensatory; the runtime is a policy *subject*, never its author (`FACT`: `policy.py:5–6`). |
| **Credential custody / token minting** → ActionGate | The runtime must never hold durable credentials (compromised-agent threat model; `FACT`: `action_gateway_isolated` blocked 27/27 attacks). |
| **Tamper-evident authorization audit** → ActionGate | Governance-grade decision record is external to the thing being governed. |

**INTERPRETATION.** The rule that decides every case: *if it is the reasoning that produces an action, it stays; if it is the authority, safety, or record of committing the action, it leaves.* The runtime keeps everything up to and including the observation of results; it owns none of the deciding-whether-to-commit.

---

## Deliverable 4 — AI Control Plane responsibility (where each layer starts and stops)

| Layer | Starts at | Stops at | Owns (sole) | Does NOT touch (FACT) |
|---|---|---|---|---|
| **Context Minimization** | receipt of the proposal's `context_bundle` (optional) | handing the reduced context to the reader | context relevance *for the ActionGate decision* | never authorizes, never judges safety (`RESPONSIBILITY_MATRIX.md`); no-op without ActionGate-shaped spans (`FACT`) |
| **ActionGate** | receipt of the canonical `action` + `authority` + `policy_ref` | emitting the 6-outcome verdict + (on ALLOW) a single-use token + brokered credential | authorization, hard policy, credential custody, approver quorum, tamper-evident audit | never evaluates operational readiness (`FACT`: `ACP_ACTIONGATE_BOUNDARY.md`) |
| **ACP** | receipt of the authorized action + live domain world-state | emitting operational verdict (PROCEED/HOLD/REOBSERVE) | operational safety against live state, blast radius, readiness, freeze, rollback | never authorizes; mints no token (`FACT`: imports only an opaque verdict, `composition.py:28`) |
| **Composition** | both verdicts present, identity-bound | one eligibility class + (if eligible) release of the token to the runtime's adapter | linking verdicts | never overrides either (`FACT`) |

**No duplicated ownership (FACT-anchored):** the prior audits proved "duplicated-logic count 0, ownership violations 0" for these layers (`acp/RESPONSIBILITY_MATRIX.md`), and that each consumes a *disjoint* slice of the proposal (Context-Min ← `context_bundle`; ActionGate ← `action`+`authority`+`policy_ref`; ACP ← authorized action + world-state pulled from the domain). The boundary object's field partition *is* the ownership partition.

---

## Deliverable 5 — Universal runtime audit

See `UNIVERSAL_RUNTIME_AUDIT.md` for the full per-framework table. Summary verdict: **every listed framework can emit an Execution Proposal**, because they all reduce to a tool-calling loop (`FACT`: `ACTIONGATE_VC_BRIEF.md:21–22`), and the schema describes the tool call, not the framework. The adapter cost varies: **trivial** for Ugence (native) and MCP-speaking runtimes (OpenAI Agents SDK, Google ADK, Claude Code, Semantic Kernel increasingly speak MCP — `EXTERNAL KNOWLEDGE`); **moderate** for graph/role runtimes (LangGraph, CrewAI); **higher** for free-form code executors (AutoGen) and closed/managed runtimes (Bedrock Agents). No framework is *unable* to emit a proposal; the only hard cases are coarse-granularity (code exec) and constrained interception points (managed), both adapter costs, not schema failures.

---

## Deliverable 6 — Competitive positioning: where is the moat?

**Assume every company eventually builds an excellent Agent Runtime.** Does the moat become (A) the runtime, (B) the AI Control Plane, or (C) both?

# Answer: **B — the AI Control Plane.**

**Technical reasoning (FACT + INTERPRETATION):**
1. **Runtimes converge.** Planning, memory, reflection, multi-agent — these are being commoditized across OpenAI/LangGraph/AutoGen/ADK (`EXTERNAL KNOWLEDGE`), and the prior review found Ugence's runtime is *weaker* on exactly these axes (`FACT`: `../agentic_framework_review/`). A moat cannot be built on the side everyone is racing to the same place.
2. **The Control Plane is structurally external and structurally hard.** A deterministic, credential-controlling, state-revalidating authorization boundary *cannot be provided by the runtime itself* — a boundary the agent sits on top of is not a boundary (`FACT`: `ACTIONGATE_VC_BRIEF.md:39–41`). And it is provably runtime-independent (`FACT`: `../ai_control_plane_v3/`), so it governs *every* runtime, including competitors'.
3. **The Execution Proposal boundary makes the runtime a commodity input and the Control Plane the point of control.** The more runtimes standardize on emitting proposals, the more the value concentrates at the layer that decides on them.

**Why not C:** claiming "both" is the comfortable answer, but the evidence says the runtime is a contested, converging market where Ugence is behind, while the Control Plane is a category competitors don't have as a first-class layer at all (`FACT`: Part 6 of `../ai_control_plane_v3/`). Diluting focus across both weakens the one defensible position. **The runtime is a necessary product; the Control Plane is the moat.**

**Concrete improvement (not mere agreement):** make the Execution Proposal an **open, published standard** and offer a **reference runtime**. If Ugence *owns the standard* that competitors' runtimes emit into, the moat compounds: every third-party runtime that adopts the proposal format increases the Control Plane's reach without Ugence building it.

---

## Deliverable 7 — Product positioning

**Is `Specialized AI Systems → Execution Proposal → AI Control Plane → AI Infrastructure` a cleaner story?**

**RECOMMENDATION — yes, with one addition: make the Execution Proposal an explicit, named seam, and show the return path.** The three-family taxonomy is sound (`FACT`: consistent with `../agent_runtime_v2/07` and `../ai_control_plane_v3/09`). The Execution Proposal is the *interface* between family 1 and family 2, and naming it is what turns "a collection of products" into "a platform with a contract." (Canonical portfolio taxonomy: `UGENCE_PLATFORM_OVERVIEW.md`.)

```
   Specialized AI Systems  (Hybrid LLM · LLM Steering Controller · Agent Runtime · Autonomous Runtime · future)
            │  emit
            ▼
   ══════ EXECUTION PROPOSAL (open contract) ══════
            │
            ▼
   AI Control Plane  (Context Minimization · ActionGate · ACP)
            │  verdict + single-use token
            ▼
   AI Infrastructure  (KVPro · Cloud Scaling Controller · future)
            │  execute
            ▼
        result ──────────────┐
            └── observation ──┘  ▲ returns to the Specialized AI System (F1)
```

**The correction to the proposed diagram:** add the **observation return arrow** (F1). The story is a *loop*, not a waterfall: the Specialized AI System proposes, the Control Plane governs, the Infrastructure executes, and the *result returns to the Specialized AI System* to continue reasoning. A one-way diagram mis-sells the architecture and would confuse buyers about where state lives.

**Is another taxonomy better?** No — but sharpen the labels: family 1 = "systems that *generate* proposals," family 2 = "the plane that *governs* them," family 3 = "the substrate that *runs* them." Generate → govern → run → observe. That verb chain is the cleanest articulation.

---

## Deliverable 8 — Future roadmap (runtime becomes *more focused*, not larger)

**Discipline (from the milestone): avoid feature creep; the runtime should shrink in responsibility while deepening in its core.** Three major versions:

### v-next (focus): *become a clean proposer*
- Implement the Execution Proposal as the real output boundary; route consequential actions through the Control Plane; keep the observation return path (F1).
- Add the **risk-tiered fast path** (F2): the runtime classifies action consequence; low-risk reads take a cheap path, consequential actions the full round-trip.
- **Remove**, don't add: delete the runtime's internal soft authorization PDPs and the falsified CG-governance apparatus (`FACT`: prior review) — they are responsibilities that now leave.

### v-after (deepen the core): *best-in-class reasoning + memory*
- Invest only in the eight owned capabilities: planning, decomposition, reflection/self-correction, uncertainty, durable memory, checkpointing, observation-driven re-planning.
- Close the memory/durability gaps (`FACT`: retention pending, trace not replayable) — these are *runtime* depth, not new surface.

### v-later (scale the proposer): *multi-agent as recursion, not a new subsystem*
- Multi-agent = more proposers emitting to the same Control Plane; each agent a principal (`FACT`: `../agent_runtime_v2/05`). No new governance is built in the runtime.

**Anti-creep rule (RECOMMENDATION):** a proposed runtime feature is rejected if it (a) makes an authorization/safety/deployment decision, or (b) requires the runtime to hold a durable credential, or (c) duplicates a Control-Plane concern. The runtime's surface should *shrink* across versions as governance leaves; only its reasoning/memory *depth* grows.

---

## Deliverable 9 — Missing capabilities (before this is genuinely best-in-class)

**Required** (the architecture is incomplete without these):
- `FACT`-grounded: **observation/result return channel** as a first-class part of the boundary (F1) — today implicit.
- **Risk-tiered governance path** (F2) — else interactive runtimes are unusable.
- **Network transport** for the proposal (today in-process/planned) — else no external runtime can participate.
- **Cross-runtime identity fix** — exclude provenance from the action digest (`FACT`: `../ai_control_plane_v3/` R3) — else approvals don't port across runtimes.
- **Durable run state + checkpointing** in the runtime — else long tasks and honest "replay" are impossible (`FACT`: trace is analytics-only today).

**Recommended** (needed for best-in-class, not for correctness):
- An **open, published Execution Proposal standard** + adapter SDK (Deliverable 6 improvement).
- **Per-domain ACP adapters** beyond cloud/robotics (finance/healthcare/BP world-models).
- **Observability export** (OTel) from the runtime; **governance-grade audit surface** from ActionGate.
- **Dry-run / simulate** path for coarse-granularity actions (code executors).

**Optional** (upside, not table-stakes):
- Policy-aware proposal pre-screening (propose only likely-authorizable actions — efficiency, F3).
- Multi-agent coordination primitives.
- A reference adapter for each major framework (beyond the universal MCP adapter).

---

## Deliverable 10 — Risks (what could invalidate this architecture)

| Risk | Type | Severity | Detail |
|---|---|---|---|
| **The return path is ignored** | INTERPRETATION | high-if-ignored | If built as a literal one-way pipeline (F1), the runtime can't observe results and the agent loop breaks. Mandatory correction, not optional. |
| **Governance latency kills interactivity** | EXTERNAL KNOWLEDGE | high | Without risk-tiering (F2), per-action round-trips make interactive runtimes unusable; competitors with lighter governance feel faster. |
| **Empirical undemonstration** | FACT | medium | No external runtime has produced a proposal end-to-end; the universality is architecturally supported, not yet shown (`../ai_control_plane_v3/` R8). |
| **Transport/maturity** | FACT | medium | Shadow-only, in-process transport, one validated connector. Real deployment is unproven. |
| **Standard-adoption failure** | SPECULATION | high (strategic) | The moat (Deliverable 6) depends on runtimes *adopting* the proposal format. If the industry standardizes on a different governance interface (or MCP grows its own), Ugence's contract is bypassed. **This is the most dangerous assumption.** |
| **Context Minimization over-claim** | FACT | low-medium | Presenting it as universal context governance is false (`FACT`: ActionGate-coupled); over-claiming damages credibility. |
| **Competitors add a governance layer** | EXTERNAL KNOWLEDGE | medium | A hyperscaler could bolt deterministic authorization onto its managed agent product (Bedrock + IAM is adjacent). Ugence's lead is architectural depth (cross-domain ACP, non-compensatory determinism), not permanence. |

**Dangerous assumptions, named (RECOMMENDATION to stress-test):**
1. *"Runtimes will emit into our proposal format."* — Not guaranteed; mitigate by making it an open standard early (Deliverable 6) and by leading with the MCP adapter so adoption needs no runtime change.
2. *"Governance can be per-action without hurting UX."* — False without risk-tiering (F2); design the fast path first.
3. *"The pipeline is one-way."* — False (F1); the loop must be first-class.

**Where competitors could outperform:** on **runtime UX and ecosystem** (they already do — `FACT`), and on **governance latency** if Ugence's determinism is heavy. Ugence must not compete on runtime features; it must make the Control Plane both *unmatched in rigor* and *fast enough to disappear*.

---

## Deliverable 11 — Executive recommendation (the name)

**As CTO: yes, rename "Agentic Framework" — but "Agent Runtime" is only half-right.** "Agentic Framework" is generic (every vendor has one) and "framework" understates it. "Agent Runtime" is honest about the category but does not encode the *architectural role* this milestone establishes — that the thing's entire job is to *produce governed proposals*, not to govern.

**RECOMMENDATION — primary name: `Proposer` (product), positioned as an "Agent Runtime that emits Execution Proposals."**

- **Why "Proposer":** it names the exact architectural role (Deliverable 3/6) — it *proposes*; it does not authorize. The name itself enforces the boundary: a "Proposer" that authorized would be misnamed. It is short, non-generic, and un-buzzwordy (the milestone's earlier constraint).
- **Category descriptor:** "Agent Runtime" as the *category*, "Proposer" as the *product* — "Ugence Proposer, an Agent Runtime." This keeps the searchable category while owning a distinctive name.
- **Codename continuity:** the internal "Sentinel" brand (`FACT`: prior review) leans security/governance — the *opposite* of the proposer role — so retire it for this product to avoid implying the runtime governs.

**Alternatives considered:**
- *"Agent Runtime"* (plain) — acceptable, category-honest, but forgettable and role-silent. Use as the category, not the product name.
- *"Reasoner" / "Deliberator"* — capture the reasoning core but not the *output* (the proposal) that defines the boundary.
- *"Cognition Runtime"* — risks the same overclaim as the falsified CG apparatus (`FACT`); avoid.

**The strongest name is the one that makes the architecture self-documenting.** "Proposer" does: it tells every engineer and buyer that this system's job ends at the Execution Proposal, and that authority lives elsewhere — which is precisely the thesis this milestone validated. Reserve "AI Control Plane" for the governance layer; name the runtime for what it uniquely does: it proposes.

---

## Summary

- **Verdict: `SUPPORTED`** — the runtime can become an Execution Proposal Engine; the four responsibilities (authorization, operational safety, deployment, governance) genuinely leave, proven by the Control Plane's runtime-independent input contracts. Two mandatory corrections keep it from being a broken one-way pipeline: **the observation return path (F1)** and **risk-tiered governance (F2)**.
- **The moat is the AI Control Plane (B)**, not the runtime — and it compounds if the Execution Proposal becomes an open standard.
- **Product story:** generate → govern → run → *observe* (loop), with the Execution Proposal as the named seam.
- **Name:** `Proposer` (an Agent Runtime that emits Execution Proposals) — a name that makes the boundary self-enforcing.
- **Improvements over mere agreement:** add the return arrow, add risk-tiering, publish the proposal as an open standard, fix cross-runtime identity, and keep the runtime *shrinking* in responsibility while deepening in reasoning.
