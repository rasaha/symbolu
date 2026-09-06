# workflow_ir.v2 — Semantic Enrichment Contract

`workflow_ir.v2` is an **additive** contract that enriches a compiled
`workflow_ir.v1` graph with role-relevant semantics the compiler legitimately owns.
v1 is unchanged and its fingerprints are byte-stable.

## Shape

`WorkflowIRv2` embeds the exact v1 graph and adds enrichment beside it:

```
WorkflowIRv2
├── ir_version = "workflow_ir.v2", contract_version = "workflow_ir.v2"
├── policy_pack_id, policy_pack_version
├── base_ir            : the embedded, unchanged WorkflowIR (v1)
├── base_ir_digest     : pins base_ir.logical_digest()
├── node_semantics      : WorkflowNodeSemantics[]  (sorted by node_id)
├── dependency_semantics: WorkflowDependencySemantics[]
├── semantic_features   : SemanticFeature[]  (role/contract/dependency/authority/…)
├── capability_reference_manifest : sorted capability ids
├── contract_reference_manifest   : sorted contract ids
├── provenance_manifest           : sorted source policy ids
├── diagnostics        : SemanticDiagnostic[]
├── compiler_version
└── workflow_fingerprint = logical_digest()  (re-verifiable)
```

## Producing v2

- `compile_workflow_v2(pack, approval=None, *, require_approval=True)` — compile v1
  via the unchanged pipeline, then enrich.
- `enrich_workflow(ir, pack=None, *, compiler_version)` — enrich an existing v1 IR.
- `upgrade_workflow_ir(ir, ...)` — deterministic, non-destructive v1→v2 enrichment.
  It preserves all v1 information (lossless in that narrow sense) but does NOT
  recover source facts absent from v1; derived/deferred/unresolved semantics are
  labeled via their provenance derivation class, never invented.
- CLI: `compile --contract workflow_ir.v2`, `upgrade-v1`, `compare-contracts`.

## Determinism

Enrichment is a pure function of the v1 graph. Identical inputs produce identical
fingerprints across processes; the enrichment output is canonically ordered so it
adds no ordering sensitivity of its own. `upgrade-v1` of a v1 IR reproduces the exact
fingerprint of `compile --contract workflow_ir.v2`.


## Source-declared semantics (`policy_pack.v2`)

Where the source pack is `policy_pack.v2`, enrichment reads its declarations into
node semantics instead of leaving the slots empty.

A declaration reaches a node when the node was built from the object the
declaration names — that is, when `subject_object_id` is one of the node's
`input_object_ids`, the same linkage `source_policy_refs` already reports. Values
from several declarations on one node are unioned, de-duplicated and sorted, so the
result is a function of what was declared, never of declaration order.

| Field | Filled from |
| --- | --- |
| `data_classification_refs` | `SemanticDeclaration.data_classification_refs` |
| `permission_intent_refs` | `SemanticDeclaration.permission_intent_refs` |
| `required_tool_refs` | `SemanticDeclaration.required_tool_refs` |
| `DataContractRef.contract_data_version` | a declared contract ref matching that contract id |

### Declared, never inferred

A declared value carries `DerivationClass.EXPLICIT`. A contract version the policy
declares is marked `EXPLICIT` under the rule `source_declared_contract_version`;
one it does not declare stays empty under `DERIVED_FROM_CONTRACT`, never guessed. A
field the policy leaves unstated stays empty with no provenance entry at all —
there is no explicit provenance for a value nobody declared.

Note the scope: a declaration is attached to its subject's node. A node's *input*
contract belongs to its producer, so a version declared about one object does not
silently version another object's contract.

### `declared_value_provenance`

Per-value provenance lives in a top-level `declared_value_provenance` collection
rather than on `WorkflowNodeSemantics`. A new per-node field would appear in every
node's canonical bytes and move the fingerprint of every graph, including those
enriched from a v1 pack that declares nothing. The collection is empty for a
v1-sourced graph, and the logical digest **omits the key entirely** when it is
empty — so `workflow_ir.v2` fingerprints predating this addition are unchanged.

A v2 pack that declares content produces a different fingerprint. That is new
content, not a moved fingerprint.
