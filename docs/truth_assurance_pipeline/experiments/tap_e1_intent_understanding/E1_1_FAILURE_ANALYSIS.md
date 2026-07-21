# TAP-E1.1 — Failure Analysis

Severe (critical) failures are reported independently of averages (unchanged from
TAP-E1): invented actions, invented constraints/entities, dropped prohibitions,
unsupported assumptions, incorrect conflict resolution, silent ambiguity resolution,
provenance errors, clarification errors.

> All LLM counts below reflect the **author==interpreter confound**: the same
> in-session model authored the corpus and produced the interpretations, and the locked
> eval was seen by the interpreter (not double-blind). These are integration findings,
> not independent model-capability measurements. See the [experiment report](./E1_1_EXPERIMENT_REPORT.md) §2/§5.

## Severe-failure counts (v1.1 corpus)

| split | A raw | B | C | D (selected) | E | F | DET V4 | DET V0 |
|---|---|---|---|---|---|---|---|---|
| eval (24) | 30 | 0 | 0 | **0** | 0 | 1 | 7 | 31 |
| adversarial (12) | 19 | — | — | **0** | 0 | 1 | 7 | — |
| negative (12) | 12 | — | — | **0** | 0 | 0 | 0 | — |

## Where each configuration fails

**Raw LLM (A).** The dominant failure is `invented_entity` and `unsupported_assumption`:
free text has no schema, so the naive parse of the model's sentence grabs
sentence-initial capitalized words as entities and no constraints survive; on
adversarial prompts it commits to the manipulated reading (unsupported 1.00). *Free text
is not a safe interface, regardless of model quality.*

**Deterministic V4 (for comparison).** On the v1.1 corpus its failures are
`dropped_constraint` (naturally-phrased constraints like "leave the schema alone",
"off the table" are missed → constraint preservation 0.60) and, on adversarial prompts,
`resolved_material_ambiguity_without_evidence` (7 severe): the lexical ambiguity detector
does not fire on "as approved…", "the usual files", "make it say we're certified", so it
commits. This is the concrete gap the LLM-backed configuration closes under the
conditions tested.

**Selected D (LLM + extraction + provenance).** Zero severe failures on eval,
adversarial, and negative. The model paraphrases the objective and the corrected
`invented_action` metric (see below) does not penalize paraphrase; constraints are
captured by the model and reinforced by deterministic extraction; provenance is honest
(`MODEL_INFERENCE` / `DETERMINISTIC_EXTRACTION`), so no false-explicit provenance.

**F (clarification) regression.** F reintroduces 1 severe failure (a proceed-with-
assumption case pushed into commitment) and over-asks (unnecessary-clarification 0.23,
status accuracy 0.71). Adding the clarification-*asking* policy on top of a model that
already flags ambiguity via status did not help — the same "complexity is not free"
result seen in TAP-E1.

## Metric-artifact failures caught during analysis (see METRIC_AUDIT.md)

- **`invented_action` paraphrase false positives.** TAP-E1's metric flagged any
  objective verb not literally in the source ("polish"→"improve"). Observed on **dev**
  (4 cases) and corrected to be paraphrase-invariant. Without the correction the LLM
  would have shown 11–13 *phantom* severe failures on eval — a result that would have
  been **false**. Reporting it would have violated evidence discipline.
- **Material-ambiguity under-crediting.** A proceed-with-assumption case
  (PARTIALLY_RESOLVED + explicit stated_assumption) is *representing* the gap, not
  silently resolving it; the metric now credits it. Silent resolution (RESOLVED, no
  acknowledgement) remains a severe failure.

## Residual (non-severe) weaknesses

- `primary_objective_accuracy` 0.75 for the LLM (vs 1.00 deterministic) is a **scoring
  artifact** of keyword-based objective matching penalizing paraphrase; a semantic
  scorer would likely erase this gap.
- Coverage is bounded (68 LLM interpretations; dev sample 20/53) and the corpus
  is smaller than target — statistical power is limited.
- The **author==interpreter confound** may inflate every LLM number; an independent
  interpreter/author is required to trust the magnitude of the improvement.
