# Agent Runtime V2 — Architecture (Design Only)

**Milestone:** design-only. No production code, no refactoring, no implementation. This folder is the complete design.
**Premise (given):** the AI Control Plane (Context Minimization + ActionGate + ACP) owns governance. The Agentic Framework evolves into a **pure Agent Runtime** — the layer responsible only for *intelligence generation* and *workflow execution*.
**Builds on:** the prior architecture review in `../agentic_framework_review/`.

Labels used throughout every document: `FACT` (verifiable in the repo, cited) · `INTERPRETATION` · `RECOMMENDATION` · `EXTERNAL` (non-repo general knowledge, deliverable 9 only).

---

## The design in one paragraph

The Agent Runtime is the **proposer**: it turns a goal into a reasoned, reflected, tool-using workflow and emits a single typed **Execution Proposal** (proposed action + agent identity + risk/uncertainty evidence) to the AI Control Plane. The Control Plane decides — Context Minimization governs what the model reads, ActionGate authorizes the exact action and mints a single-use token, ACP confirms it is operationally safe against live state — and the runtime executes only what returns a token. The runtime never mints authority, never judges operational safety, never enforces deterministic policy, never governs context relevance. Those are the Control Plane's, and they already exist. Everything the runtime keeps is either an existing framework strength (planning, reasoning, reflection, memory, risk pre-screen, policy simulation) or an agent-runtime capability gap to build (agent identity, registry, lifecycle, checkpointing, observability export, multi-agent coordination) — none of which is a governance concern.

---

## The boundary contract (the whole design in one line)

> **Context Minimization** decides what the model may read.
> **The Agent Runtime** decides what to attempt, how to reason, and how confident it is.
> **ActionGate** decides whether the attempt is authorized.
> **ACP** decides whether it is operationally safe right now.
> Nothing decides anything twice.

The single crossing point is `ExecutionProposal → verdict + token`. Because ActionGate accepts evidence that "can only raise scrutiny, never lower a hard invariant" (FACT: `ACTIONGATE_VC_BRIEF.md`), the runtime's risk/uncertainty signals integrate with zero new Control-Plane concepts and are monotonically safe.

---

## Deliverables index

| # | Document | Answers |
|---|---|---|
| 1 | `01_RUNTIME_RESPONSIBILITY_MATRIX.md` | Exactly what the runtime owns / must not own; the Execution Proposal object |
| 2 | `02_REMOVE_OWNERSHIP_AUDIT.md` | Every subsystem: KEEP / MOVE-TO-ACTIONGATE / MOVE-TO-ACP / MOVE-TO-CONTEXT-MIN / DELETE / REDESIGN |
| 3 | `03_RUNTIME_PIPELINE_V2.md` | The V2 pipeline (goal→…→proposal→Control Plane→execute→reflect) + verdict-branch handling |
| 4 | `04_RUNTIME_CAPABILITIES.md` | Capability catalog + missing capabilities (all runtime, none governance) |
| 5 | `05_MULTI_AGENT_READINESS.md` | Single vs multi vs hierarchical → hierarchical-capable via recursion; single-agent-first |
| 6 | `06_RUNTIME_VS_CONTROL_PLANE_OWNERSHIP.md` | The clean cross-system ownership matrix — one owner per responsibility, no overlap |
| 7 | `07_PRODUCT_POSITIONING.md` | Three-family positioning and how the eight products interact |
| 8 | `08_ENTERPRISE_USE_CASES.md` | IT-ops, finance, healthcare, manufacturing, support — where each product participates |
| 9 | `09_COMPETITIVE_GAP_ANALYSIS.md` | vs OpenAI Agents SDK / LangGraph / CrewAI / AutoGen / Google ADK / Bedrock Agents |
| 10 | `10_FUTURE_ROADMAP.md` | 2–3 yr roadmap across Core Runtime / Control-Plane integration / Infrastructure integration |

---

## Key conclusions (with evidence type)

1. **The runtime's center of gravity is the proposer tier** — planning, reasoning, reflection, memory, tool selection. `FACT`-backed by the existing modules; this is what it keeps. (Deliverables 1, 4)
2. **All authorization-shaped subsystems demote or move.** The two soft PDPs (`mcp_gateway`, `GovernanceService`), the duplicate policy/approval, and the falsified CG governance either become advisory evidence, move to ActionGate, or are deleted. `MOVE-TO-ACP` and `MOVE-TO-CONTEXT-MIN` contain *no code* — the runtime never actually owned those, it only must avoid building them. (Deliverable 2)
3. **The pipeline makes the boundary structural.** There is no place in the loop where the runtime can re-own governance; authority and operational safety are per-action, non-cacheable Control-Plane calls. (Deliverables 3, 6)
4. **Multi-agent adds proposers, not governance.** Hierarchical orchestration is recursion over the single-agent pipeline; each agent has its own principal; authority is never delegated between agents. (Deliverable 5)
5. **The moat is the governed boundary, not runtime features.** Against the six named competitors, Ugence is behind on multi-agent/durability/observability but occupies a category none of them has: deterministic action authorization + operational-safety composition + cross-domain (cloud+robotics) governance. The strategic move is to make the Control Plane runtime-agnostic. (Deliverable 9)
6. **Depth before breadth.** The roadmap fixes honesty and internal duplication first, integrates the Control Plane second, and defers multi-agent until durability + identity + integration are proven. (Deliverable 10)

---

## Constraints honored

- No production code changed; no refactoring; no implementation. Design only.
- Every recommendation is grounded in repository evidence, labeled FACT/INTERPRETATION/RECOMMENDATION (EXTERNAL only for competitor knowledge in Deliverable 9).
- No capability already provided by ActionGate, ACP, or Context Minimization is duplicated — the audit (Deliverable 2) removes the existing duplicates and the boundary (Deliverable 6) enforces one owner per responsibility.
- Optimized for a coherent enterprise platform (Deliverables 7–8) over preserving legacy framework boundaries.
