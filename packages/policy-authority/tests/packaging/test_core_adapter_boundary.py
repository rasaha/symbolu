"""The generic core knows nothing about any policy family (ADR §10.2).

AST-scans every module under ``core/`` and asserts it neither imports a policy
family package nor branches on a family type. Family semantics may live only in
``adapters/``.
"""

from __future__ import annotations

import ast
import pathlib

import ugence_policy_authority

PKG_ROOT = pathlib.Path(ugence_policy_authority.__file__).resolve().parent
CORE = PKG_ROOT / "core"
ADAPTERS = PKG_ROOT / "adapters"

#: Family-owned packages the core must never reach for.
FAMILY_PACKAGES = {"ugence_uvi_policy_contracts", "ugence_governance_contracts"}

#: Family type names the core must never name, in any form.
FAMILY_TYPE_NAMES = {
    "GeographyPolicy",
    "DomainPolicy",
    "IntendedOutcomePolicy",
    "ValuationPolicy",
    "ReadinessPolicy",
    "PolicyFamily",
    "PolicyArtifactMetadata",
    "PolicyReference",
    "PolicyLifecycleState",
    "PolicyScope",
    "PolicyGate",
    "GovernedThreshold",
    "BenchmarkReference",
    "ComponentEvidenceRequirement",
}


def _core_modules():
    return sorted(CORE.rglob("*.py"))


def _imported_roots(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_the_core_exists_and_is_non_trivial():
    assert CORE.is_dir() and ADAPTERS.is_dir()
    assert len(_core_modules()) >= 10


def test_no_core_module_imports_a_policy_family_package():
    offenders = {}
    for path in _core_modules():
        bad = _imported_roots(path) & FAMILY_PACKAGES
        if bad:
            offenders[path.name] = sorted(bad)
    assert not offenders, offenders


def test_no_core_module_imports_from_the_adapters_subpackage():
    """The dependency arrow points adapters -> core, never back."""

    offenders = {}
    for path in _core_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "adapters" in node.module:
                # ``core.adapters`` (the protocol module) is core-owned and fine;
                # ``..adapters`` (the family adapters) is not.
                if node.level and node.level >= 2:
                    offenders.setdefault(path.name, []).append(node.module)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("ugence_policy_authority.adapters"):
                        offenders.setdefault(path.name, []).append(alias.name)
    assert not offenders, offenders


def test_no_core_module_names_a_policy_family_type():
    """No identifier, attribute, or string constant naming a family type."""

    offenders = {}
    for path in _core_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in FAMILY_TYPE_NAMES:
                found.add(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in FAMILY_TYPE_NAMES:
                found.add(node.attr)
        if found:
            offenders[path.name] = sorted(found)
    assert not offenders, offenders


def test_no_core_module_contains_an_isinstance_family_branch():
    """Specifically: no ``isinstance(x, GeographyPolicy)``-style chain."""

    offenders = {}
    for path in _core_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Name) and func.id in {"isinstance", "issubclass"}):
                continue
            for arg in node.args[1:]:
                for sub in ast.walk(arg):
                    if isinstance(sub, ast.Name) and sub.id in FAMILY_TYPE_NAMES:
                        offenders.setdefault(path.name, []).append(sub.id)
                    if isinstance(sub, ast.Attribute) and sub.attr in FAMILY_TYPE_NAMES:
                        offenders.setdefault(path.name, []).append(sub.attr)
    assert not offenders, offenders


def test_no_core_module_mentions_a_uvi_family_word_in_source():
    """A prose-level sweep, catching a family name smuggled into a literal."""

    banned = ("GeographyPolicy", "IntendedOutcomePolicy", "ValuationPolicy", "ReadinessPolicy")
    offenders = {}
    for path in _core_modules():
        source = path.read_text()
        hits = [word for word in banned if word in source]
        if hits:
            offenders[path.name] = hits
    assert not offenders, offenders


def test_the_uvi_adapter_is_the_only_module_importing_uvi_contracts():
    importers = set()
    for path in PKG_ROOT.rglob("*.py"):
        if "ugence_uvi_policy_contracts" in _imported_roots(path):
            importers.add(str(path.relative_to(PKG_ROOT)))
    assert importers == {"adapters/uvi.py"}, importers


def test_the_core_public_surface_is_family_neutral():
    """The core's own modules expose no family-named symbol."""

    import importlib

    for path in _core_modules():
        if path.name == "__init__.py":
            continue
        module = importlib.import_module(f"ugence_policy_authority.core.{path.stem}")
        exported = set(getattr(module, "__all__", []))
        assert not exported & FAMILY_TYPE_NAMES, (path.name, exported & FAMILY_TYPE_NAMES)
