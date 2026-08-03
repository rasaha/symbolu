# Composition Search Design

- **Algorithm**: deterministic branch-and-bound (`compose_agent_team`) with an
  admissible upper bound (current objective + best remaining ranking score + max
  diversity bonus). Pruning is safe (never prunes a branch that could beat the
  incumbent), so the result is the exact optimum.
- **Exactness proof**: `bruteforce_optimum` (full Cartesian enumeration) is compared
  against B&B in `test_composition.py`; identical score + assignment.
- **Bounds**: `maximum_ai_roles=12`, `maximum_candidates_per_role=16`,
  `maximum_assignment_combinations=100000`. Exceeding → typed `SEARCH_SPACE_EXCEEDED`
  (no truncation). Role with no feasible candidate → `NO_FEASIBLE_TEAM`.
- **Hard vs soft**: `_team_feasibility` (hard) runs before `_objective` (soft);
  objective never offsets a hard constraint. Team tie-break: lexically smallest
  assignment tuple.
- **Counters** (`SearchStatistics`) are wall-clock-independent: explored, pruned,
  feasible-team count, search-space size, optimality status, termination reason.
