"""Make this package, its dependencies and the sibling test harnesses importable in a
bare source checkout, mirroring the sibling integration packages' convention.

The matrix rows reuse the durable-execution package's real-PostgreSQL harness and the
governed-review package's fixtures rather than inventing new ones.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parents[2]

DE_TESTS = REPO / "packages" / "integration" / "durable-execution" / "tests"
GR_TESTS = REPO / "packages" / "integration" / "governed-review" / "tests"

for path in (
    PKG / "src",
    REPO / "packages" / "integration" / "governed-review" / "src",
    REPO / "packages" / "integration" / "approval-workflow" / "src",
    REPO / "packages" / "integration" / "authority-directory" / "src",
    REPO / "packages" / "governance-contracts" / "src",
    REPO / "packages" / "integration" / "agent-runtime-governance" / "src",
    REPO / "packages" / "integration" / "risk-authority-runtime" / "src",
    REPO / "packages" / "integration" / "risk-authority-status-runtime" / "src",
    REPO / "packages" / "runtime" / "agent-runtime" / "src",
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "capabilities" / "decision-authority" / "src",
    REPO / "packages" / "providers" / "actiongate" / "src",
    REPO / "packages" / "integration" / "durable-execution" / "src",
    DE_TESTS,
    GR_TESTS,
    HERE,
):
    p = str(path)
    if path.is_dir() and p not in sys.path:
        sys.path.insert(0, p)


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


try:
    _de_conftest = _load("de_conftest", DE_TESTS / "conftest.py")
    pg_databases = _de_conftest.pg_databases
    requires_postgres = _de_conftest.requires_postgres
    postgres_available = _de_conftest.postgres_available
except Exception as exc:  # noqa: BLE001 - surfaced by the rows that need it
    import pytest

    _reason = f"durable-execution harness unavailable: {exc}"
    requires_postgres = pytest.mark.skip(reason=_reason)
    postgres_available = lambda: False  # noqa: E731

    @pytest.fixture()
    def pg_databases():
        pytest.skip(_reason)
