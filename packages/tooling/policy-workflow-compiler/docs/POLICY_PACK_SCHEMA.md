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


## `policy_pack.v2` — source-declarable semantics

`policy_pack.v2` is additive. It adds two pack-level fields and one object type; a
`policy_pack.v1` pack is unchanged, and so is every v1 digest and every approval
bound to one.

| Addition | Purpose |
| --- | --- |
| `semantic_declarations` | A sidecar collection of `SemanticDeclaration` objects, each naming its `subject_object_id` and declaring data classification refs, permission *intent* refs, required tool refs, and typed input/output contract refs with versions. |
| `authoritative_source` | The exact Policy Authority issuance the pack was compiled from (PA/PWC-X1): the six-field coordinate, the issuance attestation, and the resolution context. |
| `ObjectType.SEMANTIC_DECLARATION` | Declarations are addressable `PolicyObject`s — they carry provenance refs, appear in `all_objects()`, and are diffable. |

### Why a sidecar

A declaration names its subject rather than living on it. That keeps the twenty v1
object models untouched, and it means the schema gate is a single reviewable rule
rather than a per-model concern.

### The schema gate

`models/pack_view.py::canonical_pack_view` is the one definition of a pack's logical
content, used by both the compiled release and the approval digest. It includes the
v2 fields **only** for a v2 pack, so `policy_pack.v1` canonical bytes are identical
by construction.

A **v1 pack that declares v2 content is refused** (`V2_FIELD_IN_V1_PACK`, `FATAL`),
never quietly pruned: a field that is present, reviewed, approved and then silently
excluded from the digest is worse than one either accepted or rejected.

### Fail-closed checks

| Code | Raised when |
| --- | --- |
| `V2_FIELD_IN_V1_PACK` | A `policy_pack.v1` pack carries v2 content |
| `DANGLING_DECLARATION_SUBJECT` | `subject_object_id` resolves to no object in the pack |
| `DUPLICATE_DECLARATION_SUBJECT` | Two declarations claim one subject — which governs is not a question the compiler may answer |
| `MALFORMED_CONTRACT_VERSION_REF` | A typed contract reference carries no contract id |
| `UNSUPPORTED_SCHEMA_VERSION` | The pack declares a schema this build cannot compile |

### Declared, never inferred

A declaration is preserved exactly as the source policy states it. Where the policy
declares nothing, the value stays unresolved — never defaulted. `workflow_ir.v2`
enrichment reading these values into node semantics is the next step and is not
implemented (`source_declared_semantics_implemented=false`).

### Ruling V2-B

`SEMANTIC_DECLARATION` is in `APPROVAL_SENSITIVE_OBJECT_TYPES`: changing a data
classification is governance-material and routes to P3A review.
