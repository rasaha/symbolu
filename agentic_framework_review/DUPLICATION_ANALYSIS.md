# Duplication Audit (Part 4)

Overlaps between the **Agentic Framework** and each sibling subsystem: **ACP**, **ActionGate**, **Context Minimization**, **CSR Steering Controller**, **Cloud Controller**.

Classification per overlap: **EXACT** (same computation in two places) · **CONCEPTUAL** (same responsibility, different mechanism/tier) · **COMPLEMENTARY** (adjacent, composes cleanly) · **NONE**.

Labels: `FACT` / `INTERPRETATION` / `RECOMMENDATION`.

**FACT — baseline.** There is **no code-level dependency** in either direction between the Agentic Framework and ACP / ActionGate / Context Minimization / Cloud Controller. Verified: the ACP corpus never names the framework; framework docs never name ACP/ActionGate/Context-Min; import graphs are disjoint. All overlaps below are therefore *conceptual re-implementations*, not shared code — which is exactly the duplication risk to resolve.

---

## 1. Agentic Framework ↔ ActionGate

This is the **primary duplication axis**.

| Concern | Agentic Framework | ActionGate | Class | Recommended owner |
|---|---|---|---|---|
| "May this exact tool action execute?" | `mcp_gateway.SafeMCPGateway` + `governance_service.authorize()` (threshold/risk score → ALLOW/DENY/DEFER) | `gate.evaluate()` (deterministic 6-outcome verdict, mints single-use token) | **CONCEPTUAL** | **ActionGate** (authoritative). AF = advisory pre-screen. |
| Tool/operation risk taxonomy | `ToolRiskClassifier` (5 levels, AUROC 0.82) | Frozen operation taxonomy + policy operators (REQUIRE/FORBID/MAX_SCOPE…) | **CONCEPTUAL** | Both, but AF's is *probabilistic evidence*; ActionGate's is *hard policy*. Feed AF risk → ActionGate as evidence. |
| Policy model | `policy_bundle` (versioned, scoped, fail-closed) | Signed policy bundle (hard invariants) | **CONCEPTUAL** | ActionGate for *action-authorization* policy; AF for *agent-behavior* policy. Draw the line explicitly. |
| Human approval / four-eyes | `approval_workflow` (durable, but no execute/resume) | `ESCALATE_TO_HUMAN` + approver quorum bound to exact action | **CONCEPTUAL** | ActionGate (authoritative quorum); AF owns routing/UX. |
| Credential brokering | none (mock client) | Single-use scoped credential the agent never holds | **NONE** (gap in AF) | ActionGate. |
| Audit trail | in-memory `AuditEntry` / `AgentRunTrace` (not durable/replayable) | Tamper-evident hash-chained audit | **CONCEPTUAL** | ActionGate for the authorization record; AF for the reasoning trace. |
| Execution token minting | none | Yes | **NONE** (gap in AF) | ActionGate. |

**INTERPRETATION.** The framework has, in effect, built *two* soft authorization PDPs (`mcp_gateway` in World A, `GovernanceService` in World B) for the exact question ActionGate answers authoritatively. That is duplication squared: AF-vs-ActionGate, and AF-internal (World A vs World B).

**RECOMMENDATION (single ownership).**
1. **ActionGate owns authorization, token minting, credential brokering, approver quorum, and the tamper-evident audit of the decision.**
2. **The Agentic Framework owns the *pre-screen*:** risk classification, confidence/uncertainty scoring, and reasoning-trace — emitted as **ActionGate evidence** (which can only raise scrutiny, per `ACTIONGATE_VC_BRIEF.md`). This makes the framework's best signal (raw-entropy 0.857, risk AUROC 0.82) *useful to* the control plane instead of a competing authority.
3. **Collapse World A + World B into one pre-screen path** so there is a single agent-side decision point, not two.

---

## 2. Agentic Framework ↔ Context Minimization

| Concern | Agentic Framework | Context Minimization | Class |
|---|---|---|---|
| Deciding what the model reads | `memory_store` retrieval + `request_enrichment` (assemble context) | Authorization-preserving extractive compression (deterministic gate oracle) | **COMPLEMENTARY** |
| Cost reduction of context | none | ~72% token reduction with 100% decision invariance | **NONE** (gap in AF) |
| Protecting decision-critical spans | none | Fail-closed span preservation | **NONE** |

**FACT.** AF assembles context (memory + enrichment); Context Minimization compresses it while proving authorization-equivalence. Different jobs.
**INTERPRETATION.** No duplication. They compose: AF assembles → Context Minimization compresses → LLM reads.
**RECOMMENDATION.** The framework should *consume* Context Minimization as an optional pre-read stage rather than growing its own compressor. Complementary; single owner = Context Minimization.

---

## 3. Agentic Framework ↔ ACP (operational safety)

| Concern | Agentic Framework | ACP | Class |
|---|---|---|---|
| "Is this action operationally safe against live state now?" | none (agent has no live-infra readiness model) | `ReadinessChecker`, `SafetyBounds`, blast radius, freeze windows, rollback-availability | **NONE** |
| Deterministic action selection over a candidate set | `goal_decomposition` proposes actions (LLM) | `filter_admissible` + `LexicographicActionSelector` (deterministic) | **CONCEPTUAL (different tier)** |
| Decision trace | in-memory analytics rollup | hash-chained causal `DecisionTrace` | **CONCEPTUAL** |
| Read-only policy control surface | `agentic/policy/policy_control_plane.py` | ACP runtime governor / decision ledger | **CONCEPTUAL** |

