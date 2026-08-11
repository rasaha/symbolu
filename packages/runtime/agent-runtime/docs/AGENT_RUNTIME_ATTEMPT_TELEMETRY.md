# Provider-Attempt Telemetry (CM-TA1)

> Agent Runtime records **each execution attempt** and enforces budgets. It does not
> measure how much context was removed (that is Context Minimization) or reconcile what
> the API reported consuming (that is a provider adapter). These quantities are related
> but not interchangeable.

## Why

The retry loop invokes `provider.execute(...)` one or more times per task. Each
invocation is one attempt that may have consumed provider tokens — **including a
failed, timed-out, or exception attempt**. Before this seam the runtime kept only a
final attempt *count* (`TaskInstance.attempts`) and discarded the earlier failed
attempts. A token-accounting audit needs every attempt.

## The seam

`AgentRuntimeConfig.attempt_observer` is an optional `AttemptObserver`:

```python
class AttemptObserver(Protocol):
    def on_attempt(self, attempt: ProviderAttempt) -> None: ...
```

It is notified **once per actual `provider.execute` invocation**, in invocation order,
with the runtime-authoritative `attempt_number` (1 for the first, incremented per
retry). Retried and failed attempts are recorded **distinctly** — never collapsed into
the final attempt.

`ProviderAttempt` is neutral and immutable:

| field | meaning |
| ----- | ------- |
| `provider_id`, `operation` | which provider/operation |
| `workflow_id`, `instance_id`, `task_id`, `correlation_id` | identity/attribution |
| `attempt_number` | runtime-authoritative; per-retry |
| `status` | `SUCCEEDED` / `FAILED` / `TIMEOUT` / `EXCEPTION` |
| `ok`, `provider_invoked` | outcome flags |
| `neutral_usage` | the provider's **opaque** usage mapping, forwarded verbatim, or `None` |
| `failure_category` | the runtime's neutral classification string (never provider-specific) |

It carries **no** arguments, prompts, credentials, or provider response payloads.

## Neutral usage — forwarded, never interpreted

A provider MAY attach an opaque mapping to its result:

```python
ToolResult(..., metadata={PROVIDER_USAGE_METADATA_KEY: {"prompt_tokens": 2337, ...}})
```

The runtime forwards that mapping verbatim as `ProviderAttempt.neutral_usage` and
**never parses it** — provider-specific token field names stay provider-specific.
Normalizing it into typed token fields (`ProviderTokenUsage`) is the job of an
integration adapter (`context-minimization-token-accounting-runtime`), not the runtime.
An absent or non-mapping value becomes `None` (unknown, never fabricated as empty).

## What never produces an attempt

The observer fires only from inside the execution loop, which runs **after** governance
CLEAR and the exact-action check. Therefore **no** attempt is produced for:

- a governance **HOLD / BLOCK / ESCALATE** (the provider is never invoked);
- an **exact-action** clearance or integrity rejection (fails closed before invocation);
- a **provider-not-found** (nothing to invoke).

This preserves the accounting rule that a call the provider never received incurs no
usage record.

## Boundaries

- The runtime imports **no** provider SDK and interprets **no** provider token field.
- Telemetry is observation only: it can never change the provider action, and a raising
  observer is swallowed so it can never break execution.
- Deterministic: the seam adds no wall-clock read and no random id — attempt numbering
  comes from the existing deterministic retry loop.

## Surfacing observation failures (F2)

An `AttemptObserver` that raises is **fail-open** for provider execution: the provider is
never re-invoked, its result is never erased, and retry behavior is unchanged. But the loss
is not silent when `AgentRuntimeConfig.attempt_observer_error_reporter` (an
`AttemptObservationErrorReporter`) is configured — the runtime emits exactly one structured
`AttemptObservationFailure` per observer failure:

| field | contents |
| ----- | -------- |
| `provider_id`, `operation` | which provider/operation |
| `workflow_id`, `instance_id`, `task_id`, `correlation_id` | safe identity |
| `attempt_number`, `status` | which attempt, and its neutral status |
| `error_type` | the exception **type name** only — never the message/args or any provider payload |

Guarantees: exactly one signal per observer failure; a reporter that itself raises is
contained (it can never mask the provider result); no signal on paths where no provider was
invoked; and with no reporter configured, behavior is unchanged (silent fail-open). The
structured record deliberately omits the exception message/args because an arbitrary
exception's payload may contain provider data (prompts, responses, tool arguments, credentials).
