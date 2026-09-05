#!/usr/bin/env python3
"""Report which packages have a test suite that no CI workflow executes.

Twenty-two of sixty-one packages had one when this was written — including every
package of the wave 2 and wave 3 governance programme, and four of the five wave 1
seams. Each was added with its suite passing locally and nothing running it
afterwards, because a new package needs a new workflow and nothing noticed when one
did not arrive.

This closes the class rather than the instances: ``tests/boundaries`` asserts the
report is empty, so the next package added without CI fails the build instead of
drifting for months.

**What counts as executed.** A package is covered when some workflow under
``.github/workflows`` names its directory in a ``pytest`` invocation, ``cd``s into it
before running one, or lists it as a matrix entry. That is deliberately literal — it
does not prove the invocation collects anything, only that the path is named. A
workflow that named a package and then skipped its suite would pass this check,
which is why the report says "named by", not "verified to run". Proving the stronger
property would mean running CI, which is the workflow's job, not this script's.
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
PACKAGES = REPO / "packages"

#: Packages with a suite nothing runs, and a stated reason. Empty by intent: an
#: entry here is a decision somebody has to defend, not a place to park a package.
EXEMPT: dict[str, str] = {}

_PYTEST_PATH = re.compile(r"pytest[^\n|&;]*?(packages/[A-Za-z0-9/_.\-]+)")
_CD_PATH = re.compile(r"cd\s+(packages/[A-Za-z0-9/_.\-]+)")
#: A matrix entry: ``- packages/integration/thing`` on its own line.
_MATRIX_ENTRY = re.compile(r"^\s*-\s+(packages/[A-Za-z0-9/_.\-]+)\s*$", re.MULTILINE)


def _package_root(path: str) -> str:
    """Normalize a path inside a package to the package directory itself."""

    parts = pathlib.PurePosixPath(path).parts
    if len(parts) >= 3 and parts[1] in {
            "capabilities", "integration", "products", "providers", "runtime",
            "tooling"}:
        return "/".join(parts[:3])
    return "/".join(parts[:2])


def packages_with_suites() -> list[str]:
    found = []
    for pyproject in sorted(PACKAGES.rglob("pyproject.toml")):
        package = pyproject.parent
        if (package / "tests").is_dir():
            found.append(package.relative_to(REPO).as_posix())
    return found


def packages_named_by_ci() -> set[str]:
    named: set[str] = set()
    for workflow in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        text = workflow.read_text(encoding="utf-8")
        for match in _PYTEST_PATH.finditer(text):
            named.add(_package_root(match.group(1)))
        for match in _CD_PATH.finditer(text):
            named.add(_package_root(match.group(1)))
        for match in _MATRIX_ENTRY.finditer(text):
            named.add(_package_root(match.group(1)))
    return named


def uncovered() -> list[str]:
    covered = packages_named_by_ci()
    return [p for p in packages_with_suites()
            if p not in covered and p not in EXEMPT]


def main() -> int:
    missing = uncovered()
    total = len(packages_with_suites())
    if not missing:
        print(f"PACKAGE CI COVERAGE OK — all {total} packages with a suite are "
              "named by a workflow")
        return 0
    print(f"{len(missing)} of {total} packages have a test suite no workflow runs:")
    for package in missing:
        print(f"  {package}")
    print("\nAdd the package to a workflow (packages/*/tests must be run by "
          "something), or add it to EXEMPT with a reason.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
