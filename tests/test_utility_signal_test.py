"""CPU tests for the non-lexical UTILITY falsification harness (PREREG_UTILITY_SIGNAL.md). Validates the
machinery only — NOT a claim about H1. Checks: deterministic pair-preserving scramble, real/scrambled
pairing, template parity (no formatting tell), no answer leakage to the judge, verdict logic, and that the
random/null judge shows no systematic preference."""
import sys
from pathlib import Path

_VL = Path(__file__).resolve().parent.parent / "varna_lens"
if str(_VL) not in sys.path:
    sys.path.insert(0, str(_VL))

import wordlist_utility            # noqa: E402
import utility_test as U           # noqa: E402


def test_wordlist_sized_and_tagged():
    rows = wordlist_utility.load()
    assert len(rows) >= 120
    assert {"word", "language", "category", "pronunciation", "use_case"} <= set(rows[0])
    assert {"journaling", "naming", "creative", "affective"} == {r["use_case"] for r in rows}
    assert len({r["category"] for r in rows}) == 5


def test_scramble_deterministic_and_pair_preserving():
    a1c, a1v = U.scrambled_maps(7)
    a2c, a2v = U.scrambled_maps(7)
    assert a1c == a2c and a1v == a2v                       # deterministic
    cons, vow = U.real_maps()
    # consonant scramble permutes (worldly,counter) PAIRS as units -> same pair multiset, antonym pairing kept
    assert sorted(a1c.values()) == sorted(cons.values())
    assert sorted(a1v.values()) == sorted(vow.values())
    assert a1c != cons                                     # actually permuted


def test_real_and_scrambled_artifacts_differ_but_template_matches():
    rows = wordlist_utility.load()
    cons, vow = U.real_maps()
    cm, vm = U.scrambled_maps(U.BASE_SEED)
    diffs = 0
    for r in rows[:40]:
        a, b = U.artifact(r, cons, vow), U.artifact(r, cm, vm)
        la, lb = a.split("\n"), b.split("\n")
        assert len(la) == len(lb)                          # same number of lines (template parity)
        assert la[0] == lb[0]                              # identical header (same word, same framing)
        if a != b:
            diffs += 1
    assert diffs > 30                                      # scramble actually changes the content


def test_no_truth_claim_language_in_artifacts():
    rows = wordlist_utility.load()
    cons, vow = U.real_maps()
    banned = ("means", "reveals", "proves", "hidden essence", "your word is")
    for r in rows[:30]:
        text = U.artifact(r, cons, vow).lower()
        assert not any(b in text for b in banned)


def test_emit_pairs_hides_the_answer_from_the_judge():
    items, key = U.emit_pairs(scramble_seeds=(0,))
    assert len(items) == len(wordlist_utility.load())
    for it in items:
        assert set(it) == {"id", "use_case", "A", "B"}     # judge sees no 'real_is'
        assert key[it["id"]] in ("A", "B")                 # answer kept separate


def test_score_pairs_verdict_logic():
    # synthetic: real strongly preferred -> SIGNAL; equal -> NO_UTILITY; tiny+positive -> INCONCLUSIVE
    big = {f"s0:{i}": {"A": 4.5, "B": 2.0, "prefer": "A"} for i in range(60)}
    keyA = {f"s0:{i}": "A" for i in range(60)}
    assert U.score_pairs(big, keyA)["verdict"] == "UTILITY_SIGNAL_DETECTED"
    eq = {f"s0:{i}": {"A": 3.0, "B": 3.0, "prefer": "tie"} for i in range(60)}
    assert U.score_pairs(eq, keyA)["verdict"] == "NO_UTILITY_SIGNAL"


def test_random_judge_no_systematic_preference():
    res = U.run("random", n_scramble=8)
    assert res["pref_ci95"][0] <= 0.5 <= res["pref_ci95"][1]   # 50% inside the preference CI
    assert abs(res["delta"]) < U.MIN_EFFECT                    # no practically-meaningful preference
    assert res["verdict"] != "UTILITY_SIGNAL_DETECTED"         # null judge never "detects" utility
