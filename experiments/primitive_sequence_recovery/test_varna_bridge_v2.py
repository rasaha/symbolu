"""Tests for bridge v2 (retroflex-cluster rule). Deterministic; no model, no network.
B1.4b' remains NULL_RETURN_BOTTOM."""
import json
import pathlib

import varna_bridge_v2 as B2
import stage_a_prime_coverage as A

MP = B2.base_mapping()


def _v1(phonemes):
    """v1 flat mapping for comparison."""
    return [MP[p] for p in phonemes if p in MP]


def _phon(word):
    phs = []
    for tok in word.split("-"):
        phs += A.normalize(tok, "A_PRIME_EN")["phonemes"]
    return phs


def test_retroflex_applied_and_r_survives():
    assert B2.word_to_varnas("drum") == ["dda", "ra", "ma"]     # d before r -> ḍa, r survives
    assert B2.word_to_varnas("train") == ["tta", "ra", "na"]    # t before r -> ṭa, r survives
    assert B2.word_to_varnas("dread") == ["dda", "ra", "da"]    # the one frozen item that changes
    assert B2.word_to_varnas("dry") == ["dda", "ra", "ya"]
    assert B2.word_to_varnas("tree") == ["tta", "ra"]


def test_only_tta_dda_are_added():
    # every retroflex introduced by v2 is exactly tta or dda (Phase 1)
    for w in ["drum", "train", "dread", "dry", "tree", "matrix", "hundred", "country"]:
        v1, v2 = _v1(_phon(w)), B2.word_to_varnas(w)
        added = [x for x in v2 if x not in v1]
        assert all(a in ("tta", "dda") for a in added), (w, added)


def test_unchanged_when_no_td_before_r():
    # words without a t/d immediately before r are byte-identical to v1
    for w in ["peace", "terror", "cat", "surrender", "release", "clarity", "anchor", "song"]:
        assert B2.word_to_varnas(w) == _v1(_phon(w)), w


def test_v2_equals_v1_except_at_cluster():
    # position-by-position: v2 differs from v1 ONLY where a dental maps to a retroflex
    for w in ["drum", "train", "dragon", "address", "children"]:
        v1, v2 = _v1(_phon(w)), B2.word_to_varnas(w)
        assert len(v1) == len(v2)
        for a, b in zip(v1, v2):
            assert a == b or (a, b) in (("ta", "tta"), ("da", "dda")), (w, a, b)


def test_frozen_12_targets_only_dread_changes():
    targets = json.load(open("frozen/b1_9_targets.json"))["targets"]
    changed = []
    for t in targets:
        w = t["target_text"]
        if B2.word_to_varnas(w) != _v1(_phon(w)):
            changed.append(w)
    assert changed == ["dread"], changed        # only dread moves under bridge v2


def test_aspirates_and_other_retroflex_not_touched():
    # nr/shr/ny and retroflex aspirates are NOT introduced by Phase 1
    for w in ["shrimp", "henry", "canyon", "three", "throw"]:
        v2 = B2.word_to_varnas(w)
        assert "nna" not in v2 and "nya" not in v2 and "ssa" not in v2
        assert "ttha" not in v2 and "ddha" not in v2


def test_status_not_applied():
    m = json.load(open("b1_6_phoneme_to_varna_bridge_v2.json"))
    assert m["status"] == "APPROVED_IMPLEMENTED_NOT_YET_APPLIED"
    assert m["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
    # v1 bridge untouched
    assert "context_rules" not in json.load(open("frozen/b1_6_phoneme_to_varna_bridge_manifest.json"))
