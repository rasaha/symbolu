"""Unicode NFC is enforced at **construction**, not only at canonicalization.

Audit finding A-03. Before the correction, a non-NFC identifier constructed
successfully — every structural invariant appeared to hold — and the object only
failed much later, when something asked for its canonical bytes. An object that
cannot be canonicalized is not structurally valid, so it must not exist.

ADR §22.4 fixes the pattern for the analogous coordinate: a naive datetime is
rejected "at the boundary **and again** at canonicalization". These tests assert
the same two-boundary discipline for canonical strings, and that the encoder
retains its own check as defense in depth.

Every fixture is built from explicit codepoints and **asserted to be genuinely
non-NFC before it is used**, so a test cannot silently pass against a string that
was already canonical.
"""

from __future__ import annotations

import dataclasses
import unicodedata

import pytest
from _authority_builders import envelope, submission
from _builders import (
    RECEIPT_VALID_FROM,
    claim,
    identity,
    observation,
    provenance,
    receipt,
    request,
    schema,
    scope,
)
from _authority_builders import (
    PRODUCER_AUTHORITY_ID,
    PRODUCER_KEY_ID,
    TRUST_ANCHOR_SET_ID,
    TRUST_ANCHOR_SET_VERSION,
    VERIFIER_KEY_ID,
    authority_anchor,
    producer_anchor,
)
from ugence_trusted_evidence_authority.api import (
    ApplicabilityCoordinate,
    EvidenceProvenanceChain,
    EvidenceSchemaRef,
    EvidenceTrustStage,
    EvidenceVerificationAuditRecord,
    KeyRevocation,
    ProtocolExecutionResult,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustedEvidenceCanonicalizationError,
    TrustedEvidenceContractError,
    canonical_bytes,
)

# --------------------------------------------------------------------------- #
# Fixtures, proved non-NFC before use
# --------------------------------------------------------------------------- #

#: LATIN SMALL LETTER E (U+0065) + COMBINING ACUTE ACCENT (U+0301).
NFD_E_ACUTE = "café-id"
#: The NFC spelling of the same text: LATIN SMALL LETTER E WITH ACUTE (U+00E9).
NFC_E_ACUTE = "café-id"

#: LATIN SMALL LETTER A (U+0061) + COMBINING RING ABOVE (U+030A).
NFD_A_RING = "ångstrom-ref"
NFC_A_RING = "ångstrom-ref"

#: LATIN SMALL LETTER O (U+006F) + COMBINING DIAERESIS (U+0308).
NFD_O_UMLAUT = "ö-unit"
NFC_O_UMLAUT = "ö-unit"

NON_NFC_FIXTURES = [NFD_E_ACUTE, NFD_A_RING, NFD_O_UMLAUT]
NFC_EQUIVALENTS = [NFC_E_ACUTE, NFC_A_RING, NFC_O_UMLAUT]


@pytest.mark.parametrize(
    "nfd,nfc", list(zip(NON_NFC_FIXTURES, NFC_EQUIVALENTS))
)
def test_the_attack_fixtures_are_genuinely_non_nfc(nfd, nfc):
    """Guard the guard: a fixture that were already NFC would prove nothing."""

    assert unicodedata.normalize("NFC", nfd) != nfd
    assert unicodedata.normalize("NFC", nfd) == nfc
    assert unicodedata.normalize("NFC", nfc) == nfc
    assert nfd != nfc
    # They are genuinely different byte sequences, not one string spelled twice.
    assert nfd.encode("utf-8") != nfc.encode("utf-8")
    assert len(nfd) > len(nfc)


# --------------------------------------------------------------------------- #
# The regression the audit found: construction must refuse
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("nfd", NON_NFC_FIXTURES)
def test_a_non_nfc_identifier_is_refused_at_construction(nfd):
    """The A-03 probe: this previously constructed successfully."""

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        EvidenceSchemaRef(schema_id=nfd, schema_version="1")
    assert "NFC" in str(excinfo.value)


@pytest.mark.parametrize("nfc", NFC_EQUIVALENTS)
def test_the_nfc_spelling_is_still_accepted(nfc):
    """The correction rejects non-canonical input, it does not reject Unicode."""

    built = EvidenceSchemaRef(schema_id=nfc, schema_version="1")
    assert built.schema_id == nfc
    assert canonical_bytes(built)


