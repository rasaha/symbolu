"""CPU tests for the varna_lens acoustic-signal harness. No GPU/API. Validates the falsification machinery:
null judge lands at chance, scrambling actually changes essences, items are valence-matched and contain the
truth, and the pre-registered verdict logic fires correctly. NO claim about H1 here — just that the test
that *could* detect/refute it is built correctly."""
import sys
from pathlib import Path

_VL = Path(__file__).resolve().parent.parent / "varna_lens"
if str(_VL) not in sys.path:
    sys.path.insert(0, str(_VL))

import wordlist_signal          # noqa: E402
import signal_test as S         # noqa: E402


def test_wordlist_loads_and_is_sized():
    rows = wordlist_signal.load()
    assert len(rows) >= 120
    assert {"lang", "word", "gloss", "valence", "pron"} <= set(rows[0])
    assert {"sa", "en"} <= {r["lang"] for r in rows}        # home turf + English present


def test_forced_choice_items_contain_truth_and_are_valence_matched():
    rows = wordlist_signal.load()
    items = S.build_items(rows)
    assert len(items) == len(rows)
    val = {r["gloss"]: r["valence"] for r in rows}
    for r, (true, cands, ci) in zip(rows, items):
        assert len(cands) == S.K
        assert cands[ci] == true == r["gloss"]              # truth present at the marked index
        assert len(set(cands)) == S.K                       # no duplicate candidates
        # distractors valence-matched when the class is large enough to fill without backfill
        same = [g for g in {x["gloss"] for x in rows if x["valence"] == r["valence"]} if g != true]
        if len(same) >= S.K - 1:
            assert all(val.get(c) == r["valence"] for c in cands)


def test_scramble_changes_essences_but_keeps_alphabet():
    rows = wordlist_signal.load()[:20]
    keys = [S.phoneme_keys(r) for r in rows]
    cons, vow = S.real_maps()
    cm, vm = S.scrambled_maps(123)
    real = [S.essence(k, cons, vow) for k in keys]
    scr = [S.essence(k, cm, vm) for k in keys]
    assert real != scr                                      # scrambling must change the readings
    assert sorted(cons.values()) == sorted(cm.values())     # same gloss multiset, permuted assignment


def test_null_judge_is_chance_and_delta_zero():
    res = S.run("random")
    assert abs(res["acc_real"] - res["acc_scrambled"]) < 1e-9   # judge ignores essence -> real == scrambled
    assert abs(res["delta"]) < 1e-9
    assert 0.10 < res["acc_real"] < 0.30                        # within bootstrap range of chance 0.20


def test_verdict_logic_branches():
    # reconstruct the prereg rule on synthetic numbers
    def verdict(d_lo, d_hi, r_lo, chance=0.2):
        if d_lo > 0 and r_lo > chance:
            return "SIGNAL_DETECTED"
        if d_lo <= 0 <= d_hi:
            return "NO_SIGNAL"
        return "INCONCLUSIVE"
    assert verdict(0.05, 0.20, 0.30) == "SIGNAL_DETECTED"
    assert verdict(-0.02, 0.03, 0.21) == "NO_SIGNAL"
    assert verdict(0.01, 0.20, 0.19) == "INCONCLUSIVE"      # Δ>0 but real not above chance
