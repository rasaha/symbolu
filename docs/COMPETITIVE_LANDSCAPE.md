# Agentic Framework Competitive Landscape & Differentiation Analysis

> **Version:** 1.0.0 | **Date:** 2026-04-04
>
> This document compares Sentinel's agentic governance architecture against
> the current industry landscape of agent frameworks, SDKs, and safety
> systems. The goal is an honest assessment: where Sentinel genuinely
> differentiates, where it converges with industry, and where it still
> has product gaps.

---

## Executive Summary

The agentic AI framework market has consolidated around two architectural
paradigms:

1. **Orchestration-first frameworks** — Focus on workflow composition,
   multi-agent coordination, and tool use. Governance is bolt-on or
   developer-responsibility. Examples: LangGraph, CrewAI, AutoGen.

2. **Platform agent SDKs** — Focus on model-native tool use, hosted
   execution, and guardrails-as-a-service. Governance exists but is
   primarily content filtering and permission gating. Examples: OpenAI
   Agents SDK, Google ADK, AWS Bedrock Agents, Anthropic Claude Agent SDK.

**Sentinel occupies a third position:** a governed semantic-control
architecture where governance is not a wrapper around agent execution but
is structurally embedded in the runtime decision path. The governance
engine doesn't just ask "is this tool allowed?" — it asks "what
semantic-cognitive state is the system in, and does this action make sense
given that state?"

This is an unusual architectural choice. Most frameworks treat governance
as a filter layer (input guardrails, output guardrails, permission tables).
Sentinel treats governance as a multi-layered decision engine that
integrates semantic state, domain policy, provenance control, sovereign
model signals, and audit infrastructure into the authorization path itself.

### Comparison Dimensions

This analysis evaluates frameworks across seven governance-relevant
dimensions:

| Dimension | What It Means |
|-----------|---------------|
| **Governance depth** | Is governance structural or bolt-on? How many layers? |
| **Semantic state awareness** | Does the system reason about cognitive/semantic state, or only tool permissions? |
| **Domain policy** | Can governance behavior vary by domain without code changes? |
| **Provenance / trust** | Does the system track asset trustworthiness and shadow AI? |
| **Audit / replay** | Can you forensically reconstruct why a decision was made? |
| **Safety invariants** | Are there structural guarantees (stricter-only, fail-closed, bounded effects)? |
| **Sovereign / model signal integration** | Does governance consume signals from the model's internal state? |

---

## Category 1: Orchestration-First Frameworks

These frameworks prioritize workflow composition, multi-agent coordination,
and developer ergonomics. Governance, when present, is the developer's
responsibility to add.

### LangGraph (LangChain)

**Architecture:** Directed graph of stateful nodes. Each node is a function
or LLM call. Edges define control flow (conditional routing, cycles).
State is a typed dict that flows through the graph.

**Strengths:**
- State checkpointing enables time-travel debugging and replay
- Human-in-the-loop via `interrupt()` nodes that pause execution for
  approval before resuming
- Subgraph composition for multi-agent patterns
- LangSmith integration provides tracing, evaluation, and observability
- Persistent state across conversation turns

**Governance model:**
- **No built-in governance engine.** Safety is developer-implemented via
  custom nodes in the graph
- Human-in-the-loop is structural (interrupt nodes) but not policy-driven
- No tool risk classification, no domain-aware policy, no provenance control
- No semantic state awareness — state is application-defined, not
  cognitive/semantic
- Checkpointing enables replay but not governance-aware replay (no
  "what would policy X have decided?" capability)

**Sentinel comparison:**
LangGraph is a powerful workflow engine. Sentinel is not competing on
workflow composition — it is competing on what happens at the governance
decision point. LangGraph provides the plumbing; Sentinel provides the
policy authority. They could theoretically be complementary: LangGraph
orchestrating agents, Sentinel governing their actions.

### CrewAI

**Architecture:** Role-based multi-agent system. Agents have roles, goals,
backstories, and tool access. Tasks define work units with expected outputs.
Crews orchestrate agent collaboration (sequential or hierarchical).

**Strengths:**
- Intuitive role-based agent definition
- Built-in delegation between agents
- Memory system (short-term, long-term, entity memory)
- Structured output validation
- Process types: sequential, hierarchical, consensual

**Governance model:**
- **Minimal governance.** Safety depends on prompt engineering (role
  definitions, backstories) and tool access control
- No structured approval/escalation mechanism
- No domain policy layer — all agents operate under the same rules
- No provenance tracking or shadow AI detection
- No audit trail beyond logging
- No semantic state model — agent "state" is conversational context,
  not cognitive assessment

**Sentinel comparison:**
CrewAI optimizes for developer experience in multi-agent coordination.
Sentinel optimizes for governed, auditable decision-making. CrewAI trusts
agents to behave according to their role prompts. Sentinel structurally
enforces behavior through layered policy, regardless of what the agent
"intends."

### Microsoft AutoGen

**Architecture:** Multi-agent conversation framework. Agents communicate
via message passing. Supports nested conversations, group chat patterns,
and code execution. AutoGen Studio provides a visual builder.

**Strengths:**
- Flexible multi-agent conversation patterns (two-agent, group chat,
  nested, sequential)
- Built-in code execution with Docker sandboxing
- Human proxy agent for human-in-the-loop
- Teachable agents (learning from human feedback)
- Support for diverse LLM backends

**Governance model:**
- Code execution sandboxing (Docker) is a real safety control
- Human proxy agent enables approval but is conversation-based, not
  policy-driven