def test_rejection_is_never_silent_normalization():
    """No accepted object ever holds the folded form of a refused input."""

    with pytest.raises(TrustedEvidenceContractError):
        EvidenceSchemaRef(schema_id=NFD_E_ACUTE, schema_version="1")
    # The NFC value is a *different* value the caller must supply themselves.
    folded = EvidenceSchemaRef(schema_id=NFC_E_ACUTE, schema_version="1")
    assert folded.schema_id == NFC_E_ACUTE
    assert folded.schema_id != NFD_E_ACUTE


# --------------------------------------------------------------------------- #
# The boundary is uniform — every string coordinate, nested contracts included
# --------------------------------------------------------------------------- #

def audit(**kw):
    """A minimal audit record with one overridable string coordinate."""

    from _builders import CONTENT_DIGEST, VERIFIED_AT

    return EvidenceVerificationAuditRecord(
        **{
            "act": "EVIDENCE_VERIFICATION",
            "outcome": "ADMITTED",
            "evaluated_at": VERIFIED_AT,
            "tenant_id": "tenant-1",
            "authority_id": "authority-1",
            "key_id": "key-1",
            "verification_protocol_id": "protocol-1",
            "verification_protocol_version": "1",
            "verification_request_digest": CONTENT_DIGEST,
            **kw,
        }
    )


