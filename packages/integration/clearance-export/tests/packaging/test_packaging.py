"""Distribution metadata: the dependency is one, and it is the ruled one.

CE-2 forbids extending action-clearance and gives this package no store. Both show
up here as facts about the metadata: exactly one declared dependency, and it is the
evaluator package whose frozen receipt type CE-1 requires — not the package that
persists receipts, which would smuggle a store in through the dependency graph.
"""

from __future__ import annotations

import pathlib

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[2]

try:  # Python 3.11+ ships tomllib; 3.10 resolves the same parser from tomli.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only a <3.11 run takes this branch
    import tomli as tomllib  # type: ignore[no-redef]


def _metadata() -> dict:
    return tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _names(requirements) -> set[str]:
    return {r.split(">")[0].split("=")[0].split("[")[0].strip() for r in requirements}


def test_the_distribution_is_named_as_the_ruling_named_it():
    assert _metadata()["project"]["name"] == "ugence-clearance-export"


def test_exactly_one_dependency_and_it_is_action_clearance():
    assert _names(_metadata()["project"]["dependencies"]) == {"ugence-action-clearance"}


def test_the_receipt_store_is_not_a_dependency():
    """ugence-execution-reservation persists receipts. Depending on it would give
    this package a store through the back door, which CE-2 forbids."""
    declared = _names(_metadata()["project"]["dependencies"])
    optional = _metadata()["project"].get("optional-dependencies", {})
    for requirements in optional.values():
        declared |= _names(requirements)
    assert "ugence-execution-reservation" not in declared
    assert "ugence-control-plane-root" not in declared


def test_the_distribution_ships_the_namespace_and_only_that():
    find = _metadata()["tool"]["setuptools"]["packages"]["find"]
    assert find["where"] == ["src"]
    assert find["include"] == ["ugence_clearance_export*"]


def test_the_version_is_read_statically_from_the_version_module():
    metadata = _metadata()
    assert metadata["project"]["dynamic"] == ["version"]
    assert metadata["tool"]["setuptools"]["dynamic"]["version"]["attr"] == (
        "ugence_clearance_export.version.__version__")


def test_the_readme_states_the_posture():
    readme = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "contracts only" in readme
    assert "never clears" in readme
    assert "synthetic_demonstration_only" in readme
    assert "unsigned" in readme
    assert "presented_unproven" in readme
