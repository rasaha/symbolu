# TAP — Provenance Model v0.1

A single provenance object that **survives every layer** and is **append-only**.
Architecture-only.

> Boundary: `12_RESEARCH_BOUNDARIES.md`.

---

## 1. Principle

**Every layer appends provenance; no layer replaces it.** The provenance object is
the end-to-end audit trail from user request to final response. A truth claim with no
provenance is inadmissible.

## 2. Fields (sketch)

```
Provenance = {
    request_id,
    source_ids: [],                 # documents / systems consulted
    document_spans: [],             # cited spans, with offsets
    relationship_path: [],          # Layer 1 verdicts that were used
    governance_path: [],            # Layer 2 operative source / supersession chain
    claim_ids: [],                  # Layer 4 claims and their records
    validation_decisions: [],       # per-layer decisions (status, action, reason)
    confidence_dimensions: {},      # snapshots of the ConfidenceVector per layer
    abstentions: [],                # any layer's abstention, with reason
    repair_history: [],             # localized repairs applied (08_)
    layer_seq: []                   # ordered list of layers that touched the object
}
```

## 3. Append-only discipline

- Each layer method returns `prov' = append(prov, its_contribution)`.
- Entries are immutable once written; a correction is a **new** entry (a repair,
  `08_…`), never an edit.
- `layer_seq` records the order of touches so the trail is reconstructable.

## 4. What each layer contributes

| Layer | Appends |
|---|---|
| Intent | scoped query, captured constraints |
| Retrieval | source_ids, candidate spans, retrieval scores |
| Layer 1 (relationship) | relationship_path (validated/rejected/uncertain + spans) |
| Layer 2 (governance) | governance_path (operative source, supersession, exceptions) |
| Layer 3 (packet) | the minimal evidence set + provenance coverage marker |
| Layer 4 (claim) | claim_ids, per-claim validation_decisions, claim confidence |
| Layer 5 (response) | response edits/qualifications, faithfulness decisions |
| Safety/Policy | admissibility decision (out of TAP scope) |

## 5. Provenance completeness as an evaluation target

Provenance coverage is itself measurable (`10_…`): the fraction of final-response
assertions traceable to a source span through an unbroken relationship→governance→
packet→claim chain. Incompleteness is a defect attributable to a specific layer.

## 6. Relationship to the existing prototype

The synthetic Layer-4 prototype (`relationship_claim_validation/`) already emits a
per-claim evidence record with supporting/contradicting spans and missing predicates
— the Layer-4 slice of this provenance object. The cross-layer object here
generalizes that pattern to all layers; building it end-to-end is future work
(`11_…` Cross-Layer Provenance Experiment).
