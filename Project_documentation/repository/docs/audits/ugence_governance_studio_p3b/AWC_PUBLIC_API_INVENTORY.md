# AWC Public API Inventory (consumed by P3B)

AWC 0.2.1 exposes **109** public names via `ugence_agent_workforce_composer.api`.
P3B imports ONLY that public surface (plus the public
`ugence_agent_workforce_composer.fingerprint.stamp_fingerprint` for what-if
policy re-stamping). No private AWC/compiler module, test helper, P3A generation
script, or runtime package is imported (enforced by `tests/test_architecture.py`).

## Functions the orchestration service delegates to
`adapt_compiled_workflow`, `adapt_workflow`, `declared_contract_version`,
`evaluate_workflow_eligibility`, `evaluate_registry_for_role`, `explain_role_report`,
`rank_eligible_candidates`, `build_role_dependency_graph`, `compose_agent_team`,
`build_agent_team_plan`, `build_replay_record`, `replay_agent_team_plan`,
`compare_agent_team_plans`, `compare_adaptations`, `finalize_enterprise_policy`,
`build_registry_snapshot`.

## Models validated / serialized
`AgentRegistrySnapshot`, `EnterpriseAgentPolicy`, `EligibilityPolicy`,
`AgentRankingPolicy`, `TeamCompositionPolicy`, `PermissionBoundingPolicy`,
`AgentFallbackPolicy`, plus all result models (adaptation, eligibility, ranking,
composition, plan, replay, diff, equivalence report) passed through `result` intact.
