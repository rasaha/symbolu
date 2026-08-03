# Ugence Governance Studio — Eligibility Explorer (P3C)

The first visible frontend for the Governance Studio. It consumes the **frozen
`governance_studio.api.v1`** contract over HTTP and reproduces **no** Policy
Workflow Compiler or Agent Workforce Composer logic.

- Package: `@ugence/governance-studio-frontend` `0.1.0` (private)
- Stack: Vite + React 18 + TypeScript (strict) + Tailwind + zustand (mirrors `apps/console`)
- API client: generated from `../contracts/openapi.json` with `openapi-typescript`

Synthetic demonstration data · deterministic planning only · **no ranking,
composition, permissions, fallbacks, replay, what-if, authentication, deployment
or agent execution** (those are P3D+).

## What it shows

Scenario catalog → scenario overview → workflow graph (+ accessible list) → node
details → role requirements → agent registry → **eligibility matrix** →
elimination explanations, with evidence, policy and fingerprint provenance
throughout. It clearly distinguishes **Eligible ≠ Selected ≠ Assigned ≠
Authorized ≠ Executed**.

## Develop

```bash
cd apps/ugence-governance-studio/frontend
npm install
npm run generate:api      # regenerate the typed client from the frozen contract
npm run dev               # http://127.0.0.1:5173 (expects the API at 127.0.0.1:8000)
```

Start the backend first:

```bash
pip install -c apps/ugence-governance-studio/backend/constraints.txt \
  apps/ugence-governance-studio/backend
python -m ugence_governance_studio_api.cli serve
```

Configure the API URL with `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`).

## Verify

```bash
npm run type-check         # strict TS
npm run lint               # eslint, 0 warnings
npm run test               # vitest: unit + component + a11y (axe)
npm run verify:openapi     # generated-client drift vs frozen contract
npm run verify:boundary    # no AWC/compiler/backend imports, no P3D paths
npm run verify:terminology # no ranking/selection/authorization language
npm run build              # production build
npm run e2e                # Playwright against the real backend
```

See [`../docs/FRONTEND_ARCHITECTURE.md`](../docs/FRONTEND_ARCHITECTURE.md) and the
`docs/` set for architecture, accessibility, security and testing details.
