# CER Cross-Profile Security (Deliverable 5)

The §9 security assertions, each proven by an executed test in `tests/test_cross_profile_security.py` (+ the runner). Grounded in the frozen ActionGate v2 binding semantics.

Labels: `FACT` (tested).

| # | Assertion | How it holds | Test |
|---|---|---|---|
| 1 | **scale evidence cannot authorize rollout** | Evidence binds to the v2 `action_hash`; scale and rollout have different action_hashes, so `verify_binding` raises `EvidenceBindingError` (fail closed) | `test_scale_evidence_cannot_authorize_rollout` |
| 2 | **rollout approval cannot authorize scale** | Approval binds to `action_hash`; `verify_approval` raises `ActionHashMismatchError` when checked against the scale action | `test_rollout_approval_cannot_authorize_scale` |
| 3 | **profile identifier participates in domain separation** | The profile maps 1:1 to `tool.tool_name` (`scale`/`rollout`), inside the hashed payload → different digests | `test_profile_participates_in_domain_separation` |
| 4 | **identical field names do not create collisions** | Same `target` under both profiles still yields different digests (tool_name separates) | `test_identical_field_names_no_collision` |
| 5 | **unsupported profiles fail closed** | `get_profile`/`validate_cer` raise `CERValidationError` on unknown profile | `test_unsupported_profile_fails_closed`; corpus 15 |
| 6 | **profile downgrade fails closed** | Prohibited-field enforcement rejects a rollout-only field under scale (and vice-versa) | `test_profile_downgrade_fails_closed`; corpus 18 |
| 7 | **V0.1 and V0.2 semantics cannot be confused** | The V0.2 validator rejects a `cer_version:"0.1"` CER; scale.v1 nevertheless yields the same *actuation* identity as V0.1 (identity is the actuation, not the wrapper) | `test_v01_and_v02_cannot_be_confused`, `test_v02_scale_matches_v01_identity` |
| 8 | **legacy ActionGate profile remains verifiable** | `identity_profile="v1"` still computes and is domain-separated from v2 | `test_legacy_actiongate_profile_remains_verifiable` |
| 9 | **provenance cannot alter the action digest** | ActionGate v2 excludes runtime/model/objective; changing provenance leaves the digest unchanged | `test_provenance_cannot_alter_digest` |
| 10 | **material actuation changes always alter the digest** | Any identity-bearing change (image digest, strategy, target, replicas) changes the v2 digest | `test_material_change_always_alters_digest`; corpus 05–08 |

`FACT`. Runner metric `cross_profile_collisions = 0`; `evidence_transfer_rejected = 1`; `invalid_ok = 4/4`. No cross-profile identity collision was produced anywhere in the 47-vector corpus.
