"""Make this package, its dependencies and the durable-execution test harness importable
in a bare source checkout, mirroring the sibling integration packages' convention.

The matrix rows reuse the durable-execution package's real-PostgreSQL harness rather
than inventing a second one; that module lives in the sibling's tests directory.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PKG = HERE.parent
# packages/integration/governed-review -> packages/integration -> packages -> repo
REPO = PKG.parents[2]

DE_TESTS = REPO / "packages" / "integration" / "durable-execution" / "tests"

for path in (
    PKG / "src",
    REPO / "packages" / "integration" / "approval-workflow" / "src",
    REPO / "packages" / "integration" / "authority-directory" / "src",
    REPO / "packages" / "governance-contracts" / "src",
    REPO / "packages" / "integration" / "agent-runtime-governance" / "src",
    REPO / "packages" / "integration" / "risk-authority-runtime" / "src",
    REPO / "packages" / "integration" / "risk-authority-status-runtime" / "src",
    REPO / "packages" / "runtime" / "agent-runtime" / "src",
    # Transitive, import-time dependencies of the risk-authority contracts module.
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "capabilities" / "decision-authority" / "src",
    REPO / "packages" / "providers" / "actiongate" / "src",
    REPO / "packages" / "integration" / "durable-execution" / "src",
    DE_TESTS,
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


# The durable-execution conftest owns the real-PostgreSQL fixtures. It is loaded under
# its own name (a second module called ``conftest`` would shadow this one) and its
# fixture objects are re-exported so pytest discovers them here.
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
