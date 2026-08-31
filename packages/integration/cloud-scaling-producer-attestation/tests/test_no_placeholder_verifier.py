"""Structural proof that no placeholder, optional or permissive verifier ships.

Asserted over the **source, the AST, the imports, the exports and the call graph** — not in
prose. A comment claiming there is no allow-all verifier is worth nothing; a test that walks
every function in the distribution and fails on one is worth something.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from _producer_fixtures import (
    AS_OF,
    PRODUCER_KEY_ID,
    UNTRUSTED_PRODUCER_SEED,
    build_attestation,
    build_directory,
    build_verifier,
)

import ugence_cloud_scaling_producer_attestation as pkg
from ugence_cloud_scaling_producer_attestation import (
    DenyAllTrustAnchorDirectory,
    Ed25519ProducerSignatureVerifier,
    ProducerAttestationConfigurationError,
    ProducerAttestationVerifier,
    ProducerAuthenticityOutcome,
    StaticTrustAnchorDirectory,
)

#: Property category: this module's default is declared in ``tests/conftest.py``
#: (``MODULE_PROPERTY_CATEGORY``), and a test that departs from it carries its own
#: ``@pytest.mark.<category>``, which wins. ``tests/test_property_ledger.py`` counts
#: the resolved categories, so the adversarial-to-happy ratio is machine-checked
#: rather than claimed.


PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(PKG_DIR.rglob("*.py"))

O = ProducerAuthenticityOutcome


def _trees():
    for path in SOURCES:
        yield path, ast.parse(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------- #
# 1. No verifier that returns success unconditionally
# --------------------------------------------------------------------------------------- #


def test_no_verification_function_returns_an_unconditional_true():
    """S-1: no ``verify``-shaped function has an unguarded ``return True`` at its top level.

    A ``return True`` that is not inside a conditional is exactly an allow-all verifier.
    """

    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if "verif" not in node.name and "check" not in node.name:
                continue
            for statement in node.body:
                if (
                    isinstance(statement, ast.Return)
                    and isinstance(statement.value, ast.Constant)
                    and statement.value.value is True
                ):
                    offenders.append(f"{path.name}:{node.name}")
    assert offenders == [], f"unconditional success in: {offenders}"


def test_no_source_line_grants_a_default_trusted_result():
    """S-2: no default-trusted vocabulary anywhere in the distribution's source."""

    banned = (
        "trusted = True",
        "verified = True",
        "is_trusted = True",
        "authenticated = True",
        "assume_trusted",
        "skip_verification",
        "allow_all",
        "AllowAll",
        "PermissiveVerifier",
        "NullVerifier",
        "NoopVerifier",
    )
    offenders = []
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for phrase in banned:
            if phrase in text:
                offenders.append(f"{path.name}: {phrase}")
    assert offenders == [], offenders


