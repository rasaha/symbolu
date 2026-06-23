"""Tests for the Guna-sigmoid + Vritti auxiliary-training harness.
Torch-free parts (config, metrics, decision, schema, provenance) run on CPU here; torch nn.Module parts
(projector/heads shapes, sigmoid range, finite loss) use importorskip('torch') -> run on the pod.
No runtime integration, no agentic governance, Bhava not a training target.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_SCR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

from conscious_generation_training import guna_vritti_heads as H        # noqa: E402
from conscious_generation_training import guna_vritti_metrics as M      # noqa: E402
from conscious_generation_training import eval_guna_vritti_probe as EV  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent


# ---- formula provenance + no-invention (13) -----------------------------------------------------
def test_formulas_sourced_not_invented():
    assert H.formula_available() is True
    assert H.FORMULA_PROVENANCE["invented"] is False
    assert "sigmoid 6-D" in H.FORMULA_PROVENANCE["guna"]
    assert "softmax 5-class" in H.FORMULA_PROVENANCE["vritti"]
    assert H.GUNA_DIM == 6 and H.VRITTI_DIM == 5 and H.SYMBOLIC_DIM == 32


def test_formula_unavailable_path_fails_loud():
    # if the formula were ever marked unavailable, decide() must return FORMULA_UNAVAILABLE (no invention)
    assert M.decide(formula_ok=False, label_source="real", guna={}, vritti={}) == \
        "CG_GUNA_VRITTI_FORMULA_UNAVAILABLE"


# ---- config defaults: probe mode, base frozen, Bhava/LoRA/LM off (10,12) ------------------------
def test_config_probe_defaults_and_boundaries():
    cfg = H.SymbolicHeadConfig()
    assert cfg.train_base_model is False and cfg.use_lora is False and cfg.loss_lm_weight == 0.0
    assert cfg.guna_dim == 6 and cfg.vritti_dim == 5
    cfg.assert_probe_boundaries()                       # no raise
    with pytest.raises(AssertionError):
        H.SymbolicHeadConfig(train_base_model=True).assert_probe_boundaries()


def test_no_bhava_training_target():
    # Bhava is a slice in the 32-D layout but is NOT a head/loss target in this harness
    assert "bhava" in H.SLICES
    cfg = H.SymbolicHeadConfig()
    assert not hasattr(cfg, "loss_bhava_weight")
    # no Bhava label is consumed by the loss path (only guna/vritti)
    src = (_SCR / "conscious_generation_training" / "guna_vritti_heads.py").read_text().lower()
    assert "bhava_labels" not in src and "def bhavahead" not in src


# ---- metrics (numpy; CPU) (Guna AUROC/BCE, Vritti CE/F1) ----------------------------------------
def test_guna_metrics_shapes_and_auroc():
    n = 60
    rng = np.random.default_rng(0)
    labels = (rng.random((n, 6)) > 0.5).astype(int)
    # scores correlated with labels -> AUROC should be > 0.5
    scores = labels * 0.6 + rng.random((n, 6)) * 0.4
    g = M.guna_metrics(scores, labels)
    assert set(g["per_dim_auroc"]) == set(H.GUNA_NAMES)
    assert g["macro_auroc"] > 0.6 and 0.0 <= g["bce"] < 5.0
    assert set(g["label_prevalence"]) == set(H.GUNA_NAMES)


def test_vritti_metrics_confusion_and_f1():
    n = 50
    rng = np.random.default_rng(1)
    y = rng.integers(0, 5, n)
    probs = np.full((n, 5), 0.05)
    probs[np.arange(n), y] = 0.8                          # near-perfect -> high acc/F1
    probs = probs / probs.sum(1, keepdims=True)
    v = M.vritti_metrics(probs, y)
    assert v["accuracy"] > 0.9 and v["macro_f1"] > 0.8
    assert len(v["confusion"]) == 5 and set(v["per_class_f1"]) == set(H.VRITTI_NAMES)


# ---- decision labels (9, synthetic-only) --------------------------------------------------------
def test_decision_synthetic_only():
    g = {"macro_auroc": 0.9}; v = {"macro_f1": 0.9, "per_class_f1": {i: 0 for i in range(5)}}
    assert M.decide(formula_ok=True, label_source="synthetic", guna=g, vritti=v) == \
        "CG_GUNA_VRITTI_SYNTHETIC_ONLY"


def test_decision_learns_vs_no_signal_on_real():
    pcf = {n: 0 for n in H.VRITTI_NAMES}
    learn = M.decide(formula_ok=True, label_source="real",
                     guna={"macro_auroc": 0.8}, vritti={"macro_f1": 0.5, "per_class_f1": pcf})
    none = M.decide(formula_ok=True, label_source="real",
                    guna={"macro_auroc": 0.52}, vritti={"macro_f1": 0.18, "per_class_f1": pcf})
    assert learn == "CG_GUNA_VRITTI_LEARNS_SIGNAL" and none == "CG_GUNA_VRITTI_NO_LEARNABLE_SIGNAL"


def test_decision_label_set():
    assert set(H.DECISIONS) == {
        "CG_GUNA_VRITTI_HARNESS_READY", "CG_GUNA_VRITTI_FORMULA_UNAVAILABLE",
        "CG_GUNA_VRITTI_SHAPE_ONLY_PASS", "CG_GUNA_VRITTI_SYNTHETIC_ONLY",
        "CG_GUNA_VRITTI_NO_LEARNABLE_SIGNAL", "CG_GUNA_VRITTI_LEARNS_SIGNAL",
        "CG_GUNA_VRITTI_ENV_UNAVAILABLE"}


# ---- eval dry-run produces report + synthetic-only (8) ------------------------------------------
def test_eval_dry_run_report(tmp_path):
    rc = EV.main(["--dry-run", "--out", str(tmp_path / "e.json"), "--report", str(tmp_path / "e.md")])
    assert rc == 0
    rep = json.loads((tmp_path / "e.json").read_text())
    assert rep["decision"] == "CG_GUNA_VRITTI_SYNTHETIC_ONLY"
    assert "Guna/Vritti probe" in (tmp_path / "e.md").read_text()
    assert set(rep["guna_metrics"]["per_dim_auroc"]) == set(H.GUNA_NAMES)


# ---- synthetic fixture marked (9) ---------------------------------------------------------------
def test_synthetic_fixture_marked():
    fx = _ROOT / "data" / "cg_training" / "guna_vritti_synthetic_fixture.jsonl"
    rows = [json.loads(l) for l in fx.read_text().splitlines() if l.strip()]
    assert rows and all("SYNTHETIC_FIXTURE_ONLY_NOT_VALIDATION" in r["id"] for r in rows)
    for r in rows:
        assert len(r["labels"]["guna"]) == 6 and r["labels"]["vritti"] in \
            ["pramana", "viparyaya", "vikalpa", "nidra", "smriti"]
        assert r["metadata"]["source"] == "synthetic"


# ---- 11. no agentic governance / runtime integration imported ----------------------------------
def test_no_runtime_or_agentic_integration():
    import conscious_generation_training.guna_vritti_heads  # noqa: F401
    bad = [m for m in sys.modules if "agentic" in m or "mcp_gateway" in m]
    assert bad == []


# ================= torch-gated (run on the pod; skipped where torch is absent) ===================
def test_torch_projector_and_head_shapes():
    torch = pytest.importorskip("torch")
    from conscious_generation_training.guna_vritti_heads import SymbolicHeadBundle
    cfg = H.SymbolicHeadConfig()
    bundle = SymbolicHeadBundle(cfg)
    out = bundle(torch.randn(3, 7, cfg.hidden_size))       # [B,T,H] -> pooled
    assert list(out["state"].shape) == [3, 32]
    assert list(out["guna_scores"].shape) == [3, 6]
    assert bool((out["guna_scores"] >= 0).all() and (out["guna_scores"] <= 1).all())  # sigmoid range
    assert list(out["vritti_probs"].shape) == [3, 5]
    assert torch.allclose(out["vritti_probs"].sum(-1), torch.ones(3), atol=1e-4)       # softmax


def test_torch_combined_loss_weights_and_finite():
    torch = pytest.importorskip("torch")
    from conscious_generation_training.guna_vritti_heads import SymbolicHeadBundle
    cfg = H.SymbolicHeadConfig(loss_guna_weight=2.0, loss_vritti_weight=0.0)
    bundle = SymbolicHeadBundle(cfg)
    out = bundle(torch.randn(4, cfg.hidden_size))
    gl = (torch.rand(4, 6) > 0.5).float(); vl = torch.randint(0, 5, (4,))
    total, parts = bundle.loss(out, gl, vl)
    assert torch.isfinite(total)
    # vritti weight 0 -> total == 2*guna_bce within fp tolerance
    assert abs(parts["total"] - 2.0 * parts["guna_bce"]) < 1e-4
