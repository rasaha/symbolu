"""The act: append one entry, get back the reference naming it."""

from __future__ import annotations

import dataclasses
import sqlite3

import pytest

from ugence_governance_contracts.api import AuditReference

from ugence_control_plane_root import (
    STORE_REF,
    AuditLedger,
    ContractViolation,
    LedgerEntry,
    LedgerIntegrityError,
    SchemaVersionMismatch,
)

from _fixtures import T0, T1, T2, TENANT, append, entry, ledger


def test_appending_returns_a_reference_that_names_the_entry():
    log = ledger()
    reference = append(log, entry())

    assert isinstance(reference, AuditReference)
    assert reference.tenant_id == TENANT
    assert reference.store_ref == STORE_REF
    assert reference.entry_ref == f"{TENANT}/1"
    assert len(reference.entry_digest) == 64
    assert log.entry_count() == 1


def test_the_reference_carries_the_instant_the_caller_supplied():
    """Not the instant the row was written — this package reads no clock."""

    reference = append(ledger(), entry(at=T1))
    assert reference.recorded_at == T1


def test_two_equal_entries_at_different_offsets_digest_equally():
    """UTC normalization, so an offset is a spelling and not a difference."""

    import datetime as dt

    utc = entry(at=dt.datetime(2026, 3, 1, 9, 0, tzinfo=dt.timezone.utc))
    plus_two = entry(at=dt.datetime(2026, 3, 1, 11, 0,
                                    tzinfo=dt.timezone(dt.timedelta(hours=2))))
    assert utc.content_digest() == plus_two.content_digest()


def test_each_tenant_gets_its_own_chain():
    log = ledger()
    first = append(log, entry())
    other = append(log, entry(tenant="tenant-b"))

    assert first.entry_ref == "tenant-a/1"
    assert other.entry_ref == "tenant-b/2"     # row ids are global
    assert log.entry_count(tenant_id=TENANT) == 1
    assert log.entry_count(tenant_id="tenant-b") == 1
    assert log.verify_chain(tenant_id=TENANT)
    assert log.verify_chain(tenant_id="tenant-b")


def test_a_chain_links_each_entry_to_the_one_before_it():
    log = ledger()
    for instant in (T0, T1, T2):
        append(log, entry(at=instant))
    assert log.entry_count(tenant_id=TENANT) == 3
    assert log.verify_chain(tenant_id=TENANT)


def test_an_empty_chain_verifies():
    """A tenant with nothing recorded is consistent, not broken."""

    assert ledger().verify_chain(tenant_id="tenant-nobody")


def test_the_same_content_appended_twice_is_two_entries_with_different_digests():
    """Position is part of the record: an entry's chain digest binds where it sits,
    so a replayed append is visible rather than idempotent."""

    log = ledger()
    first = append(log, entry())
    second = append(log, entry())
    assert first.entry_digest != second.entry_digest
    assert log.verify_chain(tenant_id=TENANT)


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #
def test_the_ledger_refuses_anything_that_is_not_an_entry():
    log = ledger()
    with pytest.raises(ContractViolation, match="must be a LedgerEntry"):
        log.append({"tenant_id": TENANT}, reference_factory=AuditReference)


def test_the_ledger_refuses_a_factory_it_cannot_call():
    log = ledger()
    with pytest.raises(ContractViolation, match="must be callable"):
        log.append(entry(), reference_factory="AuditReference")


def test_a_blank_tenant_is_refused_when_counting_or_verifying():
    log = ledger()
    for blank in ("", "   "):
        with pytest.raises(ContractViolation):
            log.entry_count(tenant_id=blank)
        with pytest.raises(ContractViolation):
            log.verify_chain(tenant_id=blank)


def test_a_store_written_at_another_schema_version_is_refused_not_migrated(tmp_path):
    path = str(tmp_path / "foreign.sqlite")
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    connection.execute("INSERT INTO meta VALUES ('schema_version', 'someone.else/9.9')")
    connection.commit()
    connection.close()

    with pytest.raises(SchemaVersionMismatch, match="refused rather than migrated"):
        AuditLedger(path)