**FACT.** ACP evaluates operational safety against live cluster/robot state; the framework has no such model. **INTERPRETATION.** Essentially no overlap — ACP operates a tier below the agent, at actuation. The only conceptual echoes are "action selection" (AF proposes probabilistically; ACP selects deterministically among admissible candidates — different tiers) and the read-only policy surface.
**RECOMMENDATION.** Keep disjoint. AF proposes; ACP disposes on operational safety. Single owner of operational governance = ACP.

---

## 4. Agentic Framework ↔ CSR Steering Controller

| Concern | Agentic Framework | CSR Steering Controller | Class |
|---|---|---|---|
| Shaping LLM output | `adaptive_prompts` / `reasoning_workflows` (prompt-level) | `C×R×S` frame selection + answer-audit gate (frame/answer-space level) | **CONCEPTUAL** |
| Deterministic control of generation | mostly probabilistic (prompt engineering) | deterministic frame decision ("same input → same frame") | **CONCEPTUAL** |
| Model-internal signals | CG sovereign state (falsified) | activation steering (open-weight only) | **CONCEPTUAL (both weak/parked)** |
| Answer audit / rewrite gate | `structured_output` validation | pass/rewrite/escalate audit gate | **CONCEPTUAL** |

**FACT.** CSR fixes *which meaning-frame* the LLM answers in, deterministically, and audits the answer. AF shapes generation via prompts and validates structure. Different mechanisms, adjacent goal ("control the LLM's output").
**INTERPRETATION.** Conceptual overlap, not exact. They could compose: CSR as a generation-control component *inside* the agent's reasoning tier.
**RECOMMENDATION.** Treat CSR as an optional *generation-control plug-in* for the agent runtime, not a competitor. Single owner of frame-steering = CSR; single owner of prompt-orchestration = AF.

---

## 5. Agentic Framework ↔ Cloud Controller

| Concern | Agentic Framework | Cloud Controller | Class |
|---|---|---|---|
| Kubernetes autoscaling decisions | none | `Action = d·G·P·S`, HELPING/NEUTRAL/NOT_HELPING verdict | **NONE** |
| signals→recommend→safety→approval→shadow→explain pipeline | AF has an analogous *shape* (enrich→gate→escalate→execute→trace) but for LLM tool-calls | full L0–L7 lifecycle for infra actions | **CONCEPTUAL (shape only)** |
| Approval lifecycle | `approval_workflow` state machine | `PENDING→APPROVED/DISMISSED/EXPIRED` | **CONCEPTUAL** |
| Shadow/dry-run | `shadow_ai` (a different concept: unsanctioned-AI detection) | shadow runner vs HPA divergence | **NONE** (name collision only) |

**FACT.** Different domains (LLM agent tool-calls vs k8s replica scaling). No shared responsibility. **INTERPRETATION.** The only overlap is *architectural template* — the Cloud Controller demonstrates the canonical control-plane pipeline (signals→recommend→safety→approval→shadow→explain) that a mature agent governance layer would mirror. Note the "shadow" name collision: AF's `shadow_ai` means *unsanctioned AI usage*, not dry-run.
**RECOMMENDATION.** No merge. Use the Cloud Controller's pipeline as a *design template* for how the framework's pre-screen should be structured. Single owner of cloud scaling = Cloud Controller.

---

## 6. Internal duplication *within* the Agentic Framework (must resolve first)

**FACT.** Before reconciling with siblings, the framework duplicates itself:

| Duplication | Evidence | Recommendation |
|---|---|---|
| **Two authorization PDPs** | `mcp_gateway` (World A) and `GovernanceService` (World B) both decide "may this action run?", and they don't call each other | **MERGE** into one pre-screen path |
| **Two governance schema families** | `governance_models.AuthorizationRequest` vs `governance_adapter`'s external P52 `GovernanceRequest` | **MERGE** to one; delete the facade |
| **Two safety-threshold sources** | `safety_contract` hardcodes thresholds/forbidden-caps that also live in `policy_bundle.SafetyPolicy` | **MERGE** — read from resolved policy bundle |
| **Three "approval" concepts** | `approval` (ephemeral), `approval_workflow` (durable), `approval_coverage` (report) share the word | Acceptable if documented; unify the data model |
| **"JEPA" / trust / signal adapters all re-encode tool risk** | framework trust docs: "JEPA … re-encodes tool risk" | Demote overlapping signals to ADVISORY; keep one risk source |

---

## 7. Duplication resolution — the single-ownership table

**RECOMMENDATION (no duplicated responsibility remains):**

| Responsibility | Sole owner |
|---|---|
| What the model may **read** (context relevance) | **Context Minimization** |
| What action to **propose** (planning, reasoning, reflection) | **Agentic Framework** |
| Whether an action is **authorized** (token, credential, quorum, hard policy) | **ActionGate** |
| Whether an action is **operationally safe now** (live-state readiness) | **ACP** |
| Which **meaning-frame** the LLM answers in | **CSR Steering Controller** |
| Cloud **autoscaling** decisions | **Cloud Controller** |
| Agent-side **risk pre-screen + uncertainty scoring** (as evidence) | **Agentic Framework** |
| Agent **behavior policy** (interaction mode, revision budget, domain profile) | **Agentic Framework** |
| Agent **memory / reasoning trace** | **Agentic Framework** |

**INTERPRETATION.** With this allocation, every overlap collapses to either COMPLEMENTARY (composes cleanly) or is resolved by demoting the framework's authorization-shaped parts to ADVISORY evidence feeding ActionGate. The framework stops being a second, softer control plane and becomes the *proposer + evidence source* for the real one. Parts 5–8 develop the missing-capability gaps and the redesigned boundary.
