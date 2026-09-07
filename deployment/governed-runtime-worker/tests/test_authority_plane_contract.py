"""The authority plane's contract and verb test (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md
§11 step 1, rulings AP-1 to AP-5).

The shape of the studio's SD-2 test with the sense reversed. There, seven verbs may
never appear. Here, four of them may (grant, revoke, activate, issue: AP-4) and the
other three (authorize, clear, execute) fail the build if any operation id, path or
summary names one. A guard that cannot fail is not a guard, so one test proves the scan
catches a violation.

And what each step serves. Step 2 (AP-5) mounts the four reads through
``authority_reads.py`` and nothing else: no write path is served, no module of the
worker names one outside the contract, and the plane's paths appear in no route the
review service serves. The committed JSON rendering is drift-tested against the module
so the document a reader sees is the one the test scanned.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

import governed_runtime_worker as worker
from governed_runtime_worker import authority_plane as plane
from ugence_governed_review_service.http import ROUTES
from ugence_governed_review_service.identity import PROOF_HEADER

SRC = pathlib.Path(worker.__file__).resolve().parent
PKG = SRC.parents[1]
CONTRACT = PKG / "authority-plane-contract.json"


# --------------------------------------------------------------------------- #
# AP-4: the verbs
# --------------------------------------------------------------------------- #
def test_no_operation_id_path_or_summary_names_a_refused_verb():
    assert plane.verb_violations() == [], (
        "AP-4 violation — the plane never names runtime authority:\n  "
        + "\n  ".join(plane.verb_violations()))


def test_every_write_names_exactly_one_permitted_verb_and_reads_name_none():
    for op in plane.PLANE_OPERATIONS:
        haystack = f"{op.operation_id} {op.path} {op.summary}".lower()
        named = [v for v in plane.PERMITTED_VERBS if v in haystack]
        if op.kind == "write":
            assert op.names_verb in named, (op.operation_id, named)
        else:
            # a read may mention "grants" as a noun; it declares no verb of its own
            assert op.names_verb == "", op.operation_id


def test_the_permitted_and_refused_sets_partition_the_seven_sd2_verbs():
    """The plane's four plus the runtime's three are SD-2's seven, exactly."""
    sd2 = {"issue", "activate", "revoke", "grant", "authorize", "clear", "execute"}
    assert set(plane.PERMITTED_VERBS) | set(plane.REFUSED_VERBS) == sd2
    assert set(plane.PERMITTED_VERBS) & set(plane.REFUSED_VERBS) == set()


def test_the_verb_scan_actually_catches_a_violation():
    """A guard that cannot fail is not a guard: one fake per scanned field."""
    fakes = (
        plane.PlaneOperation(operation_id="authority_clear_action", method="POST",
                             path="/authority/actions", summary="Clear one action",
                             kind="write", names_verb="grant", acts_on="x", ruling="AP-3"),
        plane.PlaneOperation(operation_id="authority_grant_role", method="POST",
                             path="/authority/execute", summary="Load a grant",
                             kind="write", names_verb="grant", acts_on="x", ruling="AP-3"),
        plane.PlaneOperation(operation_id="authority_list_grants", method="GET",
                             path="/authority/grants", summary="Authorize the listing",
                             kind="read", names_verb="", acts_on="x", ruling="AP-5"),
    )
    caught = plane.verb_violations(fakes)
    assert len(caught) == 4, caught  # id+summary of the first, path of the second, summary of the third
    assert any("operation_id names 'clear'" in c for c in caught)
    assert any("path names 'execute'" in c for c in caught)
    assert any("summary names 'authorize'" in c for c in caught)


def test_a_write_that_names_no_permitted_verb_cannot_be_declared():
    with pytest.raises(ValueError):
        plane.PlaneOperation(operation_id="authority_do_thing", method="POST",
                             path="/authority/things", summary="Do a thing",
                             kind="write", names_verb="", acts_on="x", ruling="AP-3")


# --------------------------------------------------------------------------- #
# AP-3 and AP-5: the gate and the label
# --------------------------------------------------------------------------- #
def test_every_write_carries_the_identity_gate_and_every_read_the_proof_label():
    writes = [op for op in plane.PLANE_OPERATIONS if op.kind == "write"]
    reads = [op for op in plane.PLANE_OPERATIONS if op.kind == "read"]
    assert len(writes) == 4 and len(reads) == 4
    for op in writes:
        assert op.ruling.startswith("AP-3") and "IDP_AUTHENTICATED" in op.gate and "refused" in op.gate
        # AW-1 names the two served writes and no other; the unserved two keep AP-3 alone
        assert (op.operation_id in plane.SERVED_WRITES) == ("AW-1" in op.ruling), op.operation_id
    assert plane.WRITE_PROOF_HEADER == PROOF_HEADER, "the writes read the decision route's header"
    for op in reads:
        assert op.ruling == "AP-5" and "PRESENTED_UNPROVEN" in op.gate
    assert {op.names_verb for op in writes} == set(plane.PERMITTED_VERBS), \
        "each of the four permitted verbs is named by exactly one write"


