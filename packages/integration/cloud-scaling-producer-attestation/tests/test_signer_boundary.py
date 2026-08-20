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
    REFERENCE_GRADE_SIGNERS,
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
    """G-16: production minting refuses the reference signer, at the call, fail-closed.

    The message names the grade in the same words the resolver-side denial uses
    (``REFERENCE``), because the two refusals are now the same mechanism and an operator
    reading one should recognise the other.
    """

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
    assert "REFERENCE signer" in str(exc.value)


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


# --- the reference-grade signer denial is subclass-aware (mirrors R-18 … R-25) --------- #


def _mint(signer):
    return mint_producer_attestation(
        signer=signer,
        tenant_id="tenant-1",
        subject_id="checkout-api",
        recommendation_id="rec-phase5a-1",
        recommendation_digest="sha256:" + "a" * 64,
        issued_at=REC_TIME,
        production_mode=True,
    )


class _PlainSubclass(ReferenceEd25519ProducerAttestationSigner):
    """A subclass that changes nothing. Still the reference key custodian."""


class _RelabelledSubclass(ReferenceEd25519ProducerAttestationSigner):
    """The attack: inherit the whole reference implementation, then deny being it."""

    is_reference_signer = False


class _TwoLevelSubclass(_RelabelledSubclass):
    """Distance from the base does not launder the inheritance."""


class _Unrelated:
    """A mixin with no signing behaviour of its own."""


class _MultipleInheritance(_Unrelated, ReferenceEd25519ProducerAttestationSigner):
    """One base is reference grade, which is enough."""

    is_reference_signer = False


def _sub(cls):
    return cls(
        producer_id=PRODUCER_ID,
        issuer=ISSUER_ID,
        producer_key_id=PRODUCER_KEY_ID,
        signing_key=signing_key(),
    )


@pytest.mark.parametrize(
    "factory, label",
    [
        (lambda: build_signer(), "the reference signer itself"),
        (lambda: _sub(_PlainSubclass), "direct subclass, no override"),
        (lambda: _sub(_RelabelledSubclass), "subclass with is_reference_signer = False"),
        (lambda: _sub(_TwoLevelSubclass), "two-level subclass"),
        (lambda: _sub(_MultipleInheritance), "multiple inheritance, one base is reference"),
    ],
)
def test_every_reference_grade_signer_subtype_is_refused_in_production(factory, label):
    """G-16a: every actual subtype of the reference signer is refused in production.

    The exact counterpart of R-18 on the resolver side, and open for the same reason: a
    subclass inherits the reference signer's whole implementation — the same in-memory
    ``TrustedEvidenceSigningKey``, built from the same caller-supplied seed — so matching
    the denial by exact type let a one-line relabelling walk straight through it.

    ``_RelabelledSubclass`` is the case that was admitted before this fix. It is not a
    contrived shape: it is what someone writes when they want the reference signer's
    behaviour and have been told production mode wants ``is_reference_signer = False``.
    """

    with pytest.raises(ProducerAttestationConfigurationError) as exc:
        _mint(factory())
    assert "REFERENCE" in str(exc.value), label


def test_a_reference_signer_subclass_cannot_relabel_its_way_in():
    """G-16b: the flag is present, false, and read — and it still does not help.

    Stated separately from G-16a because it is the whole finding: the declaration the
    subclass makes about itself is genuine, the old guard read it, and the old guard
    admitted it. The ``isinstance`` match is evaluated *first*, so the flag is never
    reached.
    """

    signer = _sub(_RelabelledSubclass)
    assert signer.is_reference_signer is False
    assert type(signer).is_reference_signer is False
    assert isinstance(signer, ReferenceEd25519ProducerAttestationSigner)

    with pytest.raises(ProducerAttestationConfigurationError) as exc:
        _mint(signer)
    message = str(exc.value)
    assert "_RelabelledSubclass" in message
    assert "subclass of ReferenceEd25519ProducerAttestationSigner" in message


