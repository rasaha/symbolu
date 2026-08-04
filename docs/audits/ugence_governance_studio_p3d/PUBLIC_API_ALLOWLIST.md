# Public API Operation Allowlist (C1)

The permissive `BANNED_API_PATHS = []` denylist is superseded by a **positive
allowlist**. The frontend may consume only the operations named in
`apps/ugence-governance-studio/frontend/security/approved-api-operations.json`,
and that manifest is validated against the frozen OpenAPI contract.

- Manifest OpenAPI sha256: `dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656` (frozen, unchanged)
- Verifier: `npm run verify:api-boundary` (`scripts/verify-api-boundary.mjs`)
- Enforced invariant:
  `consumed ⊆ approved` ∧ `consumed ∩ forbidden = ∅` ∧ `consumed ⊆ OpenAPI` ∧ no raw fetch outside the canonical client ∧ no forbidden reference in app/test code.

## Detection is consumption-based, not generation-based

The generated client (`src/generated/api.ts`) contains **all 23** operations. The
verifier ignores it and instead parses the actual `request()` / `envelope()` call
sites in the canonical client `src/api/client.ts`, resolving each `(method, path)`
to an OpenAPI `operationId`. This distinguishes *generated but unused* from *wired
into the frontend*. Operations reached only through hooks/wrappers (e.g.
`scenario_what_if` via `useWhatIf → scenarioWhatIf`) are still detected because all
consumption funnels through that single client.

## Approved operations (17) — detected as consumed

`get_health`, `get_ready`, `get_version`, `list_scenarios`, `get_scenario`,
`get_scenario_workflow`, `get_scenario_registry`, `get_scenario_eligibility`,
`explain_eligibility`, `get_scenario_ranking`, `get_scenario_plan`,
`explain_ranking`, `explain_plan`, `replay_plan`, `compare_plans`,
`scenario_what_if`, `export_scenario`.

Consumed count: **17** · unapproved consumed: **0** · forbidden consumed: **0** ·
raw unapproved fetches: **0**.

## Forbidden / internal operations (6) — never wired into the browser

`validate_workflow`, `adapt_workflow`, `compare_adaptations`,
`evaluate_eligibility`, `evaluate_ranking`, `compose_workforce`.

These lower-level primitives (paths `/api/v1/workflows/*`, `/api/v1/eligibility/evaluate`,
`/api/v1/ranking/evaluate`, `/api/v1/composition/compose`) must not appear in
application or test code (except explicit negative-fixture files marked
`api-allowlist-negative-fixtures`).

## Enforcement — failing conditions

The verifier fails when: an operation not in the manifest is consumed; a raw fetch
hits an unapproved path; a forbidden id/path appears in client/hooks/screens/tests;
a new client call consumes an operation absent from the manifest; the manifest hash
differs from the frozen contract; an approved operation no longer exists in the
OpenAPI; a forbidden operation becomes reachable through a wrapper; a raw fetch
bypasses the canonical client; the manifest has duplicate entries; or an operation
appears in both approved and forbidden sets. Each condition has a unit test in
`tests/api-allowlist.test.ts` (13 tests).
