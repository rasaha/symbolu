"""Deterministic tests for the B1.12 Gate-G0 structural audit v1. No judges, no network, no G1.

Covers: opaque-ID bijection stability; Levenshtein normalization; sorted-inventory edit baseline; corrected
d_ord|inv; self-order identity; repeated-varṇa behavior; bigram/trigram Jaccard; endpoint caps; length-span
rule; subset eligibility; optimization objective; tie-break determinism; zero-eligible-subset result; and
manifest/hash validation on the real frozen pool.
"""
import itertools
import json
import pathlib

import b1_12_g0_audit_v1 as A

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "results" / "b1_12_g0_audit_v1"


# ---- pure metric tests (fast) ----
def test_lev_and_normalization():
    assert A.lev("kitten", "sitting") == 3
    assert A.lev("abc", "abc") == 0
    assert A.lev("", "abc") == 3
    assert A.d_edit(list("abcd"), list("abdc")) == 0.5      # one adjacent transposition, len 4
    assert A.d_edit(list("ab"), list("ba")) == 1.0


def test_sorted_inventory_baseline():
    x, y = list("ABC"), list("ACD")
    assert A.lev(sorted(x), sorted(y)) == A.lev(list("ABC"), list("ACD")) == 2


def test_d_ord_given_inv_synthetic_cases():
    # the five V1.2 required cases
    assert round(A.d_ord_given_inv(list("ABC"), list("CBA")), 3) == 0.667   # same inv / diff order
    assert A.d_ord_given_inv(list("ABC"), list("DEF")) == 0.0                # diff inv / same pattern
    assert A.d_ord_given_inv(list("ABC"), list("ACD")) == 0.0                # partial: all diff is inventory
    assert A.d_ord_given_inv(list("AABC"), list("ABAC")) == 0.5             # repeated inv / diff order
    assert A.d_ord_given_inv(list("ABC"), list("ABC")) == 0.0               # identical


def test_selforder_identity():
    for s in ("ABC", "CBA", "AABC", "ABAC", "kara", "gaja"):
        x = list(s)
        assert abs(A.s_selforder(x) - A.d_edit(x, sorted(x))) < 1e-12
        assert abs(A.s_selforder(x) - A.d_ord_given_inv(x, sorted(x))) < 1e-12


def test_repeated_varna_behavior():
    # same multiset incl. repeats, different order -> positive order signal; identical -> 0
    assert A.d_ord_given_inv(list("AABC"), list("ABAC")) > 0
    assert A.d_ord_given_inv(list("AAB"), list("AAB")) == 0.0
    assert A.multiset_jaccard(list("AAB"), list("ABA")) == 1.0     # same multiset


def test_bigram_trigram_jaccard():
    assert A.bigrams(list("ABCA")) == {("A", "B"), ("B", "C"), ("C", "A")}
    assert A.trigrams(list("ABCD")) == {("A", "B", "C"), ("B", "C", "D")}
    assert A.jaccard(A.bigrams(list("ABC")), A.bigrams(list("ABC"))) == 1.0
    assert A.jaccard(A.bigrams(list("ABC")), A.bigrams(list("XYZ"))) == 0.0
    assert A.trigrams(list("AB")) == set()                         # undefined for len<3


def test_endpoint_and_length_span_rules():
    # 4 of 6 share first unit -> majority cap (<=3) violated
    firsts = [seq[0] for seq in (["A", "z"], ["A", "y"], ["A", "x"], ["A", "w"], ["B", "v"], ["C", "u"])]
    from collections import Counter
    assert max(Counter(firsts).values()) == 4 > A.ENDPOINT_MAJORITY_CAP
    lens = [3, 4, 5]
    assert (max(lens) - min(lens)) == 2 <= A.LENGTH_SPAN_CAP
    assert (5 - 2) == 3 > A.LENGTH_SPAN_CAP


