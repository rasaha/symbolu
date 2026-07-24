"""Tests for policy variants A/B/C and the acceptable_quality_threshold usage question.
Deterministic; no live calls; baseline imported read-only (never modified)."""
import copy
import json
import os

import pytest

from model_selection_experiment import policy as base, simulator as sim
from model_selection_reconciliation import variants as V

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "model_selection_experiment", "data")


def _fixtures():
    reg = json.load(open(os.path.join(_DATA, "registry_v1.json")))
    pol = json.load(open(os.path.join(_DATA, "policy_v1.json")))
    corpus = json.load(open(os.path.join(_DATA, "corpus_v1.json")))
    provs = sorted({(m["declared"].get("provider", {}) or {}).get("value")
                    if isinstance(m["declared"].get("provider"), dict)
                    else m["declared"].get("provider") for m in reg["models"].values()})
    ent = {"approved_providers": list(provs)}
    tel = sim.telemetry_feed("mature")
    return reg, pol, corpus, ent, tel


# --- Policy A preserves the baseline exactly -------------------------------

def test_policy_A_reproduces_baseline_exactly():
    reg, pol, corpus, ent, tel = _fixtures()
    for task in corpus["tasks"]:
        baseline = base.route(task, reg, ent, tel, pol, "mature", None)
        a = V.route_variant("A", task, reg, ent, tel, pol, "mature")
        assert a["selected"] == baseline["selected"]
        assert a["scored"] == baseline["scored"]
        assert a["abstained"] == baseline["abstained"]


# --- THE key question: is acceptable_quality_threshold used during selection? --

def test_baseline_and_A_ignore_acceptable_quality_threshold():
    """Proves Policy A / baseline selection is INVARIANT to the quality threshold —
    i.e. acceptable_quality_threshold is NOT an enforced selection constraint in A."""
    reg, pol, corpus, ent, tel = _fixtures()
    changed = 0
    for task in corpus["tasks"]:
        lo = copy.deepcopy(task); lo["acceptable_quality_threshold"] = 0.0
        hi = copy.deepcopy(task); hi["acceptable_quality_threshold"] = 1.0
        s_lo = V.route_variant("A", lo, reg, ent, tel, pol, "mature")["selected"]
        s_hi = V.route_variant("A", hi, reg, ent, tel, pol, "mature")["selected"]
        if s_lo != s_hi:
            changed += 1
    assert changed == 0, "Policy A selection changed with the quality threshold — it should not"


def test_policy_B_enforces_acceptable_quality_threshold():
    """Proves Policy B selection DOES depend on the quality floor — the constraint is enforced."""
    reg, pol, corpus, ent, tel = _fixtures()
    changed = 0
    for task in corpus["tasks"]:
        lo = copy.deepcopy(task); lo["acceptable_quality_threshold"] = 0.0
        hi = copy.deepcopy(task); hi["acceptable_quality_threshold"] = 0.95
        r_lo = V.route_variant("B", lo, reg, ent, tel, pol, "mature")
        r_hi = V.route_variant("B", hi, reg, ent, tel, pol, "mature")
        if (r_lo["selected"], r_lo["abstained"]) != (r_hi["selected"], r_hi["abstained"]):
            changed += 1
    assert changed > 0, "Policy B selection never changed with the floor — floor not enforced"


# --- floor correctness -----------------------------------------------------

def test_B_C_never_select_below_predicted_floor():
    reg, pol, corpus, ent, tel = _fixtures()
    for variant in ("B", "C"):
        for task in corpus["tasks"]:
            for q in (0.60, 0.70, 0.80):
                rec = V.route_variant(variant, task, reg, ent, tel, pol, "mature", q_min=q)
                if not rec["abstained"]:
                    chosen = next(c for c in rec["scored"] if c["model"] == rec["selected"])
                    assert chosen["predicted_quality"] >= q


def test_B_C_abstain_when_no_model_meets_floor():
    reg, pol, corpus, ent, tel = _fixtures()
    # a floor of 1.0 is unreachable -> must abstain on (almost) every task
    abst = sum(1 for task in corpus["tasks"]
               if V.route_variant("B", task, reg, ent, tel, pol, "mature", q_min=1.0)["abstained"])
    assert abst == len(corpus["tasks"])


# --- hard eligibility unchanged --------------------------------------------

def test_hard_eligibility_identical_across_variants():
    reg, pol, corpus, ent, tel = _fixtures()
    for task in corpus["tasks"]:
        base_rec = base.route(task, reg, ent, tel, pol, "mature", None)
        b = V.route_variant("B", task, reg, ent, tel, pol, "mature", q_min=0.0)  # floor 0 => no quality removal
        # with floor 0, B's eligible set must equal the baseline eligible set
        assert set(b["eligible"]) == set(base_rec["eligible"])


# --- determinism + dispatch ------------------------------------------------

def test_deterministic_tiebreak():
    reg, pol, corpus, ent, tel = _fixtures()
    for task in corpus["tasks"]:
        r1 = V.route_variant("C", task, reg, ent, tel, pol, "mature", q_min=0.70)
        r2 = V.route_variant("C", task, reg, ent, tel, pol, "mature", q_min=0.70)
        assert r1["selected"] == r2["selected"] and r1["fallback_chain"] == r2["fallback_chain"]


def test_unknown_variant_raises():
    reg, pol, corpus, ent, tel = _fixtures()
    with pytest.raises(ValueError):
        V.route_variant("Z", corpus["tasks"][0], reg, ent, tel, pol, "mature")


def test_B_equals_C_on_this_corpus():
    """Documented finding: lexicographic (C) == min-cost (B) on this corpus."""
    reg, pol, corpus, ent, tel = _fixtures()
    same = 0
    for task in corpus["tasks"]:
        b = V.route_variant("B", task, reg, ent, tel, pol, "mature", q_min=0.70)
        c = V.route_variant("C", task, reg, ent, tel, pol, "mature", q_min=0.70)
        same += (b["selected"] == c["selected"] and b["abstained"] == c["abstained"])
    assert same == len(corpus["tasks"])
