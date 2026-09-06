"""The one ruled local store (front-door FD-9.2): tenant-bound, append-only, a file.

Every instant is a caller input; no test reads a clock. Restart survival is proven by
closing the store and reopening the same file.
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from _fixtures import AFTER_WINDOW, LABEL, OWNER, T0, T1, TENANT, binding, registration
from ugence_governance_contracts.api import Validity

from ugence_ai_system_registry import (
    ContractViolation,
    CrossTenantRefused,
    DuplicateRegistrationError,
    RegistrationSupersessionError,
    RegistryProductionModeError,
    RegistryStorageError,
    SqliteSystemRegistry,
    SystemRegistration,
    SystemRegistryPort,
    binding_from_dict,
    binding_to_dict,
    registration_from_record,
    registration_id_for,
    registration_record,
)

OTHER_TENANT = "tenant-b"


@pytest.fixture()
def path(tmp_path) -> str:
    return str(tmp_path / "registry.sqlite3")


@pytest.fixture()
def store(path):
    s = SqliteSystemRegistry(path, tenant_id=TENANT)
    try:
        yield s
    finally:
        s.close()


def _reg(**kw) -> SystemRegistration:
    return registration(**kw)


# --------------------------------------------------------------------------- #
# the port, satisfied; the one write
# --------------------------------------------------------------------------- #
def test_the_store_satisfies_the_read_only_port_and_adds_exactly_one_write(store):
    assert isinstance(store, SystemRegistryPort)
    public = {n for n in dir(store) if not n.startswith("_")}
    writes = public - {"get_registration", "registrations_for_tenant", "registrations_for_system",
                       "registrations_by_classification", "close", "count", "all_registered_at",
                       "kind", "path", "tenant_id", "production_mode"}
    assert writes == {"register"}
    for forbidden in ("edit", "update", "delete", "revoke", "admit", "gate", "promote", "attest",
                      "approve", "resolve", "save", "upsert"):
        assert forbidden not in public


def test_register_then_read_by_id_tenant_system_and_classification(store):
    reg = _reg()
    assert store.register(reg) is reg
    assert store.count() == 1
    assert store.get_registration(reg.registration_id) == reg
    assert store.registrations_for_tenant(tenant_id=TENANT, as_of=T1) == (reg,)
    assert store.registrations_for_system(tenant_id=TENANT, system_id=reg.system_id, as_of=T1) == (reg,)
    assert store.registrations_by_classification(tenant_id=TENANT, classification_label=LABEL, as_of=T1) == (reg,)
    # outside its window it is absent from every answer, never flagged
    assert store.registrations_for_tenant(tenant_id=TENANT, as_of=AFTER_WINDOW) == ()
    assert store.get_registration("reg_nobody") is None


def test_records_survive_a_restart_of_the_process(path):
    first = SqliteSystemRegistry(path, tenant_id=TENANT)
    reg = _reg()
    first.register(reg)
    first.close()
    with pytest.raises(RegistryStorageError):
        first.count()
    second = SqliteSystemRegistry(path, tenant_id=TENANT)
    try:
        assert second.get_registration(reg.registration_id) == reg
        assert second.registrations_for_tenant(tenant_id=TENANT, as_of=T1) == (reg,)
        assert reg.record_digest() == second.get_registration(reg.registration_id).record_digest()
    finally:
        second.close()


# --------------------------------------------------------------------------- #
# refusals: tenant, duplicate, supersession, blank fields, tampering
# --------------------------------------------------------------------------- #
def test_a_read_or_write_for_another_tenant_is_a_typed_refusal_never_empty(store):
    store.register(_reg())
    with pytest.raises(CrossTenantRefused):
        store.registrations_for_tenant(tenant_id=OTHER_TENANT, as_of=T1)
    with pytest.raises(CrossTenantRefused):
        store.registrations_for_system(tenant_id=OTHER_TENANT, system_id="x", as_of=T1)
    with pytest.raises(CrossTenantRefused):
        store.registrations_by_classification(tenant_id=OTHER_TENANT, classification_label=LABEL, as_of=T1)
    foreign = registration(binding(tenant=OTHER_TENANT))
    with pytest.raises(CrossTenantRefused):
        store.register(foreign)
    assert store.count() == 1


def test_a_registry_file_is_never_rebound_to_another_tenant(path):
    SqliteSystemRegistry(path, tenant_id=TENANT).close()
    with pytest.raises(CrossTenantRefused):
        SqliteSystemRegistry(path, tenant_id=OTHER_TENANT)


def test_a_duplicate_derived_id_is_refused_and_nothing_is_edited(store):
    reg = _reg()
    store.register(reg)
    with pytest.raises(DuplicateRegistrationError):
        store.register(reg)
    assert store.count() == 1


def test_an_inadmissible_supersession_is_refused_by_the_package_rule(store):
    first = _reg()
    store.register(first)
    # same system identity under another owner: a different id, nothing to supersede
    same = registration(owner="directory://people/other", supersedes=first.registration_id)
    with pytest.raises(RegistrationSupersessionError):
        store.register(same)
    # unknown predecessor
    unknown_pred = registration(binding(version="2.0.0"), supersedes="reg_" + "0" * 32)
    with pytest.raises(RegistrationSupersessionError):
        store.register(unknown_pred)
    # admissible: a new version naming its predecessor
    successor = registration(binding(version="2.0.0"), supersedes=first.registration_id)
    store.register(successor)
    assert store.count() == 2
    assert store.registrations_for_system(tenant_id=TENANT, system_id=first.system_id,
                                          system_version="2.0.0", as_of=T1) == (successor,)


def test_a_blank_owner_or_label_is_refused_at_construction_by_the_package():
    b = binding()
    validity = Validity(issued_at=T0, expires_at=AFTER_WINDOW)
    for owner, label in ((" ", LABEL), (OWNER, ""), ("", "")):
        with pytest.raises(ContractViolation):
            SystemRegistration(registration_id=registration_id_for(b, owner or "x", validity),
                               binding=b, owner_ref=owner, classification_label=label,
                               validity=validity)


def test_a_tampered_record_cannot_reconstruct(store, path):
    reg = _reg()
    store.register(reg)
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT record_json FROM registrations").fetchone()[0]
        tampered = row.replace(LABEL, "low-risk")
        conn.execute("UPDATE registrations SET record_json = ?", (tampered,))
    with pytest.raises(ContractViolation):
        store.get_registration(reg.registration_id)


def test_production_mode_refuses_a_non_durable_location(tmp_path):
    for bad in (":memory:", "file::memory:?cache=shared"):
        with pytest.raises(RegistryProductionModeError):
            SqliteSystemRegistry(bad, tenant_id=TENANT, production_mode=True)
    ok = SqliteSystemRegistry(str(tmp_path / "prod.sqlite3"), tenant_id=TENANT, production_mode=True)
    ok.close()
    with pytest.raises(ContractViolation):
        SqliteSystemRegistry(str(tmp_path / "x.sqlite3"), tenant_id=" ")


# --------------------------------------------------------------------------- #
# serialization round trips
# --------------------------------------------------------------------------- #
def test_binding_and_registration_round_trip_through_their_records():
    reg = _reg()
    assert binding_from_dict(binding_to_dict(reg.binding)) == reg.binding
    assert registration_from_record(registration_record(reg)) == reg
    with pytest.raises(ContractViolation):
        binding_from_dict({"binding_id": "x", "unknown": 1})
    with pytest.raises(ContractViolation):
        binding_from_dict({"binding_id": "x"})  # missing required identity fields
    with pytest.raises(ContractViolation):
        registration_from_record({"registration": {}, "binding": binding_to_dict(reg.binding)})


# --------------------------------------------------------------------------- #
# the store's own boundary: sqlite and stdlib only, no clock, no network
# --------------------------------------------------------------------------- #
def test_the_store_imports_only_sqlite_and_stdlib_and_reads_no_clock():
    src = Path(__file__).resolve().parent.parent / "src" / "ugence_ai_system_registry" / "durable.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    assert roots <= {"json", "sqlite3", "threading", "datetime", "typing", "__future__"}, roots
    text = src.read_text(encoding="utf-8")
    for forbidden in ("datetime.now", "utcnow", "time.time", "socket", "http", "urllib", "requests",
                      "sqlalchemy", "psycopg", "DELETE FROM", "UPDATE registrations"):
        assert forbidden not in text, forbidden
    assert "os.environ" not in text
