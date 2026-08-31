# Agent Runtime — Provider Interface

A **provider** executes a runtime-requested operation **after** all required runtime
and external governance checks have completed. The runtime treats the provider as
opaque: it hands over a neutral `ToolInvocation` and consumes a neutral `ToolResult`.

Machine-readable form:
[`../artifacts/agent_runtime_provider_contract.json`](../artifacts/agent_runtime_provider_contract.json).

## Contract

```python
class Provider(Protocol):
    provider_id: str
    version: str
    def execute(self, invocation: ToolInvocation) -> ToolResult: ...
```

### `ToolInvocation`
`provider_id`, `operation`, `arguments`, `correlation_id`, `idempotency_key`,
`timeout`, `metadata`.

The runtime supplies an `idempotency_key` of `"{instance_id}:{task_id}"` so a provider
that supports idempotency can deduplicate a retried invocation.

### `ToolResult`
`provider_id`, `operation`, `ok`, `output`, `error`, `failure_category`, `metadata`.

- `ok=True` → the runtime marks the task `COMPLETED` and propagates `output` opaquely.
- `ok=False` → an **expected** failure reported by value; the runtime classifies it.
- Raising `ProviderExecutionError(retriable=...)` signals a failure the runtime may
  retry (subject to `RetryPolicy`). Any other exception is wrapped, never surfaced raw.

## Neutrality

The runtime embeds **no** vendor-specific behavior — no OpenAI, Anthropic, GitHub,
cloud, or database specifics. Concrete providers live in separate packages or existing
integration locations. The runtime binds only: provider id, provider version, operation
type, arguments, execution/correlation context, idempotency reference (where supported),
timeout, result, and failure classification.

## Registration

Providers are registered **explicitly** — never implicitly at import time:

```python
rt.config.provider_registry.register(MyProvider())
# or
register_provider(rt, MyProvider())
```

Registering a duplicate `provider_id` is a `RuntimeConfigurationError`. Referencing an
unregistered provider yields a `PROVIDER_NOT_FOUND` failure (fail closed), not a crash.

## No new ProviderKind

This release introduces no new provider kind. The provider boundary is a single
neutral protocol; specialization happens in concrete implementations outside the core.

## Neutral usage on `ToolResult` (CM-TA1)

A provider MAY attach an **opaque** usage mapping to its result at
`ToolResult.metadata["token_usage"]` (`PROVIDER_USAGE_METADATA_KEY`). The runtime
forwards this mapping **verbatim** into the neutral attempt telemetry
(`ProviderAttempt.neutral_usage`) and **never interprets** provider-specific token
field names. Attaching usage is entirely optional; an absent or non-mapping value is
treated as unknown (`None`), never fabricated as empty. Normalizing usage into typed
token fields belongs to an integration adapter, not the runtime. See
[`AGENT_RUNTIME_ATTEMPT_TELEMETRY.md`](AGENT_RUNTIME_ATTEMPT_TELEMETRY.md).
