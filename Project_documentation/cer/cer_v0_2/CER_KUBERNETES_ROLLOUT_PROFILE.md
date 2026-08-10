# CER Profile — kubernetes.rollout.v1 (Deliverable 3)

The second, materially distinct actuation profile. Grounded in `cer_v0_2/profiles/rollout.py` + `kubernetes.rollout.v1.schema.json`.

Labels: `FACT` (implemented/tested) · `RECOMMENDATION`.

## 1. Why rollout (materially distinct from scale)
`FACT`. A rollout changes the *manifest/image*, not the *replica count*. Its identity-bearing fields do not exist in scale: `image_digest`, `current_manifest_digest`, `rollout_strategy`, `max_surge`, `max_unavailable`, `timeout_s`, `rollback_ref`. This exercises identity-bearing fields absent from the scale profile (H2). It is not an alias for scale.

## 2. Identity-bearing fields
`FACT` (in the action digest):
- `tool.tool_name = "rollout"` (domain separator)
- `operation = DEPLOY`
- `target_resource = [namespace/deployment]`
- `arguments = {image_digest, current_manifest_digest, rollout_strategy, max_surge, max_unavailable, timeout_s}` (typed strings)
- `rollback_plan = {ref: rollback_ref}` when present (identity-bearing via ActionGate's rollback_plan projection)
- `reversibility`, `credential_scope`, `state_binding`, `policy_ref` (as in the envelope)

## 3. Argument normalization & units
`FACT` (`rollout._arguments`, `validate_actuation`): `image_digest`/`current_manifest_digest` are `sha256:<64hex>` (validated); `rollout_strategy` ∈ {RollingUpdate, Recreate}; `max_surge`/`max_unavailable`/`timeout_s` are **integer strings** (counts / whole seconds) — Action Profile typed-string numerics, no bare numbers. Canonicalization sorts keys.

## 4. Prohibited fields (downgrade guard)
`FACT`. `requested_state_transition` and `replicas` are prohibited under rollout (scale-only). A scale payload submitted under the rollout profile fails closed, and vice-versa.

## 5. Null / omission & extensions
`FACT`. All required fields must be present and non-null (fail closed); `rollback_ref` is optional. Unknown actuation fields and non-empty unrecognized `extensions` fail closed.

## 6. ActionGate projection & ACP mapping
`FACT`. Projection: `to_envelope` (§2). ACP: `CloudActionCandidate(operation=ROLLOUT, manifest_digest=image_digest, rollout_strategy, max_surge, max_unavailable, rollback_ref, current==desired replicas)` — a rollout does not change replicas, so blast radius is 0 and the ACP readiness/freeze/cooldown constraints still apply. Measured: safe rollout → PROCEED; rollout during a freeze → HELD_BY_ACP (`FREEZE_WINDOW_ACTIVE`).

## 7. Measured identity properties
`FACT`: rollout digest `72ddae26…` (base fixture); provenance-invariant; `image_digest` change → different digest; `rollout_strategy` change → different digest; ≠ scale digest for the same target. Exact-action binding preserved.
