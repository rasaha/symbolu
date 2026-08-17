"""Package boundary + declared-dependency discipline for the Phase 4C adapter.

The adapter imports exactly its two declared dependencies and nothing else from the
monorepo. It must not reach into unrelated products/apps/research trees, must not
introduce a reverse dependency, and must keep both of its dependencies leaves.

The installed-wheel behavior probe lives in ``scripts/verify_isolated_install.py``, which
proves the same public API and the same digests from site-packages with no repository on
``sys.path``. This module covers the source-tree discipline that a wheel check cannot see.
"""

from __future__ import annotations

import ast
import pathlib

import tomllib

import ugence_cloud_scaling_risk_integration

PKG = pathlib.Path(ugence_cloud_scaling_risk_integration.__file__).resolve().parent
ROOT = pathlib.Path(__file__).resolve().parents[2]  # cloud-scaling-risk-integration/

#: Import roots this integration package is allowed to reference.
_ALLOWED_MONOREPO_ROOTS = {
    "ugence_cloud_scaling_risk_integration",
    "risk_authority",                    # ugence-risk-authority (v2 contracts + seam)
    "ugence_cloud_scaling_controller",   # the advisory Cloud Scaling leaf
}

#: Monorepo roots that would signal an out-of-scope reach, an authority leak, or a
#: Phase 5/6 capability creeping in.
_FORBIDDEN_ROOTS = {
    "symbolu", "agentic", "ai_hiring", "domains", "applications",
    "tap_provider", "cloud_controller", "hybrid_llm_vnext_lab", "experiments",
    "trading", "trading2", "decision_governance",
    "cloud_scaling_operations",
    # Authority / execution packages: none of these may enter a Phase 4C adapter.
    "ugence_risk_authority_runtime",
    "ugence_risk_authority_evidence_runtime",
    "ugence_decision_authority",
    "ugence_actiongate_provider",
    "ugence_governance_contracts",
    "ugence_governance_provider_framework",
    "ugence_agent_runtime",
}


def _imports():
    for path in PKG.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield path, node.lineno, alias.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.lineno, node.module


def test_no_forbidden_monorepo_imports():
    bad = [
        f"{path.name}:{line}->{module}"
        for path, line, module in _imports()
        if module.split(".")[0] in _FORBIDDEN_ROOTS
    ]
    assert not bad, "\n".join(bad)


def test_only_the_two_declared_first_party_roots_are_imported():
    bad = []
    for path, line, module in _imports():
        root = module.split(".")[0]
        if root.startswith("ugence_") or root == "risk_authority":
            if root not in _ALLOWED_MONOREPO_ROOTS:
                bad.append(f"{path.name}:{line}->{module}")
    assert not bad, "\n".join(bad)


def test_no_third_party_runtime_dependency():
    """The adapter adds nothing beyond what its two dependencies already declare."""

    stdlib_ok = {
        "__future__", "dataclasses", "datetime", "enum", "re", "typing",
    }
    bad = []
    for path, line, module in _imports():
        root = module.split(".")[0]
        if root in _ALLOWED_MONOREPO_ROOTS or root in stdlib_ok:
            continue
        bad.append(f"{path.name}:{line}->{module}")
    assert not bad, f"unexpected runtime import(s): {bad}"


def test_declared_dependencies_match_the_imports():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {
        entry.split(">")[0].split("=")[0].split("<")[0].strip()
        for entry in metadata["project"]["dependencies"]
    }
    assert declared == {
        "ugence-cloud-scaling-controller",
        "ugence-risk-authority",
    }


def test_distribution_and_import_names_are_the_approved_ones():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["name"] == "ugence-cloud-scaling-risk-integration"
    assert ugence_cloud_scaling_risk_integration.__name__ == (
        "ugence_cloud_scaling_risk_integration"
    )
    assert ROOT.name == "cloud-scaling-risk-integration"
    assert ROOT.parent.name == "integration"


def test_version_is_the_declared_initial_release():
    assert ugence_cloud_scaling_risk_integration.__version__ == "0.1.0"
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "ugence_cloud_scaling_risk_integration.version.__version__"
    }


def test_py_typed_marker_is_present_and_packaged():
    assert (PKG / "py.typed").exists()
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = metadata["tool"]["setuptools"]["package-data"]
    assert package_data["ugence_cloud_scaling_risk_integration"] == ["py.typed"]


def test_readme_and_build_metadata_are_present():
    assert (ROOT / "README.md").exists()
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["build-system"]["build-backend"] == "setuptools.build_meta"
    assert metadata["project"]["requires-python"] == ">=3.10"
    assert metadata["project"]["readme"] == "README.md"


def test_the_isolated_install_verifier_exists():
    verifier = ROOT / "scripts" / "verify_isolated_install.py"
    assert verifier.exists()
    assert verifier.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")


def test_every_public_name_is_importable_from_the_package_root():
    for name in ugence_cloud_scaling_risk_integration.__all__:
        assert hasattr(ugence_cloud_scaling_risk_integration, name), name


def test_no_private_module_leaks_into_the_public_surface():
    exported = set(ugence_cloud_scaling_risk_integration.__all__)
    assert not any(name.startswith("_") for name in exported - {"__version__"})
