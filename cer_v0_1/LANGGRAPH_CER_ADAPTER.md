# LangGraph CER Adapter (Deliverable 5)

`cer_v0_1/producers/langgraph_adapter.py`. Grounded in the implemented adapter running **real LangGraph 1.2.9 / langchain-core 1.4.9** (installed and exercised in this environment).

Labels: `FACT` · `RECOMMENDATION`.

## Empirical status
`FACT`. **NOT `BLOCKED_NO_LANGGRAPH_RUNTIME`.** `langgraph` and `langchain_core` are installed and import cleanly; the adapter builds and runs a real `StateGraph` with a real `ToolNode`, and the cross-runtime digest equivalence was measured on actual graph execution.

## Integration (the real execution boundary)
`FACT` (milestone §4 preferred path):
- A real `StateGraph` with nodes `planner → intercept → (END | tools)`; the `k8s_scale` `@tool` is bound in a real `ToolNode`.
- The `planner` node emits a genuine `AIMessage` carrying a `k8s_scale` tool call (deterministically, so no API key is needed — but the message types, tool binding, and graph are all real langgraph objects).
- The `intercept` node reads the **pending tool call from graph state before `ToolNode` executes** and normalizes it to CER V0.1. In this shadow harness the real tool is never executed (governed eligibility is hypothetical, no cluster); a live system with a minted token would route `RESUME → tools`.
- Normalization draws the tool-call-carried facts (namespace/deployment/replicas) from the **real intercepted call** and the authority/state/policy from the runtime's shared request context.

## No control-plane coupling
`FACT`. All LangGraph-specific code is confined to this adapter. ActionGate and ACP contain no `langgraph`/`runtime_type` branch (verified by the ownership test in `tests/`). The adapter stamps **LangGraph provenance** (`runtime=langgraph`, `model=gpt-4o-mini`, `planner=langgraph.stategraph`) and a **deliberately different objective** ("please bring web up to 3 pods").

## Governed loop
`FACT`. When a control-plane `submit_cer` callback is provided (Stage 4), the `intercept` node routes `RESUME`/`REPLAN`/`STOP` on the composed result — the observation-return/governed loop. Without a callback it runs as a pure producer (returns the intercepted CER).

## Proven result
`FACT` (Stage-3 run): LangGraph's CER digest = `3cef1b0f767e2e3e…` — **identical** to the native Ugence digest for the same actuation. Deterministic across reruns.