- `max_consecutive_auto_reply` limits runaway agent loops
- No tool risk classification beyond code execution sandboxing
- No domain-aware policy, no provenance control
- No semantic state model
- No structured audit trail or governance replay
- Termination conditions are conversation-based (keyword detection),
  not governance-based

**Sentinel comparison:**
AutoGen's code execution sandboxing is a genuine safety feature that
Sentinel does not have (Sentinel governs authorization decisions, not
execution sandboxing). However, AutoGen has no governance model beyond
basic guardrails. The human proxy agent is structurally weaker than
Sentinel's multi-layer escalation system.

### Common Pattern Across Orchestration Frameworks

All three frameworks share a common governance posture:

| Aspect | LangGraph | CrewAI | AutoGen |
|--------|-----------|--------|---------|
| Governance depth | None (developer adds) | None | Minimal (sandbox) |
| Semantic state | App-defined dict | Conversational | Conversational |
| Domain policy | None | None | None |
| Provenance/trust | None | None | None |
| Audit/replay | Checkpoints (app-level) | Logs only | Logs only |
| Safety invariants | None structural | None | Docker sandbox |
| Model signal integration | None | None | None |

**Key insight:** These frameworks are not trying to solve governance. They
are solving orchestration. Governance is explicitly left to the developer
or to external systems. This is a valid architectural choice — but it means
every deployment must build its own governance stack or go without one.

---

## Category 2: Platform Agent SDKs

These are first-party SDKs from major AI providers. They integrate tightly
with their respective model APIs and offer some built-in safety controls,
primarily content guardrails and permission gating.

### OpenAI Agents SDK

**Architecture:** Lightweight Python SDK (evolved from Swarm prototype).
Agents are defined with instructions, tools, and handoff targets. The
Responses API provides the underlying model interaction with native tool
use, structured outputs, and multi-turn context.

**Key components:**
- **Agent definitions** — instructions + tools + handoffs (subagent delegation)
- **Guardrails** — input/output validators that run as separate LLM calls
  or rule-based checks before/after agent execution
- **Tracing** — Built-in trace collection for debugging and observability
- **Handoffs** — Typed agent-to-agent delegation with context transfer
- **Hosted tools** — Web search, file search, code interpreter as managed services

**Governance model:**
- Input guardrails can reject requests before agent execution
- Output guardrails can filter/modify responses after generation
- Tool use is permission-controlled via agent definition (agents can only
  use tools explicitly assigned to them)
- No semantic state awareness — governance is content-based (what the user
  said, what the model generated) not state-based (what cognitive mode the
  system is in)
- No domain-aware policy — all agents governed uniformly
- No provenance/shadow AI tracking
- Tracing provides observability but not governance replay
- No stricter-only invariants — guardrails can both block and allow

**OpenAI's governance white paper recommendations:**
OpenAI's agent safety guidance (2025) recommends: constraining action space,
requiring human approval for high-impact actions, legibility of agent
reasoning, automatic monitoring, attributability, and interruptibility.
Notably, these are *recommendations*, not built-in SDK features. The SDK
provides guardrails and tracing; the rest is developer responsibility.

**Sentinel comparison:**
OpenAI's guardrails are content filters (input/output validation). Sentinel's
governance is a multi-layered decision engine that considers semantic state,
domain policy, tool risk, provenance, and sovereign signals. OpenAI's
approach is simpler and more accessible. Sentinel's approach is deeper but
more complex. OpenAI's guardrails cannot answer "what governance regime is
the system in?" — they can only answer "does this input/output pass a check?"

### Google Agent Development Kit (ADK) / Vertex AI

**Architecture:** Agent builder platform with visual and code-based agent
construction. Supports multi-agent orchestration, tool connectors (API hub),
grounding (search, enterprise data), and deployment on Vertex AI.

**Key components:**
- **Agent definitions** — Declarative or code-based agent configuration
- **Tool connectors** — Pre-built connectors for Google services, APIs,
  databases via API Hub
- **Grounding** — Google Search grounding, enterprise data grounding
- **Orchestration** — Sequential, parallel, and loop agent patterns
- **Extensions** — Custom tool integrations
- **Evaluation** — Built-in eval framework for agent quality

**Governance model:**
- Google Cloud IAM for access control
- DLP (Data Loss Prevention) integration for content filtering
- Grounding citations for attribution
- No internal semantic governance model
- No domain-aware policy engine
- No provenance/shadow AI tracking
- Cloud-native audit logging via Cloud Audit Logs
- Safety settings on Gemini models (harassment, hate speech, etc.) —
  content-level, not semantic-state-level

**Sentinel comparison:**
Google ADK leverages Google Cloud's extensive infrastructure governance (IAM,
DLP, audit logs) but treats agent governance as an infrastructure concern,
not an architectural one. There is no semantic state model, no domain policy
translation, no bounded enrichments. The safety controls are content filters
and access controls, not cognitive-state-aware decision engines.

### AWS Bedrock Agents

**Architecture:** Managed agent service within AWS Bedrock. Agents are
configured with instructions, action groups (tool definitions), and
knowledge bases. Execution is fully managed by AWS.

**Key components:**
- **Action groups** — OpenAPI-defined tool interfaces with Lambda backends
- **Knowledge bases** — RAG integration with vector stores
- **Guardrails** — Content filtering, topic denial, PII redaction,
  word filters, contextual grounding checks
- **Agent collaboration** — Multi-agent orchestration with supervisor/worker
  patterns
- **Memory** — Session and cross-session memory retention

