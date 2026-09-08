"""A package README that states a version must state the version it ships.

``packages/capabilities/agent-value-readiness/README.md`` said ``Version: 0.4.0``
while ``__init__.py`` said ``0.4.1``. The package's own ``public_api.json`` had the
right number and its suite was green, because nothing compared the two: the
repository's one documentation-drift gate
(``tests/test_readiness_governed_value_doc_drift.py``) covers the readiness/ROI
explainer, not package READMEs.

This closes the class rather than the instance, in the manner of
``test_package_ci_coverage.py``: every package README that states a version at all
is compared against the version its distribution declares. A README that states no
version is not in scope — the gate checks agreement, it does not mandate the line.

Versions are read from source with a regex rather than by importing the packages.
Importing all of them would need each one's ``src`` tree and first-party
dependencies on ``sys.path`` — the very thing each package's own ``conftest.py``
exists to arrange — and would make a repository-wide gate fail for reasons that
have nothing to do with a version string.
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
PACKAGES = REPO / "packages"

#: ``- **Version:** 0.4.1`` / ``- **Version:** `0.3.0` `` / ``**Version:** 2.0.0``,
#: optionally followed by ``·`` and further facts the gate does not read.
_README_VERSION = re.compile(
    r"^\s*[-*]?\s*\*\*Version:\*\*\s*`?(?P<version>\d+\.\d+\.\d+[^\s`]*)`?",
    re.MULTILINE,
)
#: ``version = { attr = "pkg.version.__version__" }`` under ``[tool.setuptools.dynamic]``.
_DYNAMIC_ATTR = re.compile(r"""version\s*=\s*\{\s*attr\s*=\s*["'](?P<attr>[^"']+)["']""")
#: A statically declared ``version = "1.2.3"`` in ``[project]``.
_STATIC_VERSION = re.compile(r"""^version\s*=\s*["'](?P<version>[^"']+)["']""", re.MULTILINE)
_DUNDER_VERSION = re.compile(r"""^__version__\s*=\s*["'](?P<version>[^"']+)["']""", re.MULTILINE)


def _declared_version(package: pathlib.Path) -> str | None:
    """The version the distribution declares, or ``None`` if it cannot be read."""

    pyproject = package / "pyproject.toml"
    if not pyproject.is_file():
        return None
    text = pyproject.read_text(encoding="utf-8")

    attr = _DYNAMIC_ATTR.search(text)
    if attr is None:
        static = _STATIC_VERSION.search(text)
        return static.group("version") if static else None

    # ``pkg.__version__`` lives in ``src/pkg/__init__.py``;
    # ``pkg.version.__version__`` lives in ``src/pkg/version.py``.
    parts = attr.group("attr").split(".")
    if parts[-1] != "__version__" or len(parts) < 2:
        return None
    module = parts[:-1]
    source = package / "src" / pathlib.Path(*module[:-1]) / f"{module[-1]}.py"
    if len(module) == 1:
        source = package / "src" / module[0] / "__init__.py"
    if not source.is_file():
        return None
    found = _DUNDER_VERSION.search(source.read_text(encoding="utf-8"))
    return found.group("version") if found else None


def _readmes_stating_a_version():
    for readme in sorted(PACKAGES.rglob("README.md")):
        # Build trees are artifacts, not sources; a stale copy there is not drift.
        if "build" in readme.relative_to(PACKAGES).parts:
            continue
        package = readme.parent
        if not (package / "pyproject.toml").is_file():
            continue
        stated = _README_VERSION.search(readme.read_text(encoding="utf-8"))
        if stated is not None:
            yield readme, stated.group("version")


class PackageReadmeVersionTest(unittest.TestCase):
    def test_every_stated_readme_version_matches_the_distribution(self):
        checked = 0
        for readme, stated in _readmes_stating_a_version():
            declared = _declared_version(readme.parent)
            if declared is None:
                continue
            checked += 1
            self.assertEqual(
                stated,
                declared,
                f"\n{readme.relative_to(REPO)} states version {stated!r}, but "
                f"{readme.parent.relative_to(REPO)} declares {declared!r}.\n"
                "Update the README — a version a reader cannot trust is worse "
                "than one the README never states.",
            )
        # A regex that silently stopped matching would make this gate vacuous.
        self.assertGreater(checked, 0, "no package README stated a readable version")


if __name__ == "__main__":
    unittest.main()
