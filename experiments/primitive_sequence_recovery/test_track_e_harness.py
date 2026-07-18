"""Tests for the Track E varṇa boundary-constraint harness — SYNTHETIC TOY DATA ONLY.

No LLM call, no network, no real Sanskrit data, no real scoring. Proves the MECHANICS only:
per-arm MRR/Top-1/pairwise, the incremental deltas (A_vs_X primary), the decision precedence
that turns synthetic scorer output into one of the seven allowed Track E labels, the loud
rejection of malformed/contaminated/real-language fixtures, the mandatory toy flags, the
blinding utility, and the unavailability of any real-run path. Forbidden labels are never
emitted. Track B remains blocked; this validates structure, not meaning.

    python3 experiments/primitive_sequence_recovery/test_track_e_harness.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import track_e_harness as H          # noqa: E402
import manifest as MF                # noqa: E402
import run_primitive_recovery as RUN  # noqa: E402

_TOY = _HERE / "toy_fixtures" / "track_e_toy_cases.json"


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _raises(fn, exc=H.RejectedFixture):
    try:
        fn()
    except exc:
        return True
    except Exception as e:  # wrong exception type is still a failure
        raise AssertionError(f"expected {exc.__name__}, got {type(e).__name__}: {e}")
    return False


CASES = {c["case_id"]: c for c in H.load_cases(_TOY)}
_VALID = {cid: c for cid, c in CASES.items() if c["expected_label"] != "REJECT"}
_REJECT = {cid: c for cid, c in CASES.items() if c["expected_label"] == "REJECT"}


# ---------------------------------------------------------------- fixture hygiene ---
def test_fixture_toplevel_toy_flags_present():
    data = json.loads(_TOY.read_text(encoding="utf-8"))
    _check("fixture toy_not_for_scoring true", data["toy_not_for_scoring"] is True)
    _check("fixture synthetic_only true", data["synthetic_only"] is True)


def test_toplevel_toy_flags_mandatory():
    def _drop_flag(flag):
        data = json.loads(_TOY.read_text(encoding="utf-8"))
        data[flag] = False
        p = _HERE / "toy_fixtures" / f"_tmp_track_e_{flag}.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        try:
            H.load_cases(p)
        finally:
            p.unlink()
    _check("load_cases rejects toy_not_for_scoring=false",
           _raises(lambda: _drop_flag("toy_not_for_scoring")))
    _check("load_cases rejects synthetic_only=false",
           _raises(lambda: _drop_flag("synthetic_only")))


def test_per_case_toy_flags_mandatory():
    c = copy.deepcopy(_VALID["E-SIGNAL"])
    c["toy_not_for_scoring"] = False
    _check("per-case toy flag false -> reject", _raises(lambda: H.validate_case(c)))
    c2 = copy.deepcopy(_VALID["E-SIGNAL"])
    del c2["synthetic_only"]
    _check("per-case synthetic_only missing -> reject", _raises(lambda: H.validate_case(c2)))


def test_no_real_sanskrit_tokens_in_committed_fixtures():
    blob = _TOY.read_text(encoding="utf-8").lower()
    for tok in H.BANNED_REAL:
        _check(f"committed fixtures contain no banned marker {tok!r}", tok not in blob)


# ---------------------------------------------------------------- label coverage ----
def test_each_valid_case_matches_expected_label():
    for cid, c in _VALID.items():
        r = H.process_case(c)
        _check(f"{cid} -> {c['expected_label']}", r["label"] == c["expected_label"])
        _check(f"{cid}: label is allowed", r["label"] in H.ALLOWED_LABELS)
        _check(f"{cid}: label never forbidden", r["label"] not in H.FORBIDDEN_LABELS)


def test_every_allowed_label_is_producible():
    produced = {H.process_case(c)["label"] for c in _VALID.values()}
    for lab in H.ALLOWED_LABELS:
        _check(f"allowed label producible by a toy case: {lab}", lab in produced)


# ----------------------------------------------------------- decision precedence ----
def test_A_vs_X_primary_beats_all_other_vetoes():
    # A beats every control including X would be SIGNAL; make X tie A while B, F, I would
    # ALSO each independently veto -> the A_vs_X (context) veto must win precedence.
    c = copy.deepcopy(_VALID["E-SIGNAL"])
    good = {"c1": 0.9, "c2": 0.3, "c3": 0.2, "c4": 0.1}   # c1 rank 1
    for arm in ("A", "X", "B", "F", "I"):
        c["items"][0]["arm_scores"][arm] = dict(good)      # A ties X, B, F, I simultaneously
    r = H.process_case(c)
    _check("A_vs_X veto takes precedence over scramble/etym/Barnum vetoes",
           r["label"] == "CONTEXT_ONLY_EXPLAINS")


def test_scramble_veto_before_barnum_and_etymology():
    # A beats context (X worse) but B ties A, and I & F would also tie -> SCRAMBLE wins.
    c = copy.deepcopy(_VALID["E-SIGNAL"])
    good = {"c1": 0.9, "c2": 0.3, "c3": 0.2, "c4": 0.1}
    worse = {"c1": 0.5, "c2": 0.9, "c3": 0.2, "c4": 0.1}
    sc = c["items"][0]["arm_scores"]
    sc["A"], sc["X"] = dict(good), dict(worse)
    sc["B"], sc["F"], sc["I"] = dict(good), dict(good), dict(good)
    sc["D"] = dict(worse)
    _check("B tie fires SCRAMBLE_EQUIVALENT before Barnum/etymology",
           H.process_case(c)["label"] == "SCRAMBLE_EQUIVALENT")


def test_barnum_veto_before_etymology():
    # A beats X and B; I ties A and F would also tie -> BARNUM wins over ETYMOLOGY.
    c = copy.deepcopy(_VALID["E-SIGNAL"])
    good = {"c1": 0.9, "c2": 0.3, "c3": 0.2, "c4": 0.1}
    worse = {"c1": 0.5, "c2": 0.9, "c3": 0.2, "c4": 0.1}
    sc = c["items"][0]["arm_scores"]
    sc["A"] = dict(good)
    sc["X"], sc["B"], sc["D"] = dict(worse), dict(worse), dict(worse)
    sc["I"], sc["F"] = dict(good), dict(good)
    _check("I tie fires BARNUM_BOUNDARY before ETYMOLOGY",
           H.process_case(c)["label"] == "BARNUM_BOUNDARY")


def test_signal_requires_beating_every_control():
    r = H.process_case(_VALID["E-SIGNAL"])
    d = r["deltas"]
    _check("SIGNAL: A_vs_X > eps", d["A_vs_X"] > H.EPS)
    _check("SIGNAL: A_vs_B > eps", d["A_vs_B"] > H.EPS)
    _check("SIGNAL: A_vs_F > eps", d["A_vs_F"] > H.EPS)
    _check("SIGNAL: A_vs_D > eps", d["A_vs_D"] > H.EPS)
    _check("SIGNAL: A_vs_I > eps", d["A_vs_I"] > H.EPS)
    _check("SIGNAL label emitted", r["label"] == "BOUNDARY_CONSTRAINT_SIGNAL")


def test_dictionary_tie_gives_no_signal_not_signal():
    # A_vs_D <= eps is NOT a veto tier, but it does block SIGNAL -> NO_SIGNAL.
    r = H.process_case(_VALID["E-NO-SIGNAL"])
    _check("dictionary tie -> NO_SIGNAL (not SIGNAL)", r["label"] == "NO_SIGNAL")


# ------------------------------------------------------------ loud rejection paths --
def test_reject_cases_raise_loudly():
    for cid, c in _REJECT.items():
        _check(f"{cid} raises RejectedFixture", _raises(lambda c=c: H.process_case(c)))


def test_banned_language_token_rejected_inline():
    # Deliberately NOT committed to the fixture file; constructed here to prove the scan.
    for tok in ("varna", "sanskrit", "dhatu"):
        c = copy.deepcopy(_VALID["E-SIGNAL"])
        c["items"][0]["candidates"][1]["gloss"] = f"a {tok} reading"
        _check(f"banned token {tok!r} in a gloss -> reject",
               _raises(lambda c=c: H.validate_case(c)))


def test_forbidden_label_string_rejected_inline():
    c = copy.deepcopy(_VALID["E-SIGNAL"])
    c["note_injected"] = "ONTOLOGICAL_SIGNAL"
    _check("forbidden label string anywhere in case -> reject",
           _raises(lambda: H.validate_case(c)))


def test_malformed_candidate_sets_rejected():
    def mut(fn):
        c = copy.deepcopy(_VALID["E-SIGNAL"])
        fn(c["items"][0])
        return c
    # < 3 candidates
    c1 = mut(lambda it: it.__setitem__("candidates", it["candidates"][:2]))
    _check("<3 candidates -> reject", _raises(lambda: H.validate_case(c1)))
    # duplicate candidate_id
    c2 = mut(lambda it: it["candidates"][1].__setitem__("candidate_id", "c1"))
    _check("duplicate candidate_id -> reject", _raises(lambda: H.validate_case(c2)))
    # zero context_correct roles
    c3 = mut(lambda it: it["candidates"][0].__setitem__("role", "hard_negative"))
    _check("no context_correct role -> reject", _raises(lambda: H.validate_case(c3)))
    # two context_correct roles
    c4 = mut(lambda it: it["candidates"][1].__setitem__("role", "context_correct"))
    _check("two context_correct roles -> reject", _raises(lambda: H.validate_case(c4)))
    # context_correct id not among candidates
    c5 = mut(lambda it: it.__setitem__("context_correct", "c99"))
    _check("context_correct id absent -> reject", _raises(lambda: H.validate_case(c5)))


def test_malformed_scorer_output_rejected():
    def mut(fn):
        c = copy.deepcopy(_VALID["E-SIGNAL"])
        fn(c["items"][0]["arm_scores"])
        return c
    # missing an arm
    c1 = mut(lambda sc: sc.pop("I"))
    _check("missing arm -> reject", _raises(lambda: H.validate_case(c1)))
    # score out of [0,1]
    c2 = mut(lambda sc: sc["A"].__setitem__("c1", 1.5))
    _check("score > 1 -> reject", _raises(lambda: H.validate_case(c2)))
    # non-numeric score
    c3 = mut(lambda sc: sc["A"].__setitem__("c1", "high"))
    _check("non-numeric score -> reject", _raises(lambda: H.validate_case(c3)))
    # boolean masquerading as score
    c4 = mut(lambda sc: sc["A"].__setitem__("c1", True))
    _check("boolean score -> reject", _raises(lambda: H.validate_case(c4)))
    # missing a candidate's score in an arm
    c5 = mut(lambda sc: sc["A"].pop("c4"))
    _check("missing candidate score in an arm -> reject", _raises(lambda: H.validate_case(c5)))


# ------------------------------------------------------------------- blinding -------
def test_build_packet_blinds_roles_and_answer():
    item = _VALID["E-SIGNAL"]["items"][0]
    packet, key = H.build_packet(item, seed=1)
    blob = json.dumps(packet)
    _check("packet exposes no role labels",
           not any(r in blob for r in ("context_correct", "hard_negative",
                                       "dict_valid_context_wrong", "barnum_compatible")))
    _check("packet uses anonymized cand_ ids",
           all(c["candidate_id"].startswith("cand_") for c in packet["candidates"]))
    _check("packet hides the original context_correct id", "c1" not in blob)
    anon = key["context_correct_anon"]
    _check("key recovers the correct answer", key[anon]["orig_id"] == item["context_correct"])
    _check("every anon id maps back to an original",
           {v["orig_id"] for k, v in key.items() if isinstance(v, dict)}
           == {c["candidate_id"] for c in item["candidates"]})


# ------------------------------------------------------ determinism & real-run gate --
def test_process_case_is_deterministic():
    a = H.process_case(_VALID["E-SIGNAL"])
    b = H.process_case(_VALID["E-SIGNAL"])
    _check("process_case deterministic", a == b)


def test_real_pilot_path_unavailable():
    _check("run_real_pilot raises NotImplementedError",
           _raises(H.run_real_pilot, NotImplementedError))


def test_decide_only_ever_returns_allowed_labels():
    # exhaustive over the toy fixtures + the precedence mutations already covered above
    for c in _VALID.values():
        lab = H.process_case(c)["label"]
        _check(f"{c['case_id']}: decide within allowed set", lab in H.ALLOWED_LABELS)


# ------------------------------------------------------------------ guardrails ------
def test_guardrails_untouched():
    _check("runner NOT_RUN", RUN.run()["status"] == "NOT_RUN")
    _check("manifest NOT_READY", MF.check_readiness(_HERE / "frozen")["status"] == "NOT_READY")
    _check("harness imports no LLM/network/ML libs",
           not any(m in sys.modules for m in ("openai", "anthropic", "requests", "httpx",
                                              "torch", "transformers")))
    _check("Stage A not imported", not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("track_e_harness — synthetic mechanics tests (toy_not_for_scoring; no LLM, no real data)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Track E harness synthetic tests passed.")


if __name__ == "__main__":
    main()
