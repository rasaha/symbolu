# RELATIONSHIP GRAPHS — Minimum structure to solve each unresolved case

For every RETRIEVAL-INSUFFICIENT case, the minimum relationship graph a solver
must construct *over already-retrieved spans*. Nodes are spans/documents; edges
are typed relationships. "Graph reasoning required" = solving needs edges +
traversal, not just node presence. (`conflicting_tables` and `hidden_negation`
need a logical operator rather than a multi-node graph.)

Retrieval delivers the **nodes**. None of these cases are solved by nodes alone;
each needs the **edges/operators**, which retrieval does not produce.

## order_of_precedence — precedence reasoning (graph required)
```
[MSA §7.1  "…ninety (90) days…"] ──governed_by──▶ [Order Form §2  "…thirty (30)…"]
                                                     ▲
                        [Order Form §2 "the Order Form governs over the MSA"] ─┘ (precedence edge)
```
Solve = apply the explicit `governs_over` edge → answer follows the Order Form (30 days).
Retrieval gives all three spans; the `governs_over` edge is the missing piece.

## inconsistent_numbering — precedence + normalisation (graph required)
```
[MSA §7.1] ──alias(7.1 ≡ 7.01)──▶ [Amendment 5 §7.01] ──superseded_by──▶ (governs)
```
Solve = normalise the section identifiers, then apply supersession → 45 days.
Two edges (normalisation + supersession); retrieval supplies neither.

## policy_override — policy reasoning / cross-document governance (graph required)
```
[MSA §7.1  "…may terminate…"] ──overridden_by──▶ [Policy GOV-12  "notwithstanding any contract term"]
```
Solve = apply `overridden_by` → termination prohibited. Policy span is retrieved;
the override edge is not a span.

## conflicting_versions — version reasoning (graph required)
```
[Amendment 3 (v1) "…may terminate…"] ──conflicts_with──▶ [Amendment 3 (v2) "Neither party may…"]
                         └────────── requires: version/authority selector ──────────┘
```
Solve = select the authoritative version (needs version metadata) or, absent it,
**abstain**. Retrieving both spans yields ambiguity, not a decision.

## circular_reference — cross-document reconciliation (graph required)
```
[MSA §7  "fee defined in Schedule C"] ──defined_in──▶ [Schedule C  "fee as defined in MSA §7"]
        ▲──────────────────────────── defined_in ───────────────────────────────┘   (cycle)
```
Solve = detect the cycle → the value has no ground term → **abstain**. Retrieval
follows pointers forever; it cannot detect the cycle.

## hidden_negation — logical operator (no graph; single node)
```
[MSA §7.1  "In no event may either party terminate for convenience"]
                     └─ apply negation/polarity operator ─┘
```
Solve = read the polarity of one complete span. Evidence is already complete;
retrieval cannot correct a negation error.

## conflicting_tables — logical contradiction (2 nodes, consistency operator)
```
[MSA §7.3 prose  "three (3) months"] ──contradicts──▶ [Exhibit B table  "six (6) months"]
                      └─ apply contradiction / representation-precedence operator ─┘
```
Solve = detect the numeric contradiction and resolve/flag it. Both spans
retrieved; the contradiction operator is missing.

## Summary
| Case | Edge/operator required | Graph reasoning? |
|---|---|---|
| order_of_precedence | governs_over | yes |
| inconsistent_numbering | alias + superseded_by | yes |
| policy_override | overridden_by | yes |
| conflicting_versions | conflicts_with + version selector | yes |
| circular_reference | defined_in cycle detection | yes |
| hidden_negation | negation operator | no (logical) |
| conflicting_tables | contradiction operator | partial (2-node) |

Common thread: every unresolved case needs an **operation over spans** (typed
edge, traversal, cycle detection, polarity, contradiction). Retrieval produces
the operands; it does not produce the operation.
