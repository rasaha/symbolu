#!/usr/bin/env python3
"""Report packages with no LICENSE file, or one that contradicts their metadata.

Thirty-two of seventy-two packages had no LICENSE file when this was written, while
all seventy-two declared ``license = { text = "Proprietary" }`` in their
``pyproject.toml``. The declaration was uniform and the files were not, so the split
carried no information: a package with the file and a package without it were saying
exactly the same thing about their licensing, and the presence of the file recorded
only whether whoever added the package happened to copy one in.

The thirty-two were normalized before this gate was added, deliberately in that
order. A gate introduced midway through a migration is a gate that fails on work
nobody has done yet, which teaches everyone to ignore it.

**What is checked, and what is not.** Two things: that every package with a
``pyproject.toml`` has a ``LICENSE`` beside it, and that the file's first non-empty
line begins with the license its metadata declares. That is a consistency check
between two statements the repository already makes — it is not a legal review, and
it does not decide what the license should be.

**Why not byte-equality.** Five distinct LICENSE texts exist across the tree, from a
bare ``Proprietary`` to a twelve-line proprietary notice with a copyright line and a
redistribution clause. All five name the same license; they differ in how much they
say about it. Normalizing that wording is a separate decision from requiring the
file to exist and agree with the metadata, and it is not one this script makes: a
package may say more than ``Proprietary``, but it may not say something else.
"""

from __future__ import annotations

import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 — the backport, as the workflows install it.
    import tomli as tomllib  # type: ignore[no-redef]

REPO = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = REPO / "packages"

#: Packages exempt from the license gate, and a stated reason. Empty by intent: an
#: entry here is a decision somebody has to defend, not a place to park a package.
EXEMPT: dict[str, str] = {}


def _declared_license(pyproject: pathlib.Path) -> str | None:
    """The license text a package's metadata declares, or None if it declares none."""
    project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
    declared = project.get("license")
    if isinstance(declared, dict):
        # PEP 621 allows either an inline text or a path to a file.
        return declared.get("text") or declared.get("file")
    return declared


def _first_meaningful_line(path: pathlib.Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            return line.strip()
    return ""


def violations() -> list[tuple[str, str]]:
    """Every (package, reason) pair failing the gate, sorted by package path."""
    found: list[tuple[str, str]] = []
    for pyproject in sorted(PACKAGES.rglob("pyproject.toml")):
        package = pyproject.parent
        try:
            relative = package.relative_to(REPO).as_posix()
        except ValueError:
            # PACKAGES was repointed outside the repository — the failure-mode test
            # does exactly this. Name the package by its path under whatever root is
            # in force rather than crashing on the repo-relative assumption.
            relative = package.relative_to(PACKAGES).as_posix()
        if relative in EXEMPT:
            continue

        declared = _declared_license(pyproject)
        if not declared:
            found.append((relative, "pyproject.toml declares no license"))
            continue

        license_file = package / "LICENSE"
        if not license_file.exists():
            found.append((relative, f"no LICENSE file (metadata declares {declared!r})"))
            continue

        first = _first_meaningful_line(license_file)
        if not first.startswith(declared):
            found.append((
                relative,
                f"LICENSE begins {first[:50]!r}, which does not match the "
                f"declared license {declared!r}",
            ))
    return found


def main() -> int:
    failures = violations()
    total = len(list(PACKAGES.rglob("pyproject.toml")))
    if not failures:
        print(f"PACKAGE LICENSE OK — all {total} packages ship a LICENSE consistent "
              "with their pyproject.toml")
        return 0
    print(f"{len(failures)} of {total} packages fail the license gate:")
    for package, reason in failures:
        print(f"  {package} — {reason}")
    print("\nAdd a LICENSE naming the license the package's pyproject.toml declares, "
          "or add the package to EXEMPT with a reason.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
