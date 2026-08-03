# Frontend Architecture (P3C)

```
src/
├── app/            App shell + router + CompatibilityGate
├── api/            typed HTTP client, view-model types, compatibility check
├── generated/      openapi-typescript output + recorded source hash
├── components/     AppShell, MaturityBanner
├── design-system/  accessible primitives + loading/error/empty states
├── features/       scenarios · workflow · roles · registry · eligibility · explanations
├── hooks/          react-query hooks (immutable per-scenario cache)
├── lib/            config, deterministic domain label/style maps
└── state/          zustand store (selection, filters, sort, panel state)
```

Data flow: **compatibility gate → react-query hook → typed client → OpenAPI
envelope → view-model → component**. The frontend fetches, validates
compatibility, formats, filters and sorts for presentation, and renders. It
computes no domain outcome; server responses are authoritative.

## Permission display boundary

P3C displays permission **requirements** and permission-related eligibility
evidence (role-required/prohibited/requested permissions, authority ceilings,
policy-related permission failures). It does **not** display composition-time
permission proposals and does not grant or provision permissions (P3D+).
