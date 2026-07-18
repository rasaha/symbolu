"""CPU tests for Phase 4D — Guna/Vritti-controlled residual Bhava. Synthetic only, no GPU.

Validates the residualization math (orthonormal project-out, train-fold-only), the leakage gate, the
strict incremental gate, every PHASE4D_* decision label, and end-to-end: a planted residual-Bhava
signal (after removing Guna/Vritti) yields ADDS_SIGNAL, target leakage in Vritti supervision yields
LEAKAGE_SUSPECTED. No Bhava wiring, no Phase 1-3 change.
"""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

np = pytest.importorskip("numpy")

from csr_match_filter import phase4d_residual_bhava as D       # noqa: E402


# ---- residualization math ------------------------------------------------------------------------

def test_orthobasis_and_residualize_project_out():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((50, 8))
    g = np.zeros(8); g[0] = 1.0
    v = np.zeros(8); v[1] = 1.0
    B = D.orthobasis([g, v])
    assert B.shape == (2, 8) and np.allclose(B @ B.T, np.eye(2), atol=1e-8)
    R = D.residualize(X, B)
    assert np.allclose(R @ B.T, 0.0, atol=1e-8)               # residual orthogonal to removed dirs
    # variance along removed dims is gone, other dims preserved
    assert R[:, 0].var() < 1e-8 and R[:, 1].var() < 1e-8
    assert np.allclose(R[:, 2:], X[:, 2:])


def test_residualize_empty_basis_is_identity():
    X = np.ones((4, 5))
    assert np.array_equal(D.residualize(X, np.zeros((0, 5))), X)


# ---- gate + decision -----------------------------------------------------------------------------

def _d(delta, excl):
    return {"delta": delta, "ci_low": delta - 0.01, "ci_high": delta + 0.01, "excludes_zero": excl}


def test_gate_passes():
    good = {"delta_vs_hidden": _d(0.08, True), "delta_vs_random": _d(0.07, True),
            "delta_vs_ngram": _d(0.06, True)}
    assert D.gate_passes(good)
    for k in good:
        bad = dict(good); bad[k] = _d(0.02, False)
        assert not D.gate_passes(bad)


def test_decide_all_labels():
    cfg_pass = [{"gate": True}] * 6
    cfg_fail = [{"gate": False}] * 6
    assert D.decide(0.5, 5, cfg_pass, 0.72, 0.5, 5, 200) == "PHASE4D_INSUFFICIENT_LABEL_POWER"
    assert D.decide(0.85, 5, cfg_pass, 0.72, 0.5, 200, 200) == "PHASE4D_LEAKAGE_SUSPECTED"
    assert D.decide(0.5, 1.5, cfg_pass, 0.72, 0.5, 200, 200) == "PHASE4D_RESIDUAL_BHAVA_COLLAPSE"
    assert D.decide(0.5, 5, cfg_pass, 0.72, 0.5, 200, 200) == "PHASE4D_RESIDUAL_BHAVA_ADDS_SIGNAL"
    assert D.decide(0.5, 5, cfg_fail, 0.76, 0.75, 200, 200) == "PHASE4D_GUNA_VRITTI_SUFFICIENT"
    assert D.decide(0.5, 5, cfg_fail, 0.76, 0.55, 200, 200) == "PHASE4D_HIDDEN_ONLY_SUFFICIENT"
    assert D.decide(0.5, 5, cfg_fail, 0.55, 0.50, 200, 200) == "PHASE4D_RESIDUAL_BHAVA_NO_INCREMENTAL_SIGNAL"


def test_vritti_label_excludes_target():
    rows = [{"labels": {"frame_violation": True, "rejected_domain_leak": False,
                        "secondary_promoted": True, "answer_too_generic": False,
                        "factuality_suspected": False}}]
    # evaluating frame_violation -> Vritti must NOT use frame_violation (uses secondary/rejected)
    assert D.vritti_label(rows, "frame_violation")[0] == 1          # secondary_promoted True
    rows2 = [{"labels": {"frame_violation": True, "rejected_domain_leak": False,
                         "secondary_promoted": False, "answer_too_generic": False,
                         "factuality_suspected": False}}]
    assert D.vritti_label(rows2, "frame_violation")[0] == 0         # frame_violation excluded


