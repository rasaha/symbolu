"""Determinism + integrity tests for the varṇa provenance register (Part E Step 1). NO network, NO model.

Proves: all 34 varṇas classified, 68 poles, byte-identical repeat runs, every status is one of the eight allowed,
the readiness verdict is one of the three allowed, and the frozen sources are untouched (additive-only register).

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. B1.4b′ NULL_RETURN_BOTTOM; Track B blocked.
"""
import hashlib
import json
import pathlib

import b1_varna_provenance_register as R

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "varna_provenance_register"
ALLOWED_STATUS = {"PRIMARY_ATTESTED", "SECONDARY_ATTESTED", "INFERRED", "AUTHORED_PROVISIONAL",
                  "CONTRADICTORY", "MISSING", "OUT_OF_SCOPE", "UNRESOLVED"}
ALLOWED_VERDICT = {"READY_FOR_INVENTORY_DECISION", "BLOCKED_BY_PROVENANCE_GAPS", "BLOCKED_BY_SOURCE_CONTRADICTIONS"}


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def test_all_34_and_68_poles():
    reg, _ = R.build()
    assert len(reg["varnas"]) == 34
    assert reg["validation"]["all_34_accounted"] is True
    assert reg["validation"]["n_poles_total"] == 68


def test_statuses_and_verdict_allowed():
    reg, _ = R.build()
    for rec in reg["varnas"]:
        for side in ("binding", "liberating"):
            assert rec["poles"][side]["provenance_status"] in ALLOWED_STATUS
    for rule in reg["rules"]:
        assert rule["provenance_status"] in ALLOWED_STATUS
    assert reg["readiness_verdict"] in ALLOWED_VERDICT


def test_repeat_run_byte_identical():
    R.build(); h1 = {f.name: _sha(f) for f in OUT.glob("*")}
    R.build(); h2 = {f.name: _sha(f) for f in OUT.glob("*")}
    assert h1 == h2


def test_missing_inventory_present():
    reg, _ = R.build()
    for cat in ("vowels", "anusvara", "visarga"):
        assert reg["missing_inventory"][cat]["status"] == "MISSING"


def test_no_network_or_model_imports():
    src = (HERE / "b1_varna_provenance_register.py").read_text()
    for banned in ("import torch", "import transformers", "openai", "\nimport requests", "HfApi", "SentenceTransformer"):
        assert banned not in src


def test_frozen_table_unchanged():
    # the register reads the frozen table but must never modify it
    assert (HERE / "frozen" / "varna_polarity_table_v3.json").exists()
    d = json.load(open(HERE / "frozen" / "varna_polarity_table_v3.json", encoding="utf-8"))
    assert len(d["varnas"]) == 34
