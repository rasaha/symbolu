"""Tests for the machine-readable Guna rule-pack controls (Section 12).

These tests validate the DRAFT, NON-EXECUTABLE pack's integrity and prove the
fail-closed guards: the executable flag cannot be raised, parihara rules cannot
be silently enabled, a manual case cannot be marked verified without a frozen
edition, and any edit to a checksummed file is detected as drift. They import
the validator directly; they never compute a Guna score.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil

import pytest

_PRODUCT_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PACK = _PRODUCT_ROOT / "rules" / "ashtakoota_muhurta_chintamani_raman_v1"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_rule_pack", _PRODUCT_ROOT / "scripts" / "validate_rule_pack.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _repoint(mod, root: pathlib.Path):
    """Point the validator's module constants at a copied ``root`` product tree."""
    pack = root / "rules" / "ashtakoota_muhurta_chintamani_raman_v1"
    mod.PRODUCT_ROOT = root
    mod.PACK_DIR = pack
    mod.SOURCES = root / "rules" / "sources" / "GUNA_SOURCE_MANIFEST.json"
    mod.MANUAL = root / "rules" / "fixtures" / "guna_manual_cases.json"


@pytest.fixture
def sandbox(tmp_path):
    """A writable copy of the real rules/ tree plus a repointed validator."""
    shutil.copytree(_PRODUCT_ROOT / "rules", tmp_path / "rules")
    mod = _load_validator()
    _repoint(mod, tmp_path)
    return tmp_path, mod


def _write_json(path: pathlib.Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n")


# --- Baseline: the real, committed pack is internally consistent. --------------

def test_validator_passes_on_committed_pack():
    mod = _load_validator()
    errors = mod.validate()
    assert errors == [], f"unexpected validation errors: {errors}"


def test_executable_invariant_holds():
    manifest = json.loads((_PACK / "manifest.json").read_text())
    control = json.loads((_PACK / "pack_control.json").read_text())
    assert manifest["executable"] is False
    inv = control["executable_invariant"]
    assert inv["manifest_executable_flag"] is False
    assert inv["derived_executable"] is False
    assert inv["blockers"], "there must be recorded blockers this phase"
    assert control["counts"]["approved_rules"] == 0


def test_all_parihara_disabled():
    par = json.loads((_PACK / "parihara.json").read_text())
    assert par["rules"] and all(r["enabled"] is False for r in par["rules"])


def test_manual_coverage_complete_and_unverified():
    manual = json.loads((_PACK.parent / "fixtures" / "guna_manual_cases.json").read_text())
    coverage = {k for k in manual["required_category_coverage"] if not k.startswith("_")}
    assert len(coverage) == 22
    assert all(c["reviewer_status"] != "MANUAL_VERIFIED" for c in manual["cases"])


def test_no_source_is_frozen():
    src = json.loads((_PACK.parent / "sources" / "GUNA_SOURCE_MANIFEST.json").read_text())
    assert src["overall_status"] == "PENDING_ACQUISITION"
    assert all(not s["review_status"].startswith("FROZEN") for s in src["sources"])


# --- Fail-closed tamper guards. ------------------------------------------------

def test_checksum_drift_detected(sandbox):
    root, mod = sandbox
    manifest = root / "rules" / "ashtakoota_muhurta_chintamani_raman_v1" / "manifest.json"
    manifest.write_text(manifest.read_text() + "\n")  # whitespace change => new digest
    errors = mod.validate()
    assert any("checksum drift" in e for e in errors), errors


def test_enabling_a_parihara_is_rejected(sandbox):
    root, mod = sandbox
    p = root / "rules" / "ashtakoota_muhurta_chintamani_raman_v1" / "parihara.json"
    doc = json.loads(p.read_text())
    doc["rules"][0]["enabled"] = True
    _write_json(p, doc)
    errors = mod.validate()
    assert any("enabled must be false" in e for e in errors), errors


def test_flipping_manifest_executable_is_rejected(sandbox):
    root, mod = sandbox
    m = root / "rules" / "ashtakoota_muhurta_chintamani_raman_v1" / "manifest.json"
    doc = json.loads(m.read_text())
    doc["executable"] = True
    _write_json(m, doc)
    errors = mod.validate()
    assert any("executable must be false" in e for e in errors), errors


def test_manual_verified_without_freeze_is_rejected(sandbox):
    root, mod = sandbox
    f = root / "rules" / "fixtures" / "guna_manual_cases.json"
    doc = json.loads(f.read_text())
    doc["cases"][0]["reviewer_status"] = "MANUAL_VERIFIED"
    _write_json(f, doc)
    errors = mod.validate()
    assert any("MANUAL_VERIFIED not allowed" in e for e in errors), errors


def test_duplicate_rule_id_is_rejected(sandbox):
    root, mod = sandbox
    t = root / "rules" / "ashtakoota_muhurta_chintamani_raman_v1" / "source_traceability.json"
    doc = json.loads(t.read_text())
    doc["rules"].append(dict(doc["rules"][0]))  # duplicate rule_id
    _write_json(t, doc)
    errors = mod.validate()
    assert any("duplicate rule_id" in e for e in errors), errors


def test_out_of_range_matrix_value_is_rejected(sandbox):
    root, mod = sandbox
    y = root / "rules" / "ashtakoota_muhurta_chintamani_raman_v1" / "yoni.json"
    doc = json.loads(y.read_text())
    doc["scoring"]["yoni_score_matrix"]["0"]["1"] = 99  # > max 4
    _write_json(y, doc)
    errors = mod.validate()
    assert any("out of range" in e for e in errors), errors


def test_duplicate_json_key_is_rejected(sandbox):
    root, mod = sandbox
    m = root / "rules" / "ashtakoota_muhurta_chintamani_raman_v1" / "manifest.json"
    # Inject a literal duplicate key that json.loads with our hook must reject.
    text = m.read_text().replace('"total_max": 36,', '"total_max": 36,\n  "total_max": 37,', 1)
    m.write_text(text)
    errors = mod.validate()
    assert any("duplicate key" in e for e in errors), errors
