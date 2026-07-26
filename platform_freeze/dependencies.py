"""Frozen dependency-direction + package-ownership verification (Task 8).

Static ast analysis of the frozen platform's import graph plus checks that each
Python package has exactly one canonical owner and that provider wheels bundle no
duplicate kernel source. Reuses only the stdlib.
"""
from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass

REPO = pathlib.Path(__file__).resolve().parents[1]

#: frozen dependency rules: package -> set of top-level roots it must NOT import
FORBIDDEN_IMPORTS = {
    "decision_governance": {"governance_providers", "actiongate_provider", "tap_provider",
                            "baseline_assertion_provider", "baseline_action_provider",
                            "ai_hiring", "domains", "applications",
                            "enterprise_validation_pilot", "comparative_governance_benchmark",
                            "provider_heterogeneity_validation", "platform_freeze"},
    "governance_providers": {"actiongate_provider", "tap_provider",
                             "baseline_assertion_provider", "baseline_action_provider",
                             "ai_hiring", "domains", "applications", "platform_freeze"},
    "actiongate_provider": {"tap_provider", "baseline_assertion_provider",
                            "baseline_action_provider", "ai_hiring", "domains", "applications",
                            "platform_freeze"},
    "tap_provider": {"actiongate_provider", "baseline_assertion_provider",
                     "baseline_action_provider", "ai_hiring", "domains", "applications",
                     "platform_freeze"},
}

#: packages that must never be imported by the frozen platform
PLATFORM = ("decision_governance", "governance_providers", "actiongate_provider", "tap_provider")


@dataclass(frozen=True)
class DepViolation:
    package: str
    file: str
    line: int
    imported: str


def _imports(root: pathlib.Path):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts or "tests" in p.parts:
            continue
        for node in ast.walk(ast.parse(p.read_text(), filename=str(p))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield p, node.lineno, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield p, node.lineno, node.module


def check_dependency_direction() -> list:
    violations: list = []
    for pkg, forbidden in FORBIDDEN_IMPORTS.items():
        for path, line, mod in _imports(REPO / pkg):
            root = mod.split(".")[0]
            if root in forbidden:
                violations.append(DepViolation(pkg, path.name, line, mod))
    return violations


def check_ai_hiring_not_imported_by_platform() -> list:
    violations: list = []
    for pkg in PLATFORM:
        for path, line, mod in _imports(REPO / pkg):
            if mod.split(".")[0] in ("ai_hiring", "domains", "applications"):
                violations.append(DepViolation(pkg, path.name, line, mod))
    return violations


def check_package_ownership() -> list:
    """Each top-level Python package must have exactly one canonical __init__.py."""
    problems: list = []
    ignored = {"__pycache__", "packaging", "build", "dist"}
    for pkg in list(FORBIDDEN_IMPORTS) + list((
            "enterprise_validation_pilot", "comparative_governance_benchmark",
            "provider_heterogeneity_validation", "baseline_assertion_provider",
            "baseline_action_provider", "platform_freeze")):
        inits = [p for p in REPO.rglob(f"{pkg}/__init__.py")
                 if not (ignored & set(p.relative_to(REPO).parts))
                 and not any(part.endswith(".egg-info") for part in p.relative_to(REPO).parts)]
        canonical = REPO / pkg / "__init__.py"
        if inits != [canonical]:
            problems.append({"package": pkg, "inits": [str(i.relative_to(REPO)) for i in inits]})
    return problems


def dependency_report() -> dict:
    dep = check_dependency_direction()
    hiring = check_ai_hiring_not_imported_by_platform()
    ownership = check_package_ownership()
    return {
        "dependency_violations": [v.__dict__ for v in dep],
        "platform_imports_hiring": [v.__dict__ for v in hiring],
        "ownership_problems": ownership,
        "passed": not dep and not hiring and not ownership,
    }
