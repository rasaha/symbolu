"""AI-Hiring re-entry discovery (Task 12) — resolves paths + integration facts.

Provider-neutral, read-only discovery used by the re-entry baseline and its tests.
Resolves actual repository paths rather than assuming them, and reports whether the
hiring layer currently uses the provider framework.
"""
from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
_HIRING_ROOTS = ("ai_hiring", "domains/hiring", "applications/ai_hiring")
_PROVIDERS = ("tap_provider", "actiongate_provider", "governance_providers")


def _imports(root: pathlib.Path):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        try:
            tree = ast.parse(p.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield node.module


def discover_hiring() -> dict:
    present = {r: (REPO / r).exists() for r in _HIRING_ROOTS}
    uses_providers = {}
    for r in _HIRING_ROOTS:
        root = REPO / r
        mods = set(_imports(root)) if root.exists() else set()
        uses_providers[r] = sorted({m.split(".")[0] for m in mods} & set(_PROVIDERS))
    any_provider = any(uses_providers.values())
    uses_kernel = any(
        m.split(".")[0] == "decision_governance"
        for r in _HIRING_ROOTS if (REPO / r).exists()
        for m in _imports(REPO / r))
    return {
        "roots": _HIRING_ROOTS,
        "present": present,
        "primary_package": "ai_hiring",
        "uses_provider_framework": any_provider,
        "provider_imports_by_root": uses_providers,
        "uses_dgm_kernel": uses_kernel,
        "independently_packaged": (REPO / "packaging" / "dgm-ai-hiring").exists(),
    }
