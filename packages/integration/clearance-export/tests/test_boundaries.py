"""The lines CE-1, CE-2 and CE-5 draw, held structurally rather than by discipline.

Each test here asserts that a forbidden capability is *absent from the package*,
not merely unused by it. The difference matters: a package that could open a file
and chooses not to is one refactor away from doing it.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_clearance_export as package
from ugence_clearance_export import (
    COMPILE_SHAPED_KEYS,
    NotAReceivedClearance,
    ReceivedClearanceSource,
    artifact_to_dict,
    build_export,
    select_by_receipt_id,
    select_for_tenant,
)

from _fixtures import TENANT, artifact, body

SRC = pathlib.Path(package.__file__).resolve().parent

#: CE-2: no store, no adapter, no connector, no clock, no network. Each of these
#: would be one import away, so the import is what gets banned.
FORBIDDEN_IMPORTS = {
    "sqlite3", "socket", "http", "urllib", "requests", "httpx", "asyncio",
    "subprocess", "pathlib", "os", "time", "secrets", "uuid",
}

#: CE-6 keeps the studio away from both of these. The export package must not drag
#: either in transitively either: one persists receipts, the other evaluates them.
FORBIDDEN_PACKAGES = {"ugence_execution_reservation", "ugence_control_plane_root"}


def _imports() -> set[str]:
    names: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def test_the_package_cannot_store_connect_or_read_a_clock():
    assert FORBIDDEN_IMPORTS.isdisjoint(_imports())


def test_the_package_does_not_reach_a_receipt_store_or_a_ledger():
    assert FORBIDDEN_PACKAGES.isdisjoint(_imports())


def test_the_only_first_party_dependency_is_action_clearance():
    first_party = {n for n in _imports() if n.startswith("ugence_")}
    assert first_party == {"ugence_action_clearance"}


def test_no_datetime_now_anywhere():
    """Every instant is a caller input. A clock would make two exports of one
    clearance differ, and the artifact is meant to be comparable."""
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "datetime.now" not in text, path
        assert "utcnow" not in text, path


# -- CE-5: export is a read ------------------------------------------------- #

def test_the_port_has_no_write_method():
    """A port with a write would make 'no operation may accept a receipt' (§13.3)
    a matter of discipline. Without one it is structural."""
    surface = {n for n in dir(ReceivedClearanceSource) if not n.startswith("_")}
    assert surface == {"read_receipt", "list_receipt_ids"}


def test_the_package_exposes_no_write_verb_at_all():
    written = {n for n in package.__all__
               if any(v in n.lower() for v in ("put", "save", "store", "write",
                                               "record", "accept", "persist",
                                               "issue", "sign", "grant", "clear_"))}
    assert written == set()


# -- CE-1: a compile result is not a clearance ------------------------------ #

def test_a_non_receipt_cannot_be_exported():
    with pytest.raises(NotAReceivedClearance):
        build_export(
            {"logical_digest": "abc", "workflow_ir": {}},
            identity_assurance=package.IdentityAssurance.PRESENTED_UNPROVEN,
            authenticity=package.ExportAuthenticity.UNSIGNED,
            data_classification=package.ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY)


@pytest.mark.parametrize("key", COMPILE_SHAPED_KEYS)
def test_a_compile_shaped_payload_is_refused_on_reconstruction(key):
    payload = artifact_to_dict(artifact())
    payload["receipt_body"][key] = "whatever"
    with pytest.raises(NotAReceivedClearance):
        package.artifact_from_dict(payload)


def test_the_artifact_carries_no_compile_field():
    exported = artifact_to_dict(artifact())
    flat = set(exported) | set(exported["receipt_body"])
    assert flat.isdisjoint(COMPILE_SHAPED_KEYS)


# -- pure selectors --------------------------------------------------------- #

def test_select_by_receipt_id_finds_and_misses_cleanly():
    one = body()
    assert select_by_receipt_id([one], one.receipt_id) is one
    assert select_by_receipt_id([one], "acr_absent") is None


def test_select_for_tenant_filters_without_granting():
    mine = body(tenant_id=TENANT)
    theirs = body(tenant_id="tenant-beta")
    assert select_for_tenant([mine, theirs], TENANT) == (mine,)
    assert select_for_tenant([mine, theirs], "tenant-beta") == (theirs,)


def test_maturity_is_stated_and_enforcement_is_off():
    assert package.MATURITY == "CONTRACTS_ONLY"
    assert package.ENFORCEMENT_ENABLED is False
