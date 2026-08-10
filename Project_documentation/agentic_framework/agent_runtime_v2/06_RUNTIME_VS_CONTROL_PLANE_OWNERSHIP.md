# Deliverable 6 — Runtime vs AI Control Plane: Clean Ownership Matrix

Every responsibility has **exactly one owner**. No overlap. This is the authoritative boundary for the whole platform; Deliverables 1–5 defer to it.

Labels: `FACT` (owner already provides it, cited) / `RECOMMENDATION` (proposed sole owner).

---

## 1. Master ownership matrix

| # | Responsibility | Sole owner | Evidence / rationale |
|---|---|---|---|
| 1 | Goal intake & management | **Agent Runtime** | `goal_decomposition.GoalState` (FACT) |
| 2 | Task decomposition / planning | **Agent Runtime** | `decompose_goal` (FACT); ACP "consumes a planner" (FACT) |
| 3 | Reasoning (chain/tree/debate/…) | **Agent Runtime** | `reasoning_workflows` (FACT) |
| 4 | Reflection / self-correction | **Agent Runtime** | `reflective_loop` (FACT) |
| 5 | Uncertainty / risk estimation | **Agent Runtime** | `raw_entropy` 0.857, `ToolRiskClassifier` 0.82 (FACT) |
| 6 | Tool **selection** | **Agent Runtime** | `ToolCatalog` + `action_type_to_tool` (FACT) |
| 7 | Workflow orchestration / step loop | **Agent Runtime** | `agent.py` loop (FACT) |
| 8 | Execution proposal construction | **Agent Runtime** | V2 boundary object (RECOMMENDATION) |
| 9 | Retries / backoff of runtime steps | **Agent Runtime** | scheduler retry (FACT, partial) |
| 10 | Long-running task state / checkpointing | **Agent Runtime** | V2 gap (RECOMMENDATION) |
| 11 | Plan-level compensation (saga) | **Agent Runtime** | proposes compensating actions through the Control Plane (RECOMMENDATION) |
| 12 | Human interaction (UX / routing) | **Agent Runtime** | `approval*` routing (FACT) |
| 13 | Memory (working/episodic/retention) | **Agent Runtime** | `memory_store` (FACT) |
| 14 | Agent-behavior policy (mode/budget/style/domain) | **Agent Runtime** | `policy_bundle`/`domain_policy` (FACT) |
| 15 | Agent identity (principal) | **Agent Runtime** | V2 gap (RECOMMENDATION) |
| 16 | Agent registry / capability registry | **Agent Runtime** | V2 gap (RECOMMENDATION) |
| 17 | Agent lifecycle | **Agent Runtime** | V2 gap (RECOMMENDATION) |
| 18 | Runtime observability (reasoning trace, OTel export) | **Agent Runtime** | `tracing` + V2 export (FACT/RECOMMENDATION) |
| 19 | Multi-agent coordination | **Agent Runtime** | V2 gap (RECOMMENDATION) |
| 20 | Context relevance — "what may the model read?" | **Context Minimization** | authorization-preserving compression (FACT) |
| 21 | Context compression / span preservation | **Context Minimization** | fail-closed span preservation (FACT) |
| 22 | Authorization — "may this exact action execute, once?" | **ActionGate** | 6-outcome verdict (FACT) |
| 23 | Deterministic hard-policy enforcement | **ActionGate** | signed policy bundle, hard invariants (FACT) |
| 24 | Token minting / execution grant | **ActionGate** | single-use token on ALLOW (FACT) |
| 25 | Credential brokering | **ActionGate** | single-use scoped credential (FACT) |
| 26 | Approver quorum / four-eyes authority | **ActionGate** | approvals bound to action_hash (FACT) |
| 27 | Tamper-evident authorization audit | **ActionGate** | hash-chained audit (FACT) |
| 28 | Operational safety — "safe against live state now?" | **ACP** | readiness/blast/capacity/freeze (FACT) |
| 29 | Live-state action selection over admissible set | **ACP** | `filter_admissible` + `LexicographicActionSelector` (FACT) |
| 30 | Infrastructure rollback (single action) | **ACP** | rollback-availability gating (FACT) |
| 31 | Verdict composition / eligibility | **AI Control Plane (Composition)** | `composition.py`, 8 classes (FACT) |

---

## 2. The three contested boundaries, resolved explicitly

These are the places the current framework *does* overlap the Control Plane. Each gets a single owner and a precise cut line.

### 2.1 "Policy" (appears in both)
- **Agent-behavior policy** (interaction mode, revision budget, response style, domain profile) → **Runtime** (`policy_bundle`, `domain_policy`).
- **Action-authorization policy** (may this operation run, under what hard invariants) → **ActionGate** (signed policy bundle).
- **FACT — same word, different objects:** the ACP corpus already flags this pattern ("Same word, two different computations at two different layers," `acp/ACP_ACTIONGATE_BOUNDARY.md`). RECOMMENDATION: namespace the runtime's policy as "behavior policy" to prevent drift.

### 2.2 "Approval" (appears in both)
- **Approval UX / routing / record** → **Runtime** (`approval`, `approval_workflow`).
- **Authoritative approver-quorum decision** → **ActionGate** (`ESCALATE_TO_HUMAN` + bound approvals).
- Cut line: the runtime *presents* the approval and *records* it; ActionGate *decides* whether the quorum is satisfied and only then authorizes.

### 2.3 "Risk / safety" (appears in both)
- **Soft risk/uncertainty pre-screen** (advisory, to decide what to propose and how confident) → **Runtime** (`ToolRiskClassifier`, raw-entropy).
- **Hard safety gate** (non-compensatory, blocks execution) → **ActionGate** (authorization) + **ACP** (operational).
- Cut line: the runtime's risk score is **evidence that can only raise scrutiny** (FACT: ActionGate's evidence contract); it can never *lower* a hard invariant and never *is* the final gate.

---

## 3. Overlap check — proof of no double ownership

**RECOMMENDATION — the falsifiable test** (mirrors ACP's own "duplicated-logic count 0" method, FACT: `acp/RESPONSIBILITY_MATRIX.md`):

For every responsibility 1–31, exactly one system's code makes the decision. In V2 this is enforceable structurally:
- The runtime imports an `ActionGateClient` / `ContextMinimizationClient` but **contains no authorization, credential, operational-safety, or compression logic of its own** (the "MOVE/DELETE" verdicts in Deliverable 2 remove the existing copies).
- The Control Plane **contains no LLM, planning, reasoning, or memory** (FACT: ActionGate is stdlib-only "no AI"; ACP "consumes a planner").

**INTERPRETATION.** The two sides are disjoint by construction: the runtime is the only probabilistic reasoner; the Control Plane is the only deterministic governor. The single crossing point is the `ExecutionProposal → verdict + token` exchange. That single, typed seam is what makes "exactly one owner per responsibility" checkable rather than aspirational.

---

## 4. One-line ownership summary

> **Context Minimization** decides what the model may read.
> **The Agent Runtime** decides what to attempt, how to reason, and how confident it is.
> **ActionGate** decides whether the attempt is authorized.
> **ACP** decides whether it is operationally safe right now.
> Nothing decides anything twice.
