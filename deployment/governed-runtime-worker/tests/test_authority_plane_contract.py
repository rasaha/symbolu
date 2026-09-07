"""The authority plane's contract and verb test (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md
§11 step 1, rulings AP-1 to AP-5).

The shape of the studio's SD-2 test with the sense reversed. There, seven verbs may
never appear. Here, four of them may (grant, revoke, activate, issue: AP-4) and the
other three (authorize, clear, execute) fail the build if any operation id, path or
summary names one. A guard that cannot fail is not a guard, so one test proves the scan
catches a violation.

And the step's other claim: nothing is served. The plane's paths appear in no route
the review service serves, and neither the composition nor the server imports the
plane. The committed JSON rendering is drift-tested against the module so the
document a reader sees is the one the test scanned.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

import governed_runtime_worker as worker
from governed_runtime_worker import authority_plane as plane
from ugence_governed_review_service.http import ROUTES

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
        assert op.ruling == "AP-3" and "IDP_AUTHENTICATED" in op.gate and "refused" in op.gate
    for op in reads:
        assert op.ruling == "AP-5" and "PRESENTED_UNPROVEN" in op.gate
    assert {op.names_verb for op in writes} == set(plane.PERMITTED_VERBS), \
        "each of the four permitted verbs is named by exactly one write"


# --------------------------------------------------------------------------- #
# Step 1 serves nothing
# --------------------------------------------------------------------------- #
def test_nothing_is_served_and_no_plane_path_overlaps_the_review_routes():
    assert plane.SERVED is False
    served_paths = {path for _m, path, _o in ROUTES}
    plane_paths = {op.path for op in plane.PLANE_OPERATIONS}
    assert served_paths.isdisjoint(plane_paths)
    assert all(p.startswith("/authority/") for p in plane_paths)
    assert all(not p.startswith("/authority/") for p in served_paths)
    # the one reused read is a route the service already serves, unchanged
    for m, p, o in plane.REUSED_EXISTING:
        assert (m, p, o) in ROUTES


def test_neither_the_composition_nor_the_server_imports_the_plane():
    for name in ("composition.py", "server.py", "starter.py", "workload.py", "__init__.py"):
        tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "authority_plane" in node.module:
                raise AssertionError(f"{name} imports the plane; step 1 serves nothing")
            if isinstance(node, ast.ImportFrom) and node.module in ("", None) and any(
                    a.name == "authority_plane" for a in node.names):
                raise AssertionError(f"{name} imports the plane; step 1 serves nothing")
            if isinstance(node, ast.Import) and any("authority_plane" in a.name for a in node.names):
                raise AssertionError(f"{name} imports the plane; step 1 serves nothing")


# --------------------------------------------------------------------------- #
# The committed rendering
# --------------------------------------------------------------------------- #
def test_the_committed_contract_is_the_module_rendered_without_drift():
    committed = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert committed == plane.contract_document()
    assert CONTRACT.read_text(encoding="utf-8") == json.dumps(plane.contract_document(), indent=2) + "\n"


def test_the_committed_contract_says_what_is_not_on_the_plane():
    committed = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert committed["served"] is False
    joined = " ".join(committed["not_on_the_plane"]).lower()
    for absent in ("authorize, clear, execute", "module composition", "nine module rows", "emergency stop"):
        assert absent in joined, absent
    assert committed["schema"] == plane.CONTRACT_SCHEMA
    assert "AP-1" in committed["ruling"] and "AP-5" in committed["ruling"]
