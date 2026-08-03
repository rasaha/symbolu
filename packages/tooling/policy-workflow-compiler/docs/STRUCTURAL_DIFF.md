# Structural Diff

The structural diff (`diff/`) compares two policy packs or two compiled packages
at the object level and reports exactly what changed. It performs an **exact
comparison only** — no natural-language or semantic interpretation.

## Change types

| Change type | Detects |
| --- | --- |
| `OBJECT_ADDED` | An object present only in the new pack. |
| `OBJECT_REMOVED` | An object present only in the old pack. |
| `OBJECT_CHANGED` | An object whose fields differ. |
| `REFERENCE_CHANGED` | A changed `related_object_ids` / reference link. |
| `PROVENANCE_CHANGED` | A change in cited provenance. |
| `AUTHORITY_CHANGED` | A change to an authority requirement. |
| `ACTION_CONSTRAINT_CHANGED` | A change to an action constraint. |
| `EXPECTED_OUTCOME_CHANGED` | A change to an expected outcome. |
| `TEST_COVERAGE_CHANGED` | A change in assurance coverage. |
| `CAPABILITY_REQUIREMENT_CHANGED` | A change in required capabilities. |

## Impact summary

Alongside the change list, the diff produces an impact summary that answers "what
does this change affect downstream?":

- `workflow_nodes_affected` — IR nodes touched by the change.
- `assurance_tests_affected` — test specifications touched.
- `approval_re_review_required` — whether the change forces a fresh human review.
- `connector_mappings_affected` — connector mappings touched.
- `authority_scope_affected` — whether authority scope shifted.

The `approval_re_review_required` flag is the operational payoff: because
approvals bind to the structural digest (see `HUMAN_APPROVAL.md`), a
structurally meaningful change invalidates a prior approval, and the impact
summary surfaces that explicitly.

## Exact comparison only

The diff is deliberately literal. It compares object fields, references,
provenance, authority, constraints, outcomes, coverage, and capability
requirements as data. It does **not** attempt to judge whether two differently
worded descriptions "mean the same thing," and it does not perform semantic
equivalence. This keeps the diff deterministic and auditable: a reported change
is a concrete field-level difference, and the absence of a reported change means
the objects are structurally identical — nothing is inferred.

See `POLICY_PACK_SCHEMA.md` for the object model the diff operates over and
`DETERMINISM.md` for why exact, canonical comparison is reliable.
