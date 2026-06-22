"""CPU tests for the supervised-observation EVALUATOR on SYNTHETIC labeled rows — no embeddings, no
traces, no GPU. Exercises join/keymap, loud failures, metric/CI math, the rater-count gate, and every
SO_* decision label. No runtime/Phase 1-3 change (the evaluator only reads + scores).
"""
import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy")
from csr_match_filter import eval_supervised_observation as EV   # noqa: E402

TH = {"min_pos": 4}   # tiny corpora in tests: lower the power floor so we exercise the real decisions


def _row(iid, sid, arm, *, rewrite, feat, baseline, raters=None, scales=None):
    human = {k: None for k in EV.LABEL_FIELDS}
    human["rewrite_needed"] = rewrite
    if scales:
        human.update(scales)
    return {"item_id": iid, "source_id": sid, "arm": arm, "group": sid,
            "prompt": "q?", "answer": "a", "human": human,
            "human_raters": raters or [human],
            "baseline_needs_rewrite": baseline,
            "feat": {"inv_match": feat.get("inv_match"), "audit_severity": feat.get("sev", 0.0),
                     "traj_drift": feat.get("traj", 0.0), "guna_quality": feat.get("guna", 0.0)},
            "availability": {"match": feat.get("inv_match") is not None}}


# ============================ join / keymap / loud failures ====================================== #
def test_join_labels_keymap_traces():
    labels = {"opaqueA": EV.parse_label_row({"rewrite_needed": "yes"}),
              "opaqueB": EV.parse_label_row({"rewrite_needed": "no"})}
    keymap = {"opaqueA": {"source_id": "ord_001", "arm": "base", "category": "x", "trace_index": 0},
              "opaqueB": {"source_id": "ord_001", "arm": "framed", "category": "x", "trace_index": 1}}
    answers = {"ord_001": {"base": "ans base", "framed": "ans framed"}}
    prompts = {"ord_001": "what?"}
    rows, rep = EV.join_rows([labels], keymap, answers, prompts)
    assert rep["n_joined"] == 2 and rep["excluded"] == []
    by = {r["item_id"]: r for r in rows}
    assert by["opaqueA"]["source_id"] == "ord_001" and by["opaqueA"]["arm"] == "base"
    assert by["opaqueA"]["answer"] == "ans base" and by["opaqueB"]["answer"] == "ans framed"


def test_missing_keymap_row_fails_loud():
    labels = {"ghost": EV.parse_label_row({"rewrite_needed": "yes"})}
    with pytest.raises(KeyError, match="not in keymap"):
        EV.join_rows([labels], {}, {}, {})


def test_missing_human_label_excluded_explicitly():
    labels = {"opaqueA": EV.parse_label_row({"rewrite_needed": ""}),       # blank primary label
              "opaqueB": EV.parse_label_row({"rewrite_needed": "yes"})}
    keymap = {"opaqueA": {"source_id": "s", "arm": "base", "category": "x", "trace_index": 0},
              "opaqueB": {"source_id": "s", "arm": "framed", "category": "x", "trace_index": 1}}
    answers = {"s": {"base": "a", "framed": "b"}}
    prompts = {"s": "q"}
    rows, rep = EV.join_rows([labels], keymap, answers, prompts)
    assert rep["n_joined"] == 1
    assert rep["excluded"] == [{"item_id": "opaqueA", "reason":
                                "missing primary human label rewrite_needed"}]


def test_missing_trace_answer_fails_loud():
    labels = {"opaqueA": EV.parse_label_row({"rewrite_needed": "yes"})}
    keymap = {"opaqueA": {"source_id": "s", "arm": "base", "category": "x", "trace_index": 0}}
    with pytest.raises(KeyError, match="no trace answer"):
        EV.join_rows([labels], keymap, {"s": {"framed": "b"}}, {"s": "q"})


