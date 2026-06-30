"""Tests for the B0 manifest loader / hash verifier / readiness gate.

Verifies (no real B0 run, no alignment, no verdict):
  - the committed frozen manifest loads and ALL pinned sha256 hashes verify,
  - tampering with a pinned hash is detected (NOT ready),
  - the real manifest is NOT ready because T_embed is DEFERRED (categorical
    T_cat is sensitivity-only and cannot substitute as primary),
  - a synthetic manifest with T_embed frozen flips readiness to ready, yet the
    runner STILL returns NOT_RUN (alignment not implemented in loader wiring),
  - the run-record schema loads and the minimal validator accepts a well-formed
    record and rejects a malformed one,
  - run() never reports computed_alignment / verdict under any path.

    python3 experiments/varna_phonetic_alignment/test_manifest_loader.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import manifest as MF   # noqa: E402
import run_b0 as RUN    # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _frozen_embedding(m):
    """Return a deep copy with T_embed marked frozen (SYNTHETIC — no real model)."""
    m2 = copy.deepcopy(m)
    m2["embedding_model_T_embed"].update(
        status="enabled", enabled=True, weights_sha256="deadbeef" * 8)
    return m2


def test_real_manifest_loads_and_hashes_verify():
    m = MF.load_manifest()
    _check("manifest loads", isinstance(m, dict) and m.get("id") == "b0_frozen_artifacts_v1")
    hv = MF.verify_hashes(m)
    _check("all pinned hashes verify against committed artifacts", hv["ok"])
    _check("no missing artifacts", hv["missing"] == [])
    _check("no hash mismatches", hv["mismatches"] == [])
    # design doc + the five named artifacts are all checked
    for name in ("design_doc", "lexicon_wordformation", "iast_ipa_map",
                 "feature_table", "decision_rule", "run_manifest_schema"):
        _check(f"hash checked: {name}", name in hv["checked"] and hv["checked"][name]["match"])


def test_tamper_detected():
    m = copy.deepcopy(MF.load_manifest())
    m["artifacts"]["lexicon_wordformation"]["sha256"] = "0" * 64
    hv = MF.verify_hashes(m)
    _check("tampered hash detected as mismatch", "lexicon_wordformation" in hv["mismatches"])
    _check("tamper => verify not ok", hv["ok"] is False)
    rd = MF.check_readiness(m)
    _check("tamper => not ready", rd["ready"] is False)


def test_real_manifest_not_ready_tembed_deferred():
    m = MF.load_manifest()
    _check("real: embedding_frozen False (DEFERRED)", MF.embedding_frozen(m) is False)
    rd = MF.check_readiness(m)
    _check("real: gate NOT ready", rd["ready"] is False)
    _check("real: reason cites T_embed not frozen",
           any("T_embed" in r for r in rd["reasons"]))
    _check("real: primary encoding is embedding (not categorical)",
           rd["primary_encoding"] == "embedding" == MF.PRIMARY_ENCODING)
    _check("real: categorical is the sensitivity encoding",
           MF.SENSITIVITY_ENCODING == "categorical")


def test_frozen_embedding_makes_ready_but_runner_still_not_run():
    m = _frozen_embedding(MF.load_manifest())
    _check("synthetic: embedding_frozen True", MF.embedding_frozen(m) is True)
    rd = MF.check_readiness(m)
    _check("synthetic: gate ready (hashes ok + T_embed frozen)", rd["ready"] is True)
    _check("synthetic: no readiness reasons", rd["reasons"] == [])
    # but the runner, fed even a ready manifest, must NOT compute alignment:
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(m, f); f.close()
    res = RUN.run(manifest_path=f.name)
    _check("ready manifest: runner still NOT_RUN", res["status"] == "NOT_RUN")
    _check("ready manifest: no alignment computed", res["computed_alignment"] is False)
    _check("ready manifest: no verdict", res["verdict"] is None)
    _check("ready manifest: reason notes alignment not implemented",
           "not implemented" in res["reason"])


def test_runner_default_path_not_run():
    res = RUN.run()
    _check("default: NOT_RUN (T_embed deferred)", res["status"] == "NOT_RUN")
    _check("default: no alignment", res["computed_alignment"] is False)
    _check("default: no verdict", res["verdict"] is None)
    _check("default: readiness attached and not ready", res["readiness"]["ready"] is False)


def test_runner_missing_manifest():
    res = RUN.run(manifest_path="/nonexistent/b0_frozen_artifacts.json")
    _check("missing manifest: NOT_RUN", res["status"] == "NOT_RUN")
    _check("missing manifest: no alignment", res["computed_alignment"] is False)


def test_schema_loads_and_validates_records():
    schema = MF.load_schema()
    _check("schema loads", schema.get("$id") == "b0_run_manifest_schema_v1")
    good = {
        "schema_version": "b0_run_manifest_schema_v1",
        "design_doc_sha256": "x", "frozen_artifacts": {
            "lexicon_wordformation": "a", "iast_ipa_map": "b",
            "ipa_feature_table": "c", "decision_rule": "d"},
        "feature_source": "approved_frozen_ipa_v1", "primary_T_status": "deferred",
        "encodings": ["categorical"], "P_distances": ["hamming"],
        "seeds": {"scramble": 0, "permutation": 0, "bootstrap": 0},
        "Ns": {"scramble_n": 1000, "permutation_n": 10000, "bootstrap_n": 2000},
        "environment": {"python": "3.x", "numpy": "1.x"},
        "run_timestamp_utc": "2026-01-01T00:00:00Z",
        "results": {"status": "NOT_RUN"},
    }
    v = MF.validate_record(good, schema)
    _check("well-formed NOT_RUN record validates", v["valid"])

    bad = copy.deepcopy(good)
    del bad["seeds"]                      # drop a required key
    bad["feature_source"] = "espeak"      # not in enum
    bad["Ns"]["scramble_n"] = 10          # below minimum
    vb = MF.validate_record(bad, schema)
    _check("malformed record rejected", vb["valid"] is False)
    _check("error: missing required reported",
           any("missing required 'seeds'" in e for e in vb["errors"]))
    _check("error: enum violation reported",
           any("feature_source" in e and "enum" in e for e in vb["errors"]))
    _check("error: minimum violation reported",
           any("scramble_n" in e and "minimum" in e for e in vb["errors"]))


def test_no_alignment_symbols_anywhere():
    # the loader/runner must expose no alignment/verdict computation
    _check("manifest module has no mantel/verdict fn",
           not any(hasattr(MF, a) for a in ("mantel_r", "partial_mantel_r", "compute_verdict")))
    _check("run module has no mantel/verdict fn",
           not any(hasattr(RUN, a) for a in ("mantel_r", "partial_mantel_r", "compute_verdict")))


def main():
    print("varna_phonetic_alignment B0 — manifest-loader tests (no run, no verdict)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll B0 manifest-loader tests passed.")


if __name__ == "__main__":
    main()