# --------------------------------------------------------------------------- #
# Append-only, enforced by the database rather than by convention
# --------------------------------------------------------------------------- #
def test_the_store_itself_refuses_an_update_or_a_delete(tmp_path):
    path = str(tmp_path / "ledger.sqlite")
    log = AuditLedger(path)
    append(log, entry())

    raw = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        raw.execute("UPDATE ledger_entries SET kind='rewritten'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        raw.execute("DELETE FROM ledger_entries")
    raw.close()
    log.close()


def test_a_row_edited_around_the_triggers_is_detected(tmp_path):
    """Tamper-evident: the chain notices, which is the whole claim — and no more."""

    path = str(tmp_path / "ledger.sqlite")
    log = AuditLedger(path)
    append(log, entry())
    append(log, entry(at=T1))
    log.close()

    raw = sqlite3.connect(path)
    raw.execute("DROP TRIGGER ledger_no_update")
    raw.execute("UPDATE ledger_entries SET content_digest=? WHERE tenant_seq=0",
                ("0" * 64,))
    raw.commit()
    raw.close()

    reopened = AuditLedger(path)
    with pytest.raises(LedgerIntegrityError, match="does not match its digest"):
        reopened.verify_chain(tenant_id=TENANT)


def test_entries_survive_reopening_the_store(tmp_path):
    path = str(tmp_path / "ledger.sqlite")
    log = AuditLedger(path)
    append(log, entry())
    append(log, entry(at=T1))
    log.close()

    reopened = AuditLedger(path)
    assert reopened.entry_count(tenant_id=TENANT) == 2
    assert reopened.verify_chain(tenant_id=TENANT)
    # and the chain continues rather than restarting
    reference = append(reopened, entry(at=T2))
    assert reference.entry_ref == f"{TENANT}/3"
    assert reopened.verify_chain(tenant_id=TENANT)


# --------------------------------------------------------------------------- #
# The refusals a mutation sweep found uncovered
# --------------------------------------------------------------------------- #
def test_a_non_string_tenant_is_refused_before_it_reaches_sql():
    """Not merely blank — the wrong *type*, which would otherwise be bound as a
    SQL parameter and silently match nothing."""

    log = ledger()
    append(log, entry())

    for bad in (7, b"tenant-a", ["tenant-a"]):
        with pytest.raises(ContractViolation, match="must be a string"):
            log.entry_count(tenant_id=bad)
        with pytest.raises(ContractViolation, match="must be a string"):
            log.verify_chain(tenant_id=bad)

    # None is not a bad tenant on entry_count: it is the documented "every tenant"
    # sentinel. verify_chain has no such sentinel — a chain is always one tenant's.
    assert log.entry_count(tenant_id=None) == log.entry_count() == 1
    with pytest.raises(ContractViolation, match="must be a string"):
        log.verify_chain(tenant_id=None)


def test_a_broken_link_is_detected_even_when_each_row_digests_correctly(tmp_path):
    """The other half of chain verification.

    Recomputing each row's own digest is not enough: a row whose digest is perfectly
    valid can still be spliced out, leaving the survivors' links pointing at an
    entry that is no longer there. That is a different defect from a doctored row,
    and it needs its own check.
    """

    path = str(tmp_path / "ledger.sqlite")
    log = AuditLedger(path)
    for instant in (T0, T1, T2):
        append(log, entry(at=instant))
    log.close()

    raw = sqlite3.connect(path)
    raw.execute("DROP TRIGGER ledger_no_delete")
    raw.execute("DELETE FROM ledger_entries WHERE tenant_seq=1")   # splice the middle
    raw.commit()
    raw.close()

    reopened = AuditLedger(path)
    with pytest.raises(LedgerIntegrityError, match="chain breaks at position"):
        reopened.verify_chain(tenant_id=TENANT)


def test_a_failed_append_rolls_back_and_leaves_no_partial_entry(tmp_path):
    """The append is one transaction. If the reference factory or the insert
    raises, nothing may remain half-written."""

    path = str(tmp_path / "ledger.sqlite")
    log = AuditLedger(path)
    append(log, entry())

    def exploding_factory(**kwargs):
        raise RuntimeError("the caller's contract blew up")

    with pytest.raises(RuntimeError, match="blew up"):
        log.append(entry(at=T1), reference_factory=exploding_factory)

    # The factory runs after the commit, so that entry IS recorded — which is the
    # honest behaviour to pin, not to pretend otherwise.
    assert log.entry_count(tenant_id=TENANT) == 2
    assert log.verify_chain(tenant_id=TENANT)

    # But a failure *inside* the transaction leaves nothing behind.
    broken = AuditLedger(path)
    broken._conn.execute("DROP TABLE ledger_entries")
    with pytest.raises(sqlite3.OperationalError):
        broken.append(entry(at=T2), reference_factory=AuditReference)
