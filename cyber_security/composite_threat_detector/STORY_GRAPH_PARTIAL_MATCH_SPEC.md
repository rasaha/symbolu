# StoryGraph Partial-Match Semantic Specification (matcher/2.0.0)

Formal reference for the corrected partial-match semantics. Advisory only;
deterministic; bounded; known-pattern. Implemented in `storygraph.py`.

## 1. Edge-evaluation states

Every graph edge evaluated during matching returns exactly one state
(`storygraph._edge_state`):

| State | Meaning |
|---|---|
| `SATISFIED` | Both endpoints bound and the condition is proven true. |
| `FAILED` | Both endpoints sufficiently bound and the condition is proven false. |
| `NOT_EVALUABLE` | An endpoint node is absent, or required evidence (e.g. an entity value, an actor) is missing. Never treated as SATISFIED or FAILED. |
| `AMBIGUOUS` | The evidence cannot yield a single reliable conclusion (e.g. an ORDER edge whose endpoints share a coordinate). |

Per-edge report fields (§4): `edge_id, kind, a, b, dim, mandatory,
is_discriminating, state, bound_source, bound_target, detail` (detail carries
`expected`/`observed`/`gap`/`reason`/`missing_nodes` as applicable). Aggregates:
`satisfied_edges, failed_edges, not_evaluable_edges, ambiguous_edges`.

CONTRADICTS: a fired incompatibility → `FAILED` (weakens the harmful hypothesis);
non-fired evaluable → `SATISFIED`; endpoint/entity absent → `NOT_EVALUABLE`.

## 2. Structural-dimension results

Per dimension (ordering, entity, timing, corroboration, contradictions, coverage),
`DimensionResult` reports `satisfied_count, failed_count, not_evaluable_count,
ambiguous_count, applicable_count, status, evaluable_ratio`.

```
applicable == 0                      -> NOT_APPLICABLE   (weight excluded from score)
failed_count > 0                     -> FAILED           (non-compensatory)
satisfied+failed == 0 and amb > 0    -> AMBIGUOUS
satisfied+failed == 0                -> NOT_EVALUABLE     (contributes 0, keeps weight)
satisfied == applicable              -> SATISFIED
otherwise                            -> PARTIAL
evaluable_ratio = satisfied / (satisfied+failed)   or None when none evaluable
```

**The ratio is computed only over evaluable edges and is NEVER 1.0 on a zero
denominator.** The scalar consistency exposed on `RiskVector` is the evaluable ratio
or `0.0`. `harmful_score` sums weighted scalars, excluding `NOT_APPLICABLE`
dimensions from the denominator; `NOT_EVALUABLE` dimensions contribute `0`.

A gate fires only when `evaluable_ratio is not None and evaluable_ratio < gate` —
i.e. only on a genuinely evaluated shortfall, never on absence of tested evidence.

## 3. Completion (non-compensatory)

A harmful graph is complete iff: all required nodes present; a completion node
present; no gate triggered; not unavailable; **no mandatory edge unsatisfied**; no
contradiction fired. A mandatory edge (all endpoint nodes required) that is bound
but `FAILED`/`AMBIGUOUS`/`NOT_EVALUABLE` sets `mandatory_unsatisfied` → not complete.
Weights rank candidate bindings only; they never determine completion.

## 4. Partial-escalation decision table (`ctd.partial_escalation/1.0.0`)

A partial (non-completing) story is `escalation_eligible` iff ALL hold:

```
required_coverage            >= min_required_coverage        (0.60)
discriminating_satisfied     >= min_discriminating_satisfied (1)   # evaluated & SAT
no mandatory edge is FAILED or AMBIGUOUS
( completion_proximity >= min_completion_proximity (0.999)
  OR corroboration.satisfied_count >= 1 )
```

`escalation_eligible` is required for the `THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT`
verdict. Otherwise a partial story yields `PARTIAL_HARMFUL_STORY` (OBSERVE) or
`NO_MATERIAL_PATTERN`. Absence of a benign explanation is not, by itself, harmful
evidence.

## 5. Specificity metadata

`StoryNode.specificity_class ∈ {COMMON, DISCRIMINATING}`; `Edge.is_discriminating`.
Only an evaluated & satisfied discriminating edge counts toward
`discriminating_satisfied`. A common administrative event is not, on its own, strong
harmful-story evidence.

## 6. Versioning

`STORYGRAPH_SCHEMA_VERSION = ctd.storygraph/1.1.0` (node/edge metadata),
`MATCHER_SEMANTICS_VERSION = ctd.storygraph.matcher/2.0.0` (this partial-match
semantics), `PARTIAL_ESCALATION_POLICY_VERSION = ctd.partial_escalation/1.0.0`. All
are bound in `evaluation/freeze.py` and reported on every `StoryMatch`
(`matcher_semantics_version`). Run-1 findings remain reconstructable at commit
`78911a9f` under `ctd.storygraph/1.0.0`.
