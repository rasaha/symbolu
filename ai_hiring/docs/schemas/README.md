# Hiring Decision Authority — Data Contracts

Machine-readable JSON Schemas (Draft 2020-12) that are the **normative** source
for the Hiring Decision Authority design. Where the prose spec
([`../HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md`](../HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md))
and a schema disagree, the schema wins.

| Schema | Contract | Spec §|
|---|---|---|
| [`role_compatibility_profile.schema.json`](role_compatibility_profile.schema.json) | Per-role, versioned weights + required evidence + confidence floors + gate refs. **No universal weighting model.** | 3 |
| [`dimension_assessment.schema.json`](dimension_assessment.schema.json) | Advisory per-dimension `{score, confidence, evidence, gaps}`. No bare scores. | 4 |
| [`evidence_record.schema.json`](evidence_record.schema.json) | Immutable evidence + TAP admission decision + lineage. Rejected evidence has no effect. | 5 |
| [`mandatory_gate.schema.json`](mandatory_gate.schema.json) | Non-compensatory hard requirement (ActionGate parity). | 6 |
| [`hiring_decision_contract.schema.json`](hiring_decision_contract.schema.json) | Versioned, compiled policy the Decision Authority evaluates. | 8 |
| [`hiring_recommendation.schema.json`](hiring_recommendation.schema.json) | Governed, explainable recommendation; `NOT_ELIGIBLE` forced on gate failure. | 9 |
| [`review_and_calibration.schema.json`](review_and_calibration.schema.json) | Predicted-vs-observed reviews (1/3/6/12-month) → contract calibration. | 10 |
| [`api_contracts.schema.json`](api_contracts.schema.json) | API request envelopes; human-only decision endpoint. | 14 |

## Cross-cutting invariants encoded in the schemas

1. **Compatibility ≠ Eligibility.** Eligibility is a conjunction of mandatory
   gates; no dimension score can satisfy a gate.
2. **Non-compensatory gates.** `MandatoryGate.status ∈ {FAILED, INDETERMINATE}`
   blocks eligibility regardless of fit, confidence, or Overall Fit Index.
3. **Overall Fit Index is non-binding.** Surfaced as a range label; the numeric
   value is display-only and must never be read by policy.
4. **AI assists, humans bind.** `HiringRecommendation.actor_type = AI` and
   `advisory_only = true`; the decision endpoint enforces `actor_type = HUMAN`.
5. **Everything cites lineage.** Every score, gate result, and claim references
   admitted Evidence Lineage nodes; rejected evidence is provably inert.
6. **Calibration is governed.** It produces the next contract version; it never
   edits history or tunes hidden weights.

## Validation

```bash
python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('ai_hiring/docs/schemas/*.json')]; print('all schemas parse')"
```
