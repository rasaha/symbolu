# Dependency Direction

```
Governance Studio frontend  ──HTTP/OpenAPI──▶  Governance Studio backend
                                                     ▼  Agent Workforce Composer 0.2.1
                                                     ▼  Policy Workflow Compiler artifacts
```

The frontend imports ONLY its own code + the generated OpenAPI client. It never
imports Python backend modules, AWC/compiler source or packages, P3A fixture
loaders, P3B orchestration internals, runtime packages, or model-provider SDKs
(enforced by `scripts/verify-boundary.mjs`). It computes no domain outcome: no
workflow classification, role extraction, eligibility/ranking/composition/
permission/fallback logic. All outcomes come from the API.