**Governance model:**
- **Guardrails for Bedrock** is the most structured governance offering in
  this category:
  - Content filters (hate, insults, sexual, violence, misconduct)
  - Denied topics (custom topic blocklists)
  - Word filters (exact match and pattern)
  - Sensitive information filters (PII detection + redaction)
  - Contextual grounding checks (hallucination detection against sources)
  - Guardrail versioning and deployment
- AWS CloudTrail for audit logging
- IAM for access control
- No semantic state model — guardrails are content-based
- No domain-aware policy beyond topic denial
- No provenance/shadow AI tracking for agent tools
- No bounded enrichments or confidence adjustments — guardrails are
  binary (block or allow)
- ApplyGuardrail API allows external use as a service

**Sentinel comparison:**
Bedrock Guardrails is the closest industry analogue to Sentinel's governance
layer — it is declarative, versioned, and has multiple filter types. However,
it operates at the content level (what was said/generated), not the semantic
state level (what cognitive regime the system is in). Bedrock cannot answer
"is the system in PROCESS_DRIFT?" or "does this action's risk match the
current domain posture?" It can answer "does this text contain PII?" and
"is this topic denied?"

The ApplyGuardrail API is notable — it moves toward governance-as-a-service,
which Sentinel does not yet offer externally.

### Anthropic Claude Agent SDK / Claude Code

**Architecture:** Lightweight agent loop SDK. The agent executes a
model-tool loop: model generates tool calls, SDK executes them, results
feed back to the model. Claude Code is the CLI/IDE agent built on this
pattern.

**Key components:**
- **Agent loop** — Automated model-call, tool-use, result cycle
- **Tool definitions** — JSON Schema tool definitions with model-native
  tool use
- **Permission modes** — User-configurable permission levels for tool
  execution (allow, ask, deny per tool category)
- **Hooks** — Shell commands that execute on events (pre/post tool call,
  notification) for custom governance injection
- **MCP (Model Context Protocol)** — Standardized protocol for tool
  server integration
- **Subagents** — Spawn isolated agent instances for parallel work

**Governance model:**
- Permission modes provide basic tool-level governance (allow/ask/deny)
- Hooks enable custom pre/post-execution checks (user-implemented)
- No built-in semantic state model
- No domain policy engine
- No provenance tracking
- No structured audit trail (conversation logs, not governance events)
- No confidence gating or safety contract
- System prompt includes behavioral guidelines (careful with destructive
  actions, confirm before shared-state operations)
- MCP servers are trusted — no shadow AI / provenance posture

**Sentinel comparison:**
Claude Agent SDK is deliberately minimal — it provides the agent loop and
lets the model's training (RLHF alignment) handle most safety. Permission
modes and hooks provide extensibility points but no built-in governance
engine. Sentinel is architecturally the opposite: governance is not an
extensibility point but the core decision engine.

### Common Pattern Across Platform SDKs

| Aspect | OpenAI | Google ADK | AWS Bedrock | Anthropic |
|--------|--------|------------|-------------|-----------|
| Governance depth | Guardrails (I/O) | Cloud IAM + DLP | Guardrails (content) | Permissions + hooks |
| Semantic state | None | None | None | None |
| Domain policy | None | None | Topic denial | None |
| Provenance/trust | None | None | None | None |
| Audit/replay | Tracing | Cloud Audit Logs | CloudTrail | Conversation logs |
| Safety invariants | None structural | None structural | Content filters | Permission modes |
| Model signal integration | None | None | None | None |

**Key insight:** Platform SDKs treat governance as content filtering
(guardrails), access control (IAM/permissions), and observability (tracing/
logs). None of them have a semantic state model. None reason about what
cognitive mode the system is in. None translate governance posture based
on domain context. This is the gap Sentinel occupies.

---

## Full Governance Capability Matrix

This matrix compares all frameworks across Sentinel's seven governance
dimensions. Ratings use a 4-point scale:

- **None** — Capability does not exist
- **Basic** — Minimal implementation (permissions, simple filters)
- **Moderate** — Structured implementation but limited scope
- **Deep** — Multi-layered, integrated into the runtime decision path

### Governance Depth

*Is governance structural or bolt-on? How many decision layers?*

| Framework | Rating | Notes |
|-----------|--------|-------|
| LangGraph | None | Developer adds via custom nodes |
| CrewAI | None | Prompt-based role constraints only |
| AutoGen | Basic | Docker sandbox for code execution |
| OpenAI Agents | Basic | Input/output guardrails (content filters) |
| Google ADK | Basic | Cloud IAM + DLP (infrastructure-level) |
| AWS Bedrock | Moderate | Multi-type content guardrails, versioned, API-accessible |
| Anthropic SDK | Basic | Permission modes + hooks (extensibility points) |
| **Sentinel** | **Deep** | **8 governance layers: semantic state, domain policy, shadow AI, confidence gate, safety contract, sovereign enrichments, pipeline guards, audit ledger** |

### Semantic State Awareness

*Does governance reason about what cognitive/semantic mode the system is in?*

| Framework | Rating | Notes |
|-----------|--------|-------|
| LangGraph | None | State is app-defined dicts, not semantic |
| CrewAI | None | State is conversational context |
| AutoGen | None | State is conversation history |
| OpenAI Agents | None | Content-based (what was said/generated) |
| Google ADK | None | No internal state model |
| AWS Bedrock | None | Content-based guardrails |
| Anthropic SDK | None | No state model |
| **Sentinel** | **Deep** | **JEPA composite (ontology + vritti), governance regimes (NORMAL/DRIFT/SHIFT/ANOMALY/UNKNOWN), sovereign state integration (S1-S4), residual signal detection** |

