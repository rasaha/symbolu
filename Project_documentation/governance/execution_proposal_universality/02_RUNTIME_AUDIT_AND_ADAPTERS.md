# Deliverables 2 & 3 — Per-Runtime Audit + Adapter Analysis

For each runtime: a study of its actual action architecture, a support classification, and the smallest adapter. The milestone says *do not assume* — so each entry names the runtime's real interception point and its hard cases.

Labels: `FACT` (Ugence/repo) · `EXTERNAL KNOWLEDGE` (competitor architecture, general knowledge to a Jan-2026 cutoff — **directional, verify against current releases**) · `INTERPRETATION`.

Classification scale: **SUPPORTED** (native) · **SUPPORTED WITH ADAPTER** · **PARTIAL** · **NOT SUPPORTED**.
Every adapter has the same anatomy: **intercept → normalize → emit → map-verdict-back**. The variance is (a) *where* the interception point is and (b) *how opaque* the runtime's action is.

---

## 0. The generic adapter anatomy

```
   RUNTIME native action  ──▶  ADAPTER  ──▶  Canonical Execution Proposal  ──▶  Control Plane
   (function call / graph      1. intercept at the ACTUATION boundary            verdict + token
    node / shell / code /      2. normalize → {tool, operation, targets, args}      │
    action group)             3. assert principal, credential_scope, reversibility   ▼
                              4. attach optional state_binding + evidence       map verdict → runtime's
                              5. exclude provenance from the ID hash            pause/deny/HITL primitive
```

**INTERPRETATION.** The adapter's difficulty is governed almost entirely by two questions: *Does the runtime expose a pre-commit interception point?* and *Is the action structured or opaque?* Structured + pre-commit hook = trivial adapter. Opaque (free-form code/shell) or post-commit-only (managed) = hard.

---

## 1. Ugence Agent Runtime — **SUPPORTED (native)**
- **FACT.** Designed to emit an `ExecutionProposal` (`../agent_runtime_v2/`); `mcp_gateway` already does tool dispatch + risk classification.
- **Adapter:** none. Map `ToolRiskClassifier` → `evidence`, tool call → `action`.
- **Hard cases:** none.

## 2. OpenAI Agents SDK — **SUPPORTED WITH ADAPTER**
- **EXTERNAL KNOWLEDGE.** Agents with typed **function tools**, agent **handoffs**, guardrails, sessions; increasingly **MCP**-capable. Tool calls are structured function invocations with typed arguments.
- **Interception:** the tool-execution lifecycle (before a function tool runs) or the MCP `tools/call` boundary.
- **Adapter:** structured function call → `action{tool=function, operation=classified, targets/args=params}`; handoff → new `principal`; prefer the MCP path (one adapter, §11). **Difficulty: low.**
- **Hard cases:** none structural — function calls are already close to the canonical action.

## 3. LangGraph — **SUPPORTED WITH ADAPTER**
- **EXTERNAL KNOWLEDGE.** Explicit stateful **graph** (nodes/edges), a shared typed **state** object, **ToolNode** for tool execution, a **checkpointer** enabling persistence and **interrupts**.
- **Interception:** wrap the ToolNode / use `interrupt` before a tool executes. Graph state can populate `state_binding`.
- **Adapter:** node tool-call → `action`; graph state → `state_binding`; on HOLD/ESCALATE use the interrupt+checkpoint to pause. **Difficulty: low–moderate.** LangGraph's checkpointer makes pause/resume the cleanest of any framework.
- **Hard cases:** none structural; a node may bundle multiple tool calls (adapter emits one proposal per call).

