# Canonical 49-guard mutation sweep — Cloud Scaling Phase 5A

> **Superseded for coverage purposes by `GUARD_INVENTORY.md` and
> `guard_classification.json`.** That pair is generated from source, reconciled against the
> recorded 65 + 28, and enforced in CI over **109** guards; the 49 below are a subset,
> measured at a head whose line numbers have since moved. This document is kept because it
> records *classifications*, and three of them are refuted by measurement — which is worth
> more as a correction than as a deletion. See "Three classifications this document got
> wrong" below.

Deterministic inventory: 87 raw `raise` sites -> 85 loose guards -> 81 strict guards ->
**49 canonical in-scope guards** (`reconciliation.py` then `candidate.py`, source order).
Anchors hold: guard 11 = `reconciliation.py:226 p_tenant != d_tenant`, guard 13 =
`reconciliation.py:236 p_subject_digest != d_subject_digest`.

Mutation: the guard's `if` header is rewritten to `if False:`, neutralising exactly that
guard. Every run is a disposable untracked copy; the tracked worktree is never mutated.
A run is scored only if it collected the full suite.

| At `dd1c8724` (audited head) | **28 killed / 21 survived** |
| At the remediated head | **33 killed / 16 survived** |
|---|---|

`attack` is a direct public-builder attack submitted with **only that guard neutralised**.

