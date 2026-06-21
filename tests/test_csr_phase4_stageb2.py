"""CPU tests for Phase 4 Stage-B2 (learned Bhava incremental test).

Synthetic activations only, no GPU. Validates: the pre-declared 7-class object-mode mapping; the
target-orthogonal supervision plumbing; in-fold direction fitting (no test leakage); the surface
n-gram baseline; the strict incremental gate and every decision label (INSUFFICIENT / LEAKAGE /
COLLAPSE / ADDS_SIGNAL / HIDDEN_ONLY_SUFFICIENT / NO_INCREMENTAL); and end-to-end that a label that
tracks the object-mode is flagged as leakage, while an orthogonal no-signal case yields
HIDDEN_ONLY_SUFFICIENT. No Bhava wiring, no Phase 1-3 change.
"""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

np = pytest.importorskip("numpy")

from csr_match_filter import phase4_stageb2_bhava as B2        # noqa: E402


# ---- taxonomy mapping ----------------------------------------------------------------------------

def test_primary_mode_mapping():
    assert B2.primary_mode("doctor", []) == "person_role"
    assert B2.primary_mode("mercury", []) == "substance_element"
    assert B2.primary_mode("apple", []) == "biological_natural"
    assert B2.primary_mode("bank", []) == "place_system_context"
    assert B2.primary_mode("antivirus", []) == "artifact_tool"
    assert B2.primary_mode("zzz_unknown", ["medicine"]) == "person_role"   # domain fallback
    assert B2.primary_mode("zzz_unknown", ["zzz"]) == "other_unknown"
    assert set(B2.PRIMARY_MODES) == {"person_role", "substance_element", "artifact_tool",
                                     "abstract_role", "biological_natural", "place_system_context",
                                     "other_unknown"}


def test_ngram_features_shape_and_determinism():
    q = ["a doctor heals patients", "explain mercury the element"]
    a = B2.ngram_features(q, dim=64)
    b = B2.ngram_features(q, dim=64)
    assert a.shape == (2, 64) and np.array_equal(a, b) and a.sum() > 0


# ---- in-fold direction fitting -------------------------------------------------------------------

def test_fit_mode_directions_train_only_and_shapes():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((80, 20))
    mode = np.array(["a"] * 30 + ["b"] * 30 + ["c"] * 20, dtype=object)
    X[mode == "a", 0] += 3.0; X[mode == "b", 1] += 3.0; X[mode == "c", 2] += 3.0
    tr = np.arange(60)                                          # only a/b in train
    dirs = B2.fit_mode_directions(X[tr], mode[tr], min_count=8)
    assert dirs["W"].shape[1] == 20 and set(dirs["modes"]) == {"a", "b"}   # 'c' absent from train
    read = B2.bhava_read(dirs, X)                              # projects ALL rows w/ TRAIN params
    assert read.shape == (80, len(dirs["modes"]))
    # rare mode (below min_count in train) is dropped -> no leakage from singletons
    dirs2 = B2.fit_mode_directions(X[:40], mode[:40], min_count=8)
    assert "c" not in dirs2["modes"]


# ---- gate + decision logic -----------------------------------------------------------------------

def _delta(d, excl):
    return {"delta": d, "ci_low": d - 0.01, "ci_high": d + 0.01, "excludes_zero": excl}


def test_gate_passes():
    good = {"delta_vs_hidden": _delta(0.08, True), "delta_vs_random": _delta(0.07, True),
            "delta_vs_ngram": _delta(0.09, True)}
    assert B2.gate_passes(good)
    for k in ("delta_vs_hidden", "delta_vs_random", "delta_vs_ngram"):
        bad = dict(good); bad[k] = _delta(0.02, False)
        assert not B2.gate_passes(bad)


def test_decide_target_all_labels():
    cfg_pass = [{"gate": True}] * 6
    cfg_fail = [{"gate": False}] * 6
    assert B2.decide_target(0.5, 5.0, cfg_pass, 0.72, 5, 200) == "PHASE4_INSUFFICIENT_LABEL_POWER"
    assert B2.decide_target(0.85, 5.0, cfg_pass, 0.72, 200, 200) == "PHASE4_BHAVA_LEAKAGE_SUSPECTED"
    assert B2.decide_target(0.5, 1.5, cfg_pass, 0.72, 200, 200) == "PHASE4_BHAVA_COLLAPSE"
    assert B2.decide_target(0.5, 5.0, cfg_pass, 0.72, 200, 200) == "PHASE4_BHAVA_ADDS_SIGNAL"
    assert B2.decide_target(0.5, 5.0, cfg_fail, 0.72, 200, 200) == "PHASE4_HIDDEN_ONLY_SUFFICIENT"
    assert B2.decide_target(0.5, 5.0, cfg_fail, 0.55, 200, 200) == "PHASE4_BHAVA_NO_INCREMENTAL_SIGNAL"


