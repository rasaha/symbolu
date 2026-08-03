# Workflow IR

The workflow intermediate representation (`compiler/workflow_ir.py`) is the
governed-workflow graph synthesized from an approved policy pack. It is a
directed graph of content-addressed nodes joined by ordered edges. It describes
structure only; it does not execute.

## Node kinds

There are fourteen node kinds:

| Node kind | Role |
| --- | --- |
| `EVIDENCE_REQUIREMENT` | Evidence that must be collected. |
| `EVIDENCE_ADMISSIBILITY` | Whether collected evidence is admissible. |
| `DECISION_RULE` | A declarative decision rule. |
| `AUTHORITY_CHECK` | Verifies required authority. |
| `APPROVAL_GATE` | An approval step gate. |
| `SEGREGATION_OF_DUTIES_GATE` | Enforces separation of duties. |
| `PROHIBITED_CONDITION` | A condition that must not hold. |
| `EXCEPTION_BRANCH` | A governed exception carve-out. |
| `OVERRIDE_GATE` | A governed override. |
| `ACTION_CONSTRAINT` | A bound on an action. |
| `SEQUENCE_RISK_CHECK` | Detects a risky action ordering. |
| `ACTION_CLEARANCE_REQUIREMENT` | A required clearance before an action. |
| `AUDIT_EMISSION` | Emits an audit event. |
| `TERMINAL_OUTCOME` | A terminal state of the workflow. |

## Edge kinds

There are nine edge kinds, expressing control flow:

`NEXT`, `ON_PASS`, `ON_FAIL`, `ON_MISSING`, `ON_EXCEPTION`, `ON_OVERRIDE`,
`ON_ESCALATE`, `ON_DENY`, `ON_INDETERMINATE`.

## Deterministic identity

- **Node ids are content-addressed.** A node id is the SHA-256 over its `kind`,
  `capability`, and the sorted ids of its input objects. Two syntactically
  identical nodes therefore share an id; a change to any input changes the id.
- **Edges carry a deterministic `order`.** Ordering is explicit and stable, so
  the emitted graph — and any digest over it — is reproducible.

## Per-node fields

Each node declares:

- `owning_capability` — the capability responsible for the node.
- `authority_type` — the kind of authority involved.
- `disposition` — `advisory` or `authoritative`.
- `public_contract_target` — the public contract the node binds to.
- `input_object_ids` — the policy objects that produced the node.
- `output_contract` — the shape the node yields.
- `failure_behavior` — how the node behaves on failure.
- `audit_requirements` — the audit emissions the node requires.

## Only-required capabilities

Synthesis emits **only the capabilities the policy actually requires**. Nothing
is included speculatively. In the Procurement demo, the compiled output contains
23 nodes and 40 edges, and references exactly four capabilities — `ACTION_GATE`,
`COMPILER`, `DECISION_AUTHORITY`, and `TAP` — with no clearance, storygraph, or
model-selection capability present.

Every node's `disposition` and `owning_capability` are checked against the
authority-boundary table before the IR is accepted; see
`AUTHORITY_BOUNDARIES.md`.

## See also: workflow_ir.v2

`workflow_ir.v2` is an additive superset that embeds this v1 graph unchanged and adds role-relevant semantics beside it. This document describes v1, which is frozen. See `WORKFLOW_IR_V2.md`.
