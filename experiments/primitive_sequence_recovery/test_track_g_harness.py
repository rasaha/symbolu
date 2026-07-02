"""Tests for the Track G polarity-boundary harness — SYNTHETIC nonsense fixtures only.

No LLM, no network, no real data. Proves: every allowed label producible; forbidden labels/banned
tokens rejected; real-run path unavailable; toy flags mandatory; A_vs_R and A_vs_X both primary;
random-flip / scramble / Barnum vetoes; post-hoc polarity -> INVALID_POSTHOC_POLARITY; malformed
fails loudly.

    python3 experiments/primitive_sequence_recovery/test_track_g_harness.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import track_g_harness as H          # noqa: E402
import manifest as MF                # noqa: E402
import run_primitive_recovery as RUN  # noqa: E402

_TOY = _HERE / "toy_fixtures" / "track_g_toy_cases.json"


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
        p = _HERE / "toy_fixtures" / f"_tmp_g_{flag}.json"; p.write_text(json.dumps(d), encoding="utf-8")
        try:
            H.load_cases(p)
        finally:
            p.unlink()
    _check("rejects toy_not_for_scoring=false", _raises(lambda: drop("toy_not_for_scoring")))
    _check("rejects synthetic_only=false", _raises(lambda: drop("synthetic_only")))


def test_each_valid_case_matches_expected_label():
    for cid, c in _VALID.items():
        r = H.process_case(c)
        _check(f"{cid} -> {c['expected_label']}", r["label"] == c["expected_label"])
        _check(f"{cid}: allowed & not forbidden",
               r["label"] in H.ALLOWED_LABELS and r["label"] not in H.FORBIDDEN_LABELS)


def test_every_allowed_label_producible():
    produced = {H.process_case(c)["label"] for c in _VALID.values()}
    for lab in H.ALLOWED_LABELS:
        _check(f"allowed label producible: {lab}", lab in produced)


def test_reject_cases_raise_loudly():
    for cid, c in _REJECT.items():
        _check(f"{cid} raises RejectedFixture", _raises(lambda c=c: H.process_case(c)))


def test_A_vs_R_is_primary():
    # a would-be SIGNAL collapses to RANDOM_POLARITY_EXPLAINS if random-flip ties A
    c = copy.deepcopy(_VALID["G-SIGNAL"])
    c["items"][0]["arm_scores"]["R"] = dict(c["items"][0]["arm_scores"]["A"])
    _check("A~R -> RANDOM_POLARITY_EXPLAINS", H.process_case(c)["label"] == "RANDOM_POLARITY_EXPLAINS")


def test_A_vs_X_primary_after_R():
    # random-flip beaten but context ties A -> CONTEXT_ONLY_EXPLAINS (R checked before X)
    c = copy.deepcopy(_VALID["G-SIGNAL"])
    c["items"][0]["arm_scores"]["X"] = dict(c["items"][0]["arm_scores"]["A"])
    _check("A~X (R beaten) -> CONTEXT_ONLY_EXPLAINS",
           H.process_case(c)["label"] == "CONTEXT_ONLY_EXPLAINS")


def test_scramble_and_barnum_vetoes():
    c = copy.deepcopy(_VALID["G-SIGNAL"])
    c["items"][0]["arm_scores"]["B"] = dict(c["items"][0]["arm_scores"]["A"])
    _check("A~B -> SCRAMBLE_EQUIVALENT", H.process_case(c)["label"] == "SCRAMBLE_EQUIVALENT")
    c2 = copy.deepcopy(_VALID["G-SIGNAL"])
    c2["items"][0]["arm_scores"]["I"] = dict(c2["items"][0]["arm_scores"]["A"])
    _check("A~I -> BARNUM_POLARITY", H.process_case(c2)["label"] == "BARNUM_POLARITY")


def test_posthoc_polarity_invalidates():
    for mut in ({"assigned_before_scoring": False}, {"frozen": False}, {"posthoc_mutated": True}):
        c = copy.deepcopy(_VALID["G-SIGNAL"]); c["polarity_assignment"].update(mut)
        _check(f"{list(mut)[0]} -> INVALID_POSTHOC_POLARITY",
               H.process_case(c)["label"] == "INVALID_POSTHOC_POLARITY")


def test_random_flip_arm_mandatory():
    c = copy.deepcopy(_VALID["G-SIGNAL"]); c["items"][0]["arm_scores"].pop("R")
    _check("missing R arm -> reject", _raises(lambda: H.validate_case(c)))


def test_polarity_assignment_required():
    c = copy.deepcopy(_VALID["G-SIGNAL"]); c["polarity_assignment"].pop("expected_pole")
    _check("incomplete polarity_assignment -> reject", _raises(lambda: H.validate_case(c)))
    c2 = copy.deepcopy(_VALID["G-SIGNAL"]); c2["polarity_assignment"]["expected_relation"] = "sideways"
    _check("bad expected_relation -> reject", _raises(lambda: H.validate_case(c2)))


def test_forbidden_and_banned_rejected_inline():
    c = copy.deepcopy(_VALID["G-SIGNAL"]); c["x"] = "ONTOLOGICAL_SIGNAL"
    _check("forbidden label -> reject", _raises(lambda: H.validate_case(c)))
    for tok in ("varna", "sanskrit", "dhatu"):
        c2 = copy.deepcopy(_VALID["G-SIGNAL"]); c2["y"] = f"a {tok} axis"
        _check(f"banned token {tok!r} -> reject", _raises(lambda c2=c2: H.validate_case(c2)))


def test_malformed_scores_rejected():
    c = copy.deepcopy(_VALID["G-SIGNAL"]); c["items"][0]["arm_scores"]["A"]["c1"] = 1.7
    _check("out-of-range score -> reject", _raises(lambda: H.validate_case(c)))
    c2 = copy.deepcopy(_VALID["G-SIGNAL"]); c2["items"][0]["candidates"][1]["role"] = "target"
    _check("two targets -> reject", _raises(lambda: H.validate_case(c2)))


def test_blinding_hides_target_and_polarity():
    item = _VALID["G-SIGNAL"]["items"][0]
    pa = _VALID["G-SIGNAL"]["polarity_assignment"]
    packet, key = H.build_packet(item, pa, seed=1)
    blob = json.dumps(packet)
    _check("packet exposes no roles",
           not any(r in blob for r in ("target", "opposite_pole", "hard_negative", "barnum_compatible")))
    _check("packet hides original target id", "c1" not in blob)
    _check("packet carries no polarity direction",
           "expected_pole" not in blob and "expected_relation" not in blob and "glorpward" not in blob)
    _check("key recovers target", key[key["target_anon"]]["orig_id"] == item["target"])


def test_real_pilot_unavailable():
    _check("run_real_pilot raises", _raises(H.run_real_pilot, NotImplementedError))


def test_guardrails_untouched():
    _check("runner NOT_RUN", RUN.run()["status"] == "NOT_RUN")
    _check("manifest NOT_READY", MF.check_readiness(_HERE / "frozen")["status"] == "NOT_READY")
    _check("no LLM/ML libs imported",
           not any(m in sys.modules for m in ("openai", "anthropic", "requests", "httpx",
                                              "torch", "transformers")))
    _check("Stage A not imported", not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("track_g_harness — synthetic polarity-boundary mechanics tests (no LLM, no real data)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Track G harness synthetic tests passed.")


if __name__ == "__main__":
    main()
