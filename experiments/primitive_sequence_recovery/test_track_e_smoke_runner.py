"""Tests for the Track E smoke-pilot runner — DRY-RUN + gates only. No LLM, no network, no run.

Proves: refusal gates (run_enabled/approval), dry-run packet generation with zero model calls,
candidate shuffle, hidden-key separation, the leak scanner (surface / varṇa / root / arm / role),
scorer-output ingestion validation (malformed / unknown / duplicate), that only allowed Track E
labels can be emitted, and that four-sphere JSON is never referenced. Synthetic scorer outputs are
constructed in-test to exercise the metric path; no real scoring occurs.

    python3 experiments/primitive_sequence_recovery/test_track_e_smoke_runner.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import track_e_smoke_runner as R      # noqa: E402
import track_e_harness as H           # noqa: E402
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
HKEY = {h["packet_id"]: h for h in HIDDEN}


# ----------------------------------------------------------------- refusal gates ----
def test_refuses_when_run_enabled_false():
    _check("run_real refuses on the shipped bundle (run_enabled:false)",
           _raises(lambda: R.run_real_smoke_pilot(), R.RefusedRun))


def test_refuses_when_not_approved():
    man = dict(BUNDLE["manifest"]); man["run_enabled"] = True   # in-memory only; file untouched
    man["approval_status"] = "NOT_APPROVED"
    fails = R.gate_failures(man, BUNDLE["seeds"], {"generator_model": "g", "scorer_model": "s",
             "approval_signature": "x", "approval_date": "2026-07-02"}, leak_ok=True, shuffle_ok=True)
    _check("approval gate blocks when not APPROVED", "approval_status is not APPROVED" in fails)


def test_approval_config_accepted_base_manifest_untouched():
    cfg_path = _HERE / "track_e_smoke_approved_run_config.json"
    cfg = R.load_approval_config(cfg_path)
    _check("approved config valid: run_enabled true", cfg["run_enabled"] is True)
    _check("approved config valid: APPROVED", cfg["approval_status"] == "APPROVED")
    res = R.run_real_smoke_pilot(approval_config=str(cfg_path))
    _check("valid config emits packets (no model call)",
           res["status"] == "PACKETS_EMITTED_FOR_EXTERNAL_SCORING" and len(res["packets"]) == 108)
    man = R.load_manifest()   # re-read base manifest from disk
    _check("BASE smoke manifest still run_enabled:false", man["run_enabled"] is False)
    _check("BASE smoke manifest still NOT_APPROVED", man["approval_status"] == "NOT_APPROVED")


def test_invalid_approval_config_refuses():
    base = R.load_approval_config(_HERE / "track_e_smoke_approved_run_config.json")
    def bad(**over):
        c = copy.deepcopy(base); c.update(over); return c
    _check("run_enabled false -> refuse",
           _raises(lambda: R.run_real_smoke_pilot(approval_config=bad(run_enabled=False)), R.RefusedRun))
    _check("not APPROVED -> refuse",
           _raises(lambda: R.run_real_smoke_pilot(approval_config=bad(approval_status="NOT_APPROVED")),
                   R.RefusedRun))
    _check("generator==scorer -> refuse",
           _raises(lambda: R.run_real_smoke_pilot(approval_config=bad(scorer_model=base["generator_model"])),
                   R.RefusedRun))
    _check("wrong packet count -> refuse",
           _raises(lambda: R.run_real_smoke_pilot(approval_config=bad(expected_packet_count=50)),
                   R.RefusedRun))
    _check("four_sphere_integrated true -> refuse",
           _raises(lambda: R.run_real_smoke_pilot(approval_config=bad(four_sphere_integrated=True)),
                   R.RefusedRun))


def test_gates_pass_only_under_full_approval():
    man = dict(BUNDLE["manifest"]); man["run_enabled"] = True; man["approval_status"] = "APPROVED"
    approval = {"generator_model": "gen-x", "scorer_model": "score-y",
                "approval_signature": "reviewer", "approval_date": "2026-07-02"}
    fails = R.gate_failures(man, BUNDLE["seeds"], approval, leak_ok=True, shuffle_ok=True)
    _check("all gates pass only with a complete approved config", fails == [])
    # missing model / seed / signature each re-block
    _check("missing scorer model re-blocks",
           "scorer_model not set" in R.gate_failures(man, BUNDLE["seeds"],
               {**approval, "scorer_model": ""}, leak_ok=True, shuffle_ok=True))
    _check("failed leak scan re-blocks",
           "leak scan did not pass" in R.gate_failures(man, BUNDLE["seeds"], approval,
               leak_ok=False, shuffle_ok=True))


# --------------------------------------------------------------- dry-run packets ----
def test_dry_run_no_model_calls():
    report, packets, hidden = R.dry_run()
    _check("dry-run produced packets", report["n_packets"] == len(packets) > 0)
    _check("dry-run made zero model calls", report["model_calls"] == 0)
    _check("dry-run did not score", report["scored"] is False)
    _check("dry-run leak scan clean", report["leak_scan"] == "clean")
    _check("no LLM/network/ML libs imported",
           not any(m in sys.modules for m in ("openai", "anthropic", "requests", "httpx",
                                              "torch", "transformers", "urllib.request")))


def test_candidate_shuffle_changes_authored_order():
    _check("every packet's shuffled order differs from authored",
           all(h["shuffled_order"] != h["authored_order"] for h in HIDDEN))
    _check("packets use anonymized opt_ ids only",
           all(c["candidate_id"].startswith("opt_") for p in PACKETS for c in p["candidates"]))


def test_hidden_key_is_separate():
    hidden_only = {"correct_candidate_id", "true_arm", "opt_to_cand", "authored_order",
                   "shuffled_order", "case_id", "barnum_variant"}
    for p in PACKETS:
        _check(f"{p['packet_id']}: no hidden fields in packet",
               not (set(p) & hidden_only))
        blob = " ".join(R._scorer_facing_strings(p)).lower()
        h = HKEY[p["packet_id"]]
        _check(f"{p['packet_id']}: correct candidate id absent from packet",
               h["correct_candidate_id"].lower() not in blob)
        _check(f"{p['packet_id']}: true arm absent from packet",
               f"\"{h['true_arm'].lower()}\"" not in blob)
    _check("hidden key carries the answer + arm for every packet",
           all(HKEY[p["packet_id"]]["correct_candidate_id"] and HKEY[p["packet_id"]]["true_arm"]
               for p in PACKETS))


# ------------------------------------------------------------------ leak scanner ----
def _one_packet():
    p = copy.deepcopy(PACKETS[0])
    h = HKEY[p["packet_id"]]
    surf = BUNDLE["words"][h["case_id"]]["dev_surface_word"]
    authored = [c["candidate_id"] for c in BUNDLE["candidates"][h["case_id"]]["candidates"]]
    return p, surf, authored


def test_clean_packet_passes_scan():
    p, surf, authored = _one_packet()
    _check("a clean packet passes the leak scan",
           R.scan_packet(p, surface_word=surf, authored_ids=authored) is True)


def test_leak_scanner_catches_surface_word():
    p, surf, authored = _one_packet()
    p["premise"] += f" (the word is {surf})"
    _check("surface-word leak caught",
           _raises(lambda: R.scan_packet(p, surface_word=surf, authored_ids=authored), R.LeakDetected))


def test_leak_scanner_catches_varna_and_root():
    p, surf, authored = _one_packet()
    q = copy.deepcopy(p); q["premise"] += " kha"           # a varṇa key
    _check("varṇa-key leak caught",
           _raises(lambda: R.scan_packet(q, surface_word=surf, authored_ids=authored), R.LeakDetected))
    r = copy.deepcopy(p); r["candidates"][0]["text"] += " moha"   # a root name
    _check("root-name leak caught",
           _raises(lambda: R.scan_packet(r, surface_word=surf, authored_ids=authored), R.LeakDetected))


def test_leak_scanner_catches_arm_labels():
    p, surf, authored = _one_packet()
    q = copy.deepcopy(p); q["premise"] += " boundary_real"
    _check("arm-token leak caught",
           _raises(lambda: R.scan_packet(q, surface_word=surf, authored_ids=authored), R.LeakDetected))
    r = copy.deepcopy(p); r["premise"] += " true_arm: A"
    _check("arm-code leak caught",
           _raises(lambda: R.scan_packet(r, surface_word=surf, authored_ids=authored), R.LeakDetected))


def test_leak_scanner_catches_roles_and_four_sphere():
    p, surf, authored = _one_packet()
    q = copy.deepcopy(p); q["premise"] += " context_correct"
    _check("candidate-role leak caught",
           _raises(lambda: R.scan_packet(q, surface_word=surf, authored_ids=authored), R.LeakDetected))
    r = copy.deepcopy(p); r["premise"] += " four_sphere"
    _check("four-sphere reference caught",
           _raises(lambda: R.scan_packet(r, surface_word=surf, authored_ids=authored), R.LeakDetected))
    s = copy.deepcopy(p); s["premise"] += " " + authored[0]      # authored cand_ id
    _check("authored candidate id leak caught",
           _raises(lambda: R.scan_packet(s, surface_word=surf, authored_ids=authored), R.LeakDetected))


def test_four_sphere_not_referenced_anywhere():
    src = (_HERE / "track_e_smoke_runner.py").read_text(encoding="utf-8").lower()
    # the runner may name 'sphere' tokens in its leak vocabulary, but must never LOAD the lexicon
    _check("runner never loads the four-sphere lexicon file",
           "track_e_varna_sphere_lexicon" not in src)
    _check("four-sphere lexicon module not imported",
           "track_e_varna_sphere_lexicon" not in sys.modules)
    _check("no packet references a sphere",
           not any("sphere" in " ".join(R._scorer_facing_strings(p)).lower() for p in PACKETS))


# --------------------------------------------------- scorer-output ingestion --------
def _outputs(scorer):
    """Build synthetic (not real) scorer outputs from the hidden key. scorer(arm, is_correct)->[0,1]."""
    outs = []
    for h in HIDDEN:
        correct_opt = next(o for o, c in h["opt_to_cand"].items() if c == h["correct_candidate_id"])
        scores = {o: scorer(h["true_arm"], o == correct_opt) for o in h["opt_to_cand"]}
        outs.append({"packet_id": h["packet_id"], "scores": scores,
                     "chosen": max(scores, key=scores.get)})
    return outs


def test_malformed_output_fails_loudly():
    opts = {h["packet_id"]: list(h["opt_to_cand"]) for h in HIDDEN}
    good = _outputs(lambda a, c: 0.9 if c else 0.2)[0]
    bad = copy.deepcopy(good); bad["scores"][next(iter(bad["scores"]))] = 1.7   # out of range
    _check("out-of-range score rejected",
           _raises(lambda: R.validate_scorer_output(bad, packet_opts=opts, seen=set()),
                   R.MalformedScorerOutput))
    bad2 = copy.deepcopy(good); bad2.pop("chosen")
    _check("missing 'chosen' rejected",
           _raises(lambda: R.validate_scorer_output(bad2, packet_opts=opts, seen=set()),
                   R.MalformedScorerOutput))
    bad3 = copy.deepcopy(good); bad3["scores"]["opt_99"] = 0.5
    _check("wrong score keys rejected",
           _raises(lambda: R.validate_scorer_output(bad3, packet_opts=opts, seen=set()),
                   R.MalformedScorerOutput))
    bad4 = copy.deepcopy(good); bad4["explanation"] = "this is about the varṇa moha"
    _check("contamination text rejected",
           _raises(lambda: R.validate_scorer_output(bad4, packet_opts=opts, seen=set()),
                   R.MalformedScorerOutput))


def test_unknown_and_duplicate_packet_ids_fail():
    opts = {h["packet_id"]: list(h["opt_to_cand"]) for h in HIDDEN}
    good = _outputs(lambda a, c: 0.9 if c else 0.2)[0]
    unknown = copy.deepcopy(good); unknown["packet_id"] = "pkt_deadbeef"
    _check("unknown packet_id rejected",
           _raises(lambda: R.validate_scorer_output(unknown, packet_opts=opts, seen=set()),
                   R.MalformedScorerOutput))
    seen = set()
    R.validate_scorer_output(good, packet_opts=opts, seen=seen)
    _check("duplicate packet_id rejected",
           _raises(lambda: R.validate_scorer_output(good, packet_opts=opts, seen=seen),
                   R.MalformedScorerOutput))


# ------------------------------------------------- metrics / labels (allowed only) --
def test_only_allowed_labels_emitted():
    # scenario 1: every arm ranks the correct candidate first -> arms not separable -> INCONCLUSIVE
    r1 = R.score_from_outputs(BUNDLE, HIDDEN, _outputs(lambda a, c: 0.9 if c else 0.1))
    _check("uniform-strong -> allowed label", r1["label"] in H.ALLOWED_LABELS)
    _check("uniform-strong -> INCONCLUSIVE", r1["label"] == "INCONCLUSIVE")
    _check("label never forbidden (1)", r1["label"] not in H.FORBIDDEN_LABELS)
    # scenario 2: only arm A ranks the correct candidate first -> A beats every control -> SIGNAL
    r2 = R.score_from_outputs(BUNDLE, HIDDEN,
                              _outputs(lambda a, c: (0.9 if c else 0.1) if a == "A" else (0.3 if c else 0.9)))
    _check("A-dominant -> allowed label", r2["label"] in H.ALLOWED_LABELS)
    _check("A-dominant -> BOUNDARY_CONSTRAINT_SIGNAL", r2["label"] == "BOUNDARY_CONSTRAINT_SIGNAL")
    _check("A-dominant primary delta positive", r2["deltas"]["A_vs_X"] > 0)
    _check("label never forbidden (2)", r2["label"] not in H.FORBIDDEN_LABELS)


# ------------------------------------------------------------------- guardrails -----
def test_guardrails_untouched():
    _check("global manifest NOT_READY",
           MF.check_readiness(_HERE / "frozen")["status"] == "NOT_READY")
    _check("psr runner NOT_RUN", RUN.run()["status"] == "NOT_RUN")
    _check("smoke manifest run_enabled false", BUNDLE["manifest"]["run_enabled"] is False)
    _check("smoke approval NOT_APPROVED", BUNDLE["manifest"]["approval_status"] == "NOT_APPROVED")
    _check("smoke manifest four_sphere_integrated false",
           BUNDLE["manifest"]["four_sphere_integrated"] is False)
    _check("Stage A not imported", not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("track_e_smoke_runner — dry-run + gate tests (no LLM, no network, no run)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Track E smoke-runner tests passed.")


if __name__ == "__main__":
    main()
