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
    "actiongate_provider", "tap_provider",
    # Vendor model SDKs:
    "openai", "anthropic", "mistralai", "transformers", "torch",
    "google", "cohere", "llama_cpp",
    # Databases / infra clients:
    "sqlalchemy", "psycopg2", "psycopg", "pymongo", "redis",
    "kubernetes", "boto3", "google.cloud", "azure",
    # Numerics the wheel must not require:
    "numpy",
}


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


def test_no_forbidden_imports_anywhere_in_core():
    offenders = {}
    for path in _iter_module_files():
        bad = _imported_roots(path) & FORBIDDEN_ROOTS
        if bad:
            offenders[str(path.relative_to(SRC_ROOT))] = sorted(bad)
    assert not offenders, f"forbidden imports found in core: {offenders}"


def test_all_third_party_imports_are_audited():
    """Every non-stdlib, non-relative import root is on the allow-list."""
    import sys

    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    unexpected = {}
    for path in _iter_module_files():
        for root in _imported_roots(path):
            if root in stdlib or root in ALLOWED_RUNTIME_ROOTS:
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
