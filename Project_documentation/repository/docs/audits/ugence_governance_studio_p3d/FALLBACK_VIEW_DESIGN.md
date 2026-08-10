# Fallback View Design

**Screen:** `src/features/fallbacks/FallbackScreen.tsx` ·
**Route:** `/scenarios/:id/fallbacks` · **Operation:** `get_scenario_plan`
(reads `fallback_plan`).

## Intent

Show, per role, the backend's fallback coverage — the ranked fallback candidates
and an explicit coverage state — so a reviewer can see where the plan is resilient
and where it is single-threaded.

## Fallback states

The `fallback_state` field is rendered verbatim; the frontend never infers coverage:

| State | Meaning | Token |
|-------|---------|-------|
| `COMPLETE` | fallback available for the role | fallback available (eligible) |
| `PARTIAL` | limited fallback coverage | limited (indeterminate) |
| `NO_FALLBACK_AVAILABLE` | no fallback exists | no fallback (ineligible) |
| `NOT_APPLICABLE` | role does not require fallback | neutral |

## Rendering rules

- A **coverage summary** (`data-testid="fallback-summary"`) reports how many roles
  have no fallback, drawn directly from the returned states — not computed by
  re-deriving eligibility in the browser.
- Fallback candidates are listed in the API's order with their identifiers; no
  re-ranking occurs client-side.
