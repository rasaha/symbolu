# Executable Model Registry Schema

*Phase 5 deliverable. Implemented in `execution_gate/registry.py`.*

## Execution-status lineage (never skip a stage)

```
declared → enumerated → authenticated → EXECUTION_VERIFIED → (currently) eligible
```

- **declared** — appears in provider docs/spec.
- **enumerated** — returned by the provider model-list endpoint.
- **authenticated** — the provider accepted our credential (endpoint answered as us).
- **execution_verified** — a real minimal inference **succeeded** (or a provider-specific
  authoritative equivalent explicitly allowed by policy). **Enumeration alone never
  qualifies.**
- **eligible** — a *current* ExecutionGate decision (recomputed per request, TTL-bounded),
  not a stored status: a verified model can still be INELIGIBLE right now (quota, policy,
  residency, cost, latency).

`execution_verified` is a durable historical fact; `eligible` is an ephemeral,
request-and-time-specific decision. The registry stores the former; the gate computes the
latter.

## Record fields

| Field | Source | Purpose |
|---|---|---|
| internal_id | ours | stable handle across provider renames |
| serving_provider | config | who serves it (Anthropic, Google, Alibaba Model Studio) |
| model_developer | config | who built it (may differ from server) |
| model_family | config | distinct lineage (claude/gemma/gemini/qwen) |
| exact_provider_model_id | provider | the string the endpoint accepts |
| declared_capabilities | provider docs | context, structured output, tools, modalities |
| verified_capabilities | our probes | what actually worked in inference |
| exec_status | lineage above | declared…execution_verified |
| last_success_ts / last_failure_ts | telemetry | recency of execution evidence |
| failure_reason_code | telemetry | normalized last failure |
| billing_tier | probe | paid / free / unknown |
| quota_state | probe | ok / exhausted / rate_limited / unknown |
| region | config | serving region |
| network_policy_state | probe | permitted / blocked |
| compliance_state | governance | approved / prohibited / unknown |
| context_capacity | provider | effective context |
| structured_output_support / tool_support | provider | feature flags |
| input_price / output_price | pricing source | cost math |
| pricing_source + retrieval_ts | authoritative docs | auditable pricing provenance |
| observed_latency / observed_reliability | telemetry | operational conditions |
| evidence_provenance | mixed | source of each field |
| ttl | config | when evidence must be refreshed |
| enabled | ops | hard on/off |

## Rules

1. A model is **eligible** only via a fresh gate decision; the registry never hard-codes
   eligibility.
2. `execution_verified` requires a real successful inference; enumeration/authentication do
   not upgrade to it.
3. Pricing must carry a source + retrieval timestamp; free-tier and paid-tier economics are
   never mixed (a free-tier-only model is not priced as paid).
4. Fields carry provenance and TTL; stale fields degrade to UNKNOWN at gate time.
