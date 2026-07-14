# Agentic Framework — Architecture Audit (Part 1)

**Milestone:** Architecture & product-positioning research.
**Scope:** `agentic/agentic_framework/` (31,217 LOC Python) + immediate governance/policy siblings under `agentic/`.
**Method:** direct source reads of the core runtime + five parallel deep-reads of the framework code, framework docs/briefs, the ACP corpus, ActionGate + Context Minimization, and CSR / Cloud Controller / Robotics / pitchbook.
**Constraint honored:** no production code, ACP, ActionGate, Context Minimization, or CSR was modified. This is a read-only audit.

**Evidence labels used throughout:** `FACT` (verifiable in source/docs, with path), `INTERPRETATION` (inference from facts), `RECOMMENDATION`, `SPECULATION`.

---

## 0. Headline structural finding

**FACT.** The `agentic/agentic_framework/` package is not one coherent product. It is **two loosely-coupled subsystems that share a vocabulary but are wired separately**, plus a large dormant/experimental signal apparatus:

- **World A — the shipped agent runtime.** `AgenticLLMWrapper` (`agent.py`) runs a fixed per-turn pipeline: goal decomposition → memory → reflective generation → coherence tracking → `SafetyGate` → action loop. Public API version `1.9.0` (`__init__.py:374`), internally branded "Sentinel."
- **World B — the standalone governance service.** `GovernanceService` (`governance_service.py`) + FastAPI `governance_api.py` expose a decision-only `POST /authorize` endpoint. **FACT:** nothing in the agent runtime imports `governance_service`; it is reachable only from `governance_api.py` and `policy_replay.py` (import-graph verified with ripgrep). World A and World B **do not call each other**.
- **The signal apparatus** — CG "sovereign state," "JEPA" governance, `trust/`, and `signal_adapters/` — is wired in places but is (a) deterministic heuristics, not the ML/neural machinery the naming implies, and (b) largely dormant or default-OFF, and in the CG case **falsified** (`signal_config.py` records CG AUROC 0.457 vs raw-entropy 0.857).

**INTERPRETATION.** The single most important input to the positioning question (Parts 6–9) is that "the Agentic Framework" is really *an agent runtime (World A) with a separable deterministic policy-decision backend (World B) bolted alongside it*. Any classification that treats it as one atomic thing will be wrong.

---

## 1. Public API surface (what the product actually ships)

**FACT** (`__init__.py`, v1.9.0): ~120 exported symbols, all belonging to **World A**: `AgenticLLMWrapper`, `build_agent`, goal decomposition, memory, reflective loop, coherence, `SafetyContract`, `LocalCritic` family, `AdaptivePolicyEngine`, `ConfidenceGate` family, `SafeMCPGateway` family, `ProactiveScheduler`, `CancellationToken`, approval (`ApprovalController`/`ApprovalPolicy`), `BudgetPolicy`, `MemoryRetentionPolicy`, structured output, tracing + trace viewer, 21 streaming-event constants, `ToolCatalog`, LLM adapters, adaptive-prompts pipeline.

**FACT — what is NOT exported:** `governance_service`, `governance_api`, `jepa_governance`, `domain_policy`, `shadow_ai`, `policy_bundle`, `policy_replay`, `approval_workflow`, `reasoning_workflows`, `olm_bridge`, the entire `trust/` package, and the entire `signal_adapters/` package.

**INTERPRETATION.** The public product is the single-agent governed execution loop. The heavy governance/policy machinery is internal/experimental — consistent with the README's self-description: "governs a *single* agent's execution path."

---

## 2. Module-by-module decomposition

Legend for the function tags: **PLAN**=planning, **EXEC**=execution, **ORCH**=orchestration, **GOV**=governance, **MON**=monitoring, **OPT**=optimization, **AUTHZ**=authorization, **REC**=recovery, **EXPL**=explainability, **MEM**=memory, **TEL**=telemetry, **POL**=policy, **HITL**=human approval, **STATE**=state-management, **SCHED**=scheduling.

### 2.1 Core runtime (World A)

