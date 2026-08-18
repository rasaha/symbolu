"""Dependency direction: this package is a zero-dependency stdlib leaf.

AST-scans every module in ``ugence_trusted_evidence_authority`` and asserts it
imports nothing but the standard library and itself. ADR §23 permits TAP to
depend on ``governance-contracts``; TEV-1 takes the narrower zero-dependency
option (DD-2 is blocked on the shapes TEV-1 produces, so importing that leaf now
would decide DD-2 by implementation).

The reverse direction is asserted too: no package in the monorepo imports this
one. TEV-1 authorizes no consumer integration (ADR §30 — UVI-EV-1 is DEFERRED),
so an import from a consumer would be scope expansion, not convenience.
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
    # third-party
    "pydantic", "numpy", "torch", "pandas", "fastapi", "cryptography", "nacl",
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
    allowed = _STDLIB | {SELF, "__future__"}
    strays = {}
    for path in _sources():
        for root in _roots(path):
            if root not in allowed:
                strays.setdefault(str(path.relative_to(PKG_ROOT)), set()).add(root)
    assert not strays, strays


def test_the_distribution_declares_zero_runtime_dependencies():
    import tomllib

    pyproject = PKG_ROOT.parents[1] / "pyproject.toml"
    if not pyproject.is_file():  # running from an installed wheel
        import importlib.metadata as md

        requires = md.requires("ugence-trusted-evidence-authority") or []
        runtime = [r for r in requires if "extra ==" not in r]
        assert runtime == [], runtime
        return
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == []


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
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue  # not importable Python for this interpreter; nothing to import
        if _imports_self(tree):
            importers.append(str(path.relative_to(repo)))
    assert not importers, (
        "TEV-1 authorizes no consumer integration (ADR §30: UVI-EV-1 DEFERRED); "
        f"unexpected imports: {importers}"
    )


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
