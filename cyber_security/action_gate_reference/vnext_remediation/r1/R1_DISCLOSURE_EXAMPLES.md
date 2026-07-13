# R1 Disclosure-Mode Examples (real output)

One action — `DB_MUTATION` with `affected_count = 25000` (limit 10000), a MEDIUM simulation
present — under each disclosure mode. Decision is unchanged across all modes:
`outcome = ESCALATE_TO_HUMAN`, `dispositive_rules = ["R7"]`. Only the remediation block
differs. (Generated from the reference implementation.)

## OFF (default)
No remediation fields. Response is byte-identical to the pre-R1 decision.

## MINIMAL — broad category, retry class, generic code; no policy internals
```json
{
  "required_changes": [
    {
      "change_id": "chg:R7:max_scope:affected_count",
      "category": "REDUCE_SCOPE",
      "retry_class": "HUMAN_ONLY",
      "requirement_code": "R_SCOPE_EXCEEDED",
      "mandatory": true
    }
  ],
  "all_unmet_conditions": [
    { "dispositive": true, "current_outcome": "ESCALATE_TO_HUMAN", "evaluated": true }
  ],
  "disclosure": { "mode": "MINIMAL",
    "redacted_fields": ["action_hash","bounds","bounds.current","bounds.limit",
      "disclosure_level","field_path","invalidates_prior_evidence","operator",
      "policy_version","requires_new_approval","source_rule_id"] }
}
```
No `rule_id`/`operator`/`field_path`/thresholds — policy structure is hidden.

## STANDARD — safe structure, generic bounds classification, no exact thresholds
```json
{
  "required_changes": [
    {
      "change_id": "chg:R7:max_scope:affected_count",
      "source_rule_id": "R7",
      "operator": "MAX_SCOPE",
      "category": "REDUCE_SCOPE",
      "field_path": "arguments.affected_count",
      "requirement_code": "R_SCOPE_EXCEEDED",
      "retry_class": "HUMAN_ONLY",
      "mandatory": true,
      "disclosure_level": "STANDARD",
      "requires_new_approval": true,
      "invalidates_prior_evidence": false,
      "policy_version": "1.4.0+sha256:aa11",
      "action_hash": "b8fcd2895a4b2231…",
      "bounds": { "classification": "EXCEEDS_LIMIT" }
    }
  ],
  "all_unmet_conditions": [
    { "rule_id": "R7", "operator": "MAX_SCOPE", "dispositive": true,
      "current_outcome": "ESCALATE_TO_HUMAN", "evaluated": true }
  ],
  "retryability": { "retryable": true, "retry_class": "HUMAN_ONLY",
                    "new_action_hash_required": false, "fresh_evaluation_required": true },
  "disclosure": { "mode": "STANDARD", "redacted_fields": ["bounds.current","bounds.limit"] },
  "retry_budget": { "max_attempts": null, "deadline": null, "compute_budget": null },
  "response_schema_version": "1.1"
}
```
`bounds` is a classification, not the numbers 25000/10000 — and `redacted_fields` says so.

## TRUSTED_PLANNER — richer, exact thresholds only if the signed policy opts in
Same as STANDARD, plus `all_unmet_conditions` for every unmet tier (planning), plus exact
`bounds:{fact,current,limit}` **iff** the policy effect carries
`"remediation": {"acceptable_bounds_disclosure": true}` — else the classification. Requires a
trusted caller context.

## HUMAN_ONLY — full detail to an authenticated human/privileged context
Like FULL, but semantically scoped to a human operator. Requires a trusted caller context.

## FULL — complete diagnostic (tests/admin/secured audit)
Exact `bounds:{"fact":"affected_count","current":"25000","limit":"10000"}`, `evidence_kind`/
`required_fidelity` where relevant, and `all_unmet_conditions` across every tier. Requires a
trusted caller context (`--trusted-admin` on the CLI). Non-production.

## Untrusted request for a privileged mode
`TRUSTED_PLANNER` / `HUMAN_ONLY` / `FULL` without a trusted caller context raise
`E_REMEDIATION_DISCLOSURE` (CLI exits non-zero). A caller-provided mode string alone can never
unlock privileged disclosure.
