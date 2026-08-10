# TAP — Confidence Model v0.1

Confidence is **multidimensional**. A single scalar is explicitly rejected.
Architecture-only.

> Boundary: `12_RESEARCH_BOUNDARIES.md`.

---

## 1. Why not a scalar

A single number hides *why* the system is (un)certain and prevents a layer from
being independently evaluated. TAP carries a **vector** whose dimensions map to
distinct, separately-measurable sources of (un)certainty.

## 2. Dimensions

```
ConfidenceVector = {
    relationship_confidence,     # Layer 1: is the relationship supported?
    governance_confidence,       # Layer 2: is applicability/operative-source certain?
    claim_confidence,            # Layer 4: is the claim supported by the packet?
    response_confidence,         # Layer 5: is the whole answer faithful?
    evidence_completeness,       # Layer 3: is the packet complete & minimal?
    judge_agreement,             # do advocate/challenger agree? (06_)
    deterministic_certainty      # did a deterministic validator settle it? (07_)
}
```

Each dimension is in `[0,1]` (or an explicit `N/A`), **owned by exactly one layer**
(except judge_agreement and deterministic_certainty, which are cross-cutting).

## 3. Rules

1. **No aggregation into a headline number** for decision-making. Layers act on the
   relevant dimension(s), not on an average. (An average may be *displayed* but never
   *decided upon*.)
2. **Deterministic certainty dominates.** When `deterministic_certainty = 1` for a
   check, judge-derived dimensions do not override it (`07_…`).
3. **Missing ≠ low.** A dimension that does not apply is `N/A`, not `0`; a dimension
   with no evidence is explicitly `insufficient`, distinct from `contradicted`.
4. **Confidence is provenance-backed.** Each dimension's value points at the spans /
   decisions that produced it (`04_…`).

## 4. Interaction with abstention

Abstention (`09_…`) is triggered by *specific* dimensions, not a scalar threshold:
- low `evidence_completeness` → packet/claim abstention;
- unresolved `governance_confidence` on a genuine conflict → governance abstention;
- `judge_agreement` low **and** no deterministic resolution → adjudication, then
  possible claim/response abstention.

## 5. Relationship to the existing prototype

The synthetic Layer-4 prototype emits a deterministic per-predicate confidence vector
(supported/ not-applicable/ not-supported/ contradicted → scores) — the
`claim_confidence` and `deterministic_certainty` slices. The other dimensions are
defined here for their owning layers and are future work to populate.
