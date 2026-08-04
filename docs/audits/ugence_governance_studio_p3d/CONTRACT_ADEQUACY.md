# Contract Adequacy Assessment (P3D)

Before implementation, each planned P3D view was checked against the live response
of the frozen `governance_studio.api.v1` contract to confirm every field the view
renders is already present. **No field was missing**, so this phase required no
contract change and raised no `GOVERNANCE_STUDIO_P3D_P3B_CONTRACT_BLOCKED`
escalation. The OpenAPI sha256 (`dc309eab…`) is unchanged.

| View | Required public fields | Present |
|------|------------------------|---------|
| Ranking | `rankings[].role_id`, `ranking_fingerprint`, `ranked_candidates[].{rank, agent_id, score, tie_group}`, per-criterion contribution (basis points) | ✅ |
| Composition | `agent_team_plan.{plan_state, role_assignments[].{role_id, primary_agent_id, selection_state}, objectives, constraints, search_statistics}` | ✅ |
| Non-greedy explanation | `explain_plan` → rationale referencing team-level objectives / search over role-local greedy choice | ✅ |
| Permission proposals | `permission_proposals[].{role_id, categorized_permissions[].{permission, category}, feasible, requires_human_review}` | ✅ |
| Fallbacks | `fallback_plan[].{role_id, fallback_state, fallback_candidates[]}` with states COMPLETE / PARTIAL / NO_FALLBACK_AVAILABLE / NOT_APPLICABLE | ✅ |
| Replay | `replay_plan` → `{match, expected_plan_fingerprint, replayed_plan_fingerprint, diagnostics[]}` | ✅ |
| Comparison | `compare_plans` → `diff.{diff_fingerprint, assignment_changes[], objective_changes[], constraint_changes[]}` | ✅ |
| What-If | `scenario_what_if` → `{baseline_state, modified_state, diff}` for the 9 allowlisted operations | ✅ |
| Export | `export_scenario` → deterministic canonical JSON snapshot | ✅ |

## NO_FEASIBLE_TEAM

`plan_state = NO_FEASIBLE_TEAM` is a first-class **domain state**, not an error.
The contract returns HTTP 200 with a populated envelope; the frontend renders it
honestly (no fabricated assignment) and never treats it as a failure. Verified
against the `cybersecurity_no_feasible_team` scenario.
