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
import os
import pathlib

import tomllib

import ugence_cloud_scaling_risk_integration

PKG = pathlib.Path(ugence_cloud_scaling_risk_integration.__file__).resolve().parent
ROOT = pathlib.Path(__file__).resolve().parents[2]  # cloud-scaling-risk-integration/

#: True when this suite is running inside a guard-sweep copy rather than in the
#: repository. ``scripts/cloud_scaling/guard_sweep.py`` copies the package root to
#: ``/tmp/ugence-sweep-<key>/<dir>``, keeping the package's own directory name but not
#: its parent, and announces itself with this variable. Exactly one assertion below is
#: about the parent directory, and in a copy it would measure the temporary directory
#: rather than the package — see ``_workdir`` in the sweep for the same failure mode
#: caught the other way round in Phase 5B.
_IN_SWEEP_COPY = os.environ.get("UGENCE_GUARD_SWEEP") == "1"

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
    if not _IN_SWEEP_COPY:
        # Where this package sits in the monorepo. Asserted, not skipped, everywhere the
        # monorepo is what the suite is running against; a sweep copy has no monorepo
        # parent to assert, and the test keeps its other three assertions there rather
        # than skipping wholesale — a skipped test would still be *collected*, but it
        # would stop measuring the distribution and import names during every mutant run.
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


# --- F-2: the offline guarantee must stay structurally enforced ------------------------
#
# The verifier's own negative controls prove the guarantee holds when it runs. These
# static checks are the cheap regression guard for the flags themselves: a dropped
# `--no-index` would otherwise turn "offline installation" back into "installation that
# happened to find a cached wheel", and nothing would visibly fail.


def _verifier_source() -> str:
    return (ROOT / "scripts" / "verify_isolated_install.py").read_text(encoding="utf-8")


def _verifier_command_tokens() -> set[str]:
    """String literals appearing in the verifier's command/env lists and dicts.

    Scanned from the **AST** rather than the raw text, so a docstring explaining why
    ``--upgrade`` is not used does not read as the verifier using it. Only literals in
    list/dict positions — where command arguments and environment values actually live —
    are collected.
    """

    tree = ast.parse(_verifier_source())
    tokens: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)):
            for element in node.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    tokens.add(element.value)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                for item in (key, value):
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        tokens.add(item.value)
    return tokens


def test_the_offline_install_disables_the_index_three_independent_ways():
    tokens = _verifier_command_tokens()
    source = _verifier_source()
    assert "--no-index" in tokens, "the offline install no longer passes --no-index"
    assert "PIP_NO_INDEX" in tokens, "PIP_NO_INDEX is no longer set"
    assert "PIP_DISABLE_PIP_VERSION_CHECK" in tokens
    assert "OFFLINE_SENTINEL_INDEX" in source


def test_the_verifier_never_upgrades_pip():
    """`pip install --upgrade pip` is a network fetch and would falsify "offline"."""

    assert "--upgrade" not in _verifier_command_tokens(), (
        "an --upgrade install reintroduces index access into the verifier"
    )


def test_the_verifier_uses_no_editable_install_and_no_real_index_url():
    tokens = _verifier_command_tokens()
    assert not {"-e", "--editable"} & tokens, (
        "an editable install would put the monorepo source tree on sys.path"
    )
    for token in tokens:
        for host in ("pypi.org", "files.pythonhosted.org"):
            assert host not in token, f"a real package-index URL appears: {token}"


def test_the_verifier_requires_every_distribution_before_going_offline():
    source = _verifier_source()
    assert "REQUIRED_DISTRIBUTIONS" in source
    assert "refusing to enter the offline phase" in source, (
        "the verifier must fail immediately on an incomplete wheelhouse"
    )


def test_the_verifier_reports_success_only_after_every_step():
    source = _verifier_source()
    assert "EXPECTED_STEPS" in source
    assert "refusing to report success" in source, (
        "VERIFIED must be unreachable unless every step recorded completion"
    )


def test_the_verifier_banner_names_only_the_stage_it_verified():
    """The run reaches the network in phase A; the banner must not claim otherwise."""

    source = _verifier_source()
    assert "OFFLINE ISOLATED INSTALLATION STAGE VERIFIED" in source
    assert "PHASE A" in source and "PHASE B" in source, (
        "the online collection phase and the offline installation phase must be labelled "
        "distinctly, so the scope of the offline claim is legible"
    )
    assert "defense in depth" in source.lower(), (
        "the sentinel index must be described as defense in depth: --no-index and "
        "PIP_NO_INDEX are the actual prohibition"
    )


def test_the_verifier_has_negative_controls():
    source = _verifier_source()
    assert "expect_offline_install_failure" in source
    assert "NEGATIVE PROBE FAILED" in source


def test_no_test_or_conftest_file_would_ship_in_the_wheel():
    """Only the runtime package is packaged: tests and conftest stay out."""

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    find = metadata["tool"]["setuptools"]["packages"]["find"]
    assert find["where"] == ["src"]
    assert find["include"] == ["ugence_cloud_scaling_risk_integration*"]
    # The tests and conftest live outside `src/`, so they cannot be collected.
    assert (ROOT / "tests").exists() and not (ROOT / "src" / "tests").exists()
    assert (ROOT / "conftest.py").exists()
    assert not (PKG / "conftest.py").exists()
    for path in PKG.rglob("*.py"):
        assert not path.name.startswith("test_"), f"a test file lives inside src/: {path}"


def test_every_public_name_is_importable_from_the_package_root():
    for name in ugence_cloud_scaling_risk_integration.__all__:
        assert hasattr(ugence_cloud_scaling_risk_integration, name), name


def test_no_private_module_leaks_into_the_public_surface():
    exported = set(ugence_cloud_scaling_risk_integration.__all__)
    assert not any(name.startswith("_") for name in exported - {"__version__"})
