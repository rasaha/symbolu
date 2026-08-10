# R1 Implementation Findings

## Finding 1 — Design ↔ R1 field-naming contradiction (recorded & reconciled)

**Contradiction.** The design package
(`../ACTIONGATE_REQUIRED_CHANGES_SCHEMA.md`) sketched a **nested** `remediation` object with
fields `condition_id`, `remediation_class`, `reason_code`, `severity_tier`, `satisfies_alone`,
and a `binding` sub-object. The R1 milestone spec instead mandates **flat top-level** fields
(`response_schema_version`, `all_unmet_conditions`, `required_changes`, `retryability`,
`disclosure`, `retry_budget`) with per-change fields `change_id`, `retry_class`,
`requirement_code`, `category`, `field_path`, `mandatory`, `requires_new_approval`,
`invalidates_prior_evidence`, `policy_version`, `action_hash`. It also introduces
`retryability` and `retry_budget`, which the design docs did not name.

**Resolution.** The R1 spec is the operative build target (it enumerates the six fields and
gives a concrete, testable example), so the implementation follows the **R1 flat schema** and
field names, while preserving the design docs' **semantics** verbatim: the retry-classification
matrix, the DENY-never-retryable invariant, non-compensatory dominance, disclosure gating, and
hash/audit invariance. Concept mapping:

| design-doc name | R1 implemented name |
|---|---|
| `condition_id` | `change_id` (changes) / `rule_id` (unmet conditions) |
| `remediation_class` | `retry_class` |
| `reason_code` | `requirement_code` |
| `severity_tier` | `current_outcome` (on unmet conditions) |
| `binding.rebind_required` | `retryability.new_action_hash_required` |
| nested `remediation` object | flat top-level fields |

No design **semantics** were changed — only the surface schema was reconciled to the R1 spec.
This is the only contradiction found.

## Finding 2 — Retry class must be operator × context, not operator alone
Confirmed against `gate.evaluate`: the same `MUST_HAVE` operator resolves to
`REQUEST_MORE_EVIDENCE` (soft → `EVIDENCE_RETRYABLE`) or `DENY` (`hard:true` →
`TERMINAL`). Classification therefore keys on the `hard` flag and the produced outcome, and
security-critical causes are clamped to `TERMINAL` regardless of any policy metadata.

## Finding 3 — Correctness via predicate reuse, not re-implementation
To guarantee the reported unmet set cannot diverge from the gate's evaluation, the projection
imports and calls the gate's own predicates (`extract_facts`, `_has_evidence`,
`_attestation_ok`, `_approver_satisfied`, `_priv_monotonic`, `_ticket_self_authored`,
`_stale`, `_SEVERITY`, `_REVERSIBILITY_ORDER`) rather than duplicating them. Tested: for every
fixture, `outcome`/`dispositive_rules` are identical before and after projection, and the
projection's dispositive severity equals the gate's outcome tier.

## Finding 4 — `MAX_*` default HUMAN_ONLY (no auto action-modification)
Per the design's threat analysis, `MAX_SCOPE`/`MAX_COST`/`MAX_BLAST_RADIUS`/
`MAX_IRREVERSIBILITY` remain `HUMAN_ONLY` unless the policy effect **explicitly** opts into
`ACTION_MODIFICATION_RETRYABLE`. Missing metadata fails conservatively. Both branches tested.

## Finding 5 — Redaction accounting made honest
Initial implementation reported an empty `redacted_fields` at STANDARD even though threshold
numbers were withheld. Fixed to diff each dispositive change against its FULL reference, so
`redacted_fields` truthfully lists what a mode withheld (e.g. `bounds.current`, `bounds.limit`
at STANDARD).

## Finding 6 — Trusted-context is a reference stub
R1 models privileged-disclosure trust with an explicit boolean / CLI `--trusted-admin`.
Documented (see `R1_SECURITY_LIMITATIONS.md`) that production transports must establish trust
cryptographically. This is a deliberate reference-implementation simplification, not a
production authorization mechanism.

## Non-findings (verified, no change needed)
- `gate.py` and every hashed module are untouched; `action_hash`/`policy_hash`/audit payload
  and all 24 conformance vectors are unchanged (`161 passed`, conformance `24/24`).
- Downstream suites unaffected (gateway 39, MCP 43, k8s 14 pass/16 skip). The
  `action_gateway_isolated` collection error (`No module named 'action_gateway'`) is a
  pre-existing cross-package import-path issue unrelated to R1 (that package is untouched and
  references neither `action_gate_ref` nor remediation).
