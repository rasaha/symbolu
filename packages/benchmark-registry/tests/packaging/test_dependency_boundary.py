"""Dependency direction: a zero-dependency leaf, in both directions.

AST-scans every module in ``ugence_benchmark_registry`` and asserts it imports
nothing but the standard library and itself.

ADR §23 permits the Benchmark Registry to consume ``governance-contracts`` and
forbids it from importing TAP, the Policy Authority, any engine and the Risk
Authority. BR-1 takes the narrower option and imports **nothing**: DD-2 — which
contracts land in the neutral leaf — is explicitly blocked on "the concrete
contract shapes from TEV-1/BR-1", so importing that leaf now would decide DD-2 by
implementation.

The reverse direction is asserted too: no package in the monorepo imports this
one. ADR §30 authorizes no consumer integration at BR-1 (BR-2 and UVI-EV-1 are
both DEFERRED), so an import from a consumer would be scope expansion.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import pytest
import ugence_benchmark_registry

PKG_ROOT = pathlib.Path(ugence_benchmark_registry.__file__).resolve().parent
SELF = "ugence_benchmark_registry"
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

#: Nothing here may ever be imported by this package. Importing any of them
#: would invert an ADR §23 arrow or put the Registry on an authority path.
#:
#: Written without the trusted-evidence package's *module* name on purpose: that
#: package's own reverse-dependency guard scans ``packages/**/*.py`` for its
#: module name as a substring, and a denylist entry would read as an import. The
#: allowlist test below is the stronger guard anyway — it admits only the stdlib
#: and this package, so every Ugence and third-party module is refused whether or
#: not it is named here.
PROHIBITED = {
    # authorities and engines (ADR §23: the Benchmark Registry "must never
    # import" TAP, Policy Authority, any engine, Risk Authority)
    "risk_authority", "ugence_risk_authority",
    "ugence_policy_authority", "policy_authority",
    "ugence_decision_authority", "decision_governance",
    "agent_value_readiness", "ugence_agent_value_readiness",
    "governed_value", "ugence_governed_value",
    "actiongate_provider", "ugence_actiongate_provider",
    "ugence_tap_provider", "tap_provider",
    "truth_assurance_pipeline",
    # agent runtime / cloud scaling / provider framework / products / platform
    "agent_runtime", "agent_runtime_migration", "cloud_scaling_operations",
    "cloud_controller", "governance_providers",
    "ugence_governance_provider_framework",
    "ai_hiring", "domains", "applications", "ugence_console_api", "platform_freeze",
    # even the neutral leaf: BR-1 declares no dependency at all (DD-2)
    "ugence_governance_contracts",
    "ugence_uvi_policy_contracts",
    # third-party
    "pydantic", "numpy", "torch", "pandas", "fastapi", "requests", "httpx",
    "boto3", "google", "azure", "jwt", "jose", "cryptography", "nacl",
    "OpenSSL", "Crypto", "ecdsa",
}


def _roots(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import within this package
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _sources():
    return sorted(PKG_ROOT.rglob("*.py"))


def test_no_prohibited_import_anywhere():
    offenders = {}
    for path in _sources():
        bad = _roots(path) & PROHIBITED
        if bad:
            offenders[str(path.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_only_the_standard_library_and_this_package_are_imported():
    """The strong form: an allowlist, so an unnamed dependency also fails."""

    allowed = _STDLIB | {SELF, "__future__"}
    strays = {}
    for path in _sources():
        for root in _roots(path):
            if root not in allowed:
                strays.setdefault(str(path.relative_to(PKG_ROOT)), set()).add(root)
    assert not strays, strays


def test_no_ugence_package_is_imported():
    for path in _sources():
        for root in _roots(path):
            if root == SELF:
                continue
            assert not root.startswith("ugence"), (path.name, root)


def test_the_distribution_declares_no_runtime_dependency():
    """Declared, not implicit: the isolated ``--no-index`` install is exact."""

    pyproject = PKG_ROOT.parents[1] / "pyproject.toml"
    if not pyproject.is_file():  # running from an installed wheel
        import importlib.metadata as md

        requires = md.requires("ugence-benchmark-registry") or []
        runtime = [r for r in requires if "extra ==" not in r]
        assert runtime == [], runtime
        return
    import tomllib

    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == []


def test_there_is_no_optional_or_conditional_import():
    """A dependency that can be missing is a dependency that can be bypassed."""

    for path in _sources():
        source = path.read_text(encoding="utf-8")
        for banned in ("find_spec", "importlib.import_module", "__import__",
                       "except ImportError"):
            assert banned not in source, (path.name, banned)


def test_no_module_defines_a_contract_another_package_owns():
    """ADR §6.3, §14, DD-11 — one definition per contract, in its owner."""

    forbidden = {
        # Governance Contracts owns these, already merged.
        "BenchmarkReference", "AssessedSystemBinding", "EvidenceReference",
        "EvidenceProvenance", "MetricClaim", "MetricObservation",
        "AssessmentContext", "PolicyThreshold",
        # Risk Authority's, and DD-11's open question.
        "SubjectContext", "SystemManifest",
    }
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in forbidden, (path.name, node.name)


# --------------------------------------------------------------------------- #
# Reverse dependency: nothing in the monorepo imports BR-1
# --------------------------------------------------------------------------- #
def _repo_root():
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packages").is_dir() and (parent / "platform_freeze").is_dir():
            return parent
    return None


def _names_an_import_of_self(name) -> bool:
    return isinstance(name, str) and (name == SELF or name.startswith(SELF + "."))


def _imports_self(tree) -> bool:
    """AST-detect a real import of this package anywhere in ``tree``.

    Deliberately **not** a raw substring scan. A package that lists this one in a
    forbidden-import denylist — in order to prove it does not import it — is
    asserting the boundary, not crossing it, and the merged trusted-evidence
    package does exactly that. Comments, docstrings and error messages are
    likewise not imports.

    Known limitation, stated rather than hidden: a dynamic import whose module
    name arrives through a variable is not statically decidable and is not
    matched.
    """

    dynamic = {"import_module", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_names_an_import_of_self(a.name) for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and _names_an_import_of_self(node.module):
                return True
        elif isinstance(node, ast.Call):
            func = node.func
            called = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else None
            )
            if called in dynamic:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and _names_an_import_of_self(
                        arg.value
                    ):
                        return True
    return False


def test_no_consumer_imports_this_package():
    repo = _repo_root()
    if repo is None:
        pytest.skip("running outside the monorepo (installed wheel)")
    own_tree = (repo / "packages" / "benchmark-registry").resolve()
    importers = []
    for path in repo.glob("packages/**/*.py"):
        resolved = path.resolve()
        if str(resolved).startswith(str(own_tree)):
            continue
        if "__pycache__" in resolved.parts or "build" in resolved.parts:
            continue
        try:
            tree = ast.parse(resolved.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        if _imports_self(tree):
            importers.append(str(path.relative_to(repo)))
    assert not importers, (
        "BR-1 authorizes no consumer integration (ADR §30: BR-2 and UVI-EV-1 are "
        f"DEFERRED); unexpected importers: {importers}"
    )


def test_this_package_does_not_break_the_trusted_evidence_reverse_guard():
    """The sibling package's own guard must still pass over this tree.

    The merged trusted-evidence package asserts that no file under
    ``packages/**/*.py`` contains its module name as a substring. Writing that
    name into a BR-1 denylist would trip it — a real, avoidable regression — so
    this test pins the constraint at its source rather than leaving it to be
    discovered by the other package's suite.
    """

    repo = _repo_root()
    if repo is None:
        pytest.skip("running outside the monorepo (installed wheel)")
    sibling = "ugence_trusted_evidence" + "_authority"
    own_tree = repo / "packages" / "benchmark-registry"
    offenders = []
    for path in sorted(own_tree.rglob("*.py")):
        if "__pycache__" in path.parts or "build" in path.parts:
            continue
        if sibling in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(repo)))
    assert not offenders, offenders
