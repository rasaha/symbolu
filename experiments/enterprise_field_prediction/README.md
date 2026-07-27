# Structured Field Prediction Diagnosis and Rescue

**Decisive question:** which enterprise facts should be computed exactly, which genuinely require
multi-record quadratic reasoning, and can the system predict those typed facts accurately enough that
the already-validated deterministic mapper produces the correct outcome on unseen workflows?

Targets the bottleneck the frozen output-mapping phase isolated: **evidence → typed structured
fields** (learned field_acc ≈ 0.45; O5 over *true* fields = 1.00). Everything upstream is frozen and
imported unchanged — the evidence ledger, deterministic joins, P5 slot policy, provenance/access
guarantees, the full slot-to-slot quadratic block, and the validated deterministic/constrained
outcome mapper (baseline at commit `a4b01e2`).

## Field ownership (§8)

Each contract field is classified and computed accordingly:

| field | ownership | how it is computed |
|---|---|---|
| budget_status | DETERMINISTIC | read the budget record's tier vs threshold |
| approval_requirement | DETERMINISTIC | `POLICY_TABLE[active_version][budget_tier]` |
| evidence_complete | DETERMINISTIC | presence of budget + active policy |
| active_policy_status | RELATIONAL | latest ACTIVE governance record; conflict across records |
| material_conflict | RELATIONAL | >1 ACTIVE governance record of differing version |
| approval_evidence_status | RELATIONAL | match an approval record to the required role |

Even the "relational" predicates are **exactly computable** by a bounded O(K) scan of the exact slot
records — they need multi-record comparison, not a learned readout.

## Arms (§7)

`F0` current learned typed heads · `F1` deterministic exact extractors (all fields) · `F2` hybrid
(deterministic + quadratic only for relational) · `F3` independent learned heads · `F4` learned +
logged consistency repair · `F5` deterministic over each field's contract-eligible masked subset ·
`F6` oracle true fields. F1/F2/F5 are the primary candidates.

## Contracts, masks, consistency

`field_contracts.py` gives every field a typed vocabulary with an UNKNOWN/INSUFFICIENT state, its
required evidence, relation path, version/conflict rules, and abstention condition. `field_masks.py`
restricts each field to its contract-eligible evidence using only runtime-observable schema fields
(leak-free, audited). `consistency_constraints.py` enforces cross-field invariants with logged
deterministic repair — silent mutation prohibited.

## Discipline

No Phase. No learned slot admission. Context not enlarged indiscriminately. Outcome contract not
redesigned. Integrity is categorical: evidence-ID preservation = 1.00, unauthorized inclusion =
0.00, label-invariant evidence routing. Acceptance thresholds (§14) fixed in advance.

## Files

`field_contracts.py` · `evidence_requirements.py` (contracts embed the requirements) ·
`deterministic_fields.py` · `relational_fields.py` · `field_masks.py` · `field_predictors.py` ·
`consistency_constraints.py` · `oracle_interventions.py` · `causal_controls.py` · `evaluate.py` ·
`run_field.py` · `tests/` · `results/` · `ENTERPRISE_FIELD_PREDICTION_REPORT.md` ·
`ENTERPRISE_FIELD_PREDICTION_RESULTS.json`.
