"""The one ruled durable home (front-door ruling FD-13.2), and the boundary it keeps.

`declare` is the only write (FD-13.4): the file is tenant-bound and never re-bound, a
declaration is never edited or deleted, a duplicate derived id is refused, and a
supersession is admitted only by the package's own rule. Every semantic prohibition
the contracts-only modules hold, this one holds too: it stores an opaque `vendor_ref`
and never a way to reach the vendor, keeps the risk posture uninterpreted and
unordered, records the `policy_ref` without resolving it, and reads no clock.
"""

from __future__ import annotations

import ast
import json
import pathlib
import sqlite3

import pytest

from ugence_vendor_dependency import (
    ContractViolation,
    CrossTenantRefused,
    DeclarationProductionModeError,
    DeclarationSupersessionError,
    DuplicateDeclarationError,
    SqliteVendorDeclarations,
    VendorDependencyPort,
    declaration_from_record,
    declaration_record,
)

from _fixtures import (
    AFTER_WINDOW,
    OTHER_POLICY,
    OTHER_POSTURE,
    OTHER_VENDOR,
    POSTURE,
    T0,
    T1,
    TENANT,
    VENDOR,
    binding,
    declaration,
    window,
)


@pytest.fixture()
def path(tmp_path) -> str:
    return str(tmp_path / "vendor-declarations.sqlite3")


@pytest.fixture()
def store(path):
    s = SqliteVendorDeclarations(path, tenant_id=TENANT)
    try:
        yield s
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# the port, and the one write
# --------------------------------------------------------------------------- #
def test_the_store_satisfies_the_read_only_port_and_adds_exactly_one_write(store):
    assert isinstance(store, VendorDependencyPort)
    writes = [name for name in dir(store)
              if not name.startswith("_") and callable(getattr(store, name))
              and name not in ("close", "count", "all_declared_at", "get_declaration",
                               "declarations_for_tenant", "declarations_for_vendor",
                               "declarations_for_system", "declarations_by_risk_posture")]
    assert writes == ["declare"], writes
    for forbidden in ("resolve", "verify", "score", "grade", "rank", "approve", "onboard",
                      "certify", "edit", "update", "delete", "revoke", "contact", "fetch"):
        assert not hasattr(store, forbidden), forbidden


def test_declare_then_read_by_id_tenant_vendor_system_and_posture(store):
    d = declaration()
    assert store.declare(d) is d
    assert store.count() == 1
    assert store.get_declaration(d.declaration_id) == d
    assert store.get_declaration("vdd_nope") is None
    assert store.declarations_for_tenant(tenant_id=TENANT, as_of=T1) == (d,)
    assert store.declarations_for_vendor(tenant_id=TENANT, vendor_ref=VENDOR, as_of=T1) == (d,)
    assert store.declarations_for_vendor(
        tenant_id=TENANT, vendor_ref=OTHER_VENDOR, as_of=T1) == ()
    assert store.declarations_for_system(
        tenant_id=TENANT, system_id=d.system_id, as_of=T1) == (d,)
    assert store.declarations_by_risk_posture(
        tenant_id=TENANT, risk_posture_label=POSTURE.label, as_of=T1) == (d,)
    assert store.declarations_by_risk_posture(
        tenant_id=TENANT, risk_posture_label=OTHER_POSTURE.label, as_of=T1) == ()
    # outside the window a declaration is absent from the answer, never flagged
    assert store.declarations_for_tenant(tenant_id=TENANT, as_of=AFTER_WINDOW) == ()
    assert store.all_declared_at(T1) == (d,)


def test_records_survive_a_restart_of_the_process(path):
    first = SqliteVendorDeclarations(path, tenant_id=TENANT)
    d = declaration()
    first.declare(d)
    first.close()

    second = SqliteVendorDeclarations(path, tenant_id=TENANT)
    try:
        assert second.count() == 1
        assert second.get_declaration(d.declaration_id) == d
    finally:
        second.close()


# --------------------------------------------------------------------------- #
# the tenant boundary
# --------------------------------------------------------------------------- #
def test_a_read_or_write_for_another_tenant_is_a_typed_refusal_never_empty(store):
    other = declaration(binding("hiring-screener", tenant="tenant-b"))
    with pytest.raises(CrossTenantRefused):
        store.declare(other)
    for call in (
        lambda: store.declarations_for_tenant(tenant_id="tenant-b", as_of=T1),
        lambda: store.declarations_for_vendor(
            tenant_id="tenant-b", vendor_ref=VENDOR, as_of=T1),
        lambda: store.declarations_for_system(tenant_id="tenant-b", system_id="x", as_of=T1),
        lambda: store.declarations_by_risk_posture(
            tenant_id="tenant-b", risk_posture_label=POSTURE.label, as_of=T1),
    ):
        with pytest.raises(CrossTenantRefused):
            call()


def test_a_declarations_file_is_never_rebound_to_another_tenant(path, store):
    store.declare(declaration())
    with pytest.raises(CrossTenantRefused, match="never"):
        SqliteVendorDeclarations(path, tenant_id="tenant-b")


