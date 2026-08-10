# EDGE_PRIORITY_RULEBOOK — Edge Prioritization Experiment v0.1

The complete, frozen set of deterministic rules the Edge Prioritization layer applies.
Every rule is a pure function of the parsed nodes, the v0.2 validated edges, and the
v0.2 confidence vector. No learned parameters; no randomness; no hidden data used to
author any rule.

## What competes
A **governance source** is a node that is the source of a `supersedes`, `overrides`,
or `governs_over` edge — the frozen packet chooses its `primary` from these. Two or
more governance sources in the same case **compete**: the frozen packet would pick
whichever appears first in node order. Prioritization decides that order.

Cases with fewer than two governance sources have no competition; the layer is a
strict no-op there (the graph, and therefore the frozen governance/packet outcome, is
identical to v0.2).

## How a competition is resolved
1. Compute the priority vector (PRIORITY_VECTOR_SPEC.md) for each competing source.
2. Rank sources by the lexicographic key over the enabled components, order
   `authority > temporal > specificity > reference > structural > confidence >
   support` (descending). Disabled components (per ablation) contribute 0.
3. The top-ranked source is the **winner**; it is placed first among the governance
   sources in the node ordering handed to the frozen governance, so the frozen packet
   selects it as `primary`.
4. For each losing source, record the **decisive component** — the first enabled
   component on which the winner strictly outranks it — as the human-readable reason.

## Rule rationale (general legal reasoning, not corpus-specific)
- **Authority first.** When two instruments both purport to govern, the later /
  higher-authority instrument controls; this is the primary tie-break, mirroring "the
  most recent amendment prevails."
- **Temporal next.** Where authority is equal, the more recent effective date wins.
- **Specificity next.** A relationship aimed at a named section is more determinate
  than one defaulting to the base clause.
- **Reference, structural, support** break residual ties toward the more directly
  governing, more central, better-corroborated source.

## Strict boundary
The layer:
- **never** adds, removes, or retypes an edge (validation owns edge membership);
- **never** runs in Mode G or Mode P (those inject gold structure and call the frozen
  code directly);
- **only** reorders the governance-input graph inside the full `resolve()` pipeline.

Therefore discovery precision/recall, classification, governance Mode G, and packet
Mode P are structurally identical to v0.2, and only the full-pipeline governance
decision — hence selective accuracy, coverage, and unsafe answers — can change.
