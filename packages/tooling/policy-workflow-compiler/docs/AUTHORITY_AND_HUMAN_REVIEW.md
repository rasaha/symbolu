# Authority and Human-Review Semantics

The compiler classifies authority; it never assigns it.

## Role-relevance mapping (fail-closed)

| Node kind / condition | Role relevance |
|---|---|
| `APPROVAL_GATE`, `OVERRIDE_GATE`, `AUTHORITY_CHECK` | `HUMAN_AUTHORITY` |
| `SEGREGATION_OF_DUTIES_GATE` | `HUMAN_REVIEW` |
| any `AUTHORITATIVE` (non-COMPILER owner) | `GOVERNANCE_OWNED` |
| advisory governance owner (TAP/STORYGRAPH/MODEL_SELECTION) | `GOVERNANCE_OWNED` |
| `EVIDENCE_REQUIREMENT` + COMPILER + `ADVISORY` | `ADVISORY_AGENT_ELIGIBLE` |
| `AUDIT_EMISSION`, `TERMINAL_OUTCOME` | `DETERMINISTIC_SERVICE` |
| otherwise | `UNSUPPORTED` |

## Human review

`HumanReviewRequirement`: `required`, `review_kind` (human_authority/human_review/
none), `authority_type`, `governance_owner`, `resolution`, `provenance`.

## Invariants

- An authoritative node is never advisory-agent-eligible.
- Binding approval, override, decision authority, ActionGate, and Action Clearance
  are surfaced as human-authority / governance-owned, never as agent role semantics.
- Missing/conflicting authority disposition fails closed at validation.
- The compiler does not grant authority, approve, authorize, clear, or override.
