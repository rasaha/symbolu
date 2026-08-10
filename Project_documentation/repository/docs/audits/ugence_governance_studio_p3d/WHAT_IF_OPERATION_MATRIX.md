# Controlled What-If Operation Matrix (C2)

Every one of the nine allowlisted operations was exercised against the **real local
backend** (`governance_studio.api.v1`) using the frozen synthetic `procurement`
scenario. All returned HTTP 200. Param **names and types** mirror the backend
`apply_perturbation` contract, not UI labels.

## Control → request mapping

| Operation | Control(s) | Request params (exact) |
|-----------|-----------|------------------------|
| FORBID_PROVIDER | provider selector (pinned registry) | `{ provider: string }` |
| REQUIRE_RESIDENCY | residency selector (pinned registry) | `{ residency: string }` |
| TIGHTEN_COST_CEILING | bounded number (≥0) | `{ ceiling: number }` |
| TIGHTEN_LATENCY_CEILING | bounded number (≥0) | `{ ceiling: number }` |
| REVOKE_AGENT_VERSION | agent@version selector (pinned registry) | `{ agent_version: string }` |
| EXPIRE_EVIDENCE | none | `{}` |
| TIGHTEN_PERMISSION_POLICY | predefined permission selector | `{ permission: string }` |
| TIGHTEN_PROVIDER_CONCENTRATION | bounded integer (0–100) | `{ limit_pct: integer }` |
| REMOVE_CANDIDATE | candidate selector (pinned registry) | `{ agent_id: string, agent_version: string }` |

## Real-backend results (scenario `procurement`)

| Operation | HTTP | baseline → modified | modified fingerprint |
|-----------|------|---------------------|----------------------|
| FORBID_PROVIDER | 200 | COMPLETE → NO_FEASIBLE_TEAM | `sha256:6ee…` |
| REQUIRE_RESIDENCY | 200 | COMPLETE → NO_FEASIBLE_TEAM | `sha256:8d8…` |
| TIGHTEN_COST_CEILING | 200 | COMPLETE → NO_FEASIBLE_TEAM | `sha256:db5…` |
| TIGHTEN_LATENCY_CEILING | 200 | COMPLETE → NO_FEASIBLE_TEAM | `sha256:ac6…` |
| REVOKE_AGENT_VERSION | 200 | COMPLETE → NO_FEASIBLE_TEAM | `sha256:c13…` |
| EXPIRE_EVIDENCE | 200 | COMPLETE → NO_FEASIBLE_TEAM | `sha256:9d5…` |
| TIGHTEN_PERMISSION_POLICY | 200 | COMPLETE → COMPLETE | `sha256:35b…` |
| TIGHTEN_PROVIDER_CONCENTRATION | 200 | COMPLETE → NO_FEASIBLE_TEAM | `sha256:49e…` |
| REMOVE_CANDIDATE | 200 | COMPLETE → NO_FEASIBLE_TEAM | `sha256:f6a…` |

Full payloads and fingerprints are in `WHAT_IF_OPERATION_MATRIX.json`.

## Immutable baseline

The **baseline plan fingerprint is identical for all nine operations**
(`sha256:c197352…`). Because each perturbation is applied to a fresh temporary copy
server-side, the frozen scenario and its baseline plan are never mutated — every
operation yields a *different* modified fingerprint while the baseline stays fixed.

## Boundary guarantees

- **API-supplied outcomes** — `modified_state`, the modified plan fingerprint and the
  `plan_diff` are rendered verbatim from the response; the browser computes no
  ranking, composition or diff.
- **Bounded input** — selects offer only pinned-registry / predefined values;
  numbers are range-validated; unsupported operations, arbitrary providers/agents/
  permissions, malformed/negative/out-of-range numbers and cross-operation
  parameters are rejected before any request is sent (see `tests/whatif-mapping.test.ts`,
  `tests/whatif-screen.test.ts`).
- **Reset** clears only client-held what-if state (submitted op/params + result view);
  it issues no request and cannot alter the baseline.

## Verification

- `tests/whatif-mapping.test.ts` — table-driven per-operation payloads + negatives.
- `tests/whatif-screen.test.tsx` — per-operation control visibility, exact posted
  payload, stale-parameter drop, disabled-while-empty, immutable baseline, reset.
- `e2e/what-if-matrix.spec.ts` — all nine exercised against the real backend (CI gate
  `what-if-real-backend-matrix`).
