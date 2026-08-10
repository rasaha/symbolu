# Deliverable 3 — Runtime Pipeline V2

The Agent Runtime V2 execution pipeline, assuming the AI Control Plane already exists. The pipeline is where the boundary is enforced: the runtime reasons and proposes; the Control Plane authorizes; the runtime executes only what returns a token.

Labels: `FACT` / `INTERPRETATION` / `RECOMMENDATION`.

---

## 1. The pipeline (per step of a task)

```
                          ┌───────────────────────── AGENT RUNTIME (probabilistic) ─────────────────────────┐
   Goal / Task ──────────▶│                                                                                  │
                          │  1. Goal Intake & Management        (goal_decomposition.GoalState)               │
                          │  2. Planner / Decomposition         (decompose_goal → ordered ActionItems)       │
                          │  3. Memory Read                     (memory_store retrieval)                     │
                          │        └──▶ [optional] Context Minimization  ◀── CONTROL PLANE (relevance)       │
                          │  4. Reasoner                        (reasoning_workflows / adaptive_prompts)      │
                          │  5. Reflection (pre-act)            (reflective_loop critique/revise)             │
                          │  6. Tool Selection                  (ToolCatalog + action_type_to_tool)          │
                          │  7. Runtime Pre-gate (soft)         (safety_contract SafetyGate — sanity only)   │
                          │  8. Uncertainty / Risk Evidence     (raw_entropy, confidence_risk_gap, risk lvl) │
                          │  9. Execution Proposal              (proposed_action + agent_principal + evidence)│
                          └───────────────────────────────────┬──────────────────────────────────────────────┘
                                                              │  ExecutionProposal
                                                              ▼
                          ┌───────────────────────── AI CONTROL PLANE (deterministic, fail-closed) ─────────┐
                          │  A. ActionGate   — AUTHORIZED?  (policy, evidence, state, approval → 6 outcomes) │
                          │  B. ACP          — OPERATIONALLY SAFE NOW?  (readiness/blast/capacity/freeze)    │
                          │  C. Composition  — link verdicts → eligible iff BOTH pass; mint single-use token │
                          └───────────────────────────────────┬──────────────────────────────────────────────┘
                                          verdict + token │  (or DENY / HOLD / ESCALATE)
                                                              ▼
                          ┌───────────────────────── AGENT RUNTIME ────────────────────────────────────────┐
                          │ 10. Execute (only with token)       (tool call via brokered credential)         │
                          │ 11. Observation                     (ingest tool result)                        │
                          │ 12. Reflection (post-act)           (did it work? self-correct / retry)         │
                          │ 13. Memory Update                   (episodic write, retention)                 │
                          │ 14. Next Step / Complete            (loop or finish; update GoalState)          │
                          └──────────────────────────────────────────────────────────────────────────────────┘
```

**FACT — this is the ACP pipeline's own shape, read from the runtime side.** `Project_documentation/control_plane/acp/AI_CONTROL_PLANE_ARCHITECTURE.md`: `Original Context → Context Minimization → LLM reader → Proposed Action → ActionGate → ACP → Compose → (eligible) Execution`. Steps 1–9 above *are* the "LLM reader → Proposed Action" box, expanded into a real agent loop; steps A–C are the Control Plane unchanged; steps 10–14 are the runtime consuming the verdict.

---

## 2. Step-by-step ownership and behavior

| # | Step | Owner | Det/Prob | Existing module (FACT) | Notes |
|---|---|---|---|---|---|
| 1 | Goal intake & management | Runtime | Prob | `goal_decomposition.GoalState` | Tracks purpose, agency level, completion |
| 2 | Planner / decomposition | Runtime | Prob | `decompose_goal` | Ordered `ActionItem`s with deps |
| 3 | Memory read | Runtime | Det | `memory_store` | Working + episodic retrieval |
| 3b | Context minimization (optional) | **Control Plane** | Det | Context Minimization | Runtime *requests* compression; never compresses itself |
| 4 | Reasoner | Runtime | Prob | `reasoning_workflows`, `adaptive_prompts` | Strategy selected per complexity |
| 5 | Reflection (pre-act) | Runtime | Prob | `reflective_loop` | Improve the plan/answer before proposing |
| 6 | Tool selection | Runtime | Prob | `ToolCatalog`, `action_type_to_tool` | *Which* tool — **not** whether it's allowed |
| 7 | Runtime pre-gate (soft) | Runtime | Det | `safety_contract.SafetyGate` | A cheap local sanity check to avoid proposing obvious nonsense; **advisory, not authoritative** |
| 8 | Uncertainty/risk evidence | Runtime | Prob | `raw_entropy_adapter`, `confidence_risk_gap`, `ToolRiskClassifier` | Packaged as scrutiny-only evidence |
| 9 | Execution proposal | Runtime | Det | *V2 seam* | The single boundary object (Deliverable 1 §4) |
| A | Authorization | **ActionGate** | Det | `action_gate_ref.gate.evaluate` | 6 outcomes; token on ALLOW |
| B | Operational safety | **ACP** | Det | ACP core + `cloud_controller` | HOLD/REOBSERVE; never authorizes |
| C | Composition | **Control Plane** | Det | `composition.py` | Eligible iff both pass; single bound identity |
| 10 | Execute (token-gated) | Runtime | Det/Prob | `agent.py` action loop | Only with the minted token + brokered credential |
| 11 | Observation | Runtime | Det | action loop | Feed result to reasoning/memory |
| 12 | Reflection (post-act) | Runtime | Prob | `reflective_loop` | Verify outcome; decide retry/self-correct |
| 13 | Memory update | Runtime | Det | `memory_store` | Episodic write + retention |
| 14 | Next step / complete | Runtime | Det | `agent.py` loop | Loop or finish |

