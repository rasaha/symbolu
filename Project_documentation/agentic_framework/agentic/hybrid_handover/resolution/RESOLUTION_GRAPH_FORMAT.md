# RESOLUTION_GRAPH_FORMAT — Typed Evidence Graph

The interchange format between stages 2 and 3. Explicit typed nodes and edges;
no free text drives governance.

## Node
```python
Node(
  key:     str,        # stable identity — the source citation, e.g. "MSA §7.1 p.12"
  type:    NodeType,   # Clause | Definition | Exception | Policy | Table |
                       # Version | Document | Section
  doc_id:  str,
  text:    str,        # the span text realising the node
  section: str | None, # normalised section id, e.g. "7.1" (7.01 → 7.1)
  attrs:   dict,       # notice_days, penalty_months, negation, allows,
                       # references, supersede_target, governs_over_target,
                       # policy_override, introduces_fee, definition_term,
                       # unusable, version_base, terminates, order
)
```

## Edge
```python
Edge(
  src:  str,       # Node.key
  type: EdgeType,  # defines | references | overrides | supersedes | governs_over |
                   # exception_to | conflicts_with | same_as | effective_after |
                   # effective_before | amends | contains
  dst:  str,       # Node.key  (or a dangling reference string, e.g. "Appendix 1")
  attrs: dict,     # e.g. {"dangling": True}
)
```
An edge is identified by its typed triple `(src, type, dst)` — the unit of
Relationship Edge Precision/Recall.

## Graph
```python
ResolvedEvidenceGraph(nodes: list[Node], edges: list[Edge])
```

## Worked examples (from the gold graphs)
```
later_amendment_override
   (Amendment 4 §3, supersedes, MSA §7.1)   (Amendment 6 §2, amends, MSA §7.1)

order_of_precedence
   (Order Form §2, governs_over, MSA §7.1)

policy_override
   (Corporate Policy GOV-12, overrides, MSA §7.1)

inconsistent_numbering
   (Amendment 5 §7.01, same_as, MSA §7.1)   (Amendment 5 §7.01, supersedes, MSA §7.1)

conflicting_definitions
   (DPA §1, conflicts_with, MSA §1)

conflicting_versions
   (Amendment 3 v1, same_as, Amendment 3 v2)  (Amendment 3 v1, conflicts_with, Amendment 3 v2)

circular_reference
   (MSA §7, references, Schedule C)   (Schedule C, references, MSA §7)      ← cycle

missing_appendix
   (MSA §7.3, references, "Appendix 1")                                     ← dangling
```

## Design notes
- **Identity, not text.** Reference edges resolve to a target's `key` (citation),
  never by matching a mention in some other node's text — this prevents fabricated
  back-edges and false cycles.
- **Dangling / phantom `dst`.** A reference whose target is not a node keeps the
  raw reference string as `dst` with `attrs.dangling = True`; governance treats it
  as grounds for abstention.
- **Section normalisation.** `section` is normalised (`7.01 → 7.1`) so alias
  relationships (`same_as`) are detectable.
- **Determinism.** Node order follows first appearance in the evidence; edge
  construction is order-stable — the graph is byte-reproducible.
