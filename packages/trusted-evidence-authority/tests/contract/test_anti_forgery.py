"""Anti-forgery posture (ADR §8.1, §10, §26.12; task §11).

The question these tests answer is not "does the package validate?" but **"can a
caller obtain an authority-authentic verified state by any route?"**

They enumerate the routes named in ADR §10 and prove each one closed:
``verified=True``; a truthy non-boolean; direct enum construction; subclassing;
property override; an authority-looking issuer name; a matching digest; a
duck-typed lookalike; and copying a valid contract across scopes.

The structural reason all of them fail is the same: **no verified state exists in
this package to reach.** ``EvidenceStructuralStatus`` has one member, and it is
``STRUCTURAL_UNVERIFIED``; no member of the refusal vocabulary means success; and
no verifier, trust anchor, key or signature exists to produce one.

TEV-1 *does* export a structural receipt payload, and that changes nothing here:
a payload declaring every reportable stage cleared under an authority-looking
verifier still reports ``STRUCTURAL_UNVERIFIED`` with ``authenticity_verified``
False. Its own forgery routes are exercised in
``tests/contract/test_receipt_payload.py``.
"""

from __future__ import annotations

import dataclasses
import enum
import inspect

import pytest
from _builders import CONTENT_DIGEST, identity, observation, request, scope
from ugence_trusted_evidence_authority import api
from ugence_trusted_evidence_authority.api import (
    TRUSTED_EVIDENCE_REFUSAL_REASONS,
    CanonicalEvidenceIdentity,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
    TrustedEvidenceContractError,
    TrustedEvidenceRefusalReason,
    canonical_digest,
)


# --------------------------------------------------------------------------- #
# 1. There is nothing to forge — no verified state exists
# --------------------------------------------------------------------------- #

