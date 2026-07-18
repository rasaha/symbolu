# Universal Runtime Audit (Deliverable 5)

Can every existing agent framework emit an Execution Proposal (per `EXECUTION_PROPOSAL_SCHEMA.md`)? For each: yes/no, and the adapter required.

Labels: `FACT` (Ugence/repo) · `EXTERNAL KNOWLEDGE` (competitor framework architecture, general knowledge to a Jan-2026 cutoff — directional, not verified against current releases) · `INTERPRETATION`.

**Baseline `FACT`:** all these frameworks "wire a model to a tool-calling loop" (`ACTIONGATE_VC_BRIEF.md:21–22`). The schema describes the *tool call* (action), not the framework, so the question is never "can it express an action" (it can) but "how much adapter work to normalize it, and can the interception point actually enforce."

---

## 1. Per-framework audit

| Framework | Emit a proposal? | Interception point (EXTERNAL KNOWLEDGE) | Adapter must translate | Enforceable? | Difficulty |
|---|---|---|---|---|---|
| **Ugence Agent Runtime** | **Yes** | native — already designed to emit `ExecutionProposal` (`FACT`: `../agent_runtime_v2/`) | near-nothing; map risk signals → `evidence` | Yes (native) | **Trivial** |
| **OpenAI Agents SDK** | **Yes** | tool/function-call boundary; MCP-capable | function call → `action`; handoff → new `principal`; prefer MCP path | Yes if adapter brokers creds | **Low** |
| **LangGraph** | **Yes** | tool-executing node wrapper; checkpointer for pause | node tool-call → `action`; graph state → `state_binding`; interrupt on HOLD/ESCALATE | Yes (strong pause/resume) | **Low–Moderate** |
| **CrewAI** | **Yes** | task tool-execution step | acting crew-member → `principal`; task call → `action`; hierarchical crews → multiple principals | Yes | **Moderate** |
| **Google ADK** | **Yes** | tool boundary; MCP-capable | prefer MCP path; workflow state → `state_binding` | Yes | **Low–Moderate** |
| **AutoGen** | **Yes (coarse)** | executor agent's tool/code execution | executor → `principal`; **code exec → `operation:EXECUTE`, `reversibility:UNKNOWN`**; needs dry-run to classify effects | Yes, but coarse granularity | **Moderate–High** |
| **Semantic Kernel** | **Yes** | "function/plugin" invocation boundary; planner-produced steps; MCP-capable | SK function call → `action`; plugin permissions → `credential_scope`; planner step → one proposal per step | Yes | **Low–Moderate** |
| **Claude Code** | **Yes (already partially separated)** | tool-call boundary is **already gated by the harness permission system** (allow/deny/ask) + hooks | Bash/Edit/Read tool call → `action`; permission decision maps to ActionGate verdict; hooks are the natural adapter seam | Yes — the seam already exists | **Low** |
| **Amazon Bedrock Agents** | **Yes** | action-group invocation (Lambda/API) + return-control hook | action-group call → `action`; IAM role → `credential_scope` (**must narrow standing role to the exact action**) | Constrained to AWS hooks | **High** |

---

## 2. Claude Code is a natural-experiment data point (worth calling out)

**EXTERNAL KNOWLEDGE / INTERPRETATION.** Claude Code is a live agent runtime in which reasoning and execution-governance are *already architecturally separated*: the model reasons and *proposes* tool calls (Bash, Edit, Read, …); a separate harness — permission modes (allow/ask/deny), hooks that can intercept and block, and an approval UX — *governs* whether each call runs. The model does not authorize its own tool calls; the harness does.

**Why this matters for the verdict:** it is an existence proof, in a widely-used product, of exactly the split this milestone proposes — *the runtime generates intelligence; a separate layer governs execution.* It also validates two of the falsification corrections in the master doc:
- **F1 (return path):** Claude Code's tool results return to the model to continue reasoning — the loop, not a one-way pipeline.
- **F2 (risk-tiering):** Claude Code already tiers — read-only calls are often auto-allowed while consequential calls prompt — demonstrating that per-action governance is only practical when risk-proportional.

`INTERPRETATION`: Claude Code is not evidence that Ugence's *specific* Control Plane is adopted (it is not), but it is strong evidence that the *architecture pattern* (propose → external governance → execute → observe) is real, shippable, and already the design of a mature agent runtime. The Execution Proposal is the generalization of what Claude Code's tool-permission boundary already does informally.

---

## 3. The two hard cases (and why they're adapter costs, not schema failures)

**FACT / EXTERNAL KNOWLEDGE.**
1. **Free-form code executors (AutoGen `UserProxyAgent`).** The "action" is arbitrary code whose effects aren't known pre-execution, so `operation`/`targets` can't be classified precisely. **Handling:** `operation:EXECUTE`, `reversibility:UNKNOWN`, and a Control-Plane `SIMULATE_AND_RETRY`/dry-run to classify effects before authorizing. The action is still *expressible*; it's just coarse.
2. **Closed/managed runtimes (Bedrock Agents).** Execution happens inside AWS; interception is limited to AWS-provided hooks (return-control, Lambda boundary). **Handling:** adapt at the action-group boundary; narrow the standing IAM role to the exact action (the gap ActionGate closes — `FACT`: `ACTIONGATE_VC_BRIEF.md:49`). Harder, but the proposal is still producible.

**INTERPRETATION.** Neither is a failure of the schema or the architecture — both are *interception-point* constraints of the runtime, not couplings in the Control Plane. Every framework *can* emit a proposal; the variance is entirely in adapter engineering effort and in how cleanly the runtime exposes its tool boundary for enforcement.

---

## 4. The universal shortcut and the verdict

**FACT + EXTERNAL KNOWLEDGE.** The Model Context Protocol (MCP) is a converging tool-call standard that OpenAI Agents SDK, Google ADK, Semantic Kernel, Claude Code, and others increasingly speak, and the repo already prototypes an MCP→ActionGate adapter (`action_gateway_mcp`). **One MCP adapter governs every MCP-speaking runtime.** This collapses most of the table into a single, high-leverage integration.

**Audit verdict:** **YES — every listed framework can emit an Execution Proposal.** Difficulty ranges from trivial (Ugence, Claude Code, MCP-native) to high (Bedrock, AutoGen), driven entirely by the runtime's interception point and action granularity — never by an inability to express the action. The one durable caveat (`FACT`, carried from `../ai_control_plane_v3/`): this is demonstrated for the repo's own reader and, architecturally, permitted for all; it has **not** been empirically run against a live third-party framework. The universality test (`../ai_control_plane_v3/07_...` §4) — same action from three runtimes → identical verdict — remains the experiment that would convert "can, by construction" into "does, demonstrated."
