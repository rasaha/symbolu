"""The frozen BR-1 layer plus the D-41 pair, in one direction, and none the other way.

The candidate rung's ratified release transition (D-40 as applied to
``BR-2C-RC``) admits exactly two third-party distributions — ``cryptography``
and ``PyNaCl`` — imported only inside the dedicated verifier module and only
for their D-41 roles. Every other prohibition here is unmoved.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

PKG = pathlib.Path(__file__).resolve().parents[2]
SRC = PKG / "src" / "ugence_benchmark_registry_authority"
PYPROJECT = (PKG / "pyproject.toml").read_text()


def _monorepo_root():
    """Walk up to the monorepo root, or return ``None`` if there is not one.

    Two properties in this module are about the **repository**, not about the
    package: that no other package imports this one, and that no other workflow
    references it. They are meaningful only when the package is sitting inside
    the monorepo. The gate-deletion mutation sweep deliberately runs the suite
    against a detached copy of the package tree, where neither question has an
    answer — so they skip there, with a stated reason, rather than failing for a
    reason that has nothing to do with the mutant under test.
    """

    for candidate in PKG.parents:
        if (candidate / ".github" / "workflows").is_dir() and (
            candidate / "packages"
        ).is_dir():
            return candidate
    return None


REPO = _monorepo_root()
_DETACHED = pytest.mark.skipif(
    REPO is None,
    reason=(
        "the package tree is detached from the monorepo (as it is under the "
        "mutation sweep); repository-scope properties have no answer here"
    ),
)

FORBIDDEN_PACKAGES = (
    "ugence_trusted_evidence_authority",
    "ugence_policy_authority",
    "risk_authority",
    "ugence_agent_value_readiness",
    "governed_value",
    "ugence_decision_authority",
    "ugence_governance_provider_framework",
    "ugence_governance_contracts",
    "ugence_action_clearance",
    "ugence_model_selection",
    "ugence_context_minimization",
    "ugence_cloud_scaling_controller",
    "ugence_agent_workforce_composer",
    "ugence_storygraph",
    "ugence_llm_steering_controller",
    "agent_runtime",
    "ugence_procurement",
)


def _absolute_imports(path):
    tree = ast.parse(path.read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


#: The verifier module — the only file the transition lets import the pair.
VERIFIER_MODULE = SRC / "verifier.py"

#: The ratified dependency set at the candidate rung, in declaration order:
#: the frozen BR-1 layer, then the D-41 pair, bounded on both sides in the same
#: style the trusted-evidence layer declares them (a selection, never an import).
RATIFIED_DEPENDENCIES = [
    "ugence-benchmark-registry==0.1.*",
    "cryptography>=41.0.7,<47.0.0",
    "PyNaCl>=1.5.0,<2.0.0",
]


def test_happy_the_declared_dependency_list_is_exactly_br1_plus_the_d41_pair():
    match = re.search(r"^dependencies = \[(.*?)\]", PYPROJECT, re.M | re.S)
    assert match, "no dependencies key in pyproject.toml"
    declared = re.findall(r'"([^"]+)"', match.group(1))
    assert declared == RATIFIED_DEPENDENCIES


def test_the_dependency_is_pinned_to_the_br1_zero_one_line():
    assert 'ugence-benchmark-registry==0.1.*' in PYPROJECT


def test_no_cryptographic_dependency_beyond_the_d41_pair_is_declared():
    """D-41 selected two. A third backend, a pure-Python Ed25519 or a Ugence
    authority's own implementation stays out, and the pair stays bounded."""

    match = re.search(r"^dependencies = \[(.*?)\]", PYPROJECT, re.M | re.S)
    declared = re.findall(r'"([^"]+)"', match.group(1))
    lowered = " ".join(declared).lower()
    for banned in ("ed25519", "pycryptodome", "pycrypto", "pyopenssl", "ecdsa",
                   "libsodium", "trusted-evidence", "policy-authority",
                   "risk-authority", "governance-contracts"):
        assert banned not in lowered, banned
    for pin in ("cryptography>=", "cryptography>=41.0.7,<", "PyNaCl>=1.5.0,<"):
        assert pin in " ".join(declared), pin


def test_the_d41_pair_is_imported_only_inside_the_verifier_module():
    for path in sorted(SRC.rglob("*.py")):
        imported = _absolute_imports(path) & {"cryptography", "nacl"}
        if path == VERIFIER_MODULE:
            assert imported == {"cryptography", "nacl"}, path.name
        else:
            assert imported == set(), (path.name, imported)


@pytest.mark.parametrize("forbidden", FORBIDDEN_PACKAGES)
def test_no_module_imports_a_forbidden_package(forbidden):
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if forbidden in _absolute_imports(path):
            offenders.append(path.name)
    assert offenders == [], offenders


def test_the_only_non_stdlib_imports_are_br1_and_the_pair_in_the_verifier_module():
    stdlib = {
        "__future__",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "json",
        "re",
        "types",
        "typing",
        "unicodedata",
    }
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        permitted = {"cryptography", "nacl"} if path == VERIFIER_MODULE else set()
        for module in sorted(_absolute_imports(path)):
            if module in stdlib or module == "ugence_benchmark_registry":
                continue
            if module in permitted:
                continue
            offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


@_DETACHED
def test_no_package_in_the_monorepo_imports_this_one():
    """The BR-2A **terminal state**, not a permanent invariant.

    BR-2B and later explicitly may depend on BR-2A after their own
    ratification. What this asserts is that *at BR-2A delivery* nothing does —
    so this milestone changes no other package's behaviour, and the freeze
    matrix for every neighbour is a statement about an untouched tree.
    """

    offenders = []
    for path in (REPO / "packages").rglob("*.py"):
        if PKG in path.parents:
            continue
        if "__pycache__" in str(path) or "/build/" in str(path):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):  # pragma: no cover
            continue
        if "ugence_benchmark_registry_authority" in text:
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], offenders


@_DETACHED
def test_no_workflow_other_than_this_packages_own_references_it():
    workflows = REPO / ".github" / "workflows"
    referencing = sorted(
        path.name
        for path in workflows.glob("*.yml")
        if "benchmark-registry-authority" in path.read_text()
    )
    assert referencing == ["benchmark-registry-authority-ci.yml"]


def test_the_frozen_br1_package_directory_is_not_modified_by_this_package():
    """Nothing here writes to, imports privately from, or shadows BR-1's tree."""

    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text()
        assert "ugence_benchmark_registry.contracts" not in text, path.name
        assert "ugence_benchmark_registry._" not in text, path.name


def test_only_the_public_br1_surface_is_imported():
    """BR-1's private modules are not an API and are never reached into."""

    from ugence_benchmark_registry import api as br1_api

    imported = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module == "ugence_benchmark_registry"
            ):
                imported.update(alias.name for alias in node.names)
    assert imported, "nothing is imported from BR-1 at all"
    assert imported <= set(br1_api.__all__), sorted(
        imported - set(br1_api.__all__)
    )
