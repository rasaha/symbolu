"""The records are located by exactly one rule or refused: never a parent, sibling or
unrelated checkout; an absent or ambiguous root fails closed; only the intended schema."""

from __future__ import annotations

import json
import os
import pathlib
import shutil

import pytest

from ugence_model_egress_validation import RecordsNotLocated, load_records, records_directory
from ugence_model_egress_validation import drift


def _make_checkout(root: pathlib.Path, *, with_records: bool, schema: str = "model-egress-unit.live-provider-designation.v1") -> pathlib.Path:
    (root / ".git").mkdir(parents=True)
    unit = root / "packages" / "integration" / "model-egress-unit"
    if with_records:
        unit.mkdir(parents=True)
        src = records_directory()
        d = json.loads((src / "MEU_LIVE_PROVIDER_DESIGNATION.json").read_text(encoding="utf-8"))
        d["schema"] = schema
        d["_marker"] = str(root)
        (unit / "MEU_LIVE_PROVIDER_DESIGNATION.json").write_text(json.dumps(d), encoding="utf-8")
        shutil.copy(src / "MEU_LIVE_VALIDATION.json", unit / "MEU_LIVE_VALIDATION.json")
    return unit


@pytest.fixture
def installed_unit(monkeypatch):
    """Pretend the unit is installed (no source-checkout records beside it)."""

    monkeypatch.setattr(drift, "_unit_source_records", lambda: None)


def test_the_intended_checkout_is_the_one_containing_the_working_directory(tmp_path, monkeypatch, installed_unit):
    unit = _make_checkout(tmp_path / "intended", with_records=True)
    nested = tmp_path / "intended" / "packages" / "integration" / "model-egress-validation"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert records_directory() == unit.resolve()
    assert load_records()["designation"]["_marker"] == str(tmp_path / "intended")


def test_a_parent_checkout_is_never_consulted(tmp_path, monkeypatch, installed_unit):
    _make_checkout(tmp_path / "parent", with_records=True)
    inner = _make_checkout(tmp_path / "parent" / "vendor" / "inner", with_records=False)
    monkeypatch.chdir(inner.parents[2])  # inside the inner checkout, which has no records
    with pytest.raises(RecordsNotLocated, match="not located"):
        records_directory()


def test_a_sibling_or_unrelated_checkout_is_never_consulted(tmp_path, monkeypatch, installed_unit):
    _make_checkout(tmp_path / "sibling", with_records=True)
    unrelated = _make_checkout(tmp_path / "unrelated", with_records=False)
    monkeypatch.chdir(unrelated.parents[2])
    with pytest.raises(RecordsNotLocated):
        records_directory()
    monkeypatch.chdir(tmp_path)  # no checkout at all above
    with pytest.raises(RecordsNotLocated):
        records_directory()


def test_an_ambiguous_root_fails_closed_and_records_can_be_named_explicitly(tmp_path, monkeypatch):
    other = _make_checkout(tmp_path / "other", with_records=True)
    source = records_directory()  # the unit's own source checkout, from this test run
    monkeypatch.setattr(drift, "_unit_source_records", lambda: source)
    monkeypatch.chdir(other.parents[2])
    with pytest.raises(RecordsNotLocated, match="ambiguous"):
        records_directory()
    assert load_records(other)["designation"]["_marker"] == str(tmp_path / "other")
    assert "_marker" not in load_records(source)["designation"]


def test_a_directory_with_the_wrong_schema_or_a_missing_record_is_refused(tmp_path):
    wrong = _make_checkout(tmp_path / "wrong", with_records=True, schema="something-else.v9")
    with pytest.raises(RecordsNotLocated, match="schema"):
        load_records(wrong)
    partial = tmp_path / "partial"
    partial.mkdir()
    shutil.copy(records_directory() / "MEU_LIVE_VALIDATION.json", partial / "MEU_LIVE_VALIDATION.json")
    with pytest.raises(RecordsNotLocated, match="both records"):
        load_records(partial)


def test_loading_is_read_only(tmp_path):
    unit = _make_checkout(tmp_path / "ro", with_records=True)
    for name in ("MEU_LIVE_PROVIDER_DESIGNATION.json", "MEU_LIVE_VALIDATION.json"):
        os.chmod(unit / name, 0o444)
    assert load_records(unit)["validation"]["meu_live_status"] == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"