STRING_COORDINATES = [
    ("EvidenceSchemaRef.schema_id", lambda v: schema(schema_id=v)),
    ("EvidenceSchemaRef.schema_version", lambda v: schema(schema_version=v)),
    ("EvidenceObservation.producer_id", lambda v: observation(producer_id=v)),
    ("EvidenceObservation.issuer_id", lambda v: observation(issuer_id=v)),
    ("EvidenceScopeBinding.tenant_id", lambda v: scope(tenant_id=v)),
    ("EvidenceScopeBinding.assessment_context_ref", lambda v: scope(assessment_context_ref=v)),
    ("EvidenceScopeBinding.subject_ref", lambda v: scope(subject_ref=v)),
    ("EvidenceScopeBinding.assessment_purpose_ref", lambda v: scope(assessment_purpose_ref=v)),
    ("EvidenceScopeBinding.usage_scope_ref", lambda v: scope(usage_scope_ref=v)),
    ("EvidenceScopeBinding.assessed_system_binding_ref", lambda v: scope(assessed_system_binding_ref=v)),
    ("EvidenceClaimBinding.claim_ref", lambda v: claim(claim_ref=v)),
    ("EvidenceClaimBinding.metric_ref", lambda v: claim(metric_ref=v)),
    ("EvidenceClaimBinding.unit", lambda v: claim(unit=v)),
    ("EvidenceClaimBinding.measurement_semantics_ref", lambda v: claim(measurement_semantics_ref=v)),
    ("EvidenceProvenanceChain.chain_ref", lambda v: provenance(chain_ref=v)),
    ("CanonicalEvidenceIdentity.evidence_id", lambda v: identity(evidence_id=v)),
    ("CanonicalEvidenceIdentity.evidence_type", lambda v: identity(evidence_type=v)),
    ("ApplicabilityCoordinate.value", lambda v: ApplicabilityCoordinate.applicable(v)),
    ("EvidenceVerificationRequest.expected_tenant_id", lambda v: request(expected_tenant_id=v)),
    ("EvidenceVerificationRequest.expected_subject_ref", lambda v: request(expected_subject_ref=v)),
    ("EvidenceVerificationRequest.expected_assessment_context_ref", lambda v: request(expected_assessment_context_ref=v)),
    ("EvidenceVerificationRequest.expected_assessment_purpose_ref", lambda v: request(expected_assessment_purpose_ref=v)),
    ("EvidenceVerificationRequest.expected_usage_scope_ref", lambda v: request(expected_usage_scope_ref=v)),
    ("EvidenceVerificationRequest.expected_assessed_system_binding_ref", lambda v: request(expected_assessed_system_binding_ref=v)),
    ("EvidenceVerificationReceiptPayload.receipt_id", lambda v: receipt(receipt_id=v)),
    ("EvidenceVerificationReceiptPayload.verifier_authority_id", lambda v: receipt(verifier_authority_id=v)),
    ("EvidenceVerificationReceiptPayload.verifier_key_id", lambda v: receipt(verifier_key_id=v)),
    ("EvidenceVerificationReceiptPayload.verification_protocol_id", lambda v: receipt(verification_protocol_id=v)),
    ("EvidenceVerificationReceiptPayload.verification_protocol_version", lambda v: receipt(verification_protocol_version=v)),
    # -- TEV-2 --------------------------------------------------------------
    ("TrustAnchorCoordinate.authority_id", lambda v: TrustAnchorCoordinate(
        authority_id=v, key_id=VERIFIER_KEY_ID,
        capability=TrustAnchorCapability.RECEIPT_ISSUANCE)),
    ("TrustAnchorCoordinate.key_id", lambda v: TrustAnchorCoordinate(
        authority_id=PRODUCER_AUTHORITY_ID, key_id=v,
        capability=TrustAnchorCapability.RECEIPT_ISSUANCE)),
    ("KeyRevocation.reason_ref", lambda v: KeyRevocation(
        effective_at=RECEIPT_VALID_FROM, reason_ref=v)),
    ("TrustAnchorRecord.authority_id", lambda v: producer_anchor(authority_id=v)),
    ("TrustAnchorRecord.key_id", lambda v: producer_anchor(key_id=v)),
    ("TrustAnchorRecord.trust_anchor_set_id", lambda v: producer_anchor(trust_anchor_set_id=v)),
    ("TrustAnchorRecord.trust_anchor_set_version", lambda v: producer_anchor(trust_anchor_set_version=v)),
    ("SignedEvidenceSubmission.producer_authority_id", lambda v: submission(producer_authority_id=v)),
    ("SignedEvidenceSubmission.producer_key_id", lambda v: submission(producer_key_id=v)),
    ("SignedEvidenceVerificationReceipt.signer_authority_id",
     lambda v: dataclasses.replace(envelope(), signer_authority_id=v)),
    ("SignedEvidenceVerificationReceipt.signing_key_id",
     lambda v: dataclasses.replace(envelope(), signing_key_id=v)),
    ("ProtocolExecutionResult.protocol_id", lambda v: ProtocolExecutionResult(
        protocol_id=v, protocol_version="1",
        cleared_stages=(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,))),
    ("ProtocolExecutionResult.protocol_version", lambda v: ProtocolExecutionResult(
        protocol_id="p", protocol_version=v,
        cleared_stages=(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,))),
    ("EvidenceVerificationAuditRecord.act", lambda v: audit(act=v)),
    ("EvidenceVerificationAuditRecord.outcome", lambda v: audit(outcome=v)),
    ("EvidenceVerificationAuditRecord.tenant_id", lambda v: audit(tenant_id=v)),
    ("EvidenceVerificationAuditRecord.authority_id", lambda v: audit(authority_id=v)),
    ("EvidenceVerificationAuditRecord.key_id", lambda v: audit(key_id=v)),
    ("EvidenceVerificationAuditRecord.verification_protocol_id",
     lambda v: audit(verification_protocol_id=v)),
    ("EvidenceVerificationAuditRecord.verification_protocol_version",
     lambda v: audit(verification_protocol_version=v)),
    # Hex-encoded material still runs through the same canonical-string gate
    # before its stricter base16 rule, so it is covered here rather than exempt.
    ("SignedEvidenceVerificationReceipt.signature",
     lambda v: dataclasses.replace(envelope(), signature=v)),
    ("SignedEvidenceSubmission.signature", lambda v: submission(signature=v)),
    ("TrustAnchorRecord.public_key", lambda v: producer_anchor(public_key=v)),
]


@pytest.mark.parametrize("coordinate,build", STRING_COORDINATES, ids=[c for c, _ in STRING_COORDINATES])
def test_every_string_coordinate_refuses_non_nfc_at_construction(coordinate, build):
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        build(NFD_E_ACUTE)
    assert "NFC" in str(excinfo.value), coordinate


