# Ugence CM-TA1 — Context Minimization × Token Accounting × Agent Runtime

A **narrowly-scoped, one-way integration** that wires the Context Minimization
token-accounting contracts to the Agent Runtime's neutral provider-attempt telemetry.

> Context Minimization measures **how much context was safely removed**. Provider
> reconciliation measures **what the API reported consuming**. Agent Runtime records
> **each execution attempt** and enforces budgets. These quantities are related but not
> interchangeable — this package keeps them linked without collapsing them.

## What it does

- **Translate** a neutral Agent Runtime `ProviderAttempt` into a Context Minimization
  `ApiCallTokenRecord` via an **injected**, provider-specific `UsageNormalizer`. The
  runtime forwards a provider's opaque usage mapping uninterpreted; this package types it.
- **Record** every attempt — including retries and failed/exception attempts — through a
  CM `TokenAccountingSink`. Unknown usage stays unknown (never zero); retried attempts stay
  distinct; the idempotent-replay contract (byte-identical or reject) is preserved.
- **Settle** H22-D budgets from **measured** usage when authoritative, falling back to the
  existing **conservative full-reservation** settlement when usage is unavailable, and
  surfacing `BudgetEstimateExceeded` rather than clamping or hiding an overrun.

## Dependency direction (one-way)

```
ugence-context-minimization  (leaf, stdlib-only)
                 \
                  >--  ugence-context-minimization-token-accounting-runtime  (this package)
                 /
ugence-agent-runtime         (core, stdlib-only)
```

This package imports both cores; **neither core imports this package**. The base install
carries **no** concrete OpenAI/Anthropic/Google SDK and **no** tokenizer — provider-specific
usage normalizers are optional and live outside this package.

## Quick start

```python
from ugence_cm_token_accounting_runtime import (
    RuntimeTokenAccountingBridge, MappingUsageNormalizer, settle_budget_from_usage,
)
from ugence_context_minimization.api import (
    prepare_api_call_measurement, aggregate_logical_request_usage, InMemoryTokenAccountingSink,
)
from ugence_agent_runtime.api import AgentRuntimeConfig, create_runtime

# 1. A mechanical, provider-shaped normalizer (a real vendor SDK normalizer lives outside).
normalizer = MappingUsageNormalizer(
    {"input_tokens": "prompt_tokens", "output_tokens": "completion_tokens"},
    schema_name="vendor.v1", adapter_id="vendor-adapter", adapter_version="1",
)

# 2. The bridge is the runtime's attempt observer.
sink = InMemoryTokenAccountingSink()
bridge = RuntimeTokenAccountingBridge(sink, normalizer=normalizer)
runtime = create_runtime(AgentRuntimeConfig(attempt_observer=bridge))

# 3. Prepare a measurement per logical request and register it by runtime identity.
inst = runtime.prepare_workflow(definition)
prepared = prepare_api_call_measurement(
    minimization_result=result, logical_request_id="req-42", provider_id="vendor",
)
bridge.register(prepared, instance_id=inst.instance_id, task_id="task-1")

# 4. Drive the workflow; the bridge records one ApiCallTokenRecord per attempt.
#    Then aggregate + settle at the quantum boundary.
summary = aggregate_logical_request_usage(sink.records)
settlement = settle_budget_from_usage(coordinator, inst.instance_id,
                                      sink.records[-1].provider_usage)
```

## What this is not

- **Not** a provider adapter. `MappingUsageNormalizer` is a mechanical key-mapping helper,
  not a vendor SDK. **No real provider adapter is implemented here.**
- **Not** invoice reconciliation. Provider-reported usage is authoritative only for the API
  response reconciled; billing/invoice reconciliation is a later external concern.
- **Not** persistence. It uses the CM `TokenAccountingSink` protocol; durable storage is an
  external concern (the in-memory sink is for tests/reference).

See [`docs/INTEGRATION.md`](docs/INTEGRATION.md) and
[`docs/PACKAGE_BOUNDARY.md`](docs/PACKAGE_BOUNDARY.md).
