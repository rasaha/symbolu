# Architecture

```
application / control plane
        │  ActionGovernanceRequest
        ▼
ActionGateProvider  (ugence_actiongate_provider.provider)
        │  map_request → native ActionGateRequest
        ▼
ActionGateClient  (in_process | remote seam)
        │
        ▼
ActionGateEngine  (core.py — pure vendor engine; stdlib only)
        │  ActionGateDecision
        ▼
map_result → ActionGovernanceResult  (outcome, constraints, obligations, expiry, …)
```

## Layers

- **Core** (`core.py`) — the vendor policy engine. Deterministic, offline, imports
  only the standard library. Imports neither the framework nor the kernel.
- **Client** (`client/`) — a narrow seam supporting an in-process engine or a remote
  service abstraction (no third-party HTTP dependency).
- **Provider** (`provider.py`) — adapts the core onto the neutral
  `ActionGovernanceProvider` contract: request/result mapping, error translation,
  health, observability. Consumes only `ugence_governance_provider_framework.api`.
- **Framework control-plane adapter** (owned by the framework, optional
  `decision-authority` extra) — normalizes a provider `ProviderError` to a fail-safe
  `INDETERMINATE` and bridges to the kernel `ActionControlPlanePort`. **Dispatch and
  execution live beyond this boundary — never in ActionGate.**

## Dependency direction

`application → ugence_actiongate_provider → ugence_governance_provider_framework.api`.
The kernel and framework never import ActionGate. ActionGate and TAP are independent
peers.
