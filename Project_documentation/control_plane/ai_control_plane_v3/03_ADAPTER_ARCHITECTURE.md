# Part 3 — Adapter Architecture

Assuming an external runtime exists, design (do not implement) the adapters that translate between each runtime and the AI Control Plane. The adapter is where all runtime-specificity is confined, so the Control Plane stays runtime-independent.

Labels: `FACT` (repo evidence) · `INTERPRETATION` · `RECOMMENDATION` · `EXTERNAL KNOWLEDGE` (competitor framework internals, general knowledge as of a Jan-2026 cutoff, not repo-verified).

---

## 1. The adapter is a bidirectional translator

```
   RUNTIME (any)                    ADAPTER                       AI CONTROL PLANE
   ─────────────                    ───────                       ────────────────
   emits a tool call   ─────▶  Normalization  ─────▶  canonical ExecutionProposal
   (framework-native)          (framework→canonical)   (Part 1 contract)
                                                              │
                                                              ▼
                                                   ActionGate → ACP → Compose
                                                              │
   executes / handles  ◀─────  Denormalization ◀─────  Decision (verdict + token
   (framework-native)          (verdict→framework)      or DENY/HOLD/ESCALATE)
```

**FACT — this seam already exists in ActionGate.** ActionGate is explicitly built to sit at "the layer between *'the model emitted a tool call'* and *'that exact call committed'*," and reduces "every action entering an ActionGate-supported adapter … to a canonical action envelope" (`ACTIONGATE_VC_BRIEF.md:26–92`). The repo already ships multiple such adapters: a generic gateway, an **MCP adapter** (`action_gateway_mcp`), a **Kubernetes adapter** (`action_gateway_k8s`), and an isolated variant. **The adapter pattern is not hypothetical — it is the shipped integration model.**

**INTERPRETATION.** Because ActionGate/ACP already consume a canonical action (Part 2), each runtime adapter has exactly two jobs: (1) turn the runtime's native tool-call into the canonical `ExecutionProposal`; (2) turn the Control Plane's verdict back into a framework-native continue/deny/pause. Nothing runtime-specific leaks past the adapter.

---

## 2. What every adapter must translate (the common checklist)

Derived from the Part-1 contract and the input-contract audits. Every adapter, regardless of runtime, must map:

| Canonical field | Adapter must source it from the runtime's… |
|---|---|
| `principal` (agent_identity) | the runtime's agent/session identity (and sign it) |
| `requested_action.tool` | the native tool/function name the runtime is about to call |
| `requested_action.operation` | classify the tool-call into the frozen operation taxonomy |
| `requested_action.target_resource[]` | the resource(s) the call touches (often inside args) |
| `requested_action.arguments` | the native call arguments, re-serialized to the canonical Action Profile (typed-string numerics, JCS) |
| `credential_scope` | the permission the call needs (mapped from the tool) |
| `state_binding` | the world-state hash + freshness the decision is made against |
| `reversibility` | classify the operation's consequence class |
| `risk_evidence` (opt) | the runtime's own risk/uncertainty score (scrutiny-only) |
| `expected_outcome` (opt) | the runtime's dry-run/simulation output, if any |

