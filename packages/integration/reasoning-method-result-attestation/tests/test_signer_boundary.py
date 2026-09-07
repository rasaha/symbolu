"""The reference signer is for tests; production refuses it structurally.

Also: no production signer, key loading, key generation, network, filesystem,
environment-variable, credential or discovery code exists anywhere under src/,
and no key for any comparison engine exists in this package (ADR §4).
"""

from __future__ import annotations

import ast
import pathlib
import pickle

import pytest

import ugence_reasoning_method_result_attestation as ra
from _fixtures import ENGINE, ENGINE_ID, SIGNED_AT, engine_signer, result

SRC = pathlib.Path(ra.__file__).resolve().parent


def test_the_reference_signer_is_marked_at_class_level_and_immutable():
    assert ra.ReferenceEd25519ComparisonResultSigner.is_reference_signer is True
    signer = engine_signer()
    with pytest.raises(AttributeError):
        signer.is_reference_signer = False  # type: ignore[misc]
    with pytest.raises(AttributeError):
        signer._signing_key = None  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        pickle.dumps(signer)


def test_production_signing_refuses_the_reference_signer_and_every_subclass_of_it():
    with pytest.raises(ra.ComparisonResultAttestationSigningBoundaryError):
        ra.sign_comparison_result(result(), signer=engine_signer(), signed_at=SIGNED_AT, production_mode=True)

    class Disguised(ra.ReferenceEd25519ComparisonResultSigner):
        is_reference_signer = False

    with pytest.raises(ra.ComparisonResultAttestationSigningBoundaryError):
        ra.sign_comparison_result(
            result(),
            signer=Disguised(b"\x09" * 32, signer_identity=ENGINE_ID, signer_key_id="k", signer_role=ENGINE),
            signed_at=SIGNED_AT, production_mode=True,
        )


def test_a_signer_that_has_not_declared_itself_non_reference_is_refused_in_production():
    class Silent:
        signer_identity = ENGINE_ID
        signer_key_id = "k"
        signer_role = ENGINE

        def sign_comparison_result(self, signed_bytes):
            return "ab" * 64

    with pytest.raises(ra.ComparisonResultAttestationSigningBoundaryError):
        ra.sign_comparison_result(result(), signer=Silent(), signed_at=SIGNED_AT, production_mode=True)


def test_a_non_signer_is_refused_in_every_mode():
    for bad in (None, object(), "signer"):
        with pytest.raises(ra.ComparisonResultAttestationSigningBoundaryError):
            ra.sign_comparison_result(result(), signer=bad, signed_at=SIGNED_AT)  # type: ignore[arg-type]


def test_signing_refuses_a_naive_instant_and_a_result_it_cannot_canonicalize():
    from datetime import datetime

    with pytest.raises(ra.ComparisonResultAttestationContractError):
        ra.sign_comparison_result(result(), signer=engine_signer(), signed_at=datetime(2026, 9, 6, 12, 0))
    with pytest.raises(ra.ComparisonResultAttestationContractError):
        ra.sign_comparison_result(result(request_id="e\u0301"), signer=engine_signer(), signed_at=SIGNED_AT)


def test_no_key_loading_generation_network_filesystem_env_or_discovery_code_exists():
    banned_modules = {"os", "pathlib", "socket", "ssl", "http", "urllib", "secrets", "random",
                      "subprocess", "shutil", "tempfile", "glob", "importlib", "pkgutil",
                      "cryptography", "nacl", "requests", "httpx", "boto3", "kubernetes"}
    banned_calls = {"generate", "generate_private_key", "getenv", "environ", "open", "urlopen",
                    "connect", "listen", "walk", "listdir", "load_pem_private_key",
                    "from_private_bytes", "token_bytes", "urandom"}
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {a.name.split(".")[0] for a in node.names} & banned_modules, path.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                assert node.module.split(".")[0] not in banned_modules, (path.name, node.module)
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                assert name not in banned_calls, (path.name, name)
            elif isinstance(node, ast.Attribute) and node.attr == "environ":
                raise AssertionError(f"{path.name}: reads the environment")


def test_no_clock_is_read_anywhere():
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                assert name not in ("now", "utcnow", "today", "time", "monotonic", "perf_counter"), (
                    path.name, name)
                if name == "astimezone":
                    assert node.args, f"{path.name}: zero-argument astimezone infers the local zone"


def test_the_only_signer_class_under_src_is_the_reference_one():
    signers = []
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and "Signer" in node.name and "Port" not in node.name:
                signers.append(node.name)
    assert signers == ["ReferenceEd25519ComparisonResultSigner"]


def test_no_seed_key_or_anchor_for_the_comparison_engine_is_shipped():
    """ADR §4: no signing key for the engine identity exists anywhere. The only seeds
    in this distribution are the suite's, and none is under src/."""

    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "ugence-readiness-comparison" not in text, path.name
        assert "\\x01\" * 32" not in text and "b'\\x01'" not in text, path.name
