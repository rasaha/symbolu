# Governance Provider Framework (GPF) Relationship

## Options considered

1. A directly-invoked platform capability.
2. An existing governance-provider-family implementation (`ACTION_GOVERNANCE`).
3. A new provider family (new `ProviderKind`).
4. A product-internal service.

## Decision

> **Action Clearance is a directly-invoked capability.** Signal adapters are product/integration
> adapters. **No new `ProviderKind` is required or added.**

Rationale:

- The three existing `ProviderKind` peers (`ASSERTION_GOVERNANCE`, `ACTION_GOVERNANCE`,
  `EXTERNAL_EXECUTION`) are governance *provider* families resolved by GPF. Action Clearance is not a
  provider that GPF selects among alternatives — it is a deterministic capability the Workflow Service
  invokes directly after ActionGate, exactly like the live composition invokes the clearance step
  directly (not via provider resolution).
- Model Selection is the precedent: a directly-invoked, stdlib-leaf capability that does **not** add a
  `ProviderKind`. Action Clearance follows the same shape.
- Adding a `ProviderKind` would imply GPF has authority to route/select clearance implementations, which
  would blur the authority boundary and invite the "new ProviderKind proliferation" risk (RISK_REGISTER
  R-PK).

Deviation from "directly invoked" is permitted **only** if live contracts later prove direct invocation
cannot satisfy lifecycle or resolution needs. No such proof exists today, so **no `ProviderKind` is
added in this phase.**

## Adapter registration & resolution (without GPF authority)

Signal adapters (identity, incident, change-management, GitHub, target-state, execution-ledger
projections) are registered and resolved by the **product/workflow layer**, not GPF:

- adapters implement a narrow, package-local `SignalAdapter` protocol (produce normalized
  `TrustedSignal`s for a set of `signal_type`s);
- the Workflow Service composes the `SignalBundle` from the adapters it selects for a given profile;
- resolution is explicit configuration (which adapter serves which `signal_type` for which profile) —
  never inferred, never given governance authority.

GPF remains authoritative for the *provider* families it already owns; it is given **no** authority over
clearance. If a future integration wants clearance signals sourced from a GPF provider (e.g. an
execution provider surfacing target-state), that provider is consumed as a signal **source** through an
adapter — it does not make Action Clearance a GPF provider.
