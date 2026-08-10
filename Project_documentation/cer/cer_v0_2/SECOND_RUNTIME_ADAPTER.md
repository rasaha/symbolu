# Second Runtime Adapter — OpenAI Agents SDK (Deliverable 4)

`cer_v0_2/producers/openai_agents_adapter.py`. Grounded in the implemented adapter running **real `openai-agents` 0.18.2**.

Labels: `FACT` (measured) · `RECOMMENDATION`.

## Empirical status
`FACT`. **Not `BLOCKED_NO_SECOND_RUNTIME`.** `openai-agents==0.18.2` is installed and imports (`from agents import Agent, Runner`). The adapter drives the **real `Runner` event loop**; a deterministic model stub emits a real `ResponseFunctionToolCall`; the runtime **genuinely creates a `ToolCallItem`** (the pending action object), which the adapter reads. No live model API is used; the graph/loop/tool-dispatch are the SDK's own.

## Integration (real pre-tool boundary)
`FACT`:
- The governed tools `k8s_scale` / `k8s_rollout` are real `@function_tool`s whose bodies are **shadow no-ops** returning `PENDING_GOVERNANCE` (they never actuate).
- `_StubModel.get_response` (implementing the SDK `Model` interface) returns a `ResponseFunctionToolCall` for the requested profile's tool, then a final message to end the loop.
- `Runner.run(...)` executes the real agent loop; the adapter reads the resulting `ToolCallItem` from `res.new_items` and normalizes it to CER.
- A hand-authored runtime object would NOT count; here the SDK Runner parses the model output and constructs the tool-call item itself.

## Adapter obligations (all met)
`FACT`:
- Preserves the real principal (from the `EnvelopeContext`, established outside the model).
- Normalizes the intercepted tool call → CER; provenance (`runtime=openai-agents`, model, planner=`openai-agents.runner`) kept **outside** the action identity.
- Rejects missing identity-bearing fields / unsupported extensions via `envelope.validate_cer` (fail closed).
- Prevents direct governed-tool bypass: the shadow tool never actuates; execution eligibility comes only from the control plane.
- Returns the governed result to the runtime and preserves the observation/reflection loop (shared `cer_v0_1.observation`).
- No OpenAI-Agents-specific logic in CER, ActionGate, or ACP (verified by the ownership test).

## Measured result
`FACT`. For the same actuation, the OpenAI Agents adapter's digest **equals** the Ugence and LangGraph digests, for **both** profiles: scale `07f7a6aa…`, rollout `72ddae26…`. Provenance is `openai-agents` (distinct from the others). Deterministic across reruns.
