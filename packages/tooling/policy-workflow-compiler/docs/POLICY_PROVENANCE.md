# Policy Provenance

Every enriched semantic value is traceable via `PolicyProvenanceRef`:
`derivation_class`, `source_policy_id`, `source_policy_version`, `source_object_ids`,
`source_declaration`, `source_refs`, `compiler_rule`, `compiler_version`,
`contract_version`.

## Derivation classes

`EXPLICIT`, `DETERMINISTIC_MAPPING`, `DERIVED_FROM_CONTRACT`, `DERIVED_FROM_EDGE`,
`DEFAULTED_SAFE`, `UNRESOLVED`. `DEFAULTED_SAFE` is not used where the value affects
authority, eligibility, or contract compatibility.

## Guarantees

- Every node-semantics and dependency value has provenance naming the exact
  deterministic compiler rule that produced it.
- `source_object_ids` trace a compiled node back to the source policy objects that
  fed it.
- The release validator detects broken provenance (`BROKEN_PROVENANCE`) and a policy
  id that disagrees with the release (`CONFLICTING_POLICY_SOURCE`).
- Provenance is ordering-independent (canonicalized).