### Domain Policy Translation

*Can governance behavior vary by domain without code changes?*

| Framework | Rating | Notes |
|-----------|--------|-------|
| LangGraph | None | — |
| CrewAI | None | — |
| AutoGen | None | — |
| OpenAI Agents | None | — |
| Google ADK | None | — |
| AWS Bedrock | Basic | Topic denial lists per guardrail config |
| Anthropic SDK | None | — |
| **Sentinel** | **Deep** | **Declarative domain profiles (finance, devops, research), action coherence matrices per regime, tool-level permissions, vritti guards, threshold gates. Stricter-only invariant.** |

### Provenance / Trust Control

*Does the system track asset trustworthiness and detect shadow AI?*

| Framework | Rating | Notes |
|-----------|--------|-------|
| LangGraph | None | — |
| CrewAI | None | — |
| AutoGen | None | — |
| OpenAI Agents | None | Agent tool access is static |
| Google ADK | None | — |
| AWS Bedrock | None | — |
| Anthropic SDK | None | MCP servers are trusted |
| **Sentinel** | **Deep** | **5-state provenance model (APPROVED/UNVERIFIED/SHADOW/QUARANTINED/REVOKED), ShadowRegistry with pattern matching, 13 risk factors, 10 declarative policy rules, semantic mismatch detection, 9 graduated containment modes** |

### Audit / Replay Capability

*Can you forensically reconstruct why a governance decision was made?*

| Framework | Rating | Notes |
|-----------|--------|-------|
| LangGraph | Moderate | State checkpoints enable replay, but not governance-aware |
| CrewAI | None | Logs only |
| AutoGen | None | Conversation logs only |
| OpenAI Agents | Basic | Tracing for debugging, not governance forensics |
| Google ADK | Basic | Cloud Audit Logs (infrastructure events) |
| AWS Bedrock | Moderate | CloudTrail + guardrail trace, but no semantic replay |
| Anthropic SDK | None | Conversation logs |
| **Sentinel** | **Deep** | **Per-decision AuditEvent with JEPA regime, domain policy, shadow assessment, sovereign signals (S1-S4), confidence breakdown. Hash-chained append-only ledger. Deterministic replay verifier. Every governance layer contributes individually auditable data.** |

### Safety Invariants

*Are there structural guarantees that governance can only make things stricter?*

| Framework | Rating | Notes |
|-----------|--------|-------|
| LangGraph | None | — |
| CrewAI | None | — |
| AutoGen | Basic | Docker containment (execution-level) |
| OpenAI Agents | None | Guardrails can both block and allow |
| Google ADK | None | — |
| AWS Bedrock | Basic | Content filters are binary block/allow |
| Anthropic SDK | None | — |
| **Sentinel** | **Deep** | **Stricter-only invariant across all layers: domain can only restrict, shadow can only restrict, sovereign penalties are non-negative, JEPA override is stricter-only, aggregate sovereign penalty cap (0.20), fail-closed defaults throughout** |

### Model Signal Integration

*Does governance consume signals from the model's internal cognitive state?*

| Framework | Rating | Notes |
|-----------|--------|-------|
| LangGraph | None | — |
| CrewAI | None | — |
| AutoGen | None | — |
| OpenAI Agents | None | — |
| Google ADK | None | — |
| AWS Bedrock | None | — |
| Anthropic SDK | None | — |
| **Sentinel** | **Deep** | **S1: vritti/entropy adapters. S2: sovereign health/insight. S3: reasoning-kernel diagnostics. S4: guna anomaly/bhava/governor telemetry. Bridge-first architecture (no PyTorch in governance). Bounded effects with aggregate cap.** |

### Summary Scorecard

| Framework | Gov Depth | Semantic | Domain | Provenance | Audit | Invariants | Model Signals |
|-----------|-----------|----------|--------|------------|-------|------------|---------------|
| LangGraph | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| CrewAI | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AutoGen | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| OpenAI Agents | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| Google ADK | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| AWS Bedrock | 2 | 0 | 1 | 0 | 2 | 1 | 0 |
| Anthropic SDK | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Sentinel** | **3** | **3** | **3** | **3** | **3** | **3** | **3** |

*(0=None, 1=Basic, 2=Moderate, 3=Deep)*

**This matrix makes the differentiation stark.** Sentinel is the only
framework that scores above zero on semantic state awareness, domain
policy, provenance control, and model signal integration. These are not
incremental improvements — they are capabilities that no other framework
in this comparison attempts.

---

## Where Sentinel Genuinely Differentiates

The following are architectural differentiators that are not marketing
claims but structural realities in the codebase.

### 1. Governance Is State-Aware, Not Just Rule-Aware

Most agent governance answers: "Is this tool/action permitted?"

Sentinel answers: "Given the current semantic-cognitive state, the domain
context, the asset provenance, and the sovereign model signals — is this
action appropriate, and how confident are we?"

This is a fundamentally different question. It means governance behavior
changes based on the system's internal state, not just external rules.
A `file_write` action that is ALLOW in NORMAL regime becomes DEFER in
PROCESS_DRIFT and DENY in DUAL_ANOMALY — without any change to
permissions or rules.

**No other framework in this comparison has this capability.**

### 2. Multi-Layer Governance With Clean Separation

Sentinel separates governance concerns into distinct, composable layers:

