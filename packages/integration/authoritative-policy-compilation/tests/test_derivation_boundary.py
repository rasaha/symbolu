"""What this root may do, proved over the shipped source rather than promised.

Three disciplines are measured by AST, so a later edit cannot quietly relax them:

* **the derivation prohibition** — ``AuthoritativeSourceRef`` is constructed at
  exactly one node, inside ``_derive_source_ref``, from the resolution alone.
* **the custody bound** — the source cannot mint or read key material, and reads no
  environment, filesystem or clock of its own; trust arrives constructed.
* **the import boundary** — both neighbours are reached through their public ``api``
  modules only, and no authority semantics are reimplemented here.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

SRC = (
    pathlib.Path(__file__).resolve().parents[1]
    / "src"
    / "ugence_authoritative_policy_compilation"
)
MODULES = sorted(SRC.glob("*.py"))


def _tree(path: pathlib.Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _enclosing_function(tree: ast.AST, target: ast.AST) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target:
                    return node.name
    return ""


def test_the_reference_is_constructed_at_exactly_one_site():
    sites = []
    for module in MODULES:
        tree = _tree(module)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "AuthoritativeSourceRef"
            ):
                sites.append((module.name, _enclosing_function(tree, node)))
    assert sites == [("service.py", "_derive_source_ref")], sites


def test_the_derivation_takes_only_the_resolution():
    tree = _tree(SRC / "service.py")
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_derive_source_ref"
    )
    arguments = [a.arg for a in function.args.args]
    assert arguments == ["resolution"], arguments
    assert function.args.kwonlyargs == []
    assert function.args.defaults == []


def test_no_module_can_mint_or_read_key_material():
    banned_calls = {
        "SigningKey", "VerifyKey", "Ed25519PolicySigner", "generate", "urandom",
        "token_bytes", "getenv", "open", "read_text", "write_text", "now", "utcnow",
    }
    banned_modules = {"os", "secrets", "random", "socket", "urllib", "requests", "time"}
    offenders = []
    for module in MODULES:
        tree = _tree(module)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in banned_modules:
                        offenders.append(f"{module.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in banned_modules:
                    offenders.append(f"{module.name}: from {node.module}")
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in banned_calls:
                    offenders.append(f"{module.name}: {name}()")
    assert offenders == [], offenders


def test_both_neighbours_are_reached_through_their_public_api_only():
    offenders = []
    for module in MODULES:
        tree = _tree(module)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            root = node.module.split(".")[0]
            if root not in ("ugence_policy_authority", "ugence_policy_workflow_compiler"):
                continue
            if node.module not in (f"{root}.api",):
                offenders.append(f"{module.name}: from {node.module}")
    assert offenders == [], offenders


def test_no_authority_semantics_are_reimplemented():
    # Canonicalization and digesting belong to Policy Authority. A second
    # implementation here would drift and surface as a false failure on a valid
    # artifact, which is exactly what the X1 design refuses.
    # Measured over calls and imports, not raw text: the string "sha256:" appears
    # legitimately as the compiler's digest *format* prefix, which is a rendering
    # convention rather than an implementation of hashing.
    banned_calls = {"sha256", "blake2b", "md5", "new", "canonical_dumps", "canonical_bytes"}
    banned_modules = {"hashlib", "hmac"}
    offenders = []
    for module in MODULES:
        tree = _tree(module)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in banned_modules:
                        offenders.append(f"{module.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in banned_modules:
                    offenders.append(f"{module.name}: from {node.module}")
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in banned_calls:
                    offenders.append(f"{module.name}: {name}()")
    assert offenders == [], offenders
    # The only digesting this package performs is Policy Authority's own function.
    service = (SRC / "service.py").read_text(encoding="utf-8")
    assert "framed_body_digest" in service


def test_maturity_states_the_non_goals():
    from ugence_authoritative_policy_compilation import version_info

    info = version_info().to_dict()
    assert info["composition_root_implemented"] is True
    assert info["derived_source_reference_implemented"] is True
    assert info["body_digest_reverification_implemented"] is True
    for never in (
        "authored_source_reference_accepted",
        "issues_policy",
        "revokes_policy",
        "grants_approval",
        "holds_key_material",
        "policy_pack_builder_shipped",
        "runtime_execution_implemented",
        "pilot_validated",
        "production_certified",
    ):
        assert info[never] is False, never
