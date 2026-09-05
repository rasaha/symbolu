"""Repository-wide package import boundaries.

Two halves. The first asserts the repository itself is clean. The second builds
synthetic package trees and asserts the analyzer **reports** each violation — a
guard that cannot fail is not a guard, and this one is the only place the
"no capability package may import it" claim in the wave 2 and 3 READMEs is
actually enforced.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from check_package_import_boundaries import (  # noqa: E402
    COMPOSED_LAYERS,
    COMPOSING_LAYERS,
    LEAF_LAYER,
    check,
    discover_packages,
    module_scope_imports,
)


# --------------------------------------------------------------------------- #
# The repository is clean
# --------------------------------------------------------------------------- #
def test_the_repository_has_no_import_boundary_violations():
    report = check(_REPO_ROOT)
    assert report.ok, "\n".join(str(v) for v in report.violations)


def test_the_scan_actually_found_the_packages():
    """A scan that silently found nothing would pass the test above vacuously."""

    report = check(_REPO_ROOT)
    assert len(report.packages) >= 50
    assert len(report.namespace_owner) >= 50
    layers = {p.layer for p in report.packages}
    assert {"integration", "capabilities", LEAF_LAYER} <= layers


@pytest.mark.parametrize("namespace", [
    "ugence_governance_contracts",
    "ugence_approval_workflow",
    "ugence_authority_directory",
    "ugence_ai_system_registry",
    "ugence_data_use_admission",
    "ugence_vendor_dependency",
    "ugence_agent_assurance_evidence",
    "ugence_decision_authority",
])
def test_the_packages_that_state_this_rule_are_in_scope(namespace):
    """The wave 2 and 3 packages whose READMEs make the claim must be scanned."""

    assert namespace in check(_REPO_ROOT).namespace_owner


def test_no_capability_or_leaf_package_imports_an_integration_package():
    """The claim itself, stated directly rather than only via the aggregate."""

    report = check(_REPO_ROOT)
    integration = {ns for ns, dist in report.namespace_owner.items()
                   for p in report.packages
                   if p.distribution == dist and p.layer == "integration"}
    assert integration, "no integration packages discovered — the scan is wrong"
    offenders = [v for v in report.violations if v.rule == "layering"]
    assert offenders == []


# --------------------------------------------------------------------------- #
# The analyzer can fail
# --------------------------------------------------------------------------- #
def _write_package(root: pathlib.Path, layer: str, name: str, distribution: str,
                   namespace: str, *, dependencies=(), body: str = "") -> pathlib.Path:
    directory = root / "packages" / layer / name if layer else root / "packages" / name
    package = directory / "src" / namespace
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(body, encoding="utf-8")
    deps = ", ".join(f'"{d}"' for d in dependencies)
    (directory / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "{distribution}"\n'
        'version = "0.1.0"\n'
        f"dependencies = [{deps}]\n", encoding="utf-8")
    return directory


def _world(tmp_path: pathlib.Path, *, capability_body: str, declares=()) -> pathlib.Path:
    _write_package(tmp_path, "integration", "thing-workflow", "ugence-thing-workflow",
                   "ugence_thing_workflow")
    _write_package(tmp_path, "capabilities", "thing-capability", "ugence-thing-capability",
                   "ugence_thing_capability", dependencies=declares, body=capability_body)
    return tmp_path


def test_a_capability_importing_an_integration_package_is_caught(tmp_path):
    root = _world(tmp_path, capability_body="import ugence_thing_workflow\n",
                  declares=("ugence-thing-workflow",))  # declared, and still refused
    report = check(root)
    assert not report.ok
    layering = [v for v in report.violations if v.rule == "layering"]
    assert len(layering) == 1
    assert layering[0].imported == "ugence_thing_workflow"
    assert "may not run the other way" in layering[0].detail


def test_a_from_import_is_caught_too(tmp_path):
    root = _world(tmp_path, capability_body="from ugence_thing_workflow import Thing\n",
                  declares=("ugence-thing-workflow",))
    assert [v.rule for v in check(root).violations] == ["layering"]


def test_a_leaf_package_importing_an_integration_package_is_caught(tmp_path):
    _write_package(tmp_path, "integration", "thing-workflow", "ugence-thing-workflow",
                   "ugence_thing_workflow")
    _write_package(tmp_path, "", "thing-contracts", "ugence-thing-contracts",
                   "ugence_thing_contracts", dependencies=("ugence-thing-workflow",),
                   body="import ugence_thing_workflow\n")
    violations = check(tmp_path).violations
    assert [v.rule for v in violations] == ["layering"]
    assert violations[0].package == "thing-contracts"


def test_an_undeclared_first_party_import_is_caught(tmp_path):
    root = _world(tmp_path, capability_body="")
    _write_package(root, "capabilities", "other-capability", "ugence-other-capability",
                   "ugence_other_capability", body="import ugence_thing_capability\n")
    undeclared = [v for v in check(root).violations if v.rule == "undeclared-dependency"]
    assert len(undeclared) == 1
    assert undeclared[0].imported == "ugence_thing_capability"
    assert "does not declare" in undeclared[0].detail


def test_a_declared_same_layer_import_is_allowed(tmp_path):
    root = _world(tmp_path, capability_body="")
    _write_package(root, "capabilities", "other-capability", "ugence-other-capability",
                   "ugence_other_capability", dependencies=("ugence-thing-capability",),
                   body="import ugence_thing_capability\n")
    assert check(root).ok


def test_integration_may_import_a_capability(tmp_path):
    """The intended direction stays legal."""

    _write_package(tmp_path, "capabilities", "thing-capability", "ugence-thing-capability",
                   "ugence_thing_capability")
    _write_package(tmp_path, "integration", "thing-workflow", "ugence-thing-workflow",
                   "ugence_thing_workflow", dependencies=("ugence-thing-capability",),
                   body="import ugence_thing_capability\n")
    assert check(tmp_path).ok


def test_a_third_party_or_stdlib_import_is_never_a_violation(tmp_path):
    root = _world(tmp_path, capability_body="import json\nimport pytest\nimport nonexistent_pkg\n")
    assert check(root).ok


# --------------------------------------------------------------------------- #
# Regressions from the independent review of this gate
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("wrapper", [
    "with contextlib.suppress(ImportError):\n    {imp}\n",
    "for _ in range(1):\n    {imp}\n",
    "while True:\n    {imp}\n    break\n",
    "class Holder:\n    {imp}\n",
    "if True:\n    with contextlib.suppress(Exception):\n        {imp}\n",
])
def test_an_import_nested_at_module_scope_is_still_caught(tmp_path, wrapper):
    """Anything that runs at import time counts, however deeply nested.

    The first version only recursed into ``if`` and ``try``, so
    ``with contextlib.suppress(ImportError): import x`` — which binds exactly as
    hard as a bare import — was invisible.
    """

    body = "import contextlib\n" + wrapper.format(imp="import ugence_thing_workflow")
    root = _world(tmp_path, capability_body=body, declares=("ugence-thing-workflow",))
    assert [v.rule for v in check(root).violations] == ["layering"], body


def test_a_namespace_package_without_an_init_is_discovered(tmp_path):
    """PEP 420 namespace packages ship real code and must not read as third-party.

    ``packages/products/procurement/src`` ships ``applications`` and ``domains``
    exactly this way; missing them made every import of them invisible.
    """

    integration = tmp_path / "packages" / "integration" / "thing-workflow"
    shipped = integration / "src" / "thing_namespace" / "inner"
    shipped.mkdir(parents=True)
    (shipped / "__init__.py").write_text("", encoding="utf-8")   # no __init__ one level up
    (integration / "pyproject.toml").write_text(
        '[project]\nname = "ugence-thing-workflow"\nversion = "0.1.0"\ndependencies = []\n',
        encoding="utf-8")
    assert "thing_namespace" in {n for p in discover_packages(tmp_path) for n in p.namespaces}

    _write_package(tmp_path, "capabilities", "thing-capability", "ugence-thing-capability",
                   "ugence_thing_capability", dependencies=("ugence-thing-workflow",),
                   body="import thing_namespace\n")
    assert [v.rule for v in check(tmp_path).violations] == ["layering"]


def test_the_real_repository_registers_its_namespace_packages():
    owner = check(_REPO_ROOT).namespace_owner
    for namespace in ("applications", "domains"):
        assert namespace in owner, namespace
        assert owner[namespace] == "ugence-procurement"


def test_an_extra_counts_as_a_declaration(tmp_path):
    """A dependency declared only under [project.optional-dependencies] is declared."""

    _write_package(tmp_path, "capabilities", "thing-capability", "ugence-thing-capability",
                   "ugence_thing_capability")
    other = tmp_path / "packages" / "capabilities" / "other-capability"
    (other / "src" / "ugence_other_capability").mkdir(parents=True)
    (other / "src" / "ugence_other_capability" / "__init__.py").write_text(
        "import ugence_thing_capability\n", encoding="utf-8")
    (other / "pyproject.toml").write_text(
        '[project]\nname = "ugence-other-capability"\nversion = "0.1.0"\n'
        'dependencies = []\n\n'
        '[project.optional-dependencies]\nreference = ["ugence-thing-capability"]\n',
        encoding="utf-8")
    assert check(tmp_path).ok


def test_the_layer_model_is_deliberate():
    """Pin which layers are constrained, so the choice stays visible.

    providers / products / runtime / tooling are unconstrained on purpose: a
    product or composition root is supposed to import an integration package.
    Changing this set should require changing this test.
    """

    assert COMPOSING_LAYERS == ("integration",)
    assert COMPOSED_LAYERS == ("capabilities", LEAF_LAYER)
    report = check(_REPO_ROOT)
    unconstrained = {p.layer for p in report.packages} - set(COMPOSED_LAYERS) - set(COMPOSING_LAYERS)
    assert unconstrained == {"providers", "products", "runtime", "tooling"}


def test_the_dynamic_import_blind_spot_is_documented():
    """The gate must state what it cannot see; overselling manufactures false confidence."""

    source = (_REPO_ROOT / "scripts" / "check_package_import_boundaries.py").read_text()
    assert "static imports only" in source
    assert "importlib.import_module" in source and "workflow-fit-pilot" in source


# --------------------------------------------------------------------------- #
# Module scope vs. the optional-dependency idiom
# --------------------------------------------------------------------------- #
def test_a_function_local_import_is_not_a_dependency(tmp_path):
    """The repository's optional-dependency idiom stays legal, deliberately."""

    root = _world(tmp_path, capability_body=(
        "def use():\n"
        "    import ugence_thing_workflow  # optional at call time\n"
        "    return ugence_thing_workflow\n"))
    assert check(root).ok


