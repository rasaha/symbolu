# Eligibility Policy & Procedure

P1 is a **hard gate only** — every constraint is pass/fail; there are no preference
weights. `EligibilityPolicy` is policy-as-data controlling a generic deterministic
interpreter; enterprise decisions live in `EnterpriseAgentPolicy`, not in scattered
conditionals.

## Deterministic evaluation order

`evaluate_agent_eligibility(role, profile, snapshot, enterprise_policy,
eligibility_policy, logical_time)` evaluates constraints in
`EligibilityPolicy.evaluation_order` (default):

1. `input_integrity` — malformed role/profile → `INVALID_INPUT`; snapshot digest
   mismatch → `SNAPSHOT_INTEGRITY_FAILURE`
2. `pinned_versions` — contract-version pinning
3. `agent_status_and_version` — revoked / inactive / expired / approved-set
4. `capability_presence` — `MISSING_REQUIRED_CAPABILITY`
5. `capability_evidence` — DECLARED/MEASURED/OBSERVED discipline (see
   EVIDENCE_AND_PROVENANCE.md)
6. `input_output_contract` — schema subset compatibility
7. `tools` — required / prohibited / allow-list
8. `provider` — forbidden / not-approved / role-constrained
9. `residency_deployment`
10. `security_audit`
11. `permissions` — permission monotonicity (never broader than policy)
12. `authority_ceiling`
13. `hard_limits` — cost / latency / quality

The engine does **not** stop at the first failure (unless `short_circuit=True`):
it accumulates every applicable hard failure so the explanation is complete.

## Classification

- any FAIL → `INELIGIBLE`
- else any UNKNOWN → `INELIGIBLE` if `fail_closed_on_unknown` (default) else `INDETERMINATE`
- else `ELIGIBLE`

`ELIGIBLE` means only: no currently evaluated hard constraint disqualifies this
agent for this role under the pinned inputs. A role with zero eligible agents
returns the typed outcome `NO_ELIGIBLE_AGENT`.
