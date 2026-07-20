# Failure Attribution Report — Table 12 (hidden pilot)

Each incorrect case is attributed to exactly one PRIMARY stage, in fixed priority
order (discovery incompleteness → over-proposal → classification → governance →
packet). Counts are cases, not edges.

| primary failure stage | graph | hybrid |
|---|---|---|
| governance_application | 8 | 9 |
| packet_realization | 0 | 12 |
| relationship_classification | 2 | 1 |
| relationship_discovery | 50 | 33 |
| relationship_discovery_overproposal | 0 | 1 |

The dominant residual failure for both resolvers is **relationship discovery**
(edges still missed): the hybrid raises recall from 0.18 to 0.42 but the majority
of hidden edges remain undiscovered, so discovery is where the next research
effort should concentrate. Governance- and packet-attributed failures are shared
identically with GraphTraversal (inherited via the frozen reuse), so they are not
the hybrid's to fix. Over-proposal is the primary stage for only one case but
depresses aggregate precision across many — a precision-focused proposal gate is
the clearest single improvement for a follow-up.
