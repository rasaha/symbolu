# Agentic Framework — Responsibility Matrix (Part 3)

Per-module recommendation with justification. Verdict vocabulary (from the task):
**REMAIN** (keep as-is in the Agentic Framework), **MOVE** (ownership belongs to ACP/ActionGate/Context Minimization), **MERGE** (fold into a sibling module), **DISAPPEAR** (delete/deprecate), **ADVISORY** (demote from enforcing to signal-only), **DETERMINISTIC** (harden from soft/heuristic to deterministic).

Labels: `FACT` (basis) / `RECOMMENDATION` / `INTERPRETATION`. Every recommendation names its evidence.

> This matrix is distinct from `Project_documentation/control_plane/acp/RESPONSIBILITY_MATRIX.md` (which governs the ACP layers). This one governs the Agentic Framework modules.

---

## 1. Core runtime (World A) — the proposer

| Module | Current responsibility | Verdict | Justification |
|---|---|---|---|
| `agent.py` (`AgenticLLMWrapper`) | Per-turn orchestration of the single-agent loop | **REMAIN** | FACT: this is the product's center of gravity and the natural "proposer" tier above the control plane. RECOMMENDATION: keep, but make budget/deadline/approval enforcement uniform across `run()` and `run_stream()` (FACT: today they only apply on streaming paths, `agent.py:403–410`). |
| `agent_builder.py` / `cg_tool_dispatcher.py` | Assembly + tool-call routing | **REMAIN** | FACT: composition front doors. RECOMMENDATION: change the default from `MockMCPClient` to a real transport or a loud "mock" banner (FACT: `IS_STUB` only warns). |
| `goal_decomposition.py` | Intent → structured plan | **REMAIN** | FACT: planning is a proposer function; ACP explicitly "consumes a planner." |
| `reflective_loop.py`, `reasoning_workflows.py`, `adaptive_prompts.py`, `local_critic.py` | Reasoning / self-revision / critic routing | **REMAIN** | FACT: this is the differentiated reasoning value. INTERPRETATION: `reasoning_workflows` is standalone (only `adaptive_prompts` imports it) — RECOMMENDATION: either wire it into the loop or mark it explicitly experimental. |
| `memory_store.py`, `memory_retention.py` | Conversational memory + retention | **REMAIN** | FACT: agent state. RECOMMENDATION: finish the deferred "M3" retention wiring (FACT: `last_accessed_at` unused today). |
| `coherence_tracker.py` | Turn-level coherence metrics | **REMAIN + DETERMINISTIC** | FACT: `factual_alignment` is a hardcoded 0.7 placeholder weighted 0.15 into every score. RECOMMENDATION: either compute it or drop the constant from the weighted sum — a fabricated input should not move a governance-adjacent number. |
| `llm_adapters.py`, `inference_mistral.py`, `structured_output.py`, `streaming_events.py`, `cancellation.py`, `tool_discovery.py`, `token_budget.py`, `tracing.py`, `trace_viewer.py` | Runtime infrastructure | **REMAIN** | FACT: standard agent-runtime plumbing. RECOMMENDATION (tracing): the "replayable trace" claim is overstated — it is an analytics rollup, not a causal replay (framework readiness audit). Either build real replay or drop the claim. RECOMMENDATION (token_budget): cost caps are inert (no adapter emits cost) — wire adapter cost or remove the guarantee. |
| `proactive_scheduler.py` | Autonomous cron/interval execution | **REMAIN (experimental)** | FACT: nothing imports it and its stored `confidence_gate` is never called (dead integration). RECOMMENDATION: fix the dead `confidence_gate` wiring or remove it; keep the scheduler as an opt-in agent-side capability. |
| `benchmark_critics.py`, `validate.py`, `examples.py` | Tooling / harness / docs | **REMAIN** | FACT: dev tooling, harmless. |

## 2. Tool-authorization path — the overlap surface

