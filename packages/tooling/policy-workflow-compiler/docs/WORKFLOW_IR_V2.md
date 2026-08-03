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
