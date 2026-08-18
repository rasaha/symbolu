"""Verification, issuance and re-verification — the three separated roles.

ADR §8 ("no row may absorb another"), §30 (TEV-2's content), E-11 (the signed
receipt), E-12 / §13.2 (a receipt authorizes nothing), §12 (stages 1-5, never
stage 6), §13.1 (what the receipt must do) and §22.9-§22.10 (no clock).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest
from _authority_builders import (
    VERIFIED_AT,
    VERIFIER_AUTHORITY_ID,
    VERIFIER_KEY_ID,
    attacker_signing_key,
    authority,
    authority_anchor,
    directory,
    envelope,
    determination,
    issuer,
    producer_anchor,
    reverifier,
    signer,
    submission,
)
from _builders import AS_OF, CONTENT_DIGEST, identity, request
from ugence_trusted_evidence_authority.api import (
    RECEIPT_REPORTABLE_TRUST_STAGES,
    SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
    TRUSTED_EVIDENCE_PROTOCOL_V1_ID,
    TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION,
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
    DeclaredVerificationOutcome,
    DenyAllTrustAnchorDirectory,
    EvidenceAdmissionOutcome,
    EvidenceLifecycleState,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
    ProtocolExecutionResult,
    ReceiptIssuer,
    ReceiptVerificationOutcome,
    SignedEvidenceVerificationReceipt,
    TrustedEvidenceContractError,
    TrustedEvidenceRefusalReason,
    derive_receipt_id,
    signed_receipt_input_bytes,
)

R = TrustedEvidenceRefusalReason
UTC = timezone.utc


# --------------------------------------------------------------------------- #
# Role separation (§8)
# --------------------------------------------------------------------------- #

def test_the_verification_authority_holds_no_signing_capability():
    verifier = authority()
    for absent in ("sign", "sign_receipt", "issue", "signing_key", "_signing_key"):
        assert not hasattr(verifier, absent), absent


def test_the_issuer_verifies_nothing_and_resolves_no_trust_anchor():
    receipt_issuer = issuer()
    for absent in ("verify", "resolve", "trust_anchors", "_trust_anchors"):
        assert not hasattr(receipt_issuer, absent), absent


def test_the_independent_reverifier_holds_no_key_and_issues_nothing():
    verifier = reverifier()
    for absent in ("sign", "sign_receipt", "issue", "signing_key", "_signing_key"):
        assert not hasattr(verifier, absent), absent


@pytest.mark.parametrize(
    "build",
    [
        lambda: authority(),
        lambda: issuer(),
        lambda: reverifier(),
        lambda: signer(),
    ],
    ids=["authority", "issuer", "reverifier", "signer"],
)
def test_every_configured_object_is_immutable_after_construction(build):
    """E-5 — re-pointing a configured object would bypass the composition root."""

    obj = build()
    with pytest.raises(AttributeError):
        obj._anything = "x"
    with pytest.raises(AttributeError):
        del obj.__class__


def test_an_unconfigured_verifier_denies_rather_than_skipping_the_check():
    """E-8 — the production default is deny."""

    with pytest.raises(TrustedEvidenceContractError):
        authority(trust_anchors=object())
    with pytest.raises(TrustedEvidenceContractError):
        reverifier(trust_anchors=object())
    result = reverifier(DenyAllTrustAnchorDirectory()).verify(
        envelope(), evaluated_at=AS_OF
    )
    assert result.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED


# --------------------------------------------------------------------------- #
# The happy path, end to end
# --------------------------------------------------------------------------- #

def test_the_happy_path_admits_signs_and_re_verifies():
    result = determination()
    assert result.outcome is EvidenceAdmissionOutcome.ADMITTED
    assert result.admitted is True
    assert result.refusal_reasons == ()
    assert result.receipt_payload is not None

    signed = issuer().issue(result)
    assert signed.envelope_schema == SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1
    assert signed.signed_input_domain == TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN
    assert signed.payload is result.receipt_payload

    verification = reverifier().verify(signed, evaluated_at=AS_OF)
    assert verification.outcome is ReceiptVerificationOutcome.VERIFIED
    assert verification.verified is True
    assert verification.refusal_reason is None
    assert verification.trust_anchor_digest == authority_anchor().canonical_digest()


def test_the_admitted_payload_binds_the_adr_9_coordinates():
    payload = determination().receipt_payload
    evidence = identity()
    assert payload.source_evidence_identity_digest == evidence.canonical_digest()
    assert payload.evidence_content_digest == evidence.content_digest
    assert payload.verification_request_digest == request().canonical_digest()
    assert payload.scope == evidence.scope
    assert payload.verified_at == VERIFIED_AT              # §9 row 6
    assert payload.verifier_authority_id == VERIFIER_AUTHORITY_ID   # §9 row 14
    assert payload.verifier_key_id == VERIFIER_KEY_ID              # §9 row 14
    assert payload.verification_protocol_id == TRUSTED_EVIDENCE_PROTOCOL_V1_ID
    assert payload.verification_protocol_version == (
        TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION
    )                                                              # §9 row 15
    assert payload.declared_outcome is DeclaredVerificationOutcome.DECLARED_ADMITTED
    assert payload.evidence_valid_from == evidence.valid_from      # §9 row 17
    assert payload.evidence_valid_to == evidence.valid_to


def test_stage_six_is_never_established_even_by_a_verified_receipt():
    """§12 — policy sufficiency is requirement-relative and never TAP's."""

    result = determination()
    assert EvidenceTrustStage.POLICY_SUFFICIENT not in result.cleared_stages
    assert EvidenceTrustStage.POLICY_SUFFICIENT in result.unestablished_trust_stages

    signed = issuer().issue(result)
    assert EvidenceTrustStage.POLICY_SUFFICIENT not in (
        signed.payload.declared_cleared_stages
    )
    assert EvidenceTrustStage.POLICY_SUFFICIENT not in (
        signed.payload.declared_unattempted_stages
    )
    verification = reverifier().verify(signed, evaluated_at=AS_OF)
    assert EvidenceTrustStage.POLICY_SUFFICIENT not in (
        verification.established_trust_stages
    )


