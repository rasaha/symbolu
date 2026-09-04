"""Import boundary, clock-free rule, dependency set, production refusal, surface
discipline, and the append-only hash chain — asserted over source, AST and metadata."""

from __future__ import annotations

import ast
import pathlib
import sqlite3
import sys
import tomllib

import pytest

import ugence_execution_reservation as pkg
from ugence_execution_reservation import (
    InMemoryExecutionReservationStore,
    ProductionModeRefused,
    SqliteExecutionReservationStore,
)

from _fixtures import ACTFP, AUTHZ, T0, clear_result, key, receipt_for, sqlite_path

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_execution_reservation", "ugence_governance_contracts",
                       "ugence_action_clearance", "ugence_decision_authority"}
FORBIDDEN = {"ugence_storygraph", "ugence_code_governance", "ugence_agent_runtime", "risk_authority",
             "ugence_actiongate_provider", "actiongate_provider", "tap_provider", "governance_providers",
             "ugence_governance_provider_framework", "ugence_console_api", "symbolu_robotics", "acp",
             "pydantic", "sqlalchemy", "requests", "httpx", "aiohttp", "boto3", "kubernetes", "github",
             "azure", "google", "openai", "redis", "psycopg", "fastapi"}


def _roots(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_source_imports_only_stdlib_and_the_ratified_first_party_set():
    for src in SOURCES:
        strays = _roots(src) - STDLIB - ALLOWED_FIRST_PARTY - {"__future__"}
        assert not strays, (src.name, strays)
        assert not (_roots(src) & FORBIDDEN), (src.name, _roots(src) & FORBIDDEN)


def test_pyproject_declares_the_ratified_dependency_set_and_no_direct_pydantic():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-execution-reservation"
    assert data["project"]["dependencies"] == [
        "ugence-governance-contracts>=0.4.0",
        "ugence-action-clearance>=0.1.0",
        "ugence-decision-authority>=1.0.0",
    ]
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("pydantic", "sqlalchemy", "storygraph", "code-governance", "agent-runtime",
                      "boto3", "kubernetes", "redis", "psycopg"):
        assert forbidden not in joined
    assert pkg.__version__ == "0.1.0"


def test_no_clock_is_read_anywhere():
    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                assert name not in ("now", "utcnow", "today", "time", "monotonic", "perf_counter",
                                    "uuid4", "uuid1", "urandom", "random"), (src.name, name)
                if name == "astimezone":
                    assert node.args, f"{src.name}: zero-argument astimezone infers the local zone"


def test_adapters_expose_no_dispatch_execute_or_authority_methods():
    for cls in (InMemoryExecutionReservationStore, SqliteExecutionReservationStore):
        names = {n for n in dir(cls) if not n.startswith("_")}
        assert not names & {"dispatch", "execute", "merge", "cancel", "authorize", "issue_credential",
                            "assume_role", "run"}, cls.__name__
    forbidden_suffixes = ("Authorization", "Grant", "Envelope", "Token", "Credential", "Permit")
    assert [n for n in pkg.__all__ if n.endswith(forbidden_suffixes)] == []
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"


def test_reference_adapters_are_refused_in_production_mode(tmp_path):
    with pytest.raises(ProductionModeRefused):
        InMemoryExecutionReservationStore(production_mode=True)
    with pytest.raises(ProductionModeRefused):
        SqliteExecutionReservationStore(":memory:", production_mode=True)
    s = SqliteExecutionReservationStore(sqlite_path(tmp_path), production_mode=True)
    assert s.production_mode is True
    s.close()


def test_ledger_events_are_append_only_and_hash_linked(tmp_path):
    path = sqlite_path(tmp_path)
    s = SqliteExecutionReservationStore(path)
    r = receipt_for(clear_result()); s.put_receipt(r)
    out = s.reserve_once(key(), r.receipt_id, AUTHZ, ACTFP, 300, as_of=T0)
    assert out.is_acquired and s.verify_chain()
    raw = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("UPDATE ledger_events SET event_type='RESERVED' WHERE seq=1")
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("DELETE FROM ledger_events WHERE seq=1")
    # Even a privileged writer that drops the guard leaves a detectable break.
    raw.executescript("DROP TRIGGER ledger_events_no_update; "
                      "UPDATE ledger_events SET detail_json='{}' WHERE seq=2;")
    raw.close()
    assert s.verify_chain() is False
    s.close()


def test_schema_version_mismatch_is_refused(tmp_path):
    path = sqlite_path(tmp_path)
    SqliteExecutionReservationStore(path).close()
    raw = sqlite3.connect(path); raw.execute("UPDATE meta SET value='other' WHERE key='schema_version'"); raw.commit(); raw.close()
    from ugence_execution_reservation import StoreUnavailableError
    with pytest.raises(StoreUnavailableError):
        SqliteExecutionReservationStore(path)