def test_evaluate_bhava_no_added_value_when_orthogonal():
    rng = np.random.default_rng(1)
    n, D = 200, 40
    Xrich = rng.standard_normal((n, D))
    y = (Xrich[:, 0] + rng.standard_normal(n) * 0.4 > 0).astype(int)   # signal in a TOP dim
    mode = np.array([["a", "b", "c", "d"][i % 4] for i in range(n)], dtype=object)
    for j, mclass in enumerate("abcd"):
        Xrich[mode == mclass, 20 + j] += 3.0                  # mode signal, orthogonal to y
    groups = np.array([f"t{i % 20}" for i in range(n)])
    Xng = rng.standard_normal((n, 32))
    r = B2.evaluate_bhava(Xrich, y, groups, mode, Xng, hidden_dim=8, n_splits=4, seed=0, n_boot=150)
    assert set(r["auroc"]) == {"hidden", "bhava", "hb", "random", "ngram"}
    assert not B2.gate_passes(r)                              # orthogonal Bhava adds nothing


# ---- end-to-end -----------------------------------------------------------------------------------

def _write_run(tmp_path, leak=False, seed=0):
    rng = np.random.default_rng(seed)
    doms = ["medicine", "biology", "chemistry", "finance", "programming"]   # -> 5 modes
    rows, Xs, layers, D = [], [], list(range(6)), 200
    for t in range(60):
        term = f"wd{chr(97 + t // 26)}{chr(97 + t % 26)}qx"
        dom = doms[t % 5]
        mode_idx = t % 5
        for arm in ("base", "framed"):
            if leak:
                y = int(rng.random() < (0.9 if mode_idx == 0 else 0.1))   # label tracks the mode
            else:
                y = (t // 5) % 2                                          # balanced WITHIN each mode
            cube = rng.standard_normal((6, D))
            cube[3, :4] += (2.0 if y else -2.0)               # failure signal in top dims
            cube[3, 50 + mode_idx] += 3.0                     # mode signal in a higher dim
            rows.append({"id": term, "arm": arm, "query": term,
                         "category": "drift_adversarial" if t % 2 else "ordinary",
                         "csr_frame_summary": {"primary": [dom]},
                         "labels": {"frame_violation": bool(y), "rejected_domain_leak": False,
                                    "audit_fail": bool(y), "secondary_promoted": False}})
            Xs.append(cube)
    rd = tmp_path / "csr_phase4_v3"
    rd.mkdir(parents=True)
    np.savez_compressed(rd / "phase4_activations.npz", X=np.stack(Xs, 0).astype("float32"),
                        layers=np.array(layers),
                        ids=np.array([r["id"] for r in rows], dtype=object),
                        arms=np.array([r["arm"] for r in rows], dtype=object))
    (rd / "phase4_metadata.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    return rd


def _run(rd, monkeypatch):
    monkeypatch.setattr(sys, "argv",
                        ["x", "--run-dir", str(rd), "--targets", "frame_violation",
                         "--secondary", "", "--exploratory", "", "--rich-dim", "64",
                         "--hidden-dims", "16,32", "--seeds", "0,1", "--n-boot", "120"])
    B2.main()
    return json.loads((rd / "phase4_stageb2_bhava.json").read_text())


def test_end_to_end_hidden_only_sufficient(tmp_path, monkeypatch):
    rep = _run(_write_run(tmp_path, leak=False), monkeypatch)
    assert rep["overall_primary_verdict"] == "PHASE4_HIDDEN_ONLY_SUFFICIENT"
    fv = rep["targets"]["frame_violation"]
    assert fv["orthogonality_auroc"] <= 0.60                  # supervision orthogonal to target
    assert "by_row_type" in fv


def test_end_to_end_leakage_when_mode_tracks_target(tmp_path, monkeypatch):
    rep = _run(_write_run(tmp_path, leak=True), monkeypatch)
    fv = rep["targets"]["frame_violation"]
    assert fv["orthogonality_auroc"] > 0.60
    assert fv["decision"] == "PHASE4_BHAVA_LEAKAGE_SUSPECTED"
    assert rep["overall_primary_verdict"] == "PHASE4_BHAVA_LEAKAGE_SUSPECTED"