def test_no_verified_state_an_artifact_can_carry_exists():
    """No artifact carries a VERIFIED state. Only a *finding* may say VERIFIED.

    ``EvidenceStructuralStatus`` still has exactly one member, and TEV-2 did not
    add one: an envelope does not raise its payload's status, it wraps the
    payload and lets a verifier answer the trust question on demand.

    Exactly one enum in the package has a ``VERIFIED`` member —
    ``ReceiptVerificationOutcome`` — and it is the outcome of an act, not a
    state on an artifact. Its only ``VERIFIED`` value is produced by the single
    code path that reaches a real signature check; a caller cannot construct a
    ``ReceiptVerification`` at all, which the direct-construction test proves.
    """

    assert list(EvidenceStructuralStatus) == [
        EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    ]
    carriers = []
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            if any(m.name == "VERIFIED" for m in obj):
                carriers.append(name)
    assert carriers == ["ReceiptVerificationOutcome"], carriers

    # And no dataclass field is typed as that outcome except the verification
    # result itself, so no artifact can carry a VERIFIED value.
    from ugence_trusted_evidence_authority.api import ReceiptVerification

    for name in api.__all__:
        obj = getattr(api, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        if obj is ReceiptVerification:
            continue
        for field in dataclasses.fields(obj):
            assert "ReceiptVerificationOutcome" not in str(field.type), (name, field.name)


def test_the_receipt_type_is_a_payload_and_is_named_as_one():
    """§13.3 — there is no 'trusted but unsigned' state, so nothing is a *receipt*.

    ADR §30 and the §32 ledger assign the receipt **shape** to TEV-1, so the
    shape ships. It is named ``…ReceiptPayload``, never ``…Receipt``, because
    §13.3 rules that an unsigned artifact "is **not** a receipt".
    """

    receipt_symbols = [n for n in api.__all__ if "receipt" in n.lower()]
    assert "EvidenceVerificationReceiptPayload" in receipt_symbols

    # The unsigned TEV-1 shape is still named ``…ReceiptPayload``, never
    # ``…Receipt``. TEV-2's artifact is named ``Signed…Receipt`` because it *is*
    # signed, which is precisely the condition §13.3 attaches to the word: "a
    # receipt that is unsigned … is **not** a receipt".
    assert not hasattr(api, "EvidenceVerificationReceipt")
    assert "EvidenceVerificationReceipt" not in api.__all__

    for name in receipt_symbols:
        if name.isupper() or "_" in name:
            continue  # constants and functions name the domain they separate
        if name.endswith("Receipt"):
            assert name.startswith("Signed"), (
                f"{name} claims to be a receipt without being signed; §13.3 "
                "admits no 'trusted but unsigned' state"
            )
        else:
            assert (
                name.endswith("Payload")
                or name.endswith("Verification")
                or name.endswith("Outcome")
                or name.endswith("Verifier")
                or name.endswith("Issuer")
                or name.endswith("Signer")
                or name.endswith("Input")
                or name.endswith("Port")
            ), name


def test_the_tev2_surface_is_exactly_the_ratified_verification_layer():
    """TEV-2 ships a verifier, anchors, a signer and an envelope — and no more.

    The inverse of TEV-1's guard. What must stay absent is anything belonging to
    a *later* milestone: Benchmark Registry types (BR-1/BR-2), Readiness
    integration (UVI-EV-1 / M-3R.4), ROI (GV-F → GV-V), an ActionGate or
    deployment authorizer, credential issuance, a KMS client (DD-10), and a
    certificate authority.
    """

    present = set(api.__all__)
    for required in (
        "EvidenceVerificationAuthority",
        "SignedEvidenceVerificationReceipt",
        "SignedReceiptVerifier",
        "TrustAnchorRecord",
        "ReceiptIssuer",
    ):
        assert required in present, required

    forbidden_fragments = (
        "benchmark", "readiness", "roi", "forecast", "attribution", "valuation",
        "actiongate", "deployment", "credential", "kms", "hsm", "certificate",
        "policyapplicability", "riskauthority", "cloudscaling", "governedvalue",
    )
    for name in api.__all__:
        flattened = name.lower().replace("_", "")
        for forbidden in forbidden_fragments:
            assert forbidden not in flattened, (name, forbidden)


def test_no_public_field_anywhere_is_named_like_a_trust_flag():
    """No field asserts trust. Coordinates that *record* an act are fine.

    ``verified_at`` is deliberately **not** forbidden: it is ADR §9 row 6, the
    verification instant a receipt payload records, and recording when a claimed
    verification happened is not claiming it succeeded. What stays banned is any
    field that would *assert* a trust outcome — the flags §10 enumerates.
    """

    forbidden = {
        "verified", "is_verified", "authentic", "is_authentic", "trusted",
        "is_trusted", "signed", "verification_status", "attested", "admitted",
        "approved", "authorized", "authorizes_deployment", "valid", "is_valid",
    }
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            fields = {f.name for f in dataclasses.fields(obj)}
            assert not (fields & forbidden), (name, sorted(fields & forbidden))


def test_the_only_signature_field_is_opaque_material_never_a_trust_claim():
    """``signature`` is now a field — of the two signed artifacts, and only them.

    TEV-1 banned the name outright because nothing signed anything. TEV-2 signs,
    so the name exists; what must remain true is that it holds *material* and
    never a verdict. A ``signature`` field is therefore permitted only on the
    two signed-artifact types, must be a ``str`` in the one canonical encoding,
    and is never accompanied by a boolean saying whether it verified.
    """

    from ugence_trusted_evidence_authority.api import (
        SignedEvidenceSubmission,
        SignedEvidenceVerificationReceipt,
    )

    allowed = {SignedEvidenceSubmission, SignedEvidenceVerificationReceipt}
    for name in api.__all__:
        obj = getattr(api, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        fields = {f.name: f for f in dataclasses.fields(obj)}
        if "signature" in fields:
            assert obj in allowed, name
            assert "str" in str(fields["signature"].type), name
        # Never a stored answer about the signature.
        for banned in ("signature_valid", "signature_verified", "verified"):
            assert banned not in fields, (name, banned)


def test_the_refusal_vocabulary_offers_no_success_member_to_return():
    assert set(TrustedEvidenceRefusalReason) == set(TRUSTED_EVIDENCE_REFUSAL_REASONS)


# --------------------------------------------------------------------------- #
# 2. verified=True and truthy non-booleans
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("truthy", [True, 1, "true", "True", "VERIFIED", [1], {"a": 1}, object()])
def test_no_constructor_accepts_a_verified_flag_however_truthy(truthy):
    """There is no ``verified`` parameter to pass, truthy or otherwise."""

    with pytest.raises(TypeError):
        identity(verified=truthy)
    with pytest.raises(TypeError):
        request(verified=truthy)


@pytest.mark.parametrize("truthy", [True, 1, "true", [1]])
def test_a_truthy_value_cannot_be_assigned_onto_a_frozen_contract(truthy):
    ident = identity()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ident.authenticity_verified = truthy
    assert ident.authenticity_verified is False


def test_authenticity_verified_is_a_read_only_property_not_a_field():
    assert isinstance(
        inspect.getattr_static(CanonicalEvidenceIdentity, "authenticity_verified"),
        property,
    )
    assert "authenticity_verified" not in {
        f.name for f in dataclasses.fields(CanonicalEvidenceIdentity)
    }
    assert identity().authenticity_verified is False


def test_structural_status_is_a_read_only_property_not_a_field():
    assert isinstance(
        inspect.getattr_static(CanonicalEvidenceIdentity, "structural_status"), property
    )
    assert "structural_status" not in {
        f.name for f in dataclasses.fields(CanonicalEvidenceIdentity)
    }


# --------------------------------------------------------------------------- #
# 3. Constructing an enum directly
# --------------------------------------------------------------------------- #

def test_constructing_the_status_enum_directly_yields_only_unverified():
    assert (
        EvidenceStructuralStatus("STRUCTURAL_UNVERIFIED")
        is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    )
    for attempt in ("VERIFIED", "AUTHENTIC", "TRUSTED", "APPROVED"):
        with pytest.raises(ValueError):
            EvidenceStructuralStatus(attempt)


def test_a_trust_stage_member_is_a_name_not_an_achievement():
    """Holding ``CRYPTOGRAPHICALLY_AUTHENTIC`` establishes nothing."""

    stage = EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC
    assert isinstance(stage, str)
    ident = identity()
    assert stage in ident.unestablished_trust_stages
    assert stage not in ident.established_trust_stages
    # Naming it in a request does not establish it either.
    assert stage in request(requested_trust_stages=(stage,)).requested_trust_stages
    assert request(requested_trust_stages=(stage,)).evidence.authenticity_verified is False


def test_an_enum_cannot_be_extended_with_a_real_member_at_runtime():
    """A patched attribute is not a member, and lookup still refuses it.

    Python permits setting a plain class attribute on an ``Enum`` subclass, so
    the guarantee that matters is the stronger one: the vocabulary itself does
    not grow, ``in`` membership is unchanged, and value lookup still fails.
    """

    for enum_type in (EvidenceStructuralStatus, TrustedEvidenceRefusalReason):
        before = list(enum_type)
        try:
            enum_type.FORGED = "FORGED"
        except (AttributeError, TypeError):
            pass  # some interpreters refuse outright, which is also fine
        assert list(enum_type) == before
        assert "FORGED" not in enum_type.__members__
        with pytest.raises(ValueError):
            enum_type("FORGED")


def test_an_existing_enum_member_cannot_be_reassigned():
    with pytest.raises((AttributeError, TypeError)):
        EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED = "VERIFIED"
    assert (
        EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED.value == "STRUCTURAL_UNVERIFIED"
    )


# --------------------------------------------------------------------------- #
# 4. Subclassing a structural evidence type
# --------------------------------------------------------------------------- #

def test_a_subclass_overriding_the_status_cannot_enter_a_contract_graph():
    class ForgedIdentity(CanonicalEvidenceIdentity):
        @property
        def authenticity_verified(self) -> bool:
            return True

        @property
        def structural_status(self):
            return "AUTHORITY_VERIFIED"

    base = identity()
    forged = ForgedIdentity(**{f.name: getattr(base, f.name)
                               for f in dataclasses.fields(base)})
    # The subclass can lie about itself in isolation...
    assert forged.authenticity_verified is True
    # ...but it cannot be carried by any contract that requires the real type.
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        request(evidence=forged)
    assert "exactly" in str(excinfo.value)


def test_a_subclass_cannot_change_the_canonical_bytes_of_the_real_type():
    class ForgedIdentity(CanonicalEvidenceIdentity):
        def canonical_bytes(self) -> bytes:
            return b"forged"

    base = identity()
    forged = ForgedIdentity(**{f.name: getattr(base, f.name)
                               for f in dataclasses.fields(base)})
    # The package-level encoder ignores the override entirely: it reads fields,
    # never the instance's own method.
    assert canonical_digest(forged) != "forged"
    assert forged.canonical_bytes() == b"forged"  # only the override itself lies
    # And a subclass is refused wherever exact identity matters.
    with pytest.raises(TrustedEvidenceContractError):
        request(evidence=forged)


def test_the_type_name_is_bound_into_the_canonical_frame():
    """A subclass cannot masquerade as the base type in a digest."""

    class ForgedIdentity(CanonicalEvidenceIdentity):
        pass

    base = identity()
    forged = ForgedIdentity(**{f.name: getattr(base, f.name)
                               for f in dataclasses.fields(base)})
    assert b'"type":"ForgedIdentity"' in api.canonical_bytes(forged)
    assert canonical_digest(forged) != base.canonical_digest()


# --------------------------------------------------------------------------- #
# 5. Property override on an instance
# --------------------------------------------------------------------------- #

def test_an_instance_property_cannot_be_overridden_on_a_frozen_dataclass():
    ident = identity()
    for attribute in ("structural_status", "authenticity_verified",
                      "established_trust_stages", "unestablished_trust_stages"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(ident, attribute, "FORGED")
    assert ident.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED


def test_monkeypatching_the_class_property_does_not_change_what_a_digest_binds():
    """Even a class-level patch cannot alter the canonical bytes.

    The status is a property, so it never participates in the digest; patching
    it changes a report, not an identity. The digest — the thing a downstream
    consumer would compare — is untouched.
    """

    ident = identity()
    before = ident.canonical_digest()
    original = CanonicalEvidenceIdentity.authenticity_verified
    try:
        CanonicalEvidenceIdentity.authenticity_verified = property(lambda self: True)
        assert ident.canonical_digest() == before
        assert b"authenticity_verified" not in ident.canonical_bytes()
    finally:
        CanonicalEvidenceIdentity.authenticity_verified = original
    assert identity().authenticity_verified is False


# --------------------------------------------------------------------------- #
# 6. An authority-looking issuer or producer name
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "authority_name",
    [
        "ugence-trusted-evidence-authority",
        "Ugence Policy Authority",
        "TAP",
        "ROOT-TRUST-ANCHOR",
        "verified-by-ugence",
    ],
)
def test_an_authority_looking_name_confers_nothing(authority_name):
    """ADR §10.3 — "a string naming a verifier is not that verifier's signature"."""

    ident = identity(observation=observation(producer_id=authority_name, issuer_id=""))
    assert ident.authenticity_verified is False
    assert ident.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    assert EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC in ident.unestablished_trust_stages
    assert (
        request(evidence=ident).unperformed_verification_reason
        is TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
    )


def test_an_authority_looking_issuer_only_changes_the_digest():
    a = identity(observation=observation(issuer_id="Ugence Trust Root"))
    b = identity(observation=observation(issuer_id="issuer-b"))
    assert a.canonical_digest() != b.canonical_digest()
    assert a.authenticity_verified is b.authenticity_verified is False


# --------------------------------------------------------------------------- #
# 7. A matching digest
# --------------------------------------------------------------------------- #

def test_a_matching_content_digest_establishes_no_authenticity():
    """ADR §8.1.3 — possession is not validity; §12 stage 2 needs a trusted key."""

    req = request(expected_content_digest=CONTENT_DIGEST)
    assert req.structural_scope_mismatches() == ()
    assert req.evidence.authenticity_verified is False
    assert EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC in req.evidence.unestablished_trust_stages
    assert (
        req.unperformed_verification_reason
        is TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
    )


def test_recomputing_a_canonical_digest_is_not_verification():
    ident = identity()
    assert canonical_digest(ident) == ident.canonical_digest()
    assert ident.authenticity_verified is False
    assert len(ident.unestablished_trust_stages) == 5


def test_a_self_consistent_fabricated_identity_is_still_unverified():
    """ADR §26.12 — structural authenticity is not source authenticity.

    Everything below is internally consistent: valid digests, a coherent
    timeline, a complete custody chain, an authoritative-sounding producer. It
    is entirely fabricated, and the package says so.
    """

    fabricated = identity(
        evidence_id="totally-legitimate-evidence",
        observation=observation(producer_id="Ugence Root Authority", issuer_id=""),
    )
    assert fabricated.canonical_digest()  # it digests fine
    assert fabricated.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    assert fabricated.authenticity_verified is False
    assert fabricated.established_trust_stages == (
        EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
    )


# --------------------------------------------------------------------------- #
# 8. Duck-typed lookalikes
# --------------------------------------------------------------------------- #

def test_a_duck_typed_identity_lookalike_is_refused_by_the_request():
    @dataclasses.dataclass(frozen=True)
    class LookalikeIdentity:
        content_digest: str = CONTENT_DIGEST
        scope: object = None

        @property
        def authenticity_verified(self) -> bool:
            return True

    with pytest.raises(TrustedEvidenceContractError):
        request(evidence=LookalikeIdentity())


def test_a_lookalike_with_every_matching_attribute_name_is_still_refused():
    base = identity()

    class PerfectLookalike:
        pass

    fake = PerfectLookalike()
    for field in dataclasses.fields(base):
        setattr(fake, field.name, getattr(base, field.name))
    fake.authenticity_verified = True
    with pytest.raises(TrustedEvidenceContractError):
        request(evidence=fake)


# --------------------------------------------------------------------------- #
# 9. Cross-scope copying
# --------------------------------------------------------------------------- #

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
def test_copying_a_valid_contract_across_a_scope_is_detectable_not_silent(replay):
    original = identity()
    copied = identity(scope=scope(**replay))
    assert copied.canonical_digest() != original.canonical_digest()
    mismatches = request(evidence=copied).structural_scope_mismatches()
    assert mismatches, replay
    for reason in mismatches:
        assert reason in TRUSTED_EVIDENCE_REFUSAL_REASONS


# --------------------------------------------------------------------------- #
# 10. No object in this package authorizes anything
# --------------------------------------------------------------------------- #

def test_no_public_object_exposes_an_authorization_surface():
    """TEV-2 verifies, signs and resolves. It still authorizes nothing.

    ``verify``, ``sign_receipt``, ``issue`` and ``resolve`` are TEV-2's ratified
    verbs (§30) and are expected on the types that own them. What must remain
    absent everywhere is the *authorization* vocabulary: E-14 keeps TAP off the
    runtime path, §13.2 and E-12 keep a receipt from authorizing anything, and
    §7.1 leaves runtime action authorization with Risk Authority / ActionGate.
    """

    forbidden_members = {
        "authorize", "authorizes_deployment", "authorize_deployment",
        "authorize_action", "allow", "permit", "approve", "grant", "deploy",
        "enact", "execute", "admit_and_authorize", "authorization",
        "mint_envelope", "issue_authorization", "evaluate_policy",
        "compute_readiness", "compute_roi",
    }
    for name in api.__all__:
        obj = getattr(api, name)
        if not isinstance(obj, type):
            continue
        for member in dir(obj):
            assert member not in forbidden_members, (name, member)


def test_the_ratified_verbs_live_only_on_the_types_that_own_them():
    """Role separation (§8) asserted on the actual method surface.

    The verifier cannot sign, the signer cannot verify evidence, and the
    re-verifier can do neither. Checked as method presence rather than as prose.
    """

    from ugence_trusted_evidence_authority.api import (
        Ed25519ReceiptSigner,
        EvidenceVerificationAuthority,
        ReceiptIssuer,
        SignedReceiptVerifier,
    )

    # The verification authority holds no signing or issuing capability.
    for absent in ("sign", "sign_receipt", "issue", "signing_key"):
        assert not hasattr(EvidenceVerificationAuthority, absent), absent

    # The issuer performs no verification and resolves no trust anchor.
    for absent in ("verify", "resolve", "trust_anchors"):
        assert not hasattr(ReceiptIssuer, absent), absent

    # The independent re-verifier holds no key and issues nothing.
    for absent in ("sign", "sign_receipt", "issue", "signing_key"):
        assert not hasattr(SignedReceiptVerifier, absent), absent

    # The signer verifies nothing and admits nothing.
    for absent in ("verify", "issue", "admit", "resolve"):
        assert not hasattr(Ed25519ReceiptSigner, absent), absent


def test_no_private_key_material_is_reachable_from_any_public_artifact():
    """TEV-2 has key types — and none of them leaks a seed.

    TEV-1's guard was "no key type exists". TEV-2 has two, so the guard becomes
    the property that actually matters: private material enters only through
    ``TrustedEvidenceSigningKey``, and no contract, digest, canonical byte
    sequence, ``repr`` or verification result can carry it back out.
    """

    from ugence_trusted_evidence_authority.api import (
        TrustedEvidenceSigningKey,
        TrustedEvidenceVerificationKey,
    )

    seed = bytes(range(32))
    signing_key = TrustedEvidenceSigningKey(seed)

    # Never in a repr, in either direction.
    assert "%s" % (signing_key,) == "TrustedEvidenceSigningKey(<redacted>)"
    assert seed.hex() not in "%r" % (signing_key,)
    assert seed.hex() not in "%s" % (signing_key,)

    # No dataclass on the public surface can hold key material: the canonical
    # encoder rejects bytes, and no public contract declares a bytes field.
    from ugence_trusted_evidence_authority.api import ReceiptSigningInput

    # ``ReceiptSigningInput`` is the one non-contract carrier of bytes: it is
    # never canonicalized, never digested, never stored in an artifact, and
    # holds the *public* frame about to be signed — never key material. It is
    # exempted by identity, not by a name pattern, so a second bytes-carrying
    # type could not slip in behind it.
    exempt = {
        TrustedEvidenceSigningKey,
        TrustedEvidenceVerificationKey,
        ReceiptSigningInput,
    }
    for name in api.__all__:
        obj = getattr(api, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        if obj in exempt:
            continue
        for field in dataclasses.fields(obj):
            assert "bytes" not in str(field.type).lower(), (name, field.name)
            assert "seed" not in field.name.lower(), (name, field.name)
            assert "private" not in field.name.lower(), (name, field.name)

    # The public half is derivable; the private half is not recoverable from it.
    public = signing_key.verification_key
    assert isinstance(public, TrustedEvidenceVerificationKey)
    assert not hasattr(public, "seed")
    assert seed not in public.public_key_bytes


def test_every_constructible_object_reports_at_least_one_unestablished_stage():
    for ident in (identity(), identity(valid_from=None, valid_to=None)):
        assert len(ident.unestablished_trust_stages) >= 1
        assert EvidenceTrustStage.POLICY_SUFFICIENT in ident.unestablished_trust_stages
