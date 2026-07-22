#!/usr/bin/env python3
"""Tests for the naming-evaluation harness (deterministic parts). No model required.

  python varna_lens/tools/naming_eval/test_naming_eval.py
  pytest  varna_lens/tools/naming_eval/test_naming_eval.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import corpus as C            # noqa: E402
import arms as A              # noqa: E402
import judge as J             # noqa: E402
import run_eval as RE         # noqa: E402


def test_corpus_covers_required_categories():
    cats = {i["category"] for i in C.CORPUS}
    assert {"brand", "product", "agent", "portfolio", "difficult"} <= cats
    industries = {i.get("industry") for i in C.CORPUS if i["category"] == "brand"}
    # 10 distinct brand industries required
    assert len({i["industry"] for i in C.CORPUS if i["category"] == "brand"}) == 10
    seeds = {i["seed_concept"] for i in C.CORPUS}
    assert {"śānti", "kṣamā", "rakṣā"} <= seeds        # ś, ṣ, conjunct-kṣ cases present


def test_arms_are_deterministic_and_distinct():
    for it in C.CORPUS:
        arms1, _ = A.all_arms(it, C.CORPUS)
        arms2, _ = A.all_arms(it, C.CORPUS)
        assert arms1 == arms2, it["id"]                # deterministic
        assert len(set(arms1.values())) == 4, it["id"] # A/B/C/D all distinct


def test_only_conditioning_differs_across_arms():
    # the wrapper+brief+constraints prefix (up to CONSTRAINTS line) is identical across arms
    for it in C.CORPUS:
        arms, _ = A.all_arms(it, C.CORPUS)
        prefixes = {p.split("\nCONSTRAINTS:")[0] for p in arms.values()}
        assert len(prefixes) == 1, it["id"]


def test_random_control_uses_a_different_seed():
    for it in C.CORPUS:
        _, c_src = A.all_arms(it, C.CORPUS)
        assert c_src != it["seed_concept"], it["id"]   # Arm C injects a MISMATCHED profile


def test_injected_payload_has_no_decode_claims():
    for it in C.CORPUS:
        cond = RE.conditioning_of(A.arm_B(it)).lower()
        assert not any(p in cond for p in RE.CLAIM_PHRASES), it["id"]
        assert not any(w in cond for w in RE.RAW_DECODE), it["id"]


def test_ablation_field_costs_are_measured():
    abl = A.ablations(C.CORPUS[0])
    base = RE.est_tokens(abl["B_full"])
    # removing poles must reduce tokens; reordering must not change token count
    assert base - RE.est_tokens(abl["abl_no_binding"]) > 0
    assert base - RE.est_tokens(abl["abl_no_liberating"]) > 0
    assert RE.est_tokens(abl["abl_shuffled_order"]) == base


def test_full_profile_costs_more_than_minimal():
    for it in C.CORPUS:
        assert RE.est_tokens(A.arm_B(it)) > RE.est_tokens(A.arm_D(it)) > RE.est_tokens(A.arm_A(it)), it["id"]


def test_llm_adapter_reports_unavailable_not_fabricated():
    # with no API key, the adapter must return the explicit UNAVAILABLE sentinel, never invented data
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        assert J.generate("x") == J.UNAVAILABLE
        assert J.judge("brief", ["a", "b"]) == J.UNAVAILABLE
        assert J.llm_available() is False


def test_blind_shuffle_hides_and_recovers_labels():
    picks = {"A_baseline": "Xa", "B_profile": "Yb", "C_random": "Zc", "D_minimal": "Wd"}
    labelled, l2a = J.blind_shuffle(picks, salt="item1")
    assert set(l2a.values()) == set(picks)             # every arm represented
    assert all(lbl.startswith("opt_") for lbl, _ in labelled)  # arm identity hidden
    assert J.blind_shuffle(picks, salt="item1")[1] == l2a      # deterministic


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = []
    for t in tests:
        try:
            t(); print(f"  [PASS] {t.__name__}")
        except Exception as e:  # noqa: BLE001
            fails.append((t.__name__, e)); print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\ntest_naming_eval: {'PASS' if not fails else 'FAIL'} ({len(tests) - len(fails)}/{len(tests)})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
