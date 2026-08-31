# Agentic Framework — Technical & Product-Readiness Audit

**Independent code-grounded audit of `agentic/agentic_framework/` against `AGENTIC_FRAMEWORK_VC_BRIEF.md` (v1.9.0)**
*Prepared 2026-06-17 · Repo `rasaha/symbolu` · Branch `claude/determined-lamport-n7w0wm`*

> Method: every claim below is verified against source or test code with `file:line`
> citations, or explicitly marked **documentation-only**. The full test suite was
> collected (1,915 tests) and run. Five focused sub-audits + direct reading of the
> 1,926-line action loop (`agent.py`) and 1,877-line gateway (`mcp_gateway.py`) back
> this report. Where the brief is honest about a limitation, that is noted.

---

## 1. Executive verdict

**Maturity: a real, unusually well-built deterministic governance runtime — at late-prototype / early-pilot grade, not yet enterprise-deployable, and over-described in four specific places.**

The core thesis of the brief is **true and defensible**: governance is wired *into* the
execution path, not bolted on. The action loop genuinely enforces
`cancel → budget → approve → execute` via sequential early-returns
(`agent.py:1001/1006/1029/1119`), and the per-tool gateway is far more sophisticated
than the brief even advertises — a five-layer decision stack (forbidden-capability →
confidence gate → JEPA regime → domain policy → shadow-AI containment, "stricter wins";
`mcp_gateway.py:1082–1463`). The test suite is real and large (1,878 test functions,
1,915 collected — comfortably exceeding "1,550+").

But the framework is **narrower and more deterministic than "autonomous AI agent
runtime" implies**, and several headline properties are weaker than stated:

1. **It is a single-generation, plan-then-execute loop, not a multi-step agent.** One
   goal decomposition → one LLM generation (+ optional self-revision) → execute the
   *pre-planned* actions. There is no ReAct-style "observe tool result → think again →
   act" cycle anywhere in `agent.py`. This materially shapes what "agent" means here.
2. **"Replayable AgentRunTrace" is overstated.** The trace is a flat, append-ordered
   event list plus a derived summary — no parent/span IDs, no causal links, **no replay
   function**, not durable (`tracing.py`). It is an analytics rollup, not a causal,
   replayable record.
3. **"Hard token/cost budgets" is half-true.** Token caps are genuinely terminal
   (`agent.py:913–920`). **Cost caps are dead weight** — no shipped adapter emits a cost
   and there is no price table anywhere, so `max_cost` never fires
   (`token_budget.py:115–116`; confirmed no `cost`/`price` in `llm_adapters.py`).
4. **"Streaming" is a lifecycle wrapper, not token streaming.** No production adapter
   overrides `call_stream`; every real adapter returns the full response as one chunk
   (`llm_adapters.py:48–56`). The only multi-chunk test uses a test-local mock.