# --------------------------------------------------------------------------- #
# append-only: never edited, never deleted
# --------------------------------------------------------------------------- #
def test_a_duplicate_derived_id_is_refused_and_nothing_is_edited(store):
    d = declaration()
    store.declare(d)
    with pytest.raises(DuplicateDeclarationError, match="never edited"):
        store.declare(declaration())
    assert store.count() == 1


def test_an_inadmissible_supersession_is_refused_by_the_package_rule(store):
    first = declaration()
    store.declare(first)

    # names a predecessor that is not recorded
    absent = declaration(policy=OTHER_POLICY, supersedes="vdd_" + "0" * 32)
    with pytest.raises(DeclarationSupersessionError, match="does not exist"):
        store.declare(absent)

    # a different vendor is a new declaration, not a replacement
    elsewhere = declaration(vendor=OTHER_VENDOR, supersedes=first.declaration_id)
    with pytest.raises(DeclarationSupersessionError, match="same vendor"):
        store.declare(elsewhere)

    # an admissible one: same vendor, changed terms
    changed = declaration(policy=OTHER_POLICY, supersedes=first.declaration_id)
    assert store.declare(changed) is changed
    assert store.count() == 2


def test_a_record_altered_outside_the_package_cannot_reconstruct(store, path):
    d = declaration()
    store.declare(d)
    raw = sqlite3.connect(path)
    record = json.loads(raw.execute("SELECT record_json FROM declarations").fetchone()[0])
    record["declaration"]["policy_ref"] = "policy://something-else"
    raw.execute("UPDATE declarations SET record_json = ?",
                (json.dumps(record, sort_keys=True, separators=(",", ":")),))
    raw.commit()
    raw.close()
    with pytest.raises(ContractViolation):
        store.count()


# --------------------------------------------------------------------------- #
# FD-13.4: the posture is recorded, never ordered, ranked or scored
# --------------------------------------------------------------------------- #
def test_the_risk_posture_is_matched_by_exact_text_and_never_ordered(store):
    low = declaration(posture=POSTURE)
    high = declaration(posture=OTHER_POSTURE, policy=OTHER_POLICY)
    store.declare(low)
    store.declare(high)
    # each posture answers only its own exact text: no ordering, no severity, no ranking
    assert store.declarations_by_risk_posture(
        tenant_id=TENANT, risk_posture_label=POSTURE.label, as_of=T1) == (low,)
    assert store.declarations_by_risk_posture(
        tenant_id=TENANT, risk_posture_label=OTHER_POSTURE.label, as_of=T1) == (high,)
    # a near-miss spelling is a different posture, not a fuzzy match
    assert store.declarations_by_risk_posture(
        tenant_id=TENANT, risk_posture_label=POSTURE.label.upper(), as_of=T1) == ()
    # nothing in the answer ranks or approves
    text = json.dumps([declaration_record(d) for d in store.all_declared_at(T1)])
    for forbidden in ("severity", "tier", "rank", "score", "approved_status", "onboard"):
        assert forbidden not in text, forbidden


# --------------------------------------------------------------------------- #
# the posture, and the record round-trip
# --------------------------------------------------------------------------- #
def test_production_mode_refuses_a_non_durable_location(tmp_path):
    for location in (":memory:", "file:declarations?mode=memory"):
        with pytest.raises(DeclarationProductionModeError, match="durable file path"):
            SqliteVendorDeclarations(location, tenant_id=TENANT, production_mode=True)
    ok = SqliteVendorDeclarations(str(tmp_path / "v.sqlite3"), tenant_id=TENANT,
                                  production_mode=True)
    ok.close()


def test_a_blank_tenant_or_path_is_refused_at_construction():
    with pytest.raises(ContractViolation):
        SqliteVendorDeclarations("", tenant_id=TENANT)
    with pytest.raises(ContractViolation):
        SqliteVendorDeclarations(":memory:", tenant_id="")


def test_the_record_round_trips_and_a_tampered_id_is_refused():
    d = declaration(validity=window(T0, days=30))
    record = declaration_record(d)
    assert set(record) == {"declaration", "binding"}
    assert declaration_from_record(record) == d
    # the derived id is re-verified on the way back in
    broken = json.loads(json.dumps(record))
    broken["declaration"]["declaration_id"] = "vdd_" + "0" * 32
    with pytest.raises(ContractViolation, match="derived id"):
        declaration_from_record(broken)
    # the record carries a reference and never a way to reach the vendor
    assert "vendor_ref" in record["declaration"]
    for forbidden in ("address", "endpoint", "credential", "secret", "token", "password",
                      "email", "phone", "pricing", "invoice"):
        assert forbidden not in json.dumps(record), forbidden


def test_the_store_imports_only_sqlite_and_stdlib_reads_no_clock_and_names_no_network():
    import ugence_vendor_dependency

    source = (pathlib.Path(ugence_vendor_dependency.__file__).parent / "durable.py")
    tree = ast.parse(source.read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])
    assert roots <= {"__future__", "json", "sqlite3", "threading", "datetime", "typing"}, roots
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            assert name not in ("now", "utcnow", "today", "time", "monotonic",
                                "perf_counter", "uuid4", "uuid1", "urandom", "random"), name
    text = source.read_text().lower()
    for word in ("http", "socket", "requests", "urllib", "smtp", "webhook"):
        assert word not in text, word
