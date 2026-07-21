# TAP-E3 — Architecture

## Relationship Truth boundary (explicit)

TAP-E3 is **a provenance-preserving semantic relationship extraction, normalization,
conflict-detection, and uncertainty-representation layer.**

"Truth" in *Relationship Truth* does **not** mean metaphysical or universal truth. It
means a **faithful representation of the relationship asserted, qualified, negated,
alleged, conditioned, or contradicted by the retrieved evidence.** TAP-E3 validates the
*representation* of evidence relationships; it does **not** independently verify the
real-world correctness of the source.

TAP-E3 **may** represent "Policy A applies to contractors" (a relationship found in
evidence). It **must not** decide "Policy A is the controlling policy for this contractor
in this situation" (Governance Truth), nor whether a final claim is justified (Claim
Truth), nor answer the user.

### What "Relationship Truth" includes and does not mean

*Relationship Truth* = **faithful, provenance-preserving representation of the relationship
expressed by retrieved evidence.** It **includes** preserving: who/what is the subject;
what predicate is asserted; who/what is the object; direction; negation; modality;
attribution; temporality; scope; conditions; exceptions; conflicts; and uncertainty.

It does **not** mean any of: independent factual verification · source-reliability
adjudication · governance applicability · legal interpretation · final claim truth ·
response validation. Those responsibilities belong to later TAP layers (Governance Truth,
Claim Truth, Response Truth) — see the "Relationship Representation Is Not Source
Verification" section of the EXPERIMENT_REPORT.

## Position in the stack

```
IntentRecord (TAP-E1) ┐
                       ├─► TAP-E3 Relationship Truth ─► RelationshipRecord
RetrievalRecord (E2) ──┘
```

TAP-E1 and TAP-E2 are imported through their public interfaces only and are never
modified. TAP-E3 does not retrieve, mutate evidence, or repair upstream gaps; it
preserves upstream retrieval gaps.

## Pipeline — fifteen typed stages

1. Input validation — reject non-`IntentRecord` / non-`RetrievalRecord`.
2. Evidence-unit normalization.
3. Entity/concept candidate detection (deterministic, from each unit's known entities).
4. Predicate candidate detection (bounded lexicon).
5. Direction resolution (active/passive; by-agent → subject).
6. Polarity detection (negation never discarded).
7. Modality detection (`must`≠`may`; attribution→`ALLEGED`).
8. Temporal & scope extraction (dates, supersession, historical, geography/env/role).
9. Condition & exception extraction (`if …`, `except …`).
10. Relationship normalization (entity + ontology normalization).
11. Cross-evidence consolidation (merge true duplicates; preserve all sources).
12. Conflict detection (polarity/modality/value/ontology, with scope+temporal guards).
13. Confidence assignment (multidimensional; band floored by the minimum component).
14. Gap detection (co-occurrence, ambiguity, unsupported inference, upstream preservation).
15. `RelationshipRecord` generation.

An **append-only processing trace** records the stages executed; intermediate
transformations are not hidden. Each stage is independently testable.

## Deterministic-first

The extractor uses lexical predicate maps, passive-voice normalization, negation/modal/
temporal markers, conjunction/exception patterns, deterministic entity matching, and
explicit tie-breaking (all sorts break ties on stable keys). No model-based interpreter
is used in this phase; if one is added later it must sit behind the baseline abstraction
and be compared against the deterministic baseline. No semantic intelligence is claimed
beyond what is implemented.
