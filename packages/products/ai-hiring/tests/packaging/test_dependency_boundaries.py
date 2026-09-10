"""AST dependency-boundary tests — the independence proof.

Statically scan every module in the canonical ``ugence_ai_hiring`` package and
assert its import graph never reaches outside the audited dependency set. This is
what makes the wheel genuinely independent rather than a copy that still leans on
the monorepo.
"""

from __future__ import annotations

import ast
import pathlib

import ugence_ai_hiring

PKG_ROOT = pathlib.Path(ugence_ai_hiring.__file__).resolve().parent
SRC_ROOT = PKG_ROOT.parent  # the src/ directory (contains ugence_ai_hiring + ai_hiring facade)

# Third-party / Ugence roots the CORE is allowed to import.
ALLOWED_RUNTIME_ROOTS = {
    "pydantic",
    "ugence_decision_authority",
    "ugence_governance_provider_framework",
    "ugence_governance_contracts",
    # Optional integration, gated behind the ``api`` extra (imported lazily):
    "fastapi",
    "starlette",
    "uvicorn",
    # Self.
    "ugence_ai_hiring",
}

# Roots that must NEVER be imported by the canonical package (monorepo internals,
# legacy compat namespaces, vendor model SDKs, DB drivers, cloud/k8s clients).
FORBIDDEN_ROOTS = {
    # Monorepo internals / sibling products:
    "symbolu", "agentic", "cloud_controller", "hybrid_llm_vnext_lab",
    "experiments", "bounded_shadow_pilot", "evidence_assurance",
    "applications", "domains",
    # Legacy compat namespaces — the core must import the CANONICAL packages,
    # not the repo-root shims (which do not ship in the wheel):
    "decision_governance", "governance_providers",
    # Vendor model SDKs:
    "openai", "anthropic", "mistralai", "transformers", "torch",
    "google", "cohere", "llama_cpp",
    # Databases / infra clients:
    "sqlalchemy", "psycopg2", "psycopg", "pymongo", "redis",
    "kubernetes", "boto3", "google.cloud", "azure",
    # Numerics the wheel must not require:
    "numpy",
}

# Canonical TAP / ActionGate providers. Classification:
# OPTIONAL_CANONICAL_ADAPTER — permitted ONLY inside the isolated, optional
# ``integrations/`` subpackage (lazy-imported there); FORBIDDEN_CORE_DEPENDENCY
# everywhere else in the package.
CANONICAL_PROVIDER_ROOTS = {"ugence_tap_provider", "ugence_actiongate_provider"}

# Legacy provider namespaces. After canonical normalization AI Hiring targets the
# canonical namespaces directly, so the legacy ``tap_provider`` /
# ``actiongate_provider`` compatibility namespaces must NOT be imported anywhere in
# the production package (not even in integrations/). They remain valid only in
# retained compatibility documentation and tests.
LEGACY_PROVIDER_ROOTS = {"tap_provider", "actiongate_provider"}

# Internal modules quarantined from the rest of the package, each mapped to the
# module paths permitted to import it. Paths are dotted and relative to
# ``ugence_ai_hiring``; an empty set means nothing in the package may import it.
#
# These are intra-package edges, so ``_imported_roots`` cannot see them: it skips
# relative imports and keeps only the first segment of absolute ones.
# ``_internal_targets`` below resolves both forms to a dotted module path.
QUARANTINED_INTERNAL_MODULES: dict[str, frozenset[str]] = {
    # Overall Fit is analytics, not policy. The decision plane derives eligibility
    # from gates alone, so nothing may bind the analytics path at import time: the
    # plane can then be read, reasoned about and shipped without it.
    "hiring_decision.analytics": frozenset(),
}

INTEGRATIONS_DIR = PKG_ROOT / "integrations"


def _is_integrations(path: pathlib.Path) -> bool:
    return INTEGRATIONS_DIR in path.parents