def test_the_wrapped_payload_is_still_permanently_structurally_unverified():
    """TEV-2 wraps the TEV-1 payload; it does not raise its status."""

    signed = envelope()
    assert signed.payload.structural_status is (
        EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    )
    assert signed.payload.authenticity_verified is False
    assert EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC in (
        signed.payload.unestablished_trust_stages
    )


def test_a_verified_receipt_authorizes_nothing():
    """§13.2, E-12."""

    signed = envelope()
    verification = reverifier().verify(signed, evaluated_at=AS_OF)
    assert verification.verified
    for obj in (signed, verification, signed.payload):
        for forbidden in ("authorize", "allow", "permit", "approve", "grant",
                          "deploy", "execute", "is_authorized",
                          "policy_sufficient", "roi", "value"):
            assert not hasattr(obj, forbidden), (type(obj).__name__, forbidden)


# --------------------------------------------------------------------------- #
# The authority's ordered fail-closed checks
# --------------------------------------------------------------------------- #

def test_a_submission_about_different_evidence_is_refused():
    other = identity(evidence_id="a-different-evidence")
    result = determination(submission_=submission(other))
    assert result.outcome is EvidenceAdmissionOutcome.REFUSED
    assert R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH in result.refusal_reasons
    assert result.receipt_payload is None


@pytest.mark.parametrize(
    "state,expected",
    [
        (EvidenceLifecycleState.REVOKED, R.TRUSTED_EVIDENCE_REVOKED),
        (EvidenceLifecycleState.EXPIRED, R.TRUSTED_EVIDENCE_STALE),
    ],
)
def test_a_revoked_or_expired_artifact_is_refused_before_anything_else(state, expected):
    evidence = identity(lifecycle_state=state)
    result = determination(
        submission_=submission(evidence), request_=request(evidence=evidence)
    )
    assert result.outcome is EvidenceAdmissionOutcome.REFUSED
    assert expected in result.refusal_reasons


@pytest.mark.parametrize(
    "override,expected",
    [
        ({"expected_tenant_id": "other"}, R.TRUSTED_EVIDENCE_TENANT_MISMATCH),
        ({"expected_subject_ref": "other"}, R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH),
        (
            {"expected_assessment_context_ref": "other"},
            R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH,
        ),
        (
            {"expected_assessment_purpose_ref": "other"},
            R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
        ),
        (
            {"expected_usage_scope_ref": "other"},
            R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
        ),
    ],
)
def test_every_scope_axis_is_rechecked_by_the_authority(override, expected):
    """§8.1's closing rule — the authority re-checks, it does not assume."""

    result = determination(request_=request(**override))
    assert result.outcome is EvidenceAdmissionOutcome.REFUSED
    assert expected in result.refusal_reasons


def test_evidence_outside_its_half_open_validity_is_refused():
    early = determination(request_=request(as_of=datetime(2026, 1, 1, tzinfo=UTC)))
    assert R.TRUSTED_EVIDENCE_NOT_YET_VALID in early.refusal_reasons
    late = determination(request_=request(as_of=datetime(2026, 9, 1, tzinfo=UTC)))
    assert R.TRUSTED_EVIDENCE_STALE in late.refusal_reasons


