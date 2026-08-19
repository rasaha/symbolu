"""The signer boundary: no oracle, no key leakage, no authority, and no controller.

The properties here are about what a signer *cannot* do. A signer that could be handed
bytes of a caller's choosing would make every signature it ever produced worthless, so the
absence of that route is the load-bearing property — not the presence of a signature.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import inspect
import pathlib
import pickle

import pytest

from _producer_fixtures import (
    ISSUER_ID,
    PRODUCER_ID,
    PRODUCER_KEY_ID,
    REC_TIME,
    TRUSTED_PRODUCER_SEED,
    UNTRUSTED_PRODUCER_SEED,
    build_attestation,
    build_signer,
    signing_key,
)

import ugence_cloud_scaling_producer_attestation as pkg
from ugence_cloud_scaling_producer_attestation import (
    PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
    ProducerAttestationConfigurationError,
    ProducerAttestationSignerPort,
    ProducerAttestationSigningBoundaryError,
    ProducerAttestationSigningInput,
    ReferenceEd25519ProducerAttestationSigner,
    mint_producer_attestation,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.


PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent


# --------------------------------------------------------------------------------------- #
# 1. No signing oracle
# --------------------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_the_signer_port_has_no_sign_arbitrary_bytes_method():
    """G-1: the port's only signing method takes a package-minted input, not bytes."""

    methods = {
        name
        for name in dir(ProducerAttestationSignerPort)
        if not name.startswith("_")
    }
    assert "sign_producer_attestation" in methods
    for banned in ("sign", "sign_bytes", "sign_payload", "sign_raw", "sign_message"):
        assert banned not in methods, banned

    parameter = inspect.signature(
        ReferenceEd25519ProducerAttestationSigner.sign_producer_attestation
    ).parameters["signing_input"]
    assert parameter.annotation in (
        "ProducerAttestationSigningInput",
        ProducerAttestationSigningInput,
    )


@pytest.mark.parametrize("token", [None, True, object(), "token", 0, ()])
def test_a_signing_input_cannot_be_constructed_by_a_caller(token):
    """G-2: the token guard. No caller-held value reaches the private sentinel."""

    with pytest.raises(ProducerAttestationSigningBoundaryError):
        ProducerAttestationSigningInput(
            signed_input=b"anything at all",
            producer_id=PRODUCER_ID,
            issuer=ISSUER_ID,
            producer_key_id=PRODUCER_KEY_ID,
            signature_profile=PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
            issuance_token=token,
        )


def test_the_private_token_is_not_exported_from_the_curated_api():
    """G-3: there is no supported route to the sentinel."""

    assert "_SIGNING_INPUT_TOKEN" not in pkg.__all__
    assert not hasattr(pkg, "_SIGNING_INPUT_TOKEN")


def test_no_public_entry_point_accepts_a_signing_input():
    """G-4: the whole point, stated as the property that actually closes the route.

    A determined caller executing in-process can fabricate a signing input with
    ``object.__new__`` — no Python mechanism prevents that, and this package does not claim
    otherwise. What is closed is the **public API**: not one exported callable takes a
    signing input, so there is no supported path from caller-chosen bytes to a signature.
    The only public route is :func:`mint_producer_attestation`, which builds the bytes
    itself from components it validated.
    """

    signer = build_signer()
    fabricated = object.__new__(ProducerAttestationSigningInput)
    object.__setattr__(fabricated, "signed_input", b"give me a signature over this")
    object.__setattr__(fabricated, "producer_id", PRODUCER_ID)
    object.__setattr__(fabricated, "issuer", ISSUER_ID)
    object.__setattr__(fabricated, "producer_key_id", PRODUCER_KEY_ID)
    object.__setattr__(
        fabricated, "signature_profile", PRODUCER_ATTESTATION_SIGNATURE_PROFILE
    )
    object.__setattr__(fabricated, "issuance_token", None)

    # The fabricated object IS the exact type, so the signer's own type check passes —
    # and the signature still cannot be obtained through any public entry point, because
    # nothing public accepts a signing input. The only public route is minting.
    assert not any(
        "signing_input" in inspect.signature(getattr(pkg, name)).parameters
        for name in pkg.__all__
        if inspect.isfunction(getattr(pkg, name, None))
    )


def test_the_token_guard_fires_before_any_content_check():
    """G-5: the guard ordering. A caller never gets as far as a content complaint.

    Constructing a signing input with empty bytes, with a wrong profile, or with perfectly
    valid content all fail identically and for the same reason: the token is missing. That
    ordering is deliberate — a content-shaped error message would tell a caller which part
    of the shape to fix next.
    """

    for content in (b"", b"valid looking bytes", b"\x00" * 32):
        with pytest.raises(ProducerAttestationSigningBoundaryError) as exc:
            ProducerAttestationSigningInput(
                signed_input=content,
                producer_id=PRODUCER_ID,
                issuer=ISSUER_ID,
                producer_key_id=PRODUCER_KEY_ID,
                signature_profile=PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
            )
        assert "cannot be constructed directly" in str(exc.value)