| # | file:line | condition | before | after | attack w/ guard removed | responsible test(s) | classification if survived |
|---|---|---|---|---|---|---|---|
| 1 | `reconciliation.py:112` | `isinstance(value, bool) or not isinstance(value, int) or value < 0` | survived | survived | REFUSED | — | unreachable defence in depth — the same magnitudes are validated by ExecutionTargetScope, and guard 39 forces scope and projection to agree |
| 2 | `reconciliation.py:121` | `not isinstance(value, datetime)` | survived | survived | REFUSED | — | sibling-backed — guard 3 rejects the same value; fails closed but untyped (AttributeError on .tzinfo) |
| 3 | `reconciliation.py:123` | `value.tzinfo is None or value.utcoffset() is None` | survived | **killed** | ADMITTED | test_a_timezone_naive_validity_timestamp_is_refused[decision-evaluated_at-projection_reconciliation_failed]; test_a_timezone_naive_validity_timestamp_is_refused[decision-expires_at-missing_expiry_fact] (+5 more) | — |
| 4 | `reconciliation.py:141` | `type(projection) is not CapacityRiskSubjectProjection` | killed | **killed** | — | test_object_new_fabricated_sources_are_refused; test_subclass_controlled_property_cannot_divert_a_read (+1 more) | — |
| 5 | `reconciliation.py:147` | `type(decision) is not SubjectRiskDecision` | killed | **killed** | — | test_subclass_sources_are_refused[decision] | — |
| 6 | `reconciliation.py:199` | `validation.context_digest != p_context_digest` | survived | survived | REFUSED | — | sibling-backed — guard 10 compares the same p_context_digest against the carried context |
| 7 | `reconciliation.py:204` | `validation.subject_digest != p_subject_digest` | killed | **killed** | — | test_a_fabricated_projection_with_a_tampered_digest_is_refused[subject_digest-subject_digest_mismatch] | — |
| 8 | `reconciliation.py:209` | `validation.recommendation_digest != p_recommendation_digest` | killed | **killed** | — | test_a_fabricated_projection_with_a_tampered_digest_is_refused[recommendation_digest-recommendation_mismatch] | — |
| 9 | `reconciliation.py:214` | `p_request.digest() != p_request_digest` | survived | **killed** | ADMITTED | test_a_projection_whose_request_digest_is_a_lie_is_refused; test_the_canonical_guard_numbers_still_name_these_conditions (+1 more) | — |
| 10 | `reconciliation.py:219` | `p_context.digest() != p_context_digest` | survived | survived | REFUSED | — | sibling-backed — guard 6 compares the same p_context_digest against the revalidated binding |
| 11 | `reconciliation.py:226` | `p_tenant != d_tenant` | killed | **killed** | — | test_a_decision_issued_for_another_tenant_is_refused; test_the_projection_decision_binding_reaches_no_later_authority[tenant_id] | — |
| 12 | `reconciliation.py:231` | `p_request_digest != d_request_digest` | killed | **killed** | — | test_stale_phase4_digest_with_recomputed_outer_fields_is_refused; test_every_invalid_case_produces_no_candidate | — |
| 13 | `reconciliation.py:236` | `p_subject_digest != d_subject_digest` | killed | **killed** | — | test_a_decision_made_about_another_subject_is_refused; test_the_projection_decision_binding_reaches_no_later_authority[subject_digest] | — |
| 14 | `reconciliation.py:243` | `p_request.subject_type != SUBJECT_TYPE_CAPACITY_SUBJECT` | killed | **killed** | — | test_a_request_carrying_a_non_D4_identifier_is_refused[subject_type-some.other_subject_type] | — |
| 15 | `reconciliation.py:249` | `p_request.requested_purpose != PURPOSE_CAPACITY_ACTION` | killed | **killed** | — | test_a_request_carrying_a_non_D4_identifier_is_refused[requested_purpose-some.other_purpose] | — |
| 16 | `reconciliation.py:255` | `p_request.requested_domain != DOMAIN_CLOUD_SCALING` | killed | **killed** | — | test_a_request_carrying_a_non_D4_identifier_is_refused[requested_domain-some_other_domain] | — |
| 17 | `reconciliation.py:263` | `action_type not in CANONICAL_ACTION_TYPES` | survived | survived | REFUSED | — | unreachable defence in depth — ExecutionTargetScope refuses a non-canonical action, and guard 38 forces scope and projection to agree |
| 18 | `reconciliation.py:270` | `not isinstance(d_disposition, SubjectRiskDisposition)` | survived | survived | REFUSED | — | sibling-backed — guard 19's ALLOW-family membership test rejects a non-disposition; fails closed but untyped |
| 19 | `reconciliation.py:274` | `d_disposition not in ALLOW_FAMILY_DISPOSITIONS` | killed | **killed** | — | test_non_allow_family_dispositions_are_refused[NOT_EVALUATED]; test_non_allow_family_dispositions_are_refused[RISK_DENIED] (+2 more) | — |
| 20 | `reconciliation.py:280` | `d_risk_outcome is None` | survived | survived | REFUSED | — | non-security validation — risk_outcome.value is read when the facts are built, so absence still fails closed; untyped |
| 21 | `reconciliation.py:287` | `d_decision_snapshot is None` | survived | survived | REFUSED | — | sibling-backed — guard 22's Mapping test rejects None |
| 22 | `reconciliation.py:292` | `not isinstance(d_decision_snapshot, Mapping)` | survived | survived | REFUSED | — | sibling-backed — digest_of_snapshot refuses a non-mapping snapshot |
| 23 | `reconciliation.py:297` | `d_decision_digest is None` | survived | survived | REFUSED | — | sibling-backed — require_canonical_digest refuses None |
| 24 | `reconciliation.py:306` | `recomputed != d_decision_digest` | killed | **killed** | — | test_decision_digest_mismatch_is_refused; test_mutated_decision_snapshot_is_refused (+1 more) | — |
| 25 | `reconciliation.py:313` | `decision_id is None` | survived | survived | REFUSED | — | sibling-backed — require_canonical_identifier refuses None |
| 26 | `reconciliation.py:320` | `snapshot_tenant != p_tenant` | survived | **killed** | ADMITTED | test_a_decision_snapshot_naming_another_tenant_is_refused; test_the_canonical_guard_numbers_still_name_these_conditions (+1 more) | — |
| 27 | `reconciliation.py:325` | `snapshot_domain != DOMAIN_CLOUD_SCALING` | survived | **killed** | ADMITTED | test_a_decision_snapshot_naming_another_domain_is_refused; test_the_canonical_guard_numbers_still_name_these_conditions (+2 more) | — |
| 28 | `reconciliation.py:333` | `not p_idempotency_key` | survived | survived | REFUSED | — | sibling-backed — guard 30 rejects the resulting inequality, then require_canonical_digest refuses the empty key |
| 29 | `reconciliation.py:338` | `not d_idempotency_key` | survived | survived | REFUSED | — | sibling-backed — guard 30 rejects the resulting inequality |
| 30 | `reconciliation.py:342` | `p_idempotency_key != d_idempotency_key` | killed | **killed** | — | test_idempotency_key_mismatch_is_refused | — |
| 31 | `reconciliation.py:349` | `not isinstance(p_evidence_references, tuple) or not p_evidence_references` | survived | survived | REFUSED | — | sibling-backed — guard 32 rejects the mismatch the empty tuple creates |
| 32 | `reconciliation.py:356` | `tuple(p_request.evidence_references) != tuple(p_evidence_references)` | survived | **killed** | ADMITTED | test_a_projection_misstating_the_requests_evidence_is_refused; test_the_canonical_guard_numbers_still_name_these_conditions (+1 more) | — |
| 33 | `reconciliation.py:362` | `not evidence_snapshot_digest` | survived | survived | REFUSED | — | sibling-backed — require_canonical_digest refuses the empty digest |
| 34 | `reconciliation.py:382` | `d_expires_at is None` | survived | survived | REFUSED | — | sibling-backed — _require_datetime refuses None via guard 2 |
| 35 | `candidate.py:415` | `a_recommendation_digest != facts.recommendation_digest` | killed | **killed** | — | test_attestation_for_another_recommendation_is_refused; test_every_invalid_case_produces_no_candidate (+1 more) | — |
| 36 | `candidate.py:423` | `s_tenant != facts.tenant_id` | killed | **killed** | — | test_no_candidate_and_no_collaborator_on_any_isolated_gate[cross_tenant_scope]; test_target_scope_naming_another_tenant_is_refused | — |
| 37 | `candidate.py:427` | `not s_account` | killed | **killed** | — | test_a_scope_forced_past_its_own_account_check_is_refused; test_no_candidate_and_no_collaborator_on_any_isolated_gate[forced_account] | — |
| 38 | `candidate.py:432` | `s_action_type != facts.action_type` | killed | **killed** | — | test_action_substitution_is_refused; test_every_invalid_case_produces_no_candidate | — |
| 39 | `candidate.py:438` | `s_magnitude_before != facts.magnitude_before` | killed | **killed** | — | test_no_candidate_and_no_collaborator_on_any_isolated_gate[understated_origin]; test_target_scope_misstating_the_starting_magnitude_is_refused | — |
| 40 | `candidate.py:443` | `s_requested_magnitude != facts.magnitude_after` | killed | **killed** | — | test_no_candidate_and_no_collaborator_on_any_isolated_gate[inflated_target]; test_target_scope_requesting_a_different_target_magnitude_is_refused | — |
| 41 | `candidate.py:466` | `b_target_scope_digest != s_digest` | killed | **killed** | — | test_policy_binding_for_another_account_is_refused; test_every_invalid_case_produces_no_candidate | — |
| 42 | `candidate.py:471` | `b_max_magnitude != s_max_magnitude or b_max_delta != s_max_delta` | killed | **killed** | — | test_scope_cannot_widen_bounds_beyond_the_policy | — |
| 43 | `candidate.py:478` | `s_requested_magnitude > b_max_magnitude` | killed | **killed** | — | test_a_scope_forced_past_its_own_magnitude_ceiling_is_refused; test_no_candidate_and_no_collaborator_on_any_isolated_gate[forced_magnitude] | — |
| 44 | `candidate.py:484` | `facts.requested_delta > b_max_delta` | killed | **killed** | — | test_a_scope_forced_past_its_own_delta_ceiling_is_refused; test_no_candidate_and_no_collaborator_on_any_isolated_gate[forced_delta] | — |
| 45 | `candidate.py:225` | `self.schema_version != AUTHORIZATION_CANDIDATE_SCHEMA_VERSION` | killed | **killed** | — | test_unsupported_schema_version_is_refused_on_every_artifact | — |
| 46 | `candidate.py:249` | `self.candidate_digest != expected_digest` | killed | **killed** | — | test_candidate_cannot_be_constructed_with_a_wrong_digest; test_rogue_policy_issuer_attack_is_closed | — |
| 47 | `candidate.py:377` | `type(value) is not expected` | killed | **killed** | — | test_duck_typed_lookalikes_are_refused; test_every_invalid_case_produces_no_candidate | — |
| 48 | `candidate.py:458` | `scope_value != projected_value` | killed | **killed** | — | test_target_substitution_is_refused[compute_group-prod-eu-west-1-green]; test_target_substitution_is_refused[environment-staging] (+4 more) | — |
| 49 | `candidate.py:241` | `type(value) is not expected` | killed | **killed** | — | test_candidate_post_init_refuses_a_wrong_typed_carried_artifact | — |

