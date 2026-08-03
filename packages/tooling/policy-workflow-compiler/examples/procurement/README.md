# Procurement reference example

A reviewed, structured policy pack that encodes the existing **ugence-procurement**
reference workflow, plus an **offline** approval fixture. It is the Phase 1 proof
that the compiler's governance interpretation matches an existing governed workflow.

The canonical builder ships inside the package at
`ugence_policy_workflow_compiler.reference.procurement` (so the CLI `demo` and the
equivalence harness resolve it from the installed wheel). This directory re-exports
it for standalone example runs.

## Run

```bash
# From the installed package (deterministic, offline, credential-free):
python -m ugence_policy_workflow_compiler demo procurement --out ./compiled

# Or via the example module (with the package importable):
python -m examples.procurement
```

## What it models

Using Procurement's real behavior and reason codes as the authoritative reference:

- purchase-request completeness, supplier/budget existence (fail-closed evidence);
- non-positive-total, unknown-supplier, unknown-budget prohibited conditions;
- required human approver authority + segregation of duties;
- exact-action authorization constraints in the reference's evaluation order
  (expired → restricted supplier → restricted budget → hard limit `10_000_000`
  → auto-authorize threshold `1_000_000` → authorized);
- a legitimate counterexample (large purchase within an approved elevated budget);
- decision → purchase-order action mapping; supplier-outcome and
  reconciliation/compensation terminal behavior;
- audit requirements for decision, action, and execution.

## Equivalence

`ugence_policy_workflow_compiler.reference.procurement_equivalence.run_equivalence()`
compares this pack's interpretation to the live `ugence-procurement` across five
dimensions and reports **EQUIVALENT** (requires the `procurement-reference` extra).
Procurement is never modified to make the compiler pass.

The approval record here is an offline fixture (`is_fixture=True`) — not a real
reviewer authority.
