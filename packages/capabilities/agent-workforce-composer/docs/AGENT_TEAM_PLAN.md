# AgentTeamPlan

`build_agent_team_plan` runs the full P1→P2 pipeline (adapt → eligibility → rank →
dependency graph → compose → permission-bound → fallback) and assembles the
immutable, content-addressed `AgentTeamPlan`.

It pins every input digest: `registry_snapshot_digest`, `enterprise_policy_digest`,
`eligibility_policy_digest`, `ranking_policy_digest`, `composition_policy_digest`,
`permission_policy_digest`, `fallback_policy_digest`, plus `workflow_fingerprint`
and `compiler_source_digest`. It carries `role_assignments`,
`permission_bound_proposals`, `role_fallback_plans`, `team_constraint_results`,
`team_objective_results`, `search_statistics`, `non_agent_dispositions` (preserved
verbatim), `governance_boundary_refs`, `human_review_requirements`,
`selection_explanation`, and `plan_fingerprint`.

`plan_state`: `COMPLETE` (every AI role assigned, all hard constraints passed,
permission-feasible, exact-search established), `NO_FEASIBLE_TEAM`,
`SEARCH_SPACE_EXCEEDED`, `PARTIAL`, `INVALID_INPUT`. A non-complete state never
emits assignments as complete (`unfilled_roles` is populated instead).

The plan is a **proposal**. It grants nothing, authorizes nothing, schedules
nothing, and executes nothing.

## Selection explanation
`TeamSelectionExplanation` answers, per role: why each primary was selected, why
higher-ranked individuals were not (team-level trade-offs: provider / failure-domain
/ authority concentration, interface constraints), which candidates were eligible
but unselected (`ELIGIBLE_NOT_SELECTED`), which are fallbacks (`SELECTED_FALLBACK`),
and which were P1-ineligible (`INELIGIBLE`, with elimination reasons).