def _iter_module_files():
    for p in PKG_ROOT.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def _imported_roots(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import — internal, always fine
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _module_path(path: pathlib.Path) -> str:
    """Dotted path of ``path`` within the package, e.g. ``hiring_decision.gates``."""
    rel = path.relative_to(PKG_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_internal_targets(source: str, module_path: str, is_package_init: bool) -> set[str]:
    """Intra-package module paths ``source`` imports, by relative or absolute form.

    ``from . import analytics``, ``from .analytics import x``,
    ``from ugence_ai_hiring.hiring_decision import analytics`` and
    ``import ugence_ai_hiring.hiring_decision.analytics`` all resolve to
    ``hiring_decision.analytics``. A ``from pkg import name`` is ambiguous — ``name``
    may be a submodule or a symbol re-exported by it — so both readings are
    reported; either one binds the module at import time, which is what matters.

    Pure: takes source text and a position, touches no filesystem, so the form
    coverage below can exercise it on synthetic modules without writing into the
    package tree.
    """
    own_parts = module_path.split(".") if module_path else []
    # A relative import counts levels from the *package* containing the module. For
    # a package's own __init__.py that package is itself; for any other module it is
    # the parent. Conflating the two shifts every relative import by one level.
    pkg_parts = own_parts if is_package_init else own_parts[:-1]
    tree = ast.parse(source)
    targets: set[str] = set()

    def _add(dotted: str, names: list[str]) -> None:
        if dotted:
            targets.add(dotted)
        targets.update(f"{dotted}.{n}" if dotted else n for n in names)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "ugence_ai_hiring":
                    continue
                if alias.name.startswith("ugence_ai_hiring."):
                    targets.add(alias.name[len("ugence_ai_hiring.") :])
        elif isinstance(node, ast.ImportFrom):
            names = [a.name for a in node.names if a.name != "*"]
            if node.level:
                if node.level - 1 > len(pkg_parts):
                    continue  # escapes the package entirely
                base = pkg_parts[: len(pkg_parts) - (node.level - 1)]
                prefix = ".".join(base + (node.module.split(".") if node.module else []))
                _add(prefix, names)
            elif node.module == "ugence_ai_hiring":
                _add("", names)
            elif node.module and node.module.startswith("ugence_ai_hiring."):
                _add(node.module[len("ugence_ai_hiring.") :], names)
    return targets


def _internal_targets(path: pathlib.Path) -> set[str]:
    """``_resolve_internal_targets`` for a real module file in the package."""
    return _resolve_internal_targets(
        path.read_text(), _module_path(path), path.name == "__init__.py"
    )


def test_quarantined_internal_modules_are_not_imported():
    """Each quarantined internal module is imported only by its permitted importers.

    This is the declarative form of the plane-isolation constraint. It is a static
    scan of every module in the package, so it holds regardless of test ordering,
    of what else is installed, and of which planes a given run happens to import.
    """
    offenders: dict[str, list[str]] = {}
    for path in _iter_module_files():
        importer = _module_path(path)
        targets = _internal_targets(path)
        for quarantined, permitted in QUARANTINED_INTERNAL_MODULES.items():
            if quarantined == importer or importer in permitted:
                continue
            if quarantined in targets:
                offenders.setdefault(quarantined, []).append(importer)
    assert not offenders, f"quarantined internal modules imported: {offenders}"


def test_the_quarantine_map_is_deliberate():
    """The quarantine map is pinned, so emptying it is a visible edit, not a drift.

    A rule table that can be silently emptied is a gate that stops gating without
    anything going red. This names what the map must contain; removing an entry
    means changing this test too, which is a decision a reviewer can see.
    """
    assert "hiring_decision.analytics" in QUARANTINED_INTERNAL_MODULES
    assert QUARANTINED_INTERNAL_MODULES["hiring_decision.analytics"] == frozenset()


def test_the_quarantine_resolver_sees_every_import_form():
    """``_internal_targets`` resolves relative and absolute forms alike.

    The resolver is the whole rule: a form it cannot see is a boundary that is not
    enforced, silently. Relative levels are counted from the package containing the
    module, which differs between a package's ``__init__.py`` and any other module,
    so both are exercised here.
    """
    # (module position, is __init__.py, import statement)
    forms = (
        ("hiring_decision", True, "from . import analytics"),
        ("hiring_decision.gates", False, "from .analytics import compute_overall_fit"),
        ("hiring_decision.gates", False,
         "from ugence_ai_hiring.hiring_decision import analytics"),
        ("hiring_decision.gates", False,
         "import ugence_ai_hiring.hiring_decision.analytics"),
        ("hiring_decision.gates", False,
         "from ugence_ai_hiring.hiring_decision.analytics import compute_overall_fit"),
        ("hiring_calibration.report", False, "from ..hiring_decision import analytics"),
        ("hiring_calibration.report", False,
         "from ..hiring_decision.analytics import compute_overall_fit"),
    )
    for module_path, is_init, statement in forms:
        targets = _resolve_internal_targets(statement + "\n", module_path, is_init)
        assert "hiring_decision.analytics" in targets, (module_path, statement, sorted(targets))

    # …and does not report it for an import that does not reach it, so the coverage
    # above is not just a function that says yes to everything.
    assert "hiring_decision.analytics" not in _resolve_internal_targets(
        "from .gates import MandatoryGateEvaluator\n", "hiring_decision.eligibility", False
    )


def test_no_forbidden_imports_anywhere_in_core():
    offenders = {}
    for path in _iter_module_files():
        roots = _imported_roots(path)
        bad = set(roots & FORBIDDEN_ROOTS)
        # The legacy provider namespaces are FORBIDDEN everywhere in the production
        # package — AI Hiring targets the canonical namespaces directly.
        bad |= roots & LEGACY_PROVIDER_ROOTS
        # The canonical concrete providers are FORBIDDEN in the core; permitted only
        # in the isolated optional integrations/ subpackage.
        if not _is_integrations(path):
            bad |= roots & CANONICAL_PROVIDER_ROOTS
        if bad:
            offenders[str(path.relative_to(SRC_ROOT))] = sorted(bad)
    assert not offenders, f"forbidden imports found in core: {offenders}"


def test_concrete_tap_actiongate_only_in_integrations():
    """The concrete canonical TAP/ActionGate providers are referenced ONLY in integrations/.

    Enforces the boundary: ugence_tap_provider / ugence_actiongate_provider are an
    OPTIONAL_CANONICAL_ADAPTER dependency confined to the optional adapter
    subpackage, never a core dependency.
    """
    leaks = {}
    for path in _iter_module_files():
        if _is_integrations(path):
            continue
        hit = _imported_roots(path) & CANONICAL_PROVIDER_ROOTS
        if hit:
            leaks[str(path.relative_to(SRC_ROOT))] = sorted(hit)
    assert not leaks, f"concrete TAP/ActionGate referenced outside integrations/: {leaks}"


def test_no_legacy_provider_namespace_imported_anywhere():
    """The legacy tap_provider / actiongate_provider namespaces are imported nowhere.

    §21: production AI Hiring code must directly target the canonical namespaces;
    ``import tap_provider`` / ``from actiongate_provider ...`` are forbidden across
    the whole package, including the integrations/ adapters.
    """
    leaks = {}
    for path in _iter_module_files():
        hit = _imported_roots(path) & LEGACY_PROVIDER_ROOTS
        if hit:
            leaks[str(path.relative_to(SRC_ROOT))] = sorted(hit)
    assert not leaks, f"legacy provider namespace imported in production code: {leaks}"


def test_all_third_party_imports_are_audited():
    """Every non-stdlib, non-relative import root is on the allow-list."""
    import sys

    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    unexpected = {}
    for path in _iter_module_files():
        allowed = set(ALLOWED_RUNTIME_ROOTS)
        # Canonical providers are an audited OPTIONAL_CANONICAL_ADAPTER dependency
        # only in the integrations/ subpackage.
        if _is_integrations(path):
            allowed |= CANONICAL_PROVIDER_ROOTS
        for root in _imported_roots(path):
            if root in stdlib or root in allowed:
                continue
            # __future__ and common builtins-adjacent roots
            if root in {"__future__"}:
                continue
            unexpected.setdefault(root, []).append(
                str(path.relative_to(SRC_ROOT))
            )
    assert not unexpected, f"un-audited third-party imports: {list(unexpected)}"


def test_no_vendor_model_sdk_hard_import_on_package_import():
    """Importing the package must not pull in any vendor model SDK."""
    import importlib
    import sys

    for sdk in ("openai", "anthropic", "mistralai", "torch", "transformers"):
        # Not already imported as a side effect of importing ugence_ai_hiring.
        assert sdk not in sys.modules, f"{sdk} imported as a side effect"

    # And the package itself imports cleanly with no such SDK installed.
    importlib.import_module("ugence_ai_hiring")


def test_core_import_requires_no_database_driver():
    import sys

    for drv in ("sqlalchemy", "psycopg2", "psycopg", "pymongo", "redis"):
        assert drv not in sys.modules, f"{drv} imported as a side effect"
