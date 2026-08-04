# Ugence Governance Studio — Planning Explorer (P3D)

The visible frontend for the Governance Studio. It consumes the **frozen
`governance_studio.api.v1`** contract over HTTP and reproduces **no** Policy
Workflow Compiler or Agent Workforce Composer logic — every domain number is
computed by the backend and only displayed here.

- Package: `@ugence/governance-studio-frontend` `0.2.0` (private)
- Stack: Vite + React 18 + TypeScript (strict) + Tailwind + zustand + TanStack Query (mirrors `apps/console`)
- API client: generated from `../contracts/openapi.json` with `openapi-typescript`
  (sha256 `dc309eab…`, drift-verified)

Synthetic demonstration data · deterministic planning only · **no authentication,
deployment, permission granting, runtime provisioning or agent execution**.

## What it shows

P3C (eligibility) plus the P3D planning explorer:

- **Eligibility matrix** + elimination explanations (P3C)
- **Ranking Explorer** — canonical ranked candidates + score decomposition (bp)
- **Composition Explorer** — plan state, assignments, non-greedy explanation, `NO_FEASIBLE_TEAM` rendered honestly
- **Permission Proposals** — categorised proposed scopes with a no-grant notice
- **Fallbacks** — per-role fallback coverage and explicit fallback states
- **Replay** — plan fingerprint match + deterministic export (not agent re-execution)
- **Comparison** — the backend's plan diff
- **Controlled What-If** — nine allowlisted bounded perturbations on a temporary copy

It consistently distinguishes **Eligible ≠ Ranked ≠ Selected ≠ Assigned ≠
Proposed ≠ Granted ≠ Executed**.

## Implemented (P3D)

Ranking, composition, permission **proposals** (display only), fallback coverage,
plan replay, plan comparison, controlled what-if (9 allowlisted operations),
deterministic export.

## Not implemented (P3E+)

Authentication / authorization, deployment, **granting or provisioning** of any
permission, runtime provisioning, agent execution, arbitrary/free-form scenario or
policy input, workflow authoring/editing.

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
npm run test               # vitest: unit + component + decoders + a11y (axe)
npm run verify:openapi       # generated-client drift vs frozen contract
npm run verify:api-boundary  # positive allowlist: only approved public operations consumed
npm run verify:boundary      # no AWC/compiler/backend imports, no model SDKs
npm run verify:terminology   # no grant/provisioning/authorization/execution language
npm run verify:contrast      # measured WCAG 2.2 token contrast, content-type classified (34 pairs)
npm run verify:version       # package/lockfile/docs all report 0.2.0
npm run verify:tracked-sources # every imported source file is git-tracked (clean-checkout safety)
npm run audit:dependencies   # blocking: fail on high/critical production vulnerabilities
npm run build                # production build
npm run e2e                  # Playwright: all scenarios + nine-operation what-if matrix (real backend)
```

## Boundaries

The Studio **proposes** permission scopes and displays permission requirements; it
never grants, provisions, activates or authorizes anything, holds no secrets, and
accepts no arbitrary JSON / policy / URL / code / fixture-upload input. The only
mutating-looking control is what-if, restricted to nine allowlisted operations with
validated parameters applied to a server-side temporary copy. Every response is
validated by a fail-closed decoder; `NO_FEASIBLE_TEAM` is a domain state, not an
error. The frozen OpenAPI contract and the platform-freeze digest are unchanged by
this frontend.

See the [`../docs/`](../docs/) set (RANKING_EXPLORER, COMPOSITION_EXPLORER,
NON_GREEDY_COMPOSITION, PERMISSION_PROPOSAL_EXPLORER, FALLBACK_EXPLORER,
PLAN_REPLAY, PLAN_COMPARISON, CONTROLLED_WHAT_IF, P3D_ACCESSIBILITY, P3D_SECURITY,
P3D_TESTING, KNOWN_LIMITATIONS_P3D) and the P3D audit at
[`docs/audits/ugence_governance_studio_p3d/`](../../../docs/audits/ugence_governance_studio_p3d/).
