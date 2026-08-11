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

- The **default** governance hook fails closed: with no adapter configured, consequential
  transitions are BLOCKed (`GOVERNANCE_NOT_CONFIGURED`). An always-CLEAR hook is never a
  default (see `AGENT_RUNTIME_GOVERNANCE_INTEGRATION.md`).
- A CLEAR result executes **only** when bound to the exact proposal (fingerprint +
  non-empty reference, not expired); otherwise the runtime fails closed and the provider
  is not called.
- A missing or unrecognized governance disposition resolves to `STOP`, never `CLEAR`.
- A corrupt/tampered checkpoint is rejected on recovery.
- An unknown provider yields a classified `PROVIDER_NOT_FOUND` failure, not execution.
- Concurrency is bounded; unbounded concurrency is a configuration error.

## No enforcement, no execution authority

The runtime does not enforce policy and mints no execution authority. It coordinates;
permission is always determined by the external governance boundary.

## Attempt telemetry (CM-TA1)

The neutral attempt observer receives identities, a neutral status, and a provider's
**opaque** usage mapping only — never arguments, prompts, credentials, or provider
response payloads. The runtime interprets no provider-specific token field. Telemetry is
observation only: it can never change the provider action, and a raising observer is
swallowed so it can never break execution or alter a governed transition.

## Attempt-observation failure surfacing (CM-TA1 F2)

When an attempt observer raises, the optional error reporter receives a structured
`AttemptObservationFailure` carrying safe identity and the exception **type name** only —
never the exception message/args or any provider payload — because arbitrary exception
payloads may embed provider data. The reporter cannot influence provider execution, and a
raising reporter is contained so it can never mask the provider result. Default (no reporter)
preserves the prior silent fail-open.
