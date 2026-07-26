# Platform v1.0 — Provider Development Guide

How to build a new governance provider against the frozen framework **without**
reopening the platform. TAP, ActionGate, and the two baseline validation providers
are the reference implementations.

## Rules

1. Implement the neutral contract for your family: `AssertionGovernanceProvider`
   (`evaluate`) or `ActionGovernanceProvider` (`authorize`). External-execution
   providers implement the execution contract.
2. Keep a **pure vendor core** that imports neither `decision_governance` nor
   `governance_providers`; adapt it to the neutral contract in a provider layer.
3. Consume only `governance_providers.api` and, where strictly necessary,
   `decision_governance.api`. Never import another concrete provider (same or other
   family) — F16/F17.
4. Declare an honest `ProviderDescriptor` (kind, version, `ProviderCompatibility`,
   `ProviderCapabilities`). Claim a capability only if you genuinely support it.
5. Be **fail-safe**: infrastructure failure (timeout/unavailable/malformed/
   protocol) must never produce SUPPORTED or AUTHORIZED. Assertion providers map
   such failures to INDETERMINATE; action providers raise a classified
   `ProviderError` that the control-plane adapter normalizes to INDETERMINATE.
6. Never execute actions from an action/assertion provider (F6/F8).
7. Emit deterministic result fingerprints and structured observability; log no
   secrets or unrestricted evidence.

## Conformance

Pass the shared kit unchanged:

```
from governance_providers.conformance import run_assertion_provider_conformance  # or _action_
assert run_assertion_provider_conformance(lambda: build_your_provider()).passed
```

Add a provider-specific conformance suite (mapping, provenance, each outcome,
error translation, determinism, idempotency). Package independently, depending on
`decision-governance==1.0.0` and `dgm-provider-framework==0.1.0`; bundle no kernel/
framework source (symlink the canonical package).

## Adding capabilities

New capability tags are additive (MINOR). They do not change the neutral contract.
Register the provider through the framework registry; resolution and failover
behaviour is provided by the framework + application resolution policy — do not
build a bespoke selection mechanism inside a provider.