@pytest.mark.happy
def test_a_custodian_that_composes_a_reference_signer_is_still_admitted():
    """G-17a: the positive control the denial must not swallow.

    ``test_a_production_signer_is_admitted`` (G-17) covers an independently implemented
    custodian. This one is the harder case: a custodian that *holds* a reference signer and
    delegates to it. It is admitted, because composition is a decision about where the key
    lives, and this custodian never declared itself reference grade — exactly the
    resolver-side ruling in R-21/R-22, applied here.
    """

    inner = build_signer()

    class ComposingCustodian:
        is_reference_signer = False
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = PRODUCER_KEY_ID
        signature_profile = PRODUCER_ATTESTATION_SIGNATURE_PROFILE

        def sign_producer_attestation(self, signing_input):
            return inner.sign_producer_attestation(signing_input)

    custodian = ComposingCustodian()
    assert not isinstance(custodian, REFERENCE_GRADE_SIGNERS)
    assert _mint(custodian).producer_key_id == PRODUCER_KEY_ID


@pytest.mark.happy
def test_reference_grade_signers_names_exactly_the_shipped_reference_signer():
    """G-16c: the tuple is the inventory, and it is neither empty nor over-broad."""

    assert REFERENCE_GRADE_SIGNERS == (ReferenceEd25519ProducerAttestationSigner,)
    assert "REFERENCE_GRADE_SIGNERS" in pkg.__all__


def test_the_reference_grade_signer_denial_uses_subclass_aware_matching():
    """G-16d: asserted over the source, so a revert to exact-type matching fails here.

    The AST counterpart of R-25, and the anti-regression that actually matters: the denial
    must be ``isinstance``-based. Exact-type matching is what let a subclass inherit the
    reference key custodian and relabel itself production.

    It also pins the ordering — but for the honest reason, which is **diagnostic, not
    security**. Both checks raise and neither admits, so swapping them leaves every subclass
    refused; what changes is which message an operator gets. An earlier revision of the
    docstring in ``signing.py`` claimed the order stopped a relabelled subclass reaching "the
    branch that would have admitted it", and there is no such branch. The ordering assertion
    is kept because the message is worth protecting, and it is described here as what it is.
    """

    source = inspect.getsource(mint_producer_attestation)
    tree = ast.parse(source.lstrip())
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "isinstance" in calls, (
        "the reference-grade signer denial must be subclass-aware; exact-type matching "
        "lets a subclass inherit the reference key custodian and relabel itself production"
    )

    isinstance_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "isinstance"
        and any(
            isinstance(arg, ast.Name) and arg.id == "REFERENCE_GRADE_SIGNERS"
            for arg in node.args
        )
    ]
    flag_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == "is_reference_signer"
    ]
    assert isinstance_lines, "the denial must match against REFERENCE_GRADE_SIGNERS"
    assert flag_lines, "the is_reference_signer flag check is expected to remain"
    assert min(isinstance_lines) < min(flag_lines), (
        "the inheritance denial should be evaluated before the is_reference_signer flag so "
        "a subclass is NAMED as reference grade rather than reported through the flag it "
        "set for itself. This is a diagnostic guarantee, not a security one: both checks "
        "raise, so swapping them refuses the same signers with a worse message"
    )


@pytest.mark.happy
def test_the_is_reference_signer_flag_refuses_something_isinstance_cannot():
    """G-16e: the second check is not redundant, and this is what it catches.

    Stated as a property because the M-1 correction made the ``isinstance`` match carry the
    security weight, and a reader could reasonably conclude the flag check is now dead code.
    It is not: a custodian that does **not** inherit from the reference signer, but honestly
    declares itself reference grade, is invisible to ``isinstance`` and refused by the flag.
    """

    inner = build_signer()

    class HonestlyReferenceGrade:
        is_reference_signer = True
        producer_id = PRODUCER_ID
        issuer = ISSUER_ID
        producer_key_id = PRODUCER_KEY_ID
        signature_profile = PRODUCER_ATTESTATION_SIGNATURE_PROFILE

        def sign_producer_attestation(self, signing_input):
            return inner.sign_producer_attestation(signing_input)

    custodian = HonestlyReferenceGrade()
    assert not isinstance(custodian, REFERENCE_GRADE_SIGNERS)

    with pytest.raises(ProducerAttestationConfigurationError) as exc:
        _mint(custodian)
    assert "is_reference_signer is True" in str(exc.value)


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
