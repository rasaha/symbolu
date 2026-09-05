"""The entry record: what it refuses, and what it will not let you fake."""

from __future__ import annotations

import dataclasses
import pickle

import pytest

from ugence_control_plane_root import ContractViolation, LedgerEntry

from _fixtures import T0, TENANT, entry


def test_an_entry_requires_a_tenant_a_kind_and_an_author():
    for blank in ("", "   "):
        for field in ("tenant_id", "kind", "recorded_by"):
            with pytest.raises(ContractViolation, match=field):
                dataclasses.replace(entry(), **{field: blank})


def test_an_entry_refuses_a_naive_instant():
    import datetime as dt

    with pytest.raises(ContractViolation, match="timezone-aware"):
        entry(at=dt.datetime(2026, 3, 1, 9, 0))
    with pytest.raises(ContractViolation, match="must be a datetime"):
        entry(at="2026-03-01T09:00:00Z")


def test_an_entry_refuses_a_payload_its_digest_could_not_cover():
    """The digest is over the payload's canonical bytes, so a value that cannot be
    canonicalized cannot be recorded — rather than recorded and silently unhashed."""

    with pytest.raises(ContractViolation, match="must be a mapping"):
        entry(payload=["not", "a", "mapping"])
    with pytest.raises(ContractViolation, match="keys must be strings"):
        entry(payload={1: "one"})
    with pytest.raises(ContractViolation, match="JSON-serializable"):
        entry(payload={"when": object()})


def test_an_empty_payload_is_allowed():
    """An entry may record that something happened and nothing more."""

    assert entry(payload={}).payload == {}
    assert len(entry(payload={}).content_digest()) == 64


def test_the_correlation_id_is_optional_but_must_be_a_string():
    assert entry().correlation_id == ""
    assert entry(correlation="corr-1").correlation_id == "corr-1"
    with pytest.raises(ContractViolation, match="correlation_id must be a string"):
        entry(correlation=7)


def test_the_digest_covers_every_field():
    """Change any field and the digest moves; that is what binding means."""

    base = entry()
    seen = {base.content_digest()}
    for field, value in (("tenant_id", "tenant-b"), ("kind", "incident.closed"),
                         ("recorded_by", "operator-2"), ("correlation_id", "corr-9")):
        moved = dataclasses.replace(base, **{field: value}).content_digest()
        assert moved not in seen, field
        seen.add(moved)
    payload_moved = dataclasses.replace(base, payload={"subject_ref": "other"})
    assert payload_moved.content_digest() not in seen


def test_the_invariants_cannot_be_inherited_away():
    with pytest.raises(TypeError, match="may not be subclassed"):
        class _Evil(LedgerEntry):  # pragma: no cover - the body never runs
            def __post_init__(self):
                pass


def test_an_invalid_entry_cannot_be_revived_from_a_pickle():
    """``pickle`` never calls ``__init__``, so ``__setstate__`` re-runs the rules."""

    good = entry()
    assert pickle.loads(pickle.dumps(good)) == good

    doctored = dict(good.__dict__, tenant_id="")
    with pytest.raises(ContractViolation, match="tenant_id"):
        object.__new__(LedgerEntry).__setstate__(doctored)


def test_the_entry_reads_no_clock_and_holds_no_default_instant():
    """``recorded_at`` has no default: a caller must say when, every time."""

    fields = {f.name: f for f in dataclasses.fields(LedgerEntry)}
    assert fields["recorded_at"].default is dataclasses.MISSING
    assert fields["recorded_at"].default_factory is dataclasses.MISSING