## Survivor classification totals

| class | count |
|---|---|
| non-security validation | 1 |
| sibling-backed | 13 |
| unreachable defence in depth | 2 |
| **unresolved survivors** | **0** |

Every survivor was attacked directly through the public builder with only that guard
neutralised, and every one of them still refused: **no surviving guard admits a new
invalid candidate.** Three (guards 2, 18, 20) fail closed with an untyped `AttributeError`
rather than a typed rejection — disclosed as a robustness observation, not a lapse, since
no candidate is constructed in any of them.


## Three classifications this document got wrong

Every survivor above was attacked "directly through the public builder". That is the flaw:
`reconcile_phase4` is exported in `__all__` and is a public entry point of its own, and a
caller reaching it does not pass through `ExecutionTargetScope` or the candidate builder at
all. Three survivors classified as needing no coverage admit their attack outright on that
path, measured with only the named guard removed:

| Here | Now | This document said | Measured on the `reconcile_phase4` path |
|---|---|---|---|
| 1 | 44 | *unreachable defence in depth — the same magnitudes are validated by ExecutionTargetScope* | **ADMITTED.** A self-consistent projection carrying `magnitude_before=-1` reconciles with no refusal. No scope is involved. |
| 10 | 54 | *sibling-backed — guard 6 compares the same `p_context_digest`* | **Not interchangeable.** Guard 6/50 re-derives from the **request**; guard 10/54 digests the projection's **own** `context` object. A projection with a genuine request and a swapped context passes the first and fails only the second. |
| 17 | 61 | *unreachable defence in depth — ExecutionTargetScope refuses a non-canonical action* | **ADMITTED.** A fully re-derived projection naming `scale_sideways` reconciles with no refusal. |