---

## 3. What is deliberately absent from the runtime pipeline

**FACT-anchored — these steps do NOT appear in the runtime and must not be added:**
- No authorization decision inside the runtime (steps A–C are the Control Plane; the runtime only *packages* a proposal and *consumes* a verdict).
- No credential handling before step 10 — the runtime never holds a long-lived credential; ActionGate brokers a single-use one.
- No operational-readiness check — the runtime has no live-cluster/robot-state model; ACP owns it.
- No context-relevance/compression logic — step 3b is a *call* to Context Minimization, not runtime code.

**INTERPRETATION.** The pipeline makes the boundary structurally visible: everything left of the `ExecutionProposal` arrow is probabilistic reasoning the runtime owns; everything between the arrows is deterministic governance the runtime *calls*; execution resumes only after a token exists. There is no place in the loop where the runtime could accidentally re-own governance.

---

## 4. Control flow for the non-ALLOW verdicts

**RECOMMENDATION.** The runtime must handle every ActionGate/ACP outcome as a first-class branch (FACT: outcomes enumerated in `action_gate_ref/gate.py` and `Project_documentation/control_plane/acp/ACP_ACTIONGATE_BOUNDARY.md`):

| Verdict from Control Plane | Runtime behavior |
|---|---|
| `ALLOW` / `ALLOW_WITH_CONSTRAINTS` + token | Execute (step 10), applying any returned constraints |
| `DENY` (`BLOCKED_BY_AUTHORIZATION`) | Do not execute; reflect on why; re-plan or surface to user; **never retry the same action to "get through"** |
| `HOLD` / `HELD_BY_OPERATIONAL_SAFETY` (ACP) | Do not execute; optionally re-observe and re-propose later (backoff); this is a *timing* problem, not a plan problem |
| `ESCALATE_TO_HUMAN` (`PENDING_AUTHORIZATION`) | Route to the human-interaction subsystem (UX); await the authoritative approver decision from ActionGate; resume only if it becomes ALLOW |
| `REQUEST_MORE_EVIDENCE` | Gather additional runtime evidence (more reasoning, a dry-run observation) and re-propose |
| `SIMULATE_AND_RETRY` | Run the runtime's own what-if/dry-run, attach the result, re-propose |
| `*_MISMATCH` / `SHADOW_ERROR` | Fail closed; abort the step; log; surface an error |

**INTERPRETATION.** These branches are where the runtime's *reflection and self-correction* capabilities (Deliverable 4) earn their keep: a denied or held proposal is an observation to reason about, not a wall. The runtime's job is to *converge on a proposal the Control Plane will authorize* — not to argue with it.

---

## 5. Long-running & multi-step behavior

**RECOMMENDATION.** Steps 1–14 are one iteration. A task loops until `GoalState` is complete or a budget/deadline stops it. For long-running tasks (Deliverable 4), the runtime must:
- checkpoint durable run state after each authorized execution (step 13), so a crash resumes at step 14 rather than step 1;
- re-acquire a fresh token per action (FACT: ActionGate tokens are single-use), never cache authority across steps;
- re-request operational-safety per action (FACT: ACP evaluates against *live* state each time), never assume a prior HOLD/PROCEED still holds.

This is the pipeline's most important interaction with the Control Plane's determinism guarantees: **authority and safety are per-action and non-cacheable; only the runtime's reasoning state is durable.**
