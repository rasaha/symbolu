# Authority Boundary Check (P2)

- P2 owns: ranking, cross-role compatibility, bounded team composition, proposed
  permission bounds, fallback ordering, AgentTeamPlan, plan explanation/replay/diff.
- P2 must NOT own (verified absent from API/code): agent execution, permission
  grants, action authorization, binding decisions, operational clearance, model
  choice, workflow scheduling.
- Non-agent P1 dispositions are preserved verbatim in the plan and never assigned
  (P2-I9). Governance/human nodes surface as `governance_boundary_refs`.
- Permission monotonicity and authority ceilings enforced (P2-I11/I13). No plan
  broadens role/enterprise/agent/governance authority.
- No score/rank ever converts a P1-ineligible agent into a candidate (P2-I1).
