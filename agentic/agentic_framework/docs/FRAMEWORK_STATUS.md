# Framework Status

Current status of the Agentic Framework as of version 1.8.0.

This page separates what is fully implemented and tested from what
is partially proved or intentionally deferred. It mirrors the
internal architecture truth in plain language.

---

## Fully implemented and tested

These capabilities are regression-tested (1500+ tests) and committed.

| Capability | What it means | Test evidence |
|-----------|--------------|---------------|
| **Goal decomposition** | Extracts structured intent and action items from user input | Core test suite |
| **Reflective generation** | LLM self-critiques and optionally revises its own output | Core test suite |
| **Coherence tracking** | Tracks conversation-level coherence across turns | Core test suite |
| **Memory store** | Persistent context management external to the LLM | Core test suite |
| **Safety gate (turn-level)** | Blocks actions when coherence metrics fall below thresholds | `test_agent.py` |
| **MCP gateway (per-tool)** | Risk classification, confidence gating, audit logging per tool call | `test_mcp_gateway.py` |
| **CG signal enrichment** | Entropy and coherence signals from model internal state enrich tool-call governance | `test_cg_tool_demo.py` |
| **Dispatcher/factory composition** | `CGToolDispatcher` + `build_cg_mcp_agent()` compose the full runtime | Unit + integration tests |
| **Streaming events (R1)** | 17 structured event types covering the full agent lifecycle | 28 tests |
| **Async + cancellation (R2)** | Async streaming and cancellation tokens that stop execution at checkpoints | 31 tests |
| **Human approval interrupts (R4)** | Pre-action approval gates with configurable policy and callback | 33 tests |
| **Structured outputs (R6)** | Schema-enforced output with dataclass, dict, and Pydantic validation | 44 tests |
| **MCP tool discovery (R8)** | Read-only introspection and filtered search over registered tools | 38 tests |
| **Usage and budget tracking (R9)** | Token/cost accounting with hard budget caps; budget exceedance is a terminal event | 37 tests |
| **Tracing (R11)** | In-memory event recording and trace summary derivation | 26 tests |
| **Cross-feature hardening** | Approval+budget ordering, cancellation+approval interaction, denied-approval traces, accounting mode correctness | 23 tests |

### Action loop ordering (pinned by tests)

The ordering within the action loop is fixed and tested:

1. Cancellation check
2. Budget check
3. Approval gate
4. ACTION_STARTED → execute → ACTION_COMPLETED

Budget is checked before approvals. Cancellation is checked before
budget. This ordering is not configurable — it is part of the
runtime contract.

---

## Partially proved

| Capability | Current state |
|-----------|--------------|
| **Real local model inference** (`MistralCGAdapter` via `--cg`) | Wiring and factory composition are proved in repo. Real local inference requires torch + checkpoint + GPU environment and is **operator-validated** at first run, not repo-validated. |
| **Async event loop** | `run_stream_async()` works but some test-harness edge cases around `asyncio.get_event_loop()` in Python 3.11+ are known. Not a runtime bug — a test infrastructure issue. |

---

## Intentionally deferred

These are known gaps that are not planned for the current release.

| Capability | Why it is deferred |
|-----------|-------------------|
| **Multi-agent orchestration** | Out of scope. The framework governs a single agent's execution path. Agent-to-agent handoffs, orchestration graphs, and multi-agent coordination are not implemented. |
| **External telemetry backend** | Tracing is in-memory and local. OpenTelemetry integration, cloud export, and persistent audit storage are not built. |
| **Broad runtime adoption** | The single runnable entry point is `inference_mistral.py`. Other subsystems (voice, web, API servers) have not been migrated to this runtime. |
| **`AuthorizationRequest`-side enrichment** | The enrichment seam exists in code, but no production caller simultaneously holds a CG adapter and constructs an `AuthorizationRequest`. Deferred until an honest caller exists. |
| **`sovereign_projection_metadata` on MCP path** | The MCP path has 32D state, not a full `SovereignProjectionResult`. Attaching projection metadata would require a producer that does not exist on this path. Honest absence, not a gap. |
| **RAG / vector store integration** | Not built in. Bring your own retrieval pipeline. |
| **Hosted deployment / scaling** | This is a library, not a managed service. |

---

## Version history

| Version | Summary |
|---------|---------|
| 1.8.0 | R1–R11 runtime primitives complete. Streaming, cancellation, approvals, structured outputs, MCP discovery, usage/budget tracking, tracing, cross-feature hardening. |

---

## See also

- [What Is Agentic Framework](WHAT_IS_AGENTIC_FRAMEWORK.md) —
  overview
- [Why Agentic Is Different](WHY_AGENTIC_IS_DIFFERENT.md) —
  differentiator doc
- [First Governed Agent](FIRST_GOVERNED_AGENT.md) — build guide
