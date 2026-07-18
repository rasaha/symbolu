"""Tests for the Track D Stage-D0 LLM-scorer pilot harness — SYNTHETIC TOY DATA ONLY.

No LLM call, no network, no real Sanskrit data, no real scoring. Proves the mechanics:
anonymization, arm-randomization with hidden key, Barnum max(I1..I4) rule, JSON validation,
contamination propagation, label assignment, malformed handling, and the no-real-data guard.

    python3 experiments/primitive_sequence_recovery/test_track_d_d0_harness.py
"""
from __future__ import annotations

import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import track_d_d0_harness as H          # noqa: E402
import manifest as MF                   # noqa: E402
import run_primitive_recovery as RUN    # noqa: E402

_TOY = _HERE / "toy_fixtures" / "d0_toy_cases.json"


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _cases():
    data = json.loads(_TOY.read_text(encoding="utf-8"))
    _check("fixture marked toy_not_for_scoring", data["toy_not_for_scoring"] is True)
    return {c["target_id"]: c for c in data["cases"]}


CASES = _cases()


def test_no_real_data_guard():
    raised = False
    try:
        H.build_packet({"compositions": {}, "profiles": {}}, seed=0)  # no toy mark
    except ValueError:
        raised = True
    _check("build_packet rejects non-toy input (no real-data path)", raised)
    raised = False
    try:
        H.run_real_pilot()
    except NotImplementedError:
        raised = True
    _check("run_real_pilot is not implemented (no real scoring)", raised)


def test_anonymization_hides_arms_and_words():
    c = CASES["toy_beats_all"]
    packet, keys = H.build_packet(c, seed=1)
    blob = json.dumps(packet).lower()
    _check("packet exposes no arm labels", not any(k in blob for k in ('"a"', '"b"', '"c"', "arm")))
    _check("packet exposes no 'target'/'barnum' profile names",
           "target" not in blob and "barnum" not in blob and "i1" not in blob)
    _check("comp ids are anonymized", all(cc["comp_id"].startswith("comp_") for cc in packet["compositions"]))
    _check("prof ids are anonymized", all(pp["profile_id"].startswith("prof_") for pp in packet["profiles"]))
    _check("hidden key maps every comp to an arm", set(keys["comp"].values()) == {"A", "B", "C"})
    _check("hidden key maps profiles incl target + I1..I4",
           set(keys["prof"].values()) == {"target", "I1", "I2", "I3", "I4"})


def test_randomization_deterministic_but_shuffles():
    c = CASES["toy_beats_all"]
    p0, k0 = H.build_packet(c, seed=1)
    p0b, k0b = H.build_packet(c, seed=1)
    _check("same seed -> identical packet", p0 == p0b and k0 == k0b)
    # different seeds should (usually) permute the hidden mapping; check order differs somewhere
    orders = {tuple(k["comp"].values()) for k in (H.build_packet(c, seed=s)[1] for s in range(6))}
    _check("varying seed permutes arm order", len(orders) > 1)


def test_synthesize_maps_named_to_anonymous():
    c = CASES["toy_beats_all"]
    packet, keys = H.build_packet(c, seed=2)
    resp = H.synthesize_response(c["judge_behavior"], keys)
    _check("synthesized response validates", H.validate_response(resp, packet) == [])
    # the composition keyed as arm A must carry A's named target score
    inv = {arm: cid for cid, arm in keys["comp"].items()}
    tgt = {name: pid for pid, name in keys["prof"].items()}["target"]
    _check("named A/target score preserved through anonymization",
           abs(resp["scores"][inv["A"]][tgt] - 0.90) < 1e-9)


def test_json_validation_catches_malformed_and_out_of_range():
    c = CASES["toy_beats_all"]
    packet, _ = H.build_packet(c, seed=0)
    _check("malformed JSON string -> error", H.validate_response("{not json", packet) != [])
    _check("missing scores -> error", H.validate_response({}, packet) != [])
    bad = {"scores": {cc["comp_id"]: {pp["profile_id"]: 2.0 for pp in packet["profiles"]}
                      for cc in packet["compositions"]}}
    _check("out-of-range score -> error", any("out of [0,1]" in e for e in H.validate_response(bad, packet)))


def test_barnum_max_rule_and_labels():
    r = H.process_case(CASES["toy_beats_all"], seed=3)
    _check("beats-all -> SUGGESTIVE", r["label"] == "LLM_PILOT_SUGGESTIVE")
    _check("beats-all -> A>maxBarnum", r["metrics"]["A_vs_maxBarnum"] > 0)
    _check("beats-all -> target rank 1 under A", r["metrics"]["target_profile_rank_under_A"] == 1)

    r2 = H.process_case(CASES["toy_loses_barnum"], seed=3)
    _check("loses-barnum -> NO_SIGNAL", r2["label"] == "LLM_PILOT_NO_SIGNAL")
    _check("loses-barnum -> A<=maxBarnum", r2["metrics"]["A_vs_maxBarnum"] <= 0)


def test_contamination_propagates_and_overrides():
    r = H.process_case(CASES["toy_contaminated"], seed=3)
    _check("contaminated -> CONTAMINATED label", r["label"] == "LLM_PILOT_CONTAMINATED")
    _check("contaminated -> reasons recorded", len(r["contamination"]) > 0)
    _check("contamination overrides even a high A score",
           r["metrics"] is None or r["label"] == "LLM_PILOT_CONTAMINATED")


def test_malformed_response_is_inconclusive():
    r = H.process_case(CASES["toy_malformed"], seed=3)
    _check("malformed -> INCONCLUSIVE", r["label"] == "LLM_PILOT_INCONCLUSIVE")
    _check("malformed -> errors recorded", len(r["errors"]) > 0)
    _check("malformed -> no metrics computed", r["metrics"] is None)


def test_all_toy_cases_match_expected_labels():
    for tid, c in CASES.items():
        r = H.process_case(c, seed=5)
        _check(f"{tid} -> {c['expected_label']}", r["label"] == c["expected_label"])
        _check(f"{tid}: label never forbidden", r["label"] not in H.FORBIDDEN_LABELS)


def test_guardrails_untouched():
    _check("runner NOT_RUN", RUN.run()["status"] == "NOT_RUN")
    _check("manifest NOT_READY", MF.check_readiness(_HERE / "frozen")["status"] == "NOT_READY")
    _check("harness imports no LLM/network libs",
           not any(m in sys.modules for m in ("openai", "anthropic", "requests", "httpx",
                                              "torch", "transformers")))
    _check("Stage A not imported", not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("track_d_d0_harness — synthetic dry-run tests (toy_not_for_scoring; no LLM, no real data)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Track D D0 harness dry-run tests passed.")


if __name__ == "__main__":
    main()
