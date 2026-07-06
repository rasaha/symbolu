#!/usr/bin/env python3
"""Synthetic-fixture tests for score_b1_3_concrete_object_llm.py.

No real judge outputs are scored. Each test fabricates a small judge-output set that should drive the scorer to
a specific terminal label, verifying the decision logic. Structure, not validated meaning.

Run: python3 test_score_b1_3_concrete_object_llm.py
"""
import json, os, tempfile, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score_b1_3_concrete_object_llm as S

COMPS = S.REQUIRED_COMPARISONS
CONTROLS_NON_MID_FAR = ["A_real_vs_R_scrambled", "A_real_vs_R_random", "A_real_vs_X_neutral",
                        "A_real_vs_semantic_only_baseline", "A_real_vs_R_deranged_near"]

def _row(item, comp, a_won, model="modelA", family="tool", tier="primary", invalid=False,
         parse="ok", stratum=None):
    # A_real fixed on left; selected 'A' iff a_won
    other = comp.replace("A_real_vs_", "")
    return {
        "item_id": item, "comparison_id": comp, "target_word": item.split("#")[0],
        "primary_or_secondary_or_diagnostic": tier, "object_family": family,
        "model_id": model, "arm_left": "A_real", "arm_right": other,
        "selected_option": ("A" if a_won else "B"), "parse_status": parse,
        "invalid_flag": invalid, "deranged_stratum": stratum,
    }

def build(judge_rows, style_pass=True):
    d = tempfile.mkdtemp()
    stim = os.path.join(d, "stim.jsonl"); jud = os.path.join(d, "jud.jsonl")
    aud = os.path.join(d, "aud.json"); con = os.path.join(d, "con.json")
    oj = os.path.join(d, "out.json"); om = os.path.join(d, "out.md")
    open(stim, "w").write("")  # stimuli hashed only; content not required for scoring
    with open(jud, "w") as f:
        for r in judge_rows:
            f.write(json.dumps(r) + "\n")
    subpass = bool(style_pass)
    audit = {
        "style_parity_audit": {"pass": subpass}, "style_tell_audit": {"pass": subpass, "balanced_accuracy": 0.38},
        "denotation_leakage_audit": {"pass": subpass}, "quality_parity_audit": {"pass": subpass},
        "semantic_baseline_audit": {"pass": subpass}, "overall_audit_pass": subpass,
    }
    open(aud, "w").write(json.dumps(audit))
    open(con, "w").write(json.dumps({"artifact": "contract_stub"}))
    rep = S.score(stim, jud, aud, con, oj, om)
    return rep

def gen(win_rates, n_per=40, model_split=None, tier="primary"):
    """win_rates: {comparison: p_a_real_win}. Produces n_per rows per comparison with that many A_real wins."""
    rows = []
    models = model_split or ["modelA", "modelB"]
    for comp, p in win_rates.items():
        wins = round(p * n_per)
        for i in range(n_per):
            a_won = i < wins
            model = models[i % len(models)]
            rows.append(_row(f"w{i}#{comp}", comp, a_won, model=model, tier=tier))
    return rows

# ------------------------------------------------------------------ tests
def test_strong():
    wr = {c: 0.85 for c in COMPS}  # A_real dominates every arm incl. near
    rep = build(gen(wr))
    assert rep["terminal_label"] == "LLM_OBJECT_MODULATION_SIGNAL_EARNED_STRONG", rep["terminal_label"]

def test_category_limited():
    wr = {c: 0.85 for c in COMPS}
    wr["A_real_vs_R_deranged_near"] = 0.50  # ties near -> not word-specific
    rep = build(gen(wr))
    assert rep["terminal_label"] == "LLM_OBJECT_MODULATION_SIGNAL_EARNED_CATEGORY_LIMITED", rep["terminal_label"]

def test_semantic_baseline_explains():
    wr = {c: 0.85 for c in COMPS}
    wr["A_real_vs_semantic_only_baseline"] = 0.45  # baseline beats/matches A_real
    rep = build(gen(wr))
    assert rep["terminal_label"] == "LLM_OBJECT_MODULATION_SEMANTIC_BASELINE_EXPLAINS", rep["terminal_label"]

def test_null_mid_fail():
    wr = {c: 0.85 for c in COMPS}
    wr["A_real_vs_R_deranged_mid"] = 0.50  # mid at chance -> NULL
    rep = build(gen(wr))
    assert rep["terminal_label"] == "LLM_OBJECT_MODULATION_NULL", rep["terminal_label"]

def test_invalid_run():
    wr = {c: 0.85 for c in COMPS}
    rows = gen(wr, n_per=40)
    # inject >10% invalids
    for i in range(60):
        rows.append(_row(f"bad{i}#A_real_vs_R_deranged_mid", "A_real_vs_R_deranged_mid", True, invalid=True))
    rep = build(rows)
    assert rep["terminal_label"] == "LLM_OBJECT_MODULATION_INVALID_RUN", rep["terminal_label"]

def test_style_confounded():
    wr = {c: 0.85 for c in COMPS}
    rep = build(gen(wr), style_pass=False)  # audits did not pass
    assert rep["terminal_label"] == "LLM_OBJECT_MODULATION_STYLE_CONFOUNDED", rep["terminal_label"]

def test_missing_comparison_invalid():
    wr = {c: 0.85 for c in COMPS if c != "A_real_vs_R_random"}  # drop one required comparison
    rep = build(gen(wr))
    assert rep["terminal_label"] == "LLM_OBJECT_MODULATION_INVALID_RUN", rep["terminal_label"]

def test_selection_mapping():
    # left/right and A/B both map correctly
    assert S.selected_side("A") == "left" and S.selected_side("B") == "right"
    assert S.selected_side("left") == "left" and S.selected_side("right") == "right"
    assert S.selected_side("garbage") is None and S.selected_side(None) is None

def test_model_family_dominance_null():
    # A_real beats all arms, but ALL wins come from one model family -> dominance -> NULL
    wr = {c: 0.85 for c in COMPS}
    rows = []
    for comp, p in wr.items():
        n = 40; wins = round(p * n)
        for i in range(n):
            a_won = i < wins
            # every A_real win attributed to modelA; losses to modelB
            model = "modelA" if a_won else "modelB"
            rows.append(_row(f"w{i}#{comp}", comp, a_won, model=model))
    rep = build(rows)
    assert rep["single_model_family_dominates"] is True, rep["single_model_family_dominates"]
    assert rep["terminal_label"] == "LLM_OBJECT_MODULATION_NULL", rep["terminal_label"]

def test_ci_helpers():
    lo, hi, p = S.wilson_interval(34, 40)
    assert 0 < lo < p < hi < 1
    cplo, cphi = S.clopper_pearson(34, 40)
    assert 0 < cplo < 0.85 < cphi < 1
    # Holm monotonicity
    adj = S.holm({"a": 0.01, "b": 0.02, "c": 0.5})
    assert adj["a"] <= adj["b"] <= adj["c"]

def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} tests passed")
    return passed == len(tests)

if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