```
  Semantic state (JEPA)   → "what state are we in?"
  Domain policy           → "what does that mean in this domain?"
  Shadow AI control       → "is this asset trustworthy?"
  Sovereign enrichments   → "what does the model's internal state suggest?"
  Enforcement             → "what do we do about it?"
  Audit                   → "what happened and why?"
```

Each layer can only restrict, never relax. Each layer is independently
auditable. Each layer has its own fail-closed default.

Most frameworks collapse all governance into a single filter (guardrails)
or delegate it entirely to the developer. Sentinel's layered approach
means that adding a new governance concern (e.g., shadow AI) does not
require modifying existing governance logic — it composes additively.

### 3. Declarative Domain Policy Translation

Sentinel translates semantic governance into domain-specific behavior via
declarative profiles:

- Finance: destructive always blocked, drift blocks all writes,
  misperception blocks everything
- DevOps: reads/writes OK in normal, destructive sandboxed, deploy
  blocked during drift
- Research: read-heavy, writes draft-only, no destructive ever

This is not prompt engineering. It is a structured policy evaluation
pipeline with matrix lookups, coherence rules, tool permissions, threshold
gates, and vritti guards — all composing with stricter-only semantics.

**No other framework has domain-aware governance translation.**

### 4. Shadow AI / Provenance Control

Sentinel tracks whether AI assets (models, tools, plugins) are sanctioned:

- 5-state provenance model (APPROVED through REVOKED)
- 13 individually auditable risk factors
- 10 declarative policy rules
- Semantic mismatch detection (approved asset behaving outside boundary)
- 9 graduated containment modes

This is not just "is this tool in an allowlist?" It is "is this tool
behaving consistently with what it was approved to do?"

**No other framework in this comparison tracks asset provenance.**

### 5. Sovereign Model Signal Integration (S1-S4)

Sentinel is the only framework that integrates signals from the model's
own internal cognitive state into governance decisions:

- Vritti (cognitive mode) affects governance posture
- Entropy drives bounded confidence penalties
- Guna anomalies (collapse, oscillation) trigger additional caution
- Reasoning-kernel diagnostics (mauna/silence) add governance signals
- All effects are bounded, capped, and fail-safe

This is architecturally unique. Other frameworks treat the model as an
opaque function (input in, output out). Sentinel treats the model as a
system whose internal state is governance-relevant.

### 6. Audit as Governance Infrastructure

Sentinel's audit trail is not logging — it is governance infrastructure:

- Every decision records the full governance context: JEPA regime, domain
  policy result, shadow assessment, sovereign signals, confidence breakdown
- Hash-chained append-only ledger provides tamper evidence
- Deterministic replay verifier can reconstruct decisions
- Each governance layer contributes individually auditable data
- Audit fields distinguish real vs fallback signal sources

This is the foundation for the "why did it do that?" question that
enterprise deployments must answer.

### 7. Structural Safety Invariants

Sentinel enforces structural guarantees that cannot be violated by
configuration or policy:

- **Stricter-only:** Every governance layer can only make decisions more
  restrictive, never less. Domain cannot relax JEPA. Shadow cannot relax
  domain. Sovereign penalties are non-negative.
- **Fail-closed:** Every resolver, adapter, and policy evaluator defaults
  to the most restrictive safe option on failure
- **Bounded effects:** Sovereign confidence penalties have per-adapter
  caps and an aggregate cap (0.20). No single signal source can dominate.
- **Bridge boundary:** Governance never directly imports PyTorch model
  internals. The bridge enforces separation.

These are not policy choices — they are architectural invariants enforced
by code structure.

---

## Where Sentinel Does NOT Yet Differentiate

Honest assessment. These are areas where competitors have capabilities
Sentinel lacks, or where Sentinel's architecture has not yet matured into
a complete product.

### 1. Workflow Orchestration

**Competitors ahead:** LangGraph, CrewAI, AutoGen, OpenAI Agents

Sentinel has no multi-agent orchestration framework. It governs individual
authorization decisions, but it does not compose multi-step workflows,
manage agent-to-agent handoffs, or orchestrate parallel agent execution.

This is not necessarily a gap — Sentinel could be the governance layer
inside an orchestration framework. But as a standalone product, it does
not solve the "how do I build a multi-agent workflow?" problem.

### 2. Managed Execution / Hosted Runtime

**Competitors ahead:** AWS Bedrock, Google ADK, OpenAI Agents

Sentinel runs as a library inside the application. It does not provide:
- Managed agent hosting
- Serverless execution
- Auto-scaling
- Deployment management

Platform SDKs offer "bring your agent definition, we run it." Sentinel
offers "bring your runtime, we govern it."

### 3. Content-Level Guardrails

**Competitor ahead:** AWS Bedrock Guardrails

Sentinel's governance is semantic-state-based, not content-based. It does
not currently offer:
- PII detection / redaction
- Hate speech / toxicity filtering
- Topic denial lists
- Contextual grounding checks (hallucination detection)

These are content-level safety features that Bedrock Guardrails handles
well. Sentinel's governance answers a different question ("is the action
appropriate given the system state?") but does not address content safety
directly. These are complementary, not competitive — but a complete
product may need both.

### 4. Execution Sandboxing

**Competitor ahead:** AutoGen (Docker), OpenAI (Code Interpreter)

Sentinel governs whether an action should be authorized. It does not
sandbox the execution itself. If an authorized action is malicious or
buggy, Sentinel has no containment at the execution level.

AutoGen's Docker sandboxing and OpenAI's hosted Code Interpreter provide
genuine execution isolation that Sentinel does not.