The remaining thirteen classifications are accurate about what they claim — the guard's
removal still fails closed, via a sibling or an untyped attribute access. They were wrong
only in what was concluded from it: a guard whose removal changes the *reason* a refusal is
given is not covered by a test that only checks that some refusal happened. This package
has since ratified the typed refusal as part of the contract, so all thirteen are now
scored rather than excluded.

The summary sentence above — *"no surviving guard admits a new invalid candidate"* — holds
for the builder path it was measured on and does not hold for the reconciler path.

## What this PR added, and what each new test measures

The 2026-08-27 CI sweep at `932869c3` neutralised all **109** guards of the current
inventory — a superset of the 49 above — and found **31 survivors**. 28 of them are now
covered. A kill says the suite noticed the guard was gone; it does not say what it
noticed, so each was measured a second time with only that guard removed:

* **ADMITTED** — the boundary produced *no refusal at all*. The guard is the only thing
  between the attack and a reconciled fact.
* **UNTYPED** — it still failed closed, but through an `AttributeError` or `KeyError`
  rather than a typed refusal.
* **MISDIAGNOSED** — it still refused, with another guard's reason.

All three are defects under this package's ratified position that the typed refusal is
part of the contract. They are not the same defect, and the distinction is recorded here
rather than flattened into the word *killed*.

