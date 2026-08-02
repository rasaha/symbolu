# Agent Runtime — Security & Side-Effect Posture

## No import-time side effects

`import ugence_agent_runtime` (and constructing `AgentRuntimeConfig` / `AgentRuntime`)
performs **none** of the following:

- connect to a database;
- make an HTTP request or open a socket;
- load credentials or read secret environment variables;
- initialize an LLM client;
- start threads;
- start a scheduler;
- execute recovery;
- register global providers outside explicit configuration;
- invoke governance;
- modify environment variables.

This is verified in a fresh subprocess by `tests/test_import_boundaries.py`
(`test_import_has_no_external_side_effects`), which blocks `socket.socket` and asserts
the active thread count is unchanged across import.

## No credentials in the core

The core carries no credentials. `ExecutionContext` and `ToolInvocation` are neutral
descriptions; provider credentials belong to concrete provider implementations outside
this package. `AgentRuntimeConfig` rejects credential-bearing fields by construction —
it holds only injected dependencies and neutral policies.

## Observability minimization

Runtime events describe coordination facts only. By default they do **not** carry:

- credentials;
- raw prompts;
- secret tool arguments;
- private customer evidence;
- full provider responses.

Provider `output` is stored on the task instance for the caller but is **not** emitted
into the event stream. Governance reason codes are recorded; governance evidence is not.

## Fail-closed defaults

- A missing or unrecognized governance disposition resolves to `STOP`, never `CLEAR`.
- A corrupt/tampered checkpoint is rejected on recovery.
- An unknown provider yields a classified `PROVIDER_NOT_FOUND` failure, not execution.
- Concurrency is bounded; unbounded concurrency is a configuration error.

## No enforcement, no execution authority

The runtime does not enforce policy and mints no execution authority. It coordinates;
permission is always determined by the external governance boundary.