### 5. Developer Ecosystem / Community

**Competitors ahead:** LangChain/LangGraph, OpenAI, Anthropic

Sentinel has no public SDK, no community, no marketplace, no tutorials,
no third-party integrations. The industry leaders have massive developer
ecosystems. This is a product maturity gap, not an architectural one, but
it matters enormously for adoption.

---

## Agentic Runtime Primitives: Framework-Layer Gaps

The sections above cover high-level positioning (orchestration,
hosting, content guardrails, sandboxing, ecosystem) and governance
product gaps. This section covers a narrower, more concrete axis: the
**runtime primitives** that leading agentic frameworks expose at the
agent-loop level. These are the features a developer reaches for when
building on top of an agentic runtime — independent of governance.

Grounding: this is a comparison against `AGENTIC_ARCHITECTURE.md` §
"Inference CG Metadata ↔ MCP Gateway" and the `AgenticLLMWrapper`
runtime host (`agentic/agentic_framework/agent.py`), not the
governance engine. The governance posture is covered elsewhere in
this document.

What Sentinel's agentic runtime currently exposes:

- `AgenticLLMWrapper.run(user_input) -> AgentResult` — single-turn
  synchronous host with goal decomposition, text-level reflective
  generation, coherence tracking, `SafetyGate`, and dispatcher-backed
  action execution.
- `CGToolDispatcher` + `SafeMCPGateway` — CG-metadata-enriched
  MCP tool dispatch with per-call governance.
- `build_cg_mcp_agent(...)` — thin composition factory with a
  default `action_type → tool` mapping (`search`/`compute`/`validate`).
- `inference_mistral.py --cg` — opt-in CLI for real-inference runtime.

What leading frameworks expose at this layer that Sentinel does not:

### R1. Streaming / Incremental Output

**Competitors ahead:** OpenAI Agents SDK, Anthropic Agent SDK,
LangGraph, Pydantic AI, LlamaIndex Workflows

`AgenticLLMWrapper.run(...)` is **synchronous and returns a completed
`AgentResult`**. There is no token-streaming, no partial-response
yield, no incremental tool-call emission. Every leading framework
exposes a streaming contract (async generator, SSE, or event bus)
because agent UX and latency-sensitive workflows require it.

**Why it matters:** Without streaming, the agentic runtime cannot
power interactive UIs, cannot surface reasoning progress mid-turn,
and cannot be cancelled by a client mid-generation.

### R2. Async / Cancellation Contract

**Competitors ahead:** OpenAI Agents SDK, LangGraph, AutoGen, Pydantic AI

`run(...)` is sync and blocking. Internally it shells out to
`asyncio.new_event_loop()` to call `call_tool_simple`
(`agent.py:506-509`). There is no async `run()` method, no
`CancellationToken` equivalent, no cooperative cancellation on tool
calls in progress.

**Why it matters:** Modern agent hosts run many agents concurrently,
need to cancel runaway loops, and need to integrate with async
frameworks (FastAPI, aiohttp). A sync-only contract forces thread
pools and defeats the purpose of async tool execution.

### R3. Persistent Checkpointing / Resumable Sessions

**Competitors ahead:** LangGraph (first-class), CrewAI (memory),
AutoGen (message log), OpenAI (session state)

Sentinel has an in-process `MemoryStore` and `session_id`, but no
durable checkpoint of agent state across process boundaries. LangGraph
makes this the centerpiece of its design — every node emits a
checkpoint, runs can resume from any checkpoint, and time-travel
debugging is free.

**Why it matters:** Long-running agents need crash recovery. Human
approval workflows need the agent to pause and resume later (hours
or days). Debugging needs replay from a known state.

### R4. Human-in-the-Loop Interrupts (Structured)

**Competitors ahead:** LangGraph (`interrupt()` / `Command`),
OpenAI Agents SDK (handoffs + approvals)

Sentinel's `SafetyGate` can **block** an action, and governance can
return a `DEFER` decision, but there is **no runtime mechanism** for
the agent to pause, surface a question/approval to a caller, and
resume execution once the caller responds. The
`ApprovalManager` under `governance_patterns/` is an in-memory
prototype (already noted above), not a runtime interrupt primitive.

**Why it matters:** Governance DEFER without a structured interrupt
primitive at the runtime layer leaves a capability gap between the
governance decision and the user experience. LangGraph's `interrupt()`
is the reference implementation here.

### R5. Multi-Agent Orchestration / Handoffs

**Competitors ahead:** CrewAI (crews, roles, delegation),
AutoGen (GroupChat), LangGraph (subgraphs),
OpenAI Agents SDK (handoffs)

Sentinel is **single-agent only**. `AgenticLLMWrapper` wraps one
`LLMClient`. There is no concept of agent-to-agent handoff, no
parallel agent execution, no role-based crews, no supervisor/worker
split. The multi-agent dimension is entirely absent.

**Why it matters:** Most non-trivial agentic products are multi-agent
(planner + executor, researcher + writer + critic, router + domain
specialists). A single-agent runtime is a substrate, not a product.
This is already flagged in "Where Sentinel Does NOT Yet Differentiate"
but is restated here as a runtime-primitive gap because it shapes
what API shape downstream builders need.

### R6. Structured Outputs / Schema-Enforced Responses

**Competitors ahead:** OpenAI Agents SDK (Pydantic output_type),
Pydantic AI, Anthropic tool-use JSON schemas, Semantic Kernel

Sentinel's `AgentResult` exposes `response: str` (plus pipeline
metrics). There is no mechanism to declare a response schema and
have the runtime coerce / validate the LLM output to it. Callers
hand-parse free-form text.