def test_a_forged_producer_signature_is_refused():
    forged = submission(signing_key=attacker_signing_key())
    result = determination(submission_=forged)
    assert result.outcome is EvidenceAdmissionOutcome.REFUSED
    assert R.TRUSTED_EVIDENCE_SIGNATURE_INVALID in result.refusal_reasons


def test_an_unregistered_producer_is_refused():
    result = determination(trust_anchors=directory(authority_anchor()))
    assert R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING in result.refusal_reasons


def test_a_producer_key_outside_its_window_is_refused():
    expired = directory(
        producer_anchor(effective_to=datetime(2026, 2, 1, tzinfo=UTC)),
        authority_anchor(),
    )
    result = determination(trust_anchors=expired)
    assert R.TRUSTED_EVIDENCE_KEY_EXPIRED in result.refusal_reasons


def test_a_revoked_producer_key_is_refused():
    from ugence_trusted_evidence_authority.api import KeyRevocation

    revoked = directory(
        producer_anchor(
            revocation=KeyRevocation(effective_at=datetime(2026, 1, 1, tzinfo=UTC))
        ),
        authority_anchor(),
    )
    result = determination(trust_anchors=revoked)
    assert R.TRUSTED_EVIDENCE_KEY_REVOKED in result.refusal_reasons


def test_a_requested_stage_the_protocol_did_not_clear_is_a_refusal():
    """§12 — stages do not collapse; a partial clear is not a partial admission."""

    class NarrowProtocol:
        protocol_id = TRUSTED_EVIDENCE_PROTOCOL_V1_ID
        protocol_version = TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION

        def run_protocol(self, **kw):
            return ProtocolExecutionResult(
                protocol_id=self.protocol_id,
                protocol_version=self.protocol_version,
                cleared_stages=(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,),
            )

    verifier = authority(protocol=NarrowProtocol())
    result = verifier.verify(
        submission(),
        request(
            requested_trust_stages=(EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,)
        ),
        verified_at=VERIFIED_AT,
        verifier_key_id=VERIFIER_KEY_ID,
    )
    assert result.outcome is EvidenceAdmissionOutcome.REFUSED
    assert R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED in result.refusal_reasons


def test_a_protocol_naming_a_different_id_or_version_is_refused():
    for attribute, expected in (
        ("protocol_id", R.TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED),
        ("protocol_version", R.TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH),
    ):

        class DriftingProtocol:
            protocol_id = TRUSTED_EVIDENCE_PROTOCOL_V1_ID
            protocol_version = TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION

            def run_protocol(self, **kw):
                return ProtocolExecutionResult(
                    **{
                        "protocol_id": self.protocol_id,
                        "protocol_version": self.protocol_version,
                        "cleared_stages": (
                            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
                        ),
                        attribute: "drifted",
                    }
                )

        result = authority(protocol=DriftingProtocol()).verify(
            submission(),
            request(),
            verified_at=VERIFIED_AT,
            verifier_key_id=VERIFIER_KEY_ID,
        )
        assert result.outcome is EvidenceAdmissionOutcome.REFUSED
        assert expected in result.refusal_reasons


def test_a_protocol_returning_a_foreign_object_is_a_refusal_not_a_crash():
    class BrokenProtocol:
        protocol_id = TRUSTED_EVIDENCE_PROTOCOL_V1_ID
        protocol_version = TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION

        def run_protocol(self, **kw):
            return {"cleared_stages": list(RECEIPT_REPORTABLE_TRUST_STAGES)}

    result = authority(protocol=BrokenProtocol()).verify(
        submission(), request(), verified_at=VERIFIED_AT, verifier_key_id=VERIFIER_KEY_ID
    )
    assert result.outcome is EvidenceAdmissionOutcome.REFUSED
    assert R.TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE in result.refusal_reasons


def test_a_protocol_may_not_report_both_cleared_stages_and_refusals():
    with pytest.raises(TrustedEvidenceContractError):
        ProtocolExecutionResult(
            protocol_id="p",
            protocol_version="1",
            cleared_stages=(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,),
            refusal_reasons=(R.TRUSTED_EVIDENCE_INDETERMINATE,),
        )
    with pytest.raises(TrustedEvidenceContractError):
        ProtocolExecutionResult(protocol_id="p", protocol_version="1")