def test_subset_selection_objective_and_tiebreak_determinism():
    # synthetic opaque sequences: pick the size-3 subset maximizing min pairwise d_edit deterministically
    seqs = {"a": list("UVWX"), "b": list("XWVU"), "c": list("UVWX"), "d": list("PQRS"), "e": list("PQRT")}

    def best_subset(k):
        allok = list(itertools.combinations(sorted(seqs), k))
        scored = []
        for sub in allok:
            edits = [A.d_edit(seqs[i], seqs[j]) for i, j in itertools.combinations(sorted(sub), 2)]
            scored.append((-min(edits), -sum(edits) / len(edits), tuple(sorted(sub))))
        scored.sort()
        return scored[0][2]
    assert best_subset(3) == best_subset(3)                        # deterministic
    # a,c identical -> min d_edit 0 for any subset containing both; winner avoids that pair
    assert not ({"a", "c"} <= set(best_subset(3)))


def test_zero_eligible_subset_logic():
    # if every candidate is identical, no pair meets tau_edit -> no subset satisfies the edit floor
    x = list("ABCD")
    assert A.d_edit(x, x) == 0.0 < A.TAU_EDIT
    # self-order of an already-sorted sequence is 0 -> fails s(x)>=0.34 (candidate-level ineligible)
    assert A.s_selforder(sorted(x)) == 0.0 < A.TAU_SELF


# ---- integration on the real frozen pool (single run; deterministic) ----
_RES = A.run()


def test_run_status_and_hashes():
    m = _RES["manifest"]
    assert m["pool_sha256"] == A.POOL_SHA_EXPECTED
    assert m["parser_sha256"] == A.PARSER_SHA_EXPECTED
    assert m["invalid_reasons"] == []
    assert _RES["status"] == "G0_PASS"
    assert m["n_words_frozen"] == 35 and m["n_eligible"] == 35
    assert m["no_thresholds_changed"] and m["no_pool_membership_changed"]


def test_opaque_bijection_stable():
    idmap = json.loads((OUT / "opaque_varna_id_map.json").read_text())["map"]
    oids = [r["opaque_id"] for r in idmap]
    idents = [(r["type"], r["unit"]) for r in idmap]
    assert len(oids) == len(set(oids)) == len(set(idents))        # bijection
    # re-run reproduces the identical map (stable ordering)
    A.run()
    assert json.loads((OUT / "opaque_varna_id_map.json").read_text())["map"] == idmap


def test_selection_is_valid_and_deterministic():
    sel = json.loads((OUT / "selection.json").read_text())["selection"]
    sub = sel["selected_subset"]
    assert len(sub) == 6 and len(set(sub)) == 6
    assert sel["objective_min_pairwise_d_edit"] >= A.TAU_EDIT
    # re-run yields the identical selected subset (determinism)
    res2 = A.run()
    assert res2["selection"]["selected_subset"] == sub


def test_selected_subset_satisfies_all_hard_constraints():
    import sanskrit_stage1_parser as P
    pool = json.loads((HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json").read_text())["words"]
    parsed = {w["id"]: [(u["type"], u["unit"]) for u in P.parse(w["devanagari"])["atomic_varnas"]]
              for w in pool}
    distinct = sorted({i for s in parsed.values() for i in s})
    op = {i: f"U{k+1:02d}" for k, i in enumerate(distinct)}
    seq = {c: [op[i] for i in parsed[c]] for c in parsed}
    sub = json.loads((OUT / "selection.json").read_text())["selection"]["selected_subset"]
    lens = [len(seq[c]) for c in sub]
    assert max(lens) - min(lens) <= A.LENGTH_SPAN_CAP
    from collections import Counter
    assert max(Counter(seq[c][0] for c in sub).values()) <= A.ENDPOINT_MAJORITY_CAP
    assert max(Counter(seq[c][-1] for c in sub).values()) <= A.ENDPOINT_MAJORITY_CAP
    for a, b in itertools.combinations(sub, 2):
        assert A.d_edit(seq[a], seq[b]) >= A.TAU_EDIT
        assert A.jaccard(A.bigrams(seq[a]), A.bigrams(seq[b])) <= A.BIGRAM_JACCARD_CAP
        if len(seq[a]) >= 3 and len(seq[b]) >= 3:
            assert A.jaccard(A.trigrams(seq[a]), A.trigrams(seq[b])) <= A.TRIGRAM_JACCARD_CAP
    for c in sub:
        assert A.s_selforder(seq[c]) >= A.TAU_SELF