**Why it matters:** Production agent applications need typed, parsed
outputs. Every competitor has either Pydantic-based output types,
JSON-schema enforcement, or function-call outputs as first-class.
Sentinel puts this entirely on the caller.

### R7. Parallel Tool Calls

**Competitors ahead:** OpenAI Agents SDK, Anthropic Agent SDK,
LangGraph (fan-out)

`_execute_actions` iterates over actions sequentially; each eligible
action is dispatched in turn. There is no `asyncio.gather`-style
parallel dispatch of independent tool calls within a single turn.

**Why it matters:** When a goal decomposes into N independent lookups
(search + compute + validate), sequential dispatch is an N× latency
penalty vs parallel. Modern LLMs already emit parallel tool-call
batches; the runtime should honor them.

### R8. MCP Tool **Discovery** (not just governance over MCP)

**Competitors ahead:** Anthropic Claude Agent SDK, Claude Code,
Cursor, VS Code MCP clients

Sentinel owns `SafeMCPGateway` — governance **over** MCP tool calls.
But the gateway's mock tool set is **hardcoded**
(`create_mock_mcp_gateway` registers `search`/`compute`/`validate`).
There is no MCP **client** that discovers tools from arbitrary MCP
servers over stdio/SSE and registers their schemas dynamically.

**Why it matters:** The MCP ecosystem's value is that any
MCP-speaking server (file system, GitHub, Slack, custom domain tools)
can plug in. Without discovery, Sentinel gets the governance benefits
of MCP without the ecosystem benefits. This is a concrete, bounded
piece of work that would multiply the runtime's reach.

### R9. Cost / Token-Budget Tracking and Enforcement

**Competitors ahead:** OpenAI Agents SDK (usage tracking),
LangGraph (budget checkpoints), Semantic Kernel (telemetry)

There is no per-session token counter, no cost estimator, no
runtime-level budget enforcement that halts an agent when it burns
past a threshold. Revisions are capped by count
(`max_revisions=3`), not by spend.

**Why it matters:** Enterprise deployments need predictable cost
guardrails. Reflective loops can spiral; without a budget, the
runtime is exposed to pathological cost on degenerate inputs.

### R10. Evaluation Harness

**Competitors ahead:** Google ADK (built-in eval framework),
LangChain LangSmith, OpenAI Evals

Sentinel has rich unit/integration tests for the runtime seam, but
no opinionated **eval harness** for running an agent across a task
dataset, scoring outputs, comparing revisions, and tracking
regressions over time. Framework-level eval is what competitors
productize.

**Why it matters:** Agentic systems regress silently on prompt / model
/ policy changes. A framework without an eval story forces every
adopter to build their own. Google ADK ships this in-box as a
differentiator.

### R11. Observability / Tracing Surfaces

**Competitors ahead:** OpenAI Agents SDK (built-in tracing),
LangSmith, AutoGen (conversation logs)

Sentinel emits governance audit records at the MCP boundary, and
`AgentResult` carries coherence and safety-contract diagnostics,
but there is no **agent-loop tracing** primitive: no per-turn span
tree of (decompose → generate → critic → revise → action) with
durations, inputs, outputs, and linkage to governance audit.

**Why it matters:** When an agentic loop misbehaves, operators need
a tree view of the turn, not log lines. LangSmith exists because
this is a product gap in every framework that doesn't ship tracing.

### Summary

Sentinel's **governance runtime** is architecturally distinctive.
Sentinel's **agentic runtime** (the layer above governance, below
the model) is **a thin single-agent wrapper** whose primitives
trail the industry on streaming, async, checkpointing, interrupts,
multi-agent, structured outputs, parallel tools, MCP discovery,
budgets, eval, and tracing.

