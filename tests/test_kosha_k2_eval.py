"""CPU tests for the Kosha K2 quality-eval decision engine (pure aggregate/decide; no GPU, no model).
Pre-reg: docs/KOSHA_K2_QUALITY_EVAL_PREREG.md."""
import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

from conscious_generation import eval_kosha_quality as E   # noqa: E402


def _sc(pfc=1.0, rda=1.0, fact=1.0, mir=1.0, clar=1.0, conf=1.0, terse=0.0, of=0.0, wc=40.0):
    return {"primary_frame_correct": pfc, "rejected_domain_avoidance": rda, "factuality_preserved": fact,
            "must_include_recall": mir, "answer_clarity_proxy": clar, "depth_conformance": conf,
            "terse": terse, "over_framing": of, "word_count": wc}


def _per(w_conf, wk_conf, *, slices=E.LEVELS, n_each=3, **w_over):
    """Build per_example where W has w_conf depth-conformance and W+K has wk_conf, across slices."""
    rows = []
    for lvl in slices:
        for i in range(n_each):
            rows.append({"id": f"{lvl}{i}", "slice": lvl, "intended_depth": lvl,
                         "scores": {"W": _sc(conf=w_conf, **w_over), "WK": _sc(conf=wk_conf)}})
    return rows


def test_aggregate_and_counts():
    per = _per(0.2, 0.9)
    m = E.aggregate(per)
    assert m["W"]["depth_conformance"] == 0.2 and m["WK"]["depth_conformance"] == 0.9
    assert m["W"]["n"] == len(per) and m["WK"]["n"] == len(per)


def test_adds_quality_when_conformance_improves():
    per = _per(0.2, 0.9)                                   # W+K improves conformance on every level
    rep = E.run(per)
    assert rep["decision"] == "CG_KOSHA_K2_ADDS_QUALITY"
    assert rep["depth_conformance_delta"]["excludes_zero"] and rep["slices_improved"] >= 2


def test_safe_no_gain_when_equal():
    per = _per(0.7, 0.7)                                   # identical -> guardrails pass, no gain
    rep = E.run(per)
    assert rep["decision"] == "CG_KOSHA_K2_SAFE_NO_QUALITY_GAIN"


def test_degrades_frame_dominates_even_with_quality_gain():
    # W+K improves conformance but TANKS primary_frame_correct -> guardrail dominates
    per = []
    for lvl in E.LEVELS:
        for i in range(3):
            w = _sc(conf=0.2, pfc=1.0)
            wk = _sc(conf=0.95, pfc=0.5)                   # frame collapse
            per.append({"id": f"{lvl}{i}", "slice": lvl, "intended_depth": lvl,
                        "scores": {"W": w, "WK": wk}})
    rep = E.run(per)
    assert rep["decision"] == "CG_KOSHA_K2_DEGRADES_FRAME"


def test_degrades_recall():
    per = []
    for lvl in E.LEVELS:
        for i in range(3):
            per.append({"id": f"{lvl}{i}", "slice": lvl, "intended_depth": lvl,
                        "scores": {"W": _sc(conf=0.2, mir=1.0), "WK": _sc(conf=0.9, mir=0.5)}})
    rep = E.run(per)
    assert rep["decision"] == "CG_KOSHA_K2_DEGRADES_RECALL"


def test_insufficient_power():
    per = _per(0.2, 0.9, slices=("annamaya",), n_each=3)  # only 3 per arm
    rep = E.run(per)
    assert rep["decision"] == "CG_KOSHA_K2_INSUFFICIENT_POWER"


def test_decision_labels_and_markdown():
    expected = {"CG_KOSHA_K2_ADDS_QUALITY", "CG_KOSHA_K2_SAFE_NO_QUALITY_GAIN",
                "CG_KOSHA_K2_FRAME_ONLY_BEST", "CG_KOSHA_K2_DEGRADES_FRAME",
                "CG_KOSHA_K2_DEGRADES_FACTUALITY", "CG_KOSHA_K2_DEGRADES_RECALL",
                "CG_KOSHA_K2_INSUFFICIENT_POWER", "CG_KOSHA_K2_ENV_UNAVAILABLE"}
    assert set(E.DECISIONS) == expected
    md = E.to_markdown(E.run(_per(0.2, 0.9)))
    assert "frame-only (W) vs frame+Kosha (W+K)" in md and "DECISION:" in md


def test_guardrail_blocks_quality_when_overframing_rises():
    # conformance up + CI>0, but W+K raises over-framing beyond tolerance -> not ADDS_QUALITY
    per = []
    for lvl in E.LEVELS:
        for i in range(3):
            per.append({"id": f"{lvl}{i}", "slice": lvl, "intended_depth": lvl,
                        "scores": {"W": _sc(conf=0.2, of=0.0), "WK": _sc(conf=0.9, of=0.5)}})
    rep = E.run(per)
    assert rep["decision"] != "CG_KOSHA_K2_ADDS_QUALITY"
