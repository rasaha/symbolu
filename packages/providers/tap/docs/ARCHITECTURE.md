# Architecture

```
application / assessment workflow
        │  (neutral AssertionGovernanceRequest / Result)
        ▼
ugence_tap_provider.provider.TAPProvider   ── adapts ──►  ugence_governance_provider_framework.api
        │
        ├─ mapping/     neutral ↔ native request/result/controls
        ├─ errors/      native failure → classified ProviderError
        ├─ configuration/  TapSettings + factory
        ├─ health/      availability, config, protocol, evaluator, policy
        ├─ observability/  invocation records (counts/coverage only)
        └─ client/      in-process | remote seam
                 │  (native TapEvaluationRequest / Result)
                 ▼
        core/  the pure, deterministic, offline TAP engine
```

**Dependency direction:** `application → ugence_tap_provider →
ugence_governance_provider_framework.api`. The `core/` and `client/` layers import
**neither** the framework **nor** the kernel — they speak only native TAP
vocabulary. The Decision Authority kernel is reached only lazily through the
framework's optional assessment-integration adapter (the `decision-authority`
extra).

TAP is a **peer** of ActionGate: independent, mutually unaware, different provider
kinds. The `core/` layer is a pure function of request + configured policy — no
network, no clock, no model — so error modes and mappings are fully testable
offline.