def test_a_protocol_cannot_claim_policy_sufficiency():
    with pytest.raises(TrustedEvidenceContractError):
        ProtocolExecutionResult(
            protocol_id="p",
            protocol_version="1",
            cleared_stages=(EvidenceTrustStage.POLICY_SUFFICIENT,),
        )


def test_an_object_that_is_not_a_protocol_is_refused_at_construction():
    with pytest.raises(TrustedEvidenceContractError):
        authority(protocol=object())


# --------------------------------------------------------------------------- #
# Issuance
# --------------------------------------------------------------------------- #

def test_a_refused_determination_is_never_signed():
    refused = determination(request_=request(expected_tenant_id="other"))
    assert refused.outcome is EvidenceAdmissionOutcome.REFUSED
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        issuer().issue(refused)
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED


def test_a_signer_that_does_not_match_the_payload_coordinates_is_refused():
    result = determination(verifier_key_id="a-different-key")
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        issuer().issue(result)
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_KEY_ID_MISMATCH

    other_authority = authority(authority_id="a-different-authority")
    result = other_authority.verify(
        submission(), request(), verified_at=VERIFIED_AT, verifier_key_id=VERIFIER_KEY_ID
    )
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        issuer().issue(result)
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_AUTHORITY_MISMATCH


def test_a_signer_refuses_a_signing_input_addressed_elsewhere():
    from ugence_trusted_evidence_authority.api import Ed25519ReceiptSigner

    other_signer = Ed25519ReceiptSigner(
        signer_authority_id="a-different-authority",
        signing_key_id=VERIFIER_KEY_ID,
        signing_key=attacker_signing_key(),
    )
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        ReceiptIssuer(signer=other_signer).issue(determination())
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_AUTHORITY_MISMATCH


def test_a_signer_returning_malformed_material_is_refused_at_issuance():
    class BadSigner:
        signer_authority_id = VERIFIER_AUTHORITY_ID
        signing_key_id = VERIFIER_KEY_ID
        signature_profile = signer().signature_profile

        def sign_receipt(self, signing_input):
            return "not a signature"

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        ReceiptIssuer(signer=BadSigner()).issue(determination())
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID


def test_an_object_that_is_not_a_signer_is_refused_at_construction():
    with pytest.raises(TrustedEvidenceContractError):
        ReceiptIssuer(signer=object())


def test_the_signer_publishes_only_a_receipt_issuance_anchor():
    """E-3 — a receipt signer cannot publish itself as an evidence producer."""

    from ugence_trusted_evidence_authority.api import TrustAnchorCapability

    anchor = signer().trust_anchor(
        trust_anchor_set_id="set", trust_anchor_set_version="1"
    )
    assert anchor.capability is TrustAnchorCapability.RECEIPT_ISSUANCE
    assert anchor.authority_id == VERIFIER_AUTHORITY_ID
    assert anchor.key_id == VERIFIER_KEY_ID


# --------------------------------------------------------------------------- #
# Receipt identity and immutability (§13.1.7)
# --------------------------------------------------------------------------- #

def test_receipt_ids_are_deterministic_and_coordinate_sensitive():
    base = dict(
        verification_request_digest=CONTENT_DIGEST,
        verifier_authority_id="authority-1",
        verifier_key_id="key-1",
        verification_protocol_id="protocol-1",
        verification_protocol_version="1",
        verified_at=VERIFIED_AT,
    )
    first = derive_receipt_id(**base)
    assert first == derive_receipt_id(**base)
    assert first.startswith("receipt-")
    assert len(first) == len("receipt-") + 64
    for key, value in (
        ("verifier_authority_id", "authority-2"),
        ("verifier_key_id", "key-2"),
        ("verification_protocol_id", "protocol-2"),
        ("verification_protocol_version", "2"),
        ("verified_at", VERIFIED_AT + timedelta(microseconds=1)),
    ):
        assert derive_receipt_id(**{**base, key: value}) != first


def test_re_verification_mints_a_new_receipt_and_never_mutates_the_earlier_one():
    first = determination()
    later = determination(verified_at=VERIFIED_AT + timedelta(days=1))
    assert later.receipt_payload.receipt_id != first.receipt_payload.receipt_id
    assert first.receipt_payload.verified_at == VERIFIED_AT
    assert first.receipt_payload.canonical_digest() != (
        later.receipt_payload.canonical_digest()
    )
    # Both envelopes verify; neither invalidated the other.
    for signed in (issuer().issue(first), issuer().issue(later)):
        assert reverifier().verify(signed, evaluated_at=AS_OF).verified


