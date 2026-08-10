# TAP-E3 — Relationship Analysis — Experiment Report

> **Naming note.** This layer's canonical engineering name is used throughout. **Previously referred to as Relationship Truth.** For reproducibility, the package directory `tap_e3_relationship_truth/`, the schema-version prefix `tap-e3-relationship/…`, experiment IDs, and stored artifacts retain the original name — see `01_TRUTH_ASSURANCE_ARCHITECTURE.md` §2a.


> **Research & falsification phase.** Third TAP layer. Relationship extraction /
> normalization / conflict-detection / uncertainty-representation only. TAP-E1 and
> TAP-E2 are frozen upstream baselines, consumed through their public interfaces and
> never modified.

Code: [`truth_assurance_pipeline/tap_e3_relationship_truth/`](../../../../truth_assurance_pipeline/tap_e3_relationship_truth/)
· Results: [`experiments/results_v3.json`](../../../../truth_assurance_pipeline/tap_e3_relationship_truth/experiments/results_v3.json)
· Prereg: [`experiments/preregistration.json`](../../../../truth_assurance_pipeline/tap_e3_relationship_truth/experiments/preregistration.json)
· Companions: [ARCHITECTURE](ARCHITECTURE.md) · [ONTOLOGY](ONTOLOGY.md) · [SCHEMA](SCHEMA.md) · [CORPUS](CORPUS.md) · [METRICS](METRICS.md) · [FAILURE_ANALYSIS](FAILURE_ANALYSIS.md) · [LEAKAGE_AUDIT](LEAKAGE_AUDIT.md)

> **Evaluation protocol (read first).** For the recorded run the eval split was
> **content-hash locked** and the **ontology, normalization rules, metric definitions, and
> baseline configuration were frozen**. However, **evaluation outputs were inspected during
> iterative engineering and debugging, and implementation changes followed some observed
> evaluation failures** (e.g. unit-level co-occurrence gap handling, predicate-lexicon
> additions such as `depended on`, historical-dependency handling, cross-segment subject
> inheritance, consolidation-key behavior, numeric value extraction for conflict detection,
> deterministic tie-breaking, and test-data corrections). These are ordinary iterative
> mechanism development, not misconduct — but they mean the reported evaluation is a
> **locked *development* evaluation, not an untouched independent holdout**, and it was
> **not interpreter-blind or double-blind**. The verdict (`PASS_WITH_LIMITED_CLAIM`) and
> all numeric results are unchanged by this disclosure. See LEAKAGE_AUDIT.

---

## 1. Objective & boundary

Determine **what relationship each retrieved evidence unit actually establishes** between
the relevant entities — distinguishing co-occurrence from an asserted relationship,
explicit from inferred, positive from negated, current from superseded, direct from
conditional, supported from ambiguous, and source assertion from platform judgment.

TAP-E3 does **not** decide final claim truth, governance applicability, authorization, or
answer the user (see ARCHITECTURE §"Relationship Analysis boundary"). "Truth" here means a
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

Display labels below make the metric denominators explicit. The stored result keys in
`results_v3.json` are unchanged for reproducibility (`exact_triple_accuracy`,
`full_structure_accuracy`, `predicate_accuracy`, …); this table uses clearer *display*
names for the conditional (matched-only) metrics — see the denominator note under the
table and [METRICS](METRICS.md).

| metric (display label) | A | B | C | D | E | **F** |
|---|---|---|---|---|---|---|
| relationship_f1 *(end-to-end)* | 0.00 | 0.95 | 0.95 | 0.95 | 0.95 | **0.95** |
| relationship_recall *(end-to-end)* | 0.00 | 0.91 | 0.91 | 0.91 | 0.91 | **0.91** |
| matched_predicate_accuracy | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| direction_accuracy *(matched)* | 0.91 | 0.90 | 1.00 | 1.00 | 1.00 | **1.00** |
| polarity_accuracy *(matched)* | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | **1.00** |
| modality_accuracy *(matched)* | 0.00 | 0.00 | 0.00 | 1.00 | 1.00 | **1.00** |
| temporality_accuracy *(matched)* | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | **1.00** |
| matched_triple_accuracy | 0.00 | 0.90 | 1.00 | 1.00 | 1.00 | **1.00** |
| matched_full_structure_accuracy | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | **1.00** |
| provenance_completeness | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| conflict_detection_f1 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** |
| gap_detection_accuracy | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | **1.00** |
| cooccurrence_false_positive_rate | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | **0.00** |
| unsupported_relationship_rate | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | **0.00** |
| **severe_critical_failure_count** | 8 | 3 | 2 | 2 | 1 | **0** |

**Metric denominators — do not read the matched-only metrics as end-to-end accuracy.**
`relationship_precision/recall/f1` are **end-to-end detection** metrics: recall penalizes
every missing gold relationship. The triple / full-structure / predicate accuracies are
computed **only over successfully matched predicted↔gold pairs**:

