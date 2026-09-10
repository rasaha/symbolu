"""The one ruled local store: append-only, tenant-bound, verified on read, no clock."""

from __future__ import annotations

import ast
import json
import pathlib
import sqlite3
import sys

import pytest

from _fixtures import OTHER, TENANT, document, draft
from ugence_workflow_drafts import (
    SCHEMA_VERSION,
    ContractViolation,
    CrossTenantRefused,
    DraftProductionModeError,
    DraftStorageError,
    DraftSupersessionError,
    DuplicateDraftError,
    SqliteWorkflowDrafts,
    WorkflowDraftPort,
)


@pytest.fixture()
def path(tmp_path):
    return str(tmp_path / "drafts.sqlite3")


@pytest.fixture()
def store(path):
    s = SqliteWorkflowDrafts(path, tenant_id=TENANT)
    try:
        yield s
    finally:
        s.close()


def test_the_store_satisfies_the_port_and_save_is_its_only_write(store):
    assert isinstance(store, WorkflowDraftPort)
    assert store.kind == "SqliteWorkflowDrafts" and store.schema_version == SCHEMA_VERSION
    public = {n for n in dir(store) if not n.startswith("_") and callable(getattr(store, n))}
    assert public == {"save", "get_draft", "drafts_for_tenant", "lineage_of", "superseded_by",
                      "count", "close"}


def test_save_get_list_and_lineage_round_trip(store):
    a = store.save(draft(title="a"))
    b = store.save(draft(title="b", supersedes=a.draft_id))
    assert store.count() == 2
    assert store.get_draft(a.draft_id) == a and store.get_draft("wfd_" + "0" * 32) is None
    assert store.drafts_for_tenant(tenant_id=TENANT) == (b,)
    assert store.drafts_for_tenant(tenant_id=TENANT, include_superseded=True) == (a, b)
    assert store.lineage_of(b.draft_id) == (a, b)
    assert store.superseded_by(a.draft_id) == b.draft_id and store.superseded_by(b.draft_id) == ""


def test_records_survive_a_restart_and_the_file_is_never_re_bound(path):
    s = SqliteWorkflowDrafts(path, tenant_id=TENANT)
    a = s.save(draft())
    s.close()
    again = SqliteWorkflowDrafts(path, tenant_id=TENANT)
    try:
        assert again.get_draft(a.draft_id) == a and again.count() == 1
    finally:
        again.close()
    with pytest.raises(CrossTenantRefused):
        SqliteWorkflowDrafts(path, tenant_id=OTHER)


def test_a_foreign_tenant_is_a_typed_refusal_on_write_and_read(store):
    with pytest.raises(CrossTenantRefused):
        store.save(draft(tenant_id=OTHER))
    with pytest.raises(CrossTenantRefused):
        store.drafts_for_tenant(tenant_id=OTHER)
    assert store.count() == 0


def test_duplicates_and_inadmissible_supersessions_are_refused(store):
    a = store.save(draft(title="a"))
    with pytest.raises(DuplicateDraftError):
        store.save(draft(title="a"))
    with pytest.raises(DraftSupersessionError, match="not recorded"):
        store.save(draft(title="b", supersedes="wfd_" + "0" * 32))
    with pytest.raises(DraftSupersessionError, match="changes nothing"):
        store.save(draft(title="a", supersedes=a.draft_id))
    b = store.save(draft(title="b", supersedes=a.draft_id))
    with pytest.raises(DraftSupersessionError, match="already superseded"):
        store.save(draft(title="c", supersedes=a.draft_id))
    assert store.drafts_for_tenant(tenant_id=TENANT) == (b,)
    assert store.count() == 2


def test_a_record_altered_outside_the_package_cannot_be_read(store, path):
    a = store.save(draft())
    raw = sqlite3.connect(path)
    record = json.loads(raw.execute("SELECT record_json FROM drafts").fetchone()[0])
    record["draft"]["title"] = "Tampered"
    raw.execute("UPDATE drafts SET record_json = ?", (json.dumps(record),))
    raw.commit()
    raw.close()
    with pytest.raises(ContractViolation):
        store.get_draft(a.draft_id)


def test_a_stored_digest_that_disagrees_with_its_record_is_refused(store, path):
    store.save(draft())
    raw = sqlite3.connect(path)
    raw.execute("UPDATE drafts SET record_digest = ?", ("0" * 64,))
    raw.commit()
    raw.close()
    with pytest.raises(ContractViolation, match="altered outside"):
        store.count()


def test_an_unknown_schema_and_a_closed_store_are_storage_refusals(path):
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE drafts_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    raw.execute("INSERT INTO drafts_meta VALUES ('schema_version', 'workflow_drafts.sqlite.v9')")
    raw.commit()
    raw.close()
    with pytest.raises(DraftStorageError, match="does not know"):
        SqliteWorkflowDrafts(path, tenant_id=TENANT)
    s = SqliteWorkflowDrafts(":memory:", tenant_id=TENANT)
    s.close()
    with pytest.raises(DraftStorageError, match="closed"):
        s.count()


def test_production_mode_refuses_a_non_durable_location():
    for location in (":memory:", "file::memory:?cache=shared"):
        with pytest.raises(DraftProductionModeError):
            SqliteWorkflowDrafts(location, tenant_id=TENANT, production_mode=True)
    s = SqliteWorkflowDrafts(":memory:", tenant_id=TENANT)
    s.save(draft())
    assert s.count() == 1
    s.close()


def test_the_store_imports_only_sqlite_and_the_stdlib_and_reads_no_clock():
    import ugence_workflow_drafts.durable as durable

    tree = ast.parse(pathlib.Path(durable.__file__).read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            assert name not in ("now", "utcnow", "today", "time", "uuid4", "random")
    assert roots <= set(sys.stdlib_module_names) | {"__future__"}
    assert "sqlite3" in roots


def test_the_document_kept_is_the_canonical_one_not_the_text_presented(store):
    d = store.save(draft(workflow=document(zeta=1, alpha=2)))
    kept = store.get_draft(d.draft_id)
    assert kept is not None
    assert list(json.loads(kept.workflow_text)) == sorted(json.loads(kept.workflow_text))
    assert kept.workflow_digest == d.workflow_digest
