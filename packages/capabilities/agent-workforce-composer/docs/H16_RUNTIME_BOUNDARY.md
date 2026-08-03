# H16 / Runtime Boundary (documentation + plan invariants only)

P2 produces an `AgentTeamPlan`; it does not execute it. The later runtime contract
(NOT implemented in P2) is:

**P2 pre-approves** a primary agent + an ordered fallback set per role, each with a
least-privilege permission-bound proposal and pinned policy digests.

**A runtime MAY**: select from the approved set, skip unavailable candidates,
narrow permissions, escalate to human/governance, or fail closed.

**A runtime MUST NOT**: introduce an unapproved agent, broaden permissions, broaden
authority, change policy digests, or silently recompose the team.

P2 does not modify H16 runtime behaviour, move any H16 class, or add an H16
compatibility facade. `h16_migration_implemented=false`,
`runtime_handoff_implemented=false`, `live_availability_implemented=false`.
