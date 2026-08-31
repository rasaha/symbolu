# R1 Migration Notes

## For existing consumers — nothing changes unless you opt in
- Default is `remediation_mode = OFF`. With OFF, every decision response is **byte-identical**
  to the pre-R1 output. No field is added, removed, renamed, or retyped.
- `action_hash`, `policy_hash`, approval/evidence/token digests, the hashed audit payload, and
  all 24 conformance vectors are **unchanged**. No policy re-signing. No golden-hash re-issue.
- Consumers that ignore unknown response fields keep working when remediation is enabled by a
  caller — the added fields are additive and optional.

## To adopt remediation
- Library: call `remediation.project_remediation(decision, envelope, signed_policy, …,
  disclosure_mode=…)` after `gate.evaluate`, or use `remediation.decide_with_remediation(…)`.
- CLI: `decide --remediation-mode minimal|standard|trusted-planner|human-only|full`
  (privileged modes require `--trusted-admin`, non-production).
- Versioning: this is an **additive extension → SemVer MINOR**. `response_schema_version`
  becomes `"1.1"` only when remediation is present.

## Downstream packages (gateway / MCP / k8s / isolated)
- They construct their own response objects and do **not** spread the raw decision, so they are
  **unaffected** by R1 and their suites pass unchanged (gateway 39, MCP 43, k8s 14). Adding an
  opt-in remediation passthrough to those transports is a **later phase**, not R1.
- Do not make any downstream package *depend* on remediation metadata.

## Policy authors (optional)
- Rule effects may carry additive optional `remediation` metadata
  (`retry_class`, `category`, `disclosure_level`, `requirement_code`, `field_path`,
  `acceptable_bounds_disclosure`). Defaults preserve current behavior; missing metadata fails
  conservatively (no action-modification advice, no threshold disclosure, no retryability
  upgrade). Security-critical terminal conditions ignore any such metadata.
- **Policy-hash implication:** because the signed bundle is hashed whole, adding `remediation`
  metadata to a signed rule **changes `policy_hash`** (correctly — it is authorization-relevant
  and must be signed). The reference default policy is left unchanged, so its hash is stable.
  Do not smuggle remediation metadata outside the signed object to avoid the hash change.

## What does NOT migrate
No new outcome, no retry orchestrator, no planner, no auto-execution. Every revised action is
a fresh evaluation; where material fields change, prior approvals/evidence/tokens do not carry
over (they are bound to the old `action_hash`).