| Module | Current responsibility | Verdict | Justification |
|---|---|---|---|
| `mcp_gateway.py` (`SafeMCPGateway`) | Soft per-tool authorization: risk-classify → confidence gate → escalate → execute → audit | **ADVISORY (split)** | FACT: decides by threshold, mints no token, brokers no credential — this is a *soft pre-screen*, whereas ActionGate is the hard authoritative gate over "may this exact action execute, once" (`ACTIONGATE_VC_BRIEF.md`). RECOMMENDATION: keep the *risk classification + confidence pre-screen* in the framework and emit it as **ActionGate evidence** (FACT: ActionGate accepts optional evidence that can only raise scrutiny, never lower an invariant — a clean, non-duplicating integration). Delegate the *final authorization + credential brokering + token minting* to ActionGate. Keep the local execution+audit path only for dev/mock. |
| `ToolRiskClassifier`, `ToolSpec`, `ToolPermission` | 5-level tool risk taxonomy + permissions | **REMAIN** | FACT: AUROC ≈0.82; genuinely useful as pre-screen and as ActionGate evidence. |

## 3. World B — the governance decision service

| Module | Current responsibility | Verdict | Justification |
|---|---|---|---|
| `governance_service.py` (`GovernanceService`) | Standalone decision-only PDP `authorize()→ALLOW/DENY/DEFER` | **MOVE / MERGE (repositioned)** | FACT: it does ActionGate's job (decide whether a tool action may run) one tier softer, deterministically, but is **not called by the agent runtime** and mints no token. INTERPRETATION: two PDPs answering "may this action run?" is a duplicated responsibility. RECOMMENDATION: reposition `GovernanceService` as the **agent-side pre-authorization / risk-scoring adapter that produces ActionGate evidence** — not as an independent authority. Where enterprises need a single authoritative PDP, that is ActionGate, not this. |
| `governance_api.py` | FastAPI `/authorize` | **REMAIN (repositioned)** | FACT: the only network control surface. RECOMMENDATION: keep as the framework's *pre-authorization* API; document that it is advisory, not authoritative; add auth/TLS (FACT: none today). |
| `governance_models.py` | Schemas | **REMAIN** | FACT: schema layer. RECOMMENDATION: remove the never-populated `counterfactual` field and the unused `tenant_id`/`org_id`/`dry_run` future-work fields, or implement them. |
| `governance_adapter.py` | Re-export of an external P52 schema | **MERGE / DISAPPEAR** | FACT: a *second, incompatible* governance schema family whose substance lives in an un-audited external package. RECOMMENDATION: consolidate to one schema family; delete the facade. |
| `jepa_governance.py` | Deterministic heuristic "regime" override, stricter-only | **ADVISORY** | FACT: "JEPA here is NOT a trajectory predictor"; inputs are approximated from confidence scalars; the framework's own trust docs say "demote JEPA to advisory/off; it re-encodes tool risk." RECOMMENDATION: demote to a named advisory signal or remove; it must never be a blocking authority. |
| `domain_policy.py`, `policy_bundle.py`, `signal_config.py` | Versioned/scoped agent-behavior policy | **REMAIN + DETERMINISTIC** | FACT: fail-closed, deterministic policy model. RECOMMENDATION: this is legitimate *agent-behavior* policy (interaction mode, revision budget, domain profile) and should remain — but it must not be confused with ActionGate's *action-authorization* policy. Fix the latent no-op rule (`domain_policy` severity-0 ALLOW that can never win). |
| `adaptive_policy.py` | Per-session policy tuning | **REMAIN** | FACT: agent-side runtime adaptation. RECOMMENDATION: relabel "SCC gradient descent" honestly — it is fixed-step constants, not learned. |
| `safety_contract.py` (`SafetyGate`) | Turn-level fail-closed pre-gate | **REMAIN + MERGE** | FACT: 6 preconditions, but thresholds/forbidden-capabilities are hardcoded and **duplicated** rather than read from `policy_bundle.SafetyPolicy`. RECOMMENDATION: wire it to the resolved policy bundle so there is one source of safety thresholds. |
| `approval.py`, `approval_workflow.py`, `approval_coverage.py` | Human approval (ephemeral + durable) | **REMAIN (routing) / bind to ActionGate (authority)** | FACT: durable store records/transitions but never executes/resumes; ActionGate already owns `ESCALATE_TO_HUMAN` with exact-action approval binding. RECOMMENDATION: keep approval *routing/UX* in the framework; bind the authoritative approver-quorum decision to ActionGate so a single system owns "four-eyes." |
| `policy_replay.py` | Policy what-if replay | **REMAIN** | FACT: useful offline simulation; non-mutating by construction. |

