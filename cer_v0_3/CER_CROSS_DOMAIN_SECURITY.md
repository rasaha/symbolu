# CER Cross-Domain Security (Deliverable 5)

The §11 security invariants, each proven by an executed test and/or the cross-domain
runner. Grounded in the frozen ActionGate v2 binding semantics and the frozen ACP
composition invariants.

Labels: `FACT` (tested). Machinery: `conformance/cross_domain.py`,
`conformance/cross_domain_results.json`, `tests/test_cross_domain_security.py`,
`tests/test_differential.py`.

| # | Invariant | How it holds | Evidence |
|---|---|---|---|
| 1 | clean-room & original digests agree for every valid vector | independent implementations reproduce byte-identical payload/bytes/digest | differential 73/73; cross-domain `cleanroom_agreement` |
| 2 | invalid vectors fail closed in both | both implementations reject each invalid vector | differential `error_category_agree` 4/4; cross-domain `invalid_ok` 9/9 (both) |
| 3 | no secret enters identity / logs / traces / output | recursive secret guard rejects secret keys + credential value patterns before hashing | `test_no_secret_in_identity`; corpus `I01` |
| 4 | same actuation, independent producers -> same digest | ugence + tool-runtime -> identical digest `05ad2c02…` | `producer_agreement`; `test_two_producers_same_digest` |
| 5 | material change -> different digest | any identity-bearing change alters the v2 digest | `different_ok` 9/9; `test_material_change_alters_digest` |
| 6 | cross-profile evidence cannot transfer | evidence binds to the action's v2 `action_hash`; different digests -> `EvidenceBindingError` | `test_k8s_evidence_cannot_authorize_db`; runner `evidence_transfer_rejected` |
| 7 | Kubernetes & database actions cannot collide | `tool.server_id`+`tool.tool_name`+disjoint args domain-separate inside the hash | `cross_profile_collisions=0`; `test_no_cross_domain_collision` |
| 8 | unknown profiles fail closed | `get_profile`/`validate_cer` reject unknown profile | corpus `I06`; `test_unknown_profile_and_downgrade_fail_closed` |
| 9 | profile downgrade fails closed | K8s-only field under the database profile is prohibited | corpus `I13`; same test |
| 10 | runtime provenance does not affect identity | v2 excludes runtime/model/objective | `provenance_invariant`; `test_provenance_invariant` |
| 11 | ActionGate denial cannot be overridden by ACP | `compose()` maps gate DENY -> `BLOCKED_BY_AUTHORIZATION` | `test_actiongate_deny_final`; corpus `I15` |
| 12 | ACP cannot grant authorization | gate pending -> `PENDING_AUTHORIZATION` regardless of ACP | `test_acp_cannot_authorize_pending`; corpus `D20` |
| 13 | stale state invalidates execution eligibility | DB state drift (`expected_row_version` mismatch) -> `HELD_BY_ACP`, not eligible | `test_stale_state_holds`; corpus `I09` |
| 14 | no runtime-specific branch enters ActionGate or ACP | 0 runtime tokens in the frozen AG/ACP sources | `ownership_no_runtime_switch=true`; `test_no_runtime_branch` |
| 15 | no bypass reaches the real tool executor in governed mode | the tool-runtime intercepts the pending `db.mutation` call; the tool never executes | `test_tool_runtime_does_not_execute_before_governance`; corpus `I14` |
| — | action modified after approval fails closed | approval binds to `action_hash`; modifying the action -> `ActionHashMismatchError` | runner `approval_replay_rejected`; corpus `I10` |

`FACT`. Cross-domain runner: **29/29 cases passed**, `evidence_transfer_rejected=3/3`,
`cross_profile_collisions=0`, `invalid_ok=9/9`, regression digests unchanged, ownership
clean. No secret string appears anywhere in the canonical bytes or conformance output.
