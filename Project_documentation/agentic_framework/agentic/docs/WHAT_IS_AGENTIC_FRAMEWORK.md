# What Is the Agentic Framework?

The Agentic Framework is a code-first Python framework for building
**governed** agentic applications on top of any LLM. It wraps LLM
adapters (OpenAI, Anthropic, Mistral, Gemini, or your own) with a
structured execution path that includes goal decomposition, reflective
generation, safety gating, tool governance, human-in-the-loop
approvals, budget enforcement, and full event tracing — so that every
action an agent takes is observable, auditable, and controllable.

---

## Who is it for?

- **Backend / AI engineers** building agent-powered features that need
  more than "call the LLM and hope for the best."
- **Teams that need governance** — turn-level safety gates, per-tool
  risk classification, approval workflows, and budget caps.
- **Developers who want streaming observability** — structured runtime
  events, in-memory traces, and usage accounting out of the box.

---

## What can you build with it?

- A conversational agent with automatic goal decomposition and
  self-revising responses.
- A tool-calling agent whose actions are gated by safety contracts
  and per-tool risk classification.
- An approval-aware workflow where high-risk actions require human
  sign-off before execution.
- A budget-constrained agent that stops before exceeding token or
  cost limits.
- A structured-output pipeline that validates LLM responses against
  dataclass or Pydantic schemas.

---

## What makes it different from a generic agent SDK?

Most agent frameworks give you tool calling and a prompt loop.
This framework adds a **governed execution path**:

1. **Two layers of safety gating.** `SafetyGate` evaluates
   turn-level coherence before any action runs. `SafeMCPGateway`
   evaluates each individual tool call against risk classification,
   confidence thresholds, and (optionally) symbolic signal
   enrichment.
2. **Runtime primitives as execution controls.** Streaming events,
   cancellation tokens, approval gates, budget policies, and tracing
   are not bolted-on middleware — they are wired into the action
   loop with a pinned ordering: cancellation check → budget check →
   approval gate → execute → trace.
3. **Signal enrichment on runtime decisions.** When a CG-capable
   adapter is used, the framework enriches each tool call with
   entropy and coherence signals derived from the model's internal
   state — governance decisions that use more than just the text
   output.

---

## What it is not (yet)

- **Not a multi-agent platform.** There is no built-in agent-to-agent
  handoff, orchestration graph, or agent registry. It governs a
  single agent's execution path.
- **Not broadly production-adopted.** The runtime is proved by 1500+
  regression tests. The single runnable entry point today is the
  `inference_mistral.py` CLI. Other subsystems (voice, web, etc.)
  have not yet been migrated.
- **Not an external telemetry system.** Tracing is in-memory and
  local. There is no built-in OpenTelemetry or cloud export.
- **Not a managed service.** It is a library you embed in your
  Python application, not a hosted platform.

---

## See also

- [README](../README.md) — entry point with quickstart code
- [Why Agentic Is Different](WHY_AGENTIC_IS_DIFFERENT.md) —
  differentiator breakdown
- [Quickstart](QUICKSTART.md) — setup, first code, API orientation
- [First Governed Agent](FIRST_GOVERNED_AGENT.md) — build guide
- [Framework Status](FRAMEWORK_STATUS.md) — what is proved, what
  is not