def test_custody_reference_elements_are_checked_too():
    """Nested sequence elements are string coordinates like any other."""

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        EvidenceProvenanceChain(chain_ref="chain-1", custody_refs=("ok", NFD_A_RING))
    assert "NFC" in str(excinfo.value)


def test_the_string_coordinate_matrix_covers_every_declared_string_field():
    """Structural coverage: no ``str``-typed field escapes the matrix.

    A string coordinate added later without an entry here fails, rather than
    shipping outside the construction-time NFC boundary.
    """

    from ugence_trusted_evidence_authority import api

    from ugence_trusted_evidence_authority.api import (
        EvidenceVerificationDetermination,
        ReceiptSigningInput,
    )

    # Token-guarded types are exempt **by identity**, never by a name pattern —
    # a second unreachable type could not slip in behind these two. Neither is
    # caller-constructible at all: their ``__post_init__`` demands a private
    # token the curated API does not export, so no caller can supply *any*
    # string to them, NFC or otherwise. The two tests immediately below prove
    # that, so the exemption rests on a demonstrated property rather than on
    # this comment. Every string that does reach them is produced inside the
    # package from coordinates already covered by the matrix above.
    token_guarded = {EvidenceVerificationDetermination, ReceiptSigningInput}

    covered = {name for name, _ in STRING_COORDINATES}
    uncovered = set()
    for symbol in api.__all__:
        obj = getattr(api, symbol)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        if obj in token_guarded:
            continue
        for field in dataclasses.fields(obj):
            if field.type not in ("str", str):
                continue
            qualified = f"{obj.__name__}.{field.name}"
            if qualified not in covered:
                uncovered.add(qualified)

    # Digest-typed strings are validated by the stricter hex rule, which rejects
    # every non-ASCII value including any non-NFC one, so they are exempt.
    digest_fields = {n for n in uncovered if "digest" in n.rsplit(".", 1)[-1]}

    # TEV-2 adds one more exempt class, *stricter* than the NFC rule rather
    # than weaker: **pinned-constant fields**. ``envelope_schema``,
    # ``signature_profile``, ``signature_encoding`` and ``signed_input_domain``
    # are compared for equality against a single ratified constant, so every
    # value but that one is refused, non-NFC spellings included.
    #
    # Hex-encoded material is **not** exempt: ``signature`` and ``public_key``
    # run through the same canonical-string gate before their stricter base16
    # rule, so they are covered by the matrix directly.
    pinned_fields = {
        n
        for n in uncovered
        if n.rsplit(".", 1)[-1]
        in (
            "envelope_schema",
            "signature_profile",
            "signature_encoding",
            "signed_input_domain",
        )
    }
    remaining = uncovered - digest_fields - pinned_fields
    assert remaining == set(), sorted(remaining)


def test_the_token_guarded_types_admit_no_caller_supplied_string_at_all():
    """The exemption above, proved: neither type is caller-constructible.

    A caller cannot reach these constructors with a non-NFC string because a
    caller cannot reach these constructors, full stop. Attempted directly, with
    every field otherwise valid, construction is refused.
    """

    from ugence_trusted_evidence_authority.api import (
        TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
        EvidenceAdmissionOutcome,
        EvidenceVerificationDetermination,
        ReceiptSigningInput,
    )
    from _builders import CONTENT_DIGEST, VERIFIED_AT

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        EvidenceVerificationDetermination(
            outcome=EvidenceAdmissionOutcome.REFUSED,
            verification_request_digest=CONTENT_DIGEST,
            verifier_authority_id="authority-1",
            verifier_key_id="key-1",
            verification_protocol_id="protocol-1",
            verification_protocol_version="1",
            verified_at=VERIFIED_AT,
            evaluated_at=VERIFIED_AT,
            refusal_reasons=(),
        )
    assert "cannot be constructed directly" in str(excinfo.value)

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        ReceiptSigningInput(
            signed_input=b"anything at all",
            signer_authority_id="authority-1",
            signing_key_id="key-1",
            signature_profile=TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
        )
    assert "cannot be constructed directly" in str(excinfo.value)