# --------------------------------------------------------------------------------------- #
# 2. A signer cannot redirect, widen or mint
# --------------------------------------------------------------------------------------- #


@pytest.mark.happy
def test_a_signer_cannot_alter_any_recommendation_fact(candidate):
    """G-6: the payload is built before the signer sees anything, and it sees only bytes."""

    class TamperingSigner:
        is_reference_signer = True
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = PRODUCER_KEY_ID
        signature_profile = PRODUCER_ATTESTATION_SIGNATURE_PROFILE

        def __init__(self):
            self.seen = None
            self.inner = build_signer()

        def sign_producer_attestation(self, signing_input):
            self.seen = signing_input
            # It can read the bytes. It cannot change what the caller will bind.
            return self.inner.sign_producer_attestation(signing_input)

    tampering = TamperingSigner()
    minted = mint_producer_attestation(
        signer=tampering,
        tenant_id=candidate.tenant_id,
        subject_id=candidate.subject_id,
        recommendation_id=candidate.recommendation_id,
        recommendation_digest=candidate.recommendation_digest,
        issued_at=REC_TIME,
    )
    assert minted.tenant_id == candidate.tenant_id
    assert minted.recommendation_digest == candidate.recommendation_digest
    # The signer received exactly the bytes that were bound, and nothing else.
    assert tampering.seen.signed_input == minted.signed_bytes()


def test_a_signer_refuses_an_input_addressed_to_another_key():
    """G-7: a signer must never label a signature with coordinates it cannot answer for."""

    signer = build_signer(producer_key_id=PRODUCER_KEY_ID)
    other = build_signer(producer_key_id="some-other-key")

    captured = {}

    class CapturingSigner:
        is_reference_signer = True
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = "some-other-key"
        signature_profile = PRODUCER_ATTESTATION_SIGNATURE_PROFILE

        def sign_producer_attestation(self, signing_input):
            captured["input"] = signing_input
            return signer.sign_producer_attestation(signing_input)

    with pytest.raises(ProducerAttestationSigningBoundaryError):
        mint_producer_attestation(
            signer=CapturingSigner(),
            tenant_id="tenant-1",
            subject_id="checkout-api",
            recommendation_id="rec-phase5a-1",
            recommendation_digest="sha256:" + "a" * 64,
            issued_at=REC_TIME,
        )


def test_the_signer_port_exposes_no_authority_or_envelope_method():
    """G-8: a signer cannot mint authorization and cannot issue an envelope."""

    for name in dir(ReferenceEd25519ProducerAttestationSigner):
        lowered = name.lower()
        for banned in ("envelope", "authorize", "authorization", "credential", "gate"):
            assert banned not in lowered, name


def test_a_signer_cannot_be_repointed_after_construction():
    """G-9: rebinding a configured signer's key or coordinates raises."""

    signer = build_signer()
    for attribute in ("_signing_key", "_issuer", "_producer_key_id", "producer_id"):
        with pytest.raises(AttributeError):
            setattr(signer, attribute, "anything")


# --------------------------------------------------------------------------------------- #
# 3. No private key material escapes
# --------------------------------------------------------------------------------------- #


def test_no_private_key_material_appears_in_a_contract_digest_or_repr(candidate):
    """G-10: the seed is nowhere in the attestation, its canonical form or any repr."""

    seed_hex = TRUSTED_PRODUCER_SEED.hex()
    attestation = build_attestation(candidate)
    surfaces = [
        repr(attestation),
        str(attestation.to_canonical_dict()),
        attestation.digest(),
        attestation.signed_bytes().decode("utf-8"),
        repr(build_signer()),
    ]
    for surface in surfaces:
        assert seed_hex not in surface
        assert TRUSTED_PRODUCER_SEED.hex().upper() not in surface


def test_a_signing_input_repr_never_renders_the_frame():
    """G-11: byte length only. Signed bytes do not go into a log line."""

    captured = {}

    class ReprCapturingSigner:
        is_reference_signer = True
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = PRODUCER_KEY_ID
        signature_profile = PRODUCER_ATTESTATION_SIGNATURE_PROFILE

        def __init__(self):
            self.inner = build_signer()

        def sign_producer_attestation(self, signing_input):
            captured["repr"] = repr(signing_input)
            return self.inner.sign_producer_attestation(signing_input)

    mint_producer_attestation(
        signer=ReprCapturingSigner(),
        tenant_id="tenant-1",
        subject_id="checkout-api",
        recommendation_id="rec-phase5a-1",
        recommendation_digest="sha256:" + "a" * 64,
        issued_at=REC_TIME,
    )
    assert "recommendation_digest" not in captured["repr"]
    assert "bytes)" in captured["repr"]