# --------------------------------------------------------------------------- #
# Step 2 serves the reads and nothing else
# --------------------------------------------------------------------------- #
WRITE_PATHS = tuple(op.path for op in plane.PLANE_OPERATIONS if op.kind == "write")
UNSERVED_WRITE_PATHS = tuple(op.path for op in plane.PLANE_OPERATIONS
                             if op.kind == "write" and op.operation_id not in plane.SERVED_WRITES)
READ_OPS = tuple(op for op in plane.PLANE_OPERATIONS if op.kind == "read")
SERVED_WRITE_OPS = tuple(op for op in plane.PLANE_OPERATIONS
                         if op.kind == "write" and op.operation_id in plane.SERVED_WRITES)


def test_reads_and_the_two_directory_writes_are_served_and_no_plane_path_overlaps_the_review_routes(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ugence_authority_directory import SqliteAuthorityDirectory

    from governed_runtime_worker.authority_reads import build_authority_reads
    from governed_runtime_worker.authority_writes import build_authority_writes
    from conftest import TENANT, Clock

    assert plane.READS_SERVED is True
    assert plane.SERVED_WRITES == ("authority_grant_role", "authority_revoke_grant"), "AW-2"
    assert len(UNSERVED_WRITE_PATHS) == 2
    served_paths = {path for _m, path, _o in ROUTES}
    plane_paths = {op.path for op in plane.PLANE_OPERATIONS}
    assert served_paths.isdisjoint(plane_paths)
    assert all(p.startswith("/authority/") for p in plane_paths)
    for m, p, o in plane.REUSED_EXISTING:
        assert (m, p, o) in ROUTES
    # the routers serve exactly the four reads and the two served writes, with the
    # contract's ids and summaries; the two unserved writes appear on no path
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"))
    app = FastAPI()
    app.include_router(build_authority_reads(directory, tenant_id=TENANT, clock=Clock().datetime,
                                             identity_port_configured=False))
    app.include_router(build_authority_writes(directory, tenant_id=TENANT, clock=Clock().datetime,
                                              identity_port=None))
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
    seen = {(m.upper(), path, op["operationId"], op.get("summary"))
            for path, ops in spec["paths"].items() for m, op in ops.items()}
    assert seen == {(op.method, op.path, op.operation_id, op.summary)
                    for op in READ_OPS + SERVED_WRITE_OPS}
    served_methods = {(m.upper(), path) for path, ops in spec["paths"].items() for m in ops}
    assert not any((op.method, op.path) in served_methods
                   for op in plane.PLANE_OPERATIONS if op.kind == "write" and not op.served)


def test_only_the_writes_module_names_the_directory_writes_and_the_unserved_paths_appear_nowhere():
    """A write route cannot appear by accident: its path is unique to the contract, and
    the directory's write methods are called from one module."""
    for module in SRC.glob("*.py"):
        text = module.read_text(encoding="utf-8")
        if module.name == "authority_plane.py":
            continue
        for path in UNSERVED_WRITE_PATHS:
            assert path not in text, f"{module.name} names the unserved write path {path}"
        if module.name == "authority_writes.py":
            assert "put_grant" in text and "revoke_grant" in text
            # the served paths are taken from the contract, never written as literals
            for path in WRITE_PATHS:
                assert path not in text, f"authority_writes.py hard-codes {path}"
            continue
        for path in WRITE_PATHS:
            assert path not in text, f"{module.name} names the write path {path}"
        assert "put_grant" not in text and "revoke_grant" not in text, module.name


def test_the_composition_mounts_the_reads_and_the_served_writes_and_nothing_else_of_the_plane():
    tree = ast.parse((SRC / "composition.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        # the worker's own modules only (relative imports); the directory package is
        # a composed dependency, not a plane module
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module \
                and "authority" in node.module:
            imported.add(node.module)
    assert imported == {"authority_reads", "authority_writes"}, imported
    for name in ("server.py", "starter.py", "workload.py", "__init__.py"):
        text = (SRC / name).read_text(encoding="utf-8")
        assert "authority_reads" not in text and "authority_plane" not in text, name
        assert "build_authority_writes" not in text, name


# --------------------------------------------------------------------------- #
# The committed rendering
# --------------------------------------------------------------------------- #
def test_the_committed_contract_is_the_module_rendered_without_drift():
    committed = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert committed == plane.contract_document()
    assert CONTRACT.read_text(encoding="utf-8") == json.dumps(plane.contract_document(), indent=2) + "\n"


def test_the_committed_contract_says_what_is_not_on_the_plane():
    committed = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert committed["served"] == {"reads": True, "writes": list(plane.SERVED_WRITES)}
    assert committed["write_proof_header"] == PROOF_HEADER
    for op in committed["operations"]:
        expected = op["kind"] == "read" or op["operation_id"] in plane.SERVED_WRITES
        assert op["served"] is expected, op["operation_id"]
    assert [op["operation_id"] for op in committed["operations"] if op["kind"] == "write" and not op["served"]] \
        == ["authority_activate_constitution", "authority_issue_record"]
    joined = " ".join(committed["not_on_the_plane"]).lower()
    for absent in ("authorize, clear, execute", "module composition", "nine module rows", "emergency stop"):
        assert absent in joined, absent
    assert committed["schema"] == plane.CONTRACT_SCHEMA
    assert "AP-1" in committed["ruling"] and "AP-5" in committed["ruling"] and "AW-1" in committed["ruling"]
