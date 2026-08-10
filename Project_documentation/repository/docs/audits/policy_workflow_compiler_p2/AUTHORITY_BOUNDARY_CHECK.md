# Authority Boundary Check — P2

P2 strengthens authority *metadata* without ever assigning, granting, approving, or
authorizing anything.

## What the compiler classifies (deterministically, fail-closed)

`classify_role_relevance(node)` maps each node to exactly one role relevance from
its kind, owning capability, and disposition:

| Node kind / condition | Role relevance |
|---|---|
| `APPROVAL_GATE`, `OVERRIDE_GATE`, `AUTHORITY_CHECK` | `HUMAN_AUTHORITY` |
| `SEGREGATION_OF_DUTIES_GATE` | `HUMAN_REVIEW` |
| any `AUTHORITATIVE` disposition (non-COMPILER owner) | `GOVERNANCE_OWNED` |
| advisory governance owner (`TAP`, `STORYGRAPH`, `MODEL_SELECTION`) | `GOVERNANCE_OWNED` |
| `EVIDENCE_REQUIREMENT` owned by `COMPILER`, `ADVISORY` | `ADVISORY_AGENT_ELIGIBLE` |
| `AUDIT_EMISSION`, `TERMINAL_OUTCOME` | `DETERMINISTIC_SERVICE` |
| otherwise | `UNSUPPORTED` (fail closed) |

## Guarantees (verified by tests)

- **An authoritative node is never `ADVISORY_AGENT_ELIGIBLE`.** Classification checks
  human-authority kinds and the authoritative disposition before agent-eligibility.
  The release validator additionally raises the FATAL diagnostic
  `AI_ELIGIBLE_ON_AUTHORITATIVE_NODE` if any semantics claim otherwise, and such a
  release is `INVALID` — **never** `VALID_WITH_WARNINGS`
  (`test_authoritative_node_marked_agent_eligible_is_invalid_never_warning`).
- Binding approval, override, decision authority, ActionGate action constraints, and
  Action Clearance requirements are surfaced as `HUMAN_AUTHORITY` /
  `GOVERNANCE_OWNED` with their `canonical_capability_owner` and
  `governance_boundary_refs` (the capability public-contract target). They are never
  emitted as ordinary AI-agent role semantics.
- Missing or conflicting authority disposition fails closed: the validator emits
  `MISSING_AUTHORITY_DISPOSITION` / `CONFLICTING_AUTHORITY_DISPOSITION` (ERROR) and
  the release is `INVALID`.

## What the compiler does NOT do

It does not grant authority, approve decisions, authorize actions, perform
commit-time clearance, execute overrides, or replace human approval. It only
*classifies and references* governance-owned steps. Existing P1 authority-boundary
enforcement (`validation/authority_boundaries.py`, run in the compiler and verifier)
is unchanged; P2 adds a read-only semantic projection on top of it.
