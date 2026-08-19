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
one, apart from the single consumer named in :data:`AUTHORIZED_CONSUMERS`. ADR
§30's UVI-EV-1 — *readiness* consuming receipts and resolved definitions — is
still DEFERRED, and an import driven by that milestone would still be scope
expansion. What the allowlist records is a different, separately ratified
integration; see :data:`AUTHORIZED_CONSUMERS` for exactly which, and why the
blanket refusal is unchanged for everybody else.
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


#: The one builtin that performs a dynamic import from a module-name string. Every other
#: dynamic-import callable is **derived from the file's own import statements** (see
#: ``_dynamic_import_callables``) rather than guessed from a list of likely names.
_BUILTIN_DYNAMIC_IMPORT = "__import__"

#: The attribute name that performs a dynamic import on ``importlib`` however that module
#: is bound — ``importlib.import_module`` and ``il.import_module`` alike.
_IMPORTLIB_CALLABLE = "import_module"


def _names_an_import_of_self(name) -> bool:
    """True when ``name`` is this package or a submodule of it.

    ``ugence_trusted_evidence_authority_extras`` is deliberately NOT a match: only the
    exact name or a dotted submodule counts.
    """

    return isinstance(name, str) and (name == SELF or name.startswith(SELF + "."))


def _dynamic_import_callables(tree) -> set:
    """Names that call ``importlib.import_module``, derived from this file's own imports.

    ``from importlib import import_module as im`` binds ``im`` to the dynamic importer, so
    ``im("…")`` is an import. The alias is read **out of the AST import statement** — the
    detector never carries a hardcoded guess like ``im`` or ``load``, because a guess list
    is defeated by the next name somebody picks.

    Only ``from importlib import import_module [as X]`` binds a bare callable name.
    ``import importlib as il`` binds the *module*, and ``il.import_module(…)`` is matched
    separately by attribute name, so no alias tracking is needed for that shape.

    Aliases are collected from the whole module rather than only its top level, so a
    function-local ``from importlib import import_module as im`` is seen too. The trade-off
    is deliberate and conservative: the detector may consider a name importer-bound in a
    scope where Python would not, which can only ever produce a *stricter* boundary, never
    a missed import.
    """

    callables = {_BUILTIN_DYNAMIC_IMPORT}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "importlib":
            for alias in node.names:
                if alias.name == _IMPORTLIB_CALLABLE:
                    callables.add(alias.asname or alias.name)
    return callables


