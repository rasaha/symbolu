# AWC Consumer Boundary

The compiler describes the governed workflow; the Agent Workforce Composer (AWC)
plans the workforce. P2 respects that boundary.

## The compiler owns (and now emits in v2)
Node meaning, role relevance, functional capability requirements, typed data
contracts, dependency semantics, authority / human-review classification, and policy
provenance — all deterministic, provenance-backed, enterprise-neutral.

## The compiler does NOT own (never emitted)
Agent eligibility, elimination reasons, scores, ranks, team assignments, provider/
failure-domain optimization, permission-bound proposals, fallback ordering,
AgentTeamPlan, plan comparison/replay. It also never embeds enterprise deployment
policy (provider/residency/security/cost/latency/evidence/concentration) or runtime
state, and never grants/authorizes/executes.

## Direction
AWC consumes the compiler's serialized IR as data; the compiler imports nothing from
AWC. **No change in this package modifies the AWC adapter**, and none ever should —
the adapter is AWC-owned.

Consuming the v2 contract and reducing the temporary overlay fields the compiler now
emits was **AWC P2.1**, and it is **delivered** in the AWC package
(`ugence_agent_workforce_composer.adapter_v2`, `COMPILER_V2_ADAPTER.md`, the scoped
`agent-workforce-composer-p2-1-ci.yml` workflow, and the AWC gates
`compiler_v2_adapter_implemented` / `overlay_reduction_implemented` /
`v1_v2_equivalence_harness_implemented`). The direction is unchanged by that
delivery: data flows compiler → AWC, imports never flow back.
