# Token Accounting (CM-TA1)

> Context Minimization measures **how much context was safely removed**. Provider
> reconciliation measures **what the API reported consuming**. Agent Runtime records
> **each execution attempt** and enforces budgets. These quantities are *related but
> not interchangeable*.

`ugence_context_minimization.token_accounting` adds neutral, deterministic,
stdlib-only contracts that let a caller measure and reconcile token consumption for
every model API attempt — **without** putting a tokenizer, a provider SDK, a
database, or a pricing table inside this leaf.

## Three distinct measurements

| # | Name | Type | Owner | Exactness |
| - | ---- | ---- | ----- | --------- |
| **A** | Context reduction | `MinimizationResult.original_tokens / resulting_tokens / achieved_reduction` | the minimizer | exact over the *context units it controls* |
| **B** | Complete-request estimate | `RequestTokenEstimate.estimated_input_tokens` | an **injected** `RequestTokenCounter` | depends on the counter; the default is `DEFAULT_APPROXIMATE` |
| **C** | Provider-reported usage | `ProviderTokenUsage` | the provider (post-call) | authoritative *for the response reconciled*; **not an invoice** |

They are never collapsed into one field. B is the *whole request* (system +
messages + minimized context + tool definitions + schemas + provider wrappers), so
it is a different — larger — number than A's minimized-context count.

## The core never tokenizes

The core ships exactly one counter, `DefaultApproximateRequestCounter`: a transparent
word/punctuation counter, always labelled `DEFAULT_APPROXIMATE`, that **cannot**
tokenize images/audio and never claims exactness. A real provider BPE counter is an
*injected* `RequestTokenCounter` that lives **outside** this package.

`TokenCountBasis` records provenance so an approximate count is never mistaken for
exact provider tokenization: `CALLER_SUPPLIED`, `INJECTED_COUNTER`,
`DEFAULT_APPROXIMATE`, `MIXED`, `PROVIDER_REPORTED`, `UNKNOWN`.

## Unknown is not zero

Every `ProviderTokenUsage` numeric field is `Optional[int]`; `None` means *unknown*
and is preserved verbatim. A failed or exception attempt with no usage evidence is
recorded with `usage_availability = UNAVAILABLE_*` and `provider_usage = None` — it is
**never** written as zero consumption, and it keeps the logical-request summary
`complete = False`.

Cached, cache-write, and reasoning tokens are provider-specific subsets/details. They
stay **visible** but are **not** folded into input/output totals. `derived_total()`
returns `input + output` only, and is explicitly *derived* — distinct from the
provider-reported `total_tokens`, which is preserved separately.

## Attempt vs logical request

- `logical_request_id` identifies the **business** request.
- `attempt_id` identifies **one** potentially-billable provider attempt.
- A **retry is a new `attempt_id`** (link it with `retry_of_attempt_id`). Three
  attempts under one logical request stay three `ApiCallTokenRecord`s — the final
  success never absorbs the earlier ones.

An `ApiCallTokenRecord` binds one attempt to all three measurements plus attribution
(`tenant / workflow / agent / task`) and carries a domain-separated deterministic
`record_fingerprint`. It stores **no** prompt text, credentials, secrets, or provider
response payloads. `LogicalRequestTokenSummary` aggregates all attempts of one logical
request, reporting retry-token and failed-attempt-token sums separately and attributing
context savings **once**.

## Pre-call / post-call flow

```python
from ugence_context_minimization.api import (
    prepare_api_call_measurement, reconcile_api_call_measurement,
    aggregate_logical_request_usage, ProviderTokenUsage, AttemptStatus,
    RequestComponents, InMemoryTokenAccountingSink,
)

prep = prepare_api_call_measurement(              # links to a MinimizationResult (A + B)
    minimization_result=result,
    logical_request_id="req-42",
    provider_id="acme",
    request_components=RequestComponents(
        system_text=system_prompt,
        message_texts=tuple(messages),
        minimized_context_tokens=result.resulting_tokens,
        tool_definition_texts=tuple(tool_defs),
    ),
    model_id="acme-large",
)

sink = InMemoryTokenAccountingSink()
reconcile_api_call_measurement(                   # attempt 1 failed, usage unknown (C)
    prep, attempt_id="att-1", attempt_number=1, status=AttemptStatus.FAILED, sink=sink,
)
reconcile_api_call_measurement(                   # attempt 2 (retry) succeeded, usage known
    prep, attempt_id="att-2", attempt_number=2, status=AttemptStatus.SUCCEEDED,
    retry_of_attempt_id="att-1",
    provider_usage=ProviderTokenUsage(input_tokens=2337, cached_input_tokens=1500, output_tokens=428),
    sink=sink,
)

summary = aggregate_logical_request_usage(sink.records)
assert summary.attempt_count == 2 and summary.attempts_usage_unknown == 1
assert summary.complete is False                  # a measurement gap, not zero
```

## What this is not

- Not a provider tokenizer, model SDK, or network/database/filesystem persistence.
- Not a pricing authority — **no cost is computed here**; that requires an explicit,
  versioned external pricing source.
- Not invoice reconciliation — provider-response usage is authoritative only for the
  API response being reconciled. Invoice/billing reconciliation is a later external
  concern.
- Deterministic replay reads no wall clock and generates no random ids — every id is
  caller-supplied.