def test_type_checking_and_try_imports_are_counted(tmp_path):
    for body in ("from typing import TYPE_CHECKING\n"
                 "if TYPE_CHECKING:\n    import ugence_thing_workflow\n",
                 "try:\n    import ugence_thing_workflow\nexcept ImportError:\n    pass\n"):
        target = tmp_path / body[:6].strip().replace(" ", "_")
        target.mkdir(exist_ok=True)
        root = _world(target, capability_body=body, declares=("ugence-thing-workflow",))
        assert [v.rule for v in check(root).violations] == ["layering"], body


def test_module_scope_imports_reports_lines(tmp_path):
    source = tmp_path / "m.py"
    source.write_text("import os\n\n\nfrom json import dumps\n"
                      "def f():\n    import sys\n", encoding="utf-8")
    found = dict(module_scope_imports(source))
    assert found == {"os": 1, "json": 4}   # 'sys' is function-local


def test_a_syntactically_broken_file_is_skipped_not_crashed(tmp_path):
    root = _world(tmp_path, capability_body="def (:\n")
    assert check(root).ok


def test_a_package_without_a_src_layout_is_ignored(tmp_path):
    (tmp_path / "packages" / "not-a-package").mkdir(parents=True)
    (tmp_path / "packages" / "not-a-package" / "pyproject.toml").write_text(
        '[project]\nname = "x"\n', encoding="utf-8")
    assert discover_packages(tmp_path) == []
