# Composition View Design

**Screen:** `src/features/composition/CompositionScreen.tsx` ·
**Route:** `/scenarios/:id/composition` · **Operations:** `get_scenario_plan`,
`explain_plan`.

## Intent

Show the backend's composed agent-team plan — its state, per-role assignments,
selection states, objectives/constraints and the search statistics — plus the
explanation of why composition is **not** a greedy per-role pick.

## Rendering rules

- **Plan state** (`plan_state`) is displayed verbatim: `COMPLETE`, `PARTIAL`, or
  `NO_FEASIBLE_TEAM`. Each maps to a contrast-verified semantic token.
- **Assignments** list `role_id` → `primary_agent_id` with the per-assignment
  `selection_state` ("Selected primary", "Selected fallback",
  "Eligible — not selected").
- **Non-greedy explanation** (`data-testid="non-greedy"`) states that ranking
  evaluates role-level suitability while composition optimises the team against
  objectives and constraints, so the top-ranked candidate for a role is not always
  the one assigned. Text comes from `explain_plan`.
- **Objectives, constraints and search statistics** are surfaced so the plan reads
  as the outcome of a bounded search, not an ad-hoc assignment.

## NO_FEASIBLE_TEAM

When `plan_state = NO_FEASIBLE_TEAM` the screen renders an honest
`data-testid="no-feasible-team"` panel — the unmet roles/constraints — and shows
**no** "Selected primary" assignment. This is a domain state, rendered at HTTP 200;
it is never surfaced as an error or an empty crash.
