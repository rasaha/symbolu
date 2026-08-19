"""Exactly one runtime dependency, in one direction, and none the other way."""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

PKG = pathlib.Path(__file__).resolve().parents[2]
SRC = PKG / "src" / "ugence_benchmark_registry_authority"
REPO = PKG.parents[1]
PYPROJECT = (PKG / "pyproject.toml").read_text()

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


def test_happy_the_declared_dependency_list_is_exactly_the_frozen_br1_layer():
    match = re.search(r"^dependencies = \[(.*?)\]", PYPROJECT, re.M | re.S)
    assert match, "no dependencies key in pyproject.toml"
    declared = re.findall(r'"([^"]+)"', match.group(1))
    assert declared == ["ugence-benchmark-registry==0.1.*"]


def test_the_dependency_is_pinned_to_the_br1_zero_one_line():
    assert 'ugence-benchmark-registry==0.1.*' in PYPROJECT


def test_no_cryptographic_dependency_is_declared():
    for banned in ("cryptography", "PyNaCl", "pynacl", "pyca", "nacl"):
        assert banned not in PYPROJECT, banned


@pytest.mark.parametrize("forbidden", FORBIDDEN_PACKAGES)
def test_no_module_imports_a_forbidden_package(forbidden):
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if forbidden in _absolute_imports(path):
            offenders.append(path.name)
    assert offenders == [], offenders


def test_the_only_non_stdlib_import_is_the_frozen_br1_layer():
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
        for module in sorted(_absolute_imports(path)):
            if module in stdlib or module == "ugence_benchmark_registry":
                continue
            offenders.append(f"{path.name}: {module}")
    assert offenders == [], offenders


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