| Module | Responsibility | In → Out | Det/Prob | Runtime/Design | Functions |
|---|---|---|---|---|---|
| `agent.py` (1,926 LOC) | Top-level orchestrator `AgenticLLMWrapper`; fixed per-turn pipeline; sync/stream/async/structured/trace variants | user_input, injected llm/critic/dispatcher/policies → `AgentResult`, event streams, trace | Orchestration **det**; probabilistic only at `decompose_goal` and `generator.generate` | Runtime | ORCH, EXEC, PLAN, GOV, MON, MEM, STATE, TEL, HITL, REC, POL, SCHED |
| `agent_builder.py` | `build_agent()` factory: adapter → MockMCPClient → SafeMCPGateway → CGToolDispatcher → wrapper | config → assembled agent | Det | Design/assembly | ORCH |
| `cg_tool_dispatcher.py` | `CGToolDispatcher` forwards each tool call enriched with adapter CG metadata; `build_cg_mcp_agent` | tool call → gateway result | Det | Runtime+assembly | ORCH, GOV(routing) |
| `mcp_gateway.py` (2,162 LOC) | `SafeMCPGateway` — **World-A governance kernel**: risk-classify → confidence gate → JEPA residual → domain policy → shadow containment → min-confidence floor → escalate → timed execute → audit | `MCPToolCall`+config → `MCPToolResult`+`AuditEntry` | Det (consumes prob signals, decides by threshold/rule) | Runtime hot path | GOV, AUTHZ, POL, HITL, MON, TEL, EXPL, EXEC, REC, SCHED |
| `tool_discovery.py` | Read-only `ToolCatalog` introspection over a gateway | gateway → catalog | Det | Dev tooling | EXPL |

**FACT — the action-loop ordering** (`agent.py:988–1058`, streaming path): per action `cancellation check → budget check → deadline check → approval gate → execute → trace`. The framework docs describe this ordering as "pinned by tests" / "a runtime invariant."
**FACT — enforcement gap:** budget, deadline, per-action timeout and approval are enforced **only on the streaming paths** (`run_stream`/`run_stream_async`); the plain `run()` ignores them (`agent.py:403–410` docstring).
**FACT — stub tool execution:** without an injected dispatcher + `action_type_to_tool` mapping, `search`/`compute`/`validate` actions hit hardcoded placeholder strings (`agent.py:1822–1836`). `build_agent` defaults to `MockMCPClient` — there is no real MCP transport by default.

### 2.2 Governance subsystem (World B — standalone, not called by the agent)

| Module | Responsibility | Det/Prob | Runtime/Design | Functions |
|---|---|---|---|---|
| `governance_service.py` (2,564 LOC) | Decision-only PDP: `authorize(AuthorizationRequest)→AuthorizationResponse`; fans in risk + confidence gate + 7 safety preconditions + forbidden-capability block + JEPA + ~20 signal adapters → ALLOW/DENY/DEFER. **No LLM, no execution.** | Det | Runtime | GOV, AUTHZ, POL, MON, TEL, HITL, REC, EXPL, STATE, MEM |
| `governance_api.py` | FastAPI wrapper: `POST /authorize`, `/health`, `/version` | Det | Runtime (network) | AUTHZ(transport), TEL |
| `governance_models.py` (566) | Pydantic schemas + enums; wide `AuditEvent` with ~20 optional signal sub-dicts | Det | Design+runtime | POL(schema), EXPL, TEL |
| `governance_adapter.py` | 22-line re-export facade of an **external** P52 pipeline schema (`symbolu_core.mechanical…`) — a *second, incompatible* schema family | Det | Pass-through | POL |
| `jepa_governance.py` (1,482) | Fuses a 12-layer ontology signal + 5-vritti distribution via a fixed matrix, compares to action state, emits a **stricter-only** override | **Det heuristic** — no NN, no learned params, no torch, no training | Runtime | GOV, MON, EXPL, POL, REC |

**FACT — "JEPA" is not a neural net.** `jepa_governance.py` docstring (`:29–32`): "JEPA here is NOT a trajectory predictor." All "weights" are hand-coded constants; one `numpy` cosine similarity and one `math.sqrt` geometric mean are the only math. `apply_jepa_override` "can only make stricter, never more permissive" (`:1145`).

### 2.3 Policy & safety layer

