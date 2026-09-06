# Binding Conformance (PWC-P3B)

`workflow_ir.v2` already **emits** declarative capability binding — a
`CapabilityRequirement` per role-relevant node and typed `DataContractRef`s, each
provenance-backed. What it never did was check those emissions against the registry
that defines what each capability actually is; release validation checked only that
requirements were not duplicated.

P3B is that check, and only that check. It is conformance validation, **not a second
emission path**: nothing here creates a requirement, changes one, or infers one.

## The boundary is unchanged

The registry resolves capability targets from metadata alone, and this module reads
the same metadata. It imports no provider, calls nothing, and cannot tell whether a
capability is installed — only whether the workflow's own claims about it are
internally coherent. `runtime_deployment_implemented` and
`runtime_execution_implemented` remain `false`.

## Canonical versus functional capabilities

The distinction that makes this check correct rather than noisy.

- A **canonical governance capability** (`DECISION_AUTHORITY`, `ACTION_GATE`, `TAP`,
  …) is defined in the registry, with an authority disposition to conform to. These
  are emitted with source `CAPABILITY_OWNER_MAPPING` or `EXPLICIT_POLICY`.
- A **functional capability** describes what a node *does*, not who holds authority
  for it — `EVIDENCE_REQUIREMENT -> evidence_extraction` is the shipped example.
  These are emitted with source `NODE_KIND_MAPPING`, and they are deliberately
  **not** registry entries: the registry describes authority, functional
  capabilities describe work.

Checking a functional capability against the registry would fail every valid
artifact, which is exactly the false-failure mode conformance validation must avoid.
Only the resolution check applies to both kinds.

## Refusals

| Code | Raised when | Severity |
| --- | --- | --- |
| `UNKNOWN_CAPABILITY_REF` | A canonical requirement names a capability the registry does not define | ERROR |
| `ADVISORY_CAPABILITY_ON_AUTHORITATIVE_NODE` | An advisory capability is bound to an authoritative node — advice may inform a decision, never make one | FATAL |
| `AUTHORITATIVE_CAPABILITY_MARKED_OPTIONAL` | An authoritative capability is optional at an authoritative node; "the authority may or may not be consulted" is not a governed workflow | FATAL |
| `MANDATORY_CAPABILITY_MARKED_OPTIONAL` | The registry marks the capability non-optional but the binding is OPTIONAL | ERROR |
| `CAPABILITY_CONTRACT_TARGET_MISMATCH` | The node targets a public contract the registry does not give for that capability | ERROR |
| `UNRESOLVED_CAPABILITY_BINDING` | A REQUIRED binding resolved to nothing; an unresolved OPTIONAL binding is honest, a REQUIRED one is a gap | ERROR |

The two authority failures are in the validator's authority set, so they can never
be reduced to warnings — the same floor the existing authority checks sit behind.

`ReleaseValidationResult.binding_ok` reports the class outcome alongside
`structural_ok`, `semantic_ok`, `authority_ok` and the rest.