# ============================ metric / CI math ================================================== #
def test_confusion_and_prf():
    m = EV._metrics([True, True, False, False], [True, False, False, True])
    assert m["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert m["precision"] == 0.5 and m["recall"] == 0.5 and m["f1"] == 0.5
    assert m["false_rewrite_rate"] == 0.5 and m["missed_rewrite_rate"] == 0.5
    assert m["n_pos"] == 2 and m["n_neg"] == 2


def test_bootstrap_delta_shape():
    truth = [True, True, False, False, True, False, True, False]
    cand = [True, True, False, False, True, False, True, False]   # perfect
    base = [True, False, False, False, False, False, False, False]
    d = EV.bootstrap_delta_f1(truth, cand, base, n_boot=300, seed=1)
    assert set(d) == {"delta_f1", "ci_low", "ci_high", "excludes_zero"}
    assert d["ci_low"] <= d["delta_f1"] <= d["ci_high"]
    assert d["delta_f1"] > 0 and d["excludes_zero"] is True


def test_cohen_kappa_and_spearman():
    assert EV.cohen_kappa([True, True, False, False], [True, True, False, False]) == 1.0
    assert EV.cohen_kappa([True, False, True, False], [False, True, False, True]) is not None
    assert EV.spearman([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0


def test_overlap_detection():
    assert EV.set_overlap(("audit_severity", "inv_match")) == []         # disjoint
    coll = EV.set_overlap(("audit_severity", "traj_drift", "guna_quality"))
    assert coll == []                                                    # the canonical families ARE disjoint
    # an intentionally double-counted custom set collides on the frame-movement findings
    EV.FEATURE_FINDINGS["audit_framemove_dup"] = EV.FEATURE_FINDINGS["traj_drift"]
    try:
        coll2 = EV.set_overlap(("audit_framemove_dup", "traj_drift"))
        assert coll2 and coll2[0]["shared_findings"]
    finally:
        del EV.FEATURE_FINDINGS["audit_framemove_dup"]


# ============================ decision labels =================================================== #
def _corpus_traj_class_missed_by_gate(n=12):
    """Truth driven by frame-movement (traj_drift); the narrow gate fires only on severity -> misses it.
    The DerivedVrittiTrajectory family (D/F) recovers it -> a clean, non-overlapping improvement."""
    rows = []
    for t in range(n):
        sid = f"wd{t}"
        # half the items: traj-only failures (gate misses); other half: clean negatives
        traj = 1.0 if t % 2 == 0 else 0.0
        rewrite = traj > 0
        rows.append(_row(f"o{t}", sid, "base", rewrite=rewrite,
                         feat={"sev": 0.0, "traj": traj, "guna": 0.0, "inv_match": 0.0},
                         baseline=False))                    # gate never fires -> misses every positive
    return rows


def test_decision_add_signal_two_raters():
    rows = _corpus_traj_class_missed_by_gate(16)
    # supply a concordant 2nd rater so agreement is high and ADD_SIGNAL is allowed
    for r in rows:
        r["human_raters"] = [r["human"], dict(r["human"])]
    rep = EV.run(rows, n_splits=4, seed=0, single_rater=False, thresholds=TH)
    assert rep["decision"] == "SO_DIAGNOSTICS_ADD_SIGNAL"
    assert rep["best_set"] in ("D_audit_traj", "F_all")
    assert rep["predictor_sets"][rep["best_set"]]["delta_f1_vs_baseline"]["excludes_zero"]


def test_single_rater_cannot_add_signal():
    rows = _corpus_traj_class_missed_by_gate(16)
    rep = EV.run(rows, n_splits=4, seed=0, single_rater=True, thresholds=TH)
    # identical signal, but a lone rater downgrades to NO_INCREMENTAL (descriptive only)
    assert rep["decision"] == "SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE"
    assert rep["single_rater_descriptive_only"] is True
    assert rep["decision_reasons"].get("note") == "single_rater_descriptive_only"


def test_insufficient_rater_agreement():
    rows = _corpus_traj_class_missed_by_gate(16)
    for i, r in enumerate(rows):                              # 2nd rater disagrees on rewrite_needed
        other = dict(r["human"]); other["rewrite_needed"] = not r["human"]["rewrite_needed"]
        r["human_raters"] = [r["human"], other]
    rep = EV.run(rows, n_splits=4, seed=0, single_rater=False, thresholds=TH)
    assert rep["decision"] == "SO_INSUFFICIENT_RATER_AGREEMENT"


def test_insufficient_label_power():
    rows = [_row(f"o{t}", f"w{t}", "base", rewrite=(t == 0),
                 feat={"sev": 1.0 if t == 0 else 0.0}, baseline=(t == 0)) for t in range(10)]
    rep = EV.run(rows, n_splits=3, seed=0, single_rater=True, thresholds={"min_pos": 5})
    assert rep["decision"] == "SO_INSUFFICIENT_LABEL_POWER"


def test_no_incremental_value():
    # gate already matches truth (mediocre-to-good); diagnostics add nothing clearing the gate
    rows = []
    for t in range(16):
        sev = 1.0 if t % 2 == 0 else 0.0
        rewrite = sev > 0
        rows.append(_row(f"o{t}", f"w{t}", "base", rewrite=rewrite,
                         feat={"sev": sev, "traj": 0.0, "guna": 0.0, "inv_match": 0.0},
                         baseline=rewrite))                   # gate == truth
    rep = EV.run(rows, n_splits=4, seed=0, single_rater=True, thresholds=TH)
    assert rep["decision"] in ("SO_AUDIT_GATE_VALIDATED", "SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE")
    assert rep["baseline_needs_rewrite"]["f1"] >= 0.6   # perfect gate -> VALIDATED branch


def test_audit_gate_validated_branch():
    rows = []
    for t in range(16):
        sev = 1.0 if t % 2 == 0 else 0.0
        rewrite = sev > 0
        rows.append(_row(f"o{t}", f"w{t}", "base", rewrite=rewrite,
                         feat={"sev": sev}, baseline=rewrite))
    rep = EV.run(rows, n_splits=4, seed=0, single_rater=True, thresholds=TH)
    assert rep["decision"] == "SO_AUDIT_GATE_VALIDATED"


def test_audit_gate_fails_human_labels():
    # truth driven by an UNOBSERVED cause; gate fires oppositely -> poor baseline F1, no feature helps
    rows = []
    for t in range(16):
        rewrite = t % 2 == 0
        rows.append(_row(f"o{t}", f"w{t}", "base", rewrite=rewrite,
                         feat={"sev": 0.0, "traj": 0.0, "guna": 0.0, "inv_match": 0.0},
                         baseline=(not rewrite)))             # gate is anti-correlated with truth
    rep = EV.run(rows, n_splits=4, seed=0, single_rater=True, thresholds=TH)
    assert rep["decision"] == "SO_AUDIT_GATE_FAILS_HUMAN_LABELS"
    assert rep["baseline_needs_rewrite"]["f1"] < 0.40


def test_term_overlap_invalid():
    # a clean traj-driven improvement, but force the BEST set to be overlap-invalid by aliasing a family
    rows = _corpus_traj_class_missed_by_gate(16)
    for r in rows:
        r["human_raters"] = [r["human"], dict(r["human"])]
    saved = dict(EV.PREDICTOR_SETS)
    saved_ff = dict(EV.FEATURE_FINDINGS)
    try:
        # add a feature that double-counts the frame-movement findings already in traj_drift
        EV.FEATURE_FINDINGS["traj_dup"] = EV.FEATURE_FINDINGS["traj_drift"]
        EV.PREDICTOR_SETS.clear()
        EV.PREDICTOR_SETS["G_overlap"] = ("audit_severity", "traj_drift", "traj_dup")
        # mirror traj into the dup feature on every row
        for r in rows:
            r["feat"]["traj_dup"] = r["feat"]["traj_drift"]
        rep = EV.run(rows, n_splits=4, seed=0, single_rater=False, thresholds=TH)
        assert rep["decision"] == "SO_TERM_OVERLAP_INVALID"
    finally:
        EV.PREDICTOR_SETS.clear(); EV.PREDICTOR_SETS.update(saved)
        EV.FEATURE_FINDINGS.clear(); EV.FEATURE_FINDINGS.update(saved_ff)


# ============================ output + decision-label set ======================================= #
def test_outputs_written_and_label_set(tmp_path):
    assert set(EV.DECISIONS) == {
        "SO_AUDIT_GATE_VALIDATED", "SO_DIAGNOSTICS_ADD_SIGNAL", "SO_DIAGNOSTICS_NO_INCREMENTAL_VALUE",
        "SO_AUDIT_GATE_FAILS_HUMAN_LABELS", "SO_INSUFFICIENT_RATER_AGREEMENT",
        "SO_INSUFFICIENT_LABEL_POWER", "SO_TERM_OVERLAP_INVALID"}
    rows = _corpus_traj_class_missed_by_gate(16)
    rep = EV.run(rows, n_splits=4, seed=0, single_rater=True, thresholds=TH)
    md = EV.to_markdown(rep)
    assert "Supervised Observation" in md and "DECISION:" in md
    (tmp_path / "o.json").write_text(json.dumps(rep))
    (tmp_path / "o.md").write_text(md)
    assert json.loads((tmp_path / "o.json").read_text())["decision"] == rep["decision"]


def test_no_runtime_modules_imported():
    # the evaluator must not pull in generation/runtime wrappers at import time
    import csr_match_filter.eval_supervised_observation as M  # noqa: F401
    bad = [m for m in sys.modules if m.endswith("bliss_gate") or m.endswith("signal_gov")]
    assert bad == []