| Module | Responsibility | Det/Prob | Functions | Notable wiring/gap (FACT) |
|---|---|---|---|---|
| `adaptive_policy.py` (1,065) | Per-session performance → tunes policy params ("policy-level memory") | Det (fixed-step "gradients" are constants) | POL, MEM, OPT, AUTHZ, MON, STATE | Only `confidence_gate` imports it; "SCC gradient descent" is hardcoded |
| `domain_policy.py` (1,014) | Maps a JEPA assessment → domain action mode via declarative `DomainProfile`; stricter-only, fail-closed | Det | POL, GOV, AUTHZ, EXPL | Built-in FINANCE/DEVOPS/RESEARCH; one rule is a latent no-op (severity-0 ALLOW can't win) |
| `duration_policy.py` (191) | Wall-clock predicates (run/action/approval/session limits) | Det (`time.monotonic`) | POL, GOV, MON, SCHED, REC | Consumed by `agent.py` |
| `policy_bundle.py` (918) | Externalized, versioned, scoped policy model; resolves overrides (global<tenant<domain<env), fail-closed | Det (sha256 fingerprint) | POL, GOV, AUTHZ, TEL, STATE | NOT hot-reload/DSL/durable; override can't reset a field to default |
| `policy_replay.py` (782) | "What-would-this-policy-have-done" replay of audit records via decision-only `GovernanceService` | Det | GOV, MON, EXPL, OPT, STATE | Offline analysis; not on live path |
| `safety_contract.py` (428) | **World-A** pre-execution gate: 6 preconditions → immutable all-or-nothing `SafetyContract` | Det, zero-LLM | GOV, AUTHZ, MON, POL, EXPL, STATE | **Not wired to `policy_bundle`** — thresholds + 7 forbidden capabilities hardcoded/duplicated (`:69–77`) |

### 2.4 Reasoning / prompting / generation

| Module | Responsibility | Det/Prob | Functions | Wiring (FACT) |
|---|---|---|---|---|
| `reasoning_workflows.py` (1,344) | 7 LLM-driven reasoning patterns (chain, tree, debate, map-reduce, Socratic, metacognitive) + deterministic selector | Mixed (bodies call LLM) | ORCH, PLAN, EXEC, OPT, MON, EXPL | **Only `adaptive_prompts` imports it** — standalone, not in shipped loop |
| `adaptive_prompts.py` (1,232) | Rule-based complexity detection → depth → 1–4-step prompt chains; `deepen()` | Mixed (execution calls LLM) | PLAN, ORCH, EXEC, OPT, MON, EXPL, STATE | "Adaptivity" is rule/threshold, not learned |
| `goal_decomposition.py` (472) | User input → `GoalState` (purpose, agency, ordered actions, deps) mapped to 12-D ontology | LLM-driven with rule-based fallback | PLAN, GOV, HITL, AUTHZ, STATE, SCHED | Consumed by `agent.py`; `confidence` hardcoded |
| `reflective_loop.py` (773) | generate→critique→revise; default critic is **rule-based word-counting** | Mixed | EXEC, MON, OPT, REC, EXPL, GOV | Consumed by `agent.py`; threshold 0.85 |
| `local_critic.py` (818) | Local-inference critics (Ollama/Transformers/llama.cpp) + cost-aware router | Mixed | MON, OPT, TEL, GOV, REC | API tier unwired by default; falls back to rule critic |
| `benchmark_critics.py` (476) | CLI harness over 8 static cases | Det harness | MON, OPT, EXPL | Not in any live flow |

### 2.5 Confidence / sovereign / coherence bridges

| Module | Responsibility | Det/Prob | Functions | Enforcement (FACT) |
|---|---|---|---|---|
| `confidence_gate.py` (1,141) | Aggregates ~18 signals → 1 score → 4 behavioral decisions (escalate, budget, memory weight, execute permission) | **Fully det** | GOV, AUTHZ, HITL, MON, OPT, MEM, EXPL, POL | Inert on its own — **recommends, enforces nothing**; callers must honor flags |
| `sovereign_bridge.py` (1,334) | Translates the 32-D "Sovereign State" tensor into agentic dataclasses | Det (slice arithmetic, Shannon entropy) | TEL, MON, EXPL, POL, STATE | Does NOT run the model; pure converter over caller-supplied state |
| `coherence_tracker.py` (585) | 7 turn-level coherence metrics, observation-only | Det | MON, TEL, STATE, EXPL, MEM | `factual_alignment` is a **hardcoded 0.7** placeholder weighted into every score |
| `olm_bridge.py` (632) | 12-layer Ontological Layer Model → confidence/risk signals | Fully det | GOV, POL, MON, AUTHZ, EXPL, TEL | Never constructs an OLM engine; recommends, enforces nothing |

### 2.6 Approval / scheduling / memory

**FACT — three distinct "approval" concerns share the word:**
- `approval.py` (in-memory ephemeral interrupt, R4) — HITL, AUTHZ, GOV, POL. Persists nothing.
- `approval_workflow.py` (781) — durable WAL-SQLite approval-of-record with a state machine (PENDING→APPROVED/DENIED/EXPIRED/…). HITL, AUTHZ, GOV, STATE, TEL, REC, MEM. **FACT:** records/transitions but **does NOT execute or resume** the action ("future resume layer").
- `approval_coverage.py` (202) — pre-run report of which action→tool mappings are gated. EXPL, MON, GOV.

| Module | Responsibility | Det/Prob | Functions | Wiring (FACT) |
|---|---|---|---|---|
| `proactive_scheduler.py` (894) | Autonomous cron/interval/once scheduler executing tool calls via gateway; default OFF | Det control (default confidences hardcoded) | SCHED, EXEC, ORCH, AUTHZ, GOV, MON, TEL, REC, HITL, STATE, POL | **Nothing imports it**; its stored `confidence_gate` is **never called** (dead integration); cron is real but poll-based |
| `memory_store.py` (657) | Append-only external memory + deterministic retrieval (cosine/recency) + opt-in TTL eviction | Det (embedding model pluggable) | MEM, STATE, TEL, OPT, POL | Retention read/write wiring "pending M3"; `last_accessed_at` stays empty |
| `memory_retention.py` | Frozen policy dataclass | Det | POL, GOV, MEM | All-None = no policy |

### 2.7 Support / infrastructure

| Module | Responsibility | Det/Prob | Functions | Note (FACT) |
|---|---|---|---|---|
| `token_budget.py` | Token/cost accounting + `BudgetPolicy.is_exceeded` | Det | GOV, MON, TEL, POL, OPT | Cost caps inert — no shipped adapter emits cost |
| `tracing.py` / `trace_viewer.py` | Fold events → immutable `AgentRunTrace`; terminal formatting | Det | TEL, MON, EXPL, STATE | In-memory only; **no OpenTelemetry**; not a replayable causal record |
| `streaming_events.py` | Event dataclass + ~21 constants | Det | TEL, MON, STATE | "Streaming" is lifecycle, not token streaming |
| `structured_output.py` | Schema-prompt + JSON extract + validate | Det (no LLM call) | GOV(schema), EXEC, EXPL | |
| `cancellation.py` | Cooperative `CancellationToken` | Det | REC, ORCH, STATE | Does not interrupt in-flight calls |
| `request_enrichment.py` | Adapter/CG metadata → governance kwargs | Det, fail-open | GOV, POL, AUTHZ, TEL | Neutral-when-absent |
| `signal_config.py` | Frozen uncertainty-signal config; encodes the 2026-06 pivot | Det | POL, GOV, AUTHZ | **`enable_cg_state_signals=False`**; documents CG AUROC 0.457 (anti-predictive) |
| `llm_adapters.py` (1,077) | OpenAI/Anthropic/Mistral/Gemini + `MistralCGAdapter` (real local torch) + mocks/stubs | **Prob** (real) / det (mocks) | EXEC, TEL, MEM, OPT | `MistralAdapter` lacks usage → budget estimates |
| `inference_mistral.py` (545) | The single runnable CLI entry point | Det orch / prob gen | ORCH, EXEC, SCHED, EXPL | `--cg-allow-stub` = DEV-only stub |
| `validate.py`, `examples.py` | CI smoke harness / usage examples | Det | MON, TEL | All-mock / docs |

### 2.8 `signal_adapters/` (19 files)

**FACT — package role:** governance-time signal-resolution layer bridging sovereign/pipeline subsystems (entropy, vritti, guna, DHA, coherence, UCF, ontology, predictive drift, policy) into governance. **Common pattern:** `resolve_*` → frozen `*Resolution` carrying the signal + `available`/`source_detail`/`reason_codes` + a **bounded confidence penalty** and/or escalation bias. **All deterministic, all runtime** (except `counterfactual_bridge`, offline). Per-adapter caps roll into a **sovereign aggregate cap of 0.20** — the entire apparatus can only push a decision *stricter* by ≤0.20, and goes inert (penalty 0.0) when upstream data is absent, which is the default.

**FACT — most consequential adapters:** `raw_entropy_adapter` (the one empirically-validated signal, penalty ≤0.15), `confidence_risk_gap` (escalate on "confidently uncertain"), `policy_engine_adapter` (hard allow/deny, fail-**safe**), `sovereign_health_adapter` (fail-**safe** with inline mock fallback). **FACT — dead/stub:** `rollback_adapter` captures snapshots but **the post-action rollback loop does not exist**; `readiness_adapter` cooldown is a stub; `counterfactual_bridge` is replay-only and never on the live authorization path.

### 2.9 `trust/` (10 files)

**FACT — role:** a typed, auditable formalization of already-proven governance signals ("Trust-Observable layer"). **Adds no ML.** Maps signals to `Observation`s and combines them via a deterministic, asymmetric, weakest-link tree → ALLOW/CONFIRM/BLOCK, with the rule "trust signals can lower trust but never raise it; only PROVEN validators can BLOCK." **FACT — activation:** wired into `SafeMCPGateway` but **shadow/canary-gated and NOT flipped** — constructor default `TrustMode.LEGACY` (`mcp_gateway.py:806`); the only behavioral branch relaxes a JEPA-sole BLOCK to a human CONFIRM under TRUST_CORE+REVIEWED. Per `trust/TRUST_CORE_FLIP_READINESS.md` the flip is explicitly not taken. Net: real, deterministic, audited in shadow, but currently changes no production ALLOW/BLOCK.

---

## 3. Cross-cutting facts about the whole framework

1. **FACT — determinism profile.** Essentially the entire framework is deterministic pure logic. Probabilistic elements are confined to: the real LLM adapters, LLM-backed critics, and the LLM-driven paths of goal decomposition / reflective loop / reasoning workflows / adaptive prompts. Everything labeled "governance," "policy," "JEPA," "shadow AI," "trust," and every signal adapter is deterministic.
2. **FACT — governance decorates a threshold core.** Across `mcp_gateway`, `governance_service`, `jepa_governance`, `confidence_gate`, and the adapters, the actual decision reduces to: risk classification + confidence-threshold gate + a few safety preconditions + forbidden-capability block + a stricter-only JEPA regime. The elaborate sovereign/vritti/guna/UCF/ontology machinery folds into bounded penalties (≤0.20 aggregate) that only make decisions stricter and go inert by default.
3. **FACT — "recommends but does not enforce" is pervasive.** `confidence_gate`, `sovereign_bridge`, `olm_bridge`, `coherence_tracker`, `adaptive_policy`, `duration_policy`, and `safety_contract` compute decisions/signals but enforce nothing themselves; enforcement depends on a caller honoring the flags.
4. **FACT — maturity is late-prototype.** Single runnable entry point is one CLI (`inference_mistral.py`); no CI gates the test suite; a clean full run reports failures from cross-test state pollution; the "replayable trace / hard cost caps / token streaming" claims are contradicted in the framework's own readiness audit; the CG signal moat is falsified and off by default.
5. **FACT — naming/version incoherence.** The same product is "Agentic Framework" / "Sentinel" / shipped under "Xozence Labs" (now "Ugence Labs"); versions span v1.4.0 → v6.2.0 across docs; two Python import roots (`agentic.agentic_framework` vs `symbolu.agentic_framework`) are documented.

---

## 4. What each function-area maps to (audit summary)

| Function | Where it lives in the framework | Determinism | State (FACT) |
|---|---|---|---|
| Planning | `goal_decomposition`, `adaptive_prompts`, `reasoning_workflows` | LLM-driven + rule fallback | Real (World A) / standalone |
| Execution | `agent.py` action loop, `mcp_gateway`, `proactive_scheduler` | Det control over prob tools | Real but default-mocked transport |
| Orchestration | `agent.py`, builders, dispatcher | Det | Real |
| Governance | `mcp_gateway` (A), `governance_service` (B), `jepa_governance`, `safety_contract` | Det | Two disjoint stacks |
| Monitoring | `coherence_tracker`, `tracing`, signal adapters | Det | In-memory only |
| Optimization | `adaptive_policy`, `local_critic` router, `confidence_gate` budgets | Det | Partly dead wiring |
| Authorization | `mcp_gateway`, `governance_service`, `confidence_gate` | Det threshold | Soft, non-token |
| Recovery | `cancellation`, `failure` handling, `rollback_adapter` | Det | Rollback loop unwired |
| Explainability | `trace_viewer`, `tracing`, audit entries | Det | Analytics rollup, not causal replay |
| Memory | `memory_store`, `memory_retention` | Det | Retention pending |
| Telemetry | `tracing`, audit stores, `token_budget` | Det | No external export |
| Policy | `policy_bundle`, `domain_policy`, `adaptive_policy`, `signal_config` | Det | Not fully wired to enforcement |
| Human approval | `approval` (A), `approval_workflow` (B) | Det | No resume/execute |
| State management | `memory_store`, `coherence`, approval store | Det | Partial |
| Scheduling | `proactive_scheduler`, `duration_policy` | Det | Poll-based, unimported |

**INTERPRETATION (audit conclusion feeding Part 2).** The framework already *contains* most control-plane function-areas — but at the **agent-application layer**, in **soft/probabilistically-informed, recommend-only** form, and split across two stacks that don't talk to each other. This is precisely the profile of an *agent runtime with an embryonic, non-authoritative governance backend* — not of a hardened control plane. The next document compares this profile, area by area, against the deterministic ACP reference architecture.
