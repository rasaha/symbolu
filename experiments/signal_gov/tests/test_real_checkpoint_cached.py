"""
test_real_checkpoint_cached.py — stock-checkpoint extraction (offline).

Validates the real_checkpoint_cached plumbing with a deterministic mock backend
(no torch): real logit-entropy + top-1 confidence vary per scenario; the proxy-state
vritti/JEPA path runs; the feature cache round-trips and is re-evaluated offline.

NO success claim: the mock backend is label-blind (so the ablation should NOT improve),
and the hidden-state→32-D projection is an unvalidated PROXY (vritti/JEPA may be
degenerate). Only `entropy` and `text_confidence` are genuinely model-derived here.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from experiments.signal_gov.configs import CONFIG_ORDER
from experiments.signal_gov.dataset import load_dataset
from experiments.signal_gov.features import (
    FEATURE_FIELDS,
    MockHFBackend,
    RealCheckpointCachedExtractor,
    hidden_to_state_proxy,
    predictive_entropy,
    top1_confidence,
)
from experiments.signal_gov.run_experiment import run


def _agentic_available() -> bool:
    try:
        import agentic.agentic_framework.sovereign_bridge  # noqa: F401
        return True
    except Exception:
        return False


agentic_required = pytest.mark.skipif(
    not _agentic_available(),
    reason="proxy vritti/JEPA path needs the in-repo agentic framework (numpy; no torch)",
)


# ----- pure helpers (numpy only) -----

def test_predictive_entropy_bounds():
    assert predictive_entropy(np.zeros(64)) == pytest.approx(1.0)        # uniform -> max
    peaked = np.full(64, -50.0); peaked[0] = 50.0
    assert predictive_entropy(peaked) == pytest.approx(0.0, abs=1e-6)    # one-hot -> 0
    assert predictive_entropy([1.0]) == 0.0                              # degenerate


def test_top1_confidence_bounds():
    assert top1_confidence(np.zeros(8)) == pytest.approx(1.0 / 8)        # uniform
    peaked = np.full(8, -50.0); peaked[0] = 50.0
    assert top1_confidence(peaked) == pytest.approx(1.0, abs=1e-6)


def test_hidden_to_state_proxy_shape_and_range():
    proxy = hidden_to_state_proxy(np.linspace(-3, 3, 256), dim=32)
    assert len(proxy) == 32
    assert all(0.0 <= v <= 1.0 for v in proxy)
    assert hidden_to_state_proxy(np.linspace(-3, 3, 256), dim=32) == proxy  # deterministic
    assert hidden_to_state_proxy(np.zeros(64), dim=32) == [0.5] * 32        # flat -> mid


def test_mock_backend_deterministic_and_scenario_varying():
    b = MockHFBackend()
    o1 = b.encode("prompt A")
    o2 = b.encode("prompt A")
    o3 = b.encode("prompt B")
    assert np.allclose(o1.logits, o2.logits)            # deterministic
    assert not np.allclose(o1.logits, o3.logits)        # varies by prompt


def test_missing_hf_model_raises_without_torch():
    # use_mock=False + no model name -> ValueError before any torch import.
    with pytest.raises(ValueError, match="hf_model"):
        RealCheckpointCachedExtractor(use_mock=False, hf_model=None)


# ----- end-to-end with mock backend (needs agentic pkg; NO torch) -----

@agentic_required
def test_real_checkpoint_cached_runs_mock_no_torch():
    sc = load_dataset("pilot")
    feats = RealCheckpointCachedExtractor(use_mock=True).extract_all(sc)
    assert len(feats) == len(sc)
    # real, scenario-varying signals
    assert len({round(f.entropy, 4) for f in feats}) > 1
    assert len({round(f.text_confidence, 4) for f in feats}) > 1
    for f in feats:
        assert set(f.to_dict().keys()) == set(FEATURE_FIELDS)         # schema parity
        assert "real_checkpoint_cached" in f.provenance
        assert "mock-hf" in f.provenance and "PROXY" in f.provenance
        assert all(0.0 <= v <= 1.0 for v in
                   (f.entropy, f.coherence, f.vritti_risk, f.jepa_disagreement))


@agentic_required
def test_cache_roundtrip_and_offline_eval(tmp_path):
    # run once (writes features.jsonl), then re-evaluate C1-C4 offline from the cache.
    r1 = run("real_checkpoint_cached", "pilot", tmp_path / "extract",
             hf_mock=True, n_boot=50, make_plots=False)
    cache = tmp_path / "extract" / "features.jsonl"
    assert cache.exists() and cache.stat().st_size > 0
    rows = [json.loads(ln) for ln in cache.read_text().splitlines() if ln.strip()]
    assert len(rows) == r1.results["dataset"]["n_total"]

    r2 = run("cached", "pilot", tmp_path / "eval",
             features_path=str(cache), n_boot=50, make_plots=False)
    for name in CONFIG_ORDER:
        assert r2.results["configs"][name]["auroc"] == pytest.approx(
            r1.results["configs"][name]["auroc"], abs=1e-9)  # identical offline


@agentic_required
def test_report_marks_pilot_proxy_no_claim(tmp_path):
    run("real_checkpoint_cached", "pilot", tmp_path, hf_mock=True, n_boot=50)
    report = (tmp_path / "experiment_report.md").read_text()
    assert "PROXY" in report
    assert "No benchmark success claim" in report


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("torch") is not None,
    reason="torch present: skip the no-torch ImportError check (would try to load weights)",
)
def test_real_backend_requires_torch():
    # With torch absent, requesting a real checkpoint must raise a clear ImportError.
    with pytest.raises(ImportError, match="torch"):
        RealCheckpointCachedExtractor(use_mock=False, hf_model="sshleifer/tiny-gpt2")
