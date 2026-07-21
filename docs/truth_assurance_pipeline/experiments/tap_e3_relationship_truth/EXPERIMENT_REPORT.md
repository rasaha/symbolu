# TAP-E3 — Relationship Truth — Experiment Report

> **Research & falsification phase.** Third TAP layer. Relationship extraction /
> normalization / conflict-detection / uncertainty-representation only. TAP-E1 and
> TAP-E2 are frozen upstream baselines, consumed through their public interfaces and
> never modified.

Code: [`truth_assurance_pipeline/tap_e3_relationship_truth/`](../../../../truth_assurance_pipeline/tap_e3_relationship_truth/)
· Results: [`experiments/results_v3.json`](../../../../truth_assurance_pipeline/tap_e3_relationship_truth/experiments/results_v3.json)
· Prereg: [`experiments/preregistration.json`](../../../../truth_assurance_pipeline/tap_e3_relationship_truth/experiments/preregistration.json)
· Companions: [ARCHITECTURE](./ARCHITECTURE.md) · [ONTOLOGY](./ONTOLOGY.md) · [SCHEMA](./SCHEMA.md) · [CORPUS](./CORPUS.md) · [METRICS](./METRICS.md) · [FAILURE_ANALYSIS](./FAILURE_ANALYSIS.md) · [LEAKAGE_AUDIT](./LEAKAGE_AUDIT.md)

> **Evaluation protocol (read first).** The eval split was content-hash locked and the
> configuration preregistered, but eval outputs were inspected during iterative
> engineering. This is a **locked development evaluation, not an untouched or
> interpreter-blind holdout** (not double-blind). See LEAKAGE_AUDIT.

---

## 1. Objective & boundary

Determine **what relationship each retrieved evidence unit actually establishes** between
the relevant entities — distinguishing co-occurrence from an asserted relationship,
explicit from inferred, positive from negated, current from superseded, direct from
conditional, supported from ambiguous, and source assertion from platform judgment.

TAP-E3 does **not** decide final claim truth, governance applicability, authorization, or
answer the user (see ARCHITECTURE §"Relationship Truth boundary"). "Truth" here means a
**faithful representation of the relationship asserted, qualified, negated, alleged,
conditioned, or contradicted by the evidence** — not metaphysical truth, and not
verification of the source's real-world correctness.

## 2. Inputs / output

Consumes an `IntentRecord` (TAP-E1) and a `RetrievalRecord` (TAP-E2). It does not
retrieve, mutate evidence, or repair upstream gaps — upstream retrieval gaps are
preserved. Produces a versioned `RelationshipRecord` of `RelationshipAssertion`s (with
direction, polarity, modality, temporality, scope, conditions, exceptions, explicitness,
per-unit provenance, and a multidimensional confidence vector), plus
`RelationshipConflict`s, `RelationshipGap`s, and an append-only processing trace.

## 3. Pipeline & determinism

Fifteen typed stages (see ARCHITECTURE), deterministic-first: a bounded predicate
lexicon, passive-voice normalization, negation/modal/temporal markers, condition/
exception patterns, and deterministic entity matching (using each evidence unit's known
entities). No model-based interpreter in this phase. Output is byte-identical across
runs (a test enforces this).

## 4. Ontology & schema

A compact, versioned ontology (`tap-e3-ontology/1.0.0`) of **49 relationship types**
across six families with documented inverses (see ONTOLOGY). The versioned
`RelationshipRecord` schema (`tap-e3-relationship/1.0.0`) represents every dimension
separately — never collapsed into a binary (see SCHEMA).

## 5. Corpus

A **new, independently authored** synthetic corpus (see CORPUS): **14 evidence documents
/ 32 evidence units / 29 cases** (dev 17, eval 12) spanning direct/passive/negation/
modality/conditional/exception/supersession/conflict/co-occurrence/attribution/
coordination/historical/scope/duplicate/upstream-gap families. TAP-E2 query annotations
are **not** reused as relationship gold; gold allows ontology-equivalent predicates and
multiple normalized forms.

## 6. Baselines

A co-occurrence · B predicate-keyword · C +normalization(active/passive, ontology,
direction) · D +polarity/modality · E +temporality/scope/conditions/exceptions ·
**F full** (+consolidation, conflict, confidence, gaps, provenance, trace).

## 7. Results — locked eval (12 cases)

| metric | A | B | C | D | E | **F** |
|---|---|---|---|---|---|---|
| relationship_f1 | 0.00 | 0.95 | 0.95 | 0.95 | 0.95 | **0.95** |
| predicate_accuracy | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| direction_accuracy | 0.91 | 0.90 | 1.00 | 1.00 | 1.00 | **1.00** |
| polarity_accuracy | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | **1.00** |
| modality_accuracy | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | **1.00** |
| temporality_accuracy | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | **1.00** |
| exact_triple_accuracy | 0.00 | 0.90 | 1.00 | 1.00 | 1.00 | **1.00** |
| full_structure_accuracy | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | **1.00** |
| provenance_completeness | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| conflict_detection_f1 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** |
| gap_detection_accuracy | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | **1.00** |
| cooccurrence_false_positive_rate | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | **0.00** |
| unsupported_relationship_rate | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | **0.00** |
| **severe_critical_failure_count** | 8 | 3 | 2 | 2 | 1 | **0** |