def test_evaluate_residual_returns_all_feature_sets():
    rng = np.random.default_rng(1)
    n, Dn = 160, 24
    Xrich = rng.standard_normal((n, Dn))
    y = rng.integers(0, 2, n)
    guna = rng.integers(0, 2, n); vritti = rng.integers(0, 2, n)
    groups = np.array([f"t{i % 20}" for i in range(n)])
    Xng = rng.standard_normal((n, 16))
    r = D.evaluate_residual(Xrich, y, guna, vritti, groups, Xng, 8, 6, 4, 0, 120)
    assert set(r["auroc"]) == {"hidden", "guna", "vritti", "gv", "residual", "hb", "random", "ngram"}


# ---- end-to-end ----------------------------------------------------------------------------------

def _write_run(tmp_path, scenario, n_terms=120, seed=0):
    rng = np.random.default_rng(seed)
    rows, Xs, layers, Dn = [], [], list(range(6)), 40
    for t in range(n_terms):
        term = f"wd{chr(97 + t // 26)}{chr(97 + t % 26)}qx"
        for arm in ("base", "framed"):
            z0, z1, z2 = (rng.integers(0, 2, 3) * 2 - 1)       # guna, vritti, target latents
            cube = rng.standard_normal((6, Dn))
            for L in range(6):                                 # signal in EVERY layer (layer-agnostic)
                cube[L, 0] += 4.0 * z0                         # Guna dim (high variance)
                cube[L, 1] += 4.0 * z1                         # Vritti dim (high variance)
                cube[L, 2] += 3.0 * z2                         # target dim (below top-2 PCs)
            fv = z2 > 0
            sp = z1 > 0
            if scenario == "leakage":
                sp = fv                                        # Vritti == target -> leakage
            rows.append({"id": term, "arm": arm, "query": term,
                         "category": "drift_adversarial" if t % 2 else "ordinary",
                         "labels": {"frame_violation": bool(fv), "rejected_domain_leak": False,
                                    "secondary_promoted": bool(sp), "answer_too_generic": bool(z0 > 0),
                                    "factuality_suspected": False, "audit_fail": bool(fv)}})
            Xs.append(cube)
    rd = tmp_path / "csr_phase4_v3"
    rd.mkdir(parents=True)
    np.savez_compressed(rd / "phase4_activations.npz", X=np.stack(Xs, 0).astype("float32"),
                        layers=np.array(layers),
                        ids=np.array([r["id"] for r in rows], dtype=object),
                        arms=np.array([r["arm"] for r in rows], dtype=object))
    (rd / "phase4_metadata.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    return rd


def _run(rd, monkeypatch, hidden_dims="2"):
    monkeypatch.setattr(sys, "argv",
                        ["x", "--run-dir", str(rd), "--targets", "frame_violation",
                         "--secondary", "", "--exploratory", "", "--rich-dim", "16",
                         "--hidden-dims", hidden_dims, "--resid-dim", "8", "--seeds", "0,1,2",
                         "--n-boot", "120"])
    D.main()
    return json.loads((rd / "phase4d_residual_bhava.json").read_text())


def test_end_to_end_residual_bhava_adds_signal(tmp_path, monkeypatch):
    # target lives below the top-2 hidden PCs; appears only after removing Guna/Vritti -> residual adds
    rep = _run(_write_run(tmp_path, "adds"), monkeypatch)
    fv = rep["targets"]["frame_violation"]
    assert fv["leak_auroc"] <= 0.70                            # Guna/Vritti orthogonal to target
    assert fv["decision"] == "PHASE4D_RESIDUAL_BHAVA_ADDS_SIGNAL"
    assert rep["overall_primary_verdict"] == "PHASE4D_RESIDUAL_BHAVA_ADDS_SIGNAL"


def test_end_to_end_leakage_when_vritti_is_target(tmp_path, monkeypatch):
    rep = _run(_write_run(tmp_path, "leakage"), monkeypatch)
    fv = rep["targets"]["frame_violation"]
    assert fv["leak_auroc"] > 0.70
    assert fv["decision"] == "PHASE4D_LEAKAGE_SUSPECTED"
