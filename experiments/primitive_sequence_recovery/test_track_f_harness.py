"""Tests for the Track F inference-steering harness — SYNTHETIC judge scores only.

No LLM, no network, no real data. Proves: every allowed label producible; forbidden labels
rejected; real-run path unavailable; toy flags mandatory; A_vs_X necessary but specificity
(A_vs_B / A_vs_I) + correctness gate the positive; malformed / contaminated fixtures fail loudly.

    python3 experiments/primitive_sequence_recovery/test_track_f_harness.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import track_f_harness as H          # noqa: E402
import manifest as MF                # noqa: E402
import run_primitive_recovery as RUN  # noqa: E402

_TOY = _HERE / "toy_fixtures" / "track_f_toy_cases.json"


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _raises(fn, exc=H.RejectedFixture):
    try:
        fn()
    except exc:
        return True
    except Exception as e:
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    return False


CASES = {c["case_id"]: c for c in H.load_cases(_TOY)}
_VALID = {k: c for k, c in CASES.items() if c["expected_label"] != "REJECT"}
_REJECT = {k: c for k, c in CASES.items() if c["expected_label"] == "REJECT"}


def test_toplevel_toy_flags_mandatory():
    def drop(flag):
        d = json.loads(_TOY.read_text(encoding="utf-8")); d[flag] = False
        p = _HERE / "toy_fixtures" / f"_tmp_f_{flag}.json"; p.write_text(json.dumps(d), encoding="utf-8")
        try:
            H.load_cases(p)
        finally:
            p.unlink()
    _check("load_cases rejects toy_not_for_scoring=false", _raises(lambda: drop("toy_not_for_scoring")))
    _check("load_cases rejects synthetic_only=false", _raises(lambda: drop("synthetic_only")))


def test_each_valid_case_matches_expected_label():
    for cid, c in _VALID.items():
        r = H.process_case(c)
        _check(f"{cid} -> {c['expected_label']}", r["label"] == c["expected_label"])
        _check(f"{cid}: label allowed & not forbidden",
               r["label"] in H.ALLOWED_LABELS and r["label"] not in H.FORBIDDEN_LABELS)


def test_every_allowed_label_producible():
    produced = {H.process_case(c)["label"] for c in _VALID.values()}
    for lab in H.ALLOWED_LABELS:
        _check(f"allowed label producible: {lab}", lab in produced)


def test_reject_cases_raise_loudly():
    for cid, c in _REJECT.items():
        _check(f"{cid} raises RejectedFixture", _raises(lambda c=c: H.process_case(c)))


def test_A_vs_X_necessary():
    # even a specific, useful, correctness-preserving A yields NO_EFFECT if it doesn't differ from X
    c = copy.deepcopy(_VALID["F-SIGNAL"])
    c["items"][0]["a_distances"]["to_X"] = 0.0
    _check("A_vs_X <= eps -> NO_EFFECT", H.process_case(c)["label"] == "NO_EFFECT")


def test_specificity_gates_the_signal():
    # a would-be SIGNAL collapses to SCRAMBLE_EQUIVALENT if A stops being distinct from B
    c = copy.deepcopy(_VALID["F-SIGNAL"])
    c["items"][0]["a_distances"]["to_B"] = 0.0
    _check("A~B -> SCRAMBLE_EQUIVALENT", H.process_case(c)["label"] == "SCRAMBLE_EQUIVALENT")
    c2 = copy.deepcopy(_VALID["F-SIGNAL"])
    c2["items"][0]["a_distances"]["to_I"] = 0.0
    _check("A~I -> BARNUM_EQUIVALENT", H.process_case(c2)["label"] == "BARNUM_EQUIVALENT")
    c3 = copy.deepcopy(_VALID["F-SIGNAL"])
    c3["items"][0]["a_distances"]["to_B"] = 0.0; c3["items"][0]["a_distances"]["to_I"] = 0.0
    _check("A~B and A~I -> PROMPT_PRIMING_ONLY", H.process_case(c3)["label"] == "PROMPT_PRIMING_ONLY")


def test_correctness_gate():
    c = copy.deepcopy(_VALID["F-SIGNAL"])
    c["items"][0]["arms"]["A"]["correctness"] = 0.4   # drop vs X=0.9
    _check("correctness drop -> CORRECTNESS_DEGRADED", H.process_case(c)["label"] == "CORRECTNESS_DEGRADED")
    c2 = copy.deepcopy(_VALID["F-SIGNAL"])
    c2["items"][0]["arms"]["A"]["hallucination"] = 0.6
    _check("high hallucination -> CORRECTNESS_DEGRADED", H.process_case(c2)["label"] == "CORRECTNESS_DEGRADED")


def test_usefulness_and_noise_gate_priming():
    c = copy.deepcopy(_VALID["F-SIGNAL"])              # distinct from B/I but no usefulness gain
    c["items"][0]["arms"]["A"]["usefulness"] = 0.5     # == X usefulness -> gain 0
    _check("no usefulness gain -> PROMPT_PRIMING_ONLY", H.process_case(c)["label"] == "PROMPT_PRIMING_ONLY")
    c2 = copy.deepcopy(_VALID["F-SIGNAL"])
    c2["items"][0]["arms"]["A"]["poetic_noise"] = 0.8  # too noisy
    _check("high poetic noise -> PROMPT_PRIMING_ONLY", H.process_case(c2)["label"] == "PROMPT_PRIMING_ONLY")


def test_forbidden_label_and_banned_token_rejected_inline():
    c = copy.deepcopy(_VALID["F-SIGNAL"]); c["note_x"] = "ONTOLOGICAL_SIGNAL"
    _check("forbidden label anywhere -> reject", _raises(lambda: H.validate_case(c)))
    for tok in ("varna", "sanskrit", "dhatu"):
        c2 = copy.deepcopy(_VALID["F-SIGNAL"]); c2["note_y"] = f"a {tok} lens"
        _check(f"banned token {tok!r} -> reject", _raises(lambda c2=c2: H.validate_case(c2)))


def test_malformed_scores_rejected():
    c = copy.deepcopy(_VALID["F-SIGNAL"]); c["items"][0]["arms"]["A"]["correctness"] = 1.7
    _check("out-of-range score -> reject", _raises(lambda: H.validate_case(c)))
    c2 = copy.deepcopy(_VALID["F-SIGNAL"]); c2["items"][0]["arms"]["A"]["usefulness"] = "high"
    _check("non-numeric score -> reject", _raises(lambda: H.validate_case(c2)))
    c3 = copy.deepcopy(_VALID["F-SIGNAL"]); c3["items"][0]["a_distances"].pop("to_B")
    _check("missing a_distance -> reject", _raises(lambda: H.validate_case(c3)))


def test_blinding_hides_arm_identity():
    item = _VALID["F-SIGNAL"]["items"][0]
    packet, key = H.build_judge_packet(item, seed=1)
    blob = json.dumps(packet)
    _check("judge packet exposes no arm labels",
           not any(f'"{a}"' in blob for a in ("X", "A", "B", "F", "I", "R")))
    _check("judge packet uses resp_ ids", all(o["anon_id"].startswith("resp_") for o in packet["outputs"]))
    _check("key maps every resp_ back to an arm",
           set(key.values()) == set(a for a in ("X", "A", "B", "F", "I") ))


def test_real_pilot_unavailable():
    _check("run_real_pilot raises NotImplementedError", _raises(H.run_real_pilot, NotImplementedError))


def test_determinism():
    _check("process_case deterministic", H.process_case(_VALID["F-SIGNAL"]) == H.process_case(_VALID["F-SIGNAL"]))


def test_guardrails_untouched():
    _check("runner NOT_RUN", RUN.run()["status"] == "NOT_RUN")
    _check("manifest NOT_READY", MF.check_readiness(_HERE / "frozen")["status"] == "NOT_READY")
    _check("no LLM/ML libs imported",
           not any(m in sys.modules for m in ("openai", "anthropic", "requests", "httpx",
                                              "torch", "transformers")))
    _check("Stage A not imported", not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("track_f_harness — synthetic inference-steering mechanics tests (no LLM, no real data)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Track F harness synthetic tests passed.")


if __name__ == "__main__":
    main()
