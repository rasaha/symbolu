# GOVERNANCE_STATUS_MODEL — Governance Semantics Experiment v0.1

Every clause the layer considers receives exactly one explicit, machine-readable
status. The result is not encoded through node ordering alone; it is an explicit
`GovernanceResult` with status maps, role sets, a decision trace, and per-node
evidence vectors.

## Statuses
| status | meaning |
|---|---|
| `OPERATIVE` | carries the term needed to answer the query; the frozen packet reads from it |
| `APPLICABLE_SUPPORT` | remains applicable and supports the decision, but is not the operative source |
| `CUMULATIVE_REQUIREMENT` | imposes an additional obligation (e.g. a penalty) that stacks with the operative source |
| `DISPLACED` | superseded / discarded within scope; does not independently govern |
| `EXCEPTION` | an exception that applies only within its scope; the general rule stands outside it |
| `CONDITIONALLY_APPLICABLE` | applies outside a documented conflict/override scope |
| `UNRESOLVED` | part of an unresolved competition (drives governance abstention) |
| `IRRELEVANT_TO_QUERY` | present in the graph but not bearing on the requested decision |

## Role sets (a node may appear in more than one)
- `applicable_nodes` — the governing set (pinned to the frozen governing set).
- `displaced_nodes` — the frozen discarded set (annotated `DISPLACED`).
- `operative_nodes` — the node(s) the frozen packet should read (usually one).
- `cumulative_nodes` — additional obligation carriers (penalty).
- `conditional_nodes` — scoped/parallel applicability annotations.
- `unresolved_competitions` — conflicting operative outcomes forcing abstention.

## Decision trace
An ordered list of human-readable steps (e.g. `governing=3 prohib=1 allow=1`,
`abstain: conflicting operative terms in the governing set`,
`operative=<key> signal=prohibited frozen_primary=<key>`). Every operative choice and
every abstention names its cause, so no decision is an unexplained scalar.

## Evidence vectors
For each governing node, a decomposable vector: `relationship_out`,
`incoming_displacement`, `authority_order`, `operative_signal`,
`carries_operative_term`, `confidence`, `provenance_complete`. Decisions read these
components categorically/lexicographically; they are never collapsed into one opaque
probability.

## What the status model does NOT change
The governing SET reported for Mode G equals the frozen set. Statuses are richer
annotations over that set; the only status that changes the full-pipeline answer is
`OPERATIVE` (which node the packet reads) and the abstention flag. This keeps governance
Mode G, discovery, classification, and packet Mode P bit-identical to the control.
