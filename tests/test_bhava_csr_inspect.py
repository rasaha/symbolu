"""CPU tests for the per-example Bhava+CSR trace viewer (inspect_bhava_csr_sample.py)."""

import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy", reason="numpy required for the trace viewer")
import numpy as np  # noqa: E402
import importlib  # noqa: E402

INS = importlib.import_module("inspect_bhava_csr_sample")


def _make_run(tmp_path, n=60, with_csr=True):
    rng = np.random.RandomState(0)
    y = (rng.rand(n) > 0.5).astype(int)
    res = (y[:, None] * 2 - 1) * 1.0 + rng.randn(n, 12) * 0.6
    arr = dict(
        bhava=rng.randn(n, 12).astype(np.float32),
        bhava_entropy=np.abs(rng.randn(n, 1)).astype(np.float32),
        state_bhava=rng.randn(n, 12).astype(np.float32),
        state_bhava_entropy=np.abs(rng.randn(n, 1)).astype(np.float32),
        state32=rng.randn(n, 32).astype(np.float32),
        hidden_pooled=rng.randn(n, 4096).astype(np.float32),
        delta_bhava=(rng.randn(n, 12) * 1e-3).astype(np.float32),
        delta_bhava_norm=np.abs(rng.randn(n, 1) * 1e-3).astype(np.float32),
    )
    if with_csr:
        arr.update(
            context_r_ctx=rng.randn(n, 16).astype(np.float32),
            semantic=rng.randn(n, 4096).astype(np.float32),
            resonance_combined=res.astype(np.float32),
            phoneme_bhava=np.abs(res[:, :6]).astype(np.float32),
            vritti_consonant=np.abs(res[:, 6:]).astype(np.float32),
        )
    d = tmp_path / "run_csr"
    d.mkdir()
    np.savez_compressed(d / "features.npz", **arr)
    (d / "labels.json").write_text(json.dumps(
        [{"id": f"e{i}", "label": int(y[i]), "label_type": "correctness"} for i in range(n)]))
    (d / "config.json").write_text(json.dumps({"model_id": "stub"}))
    return d, y


def test_load_run_files(tmp_path):
    d, y = _make_run(tmp_path)
    arrays, idx, yy, ids, scores, cfg, avail = INS.load_run(d, "correctness")
    assert len(ids) == len(y) and list(yy) == list(y)
    # csr sets get scored per example
    for s in ("hidden_only", "state_bhava_only", "resonance_combined", "csr_static"):
        assert s in scores and len(scores[s]) == len(y)


def test_missing_model_output_handled(tmp_path):
    d, y = _make_run(tmp_path)
    arrays, idx, yy, ids, scores, cfg, avail = INS.load_run(d, "correctness")
    # no --data join -> trace must still render with an 'unavailable' note, not crash
    txt = INS.trace_one(None, 0, arrays, idx, yy, ids, scores, data_by_id={})
    assert "unavailable" in txt and "Prediction scores" in txt


def test_surprising_selection(tmp_path):
    d, y = _make_run(tmp_path)
    arrays, idx, yy, ids, scores, cfg, avail = INS.load_run(d, "correctness")
    pos = INS.select("surprising", yy, scores, limit=5)
    assert len(pos) <= 5
    # every 'surprising' example: hidden and resonance disagree about 0.5
    for p in pos:
        assert (scores["hidden_only"][p] >= 0.5) != (scores["resonance_combined"][p] >= 0.5)


def test_top_correct_incorrect(tmp_path):
    d, y = _make_run(tmp_path)
    arrays, idx, yy, ids, scores, cfg, avail = INS.load_run(d, "correctness")
    tc = INS.select("top_correct", yy, scores, 5)
    ti = INS.select("top_incorrect", yy, scores, 5)
    assert all(yy[p] == 1 for p in tc) and all(yy[p] == 0 for p in ti)


def test_agreement_no_nan(tmp_path):
    d, y = _make_run(tmp_path)
    arrays, idx, yy, ids, scores, cfg, avail = INS.load_run(d, "correctness")
    # no probe score is NaN (the substring 'nan' in 'resonance'/'dominant' is harmless)
    assert not any(np.isnan(np.asarray(v)).any() for v in scores.values())
    txt = INS.trace_one(None, 0, arrays, idx, yy, ids, scores, data_by_id={})
    assert "entropy: nan" not in txt and "/ nan" not in txt


def test_report_sections_present(tmp_path):
    d, y = _make_run(tmp_path)
    arrays, idx, yy, ids, scores, cfg, avail = INS.load_run(d, "correctness")
    data_by_id = {"e0": {"prompt": "Q", "expected": "6", "metadata": {"generation": "6"}}}
    txt = INS.trace_one(None, 0, arrays, idx, yy, ids, scores, data_by_id)
    for section in ("State-Bhava", "Phoneme-Bhava", "Vritti", "Resonance", "Context",
                    "Semantic", "Agreement", "Prediction scores", "Model output"):
        assert section in txt


def test_runs_without_csr_features(tmp_path):
    # legacy run (no CSR keys) must still load + trace (csr sets simply absent)
    d, y = _make_run(tmp_path, with_csr=False)
    arrays, idx, yy, ids, scores, cfg, avail = INS.load_run(d, "correctness")
    assert "hidden_only" in scores and "csr_static" not in scores
    txt = INS.trace_one(None, 0, arrays, idx, yy, ids, scores, data_by_id={})
    assert "Prediction scores" in txt
