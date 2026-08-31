"""The structural receipt payload (ADR §13, §30, §32) — audit finding A-01.

ADR §30 assigns "receipt shape (§13)" to TEV-1 and the §32 ledger states
"shape = TEV-1, service = TEV-2". These tests establish that the shape is
complete, deterministic, digest-bound — and that no caller can turn it into
proof of anything.

The central assertion, repeated in several forms: a payload declaring every
reportable stage cleared, under an authoritative-sounding verifier, with matching
digests, is **still** ``STRUCTURAL_UNVERIFIED`` with
``CRYPTOGRAPHICALLY_AUTHENTIC`` unestablished.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
import json
import pickle
from datetime import datetime, timedelta, timezone

import pytest
from _builders import (
    CONTENT_DIGEST,
    RECEIPT_VALID_FROM,
    RECEIPT_VALID_TO,
    VALID_FROM,
    VALID_TO,
    VERIFIED_AT,
    identity,
    receipt,
    refused_receipt,
    scope,
)
from ugence_trusted_evidence_authority.api import (
    EVIDENCE_TRUST_STAGE_ORDER,
    RECEIPT_REPORTABLE_TRUST_STAGES,
    DeclaredVerificationOutcome,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
    EvidenceVerificationReceiptPayload,
    TrustedEvidenceContractError,
    TrustedEvidenceRefusalReason,
    canonical_bytes,
    canonical_digest,
)

R = TrustedEvidenceRefusalReason
S = EvidenceTrustStage
UTC = timezone.utc
TICK = timedelta(microseconds=1)


# --------------------------------------------------------------------------- #
# Shape and ADR coordinate coverage
# --------------------------------------------------------------------------- #

def test_declared_field_order_is_pinned():
    assert [f.name for f in dataclasses.fields(EvidenceVerificationReceiptPayload)] == [
        "receipt_id",
        "schema",
        "source_evidence_identity_digest",
        "evidence_content_digest",
        "verification_request_digest",
        "scope",
        "verified_at",
        "verifier_authority_id",
        "verifier_key_id",
        "verification_protocol_id",
        "verification_protocol_version",
        "declared_outcome",
        "declared_cleared_stages",
        "declared_unattempted_stages",
        "declared_refusal_reasons",
        "evidence_valid_from",
        "evidence_valid_to",
        "receipt_valid_from",
        "receipt_valid_to",
    ]


def test_adr_rows_6_and_14_to_16_are_present_here():
    """The coordinates omitted from the evidence identity live on the payload."""

    names = {f.name for f in dataclasses.fields(EvidenceVerificationReceiptPayload)}
    assert "verified_at" in names                        # §9 row 6
    assert {"verifier_authority_id", "verifier_key_id"} <= names   # row 14
    assert {"verification_protocol_id", "verification_protocol_version"} <= names  # row 15
    assert {"declared_outcome", "declared_refusal_reasons"} <= names  # row 16


def test_it_binds_the_source_evidence_and_the_request():
    payload = receipt()
    assert payload.source_evidence_identity_digest == identity().canonical_digest()
    assert payload.evidence_content_digest == CONTENT_DIGEST
    assert len(payload.verification_request_digest) == 64


def test_it_binds_the_scope_coordinates_by_value():
    """§13.1.3 — tenant/context/subject/system/purpose/scope, digests not payloads."""

    assert receipt().scope == scope()
    body = json.loads(canonical_bytes(receipt()))["body"]
    assert body["scope"]["tenant_id"] == "tenant-1"
    # §27.5 — the payload binds the evidence *digest*, never a copy of it.
    assert "observation" not in body
    assert "provenance" not in body


def test_the_payload_is_frozen_and_immutable():
    payload = receipt()
    before = payload.canonical_digest()
    with pytest.raises(dataclasses.FrozenInstanceError):
        payload.receipt_id = "receipt-2"
    assert payload.canonical_digest() == before


def test_the_payload_is_deterministic():
    assert receipt() == receipt()
    assert receipt().canonical_bytes() == receipt().canonical_bytes()
    assert len({receipt().canonical_digest() for _ in range(20)}) == 1


# --------------------------------------------------------------------------- #
# No signature field — §13.3
# --------------------------------------------------------------------------- #

def test_the_payload_carries_no_signature_field_not_even_optional():
    names = {f.name for f in dataclasses.fields(EvidenceVerificationReceiptPayload)}
    for forbidden in ("signature", "signature_bytes", "signed", "signer",
                      "signing_key", "envelope", "trust_anchor", "public_key",
                      "algorithm", "alg", "key_material", "certificate"):
        assert forbidden not in names, forbidden


def test_no_signature_can_be_passed_to_the_constructor():
    for forbidden in ("signature", "signed", "signer", "trust_anchor"):
        with pytest.raises(TypeError):
            receipt(**{forbidden: b"x"})


def test_the_canonical_body_contains_no_signature_key():
    body = json.loads(canonical_bytes(receipt()))["body"]
    for key in body:
        assert "signature" not in key.lower()
        assert "signed" not in key.lower()


def test_the_verifier_key_id_is_an_opaque_string_not_key_material():
    payload = receipt(verifier_key_id="any-opaque-token")
    assert payload.verifier_key_id == "any-opaque-token"
    assert isinstance(payload.verifier_key_id, str)
    # No algorithm, curve or encoding is implied or validated.
    assert receipt(verifier_key_id="not-a-real-key-at-all").verifier_key_id


# --------------------------------------------------------------------------- #
# Declared vs established — the whole point
# --------------------------------------------------------------------------- #

def test_a_fully_admitted_payload_is_still_structurally_unverified():
    payload = receipt()
    assert payload.declared_outcome is DeclaredVerificationOutcome.DECLARED_ADMITTED
    assert set(payload.declared_cleared_stages) == set(RECEIPT_REPORTABLE_TRUST_STAGES)
    # ... and none of that establishes anything:
    assert payload.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    assert payload.authenticity_verified is False
    assert payload.established_trust_stages == (S.STRUCTURALLY_CONSTRUCTIBLE,)


def test_cryptographic_authenticity_stays_unestablished_whatever_is_declared():
    """Task-critical: a declared cleared stage is not an established stage."""

    payload = receipt()
    assert S.CRYPTOGRAPHICALLY_AUTHENTIC in payload.declared_cleared_stages
    assert S.CRYPTOGRAPHICALLY_AUTHENTIC in payload.unestablished_trust_stages
    assert payload.unestablished_trust_stages == tuple(
        s for s in EVIDENCE_TRUST_STAGE_ORDER if s is not S.STRUCTURALLY_CONSTRUCTIBLE
    )


def test_policy_sufficiency_remains_requirement_relative():
    assert S.POLICY_SUFFICIENT in receipt().unestablished_trust_stages
    assert S.POLICY_SUFFICIENT not in RECEIPT_REPORTABLE_TRUST_STAGES


def test_every_declared_outcome_member_carries_the_declared_prefix():
    for member in DeclaredVerificationOutcome:
        assert member.value.startswith("DECLARED_"), member
    assert {m.value for m in DeclaredVerificationOutcome} == {
        "DECLARED_ADMITTED",
        "DECLARED_REFUSED",
        "DECLARED_INDETERMINATE",
    }


def test_there_is_no_outcome_member_meaning_authority_verified():
    for member in DeclaredVerificationOutcome:
        for banned in ("AUTHORITY", "VERIFIED", "AUTHENTIC", "TRUSTED", "SIGNED"):
            assert banned not in member.value, member


def test_declares_admission_is_named_and_documented_as_a_claim():
    assert receipt().declares_admission is True
    assert refused_receipt().declares_admission is False
    doc = " ".join(
        (EvidenceVerificationReceiptPayload.declares_admission.__doc__ or "").split()
    )
    assert "what the payload **says**" in doc or "what the payload says" in doc
    assert "never be used as an admission decision" in doc


def test_the_envelope_verification_reason_is_always_not_performed():
    for payload in (receipt(), refused_receipt()):
        assert (
            payload.envelope_verification_reason
            is R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
        )


def test_declared_unestablished_stages_is_derived_from_the_declaration():
    payload = refused_receipt()
    assert payload.declared_cleared_stages == (S.STRUCTURALLY_CONSTRUCTIBLE,)
    assert payload.declared_unestablished_stages == tuple(
        s for s in RECEIPT_REPORTABLE_TRUST_STAGES if s is not S.STRUCTURALLY_CONSTRUCTIBLE
    )


# --------------------------------------------------------------------------- #
# Stage-list invariants
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("field", ["declared_cleared_stages", "declared_unattempted_stages"])
def test_stage_six_may_not_appear_in_either_list(field):
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        receipt(**{field: (S.POLICY_SUFFICIENT,)},
                declared_outcome=DeclaredVerificationOutcome.DECLARED_ADMITTED,
                declared_refusal_reasons=())
    assert "stages 1-5" in str(excinfo.value)


def test_a_stage_cannot_be_both_cleared_and_unattempted():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        receipt(
            declared_cleared_stages=(S.STRUCTURALLY_CONSTRUCTIBLE, S.CURRENTLY_VALID),
            declared_unattempted_stages=(S.CURRENTLY_VALID,),
        )
    assert "both cleared and not attempted" in str(excinfo.value)


def test_stage_list_order_on_input_is_semantically_irrelevant():
    forward = receipt(
        declared_cleared_stages=(S.STRUCTURALLY_CONSTRUCTIBLE, S.CURRENTLY_VALID)
    )
    backward = receipt(
        declared_cleared_stages=(S.CURRENTLY_VALID, S.STRUCTURALLY_CONSTRUCTIBLE)
    )
    assert forward == backward
    assert forward.canonical_bytes() == backward.canonical_bytes()
    assert forward.canonical_digest() == backward.canonical_digest()


def test_stage_lists_are_normalized_into_ratified_order_and_deduplicated():
    payload = receipt(
        declared_cleared_stages=[
            S.CURRENTLY_VALID,
            S.STRUCTURALLY_CONSTRUCTIBLE,
            S.CURRENTLY_VALID,
        ]
    )
    assert payload.declared_cleared_stages == (
        S.STRUCTURALLY_CONSTRUCTIBLE,
        S.CURRENTLY_VALID,
    )
    assert isinstance(payload.declared_cleared_stages, tuple)


def test_refusal_reason_order_on_input_is_semantically_irrelevant():
    a = refused_receipt(
        declared_refusal_reasons=(R.TRUSTED_EVIDENCE_TENANT_MISMATCH,
                                  R.TRUSTED_EVIDENCE_STALE)
    )
    b = refused_receipt(
        declared_refusal_reasons=(R.TRUSTED_EVIDENCE_STALE,
                                  R.TRUSTED_EVIDENCE_TENANT_MISMATCH)
    )
    assert a.canonical_digest() == b.canonical_digest()
    order = list(R)
    assert list(a.declared_refusal_reasons) == sorted(
        a.declared_refusal_reasons, key=order.index
    )


@pytest.mark.parametrize("bad", ["CURRENTLY_VALID", 1, None, True])
def test_a_stage_lookalike_is_refused(bad):
    with pytest.raises(TrustedEvidenceContractError):
        receipt(declared_cleared_stages=(bad,))


@pytest.mark.parametrize("bad", ["TRUSTED_EVIDENCE_STALE", 1, None])
def test_a_reason_lookalike_is_refused(bad):
    with pytest.raises(TrustedEvidenceContractError):
        refused_receipt(declared_refusal_reasons=(bad,))


# --------------------------------------------------------------------------- #
# Outcome / reason coherence
# --------------------------------------------------------------------------- #

def test_an_admission_may_not_carry_refusal_reasons():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        receipt(declared_refusal_reasons=(R.TRUSTED_EVIDENCE_STALE,))
    assert "every member of the vocabulary is a refusal" in str(excinfo.value)


def test_an_admission_that_clears_nothing_is_refused():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        receipt(declared_cleared_stages=())
    assert "names no cleared stage" in str(excinfo.value)


@pytest.mark.parametrize(
    "outcome",
    [
        DeclaredVerificationOutcome.DECLARED_REFUSED,
        DeclaredVerificationOutcome.DECLARED_INDETERMINATE,
    ],
)
def test_a_non_admission_must_carry_a_reason_code(outcome):
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        receipt(
            declared_outcome=outcome,
            declared_cleared_stages=(S.STRUCTURALLY_CONSTRUCTIBLE,),
            declared_refusal_reasons=(),
        )
    assert "no reason code" in str(excinfo.value)


def test_indeterminate_must_name_itself_as_indeterminate():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        receipt(
            declared_outcome=DeclaredVerificationOutcome.DECLARED_INDETERMINATE,
            declared_cleared_stages=(S.STRUCTURALLY_CONSTRUCTIBLE,),
            declared_refusal_reasons=(R.TRUSTED_EVIDENCE_STALE,),
        )
    assert "TRUSTED_EVIDENCE_INDETERMINATE" in str(excinfo.value)

    ok = receipt(
        declared_outcome=DeclaredVerificationOutcome.DECLARED_INDETERMINATE,
        declared_cleared_stages=(S.STRUCTURALLY_CONSTRUCTIBLE,),
        declared_refusal_reasons=(R.TRUSTED_EVIDENCE_INDETERMINATE,),
    )
    # An indeterminate payload is a refusal, and still establishes nothing.
    assert ok.declares_admission is False
    assert ok.authenticity_verified is False


def test_an_outcome_lookalike_is_refused():
    with pytest.raises(TrustedEvidenceContractError):
        receipt(declared_outcome="DECLARED_ADMITTED")


# --------------------------------------------------------------------------- #
# Two validity intervals, never conflated (§13.1.6)
# --------------------------------------------------------------------------- #

def test_receipt_and_evidence_validity_are_separate_coordinates():
    payload = receipt()
    assert (payload.receipt_valid_from, payload.receipt_valid_to) == (
        RECEIPT_VALID_FROM,
        RECEIPT_VALID_TO,
    )
    assert (payload.evidence_valid_from, payload.evidence_valid_to) == (
        VALID_FROM,
        VALID_TO,
    )
    assert payload.receipt_valid_from != payload.evidence_valid_from


def test_the_two_intervals_answer_different_questions():
    """A payload can be current while the evidence it attests is not."""

    payload = receipt(
        evidence_valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        evidence_valid_to=datetime(2026, 2, 1, tzinfo=UTC),
        receipt_valid_from=datetime(2026, 6, 1, tzinfo=UTC),
        receipt_valid_to=datetime(2026, 12, 1, tzinfo=UTC),
    )
    instant = datetime(2026, 7, 1, tzinfo=UTC)
    assert payload.receipt_is_valid_at(instant) is True
    assert payload.evidence_is_valid_at(instant) is False


@pytest.mark.parametrize(
    "method,lower,upper",
    [
        ("receipt_is_valid_at", RECEIPT_VALID_FROM, RECEIPT_VALID_TO),
        ("evidence_is_valid_at", VALID_FROM, VALID_TO),
    ],
)
def test_both_intervals_are_half_open(method, lower, upper):
    payload = receipt()
    check = getattr(payload, method)
    assert check(lower) is True
    assert check(lower - TICK) is False
    assert check(upper - TICK) is True
    assert check(upper) is False


@pytest.mark.parametrize("method", ["receipt_is_valid_at", "evidence_is_valid_at"])
def test_a_naive_instant_is_refused_and_the_clock_is_never_read(method):
    with pytest.raises(TrustedEvidenceContractError):
        getattr(receipt(), method)(datetime(2026, 7, 1))
    with pytest.raises(TypeError):
        getattr(receipt(), method)()


@pytest.mark.parametrize(
    "start,end",
    [
        ("evidence_valid_from", "evidence_valid_to"),
        ("receipt_valid_from", "receipt_valid_to"),
    ],
)
def test_a_reversed_or_zero_length_interval_is_refused(start, end):
    lower = datetime(2026, 5, 1, tzinfo=UTC)
    upper = datetime(2026, 4, 1, tzinfo=UTC)
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        receipt(**{start: lower, end: upper})
    assert "half-open" in str(excinfo.value)
    with pytest.raises(TrustedEvidenceContractError):
        receipt(**{start: lower, end: lower})


def test_absent_bounds_are_open_on_that_side():
    payload = receipt(
        receipt_valid_from=None,
        receipt_valid_to=None,
        evidence_valid_from=None,
        evidence_valid_to=None,
    )
    far = datetime(1990, 1, 1, tzinfo=UTC)
    assert payload.receipt_is_valid_at(far) is True
    assert payload.evidence_is_valid_at(far) is True
    assert json.loads(canonical_bytes(payload))["body"]["receipt_valid_to"] is None


# --------------------------------------------------------------------------- #
# Required coordinates
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "name",
    [
        "receipt_id",
        "verifier_authority_id",
        "verifier_key_id",
        "verification_protocol_id",
        "verification_protocol_version",
    ],
)
@pytest.mark.parametrize("blank", ["", "  ", " padded", None, 1, True])
def test_required_identifier_coordinates_cannot_be_omitted_or_blank(name, blank):
    with pytest.raises(TrustedEvidenceContractError):
        receipt(**{name: blank})


@pytest.mark.parametrize(
    "name",
    [
        "source_evidence_identity_digest",
        "evidence_content_digest",
        "verification_request_digest",
    ],
)
@pytest.mark.parametrize("bad", ["", "nope", CONTENT_DIGEST.upper(), CONTENT_DIGEST[:-1]])
def test_required_digest_coordinates_are_validated(name, bad):
    with pytest.raises(TrustedEvidenceContractError):
        receipt(**{name: bad})


def test_verified_at_is_mandatory_aware_and_has_no_default():
    field = {f.name: f for f in dataclasses.fields(EvidenceVerificationReceiptPayload)}[
        "verified_at"
    ]
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        receipt(verified_at=datetime(2026, 6, 1))
    assert "timezone-aware" in str(excinfo.value)


def test_verified_at_offset_equivalence_and_microsecond_preservation():
    ist = VERIFIED_AT.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert receipt(verified_at=ist).canonical_digest() == receipt().canonical_digest()
    assert b"08:00:00.750000Z" in receipt().canonical_bytes()
    assert (
        receipt(verified_at=VERIFIED_AT.replace(microsecond=750001)).canonical_digest()
        != receipt().canonical_digest()
    )


@pytest.mark.parametrize("name", ["schema", "scope"])
def test_nested_contracts_must_be_the_exact_type(name):
    @dataclasses.dataclass(frozen=True)
    class Lookalike:
        pass

    with pytest.raises(TrustedEvidenceContractError):
        receipt(**{name: Lookalike()})


# --------------------------------------------------------------------------- #
# Authorizes nothing (§13.2)
# --------------------------------------------------------------------------- #

def test_the_payload_exposes_no_authorization_surface():
    forbidden = {"authorize", "authorizes_deployment", "authorize_deployment",
                 "approve", "grant", "admit", "sign", "verify", "revoke",
                 "resolve", "register", "issue"}
    assert not (set(dir(EvidenceVerificationReceiptPayload)) & forbidden)


def test_no_field_is_named_like_a_trust_flag_or_authorization():
    names = {f.name for f in dataclasses.fields(EvidenceVerificationReceiptPayload)}
    for forbidden in ("verified", "is_verified", "authentic", "trusted",
                      "authorized", "approved", "admitted", "readiness",
                      "deployment", "value", "roi"):
        assert forbidden not in names, forbidden


def test_status_and_authenticity_are_read_only_properties_not_fields():
    for name in ("structural_status", "authenticity_verified"):
        assert isinstance(
            inspect.getattr_static(EvidenceVerificationReceiptPayload, name), property
        )
        assert name not in {
            f.name for f in dataclasses.fields(EvidenceVerificationReceiptPayload)
        }


# --------------------------------------------------------------------------- #
# Anti-forgery — task §14
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "truthy", [True, 1, "true", "True", "VERIFIED", [1], {"a": 1}, object()]
)
def test_no_verified_flag_can_be_passed_however_truthy(truthy):
    for name in ("verified", "authenticity_verified", "structural_status",
                 "trusted", "authentic", "authorized"):
        with pytest.raises(TypeError):
            receipt(**{name: truthy})


@pytest.mark.parametrize("truthy", [True, 1, "true", [1]])
def test_a_truthy_value_cannot_be_assigned_onto_the_frozen_payload(truthy):
    payload = receipt()
    for name in ("authenticity_verified", "structural_status"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(payload, name, truthy)
    assert payload.authenticity_verified is False


def test_object_setattr_cannot_raise_the_status():
    """``object.__setattr__`` — the usual frozen-dataclass bypass — is blocked.

    ``structural_status`` and ``authenticity_verified`` are read-only
    *properties*, which are data descriptors on the class. A data descriptor
    without a setter intercepts attribute assignment before the instance
    dictionary is reached, so even the low-level bypass raises rather than
    shadowing them. A plain field would have been overwritable here; that is
    precisely why these are properties (ADR §14.5's discipline).
    """

    payload = receipt()
    for name in ("authenticity_verified", "structural_status"):
        with pytest.raises(AttributeError) as excinfo:
            object.__setattr__(payload, name, True)
        assert "no setter" in str(excinfo.value)
    assert payload.authenticity_verified is False
    assert payload.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED


def test_object_setattr_on_a_real_field_still_cannot_forge_trust():
    """The bypass works on genuine fields — and buys the forger nothing.

    A real field *can* be rewritten this way, skipping ``__post_init__``. It
    changes the payload's declared content and therefore its digest, which is
    exactly the detectable outcome; it does not move the status.
    """

    payload = receipt()
    before = payload.canonical_digest()
    object.__setattr__(payload, "verifier_authority_id", "Ugence Root Authority")
    assert payload.canonical_digest() != before   # tampering is digest-visible
    assert payload.authenticity_verified is False
    assert payload.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED


def test_forging_cleared_stages_does_not_establish_them():
    payload = receipt(
        declared_cleared_stages=tuple(RECEIPT_REPORTABLE_TRUST_STAGES),
        verifier_authority_id="Ugence Root Trust Authority",
        verifier_key_id="root-signing-key-1",
    )
    assert payload.authenticity_verified is False
    assert S.CRYPTOGRAPHICALLY_AUTHENTIC in payload.unestablished_trust_stages
    assert payload.envelope_verification_reason is (
        R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
    )


@pytest.mark.parametrize(
    "authority",
    ["Ugence Trusted Evidence Authority", "TAP", "ROOT-TRUST-ANCHOR",
     "ugence-trusted-evidence-authority"],
)
def test_a_trusted_sounding_verifier_name_confers_nothing(authority):
    payload = receipt(verifier_authority_id=authority)
    assert payload.authenticity_verified is False
    assert payload.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED


def test_matching_evidence_and_request_digests_confer_nothing():
    payload = receipt(
        source_evidence_identity_digest=identity().canonical_digest(),
        evidence_content_digest=CONTENT_DIGEST,
    )
    assert payload.source_evidence_identity_digest == identity().canonical_digest()
    assert payload.authenticity_verified is False
    assert len(payload.unestablished_trust_stages) == 5


def test_a_subclass_can_lie_about_itself_but_gets_its_own_digest():
    class ForgedReceipt(EvidenceVerificationReceiptPayload):
        @property
        def authenticity_verified(self) -> bool:
            return True

    base = receipt()
    forged = ForgedReceipt(
        **{f.name: getattr(base, f.name) for f in dataclasses.fields(base)}
    )
    assert forged.authenticity_verified is True          # in isolation only
    assert canonical_digest(forged) != base.canonical_digest()
    assert b'"type":"ForgedReceipt"' in canonical_bytes(forged)


def test_monkeypatching_the_class_property_never_reaches_the_digest():
    payload = receipt()
    before = payload.canonical_digest()
    original = EvidenceVerificationReceiptPayload.authenticity_verified
    try:
        EvidenceVerificationReceiptPayload.authenticity_verified = property(
            lambda self: True
        )
        assert payload.canonical_digest() == before
        assert b"authenticity_verified" not in payload.canonical_bytes()
    finally:
        EvidenceVerificationReceiptPayload.authenticity_verified = original
    assert receipt().authenticity_verified is False


def test_a_duck_typed_payload_lookalike_carries_no_package_guarantee():
    base = receipt()

    class Lookalike:
        pass

    fake = Lookalike()
    for field in dataclasses.fields(base):
        setattr(fake, field.name, getattr(base, field.name))
    fake.authenticity_verified = True
    # It is not a dataclass, so the package's own encoder refuses it outright.
    from ugence_trusted_evidence_authority.api import (
        TrustedEvidenceCanonicalizationError,
    )

    with pytest.raises(TrustedEvidenceCanonicalizationError):
        canonical_bytes(fake)


@pytest.mark.parametrize(
    "replay",
    [
        dict(tenant_id="tenant-2"),
        dict(assessment_context_ref="ctx-2"),
        dict(subject_ref="subject-2"),
        dict(assessed_system_binding_ref="bind-2"),
        dict(assessment_purpose_ref="purpose-forecast"),
        dict(usage_scope_ref="scope-evaluation-only"),
    ],
)
def test_copying_a_payload_across_a_scope_is_detectable(replay):
    assert (
        receipt(scope=scope(**replay)).canonical_digest() != receipt().canonical_digest()
    )


def test_pickle_and_copy_round_trips_preserve_the_unverified_status():
    payload = receipt()
    for clone in (
        copy.copy(payload),
        copy.deepcopy(payload),
        pickle.loads(pickle.dumps(payload)),
    ):
        assert clone == payload
        assert clone.authenticity_verified is False
        assert clone.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
        assert clone.canonical_digest() == payload.canonical_digest()


def test_a_pickled_payload_cannot_smuggle_a_forged_status():
    """Pickle restores fields; the status is not one, so it cannot ride along."""

    payload = receipt()
    restored = pickle.loads(pickle.dumps(payload))
    with pytest.raises(AttributeError):
        object.__setattr__(restored, "authenticity_verified", True)
    assert restored.authenticity_verified is False
    # A pickle payload doctored to carry the attribute cannot install it either:
    # the property shadows anything the instance dictionary might hold.
    restored.__dict__["authenticity_verified"] = True
    assert restored.authenticity_verified is False
    assert restored.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED


def test_an_unknown_outcome_or_reason_value_is_refused():
    from ugence_trusted_evidence_authority.api import DeclaredVerificationOutcome as O

    for attempt in ("DECLARED_VERIFIED", "ADMITTED", "AUTHORITY_VERIFIED", "OK"):
        with pytest.raises(ValueError):
            O(attempt)
    for attempt in ("TRUSTED_EVIDENCE_ADMITTED", "TRUSTED_EVIDENCE_OK"):
        with pytest.raises(ValueError):
            R(attempt)


def test_omitting_any_required_verification_coordinate_is_refused():
    required = [
        f.name
        for f in dataclasses.fields(EvidenceVerificationReceiptPayload)
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    ]
    assert len(required) == 15
    base = {f.name: getattr(receipt(), f.name) for f in dataclasses.fields(receipt())}
    for name in required:
        incomplete = {k: v for k, v in base.items() if k != name}
        with pytest.raises(TypeError):
            EvidenceVerificationReceiptPayload(**incomplete)
