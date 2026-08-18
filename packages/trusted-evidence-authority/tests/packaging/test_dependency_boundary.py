"""Dependency direction: two maintained cryptographic backends, nothing else.

AST-scans every module in ``ugence_trusted_evidence_authority`` and asserts it
imports nothing but the standard library, itself, and the two ratified
cryptographic backends — ``cryptography`` and ``nacl`` (PyNaCl/libsodium) — and
that those two are imported from exactly one module, ``authority/backend.py``.

ADR §23 governs **Ugence package** dependency direction: which Ugence
components may import which. It does not speak to maintained third-party
cryptographic primitives, and an earlier revision of this package read it as if
it did — using that misreading to justify a handwritten Ed25519 implementation.
The independent closure audit found real vulnerabilities in that
implementation (F-01, F-02, F-03, F-06); the correction was to delete it and
call maintained backends instead. That is a narrowing of trusted code, not a
widening of the dependency surface, and this test pins the new, exact shape:
two named cryptographic distributions, one importing module, and every §23
arrow still unbroken.

The reverse direction is asserted too: no package in the monorepo imports this
one. TEV-1/TEV-2 authorize no consumer integration (ADR §30 — UVI-EV-1 is
DEFERRED), so an import from a consumer would be scope expansion.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_trusted_evidence_authority

PKG_ROOT = pathlib.Path(ugence_trusted_evidence_authority.__file__).resolve().parent
SELF = "ugence_trusted_evidence_authority"
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

#: Nothing here may ever be imported by this package. Importing any of them
#: would invert an ADR §23 arrow or put TAP on a runtime authorization path.
PROHIBITED = {
    # authorities and engines (ADR §23: "TAP ... must never import" these)
    "risk_authority", "ugence_risk_authority",
    "ugence_policy_authority", "policy_authority",
    "ugence_decision_authority", "decision_governance",
    "agent_value_readiness", "ugence_agent_value_readiness",
    "governed_value", "ugence_governed_value",
    "actiongate_provider", "ugence_actiongate_provider",
    "ugence_benchmark_registry", "benchmark_registry",
    "ugence_tap_provider", "tap_provider",
    "truth_assurance_pipeline",
    # agent runtime / cloud scaling / provider framework / products / platform
    "agent_runtime", "agent_runtime_migration", "cloud_scaling_operations",
    "cloud_controller", "governance_providers",
    "ugence_governance_provider_framework",
    "ai_hiring", "domains", "applications", "ugence_console_api", "platform_freeze",
    # even the neutral leaf: TEV-1 declares no dependency at all
    "ugence_governance_contracts",
    "ugence_uvi_policy_contracts",
    # third-party: everything except the two ratified cryptographic backends
    "pydantic", "numpy", "torch", "pandas", "fastapi", "requests", "httpx",
    "boto3", "google", "azure", "jwt", "jose", "OpenSSL", "Crypto",
    "ecdsa", "ed25519", "nacl_bindings", "pyca",
}

#: The two maintained cryptographic distributions this package calls, and the
#: single module allowed to import them. Naming both the distributions and the
#: importing module means a second crypto route cannot appear unnoticed.
CRYPTOGRAPHIC_BACKENDS = {"cryptography", "nacl"}
BACKEND_MODULE = "authority/backend.py"


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


def test_only_the_standard_library_this_package_and_the_backends_are_imported():
    allowed = _STDLIB | {SELF, "__future__"} | CRYPTOGRAPHIC_BACKENDS
    strays = {}
    for path in _sources():
        for root in _roots(path):
            if root not in allowed:
                strays.setdefault(str(path.relative_to(PKG_ROOT)), set()).add(root)
    assert not strays, strays


def test_the_cryptographic_backends_are_imported_from_exactly_one_module():
    """One module touches cryptography, so one module is what must be reviewed.

    Every other module reaches Ed25519 only through
    ``TrustedEvidenceSigningKey`` / ``TrustedEvidenceVerificationKey``, so there
    is no second path with different — possibly weaker — validation. A backend
    import appearing anywhere else fails here.
    """

    importers = sorted(
        str(path.relative_to(PKG_ROOT))
        for path in _sources()
        if _roots(path) & CRYPTOGRAPHIC_BACKENDS
    )
    assert importers == [BACKEND_MODULE], importers


def test_the_backend_module_has_no_fallback_and_no_optional_import():
    """A backend that can be missing is a backend that can be bypassed.

    ``backend.py`` may wrap its imports to *explain* an absent dependency, but
    the handler must do nothing except re-raise: no ``pass``, no assignment of
    a stub, no ``importlib`` probe, no flag another branch could read. If
    either distribution is absent the package fails to import, which is the
    only safe outcome — a package that silently degrades to a weaker check is
    worse than one that refuses to load.
    """

    path = PKG_ROOT / BACKEND_MODULE
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            caught = ast.dump(handler.type) if handler.type is not None else "bare"
            if "ImportError" not in caught and caught != "bare":
                continue
            assert handler.body, "an import handler must not be empty"
            for statement in handler.body:
                assert isinstance(statement, ast.Raise), (
                    "an ImportError handler in backend.py may only re-raise; "
                    f"found {type(statement).__name__}"
                )
        assert not node.orelse, "no else-branch may depend on an import succeeding"
        assert not node.finalbody, "no finally-branch may repair a failed import"

    # Both backends are imported at module scope, so the failure is at import
    # time rather than at the first signature check.
    module_scope = set()
    for statement in tree.body:
        module_scope |= _import_roots(statement)
        if isinstance(statement, ast.Try):
            for inner in statement.body:
                module_scope |= _import_roots(inner)
    assert CRYPTOGRAPHIC_BACKENDS <= module_scope, sorted(module_scope)

    # And no runtime feature-detection idiom anywhere in the module.
    source = path.read_text(encoding="utf-8")
    for banned in ("find_spec", "importlib.import_module", "__import__"):
        assert banned not in source, banned


def _import_roots(node):
    roots = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            roots.add(alias.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
        roots.add(node.module.split(".")[0])
    return roots


def test_the_distribution_declares_exactly_the_two_backends():
    """The declared runtime dependencies are the two backends, and only those.

    Declared, not implicit: an isolated ``--no-index`` install must be able to
    resolve them from a prepared wheelhouse, and a dependency the metadata does
    not name is a dependency that install would silently satisfy from the host.
    """

    import tomllib

    pyproject = PKG_ROOT.parents[1] / "pyproject.toml"
    if not pyproject.is_file():  # running from an installed wheel
        import importlib.metadata as md

        requires = md.requires("ugence-trusted-evidence-authority") or []
        runtime = [r for r in requires if "extra ==" not in r]
        declared = {r.split()[0].split(">")[0].split("<")[0].split("=")[0].strip()
                    for r in runtime}
        assert declared == {"cryptography", "PyNaCl"}, sorted(declared)
        return
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]
    declared = {d.split(">")[0].split("<")[0].split("=")[0].split("!")[0].strip()
                for d in dependencies}
    assert declared == {"cryptography", "PyNaCl"}, sorted(declared)
    # Every dependency is bounded on both sides: an unbounded range would let a
    # future major version change signature or validation behaviour silently.
    for requirement in dependencies:
        assert ">=" in requirement and "<" in requirement, requirement


def test_no_module_defines_a_competing_assessed_system_binding():
    """ADR §14.1 — Governance Contracts owns it, defined exactly once."""

    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name != "AssessedSystemBinding", path
                assert node.name != "SystemManifest", path  # DD-11 stays open
                assert node.name != "SubjectContext", path


# --------------------------------------------------------------------------- #
# Reverse dependency: nothing in the monorepo imports TEV-1
# --------------------------------------------------------------------------- #

def _repo_root():
    # packages/trusted-evidence-authority/tests/packaging -> repo root
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packages").is_dir() and (parent / "platform_freeze").is_dir():
            return parent
    return None


def test_no_consumer_imports_this_package():
    repo = _repo_root()
    if repo is None:
        return  # running outside the monorepo (installed wheel); nothing to scan
    own_tree = (repo / "packages" / "trusted-evidence-authority").resolve()
    importers = []
    for path in repo.glob("packages/**/*.py"):
        resolved = path.resolve()
        if str(resolved).startswith(str(own_tree)):
            continue
        if "__pycache__" in resolved.parts or "build" in resolved.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if SELF in text:
            importers.append(str(path.relative_to(repo)))
    assert not importers, (
        "TEV-1 authorizes no consumer integration (ADR §30: UVI-EV-1 DEFERRED); "
        f"unexpected references: {importers}"
    )