```
relationship_recall        = correctly recovered gold relationships ÷ all gold relationships
matched_triple_accuracy    = correct subject–predicate–object triples ÷ number of matched pairs
matched_full_structure_acc = fully-correct assertions (all dimensions) ÷ number of matched pairs
```

So a **perfect matched-structure score does not mean every gold relationship was
recovered.** In this run `relationship_recall = 0.91` and `f1 = 0.95` because one eval
sentence — "Engineers should review the design document" — uses a verb outside the bounded
lexicon and yields **no** assertion (an honest recall miss, above the 0.80 gate); yet
every *matched* assertion is structurally correct, so `matched_triple_accuracy` and
`matched_full_structure_accuracy` are 1.00. The two families measure different things and
must not be conflated.

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

## 9a. Relationship Representation Is Not Source Verification

TAP-E3 determines **what relationship the retrieved evidence asserts, qualifies, negates,
alleges, conditions, supersedes, or contradicts.** It does **not** determine whether the
source's assertion is factually true in the real world, which source is authoritative, or
which rule governs the current case.

- **Attribution.** Evidence "The audit alleges that Vendor A caused the outage." → E3
  preserves attribution and modality (`Vendor A --CAUSES--> outage`, **modality: ALLEGED**,
  attributed to the audit). E3 must **not** silently convert this into an unqualified
  real-world fact (`Vendor A --CAUSES--> outage`, asserted). The `ALLEGATION_TREATED_AS_FACT`
  critical guards this.
- **Governance.** Evidence "Policy A applies to contractors." → E3 may represent
  `Policy A --APPLIES_TO--> contractors`. It must **not** yet decide "Policy A is the
  controlling policy for this contractor in the current case" — that is **TAP-E4 Governance
  Resolution**.
- **Historical.** Evidence "System A previously depended on Library B." → E3 preserves
  `DEPENDS_ON` with **temporality: HISTORICAL**; it must **not** present the dependency as
  current. The `SUPERSEDED_RELATION_TREATED_AS_CURRENT` critical guards this.

Conflict detection identifies **incompatible evidence-stated relationships**; it does **not
adjudicate which source wins.** For "passwords must be ≥12 characters" vs "≥14 characters"
E3 emits a `VALUE_CONFLICT` and stops there — authority hierarchy, applicability,
supersession control, jurisdiction, and governing-rule selection belong to TAP-E4.

## 10. Verdict

**`PASS_WITH_LIMITED_CLAIM`.** All eleven preregistered gates pass for the selected
baseline (F) on the locked eval split.

**Supported claim.** *TAP-E3 demonstrates a deterministic, provenance-preserving
architecture for extracting and normalizing relationships expressed by retrieved evidence,
including direction, polarity, modality, temporality, scope, conditions, exceptions,
conflicts, attribution, and unresolved gaps, on the synthetic corpus used in this study.*

*This experiment does not independently establish production-grade semantic understanding,
real-world factual correctness, or external generalization.* In particular, TAP-E3 does
**not** verify whether the source itself is true (see §9a).

## 11. Frozen interface & recommendation for TAP-E4

The `RelationshipRecord` schema (`tap-e3-relationship/1.0.0`) is the **provisional frozen
interface** for downstream TAP research. Future work should **consume** it rather than
modify TAP-E3. A schema change should occur **only if TAP-E4 exposes a genuine
architectural deficiency**, and any such change must carry: an explicit schema-version
increment, a migration note, a downstream compatibility analysis, and an explanation of
why the existing interface was insufficient (see SCHEMA).

**Next layer: TAP-E4 — Governance Resolution.** It consumes `IntentRecord`, `RetrievalRecord`,
and `RelationshipRecord`, and determines **which documented rule, authority, policy,
version, jurisdiction, scope, exception, and temporal condition governs the current
situation** — e.g. taking a represented `APPLIES_TO` relationship (with its scope /
temporality / supersession) and deciding whether that policy is the *controlling* one
here. TAP-E4 is **not** implemented in this task.

```
TAP-E1  Intent Analysis
        ↓
TAP-E2  Evidence Retrieval
        ↓
TAP-E3  Relationship Analysis          ← this experiment (frozen interface: RelationshipRecord)
        ↓
TAP-E4  Governance Resolution            ← next layer
        ↓
Evidence Assembly
        ↓
Claim Validation
        ↓
Response Validation
```

## 12. Future validation (goals, not achievements)

None of the following is claimed here; each would be a stronger confirmation than this
study provides:

- larger and more linguistically diverse enterprise corpora;
- independently authored evaluation cases (author ≠ implementer);
- untouched, evaluator-blind holdouts (outputs never inspected during engineering);
- real parser- or model-based relationship extraction (behind the baseline abstraction);
- comparison against established relation-extraction systems on shared benchmarks;
- external replication by another evaluator;
- cross-document coreference resolution;
- longer, less templated evidence passages;
- adversarial attribution, negation, temporal, and exception cases;
- calibration of uncertainty and abstention.

These are future work. Only after independent, blind, and externally-benchmarked
replication should these results be trusted or generalized beyond this synthetic corpus.