## 4. Signal apparatus

| Module | Current responsibility | Verdict | Justification |
|---|---|---|---|
| `raw_entropy_adapter`, `confidence_risk_gap` | Validated uncertainty signals | **REMAIN + ADVISORY** | FACT: raw-entropy AUROC 0.857 — the one empirically-supported signal. Keep as advisory input / ActionGate evidence. |
| `signal_adapters/*` (the other ~17) | Bounded stricter-only penalties | **ADVISORY (default) / DISAPPEAR (dead)** | FACT: inert by default; `rollback_adapter` post-action loop doesn't exist; `readiness_adapter` cooldown is a stub; `counterfactual_bridge` is replay-only. RECOMMENDATION: keep the ones with a real upstream as advisory; delete the dead-wired ones or mark them clearly experimental. |
| `sovereign_bridge.py`, `olm_bridge.py`, `coherence` signal paths | Tensor/ontology → signals | **ADVISORY** | FACT: enforce nothing; translate only. Keep as optional signal producers. |
| `trust/*` | Shadow-gated trust decision layer | **REMAIN (shadow) / decide the flip** | FACT: real, deterministic, audited, but never changes a production outcome; flip explicitly not taken. RECOMMENDATION: either commit to flipping it (and then it *is* the framework's authorization logic — reconcile with ActionGate) or retire it. Perpetual shadow is technical debt. |
| CG sovereign-state governance | Model-internal "conscious generation" signal | **DISAPPEAR (as governance)** | FACT: AUROC 0.457 (anti-predictive), default OFF, "beaten by a one-line `entropy(logits)`," founder notes "kill." RECOMMENDATION: remove from the governance path entirely; it may survive as a research artifact but must not be marketed as a differentiator. |

## 5. Sibling policy layer (under `agentic/policy/`)

| Module | Current responsibility | Verdict | Justification |
|---|---|---|---|
| `policy_control_plane.py` | Read-only, zero-LLM per-domain policy state + health + tenant hooks | **REMAIN (rename)** | FACT: the framework's most genuinely control-plane-shaped module. RECOMMENDATION: this is the seed of the *agent-behavior control surface*. Keep it, but rename to avoid colliding with the repo's real "AI Control Plane" (ACP) — see Part 9 naming. |
| `policy_engine.py`, `policy_service.py`, `policy_simulation.py`, `policy_lifecycle.py` | Policy computation/simulation/lifecycle | **REMAIN** | FACT: legitimate agent-behavior policy backend. |

---

## 6. Summary counts

| Verdict | Count (approx) | Representative modules |
|---|---|---|
| **REMAIN** | ~22 | agent.py, goal_decomposition, reflective_loop, memory_store, llm_adapters, policy_bundle, domain_policy, approval*, policy_replay |
| **ADVISORY** (demote) | ~6 | jepa_governance, mcp_gateway (final-authz portion), signal_adapters, sovereign/olm bridges, trust (pending flip decision) |
| **MOVE / MERGE** | ~3 | governance_service (→ ActionGate evidence adapter), governance_adapter (→ delete), safety_contract thresholds (→ policy_bundle) |
| **DISAPPEAR** | ~2 | CG sovereign-state governance, dead-wired signal adapters |
| **DETERMINISTIC** (harden) | ~2 | coherence_tracker.factual_alignment, adaptive_policy "gradients" labeling |

**INTERPRETATION.** No module needs to be rebuilt as a control plane. The dominant verdict is REMAIN — because the framework's real value is the *proposer/reasoning* tier — and the second-most-common is ADVISORY/MOVE — because its *authorization-shaped* parts duplicate ActionGate at a softer tier and should feed the control plane rather than compete with it. Part 4 quantifies exactly which overlaps are exact vs conceptual vs complementary.