(relationship_f1 caps at 0.95 because one eval sentence — "Engineers should review the
design document" — uses a verb outside the bounded lexicon and yields no assertion; an
honest recall miss, above the 0.80 gate.)

### Preregistered gates — selected config F (locked eval)

| gate | value | threshold | pass |
|---|---|---|---|
| relationship_f1 ≥ 0.80 | 0.95 | 0.80 | ✅ |
| predicate_accuracy ≥ 0.85 | 1.00 | 0.85 | ✅ |
| direction_accuracy ≥ 0.90 | 1.00 | 0.90 | ✅ |
| polarity_accuracy ≥ 0.95 | 1.00 | 0.95 | ✅ |
| modality_accuracy ≥ 0.85 | 1.00 | 0.85 | ✅ |
| provenance_completeness == 1.00 | 1.00 | 1.00 | ✅ |
| conflict_detection_f1 ≥ 0.75 | 1.00 | 0.75 | ✅ |
| gap_detection_accuracy ≥ 0.75 | 1.00 | 0.75 | ✅ |
| cooccurrence_false_positive_rate ≤ 0.10 | 0.00 | 0.10 | ✅ |
| unsupported_relationship_rate ≤ 0.10 | 0.00 | 0.10 | ✅ |
| severe_critical_failure_count == 0 | 0 | 0 | ✅ |

**Selection:** the simplest baseline satisfying **all** gates on the dev split. Only **F**
does — the conflict-detection and severe-failure gates require the consolidation/conflict
stage, and gap detection requires E-level extraction. This is a genuine necessity of the
preregistered gates for this corpus, not an assumption that "complex wins"; simpler
baselines each fail specific gates (see below).

## 8. Critical failures (independent; Section 19)

| failure | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| DIRECTION_REVERSED | 1 | 1 | 0 | 0 | 0 | 0 |
| AUTHORIZATION_INVERTED | 2 | 0 | 0 | 0 | 0 | 0 |
| PROHIBITION_DROPPED | 2 | 0 | 0 | 0 | 0 | 0 |
| CONFLICT_HIDDEN | 1 | 1 | 1 | 1 | 1 | 0 |
| UNSUPPORTED_RELATIONSHIP_EMITTED | 1 | 0 | 0 | 0 | 0 | 0 |
| UPSTREAM_GAP_IGNORED | 1 | 1 | 1 | 1 | 0 | 0 |
| **total severe** | **8** | **3** | **2** | **2** | **1** | **0** |

The ladder is honest: co-occurrence (A) invents relationships and inverts authorization;
predicate-keyword (B) reverses passives; conflict-hiding persists until consolidation (F);
upstream-gap-ignoring persists until the gap stage (E). See FAILURE_ANALYSIS.

## 9. Limitations

- Small synthetic corpus (32 units / 29 cases); mechanism/construction validation only.
- **Deterministic, pattern-based extraction over sentences authored to be parseable** —
  not general NLU. Entity detection uses each unit's known entities, not open NER.
- A bounded predicate lexicon: out-of-lexicon verbs yield no assertion (visible as the
  0.95 recall).
- Locked **development** evaluation, inspected during iteration (not an untouched
  holdout).
- No model-based interpreter in this phase (kept behind the baseline abstraction for
  future comparison).

## 10. Verdict

**`PASS_WITH_LIMITED_CLAIM`.** All eleven preregistered gates pass for the selected
baseline (F) on the locked eval split. **Supported claim:** *TAP-E3 demonstrates a
deterministic, provenance-preserving architecture for extracting and normalizing
evidence-stated relationships — including direction, polarity, modality, temporality,
scope, conditions, exceptions, conflicts, and unresolved gaps — on the synthetic corpus
used in this study.* It does **not** claim production semantic understanding or external
generalization.

## 11. Frozen interface & recommendation for TAP-E4

The `RelationshipRecord` schema (`tap-e3-relationship/1.0.0`) is the **provisional frozen
interface** for downstream TAP research; future work compares against it and changes it
only if TAP-E4 exposes a genuine interface deficiency (via explicit schema versioning).

**Next layer: TAP-E4 — Governance Truth.** It should consume `IntentRecord`,
`RetrievalRecord`, and `RelationshipRecord`, and determine **which documented rules,
authorities, policies, versions, jurisdictions, exceptions, and temporal conditions
govern the current situation** — e.g. taking a represented `APPLIES_TO` relationship (and
its scope/temporality/supersession) and deciding whether that policy is the *controlling*
one here. TAP-E4 must not be implemented as part of this task.
