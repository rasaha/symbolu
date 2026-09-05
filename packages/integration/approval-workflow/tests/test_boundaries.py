"""Import boundary, the clock-free rule, the declared dependency set, production
refusal, surface discipline, and the append-only hash chain — asserted over source,
AST and metadata.

These are the ADR's prohibitions made mechanical: the package imports only
governance-contracts and the standard library, copies the execution-reservation
ledger shape without importing it, reads no clock, and offers no surface through
which it could approve, authenticate or execute.
"""

from __future__ import annotations

import ast
import pathlib
import sqlite3
import sys
import tomllib

import pytest

import ugence_approval_workflow as pkg
from ugence_approval_workflow import (
    InMemoryApprovalWorkflowStore,
    ProductionModeRefused,
    SqliteApprovalWorkflowStore,
    StaticApproverEligibility,
    StoreUnavailableError,
)

from _fixtures import T2, directory, granted, sqlite_path, sqlite_store

PKG_DIR = pathlib.Path(pkg.__file__).resolve().parent
DIST = PKG_DIR.parents[1]
SOURCES = sorted(PKG_DIR.rglob("*.py"))
STDLIB = set(sys.stdlib_module_names)
ALLOWED_FIRST_PARTY = {"ugence_approval_workflow", "ugence_governance_contracts"}
FORBIDDEN = {
    # the reserved nouns and the neighbours whose shape is copied, never imported
    "ugence_decision_authority", "decision_governance", "ugence_policy_workflow_compiler",
    "ugence_execution_reservation", "ugence_cloud_scaling_operations", "ugence_storygraph",
    "ugence_action_clearance", "ugence_risk_authority", "risk_authority",
    # everything a queue has no business reaching for
    "pydantic", "sqlalchemy", "requests", "httpx", "aiohttp", "boto3", "kubernetes",
    "azure", "google", "openai", "redis", "psycopg", "fastapi", "jira", "servicenow", "pysnow",
}