@pytest.mark.parametrize(
    "build",
    [
        lambda v: dataclasses.replace(envelope(), signature=v),
        lambda v: producer_anchor(public_key=v),
    ],
    ids=["SignedEvidenceVerificationReceipt.signature", "TrustAnchorRecord.public_key"],
)
def test_hex_material_also_refuses_an_nfc_string_that_is_not_base16(build):
    """NFC is necessary but not sufficient for encoded material."""

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        build("Z" * 128)
    assert "base16" in str(excinfo.value) or "characters" in str(excinfo.value)


@pytest.mark.parametrize(
    "build",
    [
        lambda v: dataclasses.replace(envelope(), envelope_schema=v),
        lambda v: dataclasses.replace(envelope(), signature_profile=v),
        lambda v: dataclasses.replace(envelope(), signed_input_domain=v),
        lambda v: producer_anchor(signature_profile=v),
        lambda v: producer_anchor(signature_encoding=v),
    ],
    ids=[
        "envelope_schema",
        "envelope.signature_profile",
        "signed_input_domain",
        "anchor.signature_profile",
        "anchor.signature_encoding",
    ],
)
def test_pinned_constant_fields_refuse_every_value_but_the_ratified_one(build):
    """The second exemption, proved: a non-NFC spelling is simply not the constant."""

    with pytest.raises(TrustedEvidenceContractError):
        build(NFD_E_ACUTE)


@pytest.mark.parametrize(
    "name",
    [
        "content_digest",
        "assessment_context_digest",
        "assessed_system_binding_digest",
        "source_evidence_identity_digest",
    ],
)
def test_digest_coordinates_reject_non_nfc_via_the_stricter_hex_rule(name):
    builders = {
        "content_digest": lambda v: identity(content_digest=v),
        "assessment_context_digest": lambda v: scope(assessment_context_digest=v),
        "assessed_system_binding_digest": lambda v: scope(assessed_system_binding_digest=v),
        "source_evidence_identity_digest": lambda v: receipt(source_evidence_identity_digest=v),
    }
    with pytest.raises(TrustedEvidenceContractError):
        builders[name](NFD_E_ACUTE)


# --------------------------------------------------------------------------- #
# Defense in depth: the encoder keeps its own check
# --------------------------------------------------------------------------- #

def test_the_encoder_still_refuses_non_nfc_reached_by_another_route():
    """A value bypassing the constructor still fails closed at canonicalization."""

    @dataclasses.dataclass(frozen=True)
    class Holder:
        payload: object

    with pytest.raises(TrustedEvidenceCanonicalizationError) as excinfo:
        canonical_bytes(Holder(payload=NFD_E_ACUTE))
    assert "NFC" in str(excinfo.value)


def test_a_frozen_bypass_via_object_setattr_is_still_caught_by_the_encoder():
    """``object.__setattr__`` skips ``__post_init__``; the encoder does not."""

    built = schema()
    object.__setattr__(built, "schema_id", NFD_E_ACUTE)
    assert built.schema_id == NFD_E_ACUTE  # the bypass worked on the attribute...
    with pytest.raises(TrustedEvidenceCanonicalizationError):
        canonical_bytes(built)  # ... and the second boundary still refuses it


# --------------------------------------------------------------------------- #
# str subclasses stay refused (the pre-existing closed-contract rule)
# --------------------------------------------------------------------------- #

def test_a_str_subclass_is_still_refused():
    class SneakyStr(str):
        def strip(self, *args):  # would defeat the padding check
            return self

    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        schema(schema_id=SneakyStr("  padded  "))
    assert "subclasses are refused" in str(excinfo.value)


def test_padded_string_rejection_is_preserved_alongside_the_nfc_rule():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        schema(schema_id=" padded")
    assert "whitespace" in str(excinfo.value)


def test_a_value_that_is_both_padded_and_non_nfc_is_refused():
    with pytest.raises(TrustedEvidenceContractError):
        schema(schema_id=" " + NFD_E_ACUTE)


def test_the_nfc_rule_does_not_disturb_valid_ascii_coordinates():
    """The correction is a rejection rule, not a change to accepted values."""

    assert identity().canonical_digest()
    assert receipt().canonical_digest()
    assert claim().claim_ref == "claim-1"
