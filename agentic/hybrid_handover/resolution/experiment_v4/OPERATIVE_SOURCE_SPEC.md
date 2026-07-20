# OPERATIVE_SOURCE_SPEC — Governance Semantics Experiment v0.1

The central hypothesis of this experiment is that the **authority-establishing node**
and the **answer-bearing node** may differ, and that the frozen packet fails when it
reads the answer from the authority node instead of the operative node. This spec
defines the three roles and how the operative source is chosen.

## Three roles (may point to different nodes)
- **Governance source** — the node that establishes authority or applicability (the
  source of a `supersedes` / `overrides` / `governs_over` edge). This is what the frozen
  packet's `primary` rule latches onto.
- **Operative source** — the governing node that actually carries the term required to
  answer the query (the termination-for-convenience signal: prohibition or permission,
  and its notice/penalty). This is what SHOULD determine the answer.
- **Supporting source** — a node required to justify the relationship or decision but not
  itself operative (e.g. an authority node with no operative term, or a reference target).

## Selection rule (deterministic)
Among the frozen governing nodes:
1. If both a prohibition and a permission are present → no single operative source is
   safe → governance abstention (see GOVERNANCE_ABSTENTION_SPEC.md).
2. Else if any node carries a prohibition (`policy_override`/`negation`/`Policy`) → the
   latest such node is operative.
3. Else if any node carries a permission (`allows`) → the latest such node is operative.
4. Else if any node carries a secondary operative term (`notice_days`/`penalty_months`) →
   the latest such node is operative.
5. Else → abstain (authority known, operative term not locatable), or fall back to the
   frozen primary when abstention is disabled (G1–G3).

"Latest" = highest parsed document `order`. The rule deliberately does **not** assume the
highest-authority node is operative — that is exactly the v0.3 failure mode this
experiment targets.

## Realizing the choice within the frozen contract
The frozen packet accepts one `primary` node and derives one answer from it. The adapter
(GOVERNANCE_SEMANTICS_ARCHITECTURE.md) orders the operative node first and withholds
competing governance-source edges from the packet-input graph, so the frozen `primary`
rule lands on the operative node. The packet still computes tfc/notice/penalty from that
node's own attributes — the layer selects the source, never the answer text.

## Information loss (documented)
Where authority and operative sources differ, the adapter can express only a single
operative node to the frozen packet. If two operative sources are genuinely required
(cumulative conflicting operatives), the layer abstains rather than emit a lossy single
answer. Penalty stacking is the one cumulative channel the frozen packet already supports
and is preserved.

## What is measurable
Gold "operative-source" labels are not present in the frozen annotations, so
operative-source accuracy is not directly scorable; the observable proxy is whether the
operative choice yields a correct full-pipeline answer (selective accuracy) and the
per-case competing-authority analysis (COMPETING_AUTHORITY_ANALYSIS.md). This limitation
is reported, not worked around.