def _roots(path: pathlib.Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_source_imports_only_stdlib_and_governance_contracts():
    for src in SOURCES:
        roots = _roots(src)
        strays = roots - STDLIB - ALLOWED_FIRST_PARTY - {"__future__"}
        assert not strays, (src.name, strays)
        assert not (roots & FORBIDDEN), (src.name, roots & FORBIDDEN)


def test_the_ledger_shape_is_copied_and_the_reserved_nouns_are_not_imported():
    """The sibling ledger and both reserved-noun packages stay out of the import graph."""

    joined = "\n".join(src.read_text() for src in SOURCES)
    for forbidden in ("from ugence_execution_reservation", "import ugence_execution_reservation",
                      "from ugence_decision_authority", "import ugence_decision_authority",
                      "from ugence_policy_workflow_compiler", "import ugence_policy_workflow_compiler"):
        assert forbidden not in joined
    # …but the shape it copies is present: WAL, BEGIN IMMEDIATE, a unique key, and the
    # append-only triggers.
    schema = (PKG_DIR / "sqlite.py").read_text()
    assert "journal_mode=WAL" in schema and "BEGIN IMMEDIATE" in schema
    assert "ON CONFLICT DO NOTHING" in schema and "consumption_key TEXT PRIMARY KEY" in schema
    assert "ledger_events_no_update" in schema and "ledger_events_no_delete" in schema


def test_pyproject_declares_the_ratified_dependency_set():
    data = tomllib.loads((DIST / "pyproject.toml").read_text())
    assert data["project"]["name"] == "ugence-approval-workflow"
    assert data["project"]["dependencies"] == ["ugence-governance-contracts>=0.4.0"]
    joined = " ".join(data["project"]["dependencies"]).lower()
    for forbidden in ("pydantic", "decision-authority", "policy-workflow-compiler",
                      "execution-reservation", "cloud-scaling", "storygraph", "boto3",
                      "kubernetes", "redis", "psycopg", "sqlalchemy"):
        assert forbidden not in joined
    assert pkg.__version__ == "0.1.0"


def test_no_clock_is_read_anywhere():
    """Every instant is a caller input, so expiry needs no sweeper and no wall clock."""

    for src in SOURCES:
        for node in ast.walk(ast.parse(src.read_text())):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                assert name not in ("now", "utcnow", "today", "time", "monotonic",
                                    "perf_counter", "uuid4", "uuid1", "urandom",
                                    "random"), (src.name, name)
                if name == "astimezone":
                    assert node.args, f"{src.name}: zero-argument astimezone infers the local zone"


def test_expiry_goes_through_the_governance_contracts_validity():
    records = (PKG_DIR / "records.py").read_text()
    assert "from ugence_governance_contracts.api import Validity, ValidityStatus" in records
    assert "status_at" in records
    assert "Validity" in pkg.ApprovalRecord.__annotations__["validity"]


def test_no_surface_could_approve_authenticate_or_execute():
    for cls in (InMemoryApprovalWorkflowStore, SqliteApprovalWorkflowStore):
        names = {n for n in dir(cls) if not n.startswith("_")}
        assert not names & {"approve", "grant", "authenticate", "authorize", "sign",
                            "execute", "dispatch", "run", "issue_credential", "assume_role",
                            "notify", "push", "mirror", "sync"}, cls.__name__
    forbidden_suffixes = ("Authorization", "Grant", "Envelope", "Token", "Credential", "Permit",
                          "Mirror", "Connector", "Client")
    assert [n for n in pkg.__all__ if n.endswith(forbidden_suffixes)] == []
    assert pkg.ENFORCEMENT_ENABLED is False and pkg.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"


def test_no_servicenow_or_jira_adapter_ships_in_this_release():
    joined = "\n".join(src.read_text().lower() for src in SOURCES)
    for name in ("servicenow", "jira", "webhook", "http://", "https://"):
        assert name not in joined, name
    assert not [p for p in SOURCES if "mirror" in p.name or "connector" in p.name]


def test_reference_adapters_are_refused_in_production_mode(tmp_path):
    with pytest.raises(ProductionModeRefused):
        InMemoryApprovalWorkflowStore(directory(), production_mode=True)
    with pytest.raises(ProductionModeRefused):
        SqliteApprovalWorkflowStore(":memory:", directory(), production_mode=True)
    with pytest.raises(ProductionModeRefused):
        StaticApproverEligibility((), production_mode=True)
    store = SqliteApprovalWorkflowStore(sqlite_path(tmp_path), directory(), production_mode=True)
    assert store.production_mode is True
    store.close()


def test_ledger_events_are_append_only_and_hash_linked(tmp_path):
    path = sqlite_path(tmp_path)
    store = sqlite_store(tmp_path)
    record = granted(store)
    store.consume(record.approval_id, consumer_ref="decision_case:case_1",
                  subject_digest=record.subject_digest, as_of=T2)
    assert store.verify_chain()

    raw = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("UPDATE ledger_events SET event_type='GRANTED' WHERE seq=1")
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("DELETE FROM ledger_events WHERE seq=1")
    # Even a privileged writer that drops the guard leaves a detectable break.
    raw.executescript("DROP TRIGGER ledger_events_no_update; "
                      "UPDATE ledger_events SET detail_json='{}' WHERE seq=2;")
    raw.close()
    assert store.verify_chain() is False
    store.close()


def test_a_tampered_artifact_is_refused_on_read(tmp_path):
    from ugence_approval_workflow import ArtifactIntegrityError

    path = sqlite_path(tmp_path)
    store = sqlite_store(tmp_path)
    record = granted(store)
    store.close()
    raw = sqlite3.connect(path)
    raw.execute("UPDATE approvals SET record_json=replace(record_json, '\"GRANTED\"', '\"PENDING\"') "
                "WHERE approval_id=?", (record.approval_id,))
    raw.commit()
    raw.close()
    reopened = SqliteApprovalWorkflowStore(path, directory())
    with pytest.raises(ArtifactIntegrityError):
        reopened.get_approval(record.approval_id)
    reopened.close()


def test_schema_version_mismatch_is_refused(tmp_path):
    path = sqlite_path(tmp_path)
    SqliteApprovalWorkflowStore(path, directory()).close()
    raw = sqlite3.connect(path)
    raw.execute("UPDATE meta SET value='other' WHERE key='schema_version'")
    raw.commit()
    raw.close()
    with pytest.raises(StoreUnavailableError):
        SqliteApprovalWorkflowStore(path, directory())
