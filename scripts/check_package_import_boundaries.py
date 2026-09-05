#!/usr/bin/env python3
"""Repository-wide package import-boundary validation.

Closes the gap every wave 2 and wave 3 package README states but none can test:
a package can assert what *it* imports, never what imports *it*. That is a claim
about the whole repository, so it is checked here.

Both rules are **derived from the repository**, not from a hand-maintained list,
so a new package is governed the moment it exists:

**Rule 1 — layering.** `packages/integration/*` composes; `packages/capabilities/*`
and the leaf packages at `packages/*` are composed. So a capability or a leaf may
never import an integration package. Composition roots, products, applications and
other integration packages may. This is the rule the wave 2 and 3 READMEs state as
"no capability package may import it".

**Rule 2 — declared dependency.** Every first-party package a module imports **at
module scope** must be declared in that package's ``pyproject.toml`` dependencies.
Undeclared module-scope coupling is how a leaf silently stops being a leaf.

Only module-scope imports bind at import time. A function-local import is this
repository's established optional-dependency idiom — see
``policy-workflow-compiler/.../reference/procurement_equivalence.py:112`` and
``ai-hiring/.../integrations/`` — and is deliberately not treated as a dependency.
Imports inside ``if TYPE_CHECKING:`` or ``try:`` blocks at module scope *are*
counted: they name a real coupling a reader must be able to find in the manifest.

What this does NOT do: it reads source and manifests only. It imports nothing,
installs nothing, and executes no package code, so it cannot be defeated by a
side effect and needs no dependency to be present.

Exit code 0 = no violations; 1 = one or more violations.

Usage:  python scripts/check_package_import_boundaries.py [--repo-root PATH] [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys
import tomllib
from dataclasses import dataclass, field
from typing import Iterable, Optional

#: Layer directories under ``packages/``. A package directly under ``packages/``
#: (no layer directory) is a *leaf*: the contract packages everything else builds on.
LEAF_LAYER = "leaf"

#: Layers that compose. Nothing below them in the list may import them.
COMPOSING_LAYERS = ("integration",)

#: Layers that are composed and must therefore never import a composing layer.
COMPOSED_LAYERS = ("capabilities", LEAF_LAYER)


@dataclass(frozen=True)
class Package:
    """One distribution in the monorepo, as its manifest and source describe it."""

    directory: pathlib.Path
    distribution: str
    layer: str
    namespaces: frozenset[str]
    declared_distributions: frozenset[str]

    @property
    def name(self) -> str:
        return self.directory.name


@dataclass(frozen=True)
class Violation:
    rule: str
    package: str
    source: str
    line: int
    imported: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.source}:{self.line}: {self.detail}"


@dataclass
class Report:
    packages: list[Package] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    #: namespace -> distribution, for every first-party namespace found.
    namespace_owner: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.violations


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def _requirement_name(requirement: str) -> str:
    """The distribution name from a PEP 508 requirement string."""

    return re.split(r"[<>=!~\[; ]", requirement.strip())[0].strip()


def discover_packages(repo_root: pathlib.Path) -> list[Package]:
    """Every ``packages/**`` distribution that ships a ``src/`` layout."""

    packages_root = repo_root / "packages"
    found: list[Package] = []
    for manifest in sorted(packages_root.rglob("pyproject.toml")):
        directory = manifest.parent
        src = directory / "src"
        if not src.is_dir():
            continue
        try:
            project = tomllib.loads(manifest.read_text(encoding="utf-8")).get("project", {})
        except tomllib.TOMLDecodeError:
            continue
        distribution = project.get("name")
        if not distribution:
            continue
        namespaces = frozenset(
            child.name for child in src.iterdir()
            if child.is_dir() and (child / "__init__.py").is_file())
        if not namespaces:
            continue
        relative = directory.relative_to(packages_root).parts
        layer = relative[0] if len(relative) > 1 else LEAF_LAYER
        declared = frozenset(
            _requirement_name(r) for r in (project.get("dependencies") or []))
        found.append(Package(directory=directory, distribution=distribution, layer=layer,
                             namespaces=namespaces, declared_distributions=declared))
    return found


def module_scope_imports(path: pathlib.Path) -> Iterable[tuple[str, int]]:
    """Root package names imported at module scope, with line numbers.

    Module scope includes ``if TYPE_CHECKING:`` and ``try:`` blocks — those name a
    real coupling — but not imports inside a function or method, which are this
    repository's optional-dependency idiom and bind nothing at import time.
    """

    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError:
        return ()

    seen: list[tuple[str, int]] = []

    def collect(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            seen.extend((alias.name.split(".")[0], node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            seen.append((node.module.split(".")[0], node.lineno))

    for statement in tree.body:
        if isinstance(statement, (ast.If, ast.Try)):
            for nested in ast.walk(statement):
                collect(nested)
        else:
            collect(statement)
    return seen


# --------------------------------------------------------------------------- #
# The rules
# --------------------------------------------------------------------------- #
def check(repo_root: pathlib.Path) -> Report:
    report = Report(packages=discover_packages(repo_root))
    owner: dict[str, Package] = {}
    for package in report.packages:
        for namespace in package.namespaces:
            owner[namespace] = package
    report.namespace_owner = {ns: pkg.distribution for ns, pkg in owner.items()}

    for package in report.packages:
        declared_namespaces = {
            namespace
            for distribution in package.declared_distributions
            for other in report.packages if other.distribution == distribution
            for namespace in other.namespaces
        }
        for source in sorted((package.directory / "src").rglob("*.py")):
            if "__pycache__" in source.parts:
                continue
            for root, line in module_scope_imports(source):
                imported = owner.get(root)
                if imported is None or imported is package:
                    continue  # third-party, stdlib, or the package's own namespace
                where = str(source.relative_to(repo_root))

                if (package.layer in COMPOSED_LAYERS
                        and imported.layer in COMPOSING_LAYERS):
                    report.violations.append(Violation(
                        rule="layering", package=package.name, source=where, line=line,
                        imported=root,
                        detail=(f"{package.layer} package '{package.name}' imports "
                                f"{imported.layer} package '{imported.name}' ({root}). "
                                "Integration packages compose capabilities and leaves; "
                                "the dependency may not run the other way.")))

                if root not in declared_namespaces:
                    report.violations.append(Violation(
                        rule="undeclared-dependency", package=package.name, source=where,
                        line=line, imported=root,
                        detail=(f"'{package.name}' imports '{root}' at module scope but "
                                f"does not declare '{imported.distribution}' in its "
                                "pyproject dependencies.")))
    return report


# --------------------------------------------------------------------------- #
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=None,
                        help="repository root (default: the parent of this script's directory)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args(argv)

    repo_root = (pathlib.Path(args.repo_root).resolve() if args.repo_root
                 else pathlib.Path(__file__).resolve().parents[1])
    report = check(repo_root)

    if args.json:
        print(json.dumps({
            "packages": len(report.packages),
            "namespaces": len(report.namespace_owner),
            "violations": [v.__dict__ for v in report.violations],
        }, indent=2, sort_keys=True))
    else:
        print(f"scanned {len(report.packages)} packages, "
              f"{len(report.namespace_owner)} first-party namespaces")
        if report.ok:
            print("PACKAGE IMPORT BOUNDARIES OK — no layering or undeclared-dependency violations")
        else:
            print(f"{len(report.violations)} violation(s):")
            for violation in report.violations:
                print(f"  {violation}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
