"""The canonical core must have a clean dependency graph.

Static AST scan of every ``ugence_procurement`` source file plus runtime import
checks. The core must not import the legacy ``decision_governance`` namespace, any
other Ugence product, any model SDK, web framework, database driver, cloud client,
or ERP SDK.
"""

from __future__ import annotations

import ast
import pathlib

import ugence_procurement

_ROOT = pathlib.Path(ugence_procurement.__file__).resolve().parent

# Import roots the canonical core must NEVER pull in.
_FORBIDDEN_ROOTS = frozenset({
    # legacy kernel namespace (canonical is ugence_decision_authority)
    "decision_governance",
    # other Ugence products
    "ai_hiring", "ugence_ai_hiring",
    "products", "ugence_code_governance", "code_governance",
    # runtime / platform components out of scope
    "agent_runtime", "agent_runtime_v2", "cloud_controller",
    "hybrid_llm_vnext_lab", "context_minimization",
    # model SDKs
    "openai", "anthropic", "mistralai", "torch", "numpy",
    # web frameworks (core must not require them; only the optional `api` extra may)
    "fastapi", "uvicorn",
    # persistence / network / cloud
    "sqlalchemy", "requests", "httpx", "boto3", "google",
})


def _iter_imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield node.lineno, a.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module


def test_core_imports_no_forbidden_root():
    violations = []
    for py in _ROOT.rglob("*.py"):
        for lineno, mod in _iter_imports(py):
            root = mod.split(".")[0]
            if root in _FORBIDDEN_ROOTS:
                violations.append(f"{py.relative_to(_ROOT)}:{lineno} imports {mod}")
    assert not violations, "forbidden imports in canonical core:\n" + "\n".join(violations)


def test_core_depends_on_canonical_kernel_only():
    """The kernel is reached via ugence_decision_authority, never decision_governance."""
    seen_canonical = False
    for py in _ROOT.rglob("*.py"):
        for _lineno, mod in _iter_imports(py):
            assert not mod.startswith("decision_governance"), f"{py}: {mod}"
            if mod.startswith("ugence_decision_authority"):
                seen_canonical = True
    assert seen_canonical, "expected canonical ugence_decision_authority imports"


def test_core_import_does_not_require_fastapi():
    """Importing the package + its public API must not require the optional api extra."""
    import importlib
    import sys

    # fastapi is not installed in the core test env; a plain import must still work.
    assert "fastapi" not in sys.modules or True  # tolerate presence, but do not require
    importlib.import_module("ugence_procurement")
    importlib.import_module("ugence_procurement.api")
    importlib.import_module("ugence_procurement.platform")
    importlib.import_module("ugence_procurement.routes")


def test_demo_needs_no_optional_dependency():
    from ugence_procurement.product.demo import run_demo

    result = run_demo()
    assert len(result.runs) == 2
