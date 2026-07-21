# TAP-E3 — Relationship Truth

The third TAP research layer. Given an `IntentRecord` (TAP-E1) and a `RetrievalRecord`
(TAP-E2) — both consumed through their **frozen public interfaces** — it determines **what
relationship each retrieved evidence unit establishes**, with direction, polarity,
modality, temporality, scope, conditions, exceptions, conflicts, gaps, and per-unit
provenance.

> **"Truth" here is narrow:** a faithful representation of the relationship *asserted,
> qualified, negated, alleged, conditioned, or contradicted by the evidence* — **not**
> metaphysical truth, governance applicability, claim support, or a user answer. TAP-E3
> may represent "Policy A applies to contractors"; it must not decide that Policy A is the
> controlling policy here (Governance Truth), nor whether a final claim is justified (Claim
> Truth).

## Honesty (read first)

- New, independently authored synthetic corpus; TAP-E2 query gold is not reused.
- **Deterministic, pattern-based extraction over sentences authored to be parseable** —
  not general NLU. Entity detection uses each unit's known entities, not open NER.
- The eval split is content-hash locked and preregistered, but was inspected during
  iterative engineering — a **locked development evaluation, not an untouched/interpreter-
  blind holdout** (not double-blind).
- Mechanism/construction validation only — no claim of production semantic understanding
  or external generalization.

## Layout

```
tap_e3_relationship_truth/
├── ontology.py     # 49-type versioned ontology + predicate lexicon + inverses
├── schema.py       # RelationshipRecord/Assertion/Conflict/Gap (all dimensions separate)
├── normalization.py polarity.py modality.py temporality.py   # dimension detectors
├── extractor.py    # 15-stage pipeline + A–F baselines + gap detection + trace
├── conflict.py confidence.py validator.py
├── metrics.py      # per-dimension metrics + independent critical failures
├── harness.py      # E1→E2→E3 driver, dev-only selection, gates, verdict
├── loader.py       # gold-free public loader
├── corpus/         # 14 docs / 32 units / 29 cases (eval locked)
├── experiments/    # runner, preregistration, locks, results
└── tests/
```

## Run

```bash
python -m truth_assurance_pipeline.tap_e3_relationship_truth.experiments.run_experiment
python -m pytest truth_assurance_pipeline/tap_e3_relationship_truth/tests/ -q
```

## Result

Selected baseline **F** (the simplest satisfying all preregistered gates — the conflict/
gap/severe gates require it). All eleven gates pass on the locked eval split; verdict
**`PASS_WITH_LIMITED_CLAIM`**.

**Supported claim (narrow):** a deterministic, provenance-preserving architecture for
extracting and normalizing relationships expressed by retrieved evidence — including
direction, polarity, modality, temporality, scope, conditions, exceptions, conflicts,
attribution, and unresolved gaps — on this study's synthetic corpus. It does **not**
independently establish production-grade semantic understanding, real-world factual
correctness, or external generalization, and does **not** verify whether the source itself
is true.

Note on metrics: `relationship_f1`/`recall` are **end-to-end** (missing gold relationships
lower them); triple/full-structure/predicate accuracies are computed **only over matched
pairs**, so a perfect matched-structure score does not mean full recovery (see
[METRICS](../../docs/truth_assurance_pipeline/experiments/tap_e3_relationship_truth/METRICS.md)).

The `RelationshipRecord` schema is the provisional frozen downstream interface; the **next
layer is TAP-E4 — Governance Truth**. See
[`EXPERIMENT_REPORT.md`](../../docs/truth_assurance_pipeline/experiments/tap_e3_relationship_truth/EXPERIMENT_REPORT.md).
