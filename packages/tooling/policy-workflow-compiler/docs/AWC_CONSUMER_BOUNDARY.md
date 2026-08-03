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
AWC. **This PR does not modify the AWC adapter.** Consuming the v2 contract and
reducing the temporary overlay fields the compiler now emits is the next phase,
**AWC P2.1**.