And the **central differentiator** — CG entropy/vritti signal-enriched governance — is
**architecturally present and live-capable but off the default path and unproven with
real model signals**. Every test that proves a signal changed a decision uses synthetic
fixtures. The brief is honest about this ("operator-validated… not yet repo-validated
end-to-end"), and that honesty should be preserved.

**Net:** strong governance-runtime engineering; the biggest diligence risk is not that
the claims are false but that the **flagship proof points are softer than the language**
("pinned by tests" has no single end-to-end test and the full suite is not green in a
clean run; "replayable" is unimplemented; CG differentiation is untested with real
signals; nothing runs in CI). The right next phase is **hardening and proving what
already exists**, not building multi-agent, low-code, or managed-cloud surface area.

---

## 2. Repo map

```
agentic/agentic_framework/                 # the product (45 modules, ~9.2k LOC core)
├── agent.py               (1926)  AgenticLLMWrapper — THE action loop (run/run_stream/run_stream_async)
├── mcp_gateway.py         (1877)  SafeMCPGateway — per-tool 5-layer decision + audit + ToolRiskLevel/ToolSpec
├── agent_builder.py        (163)  build_agent() — one-call full-stack factory (governance on by default)
├── safety_contract.py      (428)  SafetyGate (turn-level pre-gate)
├── llm_adapters.py        (1032)  Base/OpenAI/Anthropic/Mistral/MistralCG/Mock/Sequential/Stub adapters
├── goal_decomposition.py   (472)  decompose_goal (LLM) + normalize_action_type (heuristic)
├── reflective_loop.py      (773)  ReflectiveGenerator + Rule/LLM/Hybrid critics
├── coherence_tracker.py    (585)  CoherenceEngine (heuristic, no embeddings)
├── confidence_gate.py             ConfidenceGate / ConfidenceSignals / UnifiedConfidence
├── token_budget.py         (200)  BudgetPolicy / UsageStats / estimate_tokens
├── cancellation.py          (62)  CancellationToken (cooperative)
├── approval.py             (161)  in-loop sync approval gate (wired into agent.py)
├── approval_workflow.py    (781)  SQLite durable ApprovalStore (NOT wired into agent loop)
├── approval_coverage.py           describe_approval_coverage()
├── structured_output.py    (315)  prompt + JSON extract + shallow validate (no JSON-Schema, no retry)
├── tool_discovery.py              ToolCatalog (static local snapshot)
├── streaming_events.py     (100)  22 event types + AgentRunEvent
├── tracing.py              (383)  AgentRunTrace + TraceCollector (flat list + summary; not causal/replayable)
├── trace_viewer.py                format_trace / _summary / _timeline
├── cg_tool_dispatcher.py   (287)  CGToolDispatcher (drives gateway; defaults quality/coherence=0.8)
├── jepa_governance.py     (1482)  JEPA residual governor (vritti → regime → block/escalate)
├── governance_service.py          parallel enforcement surface (sums 8 signal penalties) — NOT the MCP path
├── domain_policy.py / shadow_ai.py / duration_policy.py / adaptive_policy.py / policy_replay.py / policy_bundle.py
├── signal_adapters/  (14 files, ~4.7k LOC)  entropy_/vritti_/coherence_state_/guna_anomaly_/predictive_/...
│        (only entropy_adapter + vritti_adapter are consumed by mcp_gateway.py; rest feed governance_service)
└── tests/  (50 files, 1878 def test_, 1915 collected)

agentic/ledger/
├── governance_audit_store.py (776)  SQLite-backed, append-only, tamper-evident audit store + JSONL export
└── ledger_replay_verifier.py (952)  hash-chain replay/verify for governance events (separate from AgentRunTrace)

agentic/docs/   (33 docs)  LOWCODE_DEVELOPER_INTERFACE_SPEC.md (31KB), PILOT_*.md (x3), ADOPTION_VALIDATION_REPORT.md,
                            VALIDATION_GUIDE_MISTRAL.md, design/AGENTIC_GOVERNANCE_ARCHITECTURE.md (109KB) ... → all markdown

.github/workflows/  (9 workflows)  backbone / bcvf / core-rag / formula-drift / ontology-freeze / pipeline /
                            renderer / telemetry-audit / temporal — NONE run agentic/agentic_framework/tests
```

**Two facts that frame everything:**
- `build_agent()` (`agent_builder.py:36–160`) does compose the full stack in one call
  (`adapter → MockMCPClient → SafeMCPGateway[audit_enabled=True] → CGToolDispatcher →
  AgenticLLMWrapper`). Governance is genuinely **on by default** — but over a
  `MockMCPClient`, so out-of-the-box "execution" hits a mock unless a real MCP client is
  supplied.
- **No CI workflow runs this test suite.** "1,550+ tests passing… from our repository
  and CI" is a *local* truth; nothing in `.github/workflows/` gates the framework.

---

## 3. Claim verification table

| # | VC claim | Evidence in repo | Confidence | Missing proof | Recommended next action |
|---|---|---|---|---|---|
| 1 | Code-first Python library, `build_agent`/`ToolSpec`/`ToolRiskLevel` | `__init__.py` exports; `agent_builder.py:36`; `mcp_gateway.py:109–154` | **Proven** | — | Keep. |
| 2 | `BaseLLMAdapter` for OpenAI/Anthropic/Mistral-CG/Mock | `llm_adapters.py:28` (base), real SDK calls at `:168/:278/:351` | **Partially proven** | No real-call path is tested (mocks/`importorskip`/swallowed `ImportError` only); no retry/timeout/rate-limit/error-mapping | Add a recorded-cassette (VCR) integration test per provider; add timeouts+retries |
| 3 | SafetyGate = turn-level governance | `safety_contract.py`; called `agent.py:974` | **Proven** | Decisions depend on heuristic coherence → 18/33 approval tests carry conditional `pytest.skip("Safety gate blocked…")` (nondeterministic) | Make SafetyGate deterministic under test; remove conditional skips |
| 4 | SafeMCPGateway = per-tool governance | `mcp_gateway.py:1082–1463`, 5-layer stack | **Proven (exceeds claim)** | — | Document the extra layers (JEPA/domain/shadow) — they are undersold |
| 5 | Risk levels read_only→write→execute→destructive→privileged | `ToolRiskLevel` `mcp_gateway.py:109–115`; min-confidence map `:405–412` | **Proven** | Auto-classifier is substring/pattern based (`:321–402`), defaults to WRITE (fail-closed, good) | Keep; note classifier is heuristic when risk not explicit |
| 6 | Runtime approvals (human-in-the-loop as runtime arg) | `approval.py`; enforced **before** execute `agent.py:1029` → `:1111`; deny→`continue` `:1101` | **Proven, with caveats** | Deny = per-action skip, **not run-terminal**; in-loop gate has no persistence; durable `ApprovalStore` (`approval_workflow.py`) is **not wired** to the loop and has no resume layer | Wire durable store + resume; decide deny-semantics (skip vs halt) explicitly |
| 7 | Hard **token + cost** budgets as terminal events | Token: terminal `return` `agent.py:913–920/1006–1013`; `test_token_budget.py:244` | **Partially proven** | **Cost cap is inert** — no adapter emits `cost`, no price table (`token_budget.py:115`); budget checked **after** generation, never pre-flight; per-run only (no tenant/global quota, no concurrency safety) | Add price table + pre-flight estimate gate + global quota |
| 8 | Replayable `AgentRunTrace` | `tracing.py:55–165` (flat events + summary); `to_dict()` | **Not proven (overstated)** | No parent/causal links; **no replay function** (`grep replay` → none in tracing); not durable; no PII redaction | Either implement real replay+durability or rename to "structured run summary" |
| 9a | Streaming | event lifecycle real (`streaming_events.py`, `agent.py:880`) | **Overstated** | No adapter overrides `call_stream`; every real adapter yields one chunk (`llm_adapters.py:48–56`); only test-mock streams | Implement provider-native streaming (Anthropic `messages.stream`, etc.) |
| 9b | Async cancellation | `cancellation.py`; checkpoints `agent.py:838…1194` | **Proven** | Cooperative only — cannot preempt in-flight LLM/tool call (documented `:1120–1124`) | Keep; document latency bound |
| 9c | Structured output | `structured_output.py`; `run_structured` `agent.py:585` | **Partially proven** | No JSON-Schema; dataclass fields presence-checked, **not type-checked**; **no retry-on-invalid**; `except (…, Exception)` swallows bugs | Add jsonschema/Pydantic validation + repair-retry loop |
| 9d | Tool discovery | `tool_discovery.py`; `from_gateway` reads live registry | **Proven (thin)** | Static point-in-time snapshot; no remote `tools/list`; stale after mutation; dup-name last-write-wins | Keep; relabel as "local introspection" not "discovery" |
| 10 | Ordering `cancel→budget→approve→execute` **pinned by tests** | Pairwise pins: budget-before-approval `test_audit_hardening.py:177/206`; cancel-before-approval `:272`; denied-no-exec `test_approval.py:209`; cancel-no-exec `test_async_cancellation.py:288` | **Partially proven** | **No single end-to-end test** asserts all 4 stages in one ordered run; suite not green in clean full run; not in CI | Add one canonical `test_action_loop_contract.py`; add CI gate |
| 11 | 1,550+ tests | 1,878 `def test_`; **1,915 collected** | **Proven (count)** | "Passing" caveated: clean full run = **51 failed / 1,813 passed / 51 skipped** (failures are cross-test state pollution — all pass per-file); no CI | Fix fixture leakage; add green CI |
| 12 | Live Anthropic validation, 3/3 phases, exact usage | `ADOPTION_VALIDATION_REPORT.md`, `PILOT_INTERNAL_COPILOT_REAL_LLM.md` | **Documentation-only** | Operator-run, not in repo tests/CI; no recorded artifact | Commit a recorded (sanitized) transcript + cassette test |
| 13 | Realistic-mock regression 60/60 | docs (`TEST_RESULTS.md`/validation docs) | **Documentation-only** | Not located as a runnable suite | Convert to a committed pytest module |
| 14 | Two internal pilots | `PILOT_RESEARCH_ASSISTANT.md`, `PILOT_INTERNAL_COPILOT*.md` | **Documentation-only** | No runnable pilot `.py`; `examples.py` (578 LOC) exists but is not the pilots | Land at least one pilot as a runnable, tested example |
| 15 | CG entropy/vritti signal-enriched governance | Real wiring: `mcp_gateway.py:1134–1139` (entropy penalty), `:876–912` (vritti→JEPA→block); bridge `sovereign_bridge.py` → real EntropyEngine/ChittaVrittiEngine | **Partially proven (off default path)** | Off default path (only `MistralCGAdapter`/`StubCGLLMAdapter` populate signals); every outcome-changing test uses **synthetic** signals; real-model path never tested; entropy bounded to ≤0.15 penalty | Land one repo test driving a real (or recorded) CG forward-pass through a flipped decision |
| 16 | Roadmap: OTel, audit persistence, multi-agent, low-code, managed, SOC2 | OTel: **absent**. Audit persistence: **partially exists** (`ledger/governance_audit_store.py` SQLite + JSONL; gateway `_audit_store` hook `mcp_gateway.py:1037–1073`). Rest: roadmap | **Roadmap** (audit persistence ahead of schedule) | Surface the existing SQLite audit store in the brief; it undersells |

---

## 4. Runtime primitive audit

For each: **status · core files · public API · test coverage · failure modes · enterprise gaps.**

### 4.1 BaseLLMAdapter — *implemented (abstract)*
- `llm_adapters.py:28–104`. Abstract `call()`; concrete `call_stream` (single-chunk passthrough `:48–56`), `call_stream_async` (`asyncio.to_thread` wrap `:58–70`), `get_last_usage` (`→None` default `:85`), `call_with_messages`.
- **Gap:** the streaming/usage defaults are no-ops that every real adapter inherits unchanged → see streaming/budget gaps.

### 4.2 OpenAIAdapter / AnthropicAdapter / MistralAdapter — *implemented, untested against network*
- Real SDK calls: OpenAI `client.chat.completions.create` (`:168`), Anthropic `client.messages.create` (`:278`), Mistral `client.chat.complete` (`:351`). Anthropic supports `auth_token` or `api_key` (`:217–249`).
- **Coverage:** constructor/usage-record tests only, all behind `ImportError`/`skipTest`; **no real call path executed**. `MistralAdapter` has **no usage tracking** (no `_record_usage`) yet is the one wired into the runnable `inference_mistral.py`.
- **Enterprise gaps:** zero retry/timeout/rate-limit/error-mapping anywhere; no cost; keys passed straight to SDK (no masking).

### 4.3 MistralCGAdapter — *implemented, real-inference path never run*
- `llm_adapters.py:375–672`. Hard torch dep (`:460–464`) + `MistralCGWrapper` checkpoint. Hand-rolled autoregressive loop with **no KV cache** (O(n²) re-forward per token, `:556–561`). Vritti/Guna **sampling** gates are temperature-only nudges, **off by default** (`:573–615`). Exposes `last_cg_metadata` (32-D `state`, `delta_S`) via `get_cg_metadata()` (`:670`).
- **Coverage:** all tests bypass `__init__` and inject a MagicMock backbone; torch-gated; the one end-to-end CG smoke test is env-gated (`SYMBOLU_RUN_CG_SMOKE=1`) and **stub-backed** (`test_inference_mistral_cg_smoke.py`).
- **Gap:** the differentiator's real path is unexercised; perf footgun (no KV cache).

### 4.4 Mock / Sequential / Stub adapters — *implemented, well-tested*
- `MockLLMAdapter` (8 tests), `SequentialMockAdapter` (7), `StubCGLLMAdapter` (`IS_STUB=True`, deterministic 32-D fixture — the dev stand-in for CG). Solid.

### 4.5 GoalDecomposition — *LLM path real; surrounding logic heuristic*
- `goal_decomposition.py`. `decompose_goal` (`:319`) does a real `llm_client.call(prompt)`; on any failure **silently falls back** to `_simple_extraction` (keyword matching `:405–419`) while keeping `confidence` hardcoded high. `normalize_action_type` (`:262`) is alias-lookup + a hardcoded keyword→tool dict.
- **Coverage:** 28 tests, LLM always mocked; `normalize_action_type`/`_resolve_by_description` have **no direct unit tests**.
- **Gap:** silent fallback masks model failure; out-of-enum `agency_level` flows unchecked into the autonomy flag (`:381`) — security-relevant.

### 4.6 ReflectiveGenerator — *loop real; default critic heuristic*
- `reflective_loop.py`. Genuine generate→critique→regenerate loop (`:475–506`). **Default critic is `RuleBasedCritic`** — length + keyword-overlap + regex; `correctness` is a **constant 0.7/0.5** (`:209`). `LLMBasedCritic`/`HybridCritic` are real model-based but opt-in.
- **Coverage:** 25 tests; `generate_stream`/`_async` **untested**.
- **Gap:** default loop optimizes for length, **cannot detect factual errors**; `token_count` is `split()` word count.

### 4.7 CoherenceEngine — *deterministic heuristics, no model/embeddings*
- `coherence_tracker.py`. No embedding/vector/cosine anywhere. `factual_alignment` is **hardcoded 0.7** (`:304`); `internal_consistency` = `quality_score + 0.1`; `goal_alignment` = bag-of-words overlap with a 0.4 floor; volatility/identity = arithmetic on its own history.
- **Coverage:** 21 tests; the only text-touching logic (`_compute_goal_alignment`/stemmer) has **no direct tests**.
- **Gap:** surfaces a fabricated "factual" number that feeds `should_intervene` and the revision loop — misleading if read as grounding.

### 4.8 SafetyGate (turn-level) — *implemented*
- `safety_contract.py`, called `agent.py:974`. Fail-closed action gating on coherence state. **Nondeterminism** leaks into tests (18 conditional skips).

### 4.9 SafeMCPGateway (per-tool) — *implemented, exceeds claim*
- `mcp_gateway.py:1082–1463`. Order: forbidden-capability → `ConfidenceGate.evaluate` → JEPA regime (`effective_confidence = conf + jepa_adj − entropy_penalty`, `:1134`; threshold block `:1463`) → domain policy → shadow-AI. "Stricter wins" merging. Durable audit hook with **hard-fail on persistence error** (`:1063–1073`).
- **Coverage:** 54 tests pass in isolation (32 fail under full-suite state pollution).

### 4.10 ToolSpec / ToolRiskLevel — *implemented*
- `mcp_gateway.py:109–182`. Per-tool `risk_level`, `min_confidence`, `requires_confirmation`, capabilities. Clean.

### 4.11 Approval system — *two disjoint layers*
- **In-loop** (`approval.py`): sync callback, enforced before execute (`agent.py:1029→1111`); deny → skip-this-action-`continue` (not run-terminal); blocks forever without a `DurationPolicy` TTL. **No persistence.**
- **Durable** (`approval_workflow.py`, 781 LOC): SQLite, validated state machine, history — but **not wired** to the agent loop and **no resume layer** (records decisions, can't unblock a paused run).
- Claimed 33 tests; actual 33 + 32 + 16 = 81.

### 4.12 Budget system — *token terminal; cost inert*
- `token_budget.py`. Token caps terminal (`agent.py:913–920`). `estimate_tokens` = `len//4`. **Cost never enforced** (no adapter cost, no price table). Per-run only; no concurrency safety. 37 tests (exact).

### 4.13 Cancellation — *cooperative, correct*
- `cancellation.py`. Thread-safe `cancel()`; lock-free reads (benign in CPython); well-distributed checkpoints; cannot preempt in-flight call. 31 tests (exact).

### 4.14 Trace / AgentRunTrace — *summary, not causal/replayable*
- `tracing.py`. Flat event list (`event_type, timestamp, turn_id, session_id, payload`) + ~30 derived summary fields. **No causal links, no replay, no durability, no PII handling.** 26 + 30 tests (brief undercounts).

### 4.15 Structured output — *prompt + extract + shallow validate*
- `structured_output.py`. Robust 3-tier JSON extraction; **no JSON-Schema, no nested/dataclass type checks, no retry-on-invalid**. 44 tests (exact).

### 4.16 Streaming — *lifecycle events only*
- `streaming_events.py` + `agent.py`. 22 event types, correct ordering; but `TEXT_CHUNK` originates from the single-chunk base `call_stream`. 28 tests (exact).

---

## 5. Model-vs-runtime assessment

**Precise classification: Agentic Framework is a deterministic governance/policy runtime
that wraps a single LLM generation per turn and gates pre-planned actions. It is (in
order of weight): a governance policy engine + a deterministic runtime wrapper. It is
*optionally and unprovenly* a model-informed governance system. It is *not* a true
agentic model, and *not* a multi-step autonomous agent loop.**

Evidence:
- **Not a true agentic model.** All model intelligence is delegated to an injected LLM
  via prompts. The framework's own logic is deterministic: heuristic critics, bag-of-words
  coherence, hardcoded `factual_alignment=0.7`, keyword action-normalization.
- **Not a multi-step agent.** `run_stream` calls the LLM **once** (`agent.py:858`), then
  executes actions produced by a single up-front `decompose_goal`. No re-invocation after
  observing tool output. "Autonomous agent" here = "governed single-shot planner +
  executor."
- **Governance is the real product** and it is genuinely runtime-level: the ordering
  invariant and the 5-layer gateway are the substantive, differentiated engineering.
- **Model-informed governance (CG signals): present but inert by default.** On the
  default path the "confidence" driving the gateway comes from caller-supplied scalars
  (`quality_score`/`coherence_score`, defaulting 0.5–0.8; `cg_tool_dispatcher.py:120–121`,
  `mcp_gateway.py:820–827`) plus risk-level heuristics — **not** model internals. Entropy
  resolves to `available=False` (zero penalty) and vritti to an approximation heuristic.
  Real model signals only flow when a CG adapter is opted in (`build_cg_mcp_agent` / `--cg`).

**Are CG entropy/vritti signals in the decision path?** *Architecturally yes, operationally no
(by default), and unproven with real signals.* The math is real
(`effective_confidence = … − entropy_resolution.confidence_penalty`, `mcp_gateway.py:1134–1139`;
vritti → JEPA regime → `BLOCKED`/`ESCALATE`, `:1162–1238`), and a real tensor→signal bridge
exists (`sovereign_bridge.py` → real `EntropyEngine`/`ChittaVrittiEngine`). But: (a) the
default agent never produces signals; (b) entropy is capped at a ≤0.15 penalty and "does not
hard-block" by design; (c) **no test drives a real `MistralCGWrapper` forward-pass signal
through a flipped governance decision** — all use synthetic `EntropyResult`/vritti fixtures or
the deterministic stub. Classification: **(c) optional/off-default plumbing + (b) tested only
with fakes; not (a) live-proven; not (d) docs-only.** The brief's own wording is accurate;
keep it.

---

## 6. Critical gaps (ranked by diligence impact)

1. **The flagship "pinned by tests" claim has no single end-to-end test** and the full
   suite is **not green in a clean run** (51 failures from cross-test state pollution),
   and **nothing runs in CI.** An auditor cannot today point to one green test + one CI
   run that proves the contract. *This is the #1 risk because it undermines the core
   pitch.*
2. **"Replayable trace" is unimplemented.** No replay function, not causal, not durable.
3. **Cost budgets don't work** (no cost source). "Hard dollar caps" is unsupported as shipped.
4. **Streaming is not streaming.** Provider-native incremental output is absent.
5. **CG differentiation is unproven with real signals** and off the default path.
6. **No real-adapter test coverage** and **no resilience** (retry/timeout/rate-limit) — a
   single 429/timeout hangs or crashes a run.
7. **Approval durability gap:** the in-loop gate has no persistence/resume; the durable
   store isn't wired to the loop. A restart loses pending approvals.
8. **Heuristics presented as cognition:** `factual_alignment=0.7`, constant `correctness`,
   bag-of-words coherence feed governance signals — reputationally risky if oversold.
9. **Per-tool `_dispatch_via_mcp` spins a fresh event loop per call** (`agent.py:1865–1874`)
   — fragile under async hosts and a latency cost.
10. **Single-generation architecture** limits "autonomous agent" scope (no multi-step reasoning).

---

## 7. Recommended next phases

Prioritized. Each: objective · commercial rationale · tasks · files · tests · acceptance · demo.

### Phase A — Contract hardening & adversarial action-loop tests *(DO FIRST)*
- **Objective:** make the core invariant un-arguable: one canonical end-to-end ordering
  test, a clean-green suite, and a CI gate.
- **Why it matters:** this *is* the pitch. Enterprise risk teams sign off on "show me the
  test." Today there's no single test and no CI.
- **Tasks:** (1) write `test_action_loop_contract.py` asserting `cancel→budget→approve→execute`
  in one instrumented run; (2) add adversarial cases (hallucinated tool name, malformed
  tool call, denied approval, partial tool failure, budget exhaustion across multiple
  actions, concurrent approvals, timeout/no-retry semantics, nested actions); (3) fix the
  51 state-pollution failures (fixture/async isolation); (4) make SafetyGate deterministic
  under test (remove 18 conditional skips); (5) add `.github/workflows/agentic-framework-ci.yml`.
- **Files:** `tests/test_action_loop_contract.py` (new), `tests/conftest.py`, `safety_contract.py`,
  `tests/test_proactive_scheduler.py`/`test_mcp_gateway.py` (isolation), `.github/workflows/`.
- **Acceptance:** `pytest agentic/agentic_framework/tests -q` → **0 failed** in a clean
  env; CI green badge; the contract test reads top-to-bottom as a spec.
- **Demo:** a green CI run + the one-file contract test handed to a design partner's risk team.

### Phase C — Trace durability + OpenTelemetry + true replay *(DO SECOND — partially started)*
- **Objective:** turn `AgentRunTrace` into a durable, exportable, replayable record;
  surface the existing SQLite audit store.
- **Why it matters:** "audit + replay" is the #1 enterprise evaluator ask, and the brief
  already promises it. The SQLite `governance_audit_store` + `ledger_replay_verifier`
  already exist — this is finishing, not starting.
- **Tasks:** (1) persist `AgentRunTrace` (reuse `ledger/governance_audit_store.py`); (2)
  OTel span exporter mapping events→spans with parent links; (3) add real parent/causal
  IDs to events; (4) implement `replay(trace)` that re-drives decisions deterministically;
  (5) PII redaction hook on `payload`.
- **Files:** `tracing.py`, `trace_viewer.py`, new `otel_export.py`, `ledger/governance_audit_store.py`.
- **Tests:** trace round-trips through store; OTel spans validate; replay reproduces decisions;
  redaction scrubs configured fields.
- **Acceptance:** a run's trace appears in Jaeger/Grafana with causal spans and is
  replayable from the store; hash-chain verify passes.
- **Demo:** Jaeger screenshot + tamper-evident audit-log verify.

### Phase B — External governance benchmark vs LangGraph / CrewAI *(DO THIRD)*
- **Objective:** the first third-party-credible proof that the governance contract holds
  where competitors' don't.
- **Why it matters:** every number today is self-reported; a reproducible benchmark is the
  fundraising/sales asset.
- **Tasks:** standardized scenario suite (denied action, over-budget action, hallucinated
  tool, destructive-without-approval); thin LangGraph/CrewAI adapters; scorecard
  (blocked-correctly %, leaked-action count, audit completeness); reproducible harness +
  published methodology.
- **Files:** new `benchmarks/governance/` (scenarios, adapters, runner, scorecard).
- **Acceptance:** one command reproduces a scorecard showing Agentic Framework blocks
  denied/over-budget/destructive actions that baselines let through.
- **Demo:** the scorecard + a reproducible repo.

### Phase D — Approval policy engine / DSL *(AFTER A–C)*
- Declarative policy (risk × confidence × domain → require/deny/escalate) replacing the
  two ad-hoc approval layers; wire the durable store + resume. Closes the
  double-gating/persistence gaps (`approval_coverage.py:27–40`).

### Defer (see §8): **E** managed runtime, **F** multi-agent handoffs, **G** retrieval
adapter, **H** CG real-signal integration, **I** SOC2 — all valuable, none before A–C.

Also fold in two **fixes** (small, high-credibility): real **cost table** so budgets are
honest (touches `llm_adapters.py`, `token_budget.py`), and provider-native **streaming**
for Anthropic/OpenAI (`llm_adapters.py`). Or, if not building them now, **soften the brief
language** on cost and streaming.

---

## 8. What NOT to build next (be blunt)

**Do not build multi-agent, low-code console, CG/vritti real-model integration, or managed
cloud before the external benchmark and audit persistence (Phases A–C).** Rationale:

- **Multi-agent handoffs (F):** expands the attack surface of a contract you haven't yet
  proven end-to-end or in CI. Governing one agent's action loop is not yet diligence-tight;
  governing handoffs between agents multiplies the unproven seams. Premature.
- **Low-code console (E/console):** the 31KB `LOWCODE_DEVELOPER_INTERFACE_SPEC.md` is a
  spec, not a product gap that's blocking deals. A console makes a weak contract *look*
  finished; it doesn't make it *be* finished. Build it after the contract is CI-green and
  benchmarked.
- **CG/vritti real-model integration (H):** this is the "category of one" claim and it is
  tempting — but it is the **hardest to prove**, requires torch + a 7B checkpoint + GPU,
  has an O(n²) generation loop, and is the **least likely to close a near-term regulated
  deal** (which is gated on audit/approval/budget, not on model-internal entropy). Prove
  the deterministic governance first; land *one* recorded real-signal test (cheap) to keep
  the claim honest, then defer the rest.
- **Managed cloud (E):** premature ops/compliance burden before a reference design partner
  exists. Q1–Q2 of the brief (pilots + benchmark + OTel) must land first.

The single highest-leverage move is **Phase A**: a clean-green suite + one canonical
contract test + CI. Everything the brief sells rests on it, and it is currently the softest
spot.

---

## 9. 30 / 60 / 90-day plan

**30 days — "Make the contract un-arguable."**
- Land `test_action_loop_contract.py` (single end-to-end `cancel→budget→approve→execute`).
- Fix the 51 state-pollution failures; remove SafetyGate nondeterminism → **clean-green suite**.
- Add `agentic-framework-ci.yml` (collect 1,915 + run green on every push).
- Add adversarial loop tests (hallucinated tool, malformed call, denied approval, partial
  failure, budget-exhaustion-mid-run, concurrent approvals, timeout/no-retry).
- Fix cost accounting (price table) **or** withdraw "cost cap" language; same for "streaming"/"replayable."
- **Milestone:** green CI + a one-page "denied/over-budget action cannot execute — here's the test" diligence sheet.

**60 days — "Make it auditable and honest."**
- Persist `AgentRunTrace` via existing SQLite store; add OTel export + causal span IDs; PII redaction.
- Implement real `replay(trace)`; wire durable `ApprovalStore` + resume.
- Implement provider-native streaming (Anthropic/OpenAI); add timeouts + retries to adapters.
- Land **one** recorded/real CG-signal test that flips a governance decision.
- **Milestone:** Jaeger trace + tamper-evident audit verify + 1 real design-partner pilot running on it.

**90 days — "Prove it externally."**
- Publish the LangGraph/CrewAI governance benchmark (reproducible harness + scorecard).
- Ship the approval policy DSL (Phase D).
- Cassette-based real-adapter integration tests (OpenAI/Anthropic/Mistral) in CI.
- **Milestone:** third-party-reproducible benchmark scorecard + 2–3 external pilots.

---

## 10. Tests to add (concrete)

| Test | File | Asserts |
|---|---|---|
| `test_full_ordering_invariant_end_to_end` | `tests/test_action_loop_contract.py` (new) | In one run, instrument that checks fire in order cancel→budget→approve→execute and short-circuit correctly |
| `test_hallucinated_tool_name_blocked` | same | Unknown tool → gateway `BLOCKED`, action status `blocked`, no handler call, audit entry written |
| `test_malformed_tool_call_rejected` | same | Bad/missing params → reject before handler; trace records it |
| `test_partial_tool_failure_continues_and_traces` | same | One action fails (`status=failed`), run continues, `RUN_COMPLETED` emitted, failure in trace |
| `test_budget_exhaustion_across_multiple_actions` | same | Multi-action plan with rising usage → `BUDGET_EXCEEDED` mid-loop, remaining actions never start |
| `test_concurrent_approvals_thread_safe` | same | Parallel approval callbacks don't corrupt state/audit |
| `test_no_retry_on_adapter_error_is_explicit` | `tests/test_real_llm_hardening.py` | Document/verify error → `RUN_ERROR` (and add retry semantics) |
| `test_real_cost_budget_triggers` | `tests/test_token_budget.py` | With a price table, `max_cost` actually fires |
| `test_anthropic_streaming_multichunk` | `tests/test_streaming_events.py` | Real provider yields >1 `TEXT_CHUNK` (after streaming impl) |
| `test_trace_replayable_roundtrip` | `tests/test_tracing.py` | `replay(to_dict(trace))` reproduces decisions (after replay impl) |
| `test_cg_real_signal_flips_decision` | `tests/test_mcp_gateway.py` | A recorded CG forward-pass signal changes allow→escalate/deny |
| `test_safetygate_deterministic` | `tests/test_safety_contract.py` | Same inputs → same gate decision (removes 18 conditional skips) |
| Full-suite isolation fix | `tests/conftest.py` + offenders | `pytest tests -q` → 0 failed in clean env |

---

## 11. Demo / benchmark artifacts to create

1. **`test_action_loop_contract.py`** — the single readable spec-as-test (Phase A).
2. **`agentic-framework-ci.yml`** — green CI badge over 1,915 tests (Phase A).
3. **Governance benchmark `benchmarks/governance/`** — scenarios + LangGraph/CrewAI adapters
   + scorecard + reproducible runner (Phase B).
4. **OTel + Jaeger demo** — a governed run rendered as a causal span tree (Phase C).
5. **Tamper-evident audit demo** — append to SQLite store, then `ledger_replay_verifier`
   hash-chain verify (Phase C).
6. **One runnable, tested pilot** (Research Assistant) replacing the markdown-only pilot.
7. **Diligence one-pager** — "a denied / over-budget / destructive action cannot execute,
   and here is the exact test + CI run that proves it."

---

## 12. Developer execution checklist (commands)

```bash
# --- Environment (light deps only; torch/openai/anthropic NOT required for the suite) ---
cd /home/user/symbolu
python -m pip install "pytest>=7.4" pytest-asyncio numpy pydantic fastapi httpx

# --- Reproduce this audit's numbers ---
python -m pytest agentic/agentic_framework/tests --collect-only -q | tail -1      # → 1915 collected
python -m pytest agentic/agentic_framework/tests -q | tail -3                      # → 51 failed, 1813 passed, 51 skipped
# Prove failures are state-pollution, not logic (each passes in isolation):
python -m pytest agentic/agentic_framework/tests/test_mcp_gateway.py -q            # → 54 passed
python -m pytest agentic/agentic_framework/tests/test_token_budget.py -q           # → 37 passed
python -m pytest agentic/agentic_framework/tests/test_proactive_scheduler.py -q    # → 43 passed

# --- Verify the ordering invariant (today: pairwise, not end-to-end) ---
python -m pytest agentic/agentic_framework/tests/test_audit_hardening.py -q
python -m pytest agentic/agentic_framework/tests/test_async_cancellation.py::TestActionNonPreemptive -q

# --- Verify per-primitive counts ---
for f in test_streaming_events test_async_cancellation test_structured_output \
         test_tool_discovery test_token_budget test_tracing test_approval; do
  printf "%s: " "$f"; grep -c "def test_" agentic/agentic_framework/tests/$f.py
done

# --- Phase A deliverables to CREATE ---
#  1) agentic/agentic_framework/tests/test_action_loop_contract.py   (new — see §10)
#  2) .github/workflows/agentic-framework-ci.yml                      (new — runs the suite green)
#  3) Fix tests/conftest.py fixture isolation (the 51 failures)

# --- Missing scripts Claude should create next (in priority order) ---
#  agentic/agentic_framework/tests/test_action_loop_contract.py      (Phase A, canonical contract)
#  .github/workflows/agentic-framework-ci.yml                        (Phase A, CI gate)
#  agentic/agentic_framework/otel_export.py                          (Phase C, OTel exporter)
#  benchmarks/governance/{scenarios.py,adapters/,run_benchmark.py}   (Phase B, external benchmark)
#  agentic/agentic_framework/pricing.py                              (cost table → real cost budgets)
```

**Suggested CI workflow (skeleton for `.github/workflows/agentic-framework-ci.yml`):**
```yaml
name: agentic-framework-ci
on: { push: { paths: ["agentic/agentic_framework/**"] }, pull_request: {} }
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: python -m pip install "pytest>=7.4" pytest-asyncio numpy pydantic fastapi httpx
      - run: python -m pytest agentic/agentic_framework/tests -q
        # NOTE: currently RED in full-suite mode — Phase A must fix fixture isolation first.
```

---

### Appendix — confidence legend
**Proven** = verified in source + passing test. **Partially proven** = works but with a
material caveat. **Overstated** = the capability exists in weaker form than the word
implies. **Not proven** = claimed capability absent in code. **Documentation-only** =
asserted in markdown, not runnable/CI-gated in the repo.