def _imports_self(tree) -> bool:
    """AST-detect a real import of TEV-1 anywhere in ``tree``.

    Detects, per ADR §30's reverse-dependency rule:

    * ``import ugence_trusted_evidence_authority`` (and dotted submodules, and ``as``
      aliases, and multiline parenthesised forms — all of which the AST normalizes);
    * ``from ugence_trusted_evidence_authority[.sub] import X``;
    * ``importlib.import_module("…")``, including through an aliased ``importlib``;
    * ``from importlib import import_module [as anything]`` followed by a call through that
      binding — **the alias is resolved from the import statement, not guessed** — wherever
      the call appears, including inside functions, conditionals and ``try`` blocks;
    * ``__import__("…")``;

    in every case where the module name is a **static string literal** equal to, or a dotted
    submodule of, this package.

    It deliberately does NOT match a bare string constant that is not handed to a
    dynamic-import callable. A consumer that lists this package in a *forbidden-import
    denylist* — in order to prove it does not import it — is asserting the boundary, not
    crossing it, and the raw-substring scan this replaced flagged exactly that as a
    violation. Comments, docstrings, error messages and test descriptions are likewise not
    imports; the AST never sees comments at all, and a docstring is an ``Expr`` constant,
    not a call. A function named ``im`` is only an importer if ``im`` was actually bound to
    ``importlib.import_module`` in the same file.

    **Stated limitations — this is not data-flow analysis.** A dynamic import whose module
    name arrives through a variable, an f-string, a concatenation or a container lookup is
    not statically decidable and is not matched. Neither is a callable re-exported through a
    third module, nor an importer alias that is later rebound to something else (the
    detector keeps treating the original binding as an importer, which is the conservative
    direction). Claiming otherwise would require whole-program data-flow analysis, which is
    explicitly out of scope here.
    """

    dynamic_callables = _dynamic_import_callables(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_names_an_import_of_self(a.name) for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            # ``level > 0`` is a relative import, which can never name another package.
            if node.level == 0 and _names_an_import_of_self(node.module):
                return True
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                # ``<anything>.import_module(…)`` — covers ``importlib`` under any alias.
                is_dynamic = func.attr == _IMPORTLIB_CALLABLE
            elif isinstance(func, ast.Name):
                is_dynamic = func.id in dynamic_callables
            else:
                is_dynamic = False
            if not is_dynamic:
                continue
            for arg in node.args[:1]:
                if isinstance(arg, ast.Constant) and _names_an_import_of_self(arg.value):
                    return True
    return False


#: The **only** consumers authorized to import this package, as repo-relative path
#: prefixes. Deliberately a closed, hand-maintained list rather than a pattern: adding a
#: consumer must be a deliberate edit here, reviewed against a ratified authorization, and
#: everything not on it is still refused by the blanket assertion below.
#:
#: ``packages/integration/cloud-scaling-producer-attestation`` — **Cloud Scaling Phase
#: 5B-0A, producer authenticity.** Authorized by the ratified Phase 5B architecture brief
#: (Revision 3 §20.7 §3 and §10), which fixes this package's dependency topology as Risk
#: Authority + this package + the Phase 5A authorization contracts, and requires it to
#: "reuse TEV's ``TrustAnchorCoordinate``, ``TrustAnchorRecord``, ``TrustAnchorCapability``,
#: ``TrustAnchorResolution``, ``TrustAnchorResolverPort``, ``KeyRevocation``,
#: ``StaticTrustAnchorDirectory`` and ``DenyAllTrustAnchorDirectory`` … create no second
#: trust-anchor store and no local key map".
#:
#: This is **not** ADR §30's UVI-EV-1, which remains DEFERRED. UVI-EV-1 is readiness
#: consuming *receipts and resolved definitions*. Phase 5B-0A consumes the *trust-anchor
#: contracts*, which are payload-neutral — they import no evidence contract and presume
#: nothing about what the signed bytes contain — plus the Ed25519 backend types. It
#: consumes no receipt, admits no evidence, and reuses no evidence verifier; its own suite
#: asserts each of those absences structurally.
AUTHORIZED_CONSUMERS = (
    "packages/integration/cloud-scaling-producer-attestation",
)


def _consumer_importers(repo):
    """Every module outside this package that imports it, minus the authorized consumers."""

    own_tree = (repo / "packages" / "trusted-evidence-authority").resolve()
    authorized = tuple(
        str((repo / prefix).resolve()) for prefix in AUTHORIZED_CONSUMERS
    )
    importers = []
    for path in repo.glob("packages/**/*.py"):
        resolved = path.resolve()
        if str(resolved).startswith(str(own_tree)):
            continue
        if "__pycache__" in resolved.parts or "build" in resolved.parts:
            continue
        if any(str(resolved).startswith(prefix) for prefix in authorized):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue  # not importable Python for this interpreter; nothing to import
        if _imports_self(tree):
            importers.append(str(path.relative_to(repo)))
    return importers


def test_no_unauthorized_consumer_imports_this_package():
    repo = _repo_root()
    if repo is None:
        return  # running outside the monorepo (installed wheel); nothing to scan
    importers = _consumer_importers(repo)
    assert not importers, (
        "TEV authorizes consumer integration only for the packages named in "
        f"AUTHORIZED_CONSUMERS ({list(AUTHORIZED_CONSUMERS)}); ADR §30's UVI-EV-1 remains "
        f"DEFERRED. Unexpected imports: {importers}"
    )


def test_the_consumer_allowlist_is_exactly_the_ratified_set():
    """The allowlist is a closed list, not a pattern, and it has not grown unnoticed.

    A boundary whose exception list can be widened silently is not a boundary. Growing it
    must fail here first, so the widening is reviewed against a ratified authorization
    rather than noticed later.
    """

    assert AUTHORIZED_CONSUMERS == (
        "packages/integration/cloud-scaling-producer-attestation",
    )


def test_the_reverse_dependency_detector_still_fires_on_an_unauthorized_consumer(tmp_path):
    """A boundary test that cannot fail is not a boundary test.

    Plants an importing module at a path that is **not** on the allowlist and asserts the
    scan reports it — so the allowlist above narrows the assertion to one reviewed
    consumer, and does not disable it.
    """

    planted = tmp_path / "packages" / "some-other-consumer" / "mod.py"
    planted.parent.mkdir(parents=True)
    planted.write_text(f"import {SELF}\n", encoding="utf-8")
    (tmp_path / "packages" / "trusted-evidence-authority").mkdir(parents=True)

    found = _consumer_importers(tmp_path)
    assert found == ["packages/some-other-consumer/mod.py"], found


def test_the_authorized_consumer_is_exempt_from_the_same_scan(tmp_path):
    """...and the exemption is real: the identical module on the allowlisted path passes."""

    allowed = tmp_path / AUTHORIZED_CONSUMERS[0] / "mod.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text(f"import {SELF}\n", encoding="utf-8")
    (tmp_path / "packages" / "trusted-evidence-authority").mkdir(parents=True)

    assert _consumer_importers(tmp_path) == []


# --- the detector itself is tested, because a boundary test that cannot fail is not a
# --- boundary test, and one that fires on a denylist entry blocks correct consumers.

_REAL_IMPORTS = (
    f"import {SELF}",
    f"import {SELF}.contracts",
    f"import {SELF} as tev",
    f"import os, {SELF}",
    f"from {SELF} import canonical_digest",
    f"from {SELF}.contracts import EvidenceObservation",
    f"from {SELF} import (\n    canonical_digest,\n    canonical_bytes,\n)",
    f"from {SELF} import canonical_digest as cd",
    f'importlib.import_module("{SELF}")',
    f'importlib.import_module("{SELF}.contracts")',
    # ``import_module`` bound by its own from-import, then called. The *unbound* form
    # ``import_module("…")`` with no import statement is deliberately absent: it is not
    # executable Python, and treating a bare name as an importer without a binding is the
    # hardcoded-guess behaviour the AST-derived resolution replaced.
    f'from importlib import import_module\nimport_module("{SELF}")',
    f'__import__("{SELF}")',
    # --- F-B: importer aliases resolved from the import statement, not guessed ----------
    f"from importlib import import_module as im\nim(\"{SELF}\")",
    f"from importlib import import_module as load\nload(\"{SELF}\")",
    f"from importlib import import_module as im\nim(\"{SELF}.authority.signing\")",
    f"from importlib import import_module as im\ndef f():\n    return im(\"{SELF}\")",
    f"from importlib import import_module as im\ntry:\n    im(\"{SELF}\")\nexcept ImportError:\n    pass",
    f"from importlib import import_module as z\nif True:\n    z(\"{SELF}\")",
    f"import importlib as il\nil.import_module(\"{SELF}\")",
)

_NOT_IMPORTS = (
    # a forbidden-import denylist — asserting the boundary, not crossing it
    f'FORBIDDEN = ("ugence_policy_authority", "{SELF}")',
    f'FORBIDDEN = {{\n    "{SELF}",\n}}',
    # a negative control that asserts the package is NOT importable
    f'for m in ("symbolu", "{SELF}"):\n'
    f'    try:\n        importlib.import_module(m)\n'
    f'    except ImportError:\n        pass\n'
    f'    else:\n        raise AssertionError(m)',
    # prose and diagnostics
    f'"""This package must never import {SELF}."""',
    f'# {SELF} is deliberately not imported',
    f'raise AssertionError("do not import {SELF}")',
    f'def test_does_not_import_{SELF}():\n    pass',
    f'NAME = "{SELF}"',
    # a similarly-named but different distribution
    f"import {SELF}_extras",
    # --- F-B negatives: the alias resolution must not over-match --------------------------
    # an ordinary function named ``im`` with no importlib alias in the file
    f'def im(x):\n    return x\nim("{SELF}")',
    # a string that merely mentions the importer
    f'MSG = "call import_module({SELF}) is forbidden"',
    # an unrelated module bound to the same short name
    f'import json as im\nim.dumps("{SELF}")',
    # a module name that is not a static string — explicitly out of scope, see _imports_self
    f'from importlib import import_module as im\nname = "{SELF}"\nim(name)',
)


def test_detector_catches_every_real_import_form():
    for source in _REAL_IMPORTS:
        assert _imports_self(ast.parse(source)), f"missed a real import: {source!r}"


def test_detector_ignores_denylists_prose_and_negative_controls():
    for source in _NOT_IMPORTS:
        assert not _imports_self(ast.parse(source)), f"false positive on: {source!r}"


def test_detector_ignores_relative_imports():
    assert not _imports_self(ast.parse("from . import canonical"))
    assert not _imports_self(ast.parse("from .contracts import EvidenceObservation"))