## 4. CrewAI — **SUPPORTED WITH ADAPTER**
- **EXTERNAL KNOWLEDGE.** Role-based **crews** of agents, **tasks**, sequential/**hierarchical** process, tools attached to agents/tasks.
- **Interception:** the tool-execution step of a task (tool callback).
- **Adapter:** acting crew-member → `principal`; task tool-call → `action`; hierarchical manager → multiple principals. **Difficulty: moderate** — interception hooks are less granular than LangGraph's.
- **Hard cases:** none structural.

## 5. Google ADK — **SUPPORTED WITH ADAPTER**
- **EXTERNAL KNOWLEDGE.** Agents + tools + **workflow agents** (sequential/parallel/loop), **callbacks** (e.g., `before_tool_callback`), **MCP** support.
- **Interception:** `before_tool_callback` is a native pre-commit hook; or the MCP path.
- **Adapter:** tool call → `action`; workflow state → `state_binding`; callback returns the verdict-mapped decision. **Difficulty: low–moderate.** The callback is a clean seam.
- **Hard cases:** none structural.

## 6. AutoGen — **PARTIAL**
- **EXTERNAL KNOWLEDGE.** Conversational multi-agent; agents exchange messages; two action modes: **structured function/tool calls** and **arbitrary code execution** (`UserProxyAgent`/code executors running Python/shell).
- **Interception:** for tool calls, the tool-invocation boundary; for code, the code-executor boundary.
- **Classification split:**
  - *Structured tool calls* → **SUPPORTED WITH ADAPTER** (maps cleanly).
  - *Arbitrary code execution* → **the FF2 hard case**: the action is opaque until run; it cannot be canonicalized at the message/plan level. The adapter must intercept at the **actuation layer** — the actual OS/API calls the code makes (syscall/library shim), not the code string — or the deployment must restrict AutoGen to structured tools.
- **Adapter:** tool path = normalize function call; code path = a sandbox/syscall interceptor emitting one proposal per concrete API call, with `operation:EXECUTE`, `reversibility:UNKNOWN`, and `SIMULATE_AND_RETRY` to classify. **Difficulty: moderate (tools) / high (code).**
- **Verdict:** PARTIAL — fully governable for tool-based agents; requires lower-boundary interception for code executors.

## 7. Claude Code — **SUPPORTED WITH ADAPTER** (native seam; one opaque-action caveat)
- **EXTERNAL KNOWLEDGE / observable design.** A coding agent where the model **proposes** tool calls (Read, Edit, Write, Grep, Glob, **Bash**, WebFetch, MCP tools) and a **harness governs** them via a **permission system** (allow/ask/deny), **permission modes**, and **hooks** (PreToolUse/PostToolUse). This is already a propose→govern→execute→observe loop.
- **Interception:** the **PreToolUse hook / permission layer** is a *native pre-commit interception point* — arguably the closest thing to an Execution-Proposal seam shipping in a mature runtime today.
- **Adapter:** a PreToolUse hook emits the proposal; the permission decision maps to/from the ActionGate verdict. Structured tools (Read/Edit/MCP) normalize cleanly.
- **Hard case (FF2):** `Bash("<arbitrary shell>")` is opaque like AutoGen code — the adapter must parse the command (lossy/ambiguous) or intercept at the OS boundary. So Claude Code is *structurally split* like AutoGen, but its **native hook system makes the interception point free** and most of its tools are structured.
- **INTERPRETATION.** Claude Code is the strongest real-world existence proof of the architecture (a live runtime that already separates propose from govern) *and* a live demonstration of FF2 (Bash opacity). **Difficulty: low** for structured tools; the Bash caveat is the only wrinkle.

## 8. Semantic Kernel — **SUPPORTED WITH ADAPTER**
- **EXTERNAL KNOWLEDGE.** A **kernel** orchestrating **plugins** (native/prompt functions), **planners** that compose plugin calls, **function-calling**, and **function-invocation filters** (middleware around every function call).
- **Interception:** the **function-invocation filter** is a native, clean pre-commit middleware seam.
- **Adapter:** plugin/function call → `action`; plugin permissions → `credential_scope`; planner step → one proposal per plugin call; the filter maps the verdict. **Difficulty: low.** SK's filter middleware is purpose-built for this.
- **Hard cases:** none structural (functions are typed).

## 9. Amazon Bedrock Agents — **PARTIAL** (SUPPORTED WITH ADAPTER only via return-control)
- **EXTERNAL KNOWLEDGE.** Managed agents on AWS; **action groups** (backed by Lambda or an OpenAPI/function schema), knowledge bases; orchestration is service-managed and **executes inside AWS**. A **"return control"** option hands the action back to the caller instead of invoking the Lambda.
- **Interception:**
  - *With return control* → a genuine pre-commit proposal seam. → **SUPPORTED WITH ADAPTER.**
  - *Without return control* → the Lambda executes internally; only post-hoc traces exist. → **NOT SUPPORTED for pre-commit governance** (observe-after only). This is FF3.
- **Adapter:** at the return-control boundary, action-group invocation → `action`; the AWS IAM role → `credential_scope` (**must narrow the standing role to the exact action** — the gap ActionGate closes, `FACT`: `ACTIONGATE_VC_BRIEF.md:49`). **Difficulty: high** — closed, AWS-hook-constrained.
- **Verdict:** PARTIAL — governable pre-commit only if the deployment uses return-control; otherwise governance is post-hoc, which is not what the architecture promises.

---

## 10. Summary table

| Runtime | Classification | Interception point | Opaque-action risk | Adapter difficulty |
|---|---|---|---|---|
| Ugence Agent Runtime | **SUPPORTED (native)** | native | none | Trivial |
| OpenAI Agents SDK | SUPPORTED WITH ADAPTER | tool lifecycle / MCP | none | Low |
| LangGraph | SUPPORTED WITH ADAPTER | ToolNode / interrupt | none | Low–Moderate |
| CrewAI | SUPPORTED WITH ADAPTER | task tool step | none | Moderate |
| Google ADK | SUPPORTED WITH ADAPTER | before_tool_callback / MCP | none | Low–Moderate |
| AutoGen | **PARTIAL** | tool boundary / code executor | **high (code exec)** | Moderate / High |
| Claude Code | SUPPORTED WITH ADAPTER | PreToolUse hook (native) | medium (`Bash` opacity) | Low |
| Semantic Kernel | SUPPORTED WITH ADAPTER | function-invocation filter | none | Low |
| Amazon Bedrock Agents | **PARTIAL** | return-control (or none) | n/a | High |

**Result: 1 native, 5 supported-with-adapter, 2 partial (AutoGen code-exec, Bedrock without return-control), 0 flatly unsupported.**

---

## 11. The two structural findings (deliverable 2/3 conclusion)

**INTERPRETATION.**
1. **MCP is the universal shortcut.** Five of these runtimes (OpenAI, ADK, Claude Code, Semantic Kernel, and any MCP server) increasingly speak MCP; the repo already prototypes an MCP→ActionGate adapter (`action_gateway_mcp`). One MCP adapter collapses most of the table. Build it first.
2. **The only true blockers are opacity and closure, not coupling.** AutoGen-code and Bedrock-without-return-control are the two PARTIALs, and both fail for the *same* reason: no clean *pre-commit, structured* interception point — the action is either opaque (code) or executed-internally (managed). Neither is a coupling in the Control Plane; both are properties of the runtime's execution model. Where a runtime exposes a pre-commit hook and a structured (or interceptable) action, the adapter is small and the proposal is equivalent.

**FACT caveat.** All competitor entries are EXTERNAL KNOWLEDGE to a Jan-2026 cutoff and must be re-verified against current releases before external use; interception mechanisms (hooks, filters, return-control) evolve. The *architecture-level* conclusion — structured+pre-commit → trivial adapter; opaque/managed → hard — is stable regardless of specific API names.
