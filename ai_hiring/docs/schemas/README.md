# Hiring Decision Authority — Data Contracts

Machine-readable JSON Schemas (Draft 2020-12) that are the **normative** source
for the Hiring Decision Authority design. Where the prose spec
([`../HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md`](../HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md))
and a schema disagree, the schema wins.

The vertical is one governed **Decision Authority** domain on the shared Ugence
kernel: **Policy → Compiler (PWC) → WorkflowIR → Decision Contract → Decision
Authority → ActionGate → Runtime Assurance → Execution Receipt → Reconciliation.**

## Policy plane (compile)

| Schema | Contract | Spec §|
|---|---|---|
| [`hiring_policy_source.schema.json`](hiring_policy_source.schema.json) | Declarative, human-authored Hiring Policy (compiler input). HR declares requirements, not JSON weights. | 3 |
| [`hiring_workflow_ir.schema.json`](hiring_workflow_ir.schema.json) | **HiringWorkflowIR** — compiled, versioned, content-addressed, signed. Emits dimensions, weights, gates, evidence, thresholds, action constraints, assurance checks. | 3 |
| [`hiring_decision_contract.schema.json`](hiring_decision_contract.schema.json) | Deployable **Decision Contract** projected from one IR digest. What the Decision Authority evaluates. | 3, 8 |
| [`role_compatibility_profile.schema.json`](role_compatibility_profile.schema.json) | *Superseded as an authoring surface.* Shape of the compiler's compiled dimension model. | 3 |

## Evidence + assessment plane

| Schema | Contract | Spec §|
|---|---|---|
| [`evidence_record.schema.json`](evidence_record.schema.json) | Immutable evidence + TAP admission + lineage. Rejected evidence is inert. | 5 |
| [`dimension_assessment.schema.json`](dimension_assessment.schema.json) | Advisory per-dimension `{score, confidence, evidence, gaps}`. No bare scores. | 4 |
| [`mandatory_gate.schema.json`](mandatory_gate.schema.json) | Non-compensatory hard requirement (ActionGate parity). | 6 |

## Authority plane (decide)

| Schema | Contract | Spec §|
|---|---|---|
| [`hiring_recommendation.schema.json`](hiring_recommendation.schema.json) | Governed recommendation. Inputs are dimension evidence + gates + confidence + contract only; **the OFI never appears here.** | 7, 8 |

## Action + assurance plane (execute)

| Schema | Contract | Spec §|
|---|---|---|
| [`hiring_actiongate.schema.json`](hiring_actiongate.schema.json) | **Hiring ActionGate** — final action must match contract constraints (salary/level/role/location/approvals) or `DENY_REAUTH`. | 9 |
| [`hiring_runtime_assurance.schema.json`](hiring_runtime_assurance.schema.json) | **Runtime Assurance** — pre-write checks (approvals, references, bg-check, offer, salary policy, req) before HRIS/ATS. | 10 |
| [`hiring_execution_receipt.schema.json`](hiring_execution_receipt.schema.json) | **Execution Receipt** — attempted vs observed HRIS/ATS write. | 11 |

## Reconciliation plane (learn)

| Schema | Contract | Spec §|
|---|---|---|
| [`hiring_reconciliation_record.schema.json`](hiring_reconciliation_record.schema.json) | **Reconciliation Record** — predicted vs actual at 1/3/6/12 months → recompile the policy. | 11, 12 |
| [`review_and_calibration.schema.json`](review_and_calibration.schema.json) | Per-checkpoint review observations feeding reconciliation. | 12 |

## API

| Schema | Contract | Spec §|
|---|---|---|
| [`api_contracts.schema.json`](api_contracts.schema.json) | API request envelopes; human-only decision endpoint. | 16 |

## Cross-cutting invariants encoded in the schemas

1. **Policy is compiled, signed, reproducible.** HR authors a Hiring Policy;
   the PWC emits a content-addressed, signed `HiringWorkflowIR`; the Decision
   Contract cites its IR digest. Same policy → same digest.
2. **Compatibility ≠ Eligibility.** Eligibility is a conjunction of mandatory
   gates; no dimension score can satisfy a gate.
3. **Overall Fit Index is analytics-only.** It never enters the Decision
   Authority and appears on no decision/recommendation/action object; the
   compiler rejects any policy that references it in a rule.
4. **Action must match the contract.** Hiring ActionGate denies any deviation
   in salary/level/role/location/approvals; deviation requires reauthorization.
5. **Nothing writes un-assured.** No HRIS/ATS write without a passing ActionGate
   **and** Runtime Assurance; failures block, never silently write.
6. **AI assists, humans bind.** `HiringRecommendation.actor_type = AI`,
   `advisory_only = true`; the decision endpoint enforces `actor_type = HUMAN`.
7. **Everything cites lineage / provenance.** Scores, gates, gate verdicts,
   receipts cite admitted Evidence Lineage nodes and IR digests.
8. **Reconciliation calibrates contracts, not weights.** Predicted-vs-actual
   yields a governed proposal that recompiles the policy into the next contract
   version; it never tunes hidden model weights or edits history.

## Validation

```bash
python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('ai_hiring/docs/schemas/*.json')]; print('all schemas parse')"
```
