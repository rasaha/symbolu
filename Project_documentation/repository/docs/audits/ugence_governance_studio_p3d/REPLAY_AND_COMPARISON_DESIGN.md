# Replay and Comparison Design

## Plan Replay

**Screen:** `src/features/replay/ReplayScreen.tsx` ·
**Route:** `/scenarios/:id/replay` · **Operations:** `replay_plan`, `export_scenario`.

Replay asks the backend to recompute a plan from the same inputs and compares
fingerprints. The screen (`data-testid="replay-result"`) shows:

- `match` — whether `expected_plan_fingerprint` equals `replayed_plan_fingerprint`,
  rendered as "fingerprints match" / "fingerprints differ". The decoder does **not**
  domain-default: a missing `match` throws rather than assuming `false`.
- Both fingerprints and any `diagnostics[]`.
- A clarifying note that this **does not rerun or replay agent execution** — it
  re-derives the deterministic plan only. No execution/runtime language appears.
- A deterministic **export** of the canonical plan snapshot (`export_scenario`),
  offered as a download of the exact bytes the API returns.

## Plan Comparison

**Screen:** `src/features/compare/CompareScreen.tsx` ·
**Route:** `/scenarios/:id/compare` · **Operation:** `compare_plans`.

Comparison renders the backend-produced diff between two plans
(`data-testid="plan-diff"`):

- `diff.assignment_changes[]`, `objective_changes[]`, `constraint_changes[]` grouped
  under labelled sections ("Assignment changes", …), each change tagged
  added / removed / changed with a contrast-verified token.
- `diff.diff_fingerprint` for correlation.

The browser performs **no diff computation** — it displays the API's diff verbatim.
