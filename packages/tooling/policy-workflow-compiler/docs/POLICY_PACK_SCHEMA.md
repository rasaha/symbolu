# Policy Pack Schema

A policy pack is the compiler's sole input: a reviewed, structured
representation of a governance policy. Its schema version is `policy_pack.v1`.

## Object categories

The object model (`models/`) defines twenty object categories. Each captures one
governance concept:

| Category | Purpose |
| --- | --- |
| `PolicyPack` | The container; also carries lifecycle state and transitions. |
| `SourceDocument` | A cited source of policy text. |
| `ProvenanceReference` | A citation binding an object to a source. |
| `DecisionRule` | A declarative rule that determines a disposition. |
| `RequiredEvidence` | Evidence a workflow must collect. |
| `AuthorityRequirement` | The authority needed for an act. |
| `ApprovalPath` | An ordered path of approval steps. |
| `ApprovalStep` | A single step within an approval path. |
| `ProhibitedCondition` | A condition that must never hold. |
| `ExceptionRule` | A carve-out from a decision rule. |
| `OverrideRule` | A governed override of a decision rule. |
| `ActionConstraint` | A constraint bounding an action. |
| `SequenceRiskPattern` | A risky ordering of actions to detect. |
| `LegitimateCounterexample` | A benign case that must not trip a risk pattern. |
| `ConnectorMapping` | A mapping to an external connector. |
| `TestScenario` | A declared assurance scenario. |
| `AuditRequirement` | An audit-emission requirement. |
| `ReplayCase` | A case to be replayed deterministically. |
| `ExpectedOutcome` | The expected terminal outcome for a scenario. |
| `HumanApprovalRecord` | A human reviewer's approval of the pack. |

## Common fields

Every object carries the same identity and lifecycle-adjacent fields:

- `object_id` — unique within the pack.
- `object_type` — the category.
- `name`, `version`, `description`.
- `enabled` — whether the object participates in synthesis.
- `provenance_refs` — citations supporting the object.
- `related_object_ids` — links to other objects.

Objects are **frozen pydantic models** with `extra='forbid'`: unknown fields are
rejected and instances are immutable once constructed.

## The predicate model

Rules and conditions express logic **declaratively**, never as executable code.
A predicate is a triple:

```
(fact_key, Comparator, value)
```

- `fact_key` — names a fact supplied at evaluation time by a downstream runtime.
- `Comparator` — a fixed, enumerated operator.
- `value` — the comparison operand.

Because predicates are data, the compiler can validate, diff, and assure them
without ever running arbitrary logic. Downstream capabilities — not the
compiler — evaluate predicates against live facts.

## Provenance requirement

Every substantive object must cite provenance. An object with no provenance is
`PROPOSED_ONLY` and is flagged `REVIEW_REQUIRED`; it is excluded from synthesis
until a reviewer explicitly approves the gap. The compiler never fabricates
provenance. See `AUDIT_SCHEMA.md` and `VALIDATION_MODEL.md` for how missing
provenance surfaces as a diagnostic.