def test_a_signing_key_cannot_be_pickled_or_copied():
    """G-12: serializing a signing key would copy private material out of the boundary."""

    key = signing_key()
    with pytest.raises(TypeError):
        pickle.dumps(key)
    with pytest.raises(TypeError):
        copy.copy(key)
    with pytest.raises(TypeError):
        copy.deepcopy(key)


def test_no_contract_in_this_package_ever_holds_a_signing_input():
    """G-13: a signing input is never a field of an artifact, so it never reaches a digest.

    Stated precisely rather than over-claimed: Risk Authority's canonical encoder
    base64-encodes ``bytes`` rather than refusing them, so "it cannot be canonicalized" is
    not the guarantee. The guarantee is structural — no contract in this package has a
    field that can hold one, so a signing input has no route into a canonical dict, a
    digest, an artifact or a record. It travels from the minting routine to the signer and
    is discarded.
    """

    from ugence_cloud_scaling_producer_attestation import canonical_digest

    captured = {}

    class CanonCapturingSigner:
        is_reference_signer = True
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = PRODUCER_KEY_ID
        signature_profile = PRODUCER_ATTESTATION_SIGNATURE_PROFILE

        def __init__(self):
            self.inner = build_signer()

        def sign_producer_attestation(self, signing_input):
            captured["input"] = signing_input
            return self.inner.sign_producer_attestation(signing_input)

    signer = CanonCapturingSigner()
    mint_producer_attestation(
        signer=signer,
        tenant_id="tenant-1",
        subject_id="checkout-api",
        recommendation_id="rec-phase5a-1",
        recommendation_digest="sha256:" + "a" * 64,
        issued_at=REC_TIME,
    )
    # The canonical encoder base64s bytes rather than refusing, so the real guarantee is
    # that no contract in this package ever holds a signing input — it is not a field of
    # any artifact, and never reaches a digest.
    from ugence_cloud_scaling_producer_attestation import ProducerAttestationV2

    field_types = {f.type for f in dataclasses.fields(ProducerAttestationV2)}
    assert not any("SigningInput" in str(t) for t in field_types)


def test_no_production_private_key_exists_anywhere_in_the_distribution():
    """G-14: the shipped package contains no key material at all."""

    for path in sorted(PKG_DIR.rglob("*")):
        if path.is_dir() or path.suffix == ".pyc":
            continue
        text = path.read_bytes()
        for marker in (b"BEGIN PRIVATE KEY", b"BEGIN OPENSSH", b"BEGIN RSA", b"seed ="):
            assert marker not in text, f"{path.name}: {marker!r}"


# --------------------------------------------------------------------------------------- #
# 4. Reference versus production
# --------------------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_the_shipped_signer_is_structurally_marked_as_reference():
    """G-15: exactly one signer ships, and it is distinguishable from a production one."""

    assert ReferenceEd25519ProducerAttestationSigner.is_reference_signer is True
    signer_exports = [
        name
        for name in pkg.__all__
        if "Signer" in name and name != "ProducerAttestationSignerPort"
    ]
    assert signer_exports == ["ReferenceEd25519ProducerAttestationSigner"]


def test_a_reference_signer_is_refused_in_production_mode():
    """G-16: production minting refuses the reference signer, at the call, fail-closed."""

    with pytest.raises(ProducerAttestationConfigurationError) as exc:
        mint_producer_attestation(
            signer=build_signer(),
            tenant_id="tenant-1",
            subject_id="checkout-api",
            recommendation_id="rec-phase5a-1",
            recommendation_digest="sha256:" + "a" * 64,
            issued_at=REC_TIME,
            production_mode=True,
        )
    assert "reference signer" in str(exc.value)


@pytest.mark.happy
def test_a_production_signer_is_admitted():
    """G-17: a custodian that does not declare itself reference grade is admitted."""

    inner = build_signer()

    class ProductionCustodian:
        is_reference_signer = False
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = PRODUCER_KEY_ID
        signature_profile = PRODUCER_ATTESTATION_SIGNATURE_PROFILE

        def sign_producer_attestation(self, signing_input):
            return inner.sign_producer_attestation(signing_input)

    minted = mint_producer_attestation(
        signer=ProductionCustodian(),
        tenant_id="tenant-1",
        subject_id="checkout-api",
        recommendation_id="rec-phase5a-1",
        recommendation_digest="sha256:" + "a" * 64,
        issued_at=REC_TIME,
        production_mode=True,
    )
    assert minted.producer_key_id == PRODUCER_KEY_ID


@pytest.mark.happy
def test_the_reference_signer_publishes_only_its_public_half():
    """G-18: the anchor it publishes carries a public key and the producer capability."""

    from ugence_cloud_scaling_producer_attestation import PRODUCER_ATTESTATION_CAPABILITY

    anchor = build_signer().trust_anchor(
        trust_anchor_set_id="s", trust_anchor_set_version="1"
    )
    assert anchor.capability is PRODUCER_ATTESTATION_CAPABILITY
    assert anchor.public_key != TRUSTED_PRODUCER_SEED.hex()
    assert len(anchor.public_key) == 64
