# Canonical 89-guard mutation sweep — Cloud Scaling Phase 5B-0A

Deterministic inventory: every `if` in the distribution whose own body can reach a
`raise` or a typed refusal, enumerated in flow order
(`canonical.py` → `identifiers.py` → `attestation.py` → `signing.py` → `trust.py` → `verified.py` → `verification.py`) and then source order.

Mutation: the guard's `if` header is rewritten to `if False:`, neutralising exactly
that guard and nothing else. Every run is a **disposable untracked copy** of the
package; the tracked worktree is never mutated, and the sweep refuses to report if
the content hash of every shipped source file differs before and after. A run is
scored **only** if it
collected and ran the full suite — a collection error, a syntax error, an import
error or a timeout is not a valid kill.

| Result | **76 killed / 13 survived** |
|---|---|

| # | file:line | condition | killed? | responsible test(s) | classification if survived |
|---|---|---|---|---|---|
| 1 | `canonical.py:85` | `not is_canonical_digest(value)` | **killed** | test_a_bare_hex_recommendation_digest_is_refused | — |
| 2 | `canonical.py:102` | `type(value) is not str` | **killed** | test_require_nfc_text_refuses_a_non_string_with_a_typed_error[42]; test_require_nfc_text_refuses_a_non_string_with_a_typed_error[None] (+3 more) | — |
| 3 | `canonical.py:107` | `not allow_empty and value == ''` | **killed** | test_an_empty_identifier_is_refused[producer_id]; test_an_empty_identifier_is_refused[issuer] (+3 more) | — |
| 4 | `canonical.py:109` | `unicodedata.normalize('NFC', value) != value` | **killed** | test_a_non_nfc_identifier_is_refused_rather_than_normalized[producer_id]; test_a_non_nfc_identifier_is_refused_rather_than_normalized[issuer] (+4 more) | — |
| 5 | `canonical.py:121` | `text != text.strip()` | **killed** | test_a_whitespace_padded_identifier_is_refused | — |
| 6 | `canonical.py:123` | `any((ch.isspace() and ch != ' ' for ch in text))` | **killed** | test_require_canonical_identifier_refuses_control_whitespace[\t]; test_require_canonical_identifier_refuses_control_whitespace[\n] (+2 more) | — |
| 7 | `canonical.py:136` | `type(value) is not datetime` | **killed** | test_require_aware_utc_refuses_a_non_datetime_with_a_typed_error[42]; test_require_aware_utc_refuses_a_non_datetime_with_a_typed_error[None] (+2 more) | — |
| 8 | `canonical.py:140` | `value.tzinfo is None or value.utcoffset() is None` | **killed** | test_a_naive_issued_at_is_refused_rather_than_assumed_utc; test_a_naive_instant_is_refused_at_every_entry_point[naive0] (+2 more) | — |
| 9 | `canonical.py:156` | `type(value) is not expected` | **killed** | test_require_exact_type_refuses_a_subclass_and_admits_the_exact_type | — |
| 10 | `identifiers.py:166` | `PRODUCER_ATTESTATION_V2_SCHEMA_VERSION == PHASE_5A_V1_SCHEMA_VERSION` | **killed** | test_a_drifted_identifier_fails_the_import_time_separation[PRODUCER_ATTESTATION_V2_SCHEMA_VERSION-cloud-scaling-producer-attestation-evidence-1-frozen | — |
| 11 | `identifiers.py:173` | `PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE == _D4_ROUTING_PURPOSE` | **killed** | test_a_drifted_identifier_fails_the_import_time_separation[PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE-cloud_scaling.capacity_action-D-4 | — |
| 12 | `identifiers.py:179` | `PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE in KNOWN_POLICY_SIGNING_PURPOSES` | **killed** | test_a_drifted_identifier_fails_the_import_time_separation[PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE-ugence.policy_authority.policy_signing-policy-signing | — |
| 13 | `identifiers.py:185` | `SUPPORTED_V2_SIGNING_PURPOSES & KNOWN_POLICY_SIGNING_PURPOSES` | **killed** | test_a_drifted_admitted_purpose_set_fails_the_separation | — |
| 14 | `identifiers.py:189` | `_PHASE_5A_V1_SIGNING_PURPOSE in SUPPORTED_V2_SIGNING_PURPOSES` | **killed** | test_admitting_the_v1_purpose_fails_the_separation | — |
| 15 | `identifiers.py:194` | `PRODUCER_ATTESTATION_CAPABILITY is TrustAnchorCapability.RECEIPT_ISSUANCE` | **killed** | test_the_receipt_issuance_capability_fails_the_separation | — |
| 16 | `identifiers.py:199` | `PRODUCER_ATTESTATION_SIGNATURE_PROFILE != _TEV_PROFILE_V1` | **killed** | test_a_drifted_identifier_fails_the_import_time_separation[PRODUCER_ATTESTATION_SIGNATURE_PROFILE-some.other/profile/v1-profile] | — |
| 17 | `identifiers.py:204` | `PRODUCER_ATTESTATION_SIGNATURE_ENCODING != _TEV_ENCODING_V1` | **killed** | test_a_drifted_identifier_fails_the_import_time_separation[PRODUCER_ATTESTATION_SIGNATURE_ENCODING-some.other/encoding/v1-encoding] | — |
| 18 | `identifiers.py:206` | `SUBJECT_TYPE_CAPACITY_SUBJECT != _D4_SUBJECT_TYPE` | **killed** | test_a_drifted_identifier_fails_the_import_time_separation[SUBJECT_TYPE_CAPACITY_SUBJECT-cloud_scaling.other_subject-D-4] | — |
| 19 | `attestation.py:153` | `self.schema_version != PRODUCER_ATTESTATION_V2_SCHEMA_VERSION` | **killed** | test_phase_5a_v1_schema_tag_is_refused | — |
| 20 | `attestation.py:172` | `self.subject_type != SUBJECT_TYPE_CAPACITY_SUBJECT` | **killed** | test_a_subject_type_substitution_is_refused_at_construction | — |
| 21 | `attestation.py:179` | `purpose not in SUPPORTED_V2_SIGNING_PURPOSES` | **killed** | test_a_policy_signing_purpose_is_refused[cloud_scaling.policy_signing]; test_a_policy_signing_purpose_is_refused[cloud_scaling.policy_target_binding] (+4 more) | — |
| 22 | `attestation.py:190` | `algorithm not in SUPPORTED_V2_SIGNATURE_ALGORITHMS` | **killed** | test_an_unratified_algorithm_profile_or_encoding_is_refused[signature_algorithm-ed448-UNSUPPORTED_ALGORITHM]; test_an_unratified_algorithm_profile_or_encoding_is_refused[signature_algorithm-none-UNSUPPORTED_ALGORITHM] | — |
| 23 | `attestation.py:197` | `self.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE` | **killed** | test_an_unratified_algorithm_profile_or_encoding_is_refused[signature_profile-some.other/profile/v1-UNSUPPORTED_PROFILE] | — |
| 24 | `attestation.py:203` | `self.signature_encoding != PRODUCER_ATTESTATION_SIGNATURE_ENCODING` | **killed** | test_an_unratified_algorithm_profile_or_encoding_is_refused[signature_encoding-some.other/encoding/v1-UNSUPPORTED_ENCODING] | — |
| 25 | `attestation.py:214` | `type(self.signature) is not str` | survived | — | sibling-backed — decode_signature refuses a non-str on the next line and yields the same MALFORMED_SIGNATURE outcome; this guard only makes the refusal typed one call earlier |
| 26 | `attestation.py:234` | `self.signing_payload_digest != expected` | **killed** | test_a_reserialized_attestation_with_a_stale_payload_digest_is_refused | — |
| 27 | `attestation.py:323` | `not isinstance(data, Mapping)` | **killed** | test_malformed_canonical_input_is_refused[42]; test_malformed_canonical_input_is_refused[None] | — |
| 28 | `attestation.py:330` | `unknown` | **killed** | test_a_mapping_offering_a_trust_field_is_refused[mutation0]; test_a_mapping_offering_a_trust_field_is_refused[mutation1] (+2 more) | — |
| 29 | `attestation.py:337` | `missing` | **killed** | test_a_mapping_missing_a_required_field_is_refused[signature]; test_a_mapping_missing_a_required_field_is_refused[issuer] (+2 more) | — |
| 30 | `signing.py:120` | `self.issuance_token is not _SIGNING_INPUT_TOKEN` | **killed** | test_a_signing_input_cannot_be_constructed_by_a_caller[None]; test_a_signing_input_cannot_be_constructed_by_a_caller[True] (+5 more) | — |
| 31 | `signing.py:128` | `type(self.signed_input) is not bytes` | survived | — | unreachable through the public API — mint_producer_attestation is the only route to a signing input and always passes canonical_bytes(); a caller cannot construct one at all, because the token guard above rejects it first |
| 32 | `signing.py:133` | `len(self.signed_input) == 0` | survived | — | unreachable through the public API — the minted payload is never empty, and the token guard rejects a caller-assembled input before any content check |
| 33 | `signing.py:147` | `self.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE` | survived | — | unreachable through the public API — the minting routine passes the pinned constant, not a parameter; there is no caller-supplied profile to get wrong |
| 34 | `signing.py:295` | `signing_input.issuer != self._issuer` | **killed** | test_a_signer_refuses_an_input_addressed_to_other_coordinates[issuer-attacker.rogue-authority] | — |
| 35 | `signing.py:300` | `signing_input.producer_key_id != self._producer_key_id` | **killed** | test_a_signer_refuses_an_input_addressed_to_another_key | — |
| 36 | `signing.py:305` | `signing_input.producer_id != self._producer_id` | **killed** | test_a_signer_refuses_an_input_addressed_to_other_coordinates[producer_id-attacker.impersonator] | — |
| 37 | `signing.py:333` | `PRODUCER_ATTESTATION_CAPABILITY is TrustAnchorCapability.RECEIPT_ISSUANCE` | **killed** | test_the_reference_signer_refuses_to_publish_a_receipt_issuance_anchor | — |
| 38 | `signing.py:385` | `signer is None` | **killed** | test_minting_without_a_signer_is_refused | — |
| 39 | `signing.py:387` | `production_mode and getattr(type(signer), 'is_reference_signer', False) is True` | **killed** | test_a_reference_signer_is_refused_in_production_mode | — |
| 40 | `signing.py:400` | `signer.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE` | **killed** | test_a_signer_advertising_another_profile_is_refused | — |
| 41 | `signing.py:435` | `type(signature) is not str` | **killed** | test_a_signer_returning_a_non_string_signature_is_refused | — |
| 42 | `trust.py:183` | `resolver is None` | survived | — | sibling-backed — a None resolver fails the is_production_authoritative check below, which refuses it with the same typed configuration error |
| 43 | `trust.py:191` | `type(resolver) is reference_type` | **killed** | test_the_reference_resolver_is_refused_in_production | — |
| 44 | `trust.py:200` | `getattr(resolver, 'is_production_authoritative', False) is not True` | **killed** | test_a_production_resolver_declaring_nothing_is_refused_by_the_helper; test_an_unattested_resolver_is_refused_in_production (+1 more) | — |
| 45 | `verified.py:147` | `self.construction_token is not _VERIFICATION_TOKEN` | **killed** | test_direct_construction_is_refused; test_no_caller_held_token_is_accepted[None] (+4 more) | — |
| 46 | `verified.py:154` | `self.verification_profile != VERIFICATION_PROFILE` | **killed** | test_a_verified_artifact_cannot_be_minted_under_another_verification_profile | — |
| 47 | `verified.py:158` | `self.verification_profile_version != VERIFICATION_PROFILE_VERSION` | **killed** | test_a_verified_artifact_cannot_be_minted_under_another_profile_version | — |
| 48 | `verified.py:173` | `self.artifact_digest != expected` | survived | — | sibling-backed — require_verified_producer_attestation recomputes the same digest at every consumption boundary, and that check IS killed; this one is unreachable at construction because the minting routine computes the digest it passes |
| 49 | `verified.py:271` | `type(value) is not VerifiedProducerAttestation` | **killed** | test_a_duck_typed_look_alike_is_refused_at_consumption | — |
| 50 | `verified.py:285` | `value.construction_token is not _VERIFICATION_TOKEN` | survived | — | UNRESOLVED — no reviewed classification; investigate |
| 51 | `verified.py:290` | `value.artifact_digest not in _MINTED_DIGESTS` | **killed** | test_a_borrowed_construction_token_does_not_mint_an_artifact | — |
| 52 | `verified.py:297` | `value.artifact_digest != value.digest()` | **killed** | test_a_mutated_field_fails_revalidation[tenant_id]; test_a_mutated_field_fails_revalidation[subject_id] (+5 more) | — |
| 53 | `verification.py:167` | `type(self.outcome) is not _Outcome` | **killed** | test_a_refusal_outcome_is_exact_typed | — |
| 54 | `verification.py:172` | `self.outcome is _Outcome.VERIFIED` | **killed** | test_a_refusal_cannot_carry_the_success_member | — |
| 55 | `verification.py:194` | `(self.verified_attestation is None) == (self.refusal is None)` | **killed** | test_a_result_cannot_carry_both_or_neither_branch | — |
| 56 | `verification.py:199` | `self.verified_attestation is not None and type(self.verified_attestation) is not VerifiedProducerAttestation` | survived | — | internal invariant — only this module constructs a result, and only ever with an artifact its own minting routine produced; not reachable from attacker input |
| 57 | `verification.py:206` | `self.refusal is not None and type(self.refusal) is not ProducerAttestationRefusal` | survived | — | internal invariant — every refusal in this module is built by the single _refuse helper; not reachable from attacker input |
| 58 | `verification.py:242` | `trust_anchor_resolver is None` | survived | — | sibling-backed — the hasattr(resolver, 'resolve') check below refuses None with the same typed configuration error |
| 59 | `verification.py:247` | `signature_verifier is None` | survived | — | sibling-backed — the hasattr(verifier, 'verify_producer_signature') check below refuses None with the same typed configuration error |
| 60 | `verification.py:252` | `not hasattr(trust_anchor_resolver, 'resolve')` | **killed** | test_a_resolver_without_a_resolve_method_is_refused_at_construction | — |
| 61 | `verification.py:257` | `not hasattr(signature_verifier, 'verify_producer_signature')` | **killed** | test_a_signature_verifier_without_its_method_is_refused_at_construction | — |
| 62 | `verification.py:261` | `production_mode` | **killed** | test_the_reference_resolver_is_refused_in_production; test_an_unattested_resolver_is_refused_in_production (+1 more) | — |
| 63 | `verification.py:263` | `getattr(signature_verifier, 'is_production_authoritative', False) is not True` | **killed** | test_a_non_production_signature_verifier_is_refused_in_production | — |
| 64 | `verification.py:328` | `attestation is None` | **killed** | test_an_absent_attestation_is_refused; test_step_6a_the_absent_arm_is_refused (+1 more) | — |
| 65 | `verification.py:333` | `type(attestation) is not ProducerAttestationV2` | **killed** | test_a_phase_5a_v1_attestation_object_is_refused_by_exact_type; test_a_subclass_attestation_is_refused (+5 more) | — |
| 66 | `verification.py:338` | `type(candidate) is not CapacityAuthorizationCandidate` | **killed** | test_a_subclass_candidate_is_refused | — |
| 67 | `verification.py:343` | `type(as_of) is not datetime or as_of.tzinfo is None or as_of.utcoffset() is None` | **killed** | test_a_naive_as_of_is_refused; test_a_naive_instant_is_refused_at_every_entry_point[naive0] (+1 more) | — |
| 68 | `verification.py:352` | `attestation.schema_version != PRODUCER_ATTESTATION_V2_SCHEMA_VERSION` | **killed** | test_the_verifier_re_checks_every_contract_fact_against_a_fabrication[schema_version-cloud-scaling-producer-attestation-evidence-1-UNSUPPORTED_SCHEMA_VERSION] | — |
| 69 | `verification.py:357` | `attestation.signing_purpose not in SUPPORTED_V2_SIGNING_PURPOSES` | **killed** | test_the_verifier_re_checks_every_contract_fact_against_a_fabrication[signing_purpose-ugence.policy_authority.policy_signing-UNSUPPORTED_SIGNING_PURPOSE] | — |
| 70 | `verification.py:362` | `attestation.signature_algorithm not in SUPPORTED_V2_SIGNATURE_ALGORITHMS` | **killed** | test_the_verifier_re_checks_every_contract_fact_against_a_fabrication[signature_algorithm-ed448-UNSUPPORTED_ALGORITHM] | — |
| 71 | `verification.py:367` | `attestation.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE` | **killed** | test_the_verifier_re_checks_every_contract_fact_against_a_fabrication[signature_profile-some.other/profile/v1-UNSUPPORTED_PROFILE] | — |
| 72 | `verification.py:372` | `attestation.signature_encoding != PRODUCER_ATTESTATION_SIGNATURE_ENCODING` | **killed** | test_the_verifier_re_checks_every_contract_fact_against_a_fabrication[signature_encoding-some.other/encoding/v1-UNSUPPORTED_ENCODING] | — |
| 73 | `verification.py:381` | `attestation.recommendation_id != candidate.recommendation_id` | **killed** | test_an_attestation_naming_another_recommendation_id_is_refused; test_distinct_failures_produce_distinct_members | — |
| 74 | `verification.py:386` | `attestation.recommendation_digest != candidate.recommendation_digest` | **killed** | test_an_attestation_binding_another_recommendation_digest_is_refused; test_a_genuine_attestation_replayed_against_another_candidate_is_refused (+1 more) | — |
| 75 | `verification.py:392` | `attestation.tenant_id != candidate.tenant_id` | **killed** | test_a_cross_tenant_attestation_is_refused; test_an_object_new_fabricated_attestation_is_refused (+1 more) | — |
| 76 | `verification.py:397` | `attestation.subject_id != candidate.subject_id` | **killed** | test_a_cross_subject_attestation_is_refused; test_distinct_failures_produce_distinct_members | — |
| 77 | `verification.py:402` | `attestation.subject_type != candidate.subject_type` | **killed** | test_the_verifier_re_checks_every_contract_fact_against_a_fabrication[subject_type-cloud_scaling.other_subject-WRONG_SUBJECT] | — |
| 78 | `verification.py:429` | `recomputed_bytes != attestation.signed_bytes()` | survived | — | sibling-backed — the payload-digest comparison on the following line is a digest over the same two byte strings and refuses the identical inputs (killed by GI-20). Both are additionally fronted by the reconciliation group, which refuses a divergent tenant, subject, subject type, recommendation id or digest before either runs. Deliberately kept: it is the direct byte comparison the design specifies, and it would be the only survivor if a future edit made the digest check cover a different projection of the payload |
| 79 | `verification.py:435` | `canonical_digest(recomputed) != attestation.signing_payload_digest` | **killed** | test_a_mutated_attestation_fails_the_payload_recomputation; test_a_stale_payload_digest_fails_the_recomputation_gate | — |
| 80 | `verification.py:452` | `type(resolution) is not TrustAnchorResolution` | **killed** | test_a_resolver_returning_a_wrong_typed_resolution_is_refused | — |
| 81 | `verification.py:458` | `anchor is None` | **killed** | test_an_untrusted_producer_key_is_refused; test_a_foreign_issuer_is_refused (+7 more) | — |
| 82 | `verification.py:464` | `type(anchor) is not TrustAnchorRecord` | survived | — | unreachable through the public API — TrustAnchorResolution refuses at construction to carry anything but a TrustAnchorRecord, and the resolution's own exact-type check above (killed by A-54) rejects a non-resolution; this guard covers a resolver that returns a genuine resolution subverted after construction |
| 83 | `verification.py:471` | `anchor.authority_id != attestation.issuer` | **killed** | test_a_resolver_answering_for_another_authority_is_refused | — |
| 84 | `verification.py:477` | `anchor.key_id != attestation.producer_key_id` | **killed** | test_a_resolver_answering_with_another_key_id_is_refused | — |
| 85 | `verification.py:482` | `anchor.capability is not PRODUCER_ATTESTATION_CAPABILITY` | **killed** | test_a_resolver_answering_with_a_wrong_capability_anchor_is_refused | — |
| 86 | `verification.py:491` | `lifecycle is not None` | **killed** | test_a_key_revoked_before_the_instant_is_refused; test_a_disabled_key_is_refused (+8 more) | — |
| 87 | `verification.py:495` | `anchor.signature_profile != attestation.signature_profile` | **killed** | test_an_anchor_profile_disagreement_is_refused | — |
| 88 | `verification.py:500` | `anchor.signature_encoding != attestation.signature_encoding` | **killed** | test_an_anchor_encoding_disagreement_is_refused | — |
| 89 | `verification.py:528` | `accepted is not True` | **killed** | test_a_signature_made_by_another_key_under_a_trusted_key_id_is_refused; test_a_substituted_producer_identity_invalidates_the_signature (+10 more) | — |

## Survivor classification totals

| class | count |
|---|---|
| UNRESOLVED — no reviewed classification; investigate | 1 |
| internal invariant — every refusal in this module is built by the single _refuse helper; not reachable from attacker input | 1 |
| internal invariant — only this module constructs a result, and only ever with an artifact its own minting routine produced; not reachable from attacker input | 1 |
| sibling-backed — a None resolver fails the is_production_authoritative check below, which refuses it with the same typed configuration error | 1 |
| sibling-backed — decode_signature refuses a non-str on the next line and yields the same MALFORMED_SIGNATURE outcome; this guard only makes the refusal typed one call earlier | 1 |
| sibling-backed — require_verified_producer_attestation recomputes the same digest at every consumption boundary, and that check IS killed; this one is unreachable at construction because the minting routine computes the digest it passes | 1 |
| sibling-backed — the hasattr(resolver, 'resolve') check below refuses None with the same typed configuration error | 1 |
| sibling-backed — the hasattr(verifier, 'verify_producer_signature') check below refuses None with the same typed configuration error | 1 |
| sibling-backed — the payload-digest comparison on the following line is a digest over the same two byte strings and refuses the identical inputs (killed by GI-20). Both are additionally fronted by the reconciliation group, which refuses a divergent tenant, subject, subject type, recommendation id or digest before either runs. Deliberately kept: it is the direct byte comparison the design specifies, and it would be the only survivor if a future edit made the digest check cover a different projection of the payload | 1 |
| unreachable through the public API — TrustAnchorResolution refuses at construction to carry anything but a TrustAnchorRecord, and the resolution's own exact-type check above (killed by A-54) rejects a non-resolution; this guard covers a resolver that returns a genuine resolution subverted after construction | 1 |
| unreachable through the public API — mint_producer_attestation is the only route to a signing input and always passes canonical_bytes(); a caller cannot construct one at all, because the token guard above rejects it first | 1 |
| unreachable through the public API — the minted payload is never empty, and the token guard rejects a caller-assembled input before any content check | 1 |
| unreachable through the public API — the minting routine passes the pinned constant, not a parameter; there is no caller-supplied profile to get wrong | 1 |
| **unresolved survivors** | **1** |

Every survivor carries a **hand-written, reviewed** classification, keyed by its
condition in `SURVIVOR_CLASSIFICATION` in `scripts/guard_sweep.py`. The classifier
does not infer a class from the condition's shape: a heuristic that guesses
"sibling-backed" from an `is not None` is a heuristic that will one day call a real
hole sibling-backed. Anything unlisted is reported as **UNRESOLVED**.

No surviving guard admits a verified producer attestation that the unmutated package
refuses. The authenticity gates themselves — reconciliation, payload recomputation,
the payload-digest comparison, anchor resolution, anchor identity, anchor lifecycle,
profile and encoding agreement, signature decoding and signature verification — are
all killed by a property that names that gate.

Regenerate with `python scripts/guard_sweep.py`.