def test_no_hardcoded_public_key_or_seed_is_embedded_in_production_source():
    """S-3: no hardcoded trusted key, and no private key material, in the shipped package.

    A 64- or 128-character hex literal in production source would be a key or a signature
    baked into the distribution. There is none: every key the suite uses is built in the
    test tree, which does not ship.
    """

    import re

    hex_literal = re.compile(r"['\"][0-9a-fA-F]{64,}['\"]")
    offenders = []
    for path in SOURCES:
        for match in hex_literal.finditer(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: {match.group()[:24]}...")
    assert offenders == [], offenders


def test_no_module_imports_a_key_source_or_a_secret_source():
    """S-4: no environment-variable key loading, no filesystem key discovery, no network."""

    banned_roots = {
        "os", "pathlib", "socket", "secrets", "subprocess", "shutil", "urllib",
        "http", "requests", "boto3", "kubernetes", "azure", "google",
    }
    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in banned_roots:
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module.split(".")[0] in banned_roots:
                    offenders.append(f"{path.name}: from {node.module}")
    assert offenders == [], offenders


# --------------------------------------------------------------------------------------- #
# 2. No optional verifier: the collaborators are required
# --------------------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_the_resolver_and_the_signature_verifier_have_no_defaults():
    """S-5: both collaborators are required keyword arguments with no default value."""

    signature = inspect.signature(ProducerAttestationVerifier.__init__)
    for name in ("trust_anchor_resolver", "signature_verifier"):
        parameter = signature.parameters[name]
        assert parameter.default is inspect.Parameter.empty, name
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, name


@pytest.mark.parametrize("missing", ["trust_anchor_resolver", "signature_verifier"])
def test_a_verifier_cannot_be_constructed_without_a_collaborator(missing):
    """S-6: omission is a construction failure, not a silent permissive default."""

    kwargs = {
        "trust_anchor_resolver": build_directory(),
        "signature_verifier": Ed25519ProducerSignatureVerifier(),
    }
    kwargs[missing] = None
    with pytest.raises(ProducerAttestationConfigurationError):
        ProducerAttestationVerifier(**kwargs)


def test_no_verifier_class_can_be_constructed_with_zero_arguments():
    """S-7: there is no zero-argument, self-configuring verifier to reach for."""

    with pytest.raises(TypeError):
        ProducerAttestationVerifier()


# --------------------------------------------------------------------------------------- #
# 3. The signature-verification call is load-bearing
# --------------------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_the_verification_routine_actually_calls_the_signature_verifier():
    """S-8: the call exists in the AST of the authoritative routine."""

    source = (PKG_DIR / "verification.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "verify_producer_signature"
        for node in ast.walk(tree)
    )
    assert found, "the authoritative routine does not call verify_producer_signature"


@pytest.mark.invariant
def test_the_reference_signature_check_delegates_to_the_maintained_backend():
    """S-9: the production signature check calls the backend's ``verify``, not a stub."""

    source = inspect.getsource(Ed25519ProducerSignatureVerifier)
    tree = ast.parse(source)
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "verify" in calls
    assert "decode_signature" in {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_removing_the_signature_check_would_admit_a_forgery(candidate, directory):
    """S-10: the call is load-bearing, demonstrated rather than asserted.

    A verifier wired with a signature check that always succeeds — the exact shape of the
    placeholder this package forbids — admits an impostor that the real one refuses. So
    the real check is what produces the refusal, and removing it changes the outcome.
    """

    impostor = build_attestation(
        candidate, seed=UNTRUSTED_PRODUCER_SEED, producer_key_id=PRODUCER_KEY_ID
    )

    class AlwaysAcceptingVerifier:
        """Never shipped. Constructed here only to prove the real check decides."""

        is_production_authoritative = True

        def verify_producer_signature(self, *, anchor, signed_input, signature):
            return True

    real = build_verifier(directory=directory)
    neutered = build_verifier(
        directory=directory, signature_verifier=AlwaysAcceptingVerifier()
    )

    assert (
        real.verify(candidate=candidate, attestation=impostor, as_of=AS_OF).refusal.outcome
        is O.SIGNATURE_INVALID
    )
    assert (
        neutered.verify(
            candidate=candidate, attestation=impostor, as_of=AS_OF
        ).verified_attestation
        is not None
    ), "if this passes with the real verifier too, the signature check is not load-bearing"


def test_no_always_accepting_verifier_is_exported_or_defined_in_the_package():
    """S-11: the neutered verifier above lives in the test tree, and only there."""

    for symbol in pkg.__all__:
        lowered = symbol.lower()
        for fragment in ("allow", "permissive", "noop", "null", "stub", "fake", "dummy"):
            assert fragment not in lowered, symbol
    for path in SOURCES:
        assert "AlwaysAccepting" not in path.read_text(encoding="utf-8"), path.name


# --------------------------------------------------------------------------------------- #
# 4. No caller-supplied trust anchor, and no reference verifier in production
# --------------------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_the_verify_signature_takes_no_trust_anchor_or_key_argument():
    """S-12: a caller cannot hand the verifier the key it should trust."""

    parameters = set(inspect.signature(ProducerAttestationVerifier.verify).parameters)
    assert parameters == {"self", "candidate", "attestation", "as_of"}
    for banned in ("anchor", "key", "public_key", "trust", "resolver", "expected"):
        assert not any(banned in p for p in parameters)


def test_the_reference_resolver_is_refused_in_production():
    """S-13: reference grade, by the repository's own words, is refused in production."""

    with pytest.raises(ProducerAttestationConfigurationError) as exc:
        ProducerAttestationVerifier(
            trust_anchor_resolver=StaticTrustAnchorDirectory(()),
            signature_verifier=Ed25519ProducerSignatureVerifier(),
            production_mode=True,
        )
    assert "REFERENCE" in str(exc.value) or "reference" in str(exc.value)


def test_an_unattested_resolver_is_refused_in_production():
    """S-14: silence is refusal. A resolver must opt in explicitly."""

    class QuietResolver:
        def resolve(self, coordinate):  # pragma: no cover - construction fails first
            raise AssertionError("never reached")

    with pytest.raises(ProducerAttestationConfigurationError):
        ProducerAttestationVerifier(
            trust_anchor_resolver=QuietResolver(),
            signature_verifier=Ed25519ProducerSignatureVerifier(),
            production_mode=True,
        )


def test_a_non_production_signature_verifier_is_refused_in_production():
    """S-15: the signature verifier must declare itself production-authoritative too."""

    class UndeclaredVerifier:
        def verify_producer_signature(self, *, anchor, signed_input, signature):
            return False

    with pytest.raises(ProducerAttestationConfigurationError):
        ProducerAttestationVerifier(
            trust_anchor_resolver=DenyAllTrustAnchorDirectory(),
            signature_verifier=UndeclaredVerifier(),
            production_mode=True,
        )


@pytest.mark.happy
def test_the_deny_all_posture_is_admitted_in_production():
    """S-16: the ratified deny-by-default posture is the one 'no anchors' shape that ships."""

    verifier = ProducerAttestationVerifier(
        trust_anchor_resolver=DenyAllTrustAnchorDirectory(),
        signature_verifier=Ed25519ProducerSignatureVerifier(),
        production_mode=True,
    )
    assert verifier.production_mode is True


def test_no_exception_is_ever_converted_into_a_success():
    """S-17: every ``except`` handler in the package returns a refusal or re-raises.

    Walks each handler's body and fails if any of them can reach a
    ``ProducerAuthenticityResult`` carrying a verified attestation, or return ``True``.
    """

    offenders = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Return):
                    if isinstance(inner.value, ast.Constant) and inner.value.value is True:
                        offenders.append(f"{path.name}: except -> return True")
                    if isinstance(inner.value, ast.Call) and isinstance(
                        inner.value.func, ast.Name
                    ):
                        if inner.value.func.id == "ProducerAuthenticityResult":
                            offenders.append(
                                f"{path.name}: except -> ProducerAuthenticityResult(...)"
                            )
                    for keyword in getattr(inner.value, "keywords", []) or []:
                        if keyword.arg == "verified_attestation":
                            offenders.append(f"{path.name}: except -> verified artifact")
    assert offenders == [], offenders


def test_a_verifier_cannot_be_repointed_after_construction(verifier):
    """S-18: rebinding a collaborator is the component swap the production guard prevents."""

    with pytest.raises(AttributeError):
        verifier._signature_verifier = object()
    with pytest.raises(AttributeError):
        verifier._resolver = object()
