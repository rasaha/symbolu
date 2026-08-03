# Release Validation

`CompiledReleaseValidator.validate(ir_v2)` (or `validate_compiled_release`) checks a
`workflow_ir.v2` artifact and returns a `ReleaseValidationResult`.

## States

`VALID`, `VALID_WITH_WARNINGS`, `INVALID`, `UNSUPPORTED_VERSION`,
`INTEGRITY_FAILURE`.

## Integrity dimensions (all reported as booleans)

- **Structural** — unique node/edge ids, resolvable edge endpoints, known contract
  version.
- **Semantic** — every node has semantics; no duplicate capability requirements.
- **Authority** — semantics disposition matches the v1 node; **no AI-eligible
  classification on an authoritative node** (FATAL).
- **Contract** — input/output refs resolve and are non-empty; producers/consumers
  resolve.
- **Dependency** — dependency endpoints resolve.
- **Provenance** — every value has a rule + derivation class; policy id matches.
- **Digest** — `base_ir_digest` matches the embedded v1 graph; `workflow_fingerprint`
  matches recomputation.

## Hard floors

A digest mismatch → `INTEGRITY_FAILURE`. Any authority-boundary failure → `INVALID`.
Neither is ever downgraded to `VALID_WITH_WARNINGS`.

## Diagnostics

Typed codes include `UNKNOWN_CONTRACT_VERSION`, `MISSING_NODE_SEMANTICS`,
`AI_ELIGIBLE_ON_AUTHORITATIVE_NODE`, `CONFLICTING_AUTHORITY_DISPOSITION`,
`UNRESOLVED_CONTRACT_REF`, `DANGLING_EDGE`, `INVALID_DEPENDENCY`,
`BROKEN_PROVENANCE`, `BASE_DIGEST_MISMATCH`, `WORKFLOW_FINGERPRINT_MISMATCH`, and
more — each with severity, workflow/node/edge identity, and contract version.
