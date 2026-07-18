"""CPU tests for the surface-feature baseline guardrail (numpy, torch-free).
Pre-reg: docs/CG_GUNA_VRITTI_LABEL_SOURCE_PREREG.md §7. No model, no training, no signal claim.
"""
import json
import sys
from pathlib import Path

import numpy as np

_SCR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

from conscious_generation_training import surface_baseline as SB           # noqa: E402
from conscious_generation_training import eval_guna_vritti_probe as EV     # noqa: E402


def test_surface_features_deterministic_and_complete():
    f1 = SB.surface_features("q?", "1. First do this. 2. Then do that.")
    f2 = SB.surface_features("q?", "1. First do this. 2. Then do that.")
    assert f1 == f2                                                # deterministic
    assert set(f1) == set(SB.SURFACE_FEATURE_NAMES)
    assert f1["list_markers"] >= 1 and f1["imperative_density"] > 0
    multiline = SB.surface_features("q", "1. a\n2. b\n3. c")        # line-start markers counted
    assert multiline["list_markers"] >= 3
    assert SB.surface_features("q", "I don't know, cannot help.")["refusal_density"] > 0


def test_best_single_feature_detects_perfect_surface_predictor():
    # label = "is a list" -> list_markers feature predicts it perfectly -> AUROC 1.0, flagged confounded
    rows = []
    for i in range(20):
        is_list = i % 2 == 0
        resp = ("1. a\n2. b\n3. c" if is_list else "A short prose sentence without any list at all here.")
        rows.append({"prompt": "q", "response": resp,
                     "labels": {"guna": [int(is_list), 0, 0, None, None, None], "vritti": "pramana"}})
    rep = SB.surface_baseline(rows)
    sat = rep["guna"]["SATTVA"]
    assert sat["surface_auroc"] >= 0.85 and sat["confounded"] is True
    assert "guna:SATTVA" in rep["surface_confounded_labels"]


def test_non_predictable_label_not_confounded():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(40):
        resp = "Some neutral text of moderate length describing a topic in plain words here today."
        rows.append({"prompt": "q", "response": resp,
                     "labels": {"guna": [int(rng.integers(0, 2)), 0, 0, None, None, None],
                                "vritti": "pramana"}})
    rep = SB.surface_baseline(rows)
    # identical text -> features can't separate a random label -> not confounded
    assert rep["guna"]["SATTVA"]["confounded"] is False


def test_masked_guna_dims_skipped():
    rows = [{"prompt": "q", "response": "x y z w v", "labels": {"guna": [1, 0, 0, None, None, None],
             "vritti": "pramana"}} for _ in range(10)]
    rep = SB.surface_baseline(rows)
    for dim in ("VELOCITY", "ACCEL", "STABLE"):
        assert rep["guna"][dim] == {"masked": True}            # null dims not scored


def test_probe_beats_surface_helper():
    assert SB.probe_beats_surface(0.80, 0.70) is True          # beats by >= margin 0.05
    assert SB.probe_beats_surface(0.72, 0.70) is False         # within margin
    assert SB.probe_beats_surface(None, 0.70) is None


def test_logistic_oof_returns_none_on_tiny_n():
    X = np.random.default_rng(0).random((6, len(SB.SURFACE_FEATURE_NAMES)))
    y = np.array([0, 1, 0, 1, 0, 1])
    assert SB._logistic_oof_auroc(X, y, k=5) is None           # n < 2k -> None (no overfit nonsense)


def test_eval_integrates_baseline_on_fixture(tmp_path):
    # the committed synthetic fixture: eval --data attaches the surface baseline section
    fx = _SCR.parent / "data" / "cg_training" / "guna_vritti_synthetic_fixture.jsonl"
    EV.main(["--dry-run", "--data", str(fx), "--out", str(tmp_path / "e.json"),
             "--report", str(tmp_path / "e.md")])
    rep = json.loads((tmp_path / "e.json").read_text())
    assert "surface_baseline" in rep and "surface_confounded_labels" in rep
    md = (tmp_path / "e.md").read_text()
    assert "anti-circularity GUARDRAIL" in md
    # still synthetic -> no signal claim
    assert rep["decision"] == "CG_GUNA_VRITTI_SYNTHETIC_ONLY"


def test_baseline_only_mode(tmp_path):
    fx = _SCR.parent / "data" / "cg_training" / "guna_vritti_synthetic_fixture.jsonl"
    rc = EV.main(["--baseline-only", "--data", str(fx), "--out", str(tmp_path / "b.json")])
    assert rc == 0
    rep = json.loads((tmp_path / "b.json").read_text())
    assert "surface_baseline" in rep and "decision" not in rep   # guardrail only, no probe decision
