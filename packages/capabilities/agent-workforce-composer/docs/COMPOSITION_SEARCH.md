# Composition Search

Algorithm: **deterministic branch-and-bound** (`compose_agent_team`). Roles are
ordered by `role_id`; each role's candidates are the ranked, permission-feasible
eligible agents in rank order. An admissible upper bound — current objective +
best-possible remaining ranking score + max diversity bonus — prunes only branches
that cannot beat the incumbent, so the returned team is the **exact optimum**.

## Exactness proof
`bruteforce_optimum` performs full Cartesian enumeration with no pruning;
`tests/test_composition.py::test_exact_optimum_matches_bruteforce_oracle` asserts
B&B returns the identical score and assignment on the synthetic fixtures.

## Bounds and typed non-success
`maximum_ai_roles` (default 12), `maximum_candidates_per_role` (16),
`maximum_assignment_combinations` (100000). Exceeding any bound returns
`SEARCH_SPACE_EXCEEDED` — candidates are never silently truncated. A role with no
permission-feasible candidate returns `NO_FEASIBLE_TEAM` with `unfilled_roles`.
`SearchStatistics` reports algorithm, search-space size, assignments explored /
pruned, feasible-team count, bounds, optimality status and termination reason —
all wall-clock-independent.
