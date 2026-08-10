# R1 Response Schema (v1.1)

The decision response keeps every existing field unchanged. When `remediation_mode != OFF`,
six additive top-level fields are appended. With `OFF` (default) the response is
byte-identical to the pre-R1 output.

`response_schema_version = "1.1"`.

## Existing (unchanged) decision fields
`outcome`, `dispositive_rules`, `applied_constraints`, `action_hash`, `policy_hash`,
`state_trace`, `terminal`, `reason`, `hash_algorithm_id`.

## Added fields

```
response_schema_version : "1.1"
all_unmet_conditions    : [ UnmetCondition ]   # dispositive tier only, except FULL-tier modes
required_changes        : [ RequiredChange ]   # dispositive-tier changes (dominance)
retryability            : Retryability
disclosure              : Disclosure
retry_budget            : RetryBudget          # R1: advisory container, all null (no orchestrator)
```

### UnmetCondition
```
{ "rule_id": str, "operator": str, "dispositive": bool,
  "current_outcome": str, "evaluated": bool }
```
At MINIMAL, `rule_id`/`operator` are omitted (policy-structure hiding).

### RequiredChange (FULL/TRUSTED_PLANNER/HUMAN_ONLY shape)
```
{ "change_id": str,                  # stable, deterministic: "chg:<rule_id>:<slug>"
  "source_rule_id": str,
  "operator": str,                   # MUST_HAVE|REQUIRE_SIMULATION|REQUIRE_APPROVER|MAX_*|FORBID|…
  "category": str,                   # PROVIDE_EVIDENCE|RUN_SIMULATION|OBTAIN_APPROVAL|REDUCE_SCOPE|…
  "field_path": str,                 # e.g. "evidence.signed_artifact", "arguments.affected_count"
  "requirement_code": str,           # R_EVIDENCE_REQUIRED|R_SIMULATION_REQUIRED|R_HARD_PRECONDITION|…
  "retry_class": str,                # EVIDENCE_RETRYABLE|SIMULATION_RETRYABLE|
                                     #   ACTION_MODIFICATION_RETRYABLE|HUMAN_ONLY|TERMINAL
  "mandatory": bool,
  "disclosure_level": str,
  "requires_new_approval": bool,
  "invalidates_prior_evidence": bool,
  "policy_version": str,
  "action_hash": str,
  "bounds": { "fact": str, "current": str, "limit": str } | { "classification": "EXCEEDS_LIMIT" },
  "evidence_kind": str,              # (evidence/attestation changes, privileged modes)
  "required_fidelity": str           # (simulation changes, privileged modes)
}
```
MINIMAL keeps only `{change_id, category, retry_class, requirement_code, mandatory}`.
STANDARD keeps the structure but replaces `bounds` with `{classification:"EXCEEDS_LIMIT"}` and
drops `evidence_kind`/`required_fidelity` (no exact policy internals).

### Retryability (from the dispositive tier)
```
{ "retryable": bool,                 # false whenever the dispositive tier is TERMINAL (DENY)
  "retry_class": str | null,
  "new_action_hash_required": bool,  # true only for ACTION_MODIFICATION_RETRYABLE
  "fresh_evaluation_required": bool } # true whenever retryable
```

### Disclosure
```
{ "mode": "MINIMAL|STANDARD|TRUSTED_PLANNER|HUMAN_ONLY|FULL",
  "redacted_fields": [ str ] }       # honest list of what this mode withheld
```

### RetryBudget (advisory only in R1)
```
{ "max_attempts": null, "deadline": null, "compute_budget": null }
```
R1 introduces no orchestrator; the container is present for forward compatibility and is
populated only by an out-of-gate broker in a later phase.

## Invariants
- `required_changes` for a DENY outcome contains only `TERMINAL` entries (never a retry path).
- `retryability.retryable == False` whenever the outcome is DENY.
- Output is reproducible from `(decision inputs, signed policy, now, mode, trusted_context)`.
