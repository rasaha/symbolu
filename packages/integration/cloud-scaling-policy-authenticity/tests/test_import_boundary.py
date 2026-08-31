"""What this distribution may import, and the capabilities it must not be able to reach.

A leaf package's boundary is only real if it is measured. These tests read the shipped source
directly, so a future import cannot quietly widen the dependency surface, and they walk the
declared dependencies so the packaging metadata cannot drift from the code.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "ugence_cloud_scaling_policy_authenticity"
MODULES = sorted(SRC.glob("*.py"))


def _code_only(path: pathlib.Path) -> str:
    """The module's executable source with docstrings and comments removed.

    Scanning raw text would trip over prose: this package's docstrings deliberately *name*
    the things the code must not do ("no ``hashlib`` use"), and a test that cannot tell a
    prohibition from a violation measures nothing.
    """

    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            body.pop(0)
            if not body:
                body.append(ast.Pass())
    return ast.unparse(ast.fix_missing_locations(tree))


def _imported_roots(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.invariant
def test_the_source_tree_is_not_empty_so_these_tests_measure_something():
    assert len(MODULES) >= 8


@pytest.mark.adversarial
@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_imports_a_forbidden_neighbour(module):
    """One-way leaf. Notably absent: the Trusted Evidence Authority.

    D-5B0B-4 ratified option (a) — the policy trust anchor is the Policy Authority's own key
    ring — so lending a TEV trust anchor is not merely unused here, it is unreachable.
    """

    forbidden = {
        "ugence_trusted_evidence_authority",
        "ugence_cloud_scaling_controller",
        "ugence_cloud_scaling_operations",
        "ugence_cloud_scaling_producer_attestation",
        "risk_authority",
        "actiongate",
        "boto3",
        "botocore",
        "kubernetes",
        "requests",
        "httpx",
    }
    assert _imported_roots(module).isdisjoint(forbidden)


@pytest.mark.invariant
@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_every_third_party_import_is_stdlib_or_a_declared_dependency(module):
    declared = {
        "ugence_policy_authority",
        "ugence_cloud_scaling_authorization_contracts",
    }
    stdlib = {
        "__future__", "ast", "base64", "copy", "dataclasses", "datetime", "enum", "hashlib",
        "importlib", "json", "pathlib", "pickle", "re", "sys", "types", "typing",
        "unicodedata",
    }
    local = {"." }
    roots = _imported_roots(module)
    unexpected = roots - declared - stdlib - local
    assert not unexpected, f"{module.name} imports {sorted(unexpected)}"


@pytest.mark.adversarial
@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_reads_a_wall_clock(module):
    """D-5B0B-5: no clock. Every instant is one a caller injected."""

    source = _code_only(module)
    for forbidden in ("datetime.now", "utcnow", "time.time", "date.today", "monotonic"):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


@pytest.mark.adversarial
@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_reimplements_canonicalization_or_hashing(module):
    """Every byte flows through the Policy Authority's public canonicalization."""

    if module.name == "canonical.py":
        # The one module that names the authority's helpers, and only through its public API.
        assert "from ugence_policy_authority.api import" in module.read_text()
    source = _code_only(module)
    for forbidden in ("hashlib", "json.dumps", "sort_keys", "sha256("):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


@pytest.mark.adversarial
def test_the_distribution_declares_exactly_the_dependencies_the_code_uses():
    pyproject = (SRC.parents[1] / "pyproject.toml").read_text()
    assert '"ugence-policy-authority>=0.1.0"' in pyproject
    assert '"ugence-cloud-scaling-authorization-contracts>=0.1.0"' in pyproject
    for forbidden in (
        "ugence-trusted-evidence-authority",
        "ugence-risk-authority",
        "ugence-cloud-scaling-controller",
        "boto3",
        "kubernetes",
    ):
        assert f'"{forbidden}' not in pyproject


@pytest.mark.adversarial
def test_the_shipped_source_contains_no_signing_key_material_or_signing_call():
    for module in MODULES:
        source = _code_only(module)
        for forbidden in ("SigningKey", "from_seed", "def sign", ".sign("):
            assert forbidden not in source, f"{module.name} contains {forbidden}"
