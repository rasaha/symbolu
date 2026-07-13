"""Deterministic tests for B1.12 Gate G1 design v1. No judges, no network, no confirmatory run.

Covers: arm A/B inventory equality; A/B order inequality; A/D inventory equality; raw-word & transliteration
leakage; formatting/position-tag parity; repeated-unit preservation; content-masked arm classification;
length-only and endpoint-only elimination; deterministic rendering; manifest/hash validation. Also asserts the
G0/pool/parser inputs are untouched.
"""
import hashlib
import itertools
import json
import pathlib

import b1_12_g1_design_v1 as G1

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "results" / "b1_12_g1_design_v1"

_R = G1.build()
_POOL, _SEQ = G1.load_opaque()


def _arms():
    return json.loads((OUT / "arm_render_examples.json").read_text())["arms"]


def test_arm_AB_inventory_and_length_equal_order_differs():
    arms = _arms()
    for cid in G1.SELECTED:
        a = arms[cid]["A_true_order"]["tokens"]
        b = arms[cid]["B_order_scramble"]["tokens"]
        assert sorted(a) == sorted(b)                 # identical multiset (inventory)
        assert len(a) == len(b)                        # identical length
        assert a != b                                  # order differs
        assert b != sorted(b)                          # scramble is a genuine non-canonical order


def test_arm_AD_inventory_equal_D_is_unordered_canonical():
    arms = _arms()
    for cid in G1.SELECTED:
        a = arms[cid]["A_true_order"]["tokens"]
        d = arms[cid]["D_unordered_inventory"]["tokens"]
        assert sorted(a) == sorted(d)                  # same units
        assert d == sorted(d)                          # D removes order (canonical)
        assert a != d                                  # true order != unordered representative (s(x)>0)


def test_no_raw_word_or_transliteration_leakage():
    arms = _arms()
    iast = [w["iast"] for w in _POOL.values()]
    import re
    for cid in G1.SELECTED:
        for arm in ("A_true_order", "B_order_scramble", "D_unordered_inventory"):
            r = arms[cid][arm]["render"]
            assert re.match(r"^[pU0-9: ]+$", r)        # only tags/ids/sep — no IAST/Devanāgarī
            assert not any("ऀ" <= ch <= "ॿ" for ch in r)
            assert not any(w.lower() in r.lower() for w in iast)


def test_formatting_and_position_tag_parity():
    arms = _arms()
    for cid in G1.SELECTED:
        renders = [arms[cid][a]["render"] for a in ("A_true_order", "B_order_scramble", "D_unordered_inventory")]
        # identical position-tag skeleton p1: p2: ... across all three arms
        skeletons = [" ".join(tok.split(":")[0] for tok in r.split()) for r in renders]
        assert skeletons[0] == skeletons[1] == skeletons[2]


def test_repeated_unit_preservation():
    # renderer preserves repeats and their positions
    toks = ["U03", "U03", "U07", "U03"]
    r = G1.render_positional(toks)
    assert r == "p1:U03 p2:U03 p3:U07 p4:U03"
    assert r.count("U03") == 3
    # d_ord|inv still isolates order for a repeated-inventory pair (sanity via G0 fn)
    import b1_12_g0_audit_v1 as G0
    assert G0.d_ord_given_inv(list("AABC"), list("ABAC")) > 0


def test_content_masked_arms_indistinguishable():
    arms = _arms()
    for cid in G1.SELECTED:
        m = [arms[cid][a]["masked"] for a in ("A_true_order", "B_order_scramble", "D_unordered_inventory")]
        assert m[0] == m[1] == m[2]                    # masked -> arm identity carried ONLY by (ordered) content
        # masked render encodes length only
        assert m[0] == " ".join(f"p{i+1}:{G1.MASK}" for i in range(len(arms[cid]["A_true_order"]["tokens"])))


def test_length_only_elimination_within_trial_impossible():
    arms = _arms()
    for cid in G1.SELECTED:
        lens = {len(arms[cid][a]["tokens"]) for a in
                ("A_true_order", "B_order_scramble", "D_unordered_inventory")}
        assert len(lens) == 1                          # all arms one length -> length cannot pick the true arm


def test_endpoint_only_masked_indistinguishable():
    # with content masked, first/last positions are the same placeholder -> no endpoint artifact
    arms = _arms()
    for cid in G1.SELECTED:
        m = arms[cid]["A_true_order"]["masked"].split()
        assert m[0].endswith(G1.MASK) and m[-1].endswith(G1.MASK)


def test_cross_word_first_unit_unique_motivates_within_word():
    la = json.loads((OUT / "leakage_audit.json").read_text())
    assert la["cross_word_first_unit_unique"] is True   # cross-word candidate task WOULD leak -> within-word chosen
    assert la["all_leakage_checks_pass"] is True
    assert la["control_leakage"] is False


def test_classification_and_verdict():
    sa = json.loads((OUT / "selected_set_structural_audit.json").read_text())
    assert sa["all_distinct_inventories"] is True      # no pair shares a multiset -> cross-word = inventory
    assert sa["classification"] in ("MIXED_ORDER_AND_INVENTORY", "INVENTORY_DOMINATED")
    man = json.loads((OUT / "g1_manifest.json").read_text())
    assert man["verdict"] == "G1_PASS_WITH_LIMITED_CLAIM"
    assert man["primary_task_model"] == "MODEL_3_SAME_WORD_ORDER_DISCRIMINATION"
    assert man["evaluator_real_model_usability"] == "UNRESOLVED_NO_JUDGE_AVAILABLE"


def test_deterministic_rendering_and_rerun():
    b1 = (OUT / "arm_render_examples.json").read_bytes()
    G1.build()
    b2 = (OUT / "arm_render_examples.json").read_bytes()
    assert b1 == b2


def test_g0_and_pool_inputs_untouched():
    # G1 must not mutate the frozen pool, G0 map, or parser
    assert hashlib.sha256((HERE / "b1_12_candidate_pool_v1" / "b1_12_candidate_pool_v1.json").read_bytes()
                          ).hexdigest() == "8cf857891f95bb07e66a3048f7eabe4f1e5814777889abdf6dadb0d5d296d0b4"
    assert hashlib.sha256((HERE / "sanskrit_stage1_parser.py").read_bytes()).hexdigest() == \
        "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947"
    man = json.loads((OUT / "g1_manifest.json").read_text())
    # opaque map from G0 audit is referenced, not rebuilt-and-rewritten
    g0map = HERE / "results" / "b1_12_g0_audit_v1" / "opaque_varna_id_map.json"
    assert man["opaque_map_sha256_from_g0"] == hashlib.sha256(g0map.read_bytes()).hexdigest()