These are not architectural gaps — nothing in the governance design
prevents closing them. They are **framework-completeness gaps**.
If the strategy is Position A ("governance runtime library inside
someone else's agent framework"), most of R1-R11 can be deferred —
the host framework supplies them. If the strategy is Position B
("full governed agent platform"), closing R1, R2, R4, R6, R7, R8
is table stakes, and R3, R5, R9, R10, R11 are competitive parity.

---

## Missing Product Layers

These are the product capabilities Sentinel needs to become a complete
enterprise governance product. The architecture is strong; the
productization is incomplete.

### P1. External Governance API (Priority: Critical)

**What's missing:** Sentinel governs its own internal runtime. It cannot
yet govern external systems.

**What's needed:**
- `POST /authorize` — external authorization endpoint with stable schema
- `POST /simulate` — what-if analysis without execution
- `POST /replay` — replay a historical decision against new policy
- SDK / client library for integration
- OpenAPI specification

**Why it matters:** Without an external API, Sentinel is an internal
architecture, not reusable governance infrastructure. The ApplyGuardrail
API from AWS Bedrock is the benchmark here — governance as a callable
service.

### P2. Policy Control Plane (Priority: Critical)

**What's missing:** Domain profiles, shadow rules, and risk thresholds
are defined in Python source code. Policy changes require code deploys.

**What's needed:**
- Versioned policy bundles (separate from code)
- Tenant / org / environment scoping
- Policy diffing and impact analysis
- Policy approval workflow (who changed what, when, why)
- Hot-reload without service restart
- Validation that policy changes preserve stricter-only invariants

**Why it matters:** Enterprise customers need non-developer policy owners
to manage governance posture. "Edit Python and redeploy" is not a product
control plane.

### P3. Resumable Approval / Execution Plane (Priority: High)

**What's missing:** When governance returns DEFER, the system signals that
human confirmation is needed. But there is no structured workflow for how
that confirmation happens, is tracked, and resumes execution.

**What's needed:**
- Approval inbox / queue
- Multi-step approval chains
- SLA / expiry / escalation rules
- Resumable execution after approval
- Audit linkage: request, approval decision, resumed action

**Why it matters:** DEFER without resumable execution is structurally
incomplete. The `ApprovalManager` in `governance_patterns/` is an
in-memory prototype, not a production approval plane.

### P4. Operator Dashboard / UX (Priority: High)

**What's missing:** Sentinel has rich internal semantics but no operator
surfaces.

**What's needed:**
- Governance decision dashboard (real-time + historical)
- Policy decision traces (visual)
- Sovereign/JEPA/session state summaries
- Diff views for policy replay
- Alerting (anomalous governance patterns)
- Approval UI
- Incident investigation workflow

**Why it matters:** Governance systems fail not because the backend is
weak, but because operators cannot understand what happened fast enough.
Internal richness without external visibility is wasted.

### P5. Signal Contracts / Caller Responsibilities (Priority: High)

**What's missing:** The architecture is capable of richer behavior when
upstream signals are present, but there is no explicit contract defining
what signals are required, what is optional, and what fallback means.

**What's needed:**
- Signal contract specification (required vs optional vs enrichment)
- Signal quality / confidence metadata
- Caller responsibility documentation
- Fallback behavior specification per signal
- Runtime validation of signal contracts

**Why it matters:** Without signal contracts, the system is powerful but
uneven. Some deployments get full S1-S4 governance; others get S1-S2 only
because they don't supply projection metadata. The system handles this
safely (fail-neutral), but operators may not realize they're running in
degraded mode.

### P6. Deployment / Tenancy / Admin Lifecycle (Priority: Medium)

**What's missing:** Standard enterprise product infrastructure.

**What's needed:**
- Deployment model (library, sidecar, service)
- Tenant isolation
- Secrets / config management
- Policy bundle promotion (dev → staging → prod)
- Version compatibility / migration
- Admin roles / RBAC
- Runbooks / incident controls

### P7. Operational Safety Surfaces (Priority: Medium)

**What's missing:** Runtime operational controls for emergencies and
degraded operation.

**What's needed:**
- Emergency stop / kill switch
- Degraded mode controls (disable S3/S4, disable domain policy, etc.)
- Live policy override tools
- Operator-visible current governance state
- "Safe default behavior" documentation
- Interruptibility guarantees

**Why it matters:** OpenAI's governance guidance emphasizes
interruptibility, monitoring, and legibility. Sentinel is converging on
these internally but needs explicit operator-facing controls.

---

## Strategic Positioning

### The Honest Assessment

Sentinel is **architecturally differentiated** in ways that matter:
governance depth, semantic state awareness, domain policy, provenance
control, sovereign signal integration, and audit infrastructure. These
are not incremental features — they are structural capabilities that no
other framework in this comparison attempts.

Sentinel is **not yet a complete product.** The missing layers — external
API, policy control plane, resumable approvals, operator UX, signal
contracts, deployment lifecycle — are the difference between "impressive
architecture" and "deployable governance product."

### The Strategic Question

The comparison reveals two possible market positions:

**Position A: Governance Runtime Library**
Sentinel is the governance decision engine inside someone else's agent
framework. LangGraph orchestrates, CrewAI coordinates, Sentinel governs.
This requires: external governance API, SDK, and clear integration
contracts.

**Position B: Full Governed Agent Platform**
Sentinel is a complete agent platform with built-in orchestration AND
governance. This requires: everything in Position A, plus orchestration,
managed execution, deployment infrastructure, and developer ecosystem.

Position A is more achievable. Position B is more defensible. The
architecture supports either — but the product investments differ
significantly.

### What Competitors Cannot Easily Replicate

If a competitor wanted to match Sentinel's governance capabilities, they
would need to:

1. Design a semantic state model (JEPA-equivalent composite signals)
2. Build domain-aware policy translation (not just guardrails)
3. Implement provenance / shadow AI tracking
4. Integrate model internal state signals (bridge architecture)
5. Enforce stricter-only invariants across all layers
6. Build forensic audit infrastructure (not just logging)

This is not a weekend project. It requires architectural commitment that
is hard to retrofit into an orchestration-first or guardrails-first
framework. The governance model must be in the decision path, not around
it.

**This is Sentinel's moat: governance is structural, not decorative.**

---

## Appendix: Framework Summary Table

| Framework | Primary Focus | Governance Approach | Sentinel Relationship |
|-----------|--------------|--------------------|-----------------------|
| LangGraph | Workflow orchestration | None (developer adds) | Complementary (could govern LangGraph agents) |
| CrewAI | Multi-agent roles | None (prompt-based) | Complementary |
| AutoGen | Multi-agent conversation | Minimal (Docker sandbox) | Complementary |
| OpenAI Agents | Model-native tool use | Content guardrails | Different layer (content vs semantic) |
| Google ADK | Platform agent building | Cloud IAM + DLP | Different layer (infrastructure vs runtime) |
| AWS Bedrock | Managed agents | Content guardrails (strongest) | Complementary (content + semantic) |
| Anthropic SDK | Minimal agent loop | Permission modes + hooks | Different philosophy (minimal vs maximal governance) |
| **Sentinel** | **Governed agent decisions** | **Multi-layer semantic governance** | **Unique position** |