def test_the_envelope_and_its_payload_are_frozen():
    signed = envelope()
    with pytest.raises(dataclasses.FrozenInstanceError):
        signed.signature = "x" * 128
    with pytest.raises(dataclasses.FrozenInstanceError):
        signed.payload.receipt_id = "other"


# --------------------------------------------------------------------------- #
# The signed input and the envelope contract
# --------------------------------------------------------------------------- #

def test_the_envelope_reconstructs_its_own_signed_input():
    signed = envelope()
    assert signed.signed_input_bytes() == signed_receipt_input_bytes(
        payload=signed.payload,
        signer_authority_id=signed.signer_authority_id,
        signing_key_id=signed.signing_key_id,
        signature_profile=signed.signature_profile,
    )


def test_the_envelope_recomputes_its_payload_digest_rather_than_believing_it():
    signed = envelope()
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        dataclasses.replace(signed, payload_canonical_digest="0" * 64)
    assert excinfo.value.reason is R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH


def test_the_envelope_refuses_a_foreign_schema_or_domain():
    signed = envelope()
    for field in ("envelope_schema", "signed_input_domain"):
        with pytest.raises(TrustedEvidenceContractError) as excinfo:
            dataclasses.replace(signed, **{field: "something-else"})
        assert excinfo.value.reason is R.TRUSTED_EVIDENCE_ENVELOPE_MALFORMED


def test_the_envelope_has_no_issuance_time_field():
    """§13.1.5 — ``verified_at`` on the payload is the ratified instant."""

    fields = {f.name for f in dataclasses.fields(SignedEvidenceVerificationReceipt)}
    for banned in ("issued_at", "issuance_time", "created_at", "timestamp",
                   "signed_at", "now"):
        assert banned not in fields, banned
    assert envelope().payload.verified_at == VERIFIED_AT


def test_the_envelope_carries_no_mutable_map_or_free_form_metadata():
    signed = envelope()
    for field in dataclasses.fields(SignedEvidenceVerificationReceipt):
        value = getattr(signed, field.name)
        assert not isinstance(value, (dict, list, set)), field.name
    for banned in ("metadata", "extra", "attributes", "annotations", "extensions"):
        assert not hasattr(signed, banned), banned


def test_the_envelope_digest_is_not_the_content_digest_and_is_not_signed():
    """§13.3, §22.5-§22.6 — no fixed-point digest, no self-reference."""

    import json

    from ugence_trusted_evidence_authority.api import canonical_bytes

    signed = envelope()
    assert signed.envelope_digest() != signed.payload_canonical_digest
    body = json.loads(canonical_bytes(signed))["body"]
    # The envelope digest is not a field of the envelope.
    assert "envelope_digest" not in body
    # And the payload's own canonical bytes contain no signature.
    payload_body = json.loads(canonical_bytes(signed.payload))["body"]
    assert not any("sign" in key.lower() for key in payload_body)


# --------------------------------------------------------------------------- #
# No clock (§22.9, §22.10)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "call",
    [
        lambda: authority().verify(submission(), request(), verifier_key_id="k"),
        lambda: reverifier().verify(envelope()),
    ],
    ids=["verify", "reverify"],
)
def test_no_entry_point_defaults_its_instant(call):
    with pytest.raises(TypeError):
        call()


def test_a_naive_instant_is_refused_everywhere():
    naive = datetime(2026, 6, 1, 12, 0, 0)
    with pytest.raises(TrustedEvidenceContractError):
        authority().verify(
            submission(), request(), verified_at=naive, verifier_key_id=VERIFIER_KEY_ID
        )
    with pytest.raises(TrustedEvidenceContractError):
        reverifier().verify(envelope(), evaluated_at=naive)


def test_the_same_inputs_produce_byte_identical_outputs():
    a, b = determination(), determination()
    assert a.receipt_payload.canonical_digest() == (
        b.receipt_payload.canonical_digest()
    )
    assert issuer().issue(a).envelope_digest() == issuer().issue(b).envelope_digest()


def test_the_token_guarded_findings_are_not_canonicalizable_at_all():
    """They carry a private token, and §22.2 admits no conditional omission."""

    from ugence_trusted_evidence_authority.api import (
        TrustedEvidenceCanonicalizationError,
        canonical_bytes,
    )

    result = determination()
    verification = reverifier().verify(envelope(), evaluated_at=AS_OF)
    for finding in (result, verification):
        assert not hasattr(finding, "canonical_bytes")
        assert not hasattr(finding, "canonical_digest")
        with pytest.raises(TrustedEvidenceCanonicalizationError):
            canonical_bytes(finding)
