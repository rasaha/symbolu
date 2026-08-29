"""What this distribution may import, and what it must not be able to reach.

A leaf policy family's boundary is only real if it is measured. These tests read
the shipped source directly, so a future import cannot quietly widen the surface,
and they walk the packaging metadata so it cannot drift from the code.

The load-bearing prohibition is the Phase 5A candidate contract. Borrowing the
D-4 canonical action-type set from it would look like reuse and would in fact
place the Risk Authority behind a declarative artifact.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

SRC = (
    pathlib.Path(__file__).resolve().parents[1]
    / "src"
    / "ugence_cloud_scaling_capacity_bounds_policy"
)
MODULES = sorted(SRC.glob("*.py"))


def _code_only(path: pathlib.Path) -> str:
    """The module's executable source with docstrings removed.

    Scanning raw text would trip over prose: this package's docstrings
    deliberately *name* the things the code must not do, and a test that cannot
    tell a prohibition from a violation measures nothing.
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


def test_the_source_tree_is_not_empty_so_these_tests_measure_something():
    assert len(MODULES) >= 5


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_imports_a_forbidden_neighbour(module):
    forbidden = {
        "ugence_cloud_scaling_authorization_contracts",
        "ugence_cloud_scaling_policy_authenticity",
        "ugence_cloud_scaling_producer_attestation",
        "ugence_cloud_scaling_risk_integration",
        "ugence_trusted_evidence_authority",
        "ugence_uvi_policy_contracts",
        "risk_authority",
        "actiongate",
        "boto3",
        "botocore",
        "kubernetes",
        "requests",
        "httpx",
    }
    assert _imported_roots(module).isdisjoint(forbidden)


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_every_import_is_stdlib_or_the_one_declared_dependency(module):
    declared = {"ugence_policy_authority"}
    # ``enum`` joined this set with CapacityBoundsRejectionReason: the
    # guard-coverage ADR §3 requires this family to publish a reason vocabulary,
    # and an Enum is stdlib.
    stdlib = {"__future__", "dataclasses", "datetime", "enum", "typing"}
    roots = _imported_roots(module)
    unexpected = roots - declared - stdlib
    assert not unexpected, f"{module.name} imports {sorted(unexpected)}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_the_authority_is_reached_only_through_its_public_api(module):
    """Never ``ugence_policy_authority.core.*``: that is the authority's internals."""

    tree = ast.parse(module.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("ugence_policy_authority"):
                assert node.module == "ugence_policy_authority.api", (
                    f"{module.name} reaches {node.module}; use the public api module"
                )


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_reads_a_wall_clock(module):
    """A declarative artifact has no present tense. Every instant is a caller's."""

    source = _code_only(module)
    for forbidden in ("datetime.now", "utcnow", "time.time", "date.today", "monotonic"):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_no_module_reimplements_canonicalization_or_hashing(module):
    """Every byte flows through the Policy Authority's public canonicalization."""

    source = _code_only(module)
    for forbidden in ("hashlib", "json.dumps", "sort_keys", "sha256("):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_the_shipped_source_contains_no_signing_key_material_or_signing_call(module):
    """Signing belongs to the authority. This package supplies an artifact."""

    source = _code_only(module)
    for forbidden in ("SigningKey", "from_seed", "def sign", ".sign("):
        assert forbidden not in source, f"{module.name} contains {forbidden}"


def test_the_distribution_declares_exactly_the_dependency_the_code_uses():
    pyproject = (SRC.parents[1] / "pyproject.toml").read_text()
    assert '"ugence-policy-authority>=0.1.0"' in pyproject
    for forbidden in (
        "ugence-cloud-scaling-authorization-contracts",
        "ugence-cloud-scaling-policy-authenticity",
        "ugence-uvi-policy-contracts",
        "ugence-trusted-evidence-authority",
        "ugence-risk-authority",
        "boto3",
        "kubernetes",
    ):
        assert f'"{forbidden}' not in pyproject
