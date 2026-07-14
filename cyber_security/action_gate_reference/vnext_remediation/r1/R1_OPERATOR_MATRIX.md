# R1 Operator → Remediation Matrix (as implemented)

Grounded in `gate.evaluate` and `policy.DEFAULT_RULES`. Classification depends on
**(operator, hard flag, the outcome it produced, policy metadata)** — never the operator
alone. Security-critical terminal causes can never be upgraded by policy metadata.

| condition (operator / check) | outcome tier | retry_class | category | requirement_code | retryable |
|---|---|---|---|---|---|
| `MUST_HAVE` (soft) | REQUEST_MORE_EVIDENCE | `EVIDENCE_RETRYABLE` | PROVIDE_EVIDENCE | `R_EVIDENCE_REQUIRED` | yes |
| `MUST_HAVE` (`hard`) | DENY | `TERMINAL` | NONE | `R_HARD_PRECONDITION` | **no** |
| `REQUIRE_ATTESTATION` | REQUEST_MORE_EVIDENCE | `EVIDENCE_RETRYABLE` | PROVIDE_ATTESTATION | `R_ATTESTATION_REQUIRED` | yes |
| `REQUIRE_SIMULATION` | SIMULATE_AND_RETRY | `SIMULATION_RETRYABLE` | RUN_SIMULATION | `R_SIMULATION_REQUIRED` | yes |
| `REQUIRE_APPROVER` (absent) | ESCALATE_TO_HUMAN | `HUMAN_ONLY` | OBTAIN_APPROVAL | `R_APPROVAL_REQUIRED` | yes (human) |
| `REQUIRE_APPROVER` (present, invalid) | DENY | `TERMINAL` | NONE | `R_APPROVAL_INVALID` | **no** |
| `MAX_SCOPE` | ESCALATE_TO_HUMAN | `HUMAN_ONLY`¹ | REDUCE_SCOPE | `R_SCOPE_EXCEEDED` | yes |
| `MAX_COST` | ESCALATE_TO_HUMAN | `HUMAN_ONLY`¹ | REDUCE_COST | `R_COST_EXCEEDED` | yes |
| `MAX_BLAST_RADIUS` | ESCALATE_TO_HUMAN | `HUMAN_ONLY`¹ | REDUCE_BLAST_RADIUS | `R_BLAST_RADIUS_EXCEEDED` | yes |
| `MAX_IRREVERSIBILITY` | ESCALATE_TO_HUMAN | `HUMAN_ONLY`¹ | REDUCE_IRREVERSIBILITY | `R_IRREVERSIBILITY_EXCEEDED` | yes |
| `FORBID` (fact true) | DENY | `TERMINAL` | NONE | `R_FORBIDDEN` | **no** |
| `DENY` (guarded) | DENY | `TERMINAL` | NONE | `R_FORBIDDEN` | **no** |
| `REQUIRE` (fact false) | DENY | `TERMINAL`² | NONE | `R_REQUIRE_UNMET` | **no** |
| `PRIV_MONO` | DENY | `TERMINAL` | NONE | `R_PRIV_NON_MONOTONIC` | **no** |
| `TICKET_SOD` | DENY | `TERMINAL` | NONE | `R_TICKET_SOD` | **no** |
| `FRESHNESS` (stale) | REQUEST_MORE_EVIDENCE | `EVIDENCE_RETRYABLE` | REFRESH_STATE | `R_STALE_STATE` | yes |
| no rule for operation | ESCALATE_TO_HUMAN | `HUMAN_ONLY` | OBTAIN_APPROVAL | `R_NO_RULE` | yes (human) |
| schema invalid / policy mismatch (pre-rule) | DENY | `TERMINAL` | NONE | `R_SCHEMA_INVALID`/`R_POLICY_MISMATCH` | **no** |

¹ `MAX_*` default to `HUMAN_ONLY`. Only if the policy effect explicitly opts in
(`"remediation": {"retry_class": "ACTION_MODIFICATION_RETRYABLE"}`) does it become
`ACTION_MODIFICATION_RETRYABLE` (and then `retryability.new_action_hash_required = true`).
Missing metadata fails conservatively — no automatic action-modification advice.

² `REQUIRE` is TERMINAL by default (conservative); a policy may opt a truthfully-settable
argument into `ACTION_MODIFICATION_RETRYABLE`, but the projection never fabricates facts.

**Security clamp:** `FORBID`, `DENY`, hard `MUST_HAVE`, `REQUIRE`, `PRIV_MONO`, `TICKET_SOD`,
present-but-invalid `REQUIRE_APPROVER`, and the pre-rule DENYs are in an always-terminal set;
any policy metadata attempting to make them retryable is ignored (tested).

`retry_budget` is always `{max_attempts:null, deadline:null, compute_budget:null}` in R1
(no orchestrator). `requires_new_approval` is true for `HUMAN_ONLY` and
`ACTION_MODIFICATION_RETRYABLE`; `invalidates_prior_evidence` is true for evidence/simulation/
action-modification classes (fresh, freshly-bound evidence is required).
