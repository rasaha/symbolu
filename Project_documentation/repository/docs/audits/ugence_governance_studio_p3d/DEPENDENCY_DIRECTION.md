# Dependency Direction (P3D)

The dependency arrow points **one way**: the frontend depends on the frozen
`governance_studio.api.v1` HTTP contract, and on nothing else in the platform.

```
browser (P3D planning explorer)
        │  HTTP + generated OpenAPI types only
        ▼
governance_studio.api.v1  (frozen; sha256 dc309eab…)
        ▼
ugence-governance-studio-api  (backend, thin orchestration)
        ▼
Agent Workforce Composer 0.2.1  (all planning logic)
        ▼
Policy Workflow Compiler 0.2.0
```

## Enforced

- **No source imports across the boundary.** `scripts/verify-boundary.mjs` bans any
  import of AWC (`ugence_agent_workforce_composer`), the compiler, or backend Python
  source, and any model-provider SDK. The frontend cannot reach planning code — it
  can only call the HTTP API.
- **`BANNED_API_PATHS = []`.** P3C banned the ranking/plan/etc. endpoints because it
  was eligibility-only; P3D consumes them, so the path ban is emptied. The **import**
  bans and the model-SDK ban are unchanged.
- **Contract freeze.** `npm run verify:openapi` fails on any drift from the recorded
  OpenAPI sha256 or operation-id set.
- **No planning logic in the browser.** Every domain number (scores, plan state,
  diffs, fingerprints) is produced by the backend and only *displayed* client-side;
  decoders validate but never compute.

## Not modified by P3D

AWC source, compiler source, backend behaviour, P3A/P3B fixtures, the frozen OpenAPI
contract, and the platform-freeze digest `d993093570…` are all unchanged.
