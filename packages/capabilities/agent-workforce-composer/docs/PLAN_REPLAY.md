# Plan Replay & Comparison

## Replay
`CompositionReplayRecord` pins the workflow adaptation fingerprint, role and
non-agent-disposition fingerprints, the registry snapshot digest, all six policy
digests, the logical time, the contract versions, and the expected plan
fingerprint. `replay_agent_team_plan` rebuilds the plan from identical logical
inputs and (when given the expected plan) asserts an identical `plan_fingerprint`.
Replay reproduces candidate rankings, assignments, permission proposals, fallback
ordering, and deterministic search statistics. Wall-clock duration never enters any
fingerprint.

Cross-process determinism is proven by the distribution verifier, which builds the
plan in two separate processes and compares fingerprints.

## Comparison
`compare_agent_team_plans(a, b)` produces an `AgentTeamPlanDiff`: assignment
changes, team score delta, permission/fallback changes, policy-digest changes and
snapshot change. Comparing plans from different `workflow_identity` yields a typed
`workflow_mismatch` result rather than a misleading diff. This supports later
policy/registry what-if exploration.