| # | Module:line | Effect with the guard removed | What the mutant did instead |
|---|---|---|---|
| 1 | `canonical.py:82` | ADMITTED | `— (no exception)` |
| 7 | `canonical.py:171` | ADMITTED | `— (no exception)` |
| 12 | `target.py:101` | MISDIAGNOSED | `MagnitudeBoundError: requested delta 3 exceeds the permitted maximum delta True` |
| 15 | `target.py:168` | ADMITTED | `— (no exception)` |
| 18 | `target.py:268` | MISDIAGNOSED | `CanonicalFieldError: unknown execution-target-scope field(s): [('tenant_id', 't-1')]` |
| 24 | `target.py:436` | MISDIAGNOSED | `CanonicalFieldError: unknown policy-target-binding field(s): [('policy_id', 'p-1')]` |
| 26 | `target.py:453` | UNTYPED | `KeyError: 'policy_id'` |
| 28 | `target.py:562` | ADMITTED | `— (no exception)` |
| 29 | `target.py:572` | ADMITTED | `— (no exception)` |
| 31 | `target.py:659` | MISDIAGNOSED | `CanonicalFieldError: unknown policy-coordinate-binding field(s): [('policy_id', 'p-1')]` |
| 37 | `attestation.py:133` | MISDIAGNOSED | `ProducerAttestationError('signing_payload_digest does not equal the digest of the canonical signing payload')` |
| 40 | `attestation.py:234` | MISDIAGNOSED | `CanonicalFieldError: unknown producer-attestation field(s): [('producer_id', 'p-1')]` |
| 42 | `attestation.py:250` | UNTYPED | `KeyError: 'producer_id'` |
| 43 | `attestation.py:255` | UNTYPED | `KeyError: 'schema_version'` |
| 44 | `reconciliation.py:122` | ADMITTED | `— (no exception)` |
| 50 | `reconciliation.py:283` | MISDIAGNOSED | `ReconciliationError('context_digest does not match the carried context')` |
| 54 | `reconciliation.py:303` | MISDIAGNOSED | `ReconciliationError("action_type 'scale_sideways' is not a D-4 ratified canonical action type")` |
| 61 | `reconciliation.py:364` | ADMITTED | `— (no exception)` |
| 62 | `reconciliation.py:371` | UNTYPED | `AttributeError: 'str' object has no attribute 'value'` |
| 64 | `reconciliation.py:381` | UNTYPED | `AttributeError: 'NoneType' object has no attribute 'value'` |
| 65 | `reconciliation.py:388` | MISDIAGNOSED | `ReconciliationError('decision_snapshot must be a canonical mapping')` |
| 66 | `reconciliation.py:393` | MISDIAGNOSED | `CanonicalFieldError: a canonical snapshot must be a mapping` |
| 67 | `reconciliation.py:398` | MISDIAGNOSED | `CanonicalFieldError: decision_digest must be a canonical sha256:<64 lowercase hex> digest (got None)` |
| 69 | `reconciliation.py:414` | MISDIAGNOSED | `CanonicalFieldError: decision_snapshot.decision_id must be a string (got NoneType)` |
| 72 | `reconciliation.py:444` | MISDIAGNOSED | `CanonicalFieldError: projection.idempotency_key must be a canonical sha256:<64 lowercase hex> digest (got ''` |
| 75 | `reconciliation.py:468` | MISDIAGNOSED | `ReconciliationError("the request's evidence_references differ from the projection's")` |
| 77 | `reconciliation.py:481` | MISDIAGNOSED | `CanonicalFieldError: evidence_snapshot_digest must be a canonical sha256:<64 lowercase hex> digest (got None` |
| 81 | `reconciliation.py:538` | MISDIAGNOSED | `ReconciliationError('expires_at must be a datetime (got None)')` |
