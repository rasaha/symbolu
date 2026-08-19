"""BR-2A stops where the ratification says it stops — asserted, not promised."""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

import ugence_benchmark_registry_authority as pkg
from ugence_benchmark_registry_authority import api

PKG = pathlib.Path(__file__).resolve().parents[2]
SRC = PKG / "src" / "ugence_benchmark_registry_authority"

#: Every capability §05 forbids, as the name a class or function would carry.
FORBIDDEN_CAPABILITY_TOKENS = (
    "admissionengine",
    "admission_engine",
    "registryengine",
    "storage",
    "store_impl",
    "signatureverifier",
    "signature_verifier",
    "keyparser",
    "key_parser",
    "trustanchorstore",
    "trust_anchor_store",
    "approvalverifier",
    "approval_verifier",
    "resolverimpl",
    "resolver_impl",
    "convenienceresolver",
    "selectionapi",
    "selection_api",
    "supersessionengine",
    "adapterregistry",
    "adapter_registry",
    "identityallowlist",
    "identity_allow_list",
    "productioncompositionroot",
    "production_composition_root",
)


def test_happy_the_package_version_is_the_br2a_version():
    assert api.__version__ == "0.1.0"


def _is_port_declaration(name: str, value=None) -> bool:
    """A ``...Port`` Protocol declares a seam; it does not implement one.

    ``BenchmarkApprovalVerifierPort`` names the shape a verifier must fit, and
    ``test_confusable_and_ports.py`` proves nothing in this package fits it. The
    capability ban is on implementations, so port declarations are exempt — and
    the exemption is narrow: the name must end in ``Port`` *and* the object must
    actually be a Protocol.
    """

    if not name.endswith("Port"):
        return False
    if value is None:
        return True
    return bool(getattr(value, "_is_protocol", False))


def test_no_forbidden_capability_is_exported():
    for symbol in pkg.__all__:
        if _is_port_declaration(symbol, getattr(pkg, symbol)):
            continue
        lowered = symbol.lower().replace("_", "")
        for token in FORBIDDEN_CAPABILITY_TOKENS:
            assert token.replace("_", "") not in lowered, symbol


def test_every_port_named_symbol_really_is_an_inert_protocol():
    """The exemption above cannot be used to smuggle an implementation in."""

    for symbol in pkg.__all__:
        if symbol.endswith("Port"):
            value = getattr(pkg, symbol)
            assert getattr(value, "_is_protocol", False), symbol
            with pytest.raises(TypeError):
                value()


def test_no_class_or_function_anywhere_carries_a_forbidden_capability_name():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                if _is_port_declaration(node.name):
                    continue
                lowered = node.name.lower().replace("_", "")
                for token in FORBIDDEN_CAPABILITY_TOKENS:
                    if token.replace("_", "") in lowered:
                        offenders.append(f"{path.name}: {node.name}")
    assert offenders == [], offenders


def test_the_three_reserved_authority_issued_types_are_undefined():
    for reserved in api.BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES:
        assert not hasattr(pkg, reserved), reserved
        assert not hasattr(api, reserved), reserved


def test_the_reserved_names_appear_nowhere_as_a_class_definition():
    reserved = set(api.BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES)
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in reserved, f"{path.name}: {node.name}"


def test_no_executable_stub_or_todo_backed_runtime_path_exists():
    for path in sorted(SRC.rglob("*.py")):
        code_lines = [
            line
            for line in path.read_text().splitlines()
            if not line.strip().startswith("#")
        ]
        code = "\n".join(code_lines)
        assert "TODO" not in code, path.name
        assert "FIXME" not in code, path.name
        assert "XXX" not in code, path.name


def test_no_notimplementederror_pretends_to_be_a_port_implementation():
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                target = node.exc
                if isinstance(target, ast.Call):
                    target = target.func
                if isinstance(target, ast.Name):
                    assert target.id != "NotImplementedError", path.name


def test_no_permissive_fallback_or_default_hook_exists_in_the_encoder():
    canonical = (SRC / "contracts" / "canonical.py").read_text()
    code = canonical.split('"""', 2)[-1]
    assert "default=" not in code
    assert "except Exception" not in code
    assert "pass  # " not in code


def test_no_boolean_capability_field_exists_on_any_public_contract():
    """D-15: an unavailable guarantee is never a flippable Boolean."""

    import dataclasses

    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if not (inspect.isclass(value) and dataclasses.is_dataclass(value)):
            continue
        for f in dataclasses.fields(value):
            assert f.type is not bool, f"{symbol}.{f.name}"
            assert not f.name.startswith("is_"), f"{symbol}.{f.name}"
            assert not f.name.startswith("enable"), f"{symbol}.{f.name}"
            assert not f.name.startswith("allow"), f"{symbol}.{f.name}"


def test_no_dormant_or_reserved_future_field_exists():
    import dataclasses

    banned = ("reserved", "future", "unused", "placeholder", "todo", "tbd",
              "extension", "metadata", "extra")
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if not (inspect.isclass(value) and dataclasses.is_dataclass(value)):
            continue
        for f in dataclasses.fields(value):
            for token in banned:
                assert token not in f.name.lower(), f"{symbol}.{f.name}"


def test_nothing_in_the_package_performs_cryptography():
    banned_calls = ("hmac", "sign", "verify_signature", "ed25519", "x25519")
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id.lower() not in banned_calls, path.name


def test_the_only_hash_used_is_sha256_over_canonical_bytes():
    canonical = (SRC / "contracts" / "canonical.py").read_text()
    assert "hashlib.sha256" in canonical
    for other in ("md5", "sha1(", "sha512", "blake2"):
        assert other not in canonical


def test_no_module_outside_canonical_computes_a_digest():
    """One encoder, one digest path — enforced structurally."""

    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "canonical.py":
            continue
        if "hashlib" in path.read_text():
            offenders.append(path.name)
    assert offenders == [], offenders


def test_no_json_serialization_happens_outside_the_encoder():
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "canonical.py":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "json":
                        offenders.append(path.name)
    assert offenders == [], offenders


@pytest.mark.parametrize(
    "capability",
    [
        "register",
        "admit",
        "resolve",
        "lookup",
        "revoke",
        "append",
        "claim_slot",
        "verify",
        "sign",
        "now",
        "read",
        "write",
        "persist",
    ],
)
def test_no_module_level_function_performs_a_registry_operation(capability):
    """Pure validation only: nothing in the package *does* anything."""

    offenders = []
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if inspect.isfunction(value) and value.__name__.startswith(capability):
            offenders.append(symbol)
    assert offenders == [], offenders


def test_every_exported_function_is_a_validator_or_a_pure_reader():
    allowed_prefixes = ("require_", "is_", "canonical_", "bound_", "fault_")
    for symbol in pkg.__all__:
        value = getattr(pkg, symbol)
        if inspect.isfunction(value):
            assert symbol.startswith(allowed_prefixes), symbol
