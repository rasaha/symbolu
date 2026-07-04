"""Tests for the Track G smoke runner — DRY-RUN + gates only. No LLM, no network, no run.

Proves: dry-run packet generation with zero model calls; candidate shuffle; arm randomization;
hidden-key separation (no arm/target/role/polarity-direction in packets); leak scanner
(surface/varṇa/root/role/arm/polarity-direction/four-sphere); refusal gates (env token + approved
config); base manifest stays gated.

    python3 experiments/primitive_sequence_recovery/test_track_g_smoke_runner.py
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import track_g_smoke_runner as R      # noqa: E402
import track_g_harness as HG          # noqa: E402
import manifest as MF                 # noqa: E402
import run_primitive_recovery as RUN  # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception as e:
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    return False


BUNDLE = R.load_bundle()
PACKETS, HIDDEN = R.build_packets(BUNDLE)


def test_dry_run_no_model_calls():
    report, packets, hidden = R.dry_run()
    _check("packets emitted", report["n_packets"] == len(packets) > 0)
    _check("0 model calls", report["model_calls"] == 0)
    _check("not scored", report["scored"] is False)
    _check("leak clean", report["leak_scan"] == "clean")
    _check("arm randomized", report["arm_randomized"] is True)
    _check("no four-sphere ref", report["no_four_sphere_reference"] is True)
    _check("no heavy libs", not any(m in sys.modules for m in ("torch", "transformers", "openai")))


def test_shuffle_and_anonymization():
    _check("shuffled != authored", all(h["shuffled_order"] != h["authored_order"] for h in HIDDEN.values()))
    _check("opt_ ids only", all(c["candidate_id"].startswith("opt_") for p in PACKETS for c in p["candidates"]))


def test_hidden_key_separate():
    hid = {"true_arm", "target_id", "opt_to_cand", "authored_order", "shuffled_order", "case_id"}
    for p in PACKETS:
        _check(f"{p['packet_id']}: no hidden fields", not (set(p) & hid))
        blob = " ".join(R._facing(p)).lower()
        h = HIDDEN[p["packet_id"]]
        _check(f"{p['packet_id']}: target id absent", h["target_id"].lower() not in blob)


def _one():
    p = copy.deepcopy(PACKETS[0]); h = HIDDEN[p["packet_id"]]
    surf = BUNDLE["words"][h["case_id"].split("-")[0]]["dev_surface_word"]
    authored = [c["candidate_id"] for c in BUNDLE["candidates"][h["case_id"]]["candidates"]]
    return p, surf, authored


def test_clean_packet_passes():
    p, surf, a = _one()
    _check("clean packet passes", R.scan_packet(p, surf, a) is True)


def test_leak_scanner_catches():
    p, surf, a = _one()
    for inject, why in ((f" {surf}", "surface"), (" moha", "root"), (" kha", "varna"),
                        (" target", "role"), (" expected_pole", "polarity-direction"),
                        (" four_sphere", "four-sphere"), (" boundary onto arm A", "arm-label"),
                        (f" {a[0]}", "authored-id")):
        q = copy.deepcopy(p); q["premise"] += inject
        _check(f"catches {why} leak", _raises(lambda q=q: R.scan_packet(q, surf, a), R.LeakDetected))


def test_refusal_gates():
    os.environ.pop(R.APPROVAL_ENV, None)
    _check("refuses without env token",
           _raises(lambda: R.run_real_smoke_pilot(approval_config="x"), R.RefusedRun))
    os.environ[R.APPROVAL_ENV] = R.APPROVAL_TOKEN
    try:
        _check("refuses without config",
               _raises(lambda: R.run_real_smoke_pilot(approval_config=None), R.RefusedRun))
        # invalid config (run_enabled false) refuses via load_approval_config
        bad = _HERE / "toy_fixtures" / "_tmp_g_badcfg.json"
        bad.write_text(json.dumps({"config_type": "track_g_smoke_approved_run_config",
                                   "run_enabled": False, "approval_status": "APPROVED",
                                   "scorer_model": "m", "four_sphere_integrated": False,
                                   "approval_record": {"date": "d", "signature": "s"}}), encoding="utf-8")
        try:
            _check("refuses invalid config (run_enabled false)",
                   _raises(lambda: R.load_approval_config(str(bad)), R.RefusedRun))
        finally:
            bad.unlink()
    finally:
        os.environ.pop(R.APPROVAL_ENV, None)


def test_approved_config_accepted_base_manifest_untouched():
    cfg_path = _HERE / "track_g_smoke_approved_run_config.json"
    if not cfg_path.exists():
        _check("approved config present", False)
    os.environ[R.APPROVAL_ENV] = R.APPROVAL_TOKEN
    try:
        res = R.run_real_smoke_pilot(approval_config=str(cfg_path))
        _check("valid config emits packets (no model call)",
               res["status"] == "PACKETS_EMITTED_FOR_EXTERNAL_SCORING" and len(res["packets"]) == 90)
    finally:
        os.environ.pop(R.APPROVAL_ENV, None)
    man = json.loads((_HERE / "track_g_smoke_manifest.json").read_text())
    _check("base manifest still run_enabled:false", man["run_enabled"] is False)
    _check("base manifest still NOT_APPROVED", man["approval_status"] == "NOT_APPROVED")


def test_no_four_sphere_load():
    src = (_HERE / "track_g_smoke_runner.py").read_text(encoding="utf-8")
    _check("runner never loads four-sphere lexicon", "track_e_varna_sphere_lexicon" not in src)


def test_guardrails():
    _check("psr runner NOT_RUN", RUN.run()["status"] == "NOT_RUN")
    _check("global manifest NOT_READY", MF.check_readiness(_HERE / "frozen")["status"] == "NOT_READY")
    _check("base G manifest gated",
           BUNDLE["manifest"]["run_enabled"] is False and BUNDLE["manifest"]["approval_status"] == "NOT_APPROVED")
    _check("Stage A not imported", not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("track_g_smoke_runner — dry-run + gate tests (no LLM, no run)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Track G smoke-runner tests passed.")


if __name__ == "__main__":
    main()