And on the return path, map each Control-Plane outcome to a framework-native behavior (`ALLOW`+token → execute; `DENY`/`HOLD`/`ESCALATE`/`REQUEST_MORE_EVIDENCE`/`SIMULATE_AND_RETRY` → the framework's pause/deny/human-in-the-loop primitive).

**FACT — the hard part is `operation` + `arguments` canonicalization.** ActionGate requires args in a strict Action Profile (JCS, typed-string numerics, no bare numbers; `jcs.py:105–108`) and `operation` from a fixed 10-op taxonomy (`schema.py:34–38`). The adapter's real work is this normalization; everything else is field-copying.

---

## 3. Per-runtime adapter specifications (design only)

For each runtime: what it emits, and what its adapter must translate. `EXTERNAL KNOWLEDGE` for competitor internals; `FACT` for Ugence.

### 3.1 Ugence Runtime (Agent Runtime V2)
- **Emits (FACT):** already designed to emit an `ExecutionProposal` (see `../agent_runtime_v2/01_RUNTIME_RESPONSIBILITY_MATRIX.md` §4). Its `mcp_gateway` already does risk classification and tool dispatch.
- **Adapter work:** near-zero — the runtime is being designed *to* this contract. Map `ToolRiskClassifier` output → `risk_evidence`; map its tool call → canonical envelope.
- **Difficulty:** trivial (native).

### 3.2 MCP-based runtimes (universal path)
- **Emits (FACT):** MCP tool calls (`tool_name`, `arguments`) over the Model Context Protocol. The repo already has an `action_gateway_mcp` adapter.
- **Adapter work:** intercept the MCP `tools/call`, map tool→operation, args→canonical arguments, MCP server→`credential_scope`. **This one adapter covers every runtime that speaks MCP** (OpenAI Agents SDK, Google ADK, and others increasingly support MCP — EXTERNAL KNOWLEDGE).
- **Difficulty:** moderate; **highest leverage** — one adapter, many runtimes.
- **FACT caveat:** the existing MCP adapter is "bypassable without network + credential isolation" (`action_gateway_mcp` README) — for real enforcement the adapter must own credential brokering, not just observe the call.

### 3.3 LangGraph
- **Emits (EXTERNAL KNOWLEDGE):** graph nodes invoking tools; state passed through a typed graph; tool calls happen inside node functions.
- **Adapter work:** wrap tool-executing nodes so the tool call is intercepted before execution; translate node tool-call → canonical proposal; on `HOLD`/`ESCALATE`, use LangGraph's interrupt/checkpoint mechanism to pause the graph. Map graph state's world-view → `state_binding`.
- **Difficulty:** moderate — LangGraph's explicit graph + checkpointer make pause/resume natural.

### 3.4 OpenAI Agents SDK
- **Emits (EXTERNAL KNOWLEDGE):** tool/function calls and agent handoffs; increasingly MCP-capable.
- **Adapter work:** hook the tool-invocation boundary; each function call → canonical proposal; a handoff between agents → a new `principal` (Part 8). Prefer the MCP path where available (§3.2).
- **Difficulty:** low–moderate.

### 3.5 CrewAI
- **Emits (EXTERNAL KNOWLEDGE):** role-based agents ("crews") executing tasks with tools; sequential/hierarchical process.
- **Adapter work:** intercept the tool-execution step of a task; map the acting crew-member → `principal`; task tool-call → canonical proposal. Hierarchical crews map to multiple principals (Part 8).
- **Difficulty:** moderate.

### 3.6 Microsoft AutoGen
- **Emits (EXTERNAL KNOWLEDGE):** conversational multi-agent messages; tool calls emerge from agent turns; a `UserProxyAgent` often executes code/tools.
- **Adapter work:** intercept the executor agent's tool/code execution; the executing agent → `principal`; the tool/code action → canonical proposal. Code execution is high-risk → map to `EXECUTE`/`DESTRUCTIVE` operation classes.
- **Difficulty:** moderate–high — free-form code execution is harder to reduce to a fixed operation taxonomy than a named tool call.

### 3.7 Google ADK
- **Emits (EXTERNAL KNOWLEDGE):** agents + tools + workflows; MCP-capable.
- **Adapter work:** prefer the MCP path (§3.2); otherwise hook the tool boundary; map workflow state → `state_binding`.
- **Difficulty:** low–moderate.

### 3.8 Amazon Bedrock Agents
- **Emits (EXTERNAL KNOWLEDGE):** managed agents invoking "action groups" (Lambda/API schemas) and knowledge-base retrieval; runs inside AWS.
- **Adapter work:** intercept the action-group invocation (e.g., via the Lambda boundary or a return-control hook); action-group call → canonical proposal; IAM role → `credential_scope` (note: Bedrock already has IAM-scoped identity — the adapter must *narrow* it to the exact action, since IAM grants a standing role, which is precisely the gap ActionGate closes, `ACTIONGATE_VC_BRIEF.md:49`).
- **Difficulty:** high — managed/closed execution; interception points are constrained to AWS-provided hooks.

---

## 4. Adapter difficulty summary

| Runtime | Interception point | Canonicalization difficulty | Pause/resume support | Overall |
|---|---|---|---|---|
| Ugence Runtime | native | trivial | native | **Trivial** |
| MCP (any) | MCP `tools/call` | moderate | protocol-level | **Moderate — highest leverage** |
| LangGraph | tool-node wrapper | moderate | strong (checkpointer) | **Moderate** |
| OpenAI Agents SDK | tool-call hook / MCP | low | good | **Low–Moderate** |
| Google ADK | tool hook / MCP | low | good | **Low–Moderate** |
| CrewAI | task tool-step | moderate | basic | **Moderate** |
| AutoGen | executor agent hook | high (code exec) | basic | **Moderate–High** |
| Bedrock Agents | action-group/Lambda hook | high | managed-only | **High** |

**INTERPRETATION.** Two structural facts make the adapter architecture credible: (1) **MCP is a universal shortcut** — a single MCP adapter (which the repo already prototypes) governs any MCP-speaking runtime, and the industry is converging on MCP (EXTERNAL KNOWLEDGE); (2) **the only genuinely hard adapters are closed/managed runtimes (Bedrock) and free-form code executors (AutoGen)**, where the interception point is constrained — not because of any Control-Plane coupling, but because the runtime doesn't expose a clean tool boundary.

**RECOMMENDATION.** Build in this order: Ugence (native) → MCP (universal, one adapter, many runtimes) → LangGraph (strong pause/resume, popular) → then the rest opportunistically. Do **not** build eight bespoke adapters first; the MCP adapter is the 80/20.

---

## 5. What the adapter must NOT do

**RECOMMENDATION — the discipline that keeps the Control Plane runtime-independent:**
- The adapter must **not** pass the runtime's prompt, reasoning trace, memory, or model internals into the proposal (Part 1 MUST-NOT-EXIST). If a field can't be mapped to an *action* property, it doesn't cross.
- The adapter must **not** make authorization decisions — it translates and forwards; ActionGate decides.
- The adapter must **not** cache or reuse tokens across actions (tokens are single-use; Part 8).
- The adapter **must** own credential brokering for real enforcement — a translate-only adapter that leaves the runtime holding durable credentials is monitoring, not governance (`ACTIONGATE_VC_BRIEF.md:39–41`).
